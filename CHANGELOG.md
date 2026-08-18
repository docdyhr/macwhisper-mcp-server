# Changelog

All notable changes to this project will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.2.1] — 2026-08-18

Maintenance release. No functional change to the server — the 7 MCP tools,
their schemas, and all six security invariants are identical to 1.2.0.

### Changed
- Pinned `fastmcp` bumped `3.4.6` → `3.4.7`. Upstream release is a single
  security fix to CIMD `private_key_jwt` assertion audience validation for
  `OAuthProxy` deployments — unreachable from this server's stdio-only,
  no-network path. Validated per invariant #5: full suite green (96 tests)
  and a live stdio `initialize` + `tools/list` handshake identical to 3.4.6
  on both versions. See `docs/live-tests.md` (2026-08-17).

### Documentation
- Synced the `fastmcp` pin references in `CLAUDE.md` and `PRD.md` to `3.4.7`.
- New `docs/live-tests.md` entry (2026-08-18) recording a post-merge
  verification run on `main`: handshake, `tools/list`, and a live
  `tools/call list_models` round-trip through the real `mw` binary.

### Security
- `github/codeql-action` bumped `4.37.4` → `4.37.7` (CI only, not shipped
  in the package).

---

## [1.2.0] — 2026-08-13

### Added
- `transcribe_audio` accepts an optional `language` argument (ISO 639-1 code,
  or `"auto"`), passed through as `--language` to `mw`.
- `MACWHISPER_LANGUAGE_DEFAULTS` env var maps directories to a default
  language (e.g. `~/Desktop/DK=da`) — files in a matching directory (or its
  subdirectories) get `--language` automatically, most-specific match wins.
  An explicit `language` argument always overrides the directory default.
  Applies to both `transcribe_audio` and watch-folder transcriptions.
- New `engine` argument on `transcribe_audio` (`"macwhisper"` default, or
  `"whisper-cpp"`) — an independent transcription backend using a standalone
  `whisper-cli` binary that does not go through MacWhisper at all. New
  `MACWHISPER_WHISPERCPP_BINARY` / `MACWHISPER_WHISPERCPP_MODEL_DIR` env vars.
  v1 supports `.wav`/`.mp3`/`.flac` input only; see README for setup and
  limitations. `list_models()` now also lists whisper-cpp models when
  `MACWHISPER_WHISPERCPP_MODEL_DIR` is configured.

### Changed
- `transcribe.py` now validates the request and dispatches to a new
  `engines.py` module (MacWhisper and whisper-cpp backends); behavior of the
  MacWhisper path is unchanged. Test mock target for `subprocess.Popen` moved
  from `macwhisper_mcp.transcribe` to `macwhisper_mcp.engines` accordingly.
- The 10 MB output cap is now a single shared `MAX_OUTPUT_BYTES` constant in
  `config.py`, imported by `transcribe.py` and `watcher.py` so the two paths
  can never enforce different limits.

### Fixed
- `cancel_transcription` no longer raises `IndexError` (surfaced to the client
  as an error) when the running transcription finishes and clears the proc
  list in the gap between cancel's non-empty check and its subscript. Cancel
  now uses a single atomic subscript and degrades to "no transcription
  running" instead.
- `__version__` is now read from the installed distribution metadata instead of
  a hardcoded literal, so it can no longer drift from `pyproject.toml` on
  semantic-release bumps.
- `start_watch` now rejects a watch session when the "done" directory falls
  outside the configured allow-list (previously it silently wrote there). The
  done directory is overridable via the new `MACWHISPER_WATCH_DONE_DIR` env
  var; the default remains `<incoming>/../done`.

---

## [1.1.1] — 2026-06-23

### Changed
- **fastmcp bumped 3.2.4 → 3.4.2.** No API changes affect this server; the bump
  picks up upstream bug fixes and performance improvements.

### Fixed
- Access-denied error messages now include the allow-listed paths so the LLM
  (and user) understand why a path was rejected without requiring a separate
  `list_allowed_paths()` call.
- `transcribe_audio` tool description clarifies that files must be on the local
  filesystem, not in Claude's container — suppresses a common LLM fallback.
- Disabled FastMCP's built-in update-check nag on server startup
  (`FASTMCP_CHECK_FOR_UPDATES=off` is no longer required in the Claude Desktop
  config; the server sets it internally).
- CodeQL CI workflow now triggers on the correct branch (`main`).

### Documentation
- Added Homebrew tap as the recommended install method:
  `brew tap docdyhr/tap && brew install docdyhr/tap/macwhisper-mcp-server`
- Claude Desktop config simplified: `"command": "macwhisper-mcp"` (no hardcoded
  venv path) when installed via Homebrew or `pip install`.
- Allowed-paths env var example now uses `~/` shorthand instead of `/Users/<you>/`.
- MIT `LICENSE` file added to repo root.

---

## [1.1.0] — 2026-04-25

### Added
- `list_models()` MCP tool — runs `mw models list` and returns installed
  MacWhisper models with display names; the active model is marked `[active]`.
  Model IDs returned can be passed directly to `transcribe_audio(model=…)`.
- `persist` parameter on `transcribe_audio` — pass `persist=true` to save the
  transcription to MacWhisper's history database (`mw --persist`).
- `tests/test_server.py` — 13 tests covering all 8 MCP tools including `list_models`
  and `persist`, concurrency lock, lock-release-on-exception, and cancel.

### Fixed
- `watcher.py`: apply 10 MB output size cap to watcher transcriptions, matching
  the existing cap in `transcribe.py`.
- `publish.yml`: publish job now requires tests to pass (new `test` job that `build`
  depends on), preventing broken releases via `workflow_dispatch`.
- `ci.yml`: corrected `cache-dependency-path` from stale `requirements*.txt` to
  `pyproject.toml`.
- `pyproject.toml`: narrowed `requires-python` from `>=3.10` to `>=3.13` to match
  the Python version actually tested and supported.
- `.gitignore`: added `server.json` (MCP Registry publish artifact).

### Documentation
- README: added Homebrew install path, `mw version` verify command, updated tools
  table with `list_models` and `persist`.
- CLAUDE.md: updated status, layout, known quirks, and mock path conventions to
  reflect current codebase.

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
