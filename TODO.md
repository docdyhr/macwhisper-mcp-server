# TODO — MacWhisper MCP Server

Tracking against [PRD.md](./PRD.md).

---

## Phase 0 — Scaffolding (now)

- [x] Install Python 3.13.13 via pyenv
- [x] License MacWhisper app
- [x] Write PRD
- [x] Scaffold repo structure
- [x] Initialize git, commit `chore: initial scaffold`
- [x] Create GitHub repo (private initially), push
- [ ] Verify `mw --help` works from terminal
- [ ] Install deps: `pip install -r requirements.txt`

## Phase 1 — MVP (v0.1.0)

Goal: single tool `transcribe_audio` working end-to-end with Claude Desktop.

- [x] `src/macwhisper_mcp/config.py` — load allowed paths from env, defaults to `~/Desktop`
- [x] `src/macwhisper_mcp/transcribe.py` — `run_mw(path: Path) -> str` using `subprocess.run` with argv list
- [x] `src/macwhisper_mcp/server.py` — FastMCP server exposing `transcribe_audio`
- [x] Path validation: resolve symlinks, check prefix against allow-list
- [x] File-exists check before invoking `mw`
- [x] Error handling: missing CLI, missing file, denied path, `mw` non-zero exit
- [x] File-based logging to `~/Library/Logs/macwhisper-mcp.log` (NOT stdout)
- [x] Manual smoke test: transcribe a 30-second test clip on Desktop
- [x] Wire into Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`)
- [x] Verify end-to-end: ask Claude to transcribe → summarize a file

## Phase 2 — Hardening (v0.2.0)

- [x] Add file-extension allow-list (`.m4a`, `.mp3`, `.wav`, `.mp4`, `.mov`)
- [x] Add `list_allowed_paths()` MCP tool for discoverability
- [x] Unit tests: `test_config.py`, `test_transcribe.py` (mock `subprocess.run`)
- [x] Integration test with a tiny sample audio file checked into `tests/fixtures/`
- [x] GitHub Actions CI: lint (ruff) + tests on push/PR (fixed branch: master)
- [x] Pre-commit hooks: ruff, ruff-format (`.pre-commit-config.yaml`)
- [x] Write proper README with install + config walkthrough + screenshots
- [x] Add `scripts/smoke_test.py <audio-file>` — reusable CLI harness for live testing

## Phase 3 — Structured output (v0.3.0)

- [x] Investigate `mw` CLI flags for JSON / SRT output → logged in PRD §11
- [x] `--model` parameter exposed on `transcribe_audio` tool (engine:model-id format)
- [ ] True structured output (timestamps, segments) not available via CLI — deferred until
      MacWhisper adds a `--json` flag or we parse the internal SQLite DB directly

## Phase 4 — Ergonomics (v0.4.0)

- [ ] Watch-folder mode: `~/Transcriptions/incoming` auto-transcribes, moves to `/done`
- [ ] Language parameter passed through to `mw`
- [ ] Cancel-running-job tool
- [ ] Concurrent request handling strategy decided (queue vs. reject)

## Phase 5 — Release (v1.0.0)

- [ ] Publish to PyPI (optional)
- [ ] Public GitHub release with changelog
- [ ] Blog post / README polish for public discovery
- [ ] Consider submitting to MCP registry / awesome-mcp lists

---

## Backlog / ideas

- DMG installer or Homebrew tap for non-technical users
- Menu-bar app wrapping the server (start/stop, log viewer)
- Alternative engine support (whisper.cpp) behind same MCP interface
- Per-directory language defaults (e.g. `~/Desktop/DK/` → force Danish)

## Won't do (explicit)

- Cloud transcription — defeats the privacy goal
- Non-macOS support — MacWhisper is macOS-only
- Real-time streaming — out of scope; use a different tool if needed
