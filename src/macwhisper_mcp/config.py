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


@dataclass(frozen=True)
class Config:
    allowed_paths: tuple[Path, ...]
    mw_cli: str = DEFAULT_CLI
    log_path: Path = field(default_factory=lambda: Path(DEFAULT_LOG_PATH))

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

        return cls(
            allowed_paths=allowed,
            mw_cli=os.environ.get("MACWHISPER_CLI", DEFAULT_CLI),
            log_path=log_path,
        )

    def is_path_allowed(self, path: Path) -> bool:
        """True if `path` resolves inside any of the allow-listed directories.

        Uses `Path.resolve()` to follow symlinks before the prefix check, so a symlink
        inside an allowed dir pointing outside is still rejected.
        """
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            return False
        return any(resolved == base or base in resolved.parents for base in self.allowed_paths)
