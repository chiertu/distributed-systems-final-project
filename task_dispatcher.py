import argparse
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from multiprocessing import Pool, Queue

import zmq

from protocol import Message
from task import Task, redis_queue


class TaskDispatcher(ABC):

    class Mode:
        LOCAL = 'local'
        PUSH = 'push'
        PULL = 'pull'

    @property
    @abstractmethod
    def mode(self):
        pass

    def __init__(self, no_of_workers, port=None):
        self.no_of_workers = no_of_workers
        self.port = port
        self.id = 'MASTER'

    @abstractmethod
    def submit(self, task: Task):
        pass

    @abstractmethod
    def execute(self):
        pass

    def create_message(self, message_type, body: Task = None):
        message = Message(message_type, self.id, body)
        return message


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


class PushWorkerTaskDispatcher(TaskDispatcher):

    def __init__(self, no_of_workers, port):
        super().__init__(no_of_workers, port)
        self.socket_type = zmq.ROUTER
        self.socket = self.create_socket()
        self.worker_load = defaultdict(int)

    def find_least_loaded_worker(self) -> str:
        return min(self.worker_load, key=self.worker_load.get)

    def create_socket(self):
        context = zmq.Context()
        socket = context.socket(self.socket_type)
        socket.setsockopt_string(zmq.IDENTITY, self.id)
        socket.bind(f'tcp://127.0.0.1:{self.port}')

        return socket

    @property
    def mode(self):
        return self.Mode.PUSH

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

    def get_task(self):
        while True:
            task = redis_queue.read_channel()
            if task:
                self.submit(task)

    def execute(self):
        get_task_thread = threading.Thread(target=self.get_task)
        receive_from_workers_thread = threading.Thread(target=self.receive_from_workers)

        get_task_thread.start()
        receive_from_workers_thread.start()

        get_task_thread.join()
        receive_from_workers_thread.join()


class PullWorkerTaskDispatcher(TaskDispatcher):

    def __init__(self, no_of_workers, port):
        super().__init__(no_of_workers, port)
        self.socket_type = zmq.REP
        self.socket = self.create_socket()
        self.queue = Queue()

    def create_socket(self):
        context = zmq.Context()
        socket = context.socket(self.socket_type)
        socket.bind(f'tcp://127.0.0.1:{self.port}')

        return socket

    @property
    def mode(self):
        return self.Mode.PULL

    def submit(self, task: Task):
        message = self.create_message(Message.Type.NEW_TASK, task)
        self.queue.put((task, message))

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

    def get_task(self):
        while True:
            task = redis_queue.read_channel()
            if task:
                self.submit(task)

    def execute(self):
        get_task_thread = threading.Thread(target=self.get_task)
        respond_to_workers_thread = threading.Thread(target=self.respond_to_workers)

        get_task_thread.start()
        respond_to_workers_thread.start()

        get_task_thread.join()
        respond_to_workers_thread.join()


def initiate_task_dispatcher(mode, no_of_workers, port):
    mapping = {
        TaskDispatcher.Mode.LOCAL: LocalTaskDispatcher,
        TaskDispatcher.Mode.PULL: PullWorkerTaskDispatcher,
        TaskDispatcher.Mode.PUSH: PushWorkerTaskDispatcher
    }

    task_dispatcher = mapping[mode](no_of_workers, port)
    task_dispatcher.execute()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-mode', type=str, help='Choose among local/pull/push')
    parser.add_argument('-port', type=int, help='The port for the PULL and PUSH mode')
    parser.add_argument('-workers', type=int, help='The number of workers to be spawned in the pool')

    arguments = parser.parse_args()

    initiate_task_dispatcher(arguments.mode, arguments.workers, arguments.port)
