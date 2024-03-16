import logging
import mimetypes
import os
import re
import shutil
from typing import Optional, Dict, List

import requests
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
        self.driver = driver

        # Check if URL is single media or gallery
        self.gallery_pattern = re.compile(
            r"^https?://(www\.)?reddit\.com/gallery/[A-Za-z0-9_]+$", re.IGNORECASE
        )

        # Check if media url is valid format
        self.media_pattern = re.compile(
            r"^https?://.*\.(png|jpg|jpeg|gif|bmp|webp)(\?.*)?$", re.IGNORECASE
        )

        # Extract image name from gallery
        self.name_pattern = re.compile(r".*-(.*?)\.")

    def get_media_urls(self, content_href: str, id: str) -> Optional[List[str]]:

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

    def get_gallery_urls(self) -> Optional[List[str]]:
        """
        Checks if the post contains an image gallery. If so, returns the list of media URLs

        :param driver: The webdriver the access page content

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
    def fetch_and_save(self, url: str, path: str, name: str) -> Optional[str]:
        res = requests.get(url, stream=True)
        res.raise_for_status()

        # Guess file extension from response headers
        header = res.headers
        ext = mimetypes.guess_extension(header["content-type"])
        f_path = os.path.join(
            path,
            name + ext,
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
        Downloads media from a post if a valid  URL is found.

        :param content: Dict with scraped content of post. Has an 'id' and a 'content-href' with the image URL.
        :param download_media_dir: Dir where images will be downloaded and saved. Dir created if it does not exist.

        :return: Path of the downloaded image if download successful, else nothing
        :raises Exception: Any exception encountered during the download process is logged as an error.
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
                f_path = self.fetch_and_save(url, path, name)

                logging.info(f"Successfully downloaded post content: {f_path}")
                media_paths.append(f_path)

            except Exception as e:
                logging.error(f"Skipping. Error downloading post for ID '{id}': {e}")
                continue

        return media_paths if media_paths else None
