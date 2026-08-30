import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import httpx
import typer

from .analysis import LlamaCppAnalyzer
from .collection import RssCollector
from .config_writer import SourceFeedUpdate, write_source_feed_urls
from .domain import AnalysisConfig, LoggingConfig
from .feed_discovery import FeedDiscoveryError, discover_feed_url
from .http_client import create_collection_client
from .pipeline import CollectionPipeline
from .report import write_level_reports
from .settings import load_config

app = typer.Typer(help="Collect and classify AI-related information.")


def _create_analyzer(config: AnalysisConfig) -> LlamaCppAnalyzer:
    return LlamaCppAnalyzer(config)


def _configure_logging(config: LoggingConfig) -> None:
    log_path = Path(config.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        TimedRotatingFileHandler(
            log_path,
            when="midnight",
            interval=1,
            backupCount=config.retention_days - 1,
            encoding="utf-8",
        )
    ]
    if config.console:
        handlers.append(logging.StreamHandler())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    logging.basicConfig(level=config.level, handlers=handlers, force=True)


@app.callback()
def main() -> None:
    """AI information collector command line interface."""


@app.command()
def run(
    config: Path = typer.Option(Path("config/default.toml"), exists=False),
    output: Path | None = typer.Option(None),
) -> None:
    """Run the collection pipeline."""
    app_config = load_config(config)
    _configure_logging(app_config.logging)
    output_directory = output or Path(app_config.output.path)
    with create_collection_client(app_config.collection) as client:
        result = CollectionPipeline(
            RssCollector(client), _create_analyzer(app_config.analysis)
        ).run(app_config)
    report_directory = write_level_reports(
        output_directory,
        result.items,
        app_config.filter.literacy_levels,
    )
    for error in result.errors:
        typer.echo(f"WARNING: {error}", err=True)
    typer.echo(f"Collected {len(result.items)} analyzed articles")
    typer.echo(f"Output: {report_directory}")
    if not result.items:
        raise typer.Exit(code=1)


@app.command()
def sources(
    config: Path = typer.Option(Path("config/default.toml"), exists=True),
) -> None:
    """Discover missing source feed URLs and write them to the configuration."""
    app_config = load_config(config)
    updates: list[SourceFeedUpdate] = []
    failures: list[str] = []
    with create_collection_client(app_config.collection) as client:
        for source in app_config.collection.sources:
            if source.feed_url is not None:
                continue
            try:
                candidate = discover_feed_url(client, str(source.url))
            except (FeedDiscoveryError, httpx.HTTPError) as error:
                failures.append(f"source={source.name}: {error}")
                continue
            updates.append(
                SourceFeedUpdate(
                    name=source.name,
                    url=str(source.url),
                    feed_url=candidate.url,
                )
            )
            typer.echo(f"Detected source={source.name} feed_url={candidate.url}")

    updated = write_source_feed_urls(config, updates)
    typer.echo(f"Updated {updated} source feed URLs in {config}")
    for failure in failures:
        typer.echo(f"WARNING: {failure}", err=True)
    if failures:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
