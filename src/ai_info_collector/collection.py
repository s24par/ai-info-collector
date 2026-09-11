from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

import feedparser
import httpx
from bs4 import BeautifulSoup

from .domain import Article, CollectionConfig, SourceConfig
from .feed_discovery import discover_feed_url
from .url_utils import normalize_url


@dataclass
class CollectionResult:
    articles: list[Article]
    errors: list[str]


def normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def filter_fresh_articles(
    articles: Iterable[Article], *, now: datetime, freshness_days: int
) -> list[Article]:
    cutoff = now - timedelta(days=freshness_days)
    return [article for article in articles if cutoff <= article.published_at <= now]


def deduplicate_articles(articles: Iterable[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    unique: list[Article] = []
    for article in articles:
        url_key = normalize_url(str(article.url))
        title_key = (article.source, normalize_title(article.title))
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(article)
    return unique


class RssCollector:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def collect_source(self, source: SourceConfig) -> list[Article]:
        feed_url = (
            str(source.feed_url)
            if source.feed_url is not None
            else discover_feed_url(self.client, str(source.url)).url
        )
        response = self.client.get(feed_url, follow_redirects=True)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        articles: list[Article] = []
        for entry in feed.entries:
            published_at = _published_at(entry)
            link = entry.get("link")
            title = entry.get("title")
            if not published_at or not link or not title:
                continue
            content = _entry_content(entry)
            articles.append(
                Article(
                    source=source.name,
                    title=title.strip(),
                    url=link,
                    published_at=published_at,
                    content=content,
                )
            )
        return articles

    def _fetch_article_content(self, url: str) -> str:
        try:
            response = self.client.get(url, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            return ""

        content_type = response.headers.get("content-type", "").casefold()
        if content_type and "html" not in content_type:
            return ""
        return _extract_article_content(response.text)

    def collect(self, config: CollectionConfig) -> CollectionResult:
        articles: list[Article] = []
        errors: list[str] = []
        now = datetime.now(timezone.utc)
        for source in config.sources:
            try:
                fresh = deduplicate_articles(
                    filter_fresh_articles(
                        self.collect_source(source),
                        now=now,
                        freshness_days=config.freshness_days,
                    )
                )
            except Exception as error:
                errors.append(f"source={source.name}: {error}")
                continue
            for article in fresh:
                content = (
                    self._fetch_article_content(str(article.url)) or article.content
                )
                if content:
                    articles.append(article.model_copy(update={"content": content}))
                else:
                    errors.append(f"article={article.url}: content unavailable")
        return CollectionResult(articles=deduplicate_articles(articles), errors=errors)


def _published_at(entry: object) -> datetime | None:
    published = getattr(entry, "published_parsed", None)
    if published is None:
        return None
    return datetime(*published[:6], tzinfo=timezone.utc)


def _entry_content(entry: object) -> str:
    for item in entry.get("content", []):
        value = item.get("value", "")
        if isinstance(value, str) and (text := _plain_text(value)):
            return text
    summary = entry.get("summary", "")
    if isinstance(summary, str) and (text := _plain_text(summary)):
        return text
    return ""


def _plain_text(value: str) -> str:
    return "\n".join(BeautifulSoup(value, "html.parser").stripped_strings)


def _extract_article_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select(
        "script, style, noscript, nav, header, footer, aside, form, svg"
    ):
        element.decompose()

    candidates = [*soup.find_all("article"), *soup.find_all("main")]
    candidates.extend(soup.select('[role="main"]'))
    root = max(candidates, key=lambda item: len(item.get_text()), default=soup.body)
    if root is None:
        return ""

    blocks = root.find_all(["h1", "h2", "h3", "p", "blockquote", "pre"])
    text = "\n".join(
        normalized
        for block in blocks
        if (normalized := " ".join(block.stripped_strings))
    )
    if not text:
        text = " ".join(root.stripped_strings)
    return text.strip()
