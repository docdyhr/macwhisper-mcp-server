"""Thin wrapper around the MacWhisper `mw` CLI.

Invoked via `subprocess.Popen` with an argv list — never shell=True.
All user-supplied paths are validated against the allow-list before they reach here.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from .config import ALLOWED_EXTENSIONS, Config

log = logging.getLogger(__name__)

# Allowed characters in a model identifier (engine:model-id format).
_MODEL_RE = re.compile(r"[a-zA-Z0-9_:.-]+")

# Hard cap on mw stdout to guard against runaway output.
_MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB


class TranscribeError(Exception):
    """Raised for any user-facing transcription failure."""


def transcribe(
    path_str: str,
    config: Config,
    model: str | None = None,
    persist: bool = False,
    _proc_ref: list[subprocess.Popen] | None = None,
) -> str:
    """Transcribe an audio file and return the transcript as text.

    Args:
        path_str: Path to the audio file (expanded and validated here).
        config: Server configuration (allow-list, CLI path, …).
        model: Optional model override in ``engine:model-id`` format.
        persist: If True, pass ``--persist`` so MacWhisper saves the
            transcription to its history database.
        _proc_ref: If provided, the live Popen object is appended here so
            callers can kill it (cancel support). Cleared on completion.

    Raises:
        TranscribeError: on any validation or CLI failure.
    """
    if "\x00" in path_str:
        raise TranscribeError("Invalid path: contains null byte.")

    # Resolve symlinks *before* any other check to prevent TOCTOU races where a
    # path passes validation then changes before the CLI reads it.
    path = Path(path_str).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        raise TranscribeError(f"File not found: {path}") from None

    if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise TranscribeError(
            f"Unsupported file type '{resolved.suffix}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if not config.is_path_allowed(resolved):
        raise TranscribeError("Access denied: file is outside the configured allow-list.")

    if model is not None and not _MODEL_RE.fullmatch(model):
        raise TranscribeError(
            f"Invalid model identifier '{model}'. "
            "Use engine:model-id format, e.g. 'whisperkit:openai_whisper-large-v3-v20240930'."
        )

    cmd = [config.mw_cli, "transcribe", str(resolved)]
    if model:
        cmd.extend(["--model", model])
    if persist:
        cmd.append("--persist")
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

    if len(stdout) > _MAX_OUTPUT_BYTES:
        raise TranscribeError(
            f"MacWhisper output exceeded size limit ({_MAX_OUTPUT_BYTES // 1_000_000} MB)."
        )

    transcript = stdout.strip()
    if not transcript:
        raise TranscribeError("MacWhisper returned an empty transcript.")

    log.info("Transcribed %s chars", len(transcript))
    return transcript
