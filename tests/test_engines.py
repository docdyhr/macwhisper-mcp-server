"""Tests for the whisper-cpp engine. `subprocess.Popen` is mocked throughout.

MacWhisper-path behavior is covered by test_transcribe.py (unchanged after the
extraction into engines.py); this file focuses on the new whisper-cpp backend.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from macwhisper_mcp.engines import TranscribeError
from macwhisper_mcp.transcribe import transcribe


def _mock_popen(mocker, stdout: str = "Hello world.", returncode: int = 0):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (stdout, "")
    mock_proc.returncode = returncode
    mock = mocker.patch(
        "macwhisper_mcp.engines.subprocess.Popen",
        return_value=mock_proc,
    )
    return mock, mock_proc


@pytest.fixture
def wav_file(allowed_dir):
    f = allowed_dir / "memo.wav"
    f.write_bytes(b"not-real-audio")
    return f


@pytest.fixture
def whispercpp_config(config, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    model_file = models / "ggml-base.en.bin"
    model_file.write_bytes(b"fake model")
    return dataclasses.replace(
        config,
        whispercpp_binary="whisper-cli",
        whispercpp_model_dir=models.resolve(),
    )


def test_whispercpp_uses_argv_list_not_shell(mocker, whispercpp_config, wav_file):
    """Critical security property: never invoke the CLI through a shell."""
    mock, _ = _mock_popen(mocker)
    transcribe(
        str(wav_file),
        whispercpp_config,
        model="ggml-base.en.bin",
        engine="whisper-cpp",
    )

    args, kwargs = mock.call_args
    argv = args[0]
    assert isinstance(argv, list), "subprocess must be called with argv list, not a string"
    assert argv[0] == "whisper-cli"
    assert kwargs.get("shell", False) is False


def test_whispercpp_passes_model_and_file_flags(mocker, whispercpp_config, wav_file):
    mock, _ = _mock_popen(mocker)
    transcribe(
        str(wav_file),
        whispercpp_config,
        model="ggml-base.en.bin",
        engine="whisper-cpp",
    )
    argv = mock.call_args[0][0]
    assert "-m" in argv
    assert argv[argv.index("-m") + 1] == str(
        whispercpp_config.whispercpp_model_dir / "ggml-base.en.bin"
    )
    assert "-f" in argv
    assert argv[argv.index("-f") + 1] == str(wav_file.resolve())
    assert "-np" in argv
    assert "-nt" in argv


def test_whispercpp_passes_language_flag(mocker, whispercpp_config, wav_file):
    mock, _ = _mock_popen(mocker)
    transcribe(
        str(wav_file),
        whispercpp_config,
        model="ggml-base.en.bin",
        language="da",
        engine="whisper-cpp",
    )
    argv = mock.call_args[0][0]
    assert "-l" in argv
    assert argv[argv.index("-l") + 1] == "da"


def test_whispercpp_omits_language_flag_by_default(mocker, whispercpp_config, wav_file):
    mock, _ = _mock_popen(mocker)
    transcribe(
        str(wav_file),
        whispercpp_config,
        model="ggml-base.en.bin",
        engine="whisper-cpp",
    )
    assert "-l" not in mock.call_args[0][0]


def test_whispercpp_rejects_persist(whispercpp_config, wav_file):
    with pytest.raises(TranscribeError, match="persist=True is not supported"):
        transcribe(
            str(wav_file),
            whispercpp_config,
            model="ggml-base.en.bin",
            persist=True,
            engine="whisper-cpp",
        )


def test_whispercpp_rejects_unsupported_extension(whispercpp_config, allowed_dir):
    m4a = allowed_dir / "memo.m4a"
    m4a.write_bytes(b"fake")
    with pytest.raises(TranscribeError, match="only supports"):
        transcribe(
            str(m4a),
            whispercpp_config,
            model="ggml-base.en.bin",
            engine="whisper-cpp",
        )


def test_whispercpp_requires_model(whispercpp_config, wav_file):
    with pytest.raises(TranscribeError, match="requires a `model` argument"):
        transcribe(str(wav_file), whispercpp_config, engine="whisper-cpp")


def test_whispercpp_rejects_unknown_model_file(whispercpp_config, wav_file):
    with pytest.raises(TranscribeError, match=r"model 'nope\.bin' not found"):
        transcribe(
            str(wav_file),
            whispercpp_config,
            model="nope.bin",
            engine="whisper-cpp",
        )


def test_whispercpp_reports_missing_binary(mocker, whispercpp_config, wav_file):
    mocker.patch(
        "macwhisper_mcp.engines.subprocess.Popen",
        side_effect=FileNotFoundError("no whisper-cli"),
    )
    with pytest.raises(TranscribeError, match="not found on PATH"):
        transcribe(
            str(wav_file),
            whispercpp_config,
            model="ggml-base.en.bin",
            engine="whisper-cpp",
        )


def test_whispercpp_reports_cli_failure(mocker, whispercpp_config, wav_file):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "failed to initialize whisper context")
    mock_proc.returncode = 3
    mocker.patch("macwhisper_mcp.engines.subprocess.Popen", return_value=mock_proc)
    with pytest.raises(TranscribeError, match="failed to initialize whisper context"):
        transcribe(
            str(wav_file),
            whispercpp_config,
            model="ggml-base.en.bin",
            engine="whisper-cpp",
        )


def test_transcribe_rejects_unknown_engine(config, wav_file):
    with pytest.raises(TranscribeError, match="Unknown engine"):
        transcribe(str(wav_file), config, engine="not-a-real-engine")
