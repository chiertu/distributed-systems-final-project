"""
Script to measure the time taken by different modes (local/pull/push) using the password cracking function

Structure:
1. N workers running - either pull or push (local is going to be used as a baseline for the benchmark)
2. Script submits 20 requests with different inputs to the FAAS service
3. Measures the time taken to get the response of all 20 requests

Expected result: Time taken to return the results decreases as the number of workers increase
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from test.serialize import serialize, deserialize
from test.utils import sleep_for_1s

N = int(sys.argv[1])


def prepare_requests(function_id: str) -> dict:
    """
    Prepares the N requests to be sent to the FAAS service. This is made into a separate function because we want the
    requests submitted to be nearly concurrent. If we prepare request in the loop, it adds more delay between requests

    Assumes the function being used is sleep function
    :param function_id: Function ID of the registered password cracking function
    :return:
    """
    user_requests = {}

    for i in range(N):
        payload = ((), {})
        data = {'function_id': function_id, 'payload': serialize(payload)}
        user_requests[i] = data

    return user_requests


def register_function() -> str:
    """
    Registers the no-op function
    :return:
    """
    url = 'http://127.0.0.1:8000/register_function'
    function = serialize(sleep_for_1s)
    data = {'name': 'Sleep Function', 'payload': function}
    response = requests.post(url, json=data)

    assert response.status_code == 201
    assert 'function_id' in response.json()

    function_id = response.json().get('function_id')
    return function_id


def get_result(task_id):
    result_url = f'http://127.0.0.1:8000/result/{task_id}'
    while True:
        response = requests.get(result_url)
        response_data = response.json()

        assert response.status_code == 200
        assert response_data['task_id'] == task_id

        status = response_data.get('status')
        if status in ['COMPLETED', 'FAILED']:
            result = deserialize(response_data['result'])
            return True, result

        # Wait before querying again
        time.sleep(0.1)


def aggregate_results(task_ids):
    futures = []
    with ThreadPoolExecutor(max_workers=N) as executor:
        for task_id in task_ids:
            futures.append(executor.submit(get_result, task_id))

    for task in as_completed(futures):
        found, result = task.result()
        assert found is True
        assert result is None


def run_fleet(user_requests):
    """
    Submits the N requests to the FAAS service
    :return:
    """
    url = 'http://127.0.0.1:8000/execute_function'

    task_ids = {}
    start_time = time.time()
    for pin in user_requests:
        response = requests.post(url, json=user_requests[pin])
        task_id = response.json().get('task_id')
        task_ids[task_id] = pin

    aggregate_results(task_ids)

    end_time = time.time()
    time_taken = end_time - start_time
    print(f'Time Taken for {len(user_requests)}: {time_taken} seconds')


def execute():
    function_id = register_function()
    user_requests = prepare_requests(function_id)
    run_fleet(user_requests)


if __name__ == '__main__':
    execute()
