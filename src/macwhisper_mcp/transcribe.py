"""Thin wrapper around the MacWhisper `mw` CLI.

Invoked via `subprocess.run` with an argv list — never shell=True.
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


def transcribe(path_str: str, config: Config, model: str | None = None) -> str:
    """Transcribe an audio file and return the transcript as text.

    Raises:
        TranscribeError: on any validation or CLI failure. The message is safe to
            surface to the MCP client.
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
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60 * 60,  # 1h hard cap
        )
    except FileNotFoundError as e:
        raise TranscribeError(
            f"MacWhisper CLI '{config.mw_cli}' not found on PATH. "
            "Open MacWhisper → Settings → enable CLI."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise TranscribeError("Transcription timed out after 1 hour.") from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip() or "(no stderr)"
        raise TranscribeError(f"MacWhisper CLI failed (exit {e.returncode}): {stderr}") from e

    transcript = result.stdout.strip()
    if not transcript:
        raise TranscribeError("MacWhisper returned an empty transcript.")

    log.info("Transcribed %s chars", len(transcript))
    return transcript
