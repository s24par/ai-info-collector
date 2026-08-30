from datetime import datetime, timedelta, timezone

import httpx

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
