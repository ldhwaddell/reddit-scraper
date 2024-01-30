from RedditScraper import RedditScraper

if __name__ == "__main__":
    # url = "https://www.reddit.com/r/AmItheAsshole/"
    url = "https://www.reddit.com/r/NovaScotia/"

    with RedditScraper(url=url, headless=False) as rs:
        posts = rs.get_posts(limit=16, get_comments=False)
        print(posts)
        print(len(posts))
