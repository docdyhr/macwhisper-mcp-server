"""Integration tests using the real fixture file in tests/fixtures/.

subprocess.Popen is still mocked — MacWhisper is not installed on CI — but
the audio file on disk is real, so path validation, extension checks, and
allow-list logic all exercise the actual filesystem rather than tmp_path fakes.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macwhisper_mcp.config import Config
from macwhisper_mcp.transcribe import TranscribeError, transcribe

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_WAV = FIXTURES / "sample.wav"


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(
        allowed_paths=(FIXTURES.resolve(),),
        mw_cli="/Applications/MacWhisper.app/Contents/MacOS/mw",
        log_path=tmp_path / "test.log",
    )


def _mock_popen(mocker, stdout: str = "Silence."):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (stdout, "")
    mock_proc.returncode = 0
    return mocker.patch("macwhisper_mcp.transcribe.subprocess.Popen", return_value=mock_proc)


def test_fixture_file_exists():
    assert SAMPLE_WAV.exists(), "sample.wav fixture missing"


def test_transcribe_real_file(cfg: Config, mocker: MagicMock) -> None:
    mock = _mock_popen(mocker)

    result = transcribe(str(SAMPLE_WAV), cfg)

    assert result == "Silence."
    mock.assert_called_once()
    argv = mock.call_args[0][0]
    assert argv[0] == cfg.mw_cli
    assert argv[1] == "transcribe"
    assert Path(argv[2]) == SAMPLE_WAV.resolve()


def test_transcribe_rejects_file_outside_allow_list(
    tmp_path: Path, cfg: Config, mocker: MagicMock
) -> None:
    outside = tmp_path / "secret.wav"
    outside.write_bytes(b"x")
    _mock_popen(mocker)

    with pytest.raises(TranscribeError, match="Access denied"):
        transcribe(str(outside), cfg)


def test_transcribe_rejects_unsupported_extension(cfg: Config, mocker: MagicMock) -> None:
    fake = FIXTURES / "note.txt"
    fake.write_text("hello")
    _mock_popen(mocker)

    try:
        with pytest.raises(TranscribeError, match="Unsupported file type"):
            transcribe(str(fake), cfg)
    finally:
        fake.unlink(missing_ok=True)
