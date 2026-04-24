"""Tests for FolderWatcher."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macwhisper_mcp.config import Config
from macwhisper_mcp.watcher import FolderWatcher


@pytest.fixture
def incoming(tmp_path: Path) -> Path:
    d = tmp_path / "incoming"
    d.mkdir()
    return d


@pytest.fixture
def watch_config(tmp_path: Path, incoming: Path) -> Config:
    return Config(
        allowed_paths=(incoming.resolve(),),
        mw_cli="mw",
        log_path=tmp_path / "test.log",
    )


def _mock_watcher_popen(mocker, stdout: str = "Test transcript."):
    mock_proc = MagicMock()
    mock_proc.stdout = stdout
    mock_proc.returncode = 0
    return mocker.patch(
        "macwhisper_mcp.watcher.subprocess.run",
        return_value=mock_proc,
    )


def test_watcher_transcribes_and_moves_file(mocker, incoming, watch_config):
    _mock_watcher_popen(mocker, stdout="Hello world.")

    audio = incoming / "clip.m4a"
    audio.write_bytes(b"fake audio")

    watcher = FolderWatcher(incoming, watch_config, poll_interval=0.1)
    watcher.start()
    time.sleep(0.5)
    watcher.stop()

    results = watcher.drain_results()
    assert len(results) == 1
    assert results[0]["file"] == "clip.m4a"
    assert results[0]["transcript"] == "Hello world."
    assert results[0]["error"] is None
    assert not audio.exists(), "Original file should be moved to done/"
    assert (watcher.done_dir / "clip.m4a").exists()


def test_watcher_skips_non_audio_files(mocker, incoming, watch_config):
    mock = _mock_watcher_popen(mocker)

    (incoming / "readme.txt").write_text("ignore me")

    watcher = FolderWatcher(incoming, watch_config, poll_interval=0.1)
    watcher.start()
    time.sleep(0.3)
    watcher.stop()

    mock.assert_not_called()
    assert watcher.drain_results() == []


def test_watcher_records_error_and_restores_file(mocker, incoming, watch_config):
    mocker.patch(
        "macwhisper_mcp.watcher.subprocess.run",
        side_effect=Exception("CLI exploded"),
    )

    audio = incoming / "bad.wav"
    audio.write_bytes(b"fake")

    watcher = FolderWatcher(incoming, watch_config, poll_interval=0.1)
    watcher.start()
    time.sleep(0.5)
    watcher.stop()

    results = watcher.drain_results()
    assert len(results) == 1
    assert results[0]["error"] == "CLI exploded"
    assert results[0]["transcript"] is None
    assert audio.exists(), "File should be restored to incoming/ on failure"


def test_watcher_drain_clears_queue(mocker, incoming, watch_config):
    _mock_watcher_popen(mocker)
    (incoming / "a.m4a").write_bytes(b"x")

    watcher = FolderWatcher(incoming, watch_config, poll_interval=0.1)
    watcher.start()
    time.sleep(0.4)
    watcher.stop()

    first = watcher.drain_results()
    second = watcher.drain_results()
    assert len(first) == 1
    assert second == []


def test_watcher_is_running_reflects_state(incoming, watch_config):
    watcher = FolderWatcher(incoming, watch_config, poll_interval=0.1)
    assert not watcher.is_running
    watcher.start()
    assert watcher.is_running
    watcher.stop()
    assert not watcher.is_running
