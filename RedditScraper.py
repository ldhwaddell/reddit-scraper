from concurrent import futures
import logging
import random
import re
import time
import traceback
from urllib.parse import urlparse


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import (
    NoSuchElementException,
)

# Set up logger
logger = logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)-8s %(levelname)-8s %(message)s"
)


class RedditScraper:
    def __init__(self, url, headless=False) -> None:
        self.url = url
        self.headless = headless

    def __str__(self) -> str:
        return f"RedditScraper for url: {self.url}. Headless: {self.headless}"

    def __enter__(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")

        try:
            self.driver = webdriver.Chrome(options=options)

            # Ensure user is tring to scrape a valid subreddit
            self.validate_reddit_url(self.url)
            self.driver.get(self.url)
            return self

        except WebDriverException as e:
            logging.error(f"Failed to initialize Chrome WebDriver: {e}")
        except Exception as e:
            logging.error(f"Error occurred initializing RedditScraper: {e}")

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type:
            error_message = (
                f"An error occurred: {exception_type.__name__}: {exception_value}"
            )
            logging.error(error_message)
            logging.error("Traceback details:")
            traceback_details = "".join(traceback.format_tb(exception_traceback))
            logging.error(traceback_details)
            return False

        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException as e:
                logging.error(f"Failed to close WebDriver: {e}")
        else:
            logging.error("WebDriver not initialized.")

        # No exception, so clean exit
        return True

    def validate_reddit_url(self, url):
        parts = urlparse(url)

        if not re.search(r"www\.reddit\.com", parts.netloc):
            raise Exception("Invalid URL. Must be a link to reddit")

        if not re.fullmatch(
            r"/r/([A-Za-z0-9_]{3,21})(/(hot|new|top|rising))?/?", parts.path
        ):
            raise Exception("Invalid URL. Illegal subreddit path")

    def scrape_post_preview(self, post) -> dict:
        attributes = [
            "permalink",
            "content-href",
            "comment-count",
            "feedindex",
            "is-not-brand-safe",
            "created-timestamp",
            "post-title",
            "post-type",
            "score",
            "author",
        ]

        logging.info(f"Scraping post titled: {post.get_attribute('post-title')}")
        content = {attr: post.get_attribute(attr) for attr in attributes}

        return content

    def validate_posts_limit(self, limit):
        if limit is None:
            return True

        # Check if limit is an integer
        if not isinstance(limit, int):
            logging.error("Limit must be an integer")
            return False

        # Check if limit is a positive integer
        if limit < 1:
            logging.error(f"Limit must be at least 1. {limit} provided")
            return False

        return True

    def get_posts(self, limit=None):
        if not self.validate_posts_limit(limit):
            return []

        posts = []

        executor = futures.ThreadPoolExecutor()

        try:
            while True:
                post_elements = self.driver.find_elements(By.TAG_NAME, "shreddit-post")

                for post in post_elements[len(posts) :]:
                    if limit is not None and len(posts) >= limit:
                        break

                    # don't just append posts previews
                    posts.append(self.scrape_post_preview(post))

                last_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )

                # Scroll down to load new posts
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )

                # Add a delay to allow the page to load
                sleep = round(random.uniform(1, 4), 3)
                logging.info(f"Sleeping for {sleep} seconds")
                time.sleep(sleep)

                new_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )

                # Break the loop if we've reached the bottom of the page or reached the limit
                if new_height == last_height or (
                    limit is not None and len(posts) >= limit
                ):
                    break

        except NoSuchElementException as e:
            logging.error(f"Error while locating elements on the page: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

        # If limit is None, just log the number of posts scraped
        if limit is None:
            logging.info(f"Total posts scraped: {len(posts)}")
        elif len(posts) < limit:
            logging.warning(
                f"Could not find the desired number of posts. {len(posts)}/{limit} posts scraped."
            )

        return posts
