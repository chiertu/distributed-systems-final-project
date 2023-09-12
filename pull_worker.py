import sys
from multiprocessing import Lock

from protocol import Message, Worker


class PullWorker(Worker):

    def __init__(self, number_of_processes, master):
        super().__init__(self.Mechanism.PULL, number_of_processes, master)
        self.load = 0
        self.load_lock = Lock()

    def handle_result(self, result):
        self.queue.put(result)
        self.load_lock.acquire()
        self.load -= 1
        self.load_lock.release()

    def get_task(self):
        while True:
            if self.load >= self.no_of_workers:
                print('Avoiding tasks for some time: Hands full!')
                continue

            self.lock.acquire()

            message = self.create_message(Message.Type.REQUEST_TASK)
            self.socket.send_string(message.compose())

            response = self.socket.recv_string()
            message = Message.retrieve(response)

            self.lock.release()

            if message.message_type == Message.Type.NO_TASK:
                continue

            self.submit_task(message.body)
            self.load_lock.acquire()
            self.load += 1
            self.load_lock.release()

    def submit_result(self, *args, **kwargs):
        while True:
            if not self.queue.empty():
                task = self.queue.get(block=False)
                self.lock.acquire()

                message = self.create_message(Message.Type.RESULT_READY, task)
                self.socket.send_string(message.compose())
                self.socket.recv_string()

                self.lock.release()

    def register(self):
        message = Message(Message.Type.REGISTRATION, self.id)
        self.socket.send_string(message.compose())

        # ACK message
        self.socket.recv_string()


if __name__ == '__main__':
    num_worker_processors = int(sys.argv[1])
    dispatcher_url = sys.argv[2]

    worker = PullWorker(num_worker_processors, dispatcher_url)
    worker.execute()
