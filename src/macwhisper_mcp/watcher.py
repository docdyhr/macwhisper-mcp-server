"""Background folder watcher that auto-transcribes new audio files.

Design:
- Polls ``incoming/`` every ``poll_interval`` seconds.
- Uses an atomic rename (``incoming/file`` → ``done/.processing_file``) to claim
  each file before transcribing, so concurrent scans never double-process.
- On success: moves processed file to ``done/file`` and stores the result.
- On failure: restores the file to ``incoming/`` and stores the error.
- Results are drained by calling ``drain_results()``.
"""

from __future__ import annotations

import contextlib
import logging
import subprocess
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ALLOWED_EXTENSIONS, MAX_OUTPUT_BYTES, Config

log = logging.getLogger(__name__)


@dataclass
class WatchResult:
    file: str
    transcript: str | None
    destination: str | None
    error: str | None


class FolderWatcher:
    """Watches an ``incoming`` directory and transcribes new audio files."""

    def __init__(
        self,
        incoming: Path,
        config: Config,
        poll_interval: float = 2.0,
        done_dir: Path | None = None,
    ) -> None:
        self.incoming = incoming.resolve()
        # Default to a sibling "done" dir; callers (start_watch) may override
        # via Config.watch_done_dir and must validate it against the allow-list.
        self.done_dir = (
            done_dir.expanduser().resolve() if done_dir else self.incoming.parent / "done"
        )
        self.config = config
        self.poll_interval = poll_interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._results: list[WatchResult] = []
        self._lock = threading.Lock()
        self._failed: set[str] = set()  # filenames that failed — skipped until watcher restarts

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError(f"Already watching {self.incoming}")
        self.incoming.mkdir(parents=True, exist_ok=True)
        self.done_dir.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="macwhisper-watcher")
        self._thread.start()
        log.info("Watcher started: %s → %s", self.incoming, self.done_dir)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        log.info("Watcher stopped: %s", self.incoming)

    def drain_results(self) -> list[dict]:
        """Return all completed results and clear the internal queue."""
        with self._lock:
            results = [asdict(r) for r in self._results]
            self._results.clear()
        return results

    def _run(self) -> None:
        while not self._stop.is_set():
            self._scan()
            self._stop.wait(timeout=self.poll_interval)

    def _scan(self) -> None:
        try:
            candidates = [
                p
                for p in self.incoming.iterdir()
                if p.is_file()
                and not p.is_symlink()  # symlinks could escape the allow-list
                and p.suffix.lower() in ALLOWED_EXTENSIONS
                and p.name not in self._failed
            ]
        except OSError as e:
            log.error("Watcher scan error: %s", e)
            return
        for path in candidates:
            self._process(path)

    def _process(self, path: Path) -> None:
        processing = self.done_dir / f".processing_{path.name}"
        try:
            path.rename(processing)
        except OSError:
            return  # Another scan iteration already claimed this file

        log.info("Watcher: processing %s", path.name)
        try:
            result = subprocess.run(
                [self.config.mw_cli, "transcribe", str(processing)],
                capture_output=True,
                text=True,
                check=True,
                timeout=60 * 60,
            )
            if len(result.stdout) > MAX_OUTPUT_BYTES:
                raise ValueError(
                    f"MacWhisper output exceeded size limit ({MAX_OUTPUT_BYTES // 1_000_000} MB)."
                )
            transcript = result.stdout.strip()
            dest = self.done_dir / path.name
            processing.rename(dest)
            self._append(
                WatchResult(
                    file=path.name,
                    transcript=transcript,
                    destination=str(dest),
                    error=None,
                )
            )
            log.info("Watcher: done %s (%d chars)", path.name, len(transcript))
        except Exception as e:
            log.error("Watcher: failed %s: %s", path.name, e)
            self._failed.add(path.name)
            with contextlib.suppress(OSError):
                processing.rename(path)
            self._append(
                WatchResult(file=path.name, transcript=None, destination=None, error=str(e))
            )

    def _append(self, result: WatchResult) -> None:
        with self._lock:
            self._results.append(result)
