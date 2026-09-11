# Changelog

All notable changes to this project are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Switched the default LLM provider from local llama.cpp to the Groq cloud API (`GROQ_API_KEY` via `.env`), with automatic fallback to llama.cpp when the key is unset.
- Split analysis provider settings into `config/llama_cpp.toml` and `config/groq.toml`, merged with `config/default.toml` at load time; `config/default.toml` now only holds the common `provider`/`summary_max_characters` settings.
- Consolidated cloud LLM access on the `openai` package and introduced a generic OpenAI SDK-compatible provider registry and backend, with Claude support via `ANTHROPIC_API_KEY` and provider-specific JSON response handling.

### Added

- Added quality gates and collaboration documentation for project standardization.