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
    def __init__(self, url: str, headless=False, max_workers=None) -> None:
        self.url = url
        self.headless = headless
        self.max_workers = max_workers

    def __str__(self) -> str:
        return f"RedditScraper for url: {self.url}. Headless: {self.headless}"

    def __enter__(self):
        try:
            # Try to build WebDriver
            self.driver = self.build_web_driver(headless=self.headless)

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

        self.quit_web_driver(driver=self.driver)

        # No exception, so clean exit
        return True

    def build_web_driver(self, headless=True):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")

        return webdriver.Chrome(options=options)

    def quit_web_driver(self, driver):
        if driver:
            try:
                driver.quit()
            except WebDriverException as e:
                logging.error(f"Failed to close WebDriver: {e}")
        else:
            logging.error("WebDriver not initialized.")

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

        driver = self.build_web_driver()
        driver.get(f"https://www.reddit.com{content['permalink']}")
        title = driver.title
        print(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%{title}")
        self.quit_web_driver(driver=driver)

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

        executor = futures.ThreadPoolExecutor(max_workers=self.max_workers)
        print(executor._max_workers)

        try:
            while True:
                post_elements = self.driver.find_elements(By.TAG_NAME, "shreddit-post")

                # Calculate the starting index for new posts
                start_index = len(posts)

                if limit is None:
                    end_index = len(post_elements)
                else:
                    # Calculate the ending index - either add all remaining posts or just enough to reach the limit
                    remaining_spaces = limit - len(posts)
                    end_index = start_index + min(
                        len(post_elements) - start_index, remaining_spaces
                    )

                # Slice the post_elements list to get the posts to add
                posts_to_add = post_elements[start_index:end_index]

                # posts.extend(map(self.scrape_post_preview, posts_to_add))
                posts.extend(list(executor.map(self.scrape_post_preview, posts_to_add)))

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
        finally:
            # Always close executor
            executor.shutdown()

        # If limit is None, just log the number of posts scraped
        if limit is None:
            logging.info(f"Total posts scraped: {len(posts)}")
        elif len(posts) < limit:
            logging.warning(
                f"Could not find the desired number of posts. {len(posts)}/{limit} posts scraped."
            )

        return posts
