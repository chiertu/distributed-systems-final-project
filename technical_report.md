## Overview

### Structure of the App:
The app has 4 modules:
- **Redis Service**: An in-memory database which can store the state of the application and results
- **Web Service**: Built using FAST API and run using uvicorn
  - APIs Built and Tested:
    - _**/register_function**_: Registers the given function
    - _**/execute_function**_: Request the execution of an already registered function
    - _**/status/<task_id>**_: Gets the status of the task ID
    - _**/result/<task_id>**_: Gets the result of the task ID
- **Task Dispatcher**: Responsible for distributing work to workers, either local/pull/push
  - Runs in three modes:
    - Local: Task Dispatcher and worker pool are co-located
    - Pull: (REP socket) The workers request for tasks when they are free
    - Push: (ROUTER socket) Whenever a task is ready, it is pushed to the least busy workers
- **Workers**: Executes the function and returns the results back to the task dispatcher
  - Runs in three modes:
    - Local: Local pool of worker processes
    - Pull: (REQ socket) Workers responsible for checking if they are free and requesting and executing tasks (also return results)
    - Push: (DEALER socket) Task Dispatcher keeps track of how busy a worker is and pushes tasks to them

### File Structure:
- main.py (FAAS service)
- response_classes.py (Base classes used as responses in FAAS service)
- redis_store.py (Class to interact with redis)
- protocol.py (Message Class, Abstract class for Worker)
- pull_worker.py
- push_worker.py
- task.py (Task and Function Class)
- task_dispatcher.py (Local, Pull and Push Task Dispatcher Classes)

## Implementation Details
### Communication Protocol: Message
In order to make the communication process standardized, we have implemented a `Message` class. This message will be used by all communicating parties. This protocol supports the following message types:
  - ACK
  - NO_TASK
  - NEW_TASK
  - REQUEST_TASK
  - RESULT_READY
  - REGISTRATION

### Communication Protocol: Task
To encapsulate all required data and methods related to the task together, we have created a `Task` class. A Task object is created when user submits an execution job and is used as part of the message in the task dispatcher and worker communication
  - Task is `QUEUED` when it is submitted to the service
  - Task is `RUNNING` when it leaves Dispatcher and going to a worker
  - Task is `COMPLETED`/`FAILED` when the result is received by Dispatcher 

### Mode: Local
**Task Dispatcher:**
- The task dispatcher runs a while loop and checks for new tasks in the redis channel named `tasks`. As soon as a task arrives, the task dispatcher submits the task to the local pool using `apply_async`. 
- The pool executes the task and then updates the result directly in the redis as part of the callback. The task dispatcher acts as a mere orchestrator between redis subscription and the pool.
```python
class LocalTaskDispatcher(TaskDispatcher):

    def __init__(self, no_of_workers, port: int = None):
        super().__init__(no_of_workers, port)
        self.pool = Pool(self.no_of_workers)

    @property
    def mode(self):
        return self.Mode.LOCAL

    def submit(self, task: Task):
        task.mark_running()
        self.pool.apply_async(task.execute, callback=lambda result: result.mark_termination())

    def execute(self):
        while True:
            task = redis_queue.read_channel()
            if task:
                self.submit(task)
```
**Worker**
- The workers of the Local pool are co-located with the task dispatcher and hence have access to redis directly. The pool executes the task asynchronously and updates the task result to redis directly.

### Mode: Pull
In the pull mode, it is assumed that the task dispatcher and the workers are not co-located and need to communicate over sockets using some pre-agreed upon protocols. In this model, a REQ-REP socket is being used which makes the communication synchronous.

**Task Dispatcher:**
- In case of the PULL Task Dispatcher, the task dispatcher polls the redis for new tasks and queues them locally. When a worker requests for a new task, the task dispatcher sends a new task (dequed from its local queue) to the worker over the socket.

- The PULL task dispatcher runs two threads, one to poll redis and the other to respond to the messages of workers. Based on the workers request, it sends an appropriate response.
- Message Types that the Task Dispatcher expects:
  - REGISTRATION: The worker is registering itself
  - REQUEST_TASK: The worker is requesting a new task
  - RESULT_READY: The worker has executed a task and is returning the response

- The `Message` class instance is used to communicate by the task dispatcher and the workers. The message is serialized using `dill` and sent over the socket as a string.
```python
class PullWorkerTaskDispatcher(TaskDispatcher):
    ...
    def respond_to_workers(self):
        while True:
            message = self.socket.recv_string()
            request = Message.retrieve(message)

            if request.message_type == Message.Type.REGISTRATION:
                response = self.create_message(Message.Type.ACK)
                self.socket.send_string(response.compose())

            elif request.message_type == Message.Type.REQUEST_TASK:
                if self.queue.empty():
                    message = self.create_message(Message.Type.NO_TASK)
                else:
                    task, message = self.queue.get(block=False)
                    task.mark_running()

                self.socket.send_string(message.compose())

            elif request.message_type == Message.Type.RESULT_READY:
                task = request.body
                task.mark_termination()

                response = self.create_message(Message.Type.ACK)
                self.socket.send_string(response.compose())

            else:
                raise NotImplementedError

    def execute(self):
      get_task_thread = threading.Thread(target=self.get_task)
      respond_to_workers_thread = threading.Thread(target=self.respond_to_workers)

      get_task_thread.start()
      respond_to_workers_thread.start()

      get_task_thread.join()
      respond_to_workers_thread.join()
    ...
```
**Worker**
- The worker begins by registering itself with the task dispatcher. It then runs two threads, one to request for tasks and the other to submit the results once they are ready. The PULL worker maintains a local queue to store the results which can be then submitted by the second thread. 
- Since both the threads use the same socket, a lock is being used to ensure that the messages are not corrupted during commute.
- In addition, the worker is also responsible for keeping track of its load and only ask for more tasks when it has the resources to process them (i.e when it is free). This is done using a lock-protected variable that tracks the currently active load on the pool

### Mode: Push
In the push mode, it is assumed that the task dispatcher and the workers are not co-located and hence need to communicate over the socket using pre-agreed upon protocol message. A DEALER-ROUTER pattern is used in this case, which makes the communication asynchronous and eliminates the need for ACK messages.

**Task Dispatcher**
- The PUSH task dispatcher polls the redis to get new tasks from redis. But, unlike PULL task dispatcher, it does not need to queue them locally but rather ships them immediately to the least busy worker. 
- In order to determine which worker is the least busy, it has the additional responsibility of tracking the currently active work load on each of the workers.
- The dispatcher runs two threads, one to get tasks from redis and the other to respond to the workers who are trying to submit results.
- The dispatcher uses a ROUTER socket and binds to the given port
```python
class PushWorkerTaskDispatcher(TaskDispatcher):
    ...
    def submit(self, task: Task):
        send_to = self.find_least_loaded_worker()
        task.mark_running()
        message = self.create_message(Message.Type.NEW_TASK, task)

        self.worker_load[send_to] += 1
        self.socket.send_multipart([str.encode(send_to), str.encode(message.compose())])

    def receive_from_workers(self):
        while True:
            identity, message_body = self.socket.recv_multipart()
            message = Message.retrieve(message_body.decode())

            if message.message_type == Message.Type.REGISTRATION:
                self.worker_load[identity.decode()] = 0
                print(f'Registered {identity.decode()}')
            elif message.message_type == Message.Type.RESULT_READY:
                task = message.body
                task.mark_termination()
                self.worker_load[identity.decode()] -= 1
            else:
                raise NotImplementedError
    ...
```
**Worker**
- The worker begins by registering itself to the task dispatcher. It is extremely important in this mode as the task dispatcher needs to know the existence of the worker to assign tasks to it.
- The PUSH worker, unlike the PULL worker, is relieved of the responsibility to track its load as the task dispatcher does it. 
- Just like the PULL worker, it runs two threads, one to accept tasks from the task dispatcher and the other to submit results back to the task dispatcher.


## Running the App
### Redis Installation
Reference: [Link](https://redis.io/docs/getting-started/installation/install-redis-on-linux/)
```shell
sudo apt install lsb-release
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list

sudo apt-get update
sudo apt-get install redis
```
```shell
# Command to start the redis server
$ redis-server
```
### MPCS FAAS Service
```shell
$ pip install fastapi uvicorn[standard]
```
```shell
# Command to start the MPCS FAAS Service using uvicorn
$ uvicorn main:app --reload
```
### Starting the Task Dispatcher
```shell
# Possible Modes: local/pull/push
$ python .\task_dispatcher.py -m local -w 2
$ python .\task_dispatcher.py -m pull -p 5555
$ python .\task_dispatcher.py -m push -p 5555
```
### Starting the Worker
```shell
$ python .\pull_worker.py 2 tcp://127.0.0.1:5555
$ python .\push_worker.py 2 tcp://127.0.0.1:5555
```
