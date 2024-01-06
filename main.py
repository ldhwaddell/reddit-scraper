import logging
import random
import re
import time
from urllib.parse import urlparse


from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

    def __valid_reddit_url(self, url):
        parts = urlparse(url)

        if not re.search(r"www\.reddit\.com", parts.netloc):
            logging.error("Invalid URL. Must be a link to reddit")
            return False

        if not re.fullmatch(r"/r/([A-Za-z0-9_]{3,21})/?", parts.path):
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
        if not self.__valid_reddit_url(url):
            return False

        try:
            self.driver.get(url)
            return True
        except WebDriverException as e:
            logging.error(f"Failed to load URL {url}: {e}")
            return False

    def get_title(self):
        if self.driver:
            return self.driver.title
        else:
            logging.error("WebDriver not initialized.")
            return None

    def __scrape_post_preview(self, post) -> dict:
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

        content = {attr: post.get_attribute(attr) for attr in attributes}

        return content

    def get_posts(self, limit=3):
        posts = []

        try:
            while len(posts) < limit:
                post_elements = self.driver.find_elements(By.TAG_NAME, "shreddit-post")

                for post in post_elements[len(posts) :]:
                    if len(posts) >= limit:
                        break
                    try:
                        posts.append(self.__scrape_post_preview(post))
                        # Scroll to the current post
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView();", post
                        )
                        WebDriverWait(self.driver, 10).until(EC.visibility_of(post))
                    except StaleElementReferenceException:
                        logging.warning(
                            "Stale element reference encountered. Reattempting."
                        )
                        break  # Break the inner loop to refresh the list of posts

                # Check if more posts need to be loaded
                if len(posts) < limit:
                    # Wait for new posts to load
                    WebDriverWait(self.driver, 10).until(
                        lambda d: len(d.find_elements(By.TAG_NAME, "shreddit-post"))
                        > len(post_elements)
                    )

        except NoSuchElementException as e:
            logging.error(f"Error while locating elements on the page: {e}")
        except TimeoutException as e:
            logging.error(f"Timeout occurred while locating elements on the page: {e}")

        # except Exception as e:
        #     logging.error(f"An unexpected error occurred: {e}")

        if len(posts) < limit:
            logging.warning(
                f"Could not reach the desired number of posts. Only {len(posts)} posts scraped."
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


if __name__ == "__main__":
    scraper = RedditScraper(headless=False)
    url = "https://www.reddit.com/r/Calculatedasshattery/"
    # url = "https://www.reddit.com/r/AmItheAsshole/"

    if scraper.get(url):
        print(scraper.get_title())
        posts = scraper.get_posts(limit=60)
        print(posts)
        print(len(posts))
        scraper.close()
    else:
        print("Request to URL failed")
