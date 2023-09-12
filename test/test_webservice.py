import logging
import random
import time
import uuid

import requests

from .serialize import serialize, deserialize
from .utils import no_op, double, error_function, calculate_fibonacci, bruteforce_password, sleep_for_5s

base_url = 'http://127.0.0.1:8000'
valid_statuses = ['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED']
logger = logging.Logger('Test: Web-service', logging.DEBUG)


class FAAS:

    wait_time = 0.1  # (in seconds)

    class StatusCode:
        register = 201
        execute = 201
        status_check = 200
        result = 200

    class URLs:
        register = f'{base_url}/register_function'
        execute = f'{base_url}/execute_function'
        status_check = f'{base_url}/status/{{task_id}}'
        result = f'{base_url}/result/{{task_id}}'


class Base(FAAS):

    def register(self, function):
        data = {'name': str(uuid.uuid4()), 'payload': serialize(function)}
        response = requests.post(self.URLs.register, json=data)

        assert response.status_code == self.StatusCode.register
        assert 'function_id' in response.json()

        function_id = response.json().get('function_id')
        return function_id

    def execute(self, function_id, function_args):
        data = {'function_id': function_id, 'payload': serialize(function_args)}
        response = requests.post(self.URLs.execute, json=data)

        assert response.status_code == self.StatusCode.execute
        assert 'task_id' in response.json()

        task_id = response.json().get('task_id')
        return task_id

    def status(self, task_id):
        response = requests.get(self.URLs.status_check.format(task_id=task_id))
        response_data = response.json()

        assert response.status_code == 200
        assert response_data['task_id'] == task_id
        assert response_data['status'] in valid_statuses

    def result(self, task_id):
        result_url = self.URLs.result.format(task_id=task_id)
        for i in range(100):
            response = requests.get(result_url)
            response_data = response.json()

            assert response.status_code == 200
            assert response_data['task_id'] == task_id

            status = response_data.get('status')
            if status in ['COMPLETED', 'FAILED']:
                result = deserialize(response_data['result'])
                return result

            # Wait before querying again
            time.sleep(FAAS.wait_time)

        assert False


class TestWebServiceDouble(Base):

    def test_execution(self):
        # Pass in the format of args, kwargs
        function_id = self.register(double)
        function_args = ((2, ), {})
        task_id = self.execute(function_id, function_args)
        self.status(task_id)

    def test_result(self):
        # Executing the function
        function_id = self.register(double)
        number = random.randint(0, 10000)
        task_id = self.execute(function_id, ((number, ), {}))
        result = self.result(task_id)
        assert result == number * 2


class TestWebServiceSpectrum(Base):
    def test_no_op(self):
        function_id = self.register(no_op)
        task_id = self.execute(function_id, ((), {}))
        result = self.result(task_id)
        assert result is None

    def test_double(self):
        function_id = self.register(double)
        task_id = self.execute(function_id, ((56, ), {}))
        result = self.result(task_id)
        assert result == 112

    def test_fibonacci(self):
        function_id = self.register(calculate_fibonacci)
        task_id = self.execute(function_id, ((5, ), {}))
        result = self.result(task_id)
        assert result == 5

    def test_sleep(self):
        function_id = self.register(sleep_for_5s)
        task_id = self.execute(function_id, ((), {}))
        result = self.result(task_id)
        assert result is None

    def test_bruteforce_password(self):
        function_id = self.register(bruteforce_password)
        task_id = self.execute(function_id, (('3cab3e11c1104722a842f0095235881f', 40000, 60000), {}))
        result = self.result(task_id)
        assert result == 52040

    def test_exception(self):
        function_id = self.register(error_function)
        task_id = self.execute(function_id, ((), {}))
        result = self.result(task_id)
        assert isinstance(result, NotImplementedError)
