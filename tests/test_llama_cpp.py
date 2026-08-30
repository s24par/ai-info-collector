import json
import logging
from datetime import datetime, timezone

import pytest

from ai_info_collector.analysis import (
    LlamaCppAnalyzer,
    _build_prompt,
    _extract_json_object,
)
from ai_info_collector.domain import AnalysisConfig, Article, FilterConfig


class FakeLlamaCppBackend:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, prompt: str) -> str:
        return self.text


def test_llama_cpp_response_is_validated() -> None:
    analyzer = LlamaCppAnalyzer(
        AnalysisConfig(
            provider="llama_cpp",
            model_path="/tmp/model.gguf",
            n_threads=2,
            max_tokens=128,
        ),
        backend=FakeLlamaCppBackend(
            json.dumps(
                {
                    "summary": "日本語の要約です。",
                    "category": "AIモデル",
                    "literacy_level": 1,
                    "reason": "ローカルモデルで検証できるため",
                }
            )
        ),
    )
    article = Article(
        source="test",
        title="AI news",
        url="https://example.com/news",
        published_at=datetime.now(timezone.utc),
        content="content",
    )
    filters = FilterConfig(literacy_levels=[1], categories=["AIモデル"])

    result = analyzer.analyze(article, filters)

    assert result.category == "AIモデル"
    assert result.literacy_level == 1


def test_llama_cpp_invalid_json_logs_raw_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_response = "申し訳ありませんが、JSON形式では出力できません。"
    analyzer = LlamaCppAnalyzer(
        AnalysisConfig(
            provider="llama_cpp",
            model_path="/tmp/model.gguf",
            n_threads=2,
            max_tokens=128,
        ),
        backend=FakeLlamaCppBackend(raw_response),
    )
    article = Article(
        source="test",
        title="AI news",
        url="https://example.com/news",
        published_at=datetime.now(timezone.utc),
        content="content",
    )
    filters = FilterConfig(literacy_levels=[1], categories=["AIモデル"])

    with caplog.at_level(logging.WARNING, logger="ai_info_collector.analysis"):
        with pytest.raises(ValueError, match="not valid JSON"):
            analyzer.analyze(article, filters)

    assert any(raw_response in record.getMessage() for record in caplog.records)
    assert any(str(article.url) in record.getMessage() for record in caplog.records)


def test_llama_cpp_tolerates_preamble_around_json() -> None:
    payload = {
        "summary": "日本語の要約です。",
        "category": "AIモデル",
        "literacy_level": 1,
        "reason": "前置き付きでも救済できるため",
    }
    raw_response = f"以下がJSONです。\n{json.dumps(payload)}\n以上です。"
    analyzer = LlamaCppAnalyzer(
        AnalysisConfig(
            provider="llama_cpp",
            model_path="/tmp/model.gguf",
            n_threads=2,
            max_tokens=128,
        ),
        backend=FakeLlamaCppBackend(raw_response),
    )
    article = Article(
        source="test",
        title="AI news",
        url="https://example.com/news",
        published_at=datetime.now(timezone.utc),
        content="content",
    )
    filters = FilterConfig(literacy_levels=[1], categories=["AIモデル"])

    result = analyzer.analyze(article, filters)

    assert result.category == "AIモデル"


def test_extract_json_object_slices_between_first_and_last_brace() -> None:
    raw_response = '前置きテキスト {"a": 1} 後置きテキスト'

    assert _extract_json_object(raw_response) == '{"a": 1}'


def test_extract_json_object_returns_input_when_no_braces() -> None:
    raw_response = "JSONではありません"

    assert _extract_json_object(raw_response) == raw_response


def test_build_prompt_includes_literacy_level_definitions() -> None:
    article = Article(
        source="test",
        title="AI Article",
        url="https://example.com/article",
        published_at=datetime.now(timezone.utc),
        content="Article content here",
    )
    filters = FilterConfig(
        literacy_levels=[1, 2],
        literacy_level_definitions={
            1: "基礎的なAI用語を理解している",
            2: "実践的な開発ができる",
        },
        categories=["AIモデル"],
    )

    prompt = _build_prompt(article, filters, max_characters=200)

    assert "1: 基礎的なAI用語を理解している" in prompt
    assert "2: 実践的な開発ができる" in prompt
    assert "AIモデル" in prompt
