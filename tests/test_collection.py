from datetime import datetime, timedelta, timezone

import httpx
import pytest

from ai_info_collector.collection import (
    RssCollector,
    deduplicate_articles,
    filter_fresh_articles,
)
from ai_info_collector.domain import Article, CollectionConfig, SourceConfig


def article(title: str, url: str, published_at: datetime) -> Article:
    return Article(
        source="test",
        title=title,
        url=url,
        published_at=published_at,
        content="content",
    )


def test_filters_articles_outside_window() -> None:
    now = datetime.now(timezone.utc)
    articles = [
        article("new", "https://example.com/new", now - timedelta(days=2)),
        article("old", "https://example.com/old", now - timedelta(days=8)),
    ]

    result = filter_fresh_articles(articles, now=now, freshness_days=7)

    assert [item.title for item in result] == ["new"]


def test_deduplicates_normalized_url_and_same_source_title() -> None:
    published_at = datetime.now(timezone.utc)
    articles = [
        article("Same title", "https://EXAMPLE.com/news/?utm_source=x", published_at),
        article("Same title", "https://example.com/news", published_at),
        article("Other", "https://example.com/other", published_at),
    ]

    result = deduplicate_articles(articles)

    assert [item.title for item in result] == ["Same title", "Other"]


def test_collector_filters_and_deduplicates_while_keeping_source_failures() -> None:
    now = datetime.now(timezone.utc)

    class StubCollector(RssCollector):
        def _fetch_article_content(self, url: str) -> str:
            return ""

        def collect_source(self, source: SourceConfig) -> list[Article]:
            if source.name == "failed":
                raise RuntimeError("feed unavailable")
            return [
                article("fresh", "https://example.com/article?utm_source=test", now),
                article("duplicate", "https://example.com/article", now),
                article("old", "https://example.com/old", now - timedelta(days=8)),
            ]

    config = CollectionConfig(
        freshness_days=7,
        sources=[
            SourceConfig(name="first", url="https://example.com/first"),
            SourceConfig(name="failed", url="https://example.com/failed"),
        ],
    )

    result = StubCollector(httpx.Client()).collect(config)

    assert [item.title for item in result.articles] == ["fresh"]
    assert result.errors == ["source=failed: feed unavailable"]


def test_rss_collector_follows_feed_redirect() -> None:
    feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>Redirected article</title>
        <link>https://example.com/article</link>
        <pubDate>Fri, 28 Aug 2026 12:00:00 GMT</pubDate>
        <description>content</description>
      </item>
    </channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old-feed":
            return httpx.Response(302, headers={"Location": "/new-feed"})
        return httpx.Response(
            200, text=feed, headers={"Content-Type": "application/rss+xml"}
        )

    source = SourceConfig(
        name="test",
        url="https://example.com",
        feed_url="https://example.com/old-feed",
        max_items=10,
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        articles = RssCollector(client).collect_source(source)

    assert [item.title for item in articles] == ["Redirected article"]


def test_rss_collector_discovers_missing_feed_url() -> None:
    feed = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item><title>Discovered article</title>
                <link>https://example.com/article</link>
                <pubDate>Fri, 28 Aug 2026 12:00:00 GMT</pubDate>
                <description>content</description>
            </item>
        </channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/blog":
            html = """<html><head>
                        <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="Feed">
                        </head></html>"""
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
        return httpx.Response(
            200, text=feed, headers={"Content-Type": "application/rss+xml"}
        )

    source = SourceConfig(name="test", url="https://example.com/blog")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        articles = RssCollector(client).collect_source(source)

    assert [item.title for item in articles] == ["Discovered article"]


@pytest.mark.parametrize("summary", ["<p> </p>", "Short RSS summary"])
def test_rss_collector_prefers_page_even_when_summary_exists(summary: str) -> None:
    feed = f"""<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>Article without summary</title>
        <link>https://example.com/article</link>
        <pubDate>Fri, 28 Aug 2026 12:00:00 GMT</pubDate>
        <description><![CDATA[{summary}]]></description>
      </item>
    </channel></rss>"""
    article_html = """<html><body>
      <nav>Navigation text</nav>
      <main><h1>Article heading</h1><p>First paragraph.</p>
        <script>Ignored script text</script><p>Second paragraph.</p></main>
      <footer>Footer text</footer>
    </body></html>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/feed":
            return httpx.Response(
                200, text=feed, headers={"Content-Type": "application/rss+xml"}
            )
        return httpx.Response(
            200, text=article_html, headers={"Content-Type": "text/html"}
        )

    source = SourceConfig(
        name="test",
        url="https://example.com",
        feed_url="https://example.com/feed",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = RssCollector(client).collect(
            CollectionConfig(freshness_days=36500, sources=[source])
        )

    assert result.articles[0].content == (
        "Article heading\nFirst paragraph.\nSecond paragraph."
    )


def test_rss_collector_falls_back_to_content_before_summary() -> None:
    feed = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Example</title>
      <entry><title>Atom article</title>
        <link href="https://example.com/article" />
        <published>2026-08-28T12:00:00Z</published>
        <summary>Short summary</summary>
        <content type="text">Full content from the feed.</content>
      </entry>
    </feed>"""
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/article":
            return httpx.Response(503)
        return httpx.Response(
            200, text=feed, headers={"Content-Type": "application/atom+xml"}
        )

    source = SourceConfig(
        name="test",
        url="https://example.com",
        feed_url="https://example.com/feed",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = RssCollector(client).collect(
            CollectionConfig(freshness_days=36500, sources=[source])
        )

    assert result.articles[0].content == "Full content from the feed."
    assert requested_paths == ["/feed", "/article"]


def test_rss_collector_skips_article_when_no_content_can_be_fetched() -> None:
    feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>Unavailable article</title>
        <link>https://example.com/article</link>
        <pubDate>Fri, 28 Aug 2026 12:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/feed":
            return httpx.Response(
                200, text=feed, headers={"Content-Type": "application/rss+xml"}
            )
        return httpx.Response(503)

    source = SourceConfig(
        name="test",
        url="https://example.com",
        feed_url="https://example.com/feed",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = RssCollector(client).collect(
            CollectionConfig(freshness_days=36500, sources=[source])
        )

    assert result.articles == []
    assert result.errors == ["article=https://example.com/article: content unavailable"]


def test_page_requests_follow_freshness_and_deduplication() -> None:
    now = datetime.now(timezone.utc)
    requests = []

    class Collector(RssCollector):
        def collect_source(self, source):
            return [
                article("fresh", "https://example.com/fresh", now),
                article("duplicate", "https://example.com/fresh", now),
                article("old", "https://example.com/old", now - timedelta(days=8)),
            ]

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Collector(client).collect(
            CollectionConfig(
                sources=[SourceConfig(name="test", url="https://example.com")]
            )
        )

    assert requests == ["https://example.com/fresh"]
    assert len(result.articles) == 1
    assert result.articles[0].content == "content"
    assert result.errors == []
