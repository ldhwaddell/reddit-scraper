import logging
import re
import traceback
from concurrent import futures
from typing import Optional, Type, Dict, List
from types import TracebackType
from urllib.parse import urlparse, urljoin

from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    WebDriverException,
    NoSuchElementException,
    TimeoutException,
)

from .comments import CommentScraper
from .media import MediaScraper
from .utils import scroll_page

# Set up logger
logger = logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-8s %(levelname)-8s [%(funcName)s:%(lineno)d] %(message)s",
)


class RedditScraper:
    def __init__(self, url: str, headless: bool = False, max_workers: int = 8) -> None:
        """
        Initializes the RedditScraper with a specified URL, headless browsing option, and max worker threads.

        :param url: The URL to scrape, expected to be a Reddit URL.
        :param headless: Whether to run the browser in headless mode. Defaults to False.
        :param max_workers: The maximum number of worker threads for concurrent execution. Defaults to 8.
        """
        self.url = self.validate_reddit_url(url)
        self.headless = headless
        self.max_workers = max_workers

    def __enter__(self):
        """
        Context manager entry method to initialize the web driver and open the URL.

        :return: Returns an instance of RedditScraper.
        :raises WebDriverException: If there's a failure in initializing the Chrome WebDriver.
        :raises Exception: For any other errors during initialization.
        """
        try:
            self.driver = self.build_web_driver(headless=self.headless)
            self.driver.get(self.url)
            return self

        except WebDriverException as e:
            logging.error(f"Failed to initialize Chrome WebDriver: {e}")
            raise e
        except Exception as e:
            logging.error(f"Error occurred initializing RedditScraper: {e}")
            raise e

    def __exit__(
        self,
        exception_type: Optional[Type[BaseException]],
        exception_value: Optional[BaseException],
        exception_traceback: Optional[TracebackType],
    ) -> bool:
        """
        Context manager exit method to handle exceptions and ensure clean up.

        :param exception_type: The type of the exception if an exception has been raised.
        :param exception_value: The value of the exception if an exception has been raised.
        :param exception_traceback: The traceback of the exception if an exception has been raised.
        :return: False if an exception occurred, True otherwise.
        """
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

    def build_web_driver(self, headless: bool = True) -> webdriver.Chrome:
        """
        Builds and returns a Chrome WebDriver with specified options.

        :param headless: Specifies whether to run the web driver in headless mode. Defaults to True.
        :return: An instance of Chrome WebDriver with the specified options.
        """
        options = webdriver.ChromeOptions()
        if headless:
            user_agent = UserAgent()
            options.add_argument(f"user-agent={user_agent.random}")
            options.add_argument("--headless")
            options.add_argument("window-size=1920,1080")

        return webdriver.Chrome(options=options)

    def quit_web_driver(self, driver: webdriver.Chrome) -> None:
        """
        Safely quits the WebDriver, handling any exceptions.

        :param driver: The instance of Chrome WebDriver to be quit.
        """
        try:
            driver.quit()
        except WebDriverException as e:
            logging.error(f"Failed to close WebDriver: {e}")

    def validate_reddit_url(self, url: str) -> str:
        """
        Validates if the provided URL is a valid Reddit URL.

        :param url: The URL to validate.
        :return: The original URL if valid.
        :raises Exception: If the URL is not a valid Reddit URL or has an illegal subreddit path.
        """
        parts = urlparse(url)

        if not re.search(r"www\.reddit\.com", parts.netloc):
            raise Exception("Invalid URL. Must be a link to reddit")

        if not re.fullmatch(
            r"/r/([A-Za-z0-9_]{3,21})(/(hot|new|top|rising))?/?", parts.path
        ):
            raise Exception("Invalid URL. Illegal subreddit path")

        return url

    def validate_limit(self, limit: Optional[int]) -> bool:
        """
        Validates the limit for the number of posts or comments to scrape.

        :param limit: The limit for the number of posts to scrape. Can be None for no limit.
        :return: True if the limit is valid, False otherwise.
        """
        if limit is None:
            return True

        # Check if limit is an integer
        if not isinstance(limit, int):
            logging.error("Limit must be an integer")
            return False

        # Check if limit is a positive integer
        if limit < 0:
            logging.error(f"Limit cannot be negative. {limit} provided")
            return False

        return True

    def scrape_post_tag(self, post: WebElement) -> Dict[str, str]:
        """
        Extracts specific attributes from a post web element.

        :param post: The web element representing a post.
        :return: A dictionary containing key-value pairs of various attributes of the post. Each key and value is a string.
        """
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
            "id",
        ]

        content = {attr: post.get_attribute(attr) for attr in attributes}

        return content

    def scrape_post_content(
        self, driver: webdriver.Chrome, post_id: str
    ) -> Optional[str]:
        """
        Scrapes the content of a post. Method locates a post element by tag name and extracts and formats
        main text content. Skips elements with nested tags to avoid extracting text multiple times.

        :param driver: The Chrome WebDriver instance used to access and interact with the webpage.
        :return: A string containing the formatted text content of the post, or None if the post element is not found.
        :raises NoSuchElementException: If the specified elements are not found in the webpage.
        """
        try:
            # Find the 'shreddit-post' element
            post = driver.find_element(By.TAG_NAME, "shreddit-post")

            text_div = post.find_element(
                By.CSS_SELECTOR, f"div[id]:not(#{post_id}-overflow-cover)"
            )

            raw_text = text_div.get_attribute("innerText")
            return raw_text.strip() if raw_text else None

        except NoSuchElementException:
            # Meaning there is no body text
            return None

    def get_post(
        self, post: WebElement, comment_limit: int, download_media_dir: str
    ) -> Optional[Dict[str, Dict]]:
        """
        Scrapes content from a specific post. Optionally scrapes the comments and image contents

        :param post: A WebElement representing the post to be scraped.
        :param comment_limit: The max number of comments to scrape from a post
        :param download_media_dir: indicates to donwload media from a post

        :return: A dictionary containing the scraped content of the post, or None if an error occurs.
        """
        try:
            content = self.scrape_post_tag(post)
            logging.info(f"Scraping post titled: {content['post-title']}")

            content["url"] = urljoin("https://www.reddit.com", content["permalink"])

            driver = self.build_web_driver(headless=True)
            driver.get(content["url"])

            content["post"] = self.scrape_post_content(driver, content["id"])

            if download_media_dir:
                media_scraper = MediaScraper(driver)
                media_path = media_scraper.download_media(content, download_media_dir)
                content["media_path"] = media_path

            if comment_limit:
                logging.info("NOT IMPLEMENTED")
                # comment_scraper = CommentScraper(driver)
                # comments = comment_scraper.scrape_comments(comment_limit)
                # content["comments"] = comments

            return {"tag": content}

        except Exception as e:
            logging.error(
                f"Unable to scrape post at: {post}. An error has occurred: {e}"
            )
            # Could return url for later retry logic
            return None
        finally:
            self.quit_web_driver(driver)

    def get_posts(
        self,
        limit: Optional[int] = 5,
        comment_limit: int = 0,
        download_media_dir: str = "",
    ) -> List[Dict]:
        """
        Retrieves and scrapes a specified number of posts from a Reddit page. Handles scrolling logic

        :param limit: The maximum number of posts to scrape. If None, no limit is applied.
        :param comment_limit: The maximum number of comments to scrape per post. If None, no limit is applied.

        :return: A list of dictionaries, each containing data about a scraped post.
        """
        if not self.validate_limit(limit):
            return []

        if not self.validate_limit(comment_limit):
            return []

        post_ids = set()
        scraped_posts = []

        with futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            try:
                while True:
                    post_elements = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located(
                            (By.TAG_NAME, "shreddit-post")
                        )
                    )

                    posts_to_scrape = []

                    # Possible room for improv, remove set?
                    # Start at len(scraped_posts) to stop iteration over previously seen posts
                    for post_element in post_elements[len(scraped_posts) :]:
                        id = post_element.get_attribute("id")

                        if limit is None or len(post_ids) < limit:
                            post_ids.add(id)
                            posts_to_scrape.append(post_element)

                    scraped_posts.extend(
                        executor.map(
                            lambda post: self.get_post(
                                post, comment_limit, download_media_dir
                            ),
                            posts_to_scrape,
                        )
                    )

                    if limit is not None and len(post_ids) == limit:
                        break

                    # Exit loop if page is unable to scroll down more
                    if not scroll_page(self.driver):
                        break

            except NoSuchElementException as e:
                logging.error(f"Error while locating elements on the page: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")

        # Logging
        if limit is None:
            logging.info(f"Total posts scraped: {len(post_ids)}")
        elif len(post_ids) < limit:
            logging.warning(
                f"Could not find the desired number of posts. {len(post_ids)}/{limit} posts scraped."
            )

        return scraped_posts
