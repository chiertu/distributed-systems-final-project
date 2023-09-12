## Testing
### Test the service with different functions
To make sure that the service can handle functions of various execution time and functions that return different types of results, we tested the service on 6 different functions listed below:
- `no_op()`
- `double()`
- `sleep_for_5s()`
- `error_function()`
- `calculate_fibonacci()`
- `bruteforce_password()`

### Weak Scaling performance test
To streamline testing, we wrote `measure_time.py`. The script submits a specified number of tasks to the service and measures the time it takes to get all the results back. To simulate tasks hitting the service at the same time, the script gets all the tasks ready for submission and then uses threading to submit the tasks concurrently.

We conducted two testing sessions with two types of functions. Testing with `no-op()` gives us the pure overhead of the service. And testing with `sleep_for_1s()` gives us a more realistic	view of how the service perform in normal conditions and showcases the efficiency of the service.

For each setup listed below, we performed three runs and took the average running time of the three.
    - Local mode | 2 processes | 4 tasks
    - Local mode | 4 processes | 8 tasks
    - Local mode | 6 processes | 12 tasks
    - Local mode | 8 processes | 16 tasks
    - Local mode | 10 processes | 20 tasks

(The following tests are done in both Pull mode | Push mode)

    - 2 workers | 2 processes | 8 tasks
    - 2 workers | 4 processes | 16 tasks
    - 2 workers | 6 processes | 24 tasks
    - 2 workers | 8 processes | 32 tasks
    - 2 workers | 10 processes | 40 tasks

    - 4 workers | 2 processes | 16 tasks
    - 4 workers | 4 processes | 32 tasks
    - 4 workers | 6 processes | 48 tasks
    - 4 workers | 8 processes | 64 tasks
    - 4 workers | 10 processes | 80 tasks

    - 6 workers | 2 processes | 24 tasks
    - 6 workers | 4 processes | 48 tasks
    - 6 workers | 6 processes | 72 tasks
    - 6 workers | 8 processes | 96 tasks
    - 6 workers | 10 processes | 120 tasks

    - 8 workers | 2 processes | 32 tasks
    - 8 workers | 4 processes | 64 tasks
    - 8 workers | 6 processes | 96 tasks
    - 8 workers | 8 processes | 128 tasks
    - 8 workers | 10 processes | 160 tasks


### Latency test
For latency test, we measured the time taken by the service to complete one task of running the `sleep_for_1s()` function. For each setup listed below, we performed 10 runs and plotted the range of running time taken to finish the task.

    - Local mode | 2 processes
    - Pull mode | 1 worker | 2 processes
    - Push mode | 1 worker | 2 processes
