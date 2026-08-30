from datetime import datetime, timezone

from ai_info_collector.domain import AnalysisResult, Article
from ai_info_collector.report import render_markdown, write_level_reports


def test_markdown_contains_required_article_fields() -> None:
    article = Article(
        source="test",
        title="AI news",
        url="https://example.com/news",
        published_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        content="content",
    )
    result = AnalysisResult(
        summary="日本語の要約です。",
        category="AIモデル",
        literacy_level=2,
        reason="業務改善に関する内容のため",
    )

    markdown = render_markdown([(article, result)])

    assert "AI news" in markdown
    assert "日本語の要約です。" in markdown
    assert "https://example.com/news" in markdown
    assert "AIモデル" in markdown
    assert "リテラシーレベル: 2" in markdown


def test_write_level_reports_separates_items_and_creates_empty_levels(tmp_path) -> None:
    article = Article(
        source="test",
        title="AI news",
        url="https://example.com/news",
        published_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        content="content",
    )
    result = AnalysisResult(
        summary="日本語の要約です。",
        category="AIモデル",
        literacy_level=2,
        reason="業務改善に関する内容のため",
    )

    output_directory = write_level_reports(
        tmp_path,
        [(article, result)],
        [1, 2, 3],
        generated_at=datetime(2026, 8, 30, 12, 34, 56),
    )

    assert output_directory == tmp_path / "20260830123456"
    assert "AI news" not in (output_directory / "level_1.md").read_text(
        encoding="utf-8"
    )
    assert "AI news" in (output_directory / "level_2.md").read_text(encoding="utf-8")
    assert "AI news" not in (output_directory / "level_3.md").read_text(
        encoding="utf-8"
    )
