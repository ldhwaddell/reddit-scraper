import logging
from typing import Dict, Optional

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
        # Find "-post-rtjson-content" for the relevant comment
        content = comment.find_element(By.ID, "-post-rtjson-content")
        author = comment.get_attribute("author")
        id = comment.get_attribute("thingid")
        depth = comment.get_attribute("depth")
        permalink = comment.get_attribute("permalink")
        score = comment.get_attribute("score")
        postid = comment.get_attribute("postid")

        return {
            "author": author,
            "id": id,
            "depth": depth,
            "permalink": permalink,
            "score": score,
            "postid": postid,
            "content": content.text if content else None,
        }

    def scrape_child_comments(self, comment: WebElement):
        author = comment.get_attribute("author")
        print(f"Received comment from {author}")

        # This will neeed to be recursive
        ...

    def scrape_comments(self, comment_limit: int) -> Dict:
        all_comments = {}

        try:
            # Find the main comment tree
            comment_tree = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "shreddit-comment-tree"))
            )
            total_comments = comment_tree.get_attribute("totalcomments")
            logging.info(f"Post has {total_comments} comments")

            while True:
                current_comments = comment_tree.find_elements(
                    By.TAG_NAME, "shreddit-comment"
                )

                for comment in current_comments[len(all_comments) :]:
                    content = self.scrape_comment(comment)

                    # If comment depth is 0, then it is a parent comment
                    # We should scrape any children

                    # If comment depth is not 0, then it must be a child comment.
                    print(content)
                    print("\n\n")

                break

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
        "https://www.reddit.com/r/halifax/comments/1bh5xr9/where_would_you_go_for_a_nice_sized_pan_fried/"
    )

    cs = CommentScraper(driver)
    comments = cs.scrape_comments(comment_limit=100)
    print(comments)
