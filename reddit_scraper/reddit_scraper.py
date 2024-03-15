import string

import logging
import mimetypes
import os
import random
import re
import shutil
import time
import traceback
from concurrent import futures
from typing import Optional, Type, Dict, List
from types import TracebackType
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import requests
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

    def scroll_page(self) -> bool:
        """
        Scrolls the webpage down one viewport height and waits for new content to load. Checks if the scroll has
        resulted in new content by comparing the scroll height before and after the scroll.

        :return: True if new content is loaded (page height increased), False otherwise.
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        sleep_duration = round(random.uniform(2, 4), 3)
        logging.info(f"Sleeping for {sleep_duration} seconds")
        time.sleep(sleep_duration)

        new_height = self.driver.execute_script("return document.body.scrollHeight")
        return new_height != last_height

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

            text = post.find_element(
                By.CSS_SELECTOR, f"div[id]:not(#{post_id}-overflow-cover)"
            )

            html = text.get_attribute("innerHTML")
            soup = BeautifulSoup(html, "html.parser")

            formatted_text = ""
            for element in soup.find_all(["p", "h1", "h2", "h3", "ul", "li"]):
                # Skip elements with nested tags to text is not extracted twice
                if element.find(["p", "h1", "h2", "h3", "ul", "li"]):
                    continue

                if element.name.startswith("h"):
                    formatted_text += f"\n{element.get_text().strip()}\n"
                elif element.name == "p":
                    formatted_text += f"\n{element.get_text().strip()}"
                elif element.name in ["ul", "li"]:
                    formatted_text += f"\n{element.get_text().strip()}"

            return formatted_text
        except NoSuchElementException:
            # Meaning there is no body text
            return None

    def scrape_comments(self, driver: webdriver.Chrome, comment_limit: int) -> Dict:
        all_comments = {}
        comments = driver.find_elements(By.TAG_NAME, "shreddit-comment")

        if not comments:
            return {}

        for comment in comments:
            depth = comment.get_attribute("depth")

            # Only want to add parent comments as keys of the all_comments dict.
            # Comments with depth > 0 are children and should be inside of the respective
            # parent dict entry
            if depth == "0":
                id = comment.get_attribute("thingid")
                author = comment.get_attribute("author")
                score = comment.get_attribute("score")
                replies = self.scrape_child_comments(driver, level=1)
                all_comments[id] = {
                    "author": author,
                    "score": score,
                    "replies": replies,
                }

        return all_comments

    def scrape_child_comments(self, driver: webdriver.Chrome, level: int):
        # This will neeed to be recursive
        ...

    def download_media(
        self,
        driver: webdriver.Chrome,
        content: Dict[str, Dict],
        download_media_dir: str,
    ) -> Optional[List[str]]:
        """
        Downloads media from a post if a valid  URL is found.

        :param driver: The instance of Chrome WebDriver to use to search the page
        :param content: Dict with scraped content of post. Has an 'id' and a 'content-href' with the image URL.
        :param download_media_dir: Dir where images will be downloaded and saved. Dir created if it does not exist.

        :return: Path of the downloaded image if download successful, else nothing
        :raises Exception: Any exception encountered during the download process is logged as an error.
        """

        try:
            # The id of the post
            id = content["tag"]["id"]

            # Make the dir to save the files in if it does not exist
            os.makedirs(os.path.join(download_media_dir, id), exist_ok=True)

            # The URL of the media to download
            content_href = content["tag"]["content-href"]

            # The URLs of media to download
            media_urls = []

            # Check if URL is single media or gallery
            gallery_pattern = re.compile(
                r"^https?://(www\.)?reddit\.com/gallery/[A-Za-z0-9_]+$", re.IGNORECASE
            )

            # Check if media url is valid format
            media_pattern = re.compile(
                r"^https?://.*\.(png|jpg|jpeg|gif|bmp|webp)(\?.*)?$", re.IGNORECASE
            )

            # Extract image name from gallery
            name_pattern = re.compile(r".*-(.*?)\.")

            # If post is a gallery, extract all of the gallery image URLs
            if gallery_pattern.match(content_href):
                gallery_carousel = driver.find_element(By.TAG_NAME, "gallery-carousel")

                if not gallery_carousel:
                    logging.warning(f"No gallery carousel found for post: {id}")
                    return None

                gallery_images = gallery_carousel.find_elements(
                    By.CSS_SELECTOR, "img.absolute"
                )
                for img in gallery_images:
                    src = img.get_attribute("src")
                    if src:
                        name = name_pattern.match(src).group(1)
                        media_urls.append((src, name))

            # Not a gallery, single URL
            else:
                media_urls.append((content_href, id))

            media_paths = []
            for url, name in media_urls:

                if not media_pattern.match(url):
                    logging.warning(
                        f"URL file type did not validate for post {id}. Skipping"
                    )
                    continue

                res = requests.get(url, stream=True)

                if res.status_code == 200:
                    # Guess file extension from response headers
                    header = res.headers
                    ext = mimetypes.guess_extension(header["content-type"])
                    f_path = os.path.join(
                        download_media_dir,
                        id,
                        name + ext,
                    )
                    # Save media
                    with open(f_path, "wb") as f:
                        shutil.copyfileobj(res.raw, f)

                    logging.info(f"Successfully downloaded post content: {f_path}")
                    media_paths.append(f_path)

                else:
                    logging.warning(f"Unable to download image for {id}. Skipping")
                    continue

            return media_paths

        except Exception as e:
            logging.error(f"Error: {e}")
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
            content = {"tag": self.scrape_post_tag(post)}
            logging.info(f"Scraping post titled: {content['tag']['post-title']}")

            content["url"] = urljoin(
                "https://www.reddit.com", content["tag"]["permalink"]
            )

            driver = self.build_web_driver(headless=True)
            driver.get(content["url"])

            content["post"] = self.scrape_post_content(driver, content["tag"]["id"])

            if comment_limit:
                comments = self.scrape_comments(driver, comment_limit)
                content["comments"] = comments

            if download_media_dir:
                media_path = self.download_media(driver, content, download_media_dir)
                content["media_path"] = media_path

            return content

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
                    if not self.scroll_page():
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
