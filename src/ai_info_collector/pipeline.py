from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .collection import CollectionResult
from .domain import AnalysisResult, AppConfig, Article, CollectionConfig, FilterConfig


class ArticleCollector(Protocol):
    def collect(self, config: CollectionConfig) -> CollectionResult: ...


class ArticleAnalyzer(Protocol):
    def analyze(self, article: Article, filters: FilterConfig) -> AnalysisResult: ...


@dataclass
class PipelineResult:
    items: list[tuple[Article, AnalysisResult]]
    errors: list[str]


class CollectionPipeline:
    def __init__(self, collector: ArticleCollector, analyzer: ArticleAnalyzer) -> None:
        self.collector = collector
        self.analyzer = analyzer

    def run(self, config: AppConfig) -> PipelineResult:
        collected = self.collector.collect(config.collection)
        errors = list(collected.errors)
        source_limits = {
            source.name: source.max_items for source in config.collection.sources
        }
        accepted_by_source: dict[str, int] = {}
        items: list[tuple[Article, AnalysisResult]] = []
        for article in collected.articles:
            if (
                accepted_by_source.get(article.source, 0)
                >= source_limits[article.source]
            ):
                continue
            try:
                result = self.analyzer.analyze(article, config.filter)
            except Exception as error:
                errors.append(f"article={article.url}: {error}")
                continue
            if result.category not in config.filter.categories:
                errors.append(f"article={article.url}: category filter mismatch")
                continue
            if result.literacy_level not in config.filter.literacy_levels:
                errors.append(f"article={article.url}: literacy level filter mismatch")
                continue
            items.append((article, result))
            accepted_by_source[article.source] = (
                accepted_by_source.get(article.source, 0) + 1
            )
        return PipelineResult(items=items, errors=errors)
