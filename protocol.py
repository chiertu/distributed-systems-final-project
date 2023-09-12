import threading
import uuid
from abc import abstractmethod, ABC
from multiprocessing import Queue, Pool
from threading import Lock
from typing import Callable

import zmq

from task import Task
from utils import serialize, deserialize


class Message:
    class Type:
        ACK = 'ACK'
        NO_TASK = 'NO_TASK'
        NEW_TASK = 'NEW_TASK'
        REQUEST_TASK = 'REQUEST_TASK'
        RESULT_READY = 'RESULT_READY'
        REGISTRATION = 'REGISTRATION'

    def __init__(self, message_type, sender_id: str, body: Task = None):
        self.message_type = message_type
        self.sender = sender_id
        self.body = body

    def compose(self):
        return serialize(self)

    @classmethod
    def retrieve(cls, message_string):
        return deserialize(message_string)


class Worker(ABC):
    class Mechanism:
        PULL = 'PULL'
        PUSH = 'PUSH'

    def __init__(self, mechanism, number_of_processes, master):
        self.mechanism = mechanism
        self.no_of_workers = number_of_processes
        self.pool = Pool(processes=number_of_processes)
        self.queue = Queue()
        self.lock = Lock()
        self.master = master
        self.id = str(uuid.uuid4())
        self.socket = self.create_socket()

    @property
    def socket_type(self):
        return zmq.REQ if self.mechanism == self.Mechanism.PULL else zmq.DEALER

    def create_socket(self):
        context = zmq.Context()
        socket = context.socket(self.socket_type)
        socket.setsockopt_string(zmq.IDENTITY, self.id)

        socket.connect(self.master)
        return socket

    @abstractmethod
    def get_task(self):
        pass

    @abstractmethod
    def submit_result(self, *args, **kwargs):
        pass

    def handle_result(self, result):
        self.queue.put(result)

    def submit_task(self, task: Task):
        self.pool.apply_async(task.execute, callback=self.handle_result)

    def execute(self):
        self.register()

        get_task_thread = threading.Thread(target=self.get_task)
        submit_result_thread = threading.Thread(target=self.submit_result)

        get_task_thread.start()
        submit_result_thread.start()

        get_task_thread.join()
        submit_result_thread.join()

    @abstractmethod
    def register(self):
        pass

    def create_message(self, message_type, body: Task = None):
        message = Message(message_type, self.id, body)
        return message
