import json
from typing import Any

import redis

from utils import deserialize, serialize


class Redis:

    CHANNEL = 'tasks'

    def __init__(self):
        self.r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(self.CHANNEL)

    def insert(self, key: str, value: dict):
        self.r.set(key, json.dumps(value))

    def read(self, key: str) -> dict:
        return json.loads(self.r.get(key))

    def update(self, key: str, value: dict):
        self.insert(key, value)

    def publish_to_channel(self, message: Any):
        if type(message) != str:
            message = serialize(message)

        self.r.publish(self.CHANNEL, message)

    def read_channel(self):
        message = self.pubsub.get_message(ignore_subscribe_messages=True)

        if message is not None:
            return deserialize(message['data'])
