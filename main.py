from reddit_scraper.reddit_scraper import RedditScraper


if __name__ == "__main__":
    url = "https://www.reddit.com/r/NovaScotia/rising"

    # Instantiate a headless scraper with at most 6 threads
    with RedditScraper(url=url, headless=True, max_workers=6) as rs:

        # Scrape one post, with up to 10 comments, and download any images to a directory called test
        posts = rs.get_posts(limit=5, comment_limit=10, download_media_dir="./test")

    print(posts)
