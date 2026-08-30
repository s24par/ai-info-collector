from pathlib import Path

from ai_info_collector.config_writer import SourceFeedUpdate, write_source_feed_urls


def test_writer_matches_source_url_after_normalization(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[collection]\n[[collection.sources]]\n"
        'name = "source"\nurl = "https://EXAMPLE.com/news/?utm_source=test#section"\n',
        encoding="utf-8",
    )

    updated = write_source_feed_urls(
        config_path,
        [
            SourceFeedUpdate(
                name="source",
                url="https://example.com/news",
                feed_url="https://example.com/feed.xml",
            )
        ],
    )

    assert updated == 1
    assert 'feed_url = "https://example.com/feed.xml"' in config_path.read_text(
        encoding="utf-8"
    )
