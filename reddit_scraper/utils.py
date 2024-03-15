import functools
import logging
import time
from typing import Callable, Any


def retry(retries: int, retry_sleep_sec: int) -> Callable[..., Any]:
    """
    Decorator to add retry logic to a function.

    :param retries: the maximum number of retries.
    :param retry_sleep_sec: the number of seconds to sleep between retries.
    :return: A decorator that adds retry logic to a function.
    """

    def decorator(func):

        # Preserves info about original function. Otherwise func name will be "wrapper" not "func"
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            for attempt in range(retries):
                try:
                    return func(
                        *args, **kwargs
                    )  # should return the raw function's return value
                except Exception as e:
                    logging.error(f"Error: {e}")
                    time.sleep(retry_sleep_sec)

                logging.error(f"Trying attempt {attempt+1} of {retries}")

            logging.error(f"Function {func} retry failed")

            raise Exception(f"Exceeded max retry num: {retries} failed")

        return wrapper

    return decorator
