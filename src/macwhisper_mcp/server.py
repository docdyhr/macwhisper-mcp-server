"""FastMCP server entry point.

Run via `python -m macwhisper_mcp.server` or the `macwhisper-mcp` console script.
Communicates over stdio — do NOT print to stdout anywhere. All logs go to a file.
"""

from __future__ import annotations

import logging
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


def build_server(config: Config | None = None) -> FastMCP:
    config = config or Config.from_env()
    _setup_logging(config)
    log = logging.getLogger(__name__)
    log.info("Starting macwhisper-mcp-server, allow-list=%s", config.allowed_paths)

    mcp = FastMCP("macwhisper")

    # --- concurrency + cancel state ---
    _transcribe_lock = threading.Lock()
    _current_proc: list[subprocess.Popen] = []  # at most one element

    # --- watch-folder state ---
    _watcher: list[FolderWatcher] = []  # at most one element

    @mcp.tool()
    def transcribe_audio(path: str, model: str | None = None) -> str:
        """Transcribe a local audio file using MacWhisper and return the transcript.

        Args:
            path: Absolute path to an audio file inside the configured allow-list.
                Supported formats: m4a, mp3, mp4, mov, wav, aiff, flac.
            model: Optional model override in MacWhisper engine:model-id format,
                e.g. "whisperkit:openai_whisper-large-v3-v20240930" or
                "parakeet-pro:nvidia_parakeet-v3_494MB". Defaults to the model
                currently selected in MacWhisper.

        Returns:
            The full transcript as plain text.
        """
        if not _transcribe_lock.acquire(blocking=False):
            raise TranscribeError(
                "Busy: another transcription is already running. Try again shortly."
            )
        _current_proc.clear()
        try:
            return transcribe(path, config, model=model, _proc_ref=_current_proc)
        except TranscribeError:
            log.warning("transcribe_audio failed: %s", path)
            raise
        finally:
            _current_proc.clear()
            _transcribe_lock.release()

    @mcp.tool()
    def cancel_transcription() -> str:
        """Cancel the currently running transcription, if any."""
        if not _current_proc:
            return "No transcription is currently running."
        _current_proc[0].kill()
        log.info("Transcription cancelled by user")
        return "Transcription cancelled."

    @mcp.tool()
    def list_allowed_paths() -> list[str]:
        """Return the directories this server is allowed to read audio from."""
        return [str(p) for p in config.allowed_paths]

    @mcp.tool()
    def start_watch(folder: str) -> str:
        """Start watching a folder for new audio files to auto-transcribe.

        New audio files dropped into ``folder`` are transcribed automatically
        and moved to ``<folder>/../done/``. Call ``get_watch_results()`` to
        retrieve completed transcriptions.

        Args:
            folder: Absolute or ``~``-prefixed path to the incoming directory.
        """
        if _watcher and _watcher[0].is_running:
            return f"Already watching {_watcher[0].incoming}. Call stop_watch() first."
        incoming = Path(folder).expanduser().resolve()
        w = FolderWatcher(incoming, config)
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
