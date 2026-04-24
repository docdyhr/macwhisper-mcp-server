# Changelog

All notable changes to this project will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — v0.3.0

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
