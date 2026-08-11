"""Tests for server.py MCP tool layer."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macwhisper_mcp.config import Config
from macwhisper_mcp.server import build_server


@pytest.fixture
def allowed_dir(tmp_path: Path) -> Path:
    d = tmp_path / "allowed"
    d.mkdir()
    return d


@pytest.fixture
def audio_file(allowed_dir: Path) -> Path:
    f = allowed_dir / "memo.m4a"
    f.write_bytes(b"fake")
    return f


@pytest.fixture
def config(allowed_dir: Path, tmp_path: Path) -> Config:
    return Config(
        allowed_paths=(allowed_dir.resolve(),),
        mw_cli="mw",
        log_path=tmp_path / "test.log",
    )


def _call(mcp, tool: str, args: dict):
    """Run a single tool call synchronously via FastMCP's in-process client.

    Always uses raise_on_error=False so errors come back as is_error=True
    instead of raising ToolError — keeps test assertions uniform.
    """
    from fastmcp import Client

    async def _run():
        async with Client(mcp) as client:
            return await client.call_tool(tool, args, raise_on_error=False)

    return asyncio.run(_run())


def _error_text(result) -> str:
    """Extract error or result text from a CallToolResult."""
    if result.content:
        return result.content[0].text
    return str(result.data)


# ---------------------------------------------------------------------------
# list_allowed_paths
# ---------------------------------------------------------------------------


def test_list_allowed_paths(config, allowed_dir):
    mcp = build_server(config)
    result = _call(mcp, "list_allowed_paths", {})
    assert not result.is_error
    assert str(allowed_dir.resolve()) in result.data


# ---------------------------------------------------------------------------
# transcribe_audio — success
# ---------------------------------------------------------------------------


def test_transcribe_audio_success(mocker, config, audio_file):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Hello world.", "")
    mock_proc.returncode = 0
    mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", return_value=mock_proc)

    mcp = build_server(config)
    result = _call(mcp, "transcribe_audio", {"path": str(audio_file)})

    assert not result.is_error
    assert result.data == "Hello world."


# ---------------------------------------------------------------------------
# transcribe_audio — concurrency: second call rejected while first is running
# ---------------------------------------------------------------------------


def test_transcribe_audio_rejects_concurrent_call(mocker, config, audio_file):
    """While a transcription is in progress the lock is held; a second call must fail."""
    ready = threading.Event()
    proceed = threading.Event()

    def slow_popen(cmd, **kwargs):
        mock_proc = MagicMock()

        def slow_communicate(timeout=None):
            ready.set()
            proceed.wait(timeout=5)
            return ("transcript", "")

        mock_proc.communicate.side_effect = slow_communicate
        mock_proc.returncode = 0
        return mock_proc

    mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", side_effect=slow_popen)

    mcp = build_server(config)

    results = {}

    def first_call():
        results["first"] = _call(mcp, "transcribe_audio", {"path": str(audio_file)})

    t = threading.Thread(target=first_call)
    t.start()
    ready.wait(timeout=5)  # wait until first call has the lock

    # Second call must be rejected immediately
    second = _call(mcp, "transcribe_audio", {"path": str(audio_file)})
    assert second.is_error
    assert "Busy" in _error_text(second)

    proceed.set()
    t.join(timeout=10)
    assert not results["first"].is_error


# ---------------------------------------------------------------------------
# transcribe_audio — lock released after exception
# ---------------------------------------------------------------------------


def test_transcribe_audio_lock_released_after_exception(mocker, config, audio_file):
    call_count = 0

    def failing_then_ok(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_proc = MagicMock()
        if call_count == 1:
            mock_proc.communicate.return_value = ("", "error output")
            mock_proc.returncode = 1
        else:
            mock_proc.communicate.return_value = ("Success.", "")
            mock_proc.returncode = 0
        return mock_proc

    mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", side_effect=failing_then_ok)

    mcp = build_server(config)

    first = _call(mcp, "transcribe_audio", {"path": str(audio_file)})
    assert first.is_error  # CLI failure

    # Lock must be released — second call should succeed
    second = _call(mcp, "transcribe_audio", {"path": str(audio_file)})
    assert not second.is_error
    assert second.data == "Success."


# ---------------------------------------------------------------------------
# cancel_transcription — no active transcription
# ---------------------------------------------------------------------------


def test_cancel_transcription_no_running(config):
    mcp = build_server(config)
    result = _call(mcp, "cancel_transcription", {})
    assert not result.is_error
    assert "No transcription" in result.data


# ---------------------------------------------------------------------------
# cancel_transcription — kills running process
# ---------------------------------------------------------------------------


def test_cancel_transcription_kills_proc(mocker, config, audio_file):
    ready = threading.Event()
    proceed = threading.Event()

    def blocking_popen(cmd, **kwargs):
        mock_proc = MagicMock()

        def blocking_communicate(timeout=None):
            ready.set()
            proceed.wait(timeout=5)
            return ("", "")

        mock_proc.communicate.side_effect = blocking_communicate
        mock_proc.returncode = 0
        return mock_proc

    mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", side_effect=blocking_popen)

    mcp = build_server(config)

    def run_transcribe():
        with contextlib.suppress(Exception):  # process killed mid-transcription
            _call(mcp, "transcribe_audio", {"path": str(audio_file)})

    t = threading.Thread(target=run_transcribe)
    t.start()
    ready.wait(timeout=5)

    result = _call(mcp, "cancel_transcription", {})
    assert not result.is_error
    assert "cancelled" in result.data.lower()

    proceed.set()
    t.join(timeout=10)  # thread may error after kill — that's expected


# ---------------------------------------------------------------------------
# start_watch — access denied for path outside allow-list
# ---------------------------------------------------------------------------


def test_start_watch_rejects_path_outside_allow_list(config, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    mcp = build_server(config)
    result = _call(mcp, "start_watch", {"folder": str(outside)})
    assert result.is_error
    error = _error_text(result)
    assert "Access denied" in error
    assert str(config.allowed_paths[0]) in error


# ---------------------------------------------------------------------------
# start_watch / stop_watch / get_watch_results — basic flow
# ---------------------------------------------------------------------------


def test_start_stop_watch(config, allowed_dir):
    mcp = build_server(config)
    incoming = allowed_dir / "incoming"

    start_result = _call(mcp, "start_watch", {"folder": str(incoming)})
    assert not start_result.is_error
    assert "Watching" in start_result.data

    # Second start while running should say already watching
    second = _call(mcp, "start_watch", {"folder": str(incoming)})
    assert not second.is_error
    assert "Already watching" in second.data

    stop_result = _call(mcp, "stop_watch", {})
    assert not stop_result.is_error
    assert "Stopped" in stop_result.data


def test_stop_watch_no_active_watcher(config):
    mcp = build_server(config)
    result = _call(mcp, "stop_watch", {})
    assert not result.is_error
    assert "No active watcher" in result.data


def test_get_watch_results_no_watcher(config):
    mcp = build_server(config)
    result = _call(mcp, "get_watch_results", {})
    assert not result.is_error
    assert result.data == []


# ---------------------------------------------------------------------------
# transcribe_audio — persist flag
# ---------------------------------------------------------------------------


def test_transcribe_audio_persist_flag(mocker, config, audio_file):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Transcript.", "")
    mock_proc.returncode = 0
    mock = mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", return_value=mock_proc)

    mcp = build_server(config)
    result = _call(mcp, "transcribe_audio", {"path": str(audio_file), "persist": True})

    assert not result.is_error
    assert "--persist" in mock.call_args[0][0]


# ---------------------------------------------------------------------------
# transcribe_audio — language flag
# ---------------------------------------------------------------------------


def test_transcribe_audio_language_flag(mocker, config, audio_file):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Transcript.", "")
    mock_proc.returncode = 0
    mock = mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", return_value=mock_proc)

    mcp = build_server(config)
    result = _call(mcp, "transcribe_audio", {"path": str(audio_file), "language": "da"})

    assert not result.is_error
    argv = mock.call_args[0][0]
    assert "--language" in argv
    assert argv[argv.index("--language") + 1] == "da"


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------

_MODELS_OUTPUT = (
    "ID                                            NAME                 SIZE  \n"
    "▸ whisperkit:openai_whisper-large-v3-v20240930  Large v3 Turbo       -     \n"
    "  parakeet-pro:nvidia_parakeet-v3_494MB         Parakeet v3 (494MB)  494 MB\n"
)


def test_list_models_returns_parsed_list(mocker, config):
    mock_result = MagicMock()
    mock_result.stdout = _MODELS_OUTPUT
    mocker.patch("macwhisper_mcp.server.subprocess.run", return_value=mock_result)

    mcp = build_server(config)
    result = _call(mcp, "list_models", {})

    assert not result.is_error
    models = result.data
    assert len(models) == 2
    assert "whisperkit:openai_whisper-large-v3-v20240930" in models[0]
    assert "[active]" in models[0]
    assert "parakeet-pro:nvidia_parakeet-v3_494MB" in models[1]
    assert "[active]" not in models[1]


def test_list_models_cli_not_found(mocker, config):
    mocker.patch(
        "macwhisper_mcp.server.subprocess.run",
        side_effect=FileNotFoundError("no mw"),
    )
    mcp = build_server(config)
    result = _call(mcp, "list_models", {})
    assert result.is_error
    assert "not found" in _error_text(result)


def test_list_models_includes_whispercpp_models(mocker, config, tmp_path):
    mock_result = MagicMock()
    mock_result.stdout = _MODELS_OUTPUT
    mocker.patch("macwhisper_mcp.server.subprocess.run", return_value=mock_result)

    models_dir = tmp_path / "whispercpp-models"
    models_dir.mkdir()
    (models_dir / "ggml-base.en.bin").write_bytes(b"fake")
    (models_dir / "notes.txt").write_bytes(b"ignore me")

    cfg = dataclasses.replace(config, whispercpp_model_dir=models_dir.resolve())
    mcp = build_server(cfg)
    result = _call(mcp, "list_models", {})

    assert not result.is_error
    assert "ggml-base.en.bin [whisper-cpp]" in result.data
    assert not any("notes.txt" in m for m in result.data)


# ---------------------------------------------------------------------------
# transcribe_audio — whisper-cpp engine
# ---------------------------------------------------------------------------


def test_transcribe_audio_whispercpp_engine(mocker, config, tmp_path, allowed_dir):
    models_dir = tmp_path / "whispercpp-models"
    models_dir.mkdir()
    (models_dir / "ggml-base.en.bin").write_bytes(b"fake")
    wav = allowed_dir / "memo.wav"
    wav.write_bytes(b"fake audio")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Transcript.", "")
    mock_proc.returncode = 0
    mock = mocker.patch("macwhisper_mcp.engines.subprocess.Popen", return_value=mock_proc)

    cfg = dataclasses.replace(config, whispercpp_model_dir=models_dir.resolve())
    mcp = build_server(cfg)
    result = _call(
        mcp,
        "transcribe_audio",
        {"path": str(wav), "model": "ggml-base.en.bin", "engine": "whisper-cpp"},
    )

    assert not result.is_error
    assert result.data == "Transcript."
    assert mock.call_args[0][0][0] == "whisper-cli"


def test_transcribe_audio_unknown_engine_rejected(config, audio_file):
    mcp = build_server(config)
    result = _call(mcp, "transcribe_audio", {"path": str(audio_file), "engine": "bogus"})
    assert result.is_error
    assert "Unknown engine" in _error_text(result)


# ---------------------------------------------------------------------------
# cancel_transcription — regression: no IndexError when proc list is cleared mid-read
# ---------------------------------------------------------------------------


def test_cancel_handles_proc_cleared_mid_read(tmp_path):
    """Regression for the check-then-index race.

    The old ``if not _current_proc: ... _current_proc[0]`` form raised
    ``IndexError`` (surfaced to the client as an error) when the running
    transcription's finally block cleared ``_current_proc`` in the gap between
    the truthiness check and the subscript. We simulate that by injecting a
    list that empties itself on ``__getitem__`` — exactly the state the race
    produces — and assert cancel degrades gracefully instead of erroring.
    """

    class _RacyList(list):
        def __getitem__(self, index):
            # Emulate the finishing transcription clearing the list between
            # cancel's truthiness check and its index access.
            self.clear()
            return super().__getitem__(index)

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg = Config(
        allowed_paths=(allowed.resolve(),),
        mw_cli="mw",
        log_path=tmp_path / "test.log",
    )
    proc_state = _RacyList([MagicMock()])  # non-empty so the check would pass
    mcp = build_server(cfg, _proc_state=proc_state)

    result = _call(mcp, "cancel_transcription", {})
    assert not result.is_error
    assert "No transcription" in result.data


# ---------------------------------------------------------------------------
# start_watch — done directory must be inside the allow-list
# ---------------------------------------------------------------------------


def test_start_watch_rejects_done_dir_outside_allow_list(tmp_path):
    """When the allow-list is exactly the incoming folder, the default done dir
    (incoming.parent/done) falls outside it and must be rejected rather than
    silently written to."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    cfg = Config(
        allowed_paths=(incoming.resolve(),),
        mw_cli="mw",
        log_path=tmp_path / "test.log",
    )
    mcp = build_server(cfg)
    result = _call(mcp, "start_watch", {"folder": str(incoming)})
    assert result.is_error
    assert "done directory" in _error_text(result)


def test_start_watch_accepts_configured_done_dir_inside_allow_list(tmp_path):
    """MACWHISPER_WATCH_DONE_DIR (via Config.watch_done_dir) overrides the
    default and is accepted when inside the allow-list."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    done = tmp_path / "done"  # both under tmp_path, which we allow-list
    cfg = Config(
        allowed_paths=(tmp_path.resolve(),),
        mw_cli="mw",
        log_path=tmp_path / "test.log",
        watch_done_dir=done.resolve(),
    )
    mcp = build_server(cfg)
    try:
        result = _call(mcp, "start_watch", {"folder": str(incoming)})
        assert not result.is_error
        assert "Watching" in result.data
    finally:
        _call(mcp, "stop_watch", {})
