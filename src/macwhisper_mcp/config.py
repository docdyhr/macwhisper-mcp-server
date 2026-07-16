"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ALLOWED = str(Path.home() / "Desktop")
DEFAULT_LOG_PATH = str(Path.home() / "Library" / "Logs" / "macwhisper-mcp.log")

# MacWhisper ships its CLI binary inside the app bundle and does not put it on PATH
# by default. Prefer the app-bundle path if present, fall back to `mw` on PATH.
_BUNDLED_CLI = Path("/Applications/MacWhisper.app/Contents/MacOS/mw")
DEFAULT_CLI = str(_BUNDLED_CLI) if _BUNDLED_CLI.exists() else "mw"

# File extensions accepted by MacWhisper. Reject anything else before invoking the CLI.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".m4a", ".mp3", ".mp4", ".mov", ".wav", ".aiff", ".flac"}
)

# Hard cap on MacWhisper stdout to guard against runaway output.
# Shared by transcribe.py and watcher.py — import from here rather than
# redefining, so the two paths can never drift apart.
MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass(frozen=True)
class Config:
    allowed_paths: tuple[Path, ...]
    mw_cli: str = DEFAULT_CLI
    log_path: Path = field(default_factory=lambda: Path(DEFAULT_LOG_PATH))
    # Optional override for the watcher's "done" directory. When None, the
    # watcher defaults to <incoming>/../done (validated against the allow-list
    # in start_watch so it can never silently write outside it).
    watch_done_dir: Path | None = None

    @classmethod
    def from_env(cls) -> Config:
        raw = os.environ.get("MACWHISPER_ALLOWED_PATHS", DEFAULT_ALLOWED)
        allowed = tuple(Path(p).expanduser().resolve() for p in raw.split(":") if p.strip())
        if not allowed:
            raise ValueError("MACWHISPER_ALLOWED_PATHS must contain at least one directory.")

        log_path_str = os.environ.get("MACWHISPER_LOG_PATH", DEFAULT_LOG_PATH)
        log_path = Path(log_path_str).expanduser()
        home = Path.home()
        # resolve() without strict handles non-existent paths via lexical .. collapsing.
        if home not in log_path.resolve().parents:
            raise ValueError(
                f"MACWHISPER_LOG_PATH must be inside your home directory ({home}). Got: {log_path}"
            )

        watch_done_dir_raw = os.environ.get("MACWHISPER_WATCH_DONE_DIR")
        watch_done_dir = (
            Path(watch_done_dir_raw).expanduser().resolve() if watch_done_dir_raw else None
        )

        return cls(
            allowed_paths=allowed,
            mw_cli=os.environ.get("MACWHISPER_CLI", DEFAULT_CLI),
            log_path=log_path,
            watch_done_dir=watch_done_dir,
        )

    def is_path_allowed(self, path: Path, strict: bool = True) -> bool:
        """True if `path` resolves inside any of the allow-listed directories.

        Uses `Path.resolve()` to follow symlinks before the prefix check, so a symlink
        inside an allowed dir pointing outside is still rejected.

        Args:
            path: The path to check.
            strict: When True (default, for existing files) require the path to
                exist — a missing file is rejected. When False, allow a
                not-yet-created path (used for the watcher's ``done`` dir, which
                is validated before it is created). Symlinks are still followed
                and an escaping symlink is rejected either way.
        """
        try:
            resolved = path.resolve(strict=strict)
        except (FileNotFoundError, RuntimeError):
            return False
        return any(resolved == base or base in resolved.parents for base in self.allowed_paths)
