from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from .domain import AnalysisResult, Article


def render_markdown(items: Iterable[tuple[Article, AnalysisResult]]) -> str:
    lines = ["# AI関連情報レポート", ""]
    for article, result in items:
        lines.extend(
            [
                f"## {article.title}",
                "",
                f"- 情報源: {article.source}",
                f"- 公開日: {article.published_at.date().isoformat()}",
                f"- カテゴリ: {result.category}",
                f"- リテラシーレベル: {result.literacy_level}",
                f"- URL: {article.url}",
                "",
                result.summary,
                "",
                f"判定理由: {result.reason}",
                "",
            ]
        )
    return "\n".join(lines)


def write_markdown(path: Path, items: Iterable[tuple[Article, AnalysisResult]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(items), encoding="utf-8")


def write_level_reports(
    output_directory: Path,
    items: Iterable[tuple[Article, AnalysisResult]],
    literacy_levels: Iterable[int],
    generated_at: datetime | None = None,
) -> Path:
    report_directory = output_directory / (generated_at or datetime.now()).strftime(
        "%Y%m%d%H%M%S"
    )
    items_by_level = {level: [] for level in literacy_levels}
    for item in items:
        items_by_level.setdefault(item[1].literacy_level, []).append(item)

    for level, level_items in items_by_level.items():
        write_markdown(report_directory / f"level_{level}.md", level_items)

    return report_directory
