from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from ipaddress import ip_address
from urllib.parse import urljoin, urlsplit, urlunsplit

import feedparser
import httpx

from .url_utils import normalize_url

FEED_CONTENT_TYPES = (
    "application/rss+xml",
    "application/atom+xml",
    "application/feed+json",
    "application/xml",
    "text/xml",
)
MAX_RESPONSE_BYTES = 2_000_000


@dataclass(frozen=True)
class FeedCandidate:
    url: str
    source: str
    title: str | None = None
    content_type: str | None = None


class FeedDiscoveryError(RuntimeError):
    pass


class _AlternateFeedParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.candidates: list[FeedCandidate] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "link":
            return
        values = {name.casefold(): value for name, value in attrs if value is not None}
        rel = values.get("rel", "").casefold().split()
        href = values.get("href")
        content_type = values.get("type", "").casefold()
        if "alternate" not in rel or not href or content_type not in FEED_CONTENT_TYPES:
            return
        self.candidates.append(
            FeedCandidate(
                url=urljoin(self.base_url, href),
                source="html-alternate",
                title=values.get("title"),
                content_type=content_type,
            )
        )


def discover_feed_url(client: httpx.Client, url: str) -> FeedCandidate:
    """Discover the best RSS/Atom feed URL for a public website URL."""
    _validate_public_http_url(url)
    tried: list[str] = []
    page_response = _get(client, url)

    page_candidate = FeedCandidate(
        url=str(page_response.url),
        source="direct",
        content_type=page_response.headers.get("content-type"),
    )
    if _is_valid_feed(page_response.content):
        return page_candidate

    candidates = _html_candidates(str(page_response.url), page_response.text)
    candidates.extend(_well_known_candidates(str(page_response.url)))

    for candidate in _unique_candidates(candidates):
        _validate_public_http_url(candidate.url)
        tried.append(candidate.url)
        try:
            response = _get(client, candidate.url)
        except httpx.HTTPError:
            continue
        discovered = FeedCandidate(
            url=str(response.url),
            source=candidate.source,
            title=candidate.title,
            content_type=response.headers.get("content-type") or candidate.content_type,
        )
        if _is_valid_feed(response.content):
            return discovered

    checked = ", ".join(tried) if tried else "no feed candidates"
    raise FeedDiscoveryError(f"feed not found for {url}; checked {checked}")


def _get(client: httpx.Client, url: str) -> httpx.Response:
    response = client.get(url, follow_redirects=True)
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise FeedDiscoveryError(f"response too large: {url}")
    return response


def _is_valid_feed(content: bytes) -> bool:
    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        return False
    return bool(feed.entries or feed.feed.get("title") or feed.feed.get("link"))


def _html_candidates(base_url: str, html: str) -> list[FeedCandidate]:
    parser = _AlternateFeedParser(base_url)
    parser.feed(html)
    return sorted(parser.candidates, key=_candidate_score, reverse=True)


def _well_known_candidates(base_url: str) -> list[FeedCandidate]:
    parts = urlsplit(base_url)
    origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    without_slash = base_url.rstrip("/")
    return [
        FeedCandidate(url=f"{without_slash}/feed", source="well-known"),
        FeedCandidate(url=urljoin(origin, "/feed"), source="well-known"),
        FeedCandidate(url=urljoin(origin, "/rss.xml"), source="well-known"),
        FeedCandidate(url=urljoin(origin, "/feed.xml"), source="well-known"),
        FeedCandidate(url=urljoin(origin, "/atom.xml"), source="well-known"),
    ]


def _candidate_score(candidate: FeedCandidate) -> int:
    score = 0
    content_type = (candidate.content_type or "").casefold()
    title = (candidate.title or "").casefold()
    url = candidate.url.casefold()
    if content_type in {"application/rss+xml", "application/atom+xml"}:
        score += 30
    if "comment" in title or "comment" in url:
        score -= 20
    if any(word in title or word in url for word in ("feed", "rss", "atom")):
        score += 10
    return score


def _unique_candidates(candidates: list[FeedCandidate]) -> list[FeedCandidate]:
    seen: set[str] = set()
    unique: list[FeedCandidate] = []
    for candidate in candidates:
        key = normalize_url(candidate.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _validate_public_http_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise FeedDiscoveryError(f"unsupported feed discovery URL: {url}")
    hostname = parts.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise FeedDiscoveryError(
            f"private feed discovery host is not allowed: {hostname}"
        )
    try:
        address = ip_address(hostname)
    except ValueError:
        return
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise FeedDiscoveryError(
            f"private feed discovery host is not allowed: {hostname}"
        )
