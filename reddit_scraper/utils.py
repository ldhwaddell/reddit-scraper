import functools
import logging
import random
import time
from typing import Callable, Any

from selenium import webdriver


def scroll_page(driver: webdriver.Chrome) -> bool:
    """
    Scrolls the webpage down one viewport height and waits for new content to load. Checks if the scroll has
    resulted in new content by comparing the scroll height before and after the scroll.

    :param driver: The websdriver to use to do the scrolling
    :return: True if new content is loaded (page height increased), False otherwise.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    sleep_duration = round(random.uniform(2, 4), 3)
    logging.info(f"Sleeping for {sleep_duration} seconds")
    time.sleep(sleep_duration)

    new_height = driver.execute_script("return document.body.scrollHeight")
    return new_height != last_height


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
