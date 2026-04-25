# Changelog

All notable changes to this project will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.0.1] — 2026-04-25

### Changed
- Add `mcp-name` marker to README for MCP Registry (registry.modelcontextprotocol.io) ownership verification.

---

## [1.0.0] — 2026-04-25

First stable public release. All five development phases complete: MVP → hardening
→ structured output → ergonomics → security. 7 MCP tools, 33 tests, fully local.

### Security

- **Resolve-before-validate in `transcribe()`.** Path symlinks are now fully resolved
  *before* extension and allow-list checks, closing a TOCTOU race where a symlink could
  change between validation and CLI invocation.
- **Null-byte rejection.** Paths containing `\x00` are rejected immediately in
  `transcribe()` before any filesystem access.
- **Model identifier sanitization.** The `model` parameter is now validated against
  `[a-zA-Z0-9_:.-]+` before being passed to the CLI, preventing argument injection.
- **No allow-list leakage in errors.** "Access denied" messages no longer include the
  full allow-list; this was an information-disclosure issue.
- **`start_watch()` folder validation.** The folder path is now checked against the
  allow-list before starting the watcher; previously any directory could be watched.
- **Symlink rejection in watcher.** `FolderWatcher._scan()` skips symbolic links;
  a symlink inside `incoming/` pointing outside the allow-list could otherwise cause
  MacWhisper to read arbitrary files.
- **`MACWHISPER_LOG_PATH` must be under `$HOME`.** `Config.from_env()` rejects log
  paths outside the user's home directory to prevent log-file hijacking.
- **Output size cap.** `transcribe()` raises `TranscribeError` if `mw` stdout exceeds
  10 MB, guarding against runaway output consuming memory.

---

## [0.4.0] — 2026-04-24

### Added
- **Concurrency rejection.** A `threading.Lock` in the server rejects a second
  `transcribe_audio` call while one is already in progress, returning a clear
  "Busy" error instead of silently queuing or crashing.
- **`cancel_transcription()` MCP tool.** Kills the running MacWhisper subprocess
  mid-transcription. Useful for long audio or cold-start situations.
- **`start_watch(folder)` / `stop_watch()` / `get_watch_results()` MCP tools.**
  Background folder watcher: drops audio files into the watched `incoming/`
  directory and they are transcribed automatically and moved to `done/`.
  Failed files are skipped for the remainder of the session (not retried in a loop).
- **`watcher.py`** — `FolderWatcher` class with atomic rename-based claim to
  prevent double-processing and thread-safe result queue.
- Refactored `subprocess.run` → `subprocess.Popen + communicate` in `transcribe.py`
  to enable external process cancellation.
- 6 new watcher tests; all transcribe tests updated for Popen mock pattern.

### Investigated
- **Language parameter** (`mw --language`): flag does not exist in the MacWhisper CLI.
  Documented in PRD §11. Users select language via model choice (Whisper is
  multilingual by default).

---

## [0.3.0] — 2026-04-24

### Added
- `model` parameter on `transcribe_audio` tool — pass any `mw`-recognised model ID
  (e.g. `whisperkit:openai_whisper-large-v3-v20240930`, `parakeet-pro:nvidia_parakeet-v3_494MB`)
  to override the default model selected in MacWhisper.
- PRD §11 updated with `mw transcribe` CLI findings: no JSON/SRT output, no timestamps;
  `--model` and `--stream` are the only non-trivial flags.

### Notes
- Structured output (timestamps, speaker segments) is not available via the `mw` CLI.
  True structured output would require parsing MacWhisper's internal SQLite DB or a future
  CLI flag — deferred to a later phase.

---

## [0.2.0] — 2026-04-24

### Added
- File-extension allow-list (`.m4a`, `.mp3`, `.mp4`, `.mov`, `.wav`, `.aiff`, `.flac`) —
  unsupported extensions are rejected before the CLI is invoked.
- `list_allowed_paths()` MCP tool for discoverability.
- Integration tests using a real WAV fixture (`tests/fixtures/sample.wav`).
- `tests/fixtures/tears_in_rain.wav` — Blade Runner monologue clip for smoke testing.
- `scripts/smoke_test.py` — async MCP client harness; replaces ad-hoc `/tmp/` scripts.
- `.pre-commit-config.yaml` — ruff lint + format hooks.
- GitHub Actions CI (`ci.yml`) — lint, format, and tests on every push/PR to master.
- Full README rewrite: install walkthrough, tools table, config reference, known limitations.

### Fixed
- CI workflow was triggering on `main` — repo uses `master`; added both branches.
- `.env.example` contained hardcoded `/Users/thomas/` paths; replaced with `~/`.
- `.envrc` now loads `.env` via `dotenv_if_exists` so direnv users get env vars automatically.

---

## [0.1.0] — 2026-04-24

### Added
- `src/macwhisper_mcp/config.py` — env-driven config with path allow-list, symlink
  resolution, and auto-detection of the bundled MacWhisper CLI.
- `src/macwhisper_mcp/transcribe.py` — subprocess wrapper around `mw transcribe`;
  validates path, extension, and allow-list before invoking the CLI.
- `src/macwhisper_mcp/server.py` — FastMCP server exposing `transcribe_audio` and
  `list_allowed_paths` tools over stdio.
- File-based logging to `~/Library/Logs/macwhisper-mcp.log` (stdout reserved for MCP).
- `CLAUDE.md` — project context and invariants for Claude Code sessions.
- `docs/live-tests.md` — chronological log of end-to-end test runs.
- `PRD.md` — full product requirements including threat model (§7) and known limitations (§12).

### Verified
- Full MCP handshake (initialize → tools/list → tools/call → transcript) working over stdio.
- Live transcription confirmed from inside Claude Desktop (2026-04-24).
- Danish UTF-8 diacritics clean end-to-end (`Blåbærgrød` intact through JSON-RPC stdio).
- Cold-start latency ~13s (model load); warm ~1.9s.
