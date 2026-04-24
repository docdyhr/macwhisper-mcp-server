"""Thin wrapper around the MacWhisper `mw` CLI.

Invoked via `subprocess.Popen` with an argv list — never shell=True.
All user-supplied paths are validated against the allow-list before they reach here.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .config import ALLOWED_EXTENSIONS, Config

log = logging.getLogger(__name__)


class TranscribeError(Exception):
    """Raised for any user-facing transcription failure."""


def transcribe(
    path_str: str,
    config: Config,
    model: str | None = None,
    _proc_ref: list[subprocess.Popen] | None = None,
) -> str:
    """Transcribe an audio file and return the transcript as text.

    Args:
        path_str: Path to the audio file (expanded and validated here).
        config: Server configuration (allow-list, CLI path, …).
        model: Optional model override in ``engine:model-id`` format.
        _proc_ref: If provided, the live Popen object is appended here so
            callers can kill it (cancel support). Cleared on completion.

    Raises:
        TranscribeError: on any validation or CLI failure.
    """
    path = Path(path_str).expanduser()

    if not path.exists():
        raise TranscribeError(f"File not found: {path}")

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise TranscribeError(
            f"Unsupported file type '{path.suffix}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if not config.is_path_allowed(path):
        raise TranscribeError(
            f"Access denied: {path} is outside the allowed paths. "
            f"Configured allow-list: {[str(p) for p in config.allowed_paths]}"
        )

    resolved = path.resolve(strict=True)
    cmd = [config.mw_cli, "transcribe", str(resolved)]
    if model:
        cmd.extend(["--model", model])
    log.info("Transcribing %s (model=%s)", resolved, model or "default")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as e:
        raise TranscribeError(
            f"MacWhisper CLI '{config.mw_cli}' not found on PATH. "
            "Open MacWhisper → Settings → enable CLI."
        ) from e

    if _proc_ref is not None:
        _proc_ref.append(proc)

    try:
        stdout, stderr = proc.communicate(timeout=60 * 60)  # 1h hard cap
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise TranscribeError("Transcription timed out after 1 hour.") from None
    finally:
        if _proc_ref is not None and proc in _proc_ref:
            _proc_ref.remove(proc)

    if proc.returncode != 0:
        err = (stderr or "").strip() or "(no stderr)"
        raise TranscribeError(f"MacWhisper CLI failed (exit {proc.returncode}): {err}")

    transcript = stdout.strip()
    if not transcript:
        raise TranscribeError("MacWhisper returned an empty transcript.")

    log.info("Transcribed %s chars", len(transcript))
    return transcript
