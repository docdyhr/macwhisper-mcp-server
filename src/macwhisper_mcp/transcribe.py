"""Validates a transcription request and dispatches it to the configured engine.

All user-supplied paths and identifiers are validated against the allow-list here,
before either engine (see engines.py) ever sees them. Argv-list only — never shell=True.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from .config import ALLOWED_EXTENSIONS, LANGUAGE_RE, Config
from .engines import ENGINES, TranscribeError

log = logging.getLogger(__name__)

# Allowed characters in a model identifier: MacWhisper's engine:model-id format,
# or a flat whisper-cpp GGML filename (no subdirectories — no '/').
_MODEL_RE = re.compile(r"[a-zA-Z0-9_:.-]+")


def transcribe(
    path_str: str,
    config: Config,
    model: str | None = None,
    language: str | None = None,
    persist: bool = False,
    engine: str = "macwhisper",
    _proc_ref: list[subprocess.Popen] | None = None,
) -> str:
    """Transcribe an audio file and return the transcript as text.

    Args:
        path_str: Path to the audio file (expanded and validated here).
        config: Server configuration (allow-list, CLI path, …).
        model: Optional model override. For ``engine="macwhisper"``, an
            ``engine:model-id`` string. For ``engine="whisper-cpp"``, the filename
            of a GGML model inside ``MACWHISPER_WHISPERCPP_MODEL_DIR`` (required
            for that engine).
        language: Optional ISO 639-1 language code (or ``"auto"``) to pass through.
            Takes precedence over any directory-based default configured via
            ``MACWHISPER_LANGUAGE_DEFAULTS``. When neither is set, the engine's own
            default applies (MacWhisper: app selection; whisper-cpp: English).
        persist: If True, pass ``--persist`` so MacWhisper saves the transcription
            to its history database. Not supported by the whisper-cpp engine.
        engine: ``"macwhisper"`` (default) or ``"whisper-cpp"`` — an independent
            backend that does not invoke MacWhisper at all.
        _proc_ref: If provided, the live Popen object is appended here so
            callers can kill it (cancel support). Cleared on completion.

    Raises:
        TranscribeError: on any validation or CLI failure.
    """
    if engine not in ENGINES:
        raise TranscribeError(
            f"Unknown engine '{engine}'. Use one of: {', '.join(sorted(ENGINES))}."
        )

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
        allowed = ", ".join(str(p) for p in config.allowed_paths)
        raise TranscribeError(
            f"Access denied: '{resolved}' is outside the configured allow-list "
            f"({allowed}). If this file was uploaded to Claude, save it to one of "
            "the listed folders first. Otherwise, add its directory to "
            "MACWHISPER_ALLOWED_PATHS in claude_desktop_config.json and restart "
            "Claude Desktop."
        )

    if model is not None and not _MODEL_RE.fullmatch(model):
        raise TranscribeError(
            f"Invalid model identifier '{model}'. Use engine:model-id format "
            "(MacWhisper) or a flat filename (whisper-cpp), e.g. "
            "'whisperkit:openai_whisper-large-v3-v20240930' or 'ggml-base.en.bin'."
        )

    # Explicit override wins; otherwise fall back to a directory-based default.
    resolved_language = language if language is not None else config.language_for(resolved.parent)
    if resolved_language is not None and not LANGUAGE_RE.fullmatch(resolved_language.lower()):
        raise TranscribeError(
            f"Invalid language code '{resolved_language}'. "
            "Use an ISO 639-1 code (e.g. 'da', 'de') or 'auto'."
        )
    if resolved_language is not None:
        resolved_language = resolved_language.lower()

    return ENGINES[engine](resolved, config, model, resolved_language, persist, _proc_ref)
