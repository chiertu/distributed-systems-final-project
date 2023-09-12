import hashlib
import time


def no_op():
    """
    Does nothing
    :return:
    """
    pass


def double(x):
    """

    :param x:
    :return:
    """
    return x * 2


def sleep_for_5s():
    """
    Sleeps for 5 seconds
    :return:
    """
    time.sleep(5)


def sleep_for_1s():
    """
    Sleeps for 5 seconds
    :return:
    """
    time.sleep(1)


def error_function():
    """

    :return:
    """
    raise NotImplementedError('Not Implemented')


def calculate_fibonacci(n: int):
    """
    Calculates the nth fibonacci number
    :param n:
    :return:
    """
    if n <= 0:
        raise ValueError('Invalid Input. Sequence starts at 1. Are you a developer? Oops :P')
    if n <= 2:
        return 1
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)


def bruteforce_password(hashed_pin, start_range, end_range) -> int:
    """

    :param hashed_pin:
    :param start_range:
    :param end_range:
    :return:
    """
    for pin in range(start_range, end_range):
        if hashlib.md5(f'{pin}'.encode()).hexdigest() == hashed_pin:
            return pin
