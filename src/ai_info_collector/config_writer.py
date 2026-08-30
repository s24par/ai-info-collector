from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tomlkit

from .url_utils import normalize_url


@dataclass(frozen=True)
class SourceFeedUpdate:
    name: str
    url: str
    feed_url: str


def write_source_feed_urls(config_path: Path, updates: list[SourceFeedUpdate]) -> int:
    if not updates:
        return 0

    document = tomlkit.parse(config_path.read_text(encoding="utf-8"))
    collection = document.get("collection")
    if collection is None or "sources" not in collection:
        raise ValueError("collection.sources is missing from configuration")

    updated = 0
    for source in collection["sources"]:
        name = str(source.get("name", ""))
        url = str(source.get("url", ""))
        for update in updates:
            if (
                update.name == name
                and _same_url(update.url, url)
                and "feed_url" not in source
            ):
                source["feed_url"] = update.feed_url
                updated += 1
                break

    if updated:
        config_path.write_text(tomlkit.dumps(document), encoding="utf-8")
    return updated


def _same_url(left: str, right: str) -> bool:
    return normalize_url(left) == normalize_url(right)
