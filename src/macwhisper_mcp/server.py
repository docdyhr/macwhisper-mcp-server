"""FastMCP server entry point.

Run via `python -m macwhisper_mcp.server` or the `macwhisper-mcp` console script.
Communicates over stdio — do NOT print to stdout anywhere. All logs go to a file.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
from pathlib import Path

from fastmcp import FastMCP

from .config import Config
from .transcribe import TranscribeError, transcribe
from .watcher import FolderWatcher


def _setup_logging(config: Config) -> None:
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(config.log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_server(config: Config | None = None, _proc_state: list | None = None) -> FastMCP:
    config = config or Config.from_env()
    _setup_logging(config)
    log = logging.getLogger(__name__)
    log.info("Starting macwhisper-mcp-server, allow-list=%s", config.allowed_paths)

    mcp = FastMCP("macwhisper")

    # --- concurrency + cancel state ---
    _transcribe_lock = threading.Lock()
    # The live Popen (at most one element) so cancel_transcription can kill it.
    # ``_proc_state`` is only a test seam for injecting a racy list; production
    # always passes None and gets a fresh plain list.
    _current_proc: list[subprocess.Popen] = _proc_state if _proc_state is not None else []

    # --- watch-folder state ---
    _watcher: list[FolderWatcher] = []  # at most one element

    @mcp.tool()
    def transcribe_audio(
        path: str,
        model: str | None = None,
        language: str | None = None,
        persist: bool = False,
        engine: str = "macwhisper",
    ) -> str:
        """Transcribe a local audio file and return the transcript.

        IMPORTANT: ``path`` must be a file on the user's Mac filesystem inside the
        configured allow-list (typically ~/Desktop or ~/Downloads). Files uploaded
        to the Claude chat window are NOT accessible — ask the user to save the file
        to their Desktop or Downloads folder first.

        If this tool returns an access-denied error, do NOT attempt to transcribe the
        file by any other means (e.g. downloading a model, calling an external API, or
        using in-process speech recognition). Simply tell the user to save the file
        locally and retry with this tool.

        Args:
            path: Absolute or ``~``-prefixed path to an audio file on the local Mac
                filesystem inside the configured allow-list.
                Supported formats: m4a, mp3, mp4, mov, wav, aiff, flac (whisper-cpp
                engine only: wav, mp3, flac).
            model: Optional model override. For the default ``engine="macwhisper"``,
                an engine:model-id string, e.g.
                "whisperkit:openai_whisper-large-v3-v20240930" — use ``list_models()``
                to see what is installed. For ``engine="whisper-cpp"``, this is
                REQUIRED and must be the filename of a GGML model inside
                ``MACWHISPER_WHISPERCPP_MODEL_DIR`` (not an engine:model-id string).
            language: Optional ISO 639-1 code (e.g. "da", "de") or "auto" to force
                the transcription language. If omitted, a per-directory default is
                used when the file's folder matches one configured in
                MACWHISPER_LANGUAGE_DEFAULTS; otherwise the engine's own default
                applies (MacWhisper: app selection; whisper-cpp: English).
            persist: If True, save the transcription to MacWhisper's history.
                Defaults to False. Not supported by the whisper-cpp engine.
            engine: "macwhisper" (default) — routes through the MacWhisper CLI, or
                "whisper-cpp" — an independent local backend that does not use
                MacWhisper at all. Requires whisper-cpp installed
                (`brew install whisper-cpp`) and MACWHISPER_WHISPERCPP_MODEL_DIR set.

        Returns:
            The full transcript as plain text.
        """
        if not _transcribe_lock.acquire(blocking=False):
            raise TranscribeError(
                "Busy: another transcription is already running. Try again shortly."
            )
        _current_proc.clear()
        try:
            return transcribe(
                path,
                config,
                model=model,
                language=language,
                persist=persist,
                engine=engine,
                _proc_ref=_current_proc,
            )
        except TranscribeError:
            log.warning("transcribe_audio failed: %s", path)
            raise
        finally:
            _current_proc.clear()
            _transcribe_lock.release()

    @mcp.tool()
    def cancel_transcription() -> str:
        """Cancel the currently running transcription, if any."""
        # Single atomic subscript (no check-then-index): ``list.__getitem__``
        # is one CPython opcode, so the list cannot be cleared by the finishing
        # transcription between a truthiness check and the index. The previous
        # ``if not _current_proc: ... _current_proc[0]`` form could IndexError
        # when the running transcription's finally block cleared the list in the
        # gap between those two opcodes.
        try:
            proc = _current_proc[0]
        except IndexError:
            return "No transcription is currently running."
        proc.kill()
        log.info("Transcription cancelled by user")
        return "Transcription cancelled."

    @mcp.tool()
    def list_models() -> list[str]:
        """Return the transcription models available across all engines.

        MacWhisper entries are formatted as ``engine:model-id — Display Name [active]``
        where ``[active]`` marks the model currently selected in MacWhisper; pass the
        ``engine:model-id`` string as ``model`` with the default ``engine="macwhisper"``.
        whisper-cpp entries (if ``MACWHISPER_WHISPERCPP_MODEL_DIR`` is configured) are
        formatted as ``filename [whisper-cpp]``; pass the filename as ``model`` with
        ``engine="whisper-cpp"``. Requires the MacWhisper CLI to be reachable even if
        you only intend to use the whisper-cpp engine.
        """
        try:
            result = subprocess.run(
                [config.mw_cli, "models", "list"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except FileNotFoundError as e:
            raise TranscribeError(
                f"MacWhisper CLI '{config.mw_cli}' not found. "
                "Open MacWhisper → Settings → Advanced → install CLI."
            ) from e
        except subprocess.CalledProcessError as e:
            raise TranscribeError(
                f"MacWhisper CLI failed: {(e.stderr or '').strip() or '(no stderr)'}"
            ) from e

        # Tabular output: first line is header; subsequent lines start with
        # "▸ " (active model) or "  " (inactive).
        models: list[str] = []
        for line in result.stdout.splitlines()[1:]:
            if not line.strip():
                continue
            active = line.startswith("▸")
            parts = re.split(r"\s{2,}", line[1:].strip())
            if not parts or not parts[0]:
                continue
            model_id = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            entry = f"{model_id} — {name}" if name else model_id
            if active:
                entry += " [active]"
            models.append(entry)

        if config.whispercpp_model_dir is not None and config.whispercpp_model_dir.is_dir():
            for f in sorted(config.whispercpp_model_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in (".bin", ".gguf"):
                    models.append(f"{f.name} [whisper-cpp]")

        return models

    @mcp.tool()
    def list_allowed_paths() -> list[str]:
        """Return the directories this server is allowed to read audio from."""
        return [str(p) for p in config.allowed_paths]

    @mcp.tool()
    def start_watch(folder: str) -> str:
        """Start watching a folder for new audio files to auto-transcribe.

        New audio files dropped into ``folder`` are transcribed automatically
        and moved to a "done" directory. By default this is ``<folder>/../done``;
        override it with the ``MACWHISPER_WATCH_DONE_DIR`` env var. Both the
        incoming folder and the done directory must be inside the configured
        allow-list, otherwise the call is rejected. Call ``get_watch_results()``
        to retrieve completed transcriptions.

        Args:
            folder: Absolute or ``~``-prefixed path to the incoming directory.
        """
        if _watcher and _watcher[0].is_running:
            return f"Already watching {_watcher[0].incoming}. Call stop_watch() first."
        incoming = Path(folder).expanduser().resolve()
        if not any(incoming == base or base in incoming.parents for base in config.allowed_paths):
            allowed = ", ".join(str(p) for p in config.allowed_paths)
            raise TranscribeError(
                f"Access denied: '{incoming}' is outside the configured allow-list "
                f"({allowed}). Add the folder to MACWHISPER_ALLOWED_PATHS in "
                "~/Library/Application Support/Claude/claude_desktop_config.json "
                "and restart Claude Desktop."
            )
        # The done dir must also be inside the allow-list so the watcher never
        # silently writes outside what the user permitted. Default is a sibling
        # of the incoming folder; MACWHISPER_WATCH_DONE_DIR overrides it.
        done_dir = (
            config.watch_done_dir if config.watch_done_dir is not None else incoming.parent / "done"
        )
        if not config.is_path_allowed(done_dir, strict=False):
            allowed = ", ".join(str(p) for p in config.allowed_paths)
            raise TranscribeError(
                f"Access denied: done directory '{done_dir}' is outside the configured "
                f"allow-list ({allowed}). Set MACWHISPER_WATCH_DONE_DIR to a folder inside "
                "the allow-list (or widen MACWHISPER_ALLOWED_PATHS) and restart Claude Desktop."
            )
        w = FolderWatcher(incoming, config, done_dir=done_dir)
        w.start()
        if _watcher:
            _watcher[0] = w
        else:
            _watcher.append(w)
        return f"Watching {w.incoming} — completed files moved to {w.done_dir}"

    @mcp.tool()
    def stop_watch() -> str:
        """Stop the active folder watcher."""
        if not _watcher or not _watcher[0].is_running:
            return "No active watcher."
        w = _watcher[0]
        w.stop()
        return f"Stopped watching {w.incoming}"

    @mcp.tool()
    def get_watch_results() -> list[dict]:
        """Return completed watch-folder transcriptions and clear the queue.

        Each entry contains: ``file``, ``transcript``, ``destination``, ``error``.
        """
        if not _watcher:
            return []
        return _watcher[0].drain_results()

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
