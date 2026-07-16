"""Version derivation tests.

``__version__`` is read from the installed distribution metadata (set from
pyproject.toml at install time) rather than maintained as a literal, so it
cannot silently drift from the package version.
"""

from __future__ import annotations

from importlib.metadata import version as installed_version


def test_version_is_populated():
    from macwhisper_mcp import __version__

    assert __version__
    assert __version__ != "0.0.0.dev0", "metadata not found — package not installed?"


def test_version_matches_installed_metadata():
    from macwhisper_mcp import __version__

    assert __version__ == installed_version("macwhisper-mcp-server")
