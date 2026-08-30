from pathlib import Path

from ai_info_collector.settings import load_config

ROOT = Path(__file__).parents[1]


def test_default_config_is_valid() -> None:
    config = load_config(ROOT / "config/default.toml")

    assert config.collection.freshness_days == 7
    assert config.analysis.summary_max_characters == 200
    assert config.analysis.max_tokens == 512
    assert [source.name for source in config.collection.sources] == [
        "openai",
        "deepmind",
        "huggingface",
        "github_copilot",
        "itmedia_ai_plus",
        "stackoverflow_ai",
    ]
    assert all(source.max_items == 10 for source in config.collection.sources)
    assert config.analysis.model_path == str(
        (ROOT / "models/gguf/Qwen2.5-3B-Instruct-Q4_K_M.gguf").resolve()
    )
    assert config.filter.literacy_levels == [1, 2, 3]
    assert 1 in config.filter.literacy_level_definitions
    assert "基礎利用者" in config.filter.literacy_level_definitions[1]
    assert config.output.path == "output"
    assert config.logging.retention_days == 3


def test_source_feed_url_and_max_items_are_optional(tmp_path: Path) -> None:
    config_path = tmp_path / "minimal-source.toml"
    config_path.write_text(
        "[collection]\nfreshness_days = 7\n"
        "[[collection.sources]]\nname = 'source'\n"
        "url = 'https://example.com'\n"
        "[analysis]\nmodel_path = '/tmp/test-model.gguf'\n"
        "[output]\npath = 'report.md'\n[filter]\n"
        "literacy_levels = [1]\ncategories = ['AIモデル']\n[logging]\nfile = 'app.log'\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.collection.sources[0].feed_url is None
    assert config.collection.sources[0].max_items == 10


def test_invalid_source_max_items_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        "[collection]\nfreshness_days = 7\n"
        "[[collection.sources]]\nname = 'source'\n"
        "url = 'https://example.com'\nfeed_url = 'https://example.com/feed'\nmax_items = 0\n"
        "[analysis]\nmodel_path = '/tmp/test-model.gguf'\n"
        "[output]\npath = 'report.md'\n[filter]\n"
        "literacy_levels = [1]\ncategories = ['AIモデル']\n[logging]\nfile = 'app.log'\n"
    )

    try:
        load_config(config_path)
    except ValueError as error:
        assert "Invalid configuration" in str(error)
    else:
        raise AssertionError("Invalid configuration was accepted")
