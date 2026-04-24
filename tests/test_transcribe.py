"""Tests for the `transcribe` wrapper. `subprocess.Popen` is mocked throughout."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from macwhisper_mcp.transcribe import TranscribeError, transcribe


def _mock_popen(mocker, stdout: str = "hello world", returncode: int = 0):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (stdout, "")
    mock_proc.returncode = returncode
    mock = mocker.patch(
        "macwhisper_mcp.transcribe.subprocess.Popen",
        return_value=mock_proc,
    )
    return mock, mock_proc


def test_transcribe_returns_stdout(mocker, config, audio_file):
    _mock_popen(mocker, stdout="  transcript text  \n")
    assert transcribe(str(audio_file), config) == "transcript text"


def test_transcribe_uses_argv_list_not_shell(mocker, config, audio_file):
    """Critical security property: never invoke the CLI through a shell."""
    mock, _ = _mock_popen(mocker)
    transcribe(str(audio_file), config)

    args, kwargs = mock.call_args
    argv = args[0]
    assert isinstance(argv, list), "subprocess must be called with argv list, not a string"
    assert argv[0] == "mw"
    assert argv[1] == "transcribe"
    assert kwargs.get("shell", False) is False


def test_transcribe_rejects_missing_file(config, tmp_path):
    with pytest.raises(TranscribeError, match="File not found"):
        transcribe(str(tmp_path / "ghost.m4a"), config)


def test_transcribe_rejects_unsupported_extension(config, allowed_dir):
    bad = allowed_dir / "notes.txt"
    bad.write_text("hi")
    with pytest.raises(TranscribeError, match="Unsupported file type"):
        transcribe(str(bad), config)


def test_transcribe_rejects_path_outside_allow_list(config, tmp_path):
    outside = tmp_path / "outside.m4a"
    outside.write_bytes(b"x")
    with pytest.raises(TranscribeError, match="Access denied"):
        transcribe(str(outside), config)


def test_transcribe_reports_missing_cli(mocker, config, audio_file):
    mocker.patch(
        "macwhisper_mcp.transcribe.subprocess.Popen",
        side_effect=FileNotFoundError("no mw"),
    )
    with pytest.raises(TranscribeError, match="not found on PATH"):
        transcribe(str(audio_file), config)


def test_transcribe_reports_cli_failure(mocker, config, audio_file):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "bad audio format")
    mock_proc.returncode = 2
    mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", return_value=mock_proc)
    with pytest.raises(TranscribeError, match="bad audio format"):
        transcribe(str(audio_file), config)


def test_transcribe_reports_timeout(mocker, config, audio_file):
    mock_proc = MagicMock()
    # First communicate() raises TimeoutExpired; second (cleanup after kill) returns normally.
    mock_proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["mw"], timeout=1),
        ("", ""),
    ]
    mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", return_value=mock_proc)
    with pytest.raises(TranscribeError, match="timed out"):
        transcribe(str(audio_file), config)


def test_transcribe_rejects_empty_transcript(mocker, config, audio_file):
    _mock_popen(mocker, stdout="   \n  ")
    with pytest.raises(TranscribeError, match="empty transcript"):
        transcribe(str(audio_file), config)


def test_transcribe_passes_model_flag(mocker, config, audio_file):
    mock, _ = _mock_popen(mocker)
    transcribe(str(audio_file), config, model="whisperkit:openai_whisper-large-v3-v20240930")

    argv = mock.call_args[0][0]
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "whisperkit:openai_whisper-large-v3-v20240930"


def test_transcribe_omits_model_flag_when_none(mocker, config, audio_file):
    mock, _ = _mock_popen(mocker)
    transcribe(str(audio_file), config, model=None)

    argv = mock.call_args[0][0]
    assert "--model" not in argv


def test_transcribe_exposes_proc_ref(mocker, config, audio_file):
    _mock, mock_proc = _mock_popen(mocker)
    proc_ref: list = []
    transcribe(str(audio_file), config, _proc_ref=proc_ref)
    # proc_ref is cleared after completion
    assert proc_ref == []
    mock_proc.communicate.assert_called_once()
