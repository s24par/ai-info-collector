import httpx
import pytest

from ai_info_collector.feed_discovery import (
    FeedCandidate,
    FeedDiscoveryError,
    _unique_candidates,
    discover_feed_url,
)


def test_discovers_url_that_is_already_a_feed() -> None:
    feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Feed</title></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=feed, headers={"Content-Type": "application/rss+xml"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        candidate = discover_feed_url(client, "https://example.com/feed.xml")

    assert candidate.url == "https://example.com/feed.xml"
    assert candidate.source == "direct"


def test_discovers_feed_from_html_alternate_link() -> None:
    html = """<html><head>
    <link rel="alternate" type="application/rss+xml" href="/comments/feed" title="Comments">
    <link rel="alternate" type="application/atom+xml" href="/blog/atom.xml" title="Blog Feed">
    </head></html>"""
    feed = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title></feed>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/blog":
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
        if request.url.path == "/blog/atom.xml":
            return httpx.Response(
                200, text=feed, headers={"Content-Type": "application/atom+xml"}
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        candidate = discover_feed_url(client, "https://example.com/blog")

    assert candidate.url == "https://example.com/blog/atom.xml"
    assert candidate.source == "html-alternate"


def test_discovers_well_known_feed_when_html_has_no_link() -> None:
    feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Feed</title></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/blog/feed":
            return httpx.Response(
                200, text=feed, headers={"Content-Type": "application/rss+xml"}
            )
        return httpx.Response(
            200, text="<html></html>", headers={"Content-Type": "text/html"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        candidate = discover_feed_url(client, "https://example.com/blog")

    assert candidate.url == "https://example.com/blog/feed"
    assert candidate.source == "well-known"


def test_rejects_private_feed_discovery_hosts() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    ) as client:
        with pytest.raises(FeedDiscoveryError):
            discover_feed_url(client, "http://127.0.0.1/feed")


def test_candidate_deduplication_normalizes_tracking_parameters() -> None:
    candidates = _unique_candidates(
        [
            FeedCandidate(
                url="https://EXAMPLE.com/feed/?utm_source=test#section", source="test"
            ),
            FeedCandidate(url="https://example.com/feed", source="test"),
        ]
    )

    assert len(candidates) == 1
