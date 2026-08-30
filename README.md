# AI Information Collector

A Python application that collects AI-related information and summarizes/classifies it using a local llama.cpp inference engine.

## Overview

This app collects articles from configured RSS/Atom feeds and uses a locally placed GGUF model to summarize and categorize them. The generated results are output as Markdown reports.

The current implementation policy is as follows:

- Only local execution is supported
- Cloud LLM / OpenAI-compatible API configuration is not implemented
- The inference backend assumes `llama-cpp-python`

## Setup

```bash
uv sync --extra dev
```

Prepare a local GGUF model and set its file path in `analysis.model_path` in the configuration file.

The recommended directory structure is as follows.

```text
.
├── config/
│   └── default.toml
├── models/
│   └── gguf/
│       └── Qwen2.5-3B-Instruct-Q4_K_M.gguf
├── output/
├── src/
└── uv.lock
```

Example `model_path`:

```toml
[analysis]
provider = "llama_cpp"
model_path = "models/gguf/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
n_ctx = 40960
n_threads = 4
max_tokens = 256
temperature = 0.0
```

`llama-cpp-python` loads this GGUF file directly. Relative paths are resolved relative to the project root, so the same model can be referenced even if the execution directory changes.

## Run

```bash
uv run ai-info-collector run --config config/default.toml
```

When run, it collects articles from the configured sources and outputs the summarized/classified results to `output/%Y%m%d%H%M%S/`. Under it, `level_1.md`, `level_2.md`, and `level_3.md` are created for each configured literacy level. Files are created even for levels with no matching articles.

Logs are output to `logs/app.log` and rotated to `logs/app.log.YYYY-MM-DD` format when the date changes. The last 3 days are kept, including the current log. The retention period can be changed with `logging.retention_days`.

Collection runs in the order the sources appear in the configuration file. Articles are analyzed after checking freshness and duplication, and articles passing both the category and literacy level filters are output up to `max_items` per source.

`collection.retry_count` is the maximum number of retries after the initial request. On communication failure, HTTP 429, or HTTP 500/502/503/504 for RSS/Atom GET/HEAD requests, it retries with exponential backoff and honors the server's `Retry-After` header. Other 4xx errors and POST requests are not retried.

## Source feed discovery

An information source can be added with just `name` and `url`. `feed_url` and `max_items` are optional.

```toml
[[collection.sources]]
name = "example_ai_blog"
url = "https://example.com/blog"
```

For sources without `feed_url` set, the following command can detect the RSS/Atom feed and append it to the configuration file.

```bash
uv run ai-info-collector sources --config config/default.toml
```

This command checks `url` itself, the HTML `<link rel="alternate">`, and common paths such as `/feed` or `/rss.xml` in order. Automatic detection may fail for sites that don't publish RSS/Atom, pages generated only via JavaScript, or sites requiring login or bot protection. In such cases, manually set the RSS/Atom URL provided by the site in `feed_url`.

## Testing

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

If automatic fixes are needed, run the following.

```bash
uv run ruff check src tests --fix
uv run ruff format src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute, and [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Example configuration

`config/default.toml` is an example configuration for local llama.cpp execution.

```toml
[analysis]
provider = "llama_cpp"
summary_max_characters = 200
model_path = "models/gguf/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
n_ctx = 40960
n_threads = 4
max_tokens = 256
temperature = 0.0
```

## Notes

- Set `model_path` to the path of a GGUF file that actually exists.
- With `llama-cpp-python`, the CPU/GPU capability of the local environment affects execution performance.
