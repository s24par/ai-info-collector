import logging
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler

from typer.testing import CliRunner

from ai_info_collector import cli
from ai_info_collector.domain import AnalysisResult, Article, LoggingConfig
from ai_info_collector.feed_discovery import FeedCandidate
from ai_info_collector.pipeline import PipelineResult


class FakePipeline:
    def __init__(self, collector: object, analyzer: object) -> None:
        pass

    def run(self, config: object) -> PipelineResult:
        article = Article(
            source="test",
            title="AI news",
            url="https://example.com/news",
            published_at=datetime.now(timezone.utc),
            content="content",
        )
        result = AnalysisResult(
            summary="要約です。",
            category="AIモデル",
            literacy_level=1,
            reason="テスト",
        )
        return PipelineResult(items=[(article, result)], errors=[])


def test_run_writes_report_without_external_services(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "CollectionPipeline", FakePipeline)
    output = tmp_path / "output"

    result = CliRunner().invoke(
        cli.app, ["run", "--config", "config/default.toml", "--output", str(output)]
    )

    assert result.exit_code == 0
    report_directories = list(output.iterdir())
    assert len(report_directories) == 1
    assert str(report_directories[0]) in result.stdout
    assert "AI news" in (report_directories[0] / "level_1.md").read_text(
        encoding="utf-8"
    )
    assert (report_directories[0] / "level_2.md").exists()
    assert (report_directories[0] / "level_3.md").exists()


def test_configure_logging_creates_log_file(tmp_path) -> None:
    log_path = tmp_path / "nested" / "app.log"
    config = LoggingConfig(level="WARNING", file=str(log_path), console=False)

    cli._configure_logging(config)
    logging.getLogger("ai_info_collector.analysis").warning("test message")

    assert log_path.exists()
    assert "test message" in log_path.read_text(encoding="utf-8")
    file_handler = next(
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, TimedRotatingFileHandler)
    )
    assert file_handler.when == "MIDNIGHT"
    assert file_handler.backupCount == 2


def test_sources_writes_discovered_feed_urls(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[collection]\nfreshness_days = 7\n"
        "[[collection.sources]]\nname = 'source'\nurl = 'https://example.com'\n"
        "[analysis]\nmodel = 'model'\nmodel_path = '/tmp/test-model.gguf'\n"
        "[output]\npath = 'report.md'\n[filter]\n"
        "literacy_levels = [1]\ncategories = ['AIモデル']\n[logging]\nfile = 'app.log'\n",
        encoding="utf-8",
    )

    def fake_discover_feed_url(client, url):
        return FeedCandidate(url="https://example.com/feed.xml", source="test")

    monkeypatch.setattr(cli, "discover_feed_url", fake_discover_feed_url)

    result = CliRunner().invoke(cli.app, ["sources", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Updated 1 source feed URLs" in result.stdout
    assert 'feed_url = "https://example.com/feed.xml"' in config_path.read_text(
        encoding="utf-8"
    )
