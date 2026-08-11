"""Transcription engine backends: MacWhisper (default) and whisper-cpp (opt-in).

Each engine builds an argv list — never shell=True — for an already-validated,
allow-listed audio path and returns the transcript as plain text. The two engines
share `_run_and_capture` for process execution so timeout, exit-code, and output-size
handling can never drift apart between them.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .config import MAX_OUTPUT_BYTES, WHISPERCPP_EXTENSIONS, Config

log = logging.getLogger(__name__)


class TranscribeError(Exception):
    """Raised for any user-facing transcription failure."""


def _run_and_capture(
    cmd: list[str],
    engine_label: str,
    not_found_hint: str,
    _proc_ref: list[subprocess.Popen] | None,
) -> str:
    """Run `cmd` via Popen (argv list, never shell), capture stdout as the transcript.

    Shared by both engines: 1h timeout, non-zero-exit and output-size checks, and
    the `_proc_ref` cancel-support seam all behave identically regardless of engine.
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as e:
        raise TranscribeError(
            f"{engine_label} CLI '{cmd[0]}' not found on PATH. {not_found_hint}"
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
        raise TranscribeError(f"{engine_label} CLI failed (exit {proc.returncode}): {err}")

    if len(stdout) > MAX_OUTPUT_BYTES:
        raise TranscribeError(
            f"{engine_label} output exceeded size limit ({MAX_OUTPUT_BYTES // 1_000_000} MB)."
        )

    transcript = stdout.strip()
    if not transcript:
        raise TranscribeError(f"{engine_label} returned an empty transcript.")

    log.info("Transcribed %s chars via %s", len(transcript), engine_label)
    return transcript


def run_macwhisper(
    resolved: Path,
    config: Config,
    model: str | None,
    language: str | None,
    persist: bool,
    _proc_ref: list[subprocess.Popen] | None,
) -> str:
    """Transcribe via the MacWhisper `mw` CLI — the default, original engine."""
    cmd = [config.mw_cli, "transcribe", str(resolved)]
    if model:
        cmd.extend(["--model", model])
    if language is not None:
        cmd.extend(["--language", language])
    if persist:
        cmd.append("--persist")
    log.info(
        "Transcribing %s (engine=macwhisper, model=%s, language=%s)",
        resolved,
        model or "default",
        language or "default",
    )
    return _run_and_capture(
        cmd,
        "MacWhisper",
        "Open MacWhisper → Settings → enable CLI.",
        _proc_ref,
    )


def run_whispercpp(
    resolved: Path,
    config: Config,
    model: str | None,
    language: str | None,
    persist: bool,
    _proc_ref: list[subprocess.Popen] | None,
) -> str:
    """Transcribe via a standalone whisper-cpp binary — independent of MacWhisper.

    v1 limitations, both explicit follow-ons rather than bugs:
    - Input must be .wav/.mp3/.flac (whisper-cli's native formats, intersected with
      this server's ALLOWED_EXTENSIONS). No ffmpeg transcoding for m4a/mp4/mov/aiff.
    - No --persist equivalent: whisper.cpp has no history mechanism.
    """
    if persist:
        raise TranscribeError(
            "persist=True is not supported by the whisper-cpp engine (it has no history mechanism)."
        )
    if resolved.suffix.lower() not in WHISPERCPP_EXTENSIONS:
        raise TranscribeError(
            f"whisper-cpp engine only supports "
            f"{', '.join(sorted(WHISPERCPP_EXTENSIONS))} input (got '{resolved.suffix}'). "
            "Convert the file first, or use the default 'macwhisper' engine."
        )
    if not model:
        raise TranscribeError(
            "whisper-cpp engine requires a `model` argument: the filename of a GGML "
            ".bin model inside MACWHISPER_WHISPERCPP_MODEL_DIR (not a MacWhisper "
            "engine:model-id string)."
        )
    model_path = config.resolve_whispercpp_model(model)
    if model_path is None:
        raise TranscribeError(
            f"whisper-cpp model '{model}' not found. Set MACWHISPER_WHISPERCPP_MODEL_DIR "
            "to the directory containing your .bin GGML model files (download one from "
            "https://huggingface.co/ggerganov/whisper.cpp), and check the filename."
        )

    # -np: suppress non-result prints. -nt: plain text without [00:00:00.000 --> ...]
    # segment prefixes — verified live against whisper-cli 1.9.2; without -nt every
    # line is timestamp-prefixed, which would break the plain-transcript contract.
    cmd = [config.whispercpp_binary, "-m", str(model_path), "-f", str(resolved), "-np", "-nt"]
    if language is not None:
        cmd.extend(["-l", language])
    log.info(
        "Transcribing %s (engine=whisper-cpp, model=%s, language=%s)",
        resolved,
        model,
        language or "default (en)",
    )
    return _run_and_capture(
        cmd,
        "whisper-cpp",
        "Install it with `brew install whisper-cpp`.",
        _proc_ref,
    )


ENGINES = {
    "macwhisper": run_macwhisper,
    "whisper-cpp": run_whispercpp,
}
