from __future__ import annotations

import json
import logging
from typing import Any

from .domain import AnalysisConfig, AnalysisResult, Article, FilterConfig

logger = logging.getLogger(__name__)


class LlamaCppBackend:
    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config
        self._model: Any | None = None

    def generate(self, prompt: str) -> str:
        if self._model is None:
            try:
                from llama_cpp import Llama
            except ImportError as error:
                raise RuntimeError(
                    "llama-cpp-python is not installed; install it before using the llama_cpp provider"
                ) from error
            self._model = Llama(
                model_path=self.config.model_path,
                n_ctx=self.config.n_ctx,
                n_threads=self.config.n_threads,
            )

        # create_chat_completion applies the model's chat template (from GGUF metadata) and
        # response_format=json_object grammar-constrains generation to valid JSON, which a raw
        # text completion does not guarantee.
        completion = self._model.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            response_format={"type": "json_object"},
        )
        if isinstance(completion, dict):
            choices = completion.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if isinstance(content, str):
                    return content.strip()
        return str(completion).strip()


class LlamaCppAnalyzer:
    def __init__(
        self,
        config: AnalysisConfig,
        backend: LlamaCppBackend | None = None,
    ) -> None:
        self.config = config
        self.backend = backend or LlamaCppBackend(config)

    def analyze(self, article: Article, filters: FilterConfig) -> AnalysisResult:
        prompt = _build_prompt(article, filters, self.config.summary_max_characters)
        try:
            raw_response = self.backend.generate(prompt)
        except RuntimeError:
            raise
        except Exception as error:  # pragma: no cover - backend-specific failure path
            raise RuntimeError("llama.cpp inference failed") from error
        try:
            return _parse_analysis_response(raw_response, filters, self.config)
        except ValueError:
            logger.warning("article=%s raw_response=%r", article.url, raw_response)
            raise


def _parse_analysis_response(
    raw_response: str, filters: FilterConfig, config: AnalysisConfig
) -> AnalysisResult:
    try:
        result = AnalysisResult.model_validate(
            json.loads(_extract_json_object(raw_response))
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("LLM response was not valid JSON") from error
    if result.category not in filters.categories:
        raise ValueError(f"Unsupported category: {result.category}")
    if result.literacy_level not in filters.literacy_levels:
        raise ValueError(f"Unsupported literacy level: {result.literacy_level}")
    if len(result.summary) > config.summary_max_characters:
        raise ValueError("Summary exceeds configured character limit")
    return result


def _extract_json_object(raw_response: str) -> str:
    """Tolerate stray text around the JSON object by slicing from the first '{' to the last '}'."""
    start = raw_response.find("{")
    end = raw_response.rfind("}")
    if start == -1 or end == -1 or end < start:
        return raw_response
    return raw_response[start : end + 1]


def _build_prompt(article: Article, filters: FilterConfig, max_characters: int) -> str:
    categories = ", ".join(filters.categories)
    level_items = []
    for level in filters.literacy_levels:
        definition = filters.literacy_level_definitions.get(level, "")
        if definition:
            level_items.append(f"{level}: {definition}")
        else:
            level_items.append(str(level))
    levels = "; ".join(level_items)
    return (
        "以下の記事を分析し、JSONオブジェクトのみを返してください。前置きや説明文は一切出力しないでください。"
        f"summaryは日本語で{max_characters}文字以内、categoryは次の候補から1つ: {categories}。"
        f"literacy_levelは次の定義を基準に数値から1つ選択してください: [{levels}]。reasonは日本語で100文字以内、判定理由を簡潔に記述してください。\n"
        f"タイトル: {article.title}\n本文: {article.content}"
    )
