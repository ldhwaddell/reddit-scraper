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
    def __init__(self, driver: webdriver.Chrome, limit: int) -> None:
        self.driver = driver
        self.limit = limit
        self.comment_ids = set()

    def scrape_comment_content(self, comment: WebElement) -> Dict:
        """
        Function to scrape the content from a single comment

        :param comment: The webelement representing the comment to scrape information from
        :return: A dict with the relevant comment info
        """
        author = comment.get_attribute("author")
        id = comment.get_attribute("thingid")
        depth = comment.get_attribute("depth")
        permalink = comment.get_attribute("permalink")
        score = comment.get_attribute("score")
        postid = comment.get_attribute("postid")

        # Scrape text even if it is hidden due to downvotes
        raw_content = comment.find_element(By.CSS_SELECTOR, "div[slot='comment']")
        content = raw_content.get_attribute("innerText").strip()

        return {
            "author": author,
            "id": id,
            "depth": depth,
            "permalink": permalink,
            "score": score,
            "postid": postid,
            "content": content if content else None,
        }

    # Make this recursive?
    def scrape_children(self, comment: WebElement, depth: int):
        children = comment.find_elements(
            By.XPATH, f"//shreddit-comment[@depth='{depth}']"
        )

        for child in children:
            content = self.scrape_comment_content(child)
            if content["id"] in self.comment_ids:
                continue

    # Function assumes it is only getting parent comments
    def get(self, comment: WebElement) -> Tuple[Dict, bool]:
        """
        Ideal situation

        1. Scrape the parent comment.
        2. Scrape the children
        3. Check for more replies buttons
            - If there are none, return parent and children
        4. If there is a more replies button, click it
            - Then wait for page load
        5. scrape the children
        6. check for more replies button
            - If there are none, return parent and children
        7. If there is a more replies button, click it
            - Then wait for page load
        8. scrape the children
        9. check for more replies button
            - If there are none, return parent and children
        ...

        """
        scraped_comments = {}

        parent_id = comment.get_attribute("thingid")

        # If we have already seen the parent comment, just skip
        if parent_id in self.comment_ids:
            return ({}, True)

        # Scrape the comment
        content = self.scrape_comment_content(comment)

        # Add to scraped comments
        scraped_comments[parent_id] = content
        self.comment_ids.add(parent_id)

        # Check if limit is reached
        if len(self.comment_ids) == self.limit:
            return (scraped_comments, False)

        # Check for children
        children = comment.find_elements(By.XPATH, ".//shreddit-comment[@depth='1']")

        print(f"found {len(children)} children")
        for c in children:
            print(c.get_attribute("author"))
        print("\n\n\n")

        if not children:
            try:
                more_replies_button = comment.find_element(
                    By.CSS_SELECTOR, ".//faceplate-partial[loading='action'][last()]"
                )

                print("FOUND MORE REPLIES BUTTON IN PARENT")
                print(more_replies_button.get_attribute("slot"))
                # Wait then scrape children

            except NoSuchElementException:
                return (scraped_comments, True)
        else:
            return ({}, True)

    def scrape_comments(self) -> Dict:
        all_comments = {}

        try:
            # Find the main comment tree
            comment_tree = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "shreddit-comment-tree"))
            )
            total_comments = int(comment_tree.get_attribute("totalcomments"))
            logging.info(f"Post has {total_comments} comments")

            # Update comment limit if there aren't enough comments on the page
            if total_comments < self.limit:
                logging.warning(
                    f"Unable to scrape {self.limit}, scraping {total_comments}."
                )
                self.limit = total_comments

            while True:
                current_comments = comment_tree.find_elements(
                    By.TAG_NAME, "shreddit-comment"
                )

                # This list splice condition might need to change
                for comment in current_comments[len(all_comments) :]:
                    depth = comment.get_attribute("depth")

                    # Skip child comments, they will be scraped by parent
                    if depth != "0":
                        continue

                    # Scrapes the current comment and its children
                    scraped_comments, _continue = self.get(comment)

                    # Add scraped comments
                    all_comments.update(scraped_comments)

                    # This means that self.get() signaled it has scraped limit # of comments
                    if not _continue:
                        return all_comments

                    time.sleep(5)

                # Exit loop if page is unable to scroll down more
                if not scroll_page(self.driver):
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
        "https://www.reddit.com/r/halifax/comments/1bjbz07/hold_them_accountable_thousands_of_canadians_are/"
    )

    # "https://www.reddit.com/r/NovaScotia/comments/101jout/lets_get_us_a_mod_team/"
    # "https://www.reddit.com/r/halifax/comments/1bh5xr9/where_would_you_go_for_a_nice_sized_pan_fried/"
    cs = CommentScraper(driver, limit=100)
    comments = cs.scrape_comments()
    print(comments)
