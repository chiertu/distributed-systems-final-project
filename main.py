from fastapi import FastAPI

from response_classes import RegisterFnRep, RegisterFn, ExecuteFnRep, ExecuteFnReq, TaskResultRep, TaskStatusRep
from task import Task, Function, redis_queue

app = FastAPI()


@app.post('/register_function', response_model=RegisterFnRep, status_code=201)
async def register_function(function: RegisterFn):
    name = function.name
    payload = function.payload

    function = Function(name, payload)
    function.register()

    return function.db_record


@app.post('/execute_function', response_model=ExecuteFnRep, status_code=201)
async def execute_function(request: ExecuteFnReq):
    function_id = request.function_id
    payload = request.payload

    task = Task(function_id, payload)
    task.insert()
    redis_queue.publish_to_channel(task)

    return task.db_record


@app.get('/status/{task_id}', response_model=TaskStatusRep)
async def get_status(task_id):
    task = Task.from_db(task_id)
    return task.db_record


@app.get('/result/{task_id}', response_model=TaskResultRep)
async def get_result(task_id):
    task = Task.from_db(task_id)
    return task.db_record
