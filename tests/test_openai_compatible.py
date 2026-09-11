import sys
from types import ModuleType, SimpleNamespace

import pytest

from ai_info_collector.analysis import OpenAICompatibleBackend
from ai_info_collector.domain import OpenAICompatibleSettings


def _install_fake_openai_module(monkeypatch: pytest.MonkeyPatch, create_kwargs: dict):
    class FakeCompletions:
        def create(self, **kwargs):
            create_kwargs.update(kwargs)
            message = SimpleNamespace(content='{"result": "ok"}')
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            create_kwargs["client_init"] = kwargs
            self.chat = FakeChat()

    fake_module = ModuleType("openai")
    fake_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)


def test_groq_backend_uses_groq_base_url_and_json_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_kwargs: dict = {}
    _install_fake_openai_module(monkeypatch, create_kwargs)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    backend = OpenAICompatibleBackend(
        "groq",
        OpenAICompatibleSettings(
            model="openai/gpt-oss-120b",
            base_url="https://api.groq.com/openai/v1",
            api_key_env="GROQ_API_KEY",
            max_tokens=1536,
            temperature=0.5,
        ),
    )

    result = backend.generate("test")

    assert create_kwargs["client_init"]["api_key"] == "test-key"
    assert create_kwargs["client_init"]["base_url"] == "https://api.groq.com/openai/v1"
    assert create_kwargs["model"] == "openai/gpt-oss-120b"
    assert create_kwargs["max_tokens"] == 1536
    assert create_kwargs["temperature"] == 0.5
    assert create_kwargs["response_format"] == {"type": "json_object"}
    assert result == '{"result": "ok"}'


def test_claude_backend_uses_claude_base_url_and_omits_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_kwargs: dict = {}
    _install_fake_openai_module(monkeypatch, create_kwargs)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    backend = OpenAICompatibleBackend(
        "claude",
        OpenAICompatibleSettings(
            model="claude-sonnet-4-5",
            base_url="https://api.anthropic.com/v1/",
            api_key_env="ANTHROPIC_API_KEY",
            json_response_format=False,
        ),
    )

    backend.generate("test")

    assert create_kwargs["client_init"]["api_key"] == "test-key"
    assert create_kwargs["client_init"]["base_url"] == "https://api.anthropic.com/v1/"
    assert "response_format" not in create_kwargs


def test_backend_missing_api_key_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_kwargs: dict = {}
    _install_fake_openai_module(monkeypatch, create_kwargs)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    backend = OpenAICompatibleBackend(
        "groq",
        OpenAICompatibleSettings(
            model="openai/gpt-oss-120b",
            base_url="https://api.groq.com/openai/v1",
            api_key_env="GROQ_API_KEY",
        ),
    )

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not set"):
        backend.generate("test")


def test_arbitrary_provider_name_works_when_settings_are_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_kwargs: dict = {}
    _install_fake_openai_module(monkeypatch, create_kwargs)
    monkeypatch.setenv("CUSTOM_API_KEY", "test-key")
    backend = OpenAICompatibleBackend(
        "custom",
        OpenAICompatibleSettings(
            model="custom-model",
            base_url="https://api.example.com/v1",
            api_key_env="CUSTOM_API_KEY",
        ),
    )

    result = backend.generate("test")

    assert create_kwargs["client_init"]["base_url"] == "https://api.example.com/v1"
    assert result == '{"result": "ok"}'
