# reddit-scraper
A tool to scrape post from a subreddit. 

Example usage:

```python
if __name__ == "__main__":
    url = "https://www.reddit.com/r/AmItheAsshole/"

    with RedditScraper(url=url, headless=False) as rs:
        posts = rs.get_posts(limit=16, get_comments=False)

    print(posts)

```
