import logging
import mimetypes
import os
import re
import shutil
from typing import Optional, Dict, List, Tuple

import requests
from requests import Response
from selenium import webdriver
from selenium.webdriver.common.by import By

from .utils import retry

# Set up logger
logger = logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-8s %(levelname)-8s [%(funcName)s:%(lineno)d] %(message)s",
)


class MediaScraper:
    def __init__(self, driver: webdriver.Chrome) -> None:
        """
        Initializes the MediaScraper with a specified driver

        :param driver: The webdriver to use
        """
        self.driver = driver

        # Matches media gallery
        self.gallery_pattern = re.compile(
            r"^https?://(www\.)?reddit\.com/gallery/[A-Za-z0-9_]+$", re.IGNORECASE
        )

        # Matches valid media types
        self.media_pattern = re.compile(
            r"^https?://.*\.(png|jpg|jpeg|gif|bmp|webp)(\?.*)?$", re.IGNORECASE
        )

        # Extract image name from gallery URL
        self.name_pattern = re.compile(r".*-(.*?)\.")

    def get_media_urls(
        self, content_href: str, id: str
    ) -> Optional[List[Tuple[str, str]]]:
        """
        Checks if the post contains an image, gallery, or nothing and returns
        the corresponding list of media URLs

        :return: The list of URLs containing media from the gallery
        """
        # If post is a gallery, extract all of the gallery image URLs
        if self.gallery_pattern.match(content_href):
            urls = self.get_gallery_urls()
            return urls

        # Not a gallery, single URL
        elif self.media_pattern.match(content_href):
            return [(content_href, id)]

        # Post has no media, can skip
        else:
            return None

    def get_gallery_urls(self) -> Optional[List[Tuple[str, str]]]:
        """
        Gets the media URLs from the image gallery

        :return: The list of URLs containing media from the gallery
        """
        gallery_carousel = self.driver.find_element(By.TAG_NAME, "gallery-carousel")

        if not gallery_carousel:
            return None

        urls = []

        gallery_images = gallery_carousel.find_elements(By.CSS_SELECTOR, "img.absolute")
        for img in gallery_images:
            src = img.get_attribute("src")
            if src and self.media_pattern.match(src):
                name = self.name_pattern.match(src).group(1)
                urls.append((src, name))

        return urls

    @retry(retries=3, retry_sleep_sec=5)
    def fetch(self, url: str) -> Optional[Response]:
        """
        Fetches a URL, streams the response. Raises exception if the status code is invalid.

        :param url: The URL to fetch
        :return: The response if valid, otherwise raises exception
        """
        res = requests.get(url, stream=True)
        res.raise_for_status()
        return res

    def save(self, res: Response, path: str, f_name: str) -> str:
        """
        Extract the raw content from a response and saves it to a given directory.

        :param res: The response object to save
        :param path: The path to save the file
        :param f_name: The name to save the file as
        :return: The path the image was saved under
        """
        # Guess file extension from response headers
        header = res.headers
        ext = mimetypes.guess_extension(header["content-type"])
        f_path = os.path.join(
            path,
            f_name + ext,
        )

        # Save media
        with open(f_path, "wb") as f:
            shutil.copyfileobj(res.raw, f)
        return f_path

    def download_media(
        self,
        content: Dict[str, Dict],
        download_media_dir: str,
    ) -> Optional[List[str]]:
        """
        Retrieves media such as images from the provided URLs in the content dictionary and
        saves them to the specified directory. Directory is created if it does not already exist.
        It supports downloading media from both single URLs and Reddit gallery URLs.

        :param content: A dictionary containing the scraped content of a post
        :param download_media_dir: The directory path where the media should be downloaded and saved.
        :return: A list of file paths to the downloaded media if the download is successful. Otherwise, None.
        """

        # The URL of the media to download
        content_href = content["tag"]["content-href"]

        # The id of the post
        id = content["tag"]["id"]

        # Get possible list of URLs to fetch
        media_urls = self.get_media_urls(content_href, id)

        if not media_urls:
            logging.warning(f"No media URLs found for: {id}")
            return None

        # Make the dir to save the files in if it does not exist
        path = os.path.join(download_media_dir, id)
        os.makedirs(path, exist_ok=True)

        media_paths = []
        for url, name in media_urls:

            try:
                res = self.fetch(url)
                f_path = self.save(res, path, name)

                logging.info(f"Successfully downloaded post content: {f_path}")
                media_paths.append(f_path)

            except Exception as e:
                logging.error(f"Skipping. Error downloading post for ID '{id}': {e}")
                continue

        return media_paths if media_paths else None
