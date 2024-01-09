from RedditScraper import RedditScraper

if __name__ == "__main__":
    url = "https://www.reddit.com/r/AmItheAsshole/"

    with RedditScraper(url=url, headless=False) as rs:
        posts = rs.get_posts(limit=15)
        print(len(posts))
