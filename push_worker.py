import sys

import zmq
from zmq import Again

from protocol import Message, Worker


class PushWorker(Worker):
    
    def __init__(self, number_of_processes, master):
        super().__init__(self.Mechanism.PUSH, number_of_processes, master)

    def get_task(self):
        while True:
            self.lock.acquire()

            # Receive task
            try:
                request = self.socket.recv_string(flags=zmq.NOBLOCK)
                message = Message.retrieve(request)
                self.submit_task(message.body)
            except Again:
                pass

            self.lock.release()

    def submit_result(self, *args, **kwargs):
        while True:
            if not self.queue.empty():
                task = self.queue.get(block=False)
                self.lock.acquire()

                message = self.create_message(Message.Type.RESULT_READY, task)
                self.socket.send_string(message.compose())

                self.lock.release()

    def register(self):
        message = self.create_message(Message.Type.REGISTRATION)
        self.socket.send_string(message.compose())


if __name__ == '__main__':
    num_worker_processors = int(sys.argv[1])
    dispatcher_url = sys.argv[2]

    worker = PushWorker(num_worker_processors, dispatcher_url)
    worker.execute()
