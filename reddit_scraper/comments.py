import logging
from typing import Dict, Optional, List, Tuple

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

from utils import scroll_page

import time

# Set up logger
logger = logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-8s %(levelname)-8s [%(funcName)s:%(lineno)d] %(message)s",
)


class CommentScraper:
    def __init__(self, driver: webdriver.Chrome) -> None:
        self.driver = driver
        self.comment_ids = set()

    def scrape_comment(self, comment: WebElement) -> Dict:
        """
        Function to scrape the content from a single comment

        :param comment: The webelement representing the comment to scrape information from
        :return: A dict with the relevant comment info
        """
        content = comment.find_element(By.ID, "-post-rtjson-content")
        author = comment.get_attribute("author")
        id = comment.get_attribute("thingid")
        depth = comment.get_attribute("depth")
        permalink = comment.get_attribute("permalink")
        score = comment.get_attribute("score")
        postid = comment.get_attribute("postid")

        # Keep track of comment
        self.comment_ids.add(id)

        return {
            "author": author,
            "id": id,
            "depth": depth,
            "permalink": permalink,
            "score": score,
            "postid": postid,
            "content": content.text if content else None,
        }
    
    

    # Name will be updated to better reflect job
    def get(self, comments: List[WebElement], comment_limit: int) -> Tuple[Dict, bool]:
        scraped_comments = {}

        for comment in comments:
            depth = comment.get_attribute("depth")

            # Skip child comments, they will be scraped by parent
            if depth != "0":
                continue

            # Check for children or "more reply button"
            more_replies_buttons = comment.find_elements(
                By.CSS_SELECTOR, "faceplate-partial[loading='action']"
            )

            while more_replies_buttons:
                print(f"Found {len(more_replies_buttons)}")
                for m in more_replies_buttons:
                    m.click()
                    print("CLICKED")
                    time.sleep(10)

                # Check for children or "more reply button"
                more_replies_buttons = comment.find_elements(
                    By.CSS_SELECTOR, "faceplate-partial[loading='action']"
                )

            if len(self.comment_ids) == comment_limit:
                return (scraped_comments, False)

            return ({}, False)

            # content = self.scrape_comment(comment)

    def scrape_comments(self, comment_limit: int) -> Dict:
        all_comments = {}

        try:
            # Find the main comment tree
            comment_tree = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "shreddit-comment-tree"))
            )
            total_comments = int(comment_tree.get_attribute("totalcomments"))
            logging.info(f"Post has {total_comments} comments")

            if total_comments < comment_limit:
                logging.warning(
                    f"Unable to scrape {comment_limit}, scraping {total_comments}."
                )
                comment_limit = total_comments

            while True:
                current_comments = comment_tree.find_elements(
                    By.TAG_NAME, "shreddit-comment"
                )

                scraped_comments, _continue = self.get(
                    current_comments[len(all_comments) :], comment_limit
                )

                # Add scraped comments
                all_comments.update(scraped_comments)

                if not _continue:
                    break

                # Exit loop if page is unable to scroll down more
                if not scroll_page(self.driver):
                    break

                time.sleep(10)

            return all_comments

        except TimeoutException:
            logging.warning(
                "No comment tree found after 5 seconds. Post has no comments or error occurred"
            )
            return all_comments


if __name__ == "__main__":
    from fake_useragent import UserAgent

    options = webdriver.ChromeOptions()
    user_agent = UserAgent()
    options.add_argument(f"user-agent={user_agent.random}")
    # options.add_argument("--headless")
    options.add_argument("window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(
        "https://www.reddit.com/r/NovaScotia/comments/101jout/lets_get_us_a_mod_team/"
    )

        # "https://www.reddit.com/r/halifax/comments/1bh5xr9/where_would_you_go_for_a_nice_sized_pan_fried/"
    cs = CommentScraper(driver)
    comments = cs.scrape_comments(comment_limit=100)
    print(comments)
