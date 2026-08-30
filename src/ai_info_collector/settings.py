import tomllib
from pathlib import Path

from pydantic import ValidationError

from .domain import AppConfig


def load_config(path: Path) -> AppConfig:
    """Load and validate an application TOML configuration."""
    with path.open("rb") as config_file:
        values = tomllib.load(config_file)
    try:
        return AppConfig.model_validate(values)
    except ValidationError as error:
        raise ValueError(f"Invalid configuration: {error}") from error
