import logging
import random
import re
import time
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
    def __init__(self, headless=False) -> None:
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")

        try:
            self.driver = webdriver.Chrome(options=options)
        except WebDriverException as e:
            logging.error(f"Failed to initialize Chrome WebDriver: {e}")
            self.driver = None

    def valid_reddit_url(self, url):
        parts = urlparse(url)

        if not re.search(r"www\.reddit\.com", parts.netloc):
            logging.error("Invalid URL. Must be a link to reddit")
            return False

        if not re.fullmatch(
            r"/r/([A-Za-z0-9_]{3,21})(/(hot|new|top|rising))?/?", parts.path
        ):
            logging.error("Invalid URL. Illegal subreddit path")
            return False

        return True

    def get(self, url) -> bool:
        """
        Tries to navigate to the URL. Returns True if successful, False otherwise.
        """
        if not self.driver:
            logging.error("WebDriver not initialized.")
            return False

        # Ensure user is tring to scrape a valid subreddit
        if not self.valid_reddit_url(url):
            return False

        try:
            self.driver.get(url)
            return True
        except WebDriverException as e:
            logging.error(f"Failed to load URL {url}: {e}")
            return False

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

    def get_posts(self, limit=3):
        posts = []
        try:
            while True:
                post_elements = self.driver.find_elements(By.TAG_NAME, "shreddit-post")

                # FIX! Missing some posts
                for post in post_elements[len(posts) + 1 :]:
                    if len(posts) >= limit:
                        break

                    posts.append(self.scrape_post_preview(post))

                last_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )
                # Scroll down a bit to load new posts
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )

                # Add a delay to allow the page to load
                time.sleep(round(random.uniform(1, 4), 3))

                new_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )

                if len(posts) >= limit:
                    break

                if new_height == last_height:
                    logging.warning("Reached the bottom of the page.")
                    break

        except NoSuchElementException as e:
            logging.error(f"Error while locating elements on the page: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

        if len(posts) < limit:
            logging.warning(
                f"Could not find the desired number of posts. {len(posts)}/{limit} posts scraped."
            )

        return posts

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException as e:
                logging.error(f"Failed to close WebDriver: {e}")
        else:
            logging.error("WebDriver not initialized.")
