"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from macwhisper_mcp.config import Config


@pytest.fixture
def allowed_dir(tmp_path: Path) -> Path:
    """A tmp directory that acts as an allow-listed root."""
    d = tmp_path / "allowed"
    d.mkdir()
    return d


@pytest.fixture
def audio_file(allowed_dir: Path) -> Path:
    """A fake .m4a file inside the allow-list. Real bytes not needed — mw is mocked."""
    f = allowed_dir / "memo.m4a"
    f.write_bytes(b"not-real-audio")
    return f


@pytest.fixture
def config(allowed_dir: Path, tmp_path: Path) -> Config:
    return Config(
        allowed_paths=(allowed_dir.resolve(),),
        mw_cli="mw",
        log_path=tmp_path / "macwhisper-mcp.log",
    )
