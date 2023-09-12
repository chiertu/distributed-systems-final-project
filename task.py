import uuid

from redis_store import Redis
from utils import deserialize, serialize

redis_queue = Redis()


class Function:

    def __init__(self, name, payload):
        self.name = name
        self.payload = payload
        self.function_id = str(uuid.uuid4())

    def register(self):
        redis_queue.insert(self.function_id, self.db_record)

    @property
    def db_record(self):
        return {
            'name': self.name,
            'function_id': self.function_id,
            'payload': self.payload
        }


class Task:

    ENCODING = 'base64'

    class TaskState:
        QUEUED = 'QUEUED'
        RUNNING = 'RUNNING'
        COMPLETED = 'COMPLETED'
        FAILED = 'FAILED'

    def __init__(self, function_id, payload):
        self.function_id = str(function_id)
        self.payload = payload
        self.task_id = str(uuid.uuid4())
        self.status = self.TaskState.QUEUED
        self.result = ''

        self.function = self.get_function()

    def get_function(self):
        obj = redis_queue.read(self.function_id)['payload']
        return deserialize(obj)

    @classmethod
    def from_dict(cls, record):
        obj = cls(record['function_id'], record['payload'])
        for key, value in record.items():
            setattr(obj, key, value)

        return obj

    @classmethod
    def from_db(cls, task_id):
        task_data = redis_queue.read(task_id)
        task = cls.from_dict(task_data)

        return task

    def insert(self):
        redis_queue.insert(self.task_id, self.db_record)

    def execute(self):
        try:
            inputs = deserialize(self.payload)
            args = inputs[0]
            kwargs = inputs[1]

            self.result = self.function(*args, **kwargs)
            self.status = self.TaskState.COMPLETED

        except Exception as exc:
            self.status = self.TaskState.FAILED
            self.result = exc

        self.result = serialize(self.result)
        return self

    def mark_running(self):
        self.status = self.TaskState.RUNNING
        self.update()

    def mark_termination(self, *args, **kwargs):
        self.update()

    def update(self):
        redis_queue.update(self.task_id, self.db_record)

    @property
    def db_record(self):
        return {key: value for key, value in self.__dict__.items() if not callable(getattr(self, key))}
