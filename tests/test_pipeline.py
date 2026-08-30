from datetime import datetime, timezone

from ai_info_collector.collection import CollectionResult
from ai_info_collector.domain import AnalysisResult, AppConfig, Article
from ai_info_collector.pipeline import CollectionPipeline


class FakeCollector:
    def collect(self, config):
        return CollectionResult(
            articles=[
                Article(
                    source="openai",
                    title="openai article",
                    url="https://example.com/openai",
                    published_at=datetime.now(timezone.utc),
                    content="content",
                )
            ],
            errors=["source=deepmind: feed unavailable"],
        )


class FakeAnalyzer:
    def analyze(self, article, filters):
        return AnalysisResult(
            summary="要約です。",
            category="AIモデル",
            literacy_level=1,
            reason="テスト",
        )


class MultiArticleCollector:
    def collect(self, config):
        return CollectionResult(
            articles=[
                Article(
                    source=source.name,
                    title=f"{source.name} article {index}",
                    url=f"https://example.com/{source.name}/{index}",
                    published_at=datetime.now(timezone.utc),
                    content="content",
                )
                for source in config.sources
                for index in range(3)
            ],
            errors=[],
        )


class FilteringAnalyzer(FakeAnalyzer):
    def analyze(self, article, filters):
        result = super().analyze(article, filters)
        if article.title.endswith("0"):
            return result.model_copy(update={"category": "除外カテゴリ"})
        return result


def test_pipeline_keeps_successes_when_one_source_fails() -> None:
    config = AppConfig.model_validate(
        {
            "collection": {
                "freshness_days": 7,
                "sources": [
                    {
                        "name": "openai",
                        "url": "https://openai.com",
                        "feed_url": "https://openai.com/feed",
                        "max_items": 10,
                    },
                    {
                        "name": "deepmind",
                        "url": "https://deepmind.google",
                        "feed_url": "https://deepmind.google/feed",
                        "max_items": 10,
                    },
                ],
            },
            "analysis": {
                "provider": "llama_cpp",
                "model": "test",
                "model_path": "/tmp/test-model.gguf",
            },
            "output": {"path": "report.md"},
            "filter": {"literacy_levels": [1], "categories": ["AIモデル"]},
            "logging": {"file": "app.log"},
        }
    )

    result = CollectionPipeline(FakeCollector(), FakeAnalyzer()).run(config)

    assert len(result.items) == 1
    assert len(result.errors) == 1
    assert "deepmind" in result.errors[0]


def test_pipeline_limits_each_source_in_collection_order() -> None:
    config = AppConfig.model_validate(
        {
            "collection": {
                "freshness_days": 7,
                "sources": [
                    {
                        "name": "openai",
                        "url": "https://openai.com",
                        "feed_url": "https://openai.com/feed",
                        "max_items": 2,
                    },
                    {
                        "name": "huggingface",
                        "url": "https://huggingface.co",
                        "feed_url": "https://huggingface.co/feed",
                        "max_items": 2,
                    },
                ],
            },
            "analysis": {
                "provider": "llama_cpp",
                "model": "test",
                "model_path": "/tmp/test-model.gguf",
            },
            "output": {"path": "report.md"},
            "filter": {"literacy_levels": [1], "categories": ["AIモデル"]},
            "logging": {"file": "app.log"},
        }
    )

    result = CollectionPipeline(MultiArticleCollector(), FakeAnalyzer()).run(config)

    assert [article.title for article, _ in result.items] == [
        "openai article 0",
        "openai article 1",
        "huggingface article 0",
        "huggingface article 1",
    ]


def test_pipeline_applies_source_limit_after_filtering() -> None:
    config = AppConfig.model_validate(
        {
            "collection": {
                "freshness_days": 7,
                "sources": [
                    {
                        "name": "openai",
                        "url": "https://openai.com",
                        "feed_url": "https://openai.com/feed",
                        "max_items": 1,
                    },
                    {
                        "name": "deepmind",
                        "url": "https://deepmind.google",
                        "feed_url": "https://deepmind.google/feed",
                        "max_items": 3,
                    },
                    {
                        "name": "huggingface",
                        "url": "https://huggingface.co",
                        "feed_url": "https://huggingface.co/feed",
                        "max_items": 2,
                    },
                ],
            },
            "analysis": {
                "provider": "llama_cpp",
                "model": "test",
                "model_path": "/tmp/test-model.gguf",
            },
            "output": {"path": "report.md"},
            "filter": {"literacy_levels": [1], "categories": ["AIモデル"]},
            "logging": {"file": "app.log"},
        }
    )

    result = CollectionPipeline(MultiArticleCollector(), FilteringAnalyzer()).run(
        config
    )

    assert [article.title for article, _ in result.items] == [
        "openai article 1",
        "deepmind article 1",
        "deepmind article 2",
        "huggingface article 1",
        "huggingface article 2",
    ]
