from RedditScraper import RedditScraper

if __name__ == "__main__":
    scraper = RedditScraper(headless=False)
    url = "https://www.reddit.com/r/AmItheAsshole/rising/"

    if scraper.get(url):
        posts = scraper.get_posts(limit=7)
        print(posts)
        print(len(posts))
        scraper.close()
    else:
        print("Request to URL failed")