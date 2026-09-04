from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SourceConfig(BaseModel):
    name: str = Field(min_length=1)
    url: HttpUrl
    feed_url: HttpUrl | None = None
    max_items: int = Field(default=10, ge=1)


class CollectionConfig(BaseModel):
    freshness_days: int = Field(default=7, ge=1)
    timeout_seconds: float = Field(default=20, gt=0)
    retry_count: int = Field(default=2, ge=0)
    sources: list[SourceConfig] = Field(min_length=1)


class AnalysisConfig(BaseModel):
    provider: Literal["llama_cpp"] = "llama_cpp"
    summary_max_characters: int = Field(default=200, ge=50)
    model_path: str = Field(min_length=1)
    n_ctx: int = Field(default=4096, gt=0)
    n_threads: int = Field(default=4, gt=0)
    n_gpu_layers: int = Field(default=0, ge=-1)
    n_batch: int = Field(default=512, gt=0)
    main_gpu: int = Field(default=0, ge=0)
    max_tokens: int = Field(default=256, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)

    def model_post_init(self, __context: object) -> None:
        resolved_path = Path(self.model_path)
        if not resolved_path.is_absolute():
            repo_root = Path(__file__).resolve().parents[2]
            self.model_path = str((repo_root / resolved_path).resolve())


class OutputConfig(BaseModel):
    path: str = Field(min_length=1)


DEFAULT_LITERACY_LEVEL_DEFINITIONS: dict[int, str] = {
    1: "基礎利用者: AI利用ルールや情報漏洩リスクを理解し、日常業務でAIを利用できる",
    2: "実践利用者: 業務課題に応じたプロンプト設計やAI活用による業務改善ができ、周囲に説明できる",
    3: "推進リーダー: 部門内の活用リード、ツール選定・ルール整備への参画、運用提案ができる",
}


class FilterConfig(BaseModel):
    literacy_levels: list[int] = Field(min_length=1)
    literacy_level_definitions: dict[int, str] = Field(
        default_factory=lambda: DEFAULT_LITERACY_LEVEL_DEFINITIONS.copy()
    )
    categories: list[str] = Field(min_length=1)


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str = Field(min_length=1)
    console: bool = True
    retention_days: int = Field(default=3, ge=1)


class AppConfig(BaseModel):
    collection: CollectionConfig
    analysis: AnalysisConfig
    output: OutputConfig
    filter: FilterConfig
    logging: LoggingConfig


class Article(BaseModel):
    source: str
    title: str
    url: HttpUrl
    published_at: datetime
    content: str


class AnalysisResult(BaseModel):
    summary: str = Field(min_length=1)
    category: str
    literacy_level: int = Field(ge=1, le=3)
    reason: str = Field(min_length=1)
