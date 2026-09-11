import tomllib
from pathlib import Path

from pydantic import ValidationError

from .domain import AppConfig


def load_config(path: Path) -> AppConfig:
    """Load and validate an application TOML configuration."""
    with path.open("rb") as config_file:
        values = tomllib.load(config_file)
    _merge_provider_configs(values, path.parent)
    try:
        return AppConfig.model_validate(values)
    except ValidationError as error:
        raise ValueError(f"Invalid configuration: {error}") from error


def _merge_provider_configs(values: dict, config_dir: Path) -> None:
    """Merge sibling <provider>.toml files into analysis.<provider>, if present.

    llama_cpp is always considered since it is the fallback backend; the active
    analysis.provider is merged in addition, whatever its name.
    """
    analysis = values.get("analysis")
    if not isinstance(analysis, dict):
        return
    provider_names = {"llama_cpp", analysis.get("provider")}
    for provider in provider_names:
        if not provider:
            continue
        provider_path = config_dir / f"{provider}.toml"
        if provider_path.exists():
            with provider_path.open("rb") as provider_file:
                analysis[provider] = tomllib.load(provider_file)
