# AI Information Collector

A Python application that collects AI-related information and summarizes/classifies it using an LLM, either an OpenAI SDK-compatible cloud provider or a local llama.cpp inference engine.

## Overview

This app collects articles from configured RSS/Atom feeds and uses an LLM to summarize and categorize them. The generated results are output as Markdown reports.

The current implementation policy is as follows:

- Groq (`GROQ_API_KEY`) is the default OpenAI SDK-compatible cloud provider
- Claude, OpenAI, OpenRouter, and xAI are also supported through the same `openai` package and backend
- If the selected cloud provider's API key is not set, the app automatically falls back to a local `llama-cpp-python` model
- Analysis settings are split across `config/default.toml` (common), one provider-specific TOML file, and `config/llama_cpp.toml` for the local fallback

## Setup

```bash
uv sync --extra dev
```

Copy `.env.example` to `.env` and set the API key for the selected cloud
provider:

```bash
cp .env.example .env
# then edit .env and set GROQ_API_KEY=...
```

| Provider | `provider` value | API key environment variable | Settings file |
| --- | --- | --- | --- |
| Groq | `groq` | `GROQ_API_KEY` | `config/groq.toml` |
| Claude | `claude` | `ANTHROPIC_API_KEY` | `config/claude.toml` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `config/openai.toml` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | `config/openrouter.toml` |
| xAI | `xai` | `XAI_API_KEY` | `config/xai.toml` |
| Local llama.cpp | `llama_cpp` | Not required | `config/llama_cpp.toml` |

`.env` is loaded automatically at startup and is excluded from version control via `.gitignore`.

To use the local `llama-cpp-python` fallback (or run with `provider = "llama_cpp"` explicitly),
for instructions on using the prebuilt CPU-only `llama-cpp-python` wheel on
Windows, see [WINDOWS_SETUP.md](WINDOWS_SETUP.md).

Prepare a local GGUF model and set its file path in `model_path` in `config/llama_cpp.toml`.

The recommended directory structure is as follows.

```text
.
├── .env
├── config/
│   ├── default.toml
│   ├── claude.toml
│   ├── groq.toml
│   ├── openai.toml
│   ├── openrouter.toml
│   ├── xai.toml
│   └── llama_cpp.toml
├── models/
│   └── gguf/
│       └── Qwen2.5-3B-Instruct-Q4_K_M.gguf
├── output/
├── src/
└── uv.lock
```

Example `config/default.toml` (common settings):

```toml
[analysis]
provider = "groq"
summary_max_characters = 300
```

Example `config/groq.toml`:

```toml
model = "openai/gpt-oss-120b"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"
max_tokens = 1024
temperature = 0.0
```

Example `config/claude.toml`:

```toml
model = "claude-sonnet-4-5"
base_url = "https://api.anthropic.com/v1/"
api_key_env = "ANTHROPIC_API_KEY"
max_tokens = 1024
temperature = 0.0
json_response_format = false
```

All cloud providers use the `openai` Python package and the shared
`OpenAICompatibleBackend`. Their complete settings are in the corresponding
files under `config/`.

Example `config/llama_cpp.toml`:

```toml
model_path = "models/gguf/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
n_ctx = 40960
n_threads = 4
n_gpu_layers = 0
n_batch = 512
main_gpu = 0
max_tokens = 512
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

RSS/Atom feeds provide article discovery and publication dates. After freshness
filtering and deduplication, the linked HTML page is fetched for every article,
even when the feed includes a summary. Extracted page text is preferred for
summarization. If page content cannot be obtained, the feed's `content` field is
used, with `summary` as a last resort. Articles with no usable content are
skipped with a warning. Page extraction does not execute JavaScript or support
PDFs.

`summary_max_characters` is a generation target. If the model returns a longer
summary, the collector keeps it in the report and records a warning in the log.

`collection.retry_count` is the maximum number of retries after the initial request. On communication failure, HTTP 429, or HTTP 500/502/503/504 for feed and article-page GET/HEAD requests, it retries with exponential backoff and honors the server's `Retry-After` header. Other 4xx errors and POST requests are not retried.

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

`config/default.toml`, the selected cloud provider settings file, and
`config/llama_cpp.toml` together form a complete configuration. The repository
includes settings files for Groq, Claude, OpenAI, OpenRouter, and xAI.

## Notes

- With `provider = "groq"` and no `GROQ_API_KEY` set, the app logs a warning and falls back to `llama_cpp`; make sure `config/llama_cpp.toml` points at a valid `model_path` if you rely on this fallback.
- To use another cloud provider, set its value from the table above as `provider` in `config/default.toml` and set its API key in `.env`. An unset key uses the same llama.cpp fallback.
- To add an OpenAI SDK-compatible provider, create `config/<provider>.toml` with `model`, `base_url`, and `api_key_env`; set `provider = "<provider>"` in `config/default.toml`; then add that environment variable to `.env`. No change to `analysis.py` is required.
- Set `model_path` in `config/llama_cpp.toml` to the path of a GGUF file that actually exists.
- GPU offloading requires a hardware-accelerated `llama-cpp-python` build; the
  default CPU wheel cannot use CUDA even when `n_gpu_layers` is enabled.
- With `llama-cpp-python`, the CPU/GPU capability of the local environment affects execution performance.
