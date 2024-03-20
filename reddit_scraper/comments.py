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

        collapsed = comment.get_attribute("collapsed")
        # content = comment.find_element(By.CSS_SELECTOR, "div[slot='comment']").get_attribute("innerText").strip()

        # Ensure content is scraped even if comment is collapsed
        if collapsed == "false":
            content = comment.find_element(By.ID, "-post-rtjson-content").text
        else:
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

    # # Name will be updated to better reflect job
    # def get(self, comments: List[WebElement], comment_limit: int) -> Tuple[Dict, bool]:
    #     scraped_comments = {}

    #     for comment in comments:
    #         depth = comment.get_attribute("depth")
    #         thingid = comment.get_attribute("thingid")

    #         # Skip child comments, they will be scraped by parent
    #         if depth != "0":
    #             continue

    #         # Scrape the comment
    #         # content = self.scrape_comment_content(comment)

    #         # Check for children or "more reply button"
    #         more_replies_buttons = comment.find_elements(
    #             By.CSS_SELECTOR, "faceplate-partial[loading='action']"
    #         )

    #         while more_replies_buttons:
    #             # Go through buttons and click them
    #             logging.info(
    #                 f"Found {len(more_replies_buttons)} 'more replies' buttons"
    #             )

    #             for button in more_replies_buttons:
    #                 button.click()
    #                 print("CLICKED")
    #                 time.sleep(8)

    #                 # now scrape comments
    #                 comment_with_more_replies = comment.find_element(
    #                     By.XPATH, f"//shreddit-comment[@thingid='{thingid}']"
    #                 )

    #                 print(
    #                     len(
    #                         comment_with_more_replies.find_elements(
    #                             By.TAG_NAME, "shreddit-comment"
    #                         )
    #                     )
    #                 )

    #             # Check for children or "more reply button"
    #             more_replies_buttons = comment.find_elements(
    #                 By.CSS_SELECTOR, "faceplate-partial[loading='action']"
    #             )

    #         if len(self.comment_ids) == comment_limit:
    #             return (scraped_comments, False)

    #         return ({}, False)

    # Name will be updated to better reflect job
    # Function assumes it is only getting parent comments
    def get(self, comment: WebElement, comment_limit: int) -> Tuple[Dict, bool]:
        scraped_comments = {}

        thingid = comment.get_attribute("thingid")

        # Scrape the comment
        content = self.scrape_comment_content(comment)

        # If we have already seen the comment, just skip
        if thingid in self.comment_ids:
            return ({}, True)

        scraped_comments[thingid] = content
        self.comment_ids.add(thingid)

        # Check for children
        if len(self.comment_ids) == comment_limit:
            return (scraped_comments, False)

        # Check for "more reply" button
        try:
            more_replies_button = comment.find_element(
                By.CSS_SELECTOR, "faceplate-partial[loading='action']"
            )
        except NoSuchElementException:
            more_replies_button = None

        # No more replies
        if not more_replies_button:
            print("NO REPLIES")
            return (scraped_comments, True)

    def scrape_comments(self, comment_limit: int) -> Dict:
        all_comments = {}

        try:
            # Find the main comment tree
            comment_tree = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "shreddit-comment-tree"))
            )
            total_comments = int(comment_tree.get_attribute("totalcomments"))
            logging.info(f"Post has {total_comments} comments")

            # Update comment limit if there aren't that many ocmments on the page
            if total_comments < comment_limit:
                logging.warning(
                    f"Unable to scrape {comment_limit}, scraping {total_comments}."
                )
                comment_limit = total_comments

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
                    scraped_comments, _continue = self.get(comment, comment_limit)

                    # Add scraped comments
                    all_comments.update(scraped_comments)

                    # This means that self.get() signaled it has scraped comment_limit # of comments
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
        "https://www.reddit.com/r/NovaScotia/comments/1biyidi/what_are_my_bathroom_rights/"
    )

    # "https://www.reddit.com/r/NovaScotia/comments/101jout/lets_get_us_a_mod_team/"
    # "https://www.reddit.com/r/halifax/comments/1bh5xr9/where_would_you_go_for_a_nice_sized_pan_fried/"
    cs = CommentScraper(driver)
    comments = cs.scrape_comments(comment_limit=1000)
    print(comments)
