"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
import re
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

# whisper-cli reads flac/mp3/ogg/wav natively (per its own --help); intersected with
# ALLOWED_EXTENSIONS since .ogg isn't accepted by this server at all. m4a/mp4/mov/aiff
# would need ffmpeg transcoding first — not implemented, explicit v2 follow-on.
WHISPERCPP_EXTENSIONS: frozenset[str] = frozenset({".wav", ".mp3", ".flac"})

# whisper-cli binary name/path. No app-bundle equivalent to MacWhisper's — relies on
# PATH by default, same as `mw`'s PATH fallback.
DEFAULT_WHISPERCPP_BINARY = "whisper-cli"

# Hard cap on MacWhisper stdout to guard against runaway output.
# Shared by transcribe.py and watcher.py — import from here rather than
# redefining, so the two paths can never drift apart.
MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB

# ISO 639-1 code, or the literal "auto". Shared by the language-defaults parser
# below and by transcribe.py, which re-validates an explicit --language override
# with the same pattern (defense in depth for a directory-derived default).
LANGUAGE_RE = re.compile(r"^(auto|[a-z]{2})$")


@dataclass(frozen=True)
class Config:
    allowed_paths: tuple[Path, ...]
    mw_cli: str = DEFAULT_CLI
    log_path: Path = field(default_factory=lambda: Path(DEFAULT_LOG_PATH))
    # Optional override for the watcher's "done" directory. When None, the
    # watcher defaults to <incoming>/../done (validated against the allow-list
    # in start_watch so it can never silently write outside it).
    watch_done_dir: Path | None = None
    # Per-directory default language, most-specific (deepest path) first.
    # Populated from MACWHISPER_LANGUAGE_DEFAULTS; empty by default (no behavior change).
    language_defaults: tuple[tuple[Path, str], ...] = ()
    # whisper.cpp engine — independent of MacWhisper, opt-in via the `engine` param.
    whispercpp_binary: str = DEFAULT_WHISPERCPP_BINARY
    # Root dir for GGML model files. Required (raises at use-time, not load-time) for
    # the whisper.cpp engine — no default, no auto-download (no network calls invariant).
    whispercpp_model_dir: Path | None = None

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

        language_defaults: list[tuple[Path, str]] = []
        for entry in os.environ.get("MACWHISPER_LANGUAGE_DEFAULTS", "").split(":"):
            entry = entry.strip()
            if not entry:
                continue
            if "=" not in entry:
                raise ValueError(
                    f"Invalid MACWHISPER_LANGUAGE_DEFAULTS entry '{entry}': expected 'dir=lang'."
                )
            dir_str, lang = entry.split("=", 1)
            lang = lang.strip().lower()
            if not LANGUAGE_RE.fullmatch(lang):
                raise ValueError(
                    f"Invalid language code '{lang}' in MACWHISPER_LANGUAGE_DEFAULTS. "
                    "Use an ISO 639-1 code (e.g. 'da', 'de') or 'auto'."
                )
            language_defaults.append((Path(dir_str.strip()).expanduser().resolve(), lang))
        # Deepest path first, so language_for() returns the most specific match.
        language_defaults.sort(key=lambda pair: len(pair[0].parts), reverse=True)

        whispercpp_model_dir_raw = os.environ.get("MACWHISPER_WHISPERCPP_MODEL_DIR")
        whispercpp_model_dir = (
            Path(whispercpp_model_dir_raw).expanduser().resolve()
            if whispercpp_model_dir_raw
            else None
        )

        return cls(
            allowed_paths=allowed,
            mw_cli=os.environ.get("MACWHISPER_CLI", DEFAULT_CLI),
            log_path=log_path,
            watch_done_dir=watch_done_dir,
            language_defaults=tuple(language_defaults),
            whispercpp_binary=os.environ.get(
                "MACWHISPER_WHISPERCPP_BINARY", DEFAULT_WHISPERCPP_BINARY
            ),
            whispercpp_model_dir=whispercpp_model_dir,
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

    def resolve_whispercpp_model(self, name: str) -> Path | None:
        """Resolve `name` to a GGML model file inside MACWHISPER_WHISPERCPP_MODEL_DIR.

        Same symlink-safe prefix check as `is_path_allowed`: `name` is joined onto
        the configured model dir, resolved (following symlinks, collapsing `..`),
        and rejected unless the model dir is still an ancestor of the result. Never
        accept a raw/absolute path for `name` directly — this is the only guard
        against reading arbitrary files via the whisper.cpp `model` argument.

        Returns None if no model dir is configured, `name` escapes it, or the
        resolved file doesn't exist.
        """
        if self.whispercpp_model_dir is None:
            return None
        try:
            resolved = (self.whispercpp_model_dir / name).resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            return None
        if self.whispercpp_model_dir not in resolved.parents:
            return None
        return resolved

    def language_for(self, path: Path) -> str | None:
        """Return the configured default language for `path`, if any.

        `path` should be a resolved directory — the audio file's parent directory,
        or a watcher's incoming directory. `language_defaults` is sorted deepest-path
        first, so the first match is the most specific one.
        """
        for base, lang in self.language_defaults:
            if path == base or base in path.parents:
                return lang
        return None
