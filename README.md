# reddit-scraper

A tool to scrape posts, images, and comments from a subreddit.

Example usage:

```python
if __name__ == "__main__":
    url = "https://www.reddit.com/r/AmItheAsshole/"

    with RedditScraper(url=url, headless=False) as rs:
        posts = rs.get_posts(limit=16, get_comments=False, download_images_dir="./example")

    print(posts)

```

### Roadmap
| Item                                                                 | Status      |
|----------------------------------------------------------------------|-------------|
| Allow user to scrape specific number of posts                        | Complete    |
| Allow user to scrape all posts in a subreddit                        | Complete    |
| Allow user to download images, gifs                                  | Complete    |
| Allow user to download image galleries                               | In Progress |
| Allow user to scrape specific number of comments                     | In Progress |
| Allow user to scrape all comments on a post                          | In Progress |
| Wait until page load to continue scrolling , rather than random wait | Planned     |
| Save scraped content to a relational database                        | Planned     |

### Before Using!

Currently, urlib3 (used internally by selenium) defaults to HTTP and HTTPS connections pools with a max of 1 connection that can be reused:

```python

class HTTPConnectionPool(ConnectionPool, RequestMethods):

    """
    :param maxsize:
        Number of connections to save that can be reused. More than 1 is useful
        in multithreaded situations. If ``block`` is set to False, more
        connections will be created but they will not be saved once they've
        been used.
    """

    def __init__(
        self,
        host: str,
        port: int | None = None,
        timeout: _TYPE_TIMEOUT | None = _DEFAULT_TIMEOUT,
        maxsize: int = 1,
        block: bool = False,
        headers: typing.Mapping[str, str] | None = None,
        retries: Retry | bool | int | None = None,
        _proxy: Url | None = None,
        _proxy_headers: typing.Mapping[str, str] | None = None,
        _proxy_config: ProxyConfig | None = None,
        **conn_kw: typing.Any,
    ):

```

The concurrency introduced by `ThreadPoolExecutor` causes the following error:

```
2024-03-12 22:40:25,164 urllib3.connectionpool WARNING  Connection pool is full, discarding connection: localhost. Connection pool size: 1
```

To fix this, increase the `maxsize` in `urllib3/connectionpool.py` to a number larger than or equal to the default `max_workers = 8` of the `RedditScraper`.
