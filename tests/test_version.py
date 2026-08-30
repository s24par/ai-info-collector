"""Package version tests."""

from importlib.metadata import version

from ai_info_collector import __version__


def test_version_matches_package_metadata() -> None:
    """Expose the version defined in package metadata."""
    assert __version__ == version("ai-info-collector")
