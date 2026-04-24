# TODO — MacWhisper MCP Server

Tracking against [PRD.md](./PRD.md).

---

## Phase 0 — Scaffolding (now)

- [x] Install Python 3.13.13 via pyenv
- [x] License MacWhisper app
- [x] Write PRD
- [ ] Scaffold repo structure
- [ ] Initialize git, commit `chore: initial scaffold`
- [ ] Create GitHub repo (private initially), push
- [ ] Verify `mw --help` works from terminal
- [ ] Install deps: `pip install -r requirements.txt`

## Phase 1 — MVP (v0.1.0)

Goal: single tool `transcribe_audio` working end-to-end with Claude Desktop.

- [ ] `src/macwhisper_mcp/config.py` — load allowed paths from env, defaults to `~/Desktop`
- [ ] `src/macwhisper_mcp/transcribe.py` — `run_mw(path: Path) -> str` using `subprocess.run` with argv list
- [ ] `src/macwhisper_mcp/server.py` — FastMCP server exposing `transcribe_audio`
- [ ] Path validation: resolve symlinks, check prefix against allow-list
- [ ] File-exists check before invoking `mw`
- [ ] Error handling: missing CLI, missing file, denied path, `mw` non-zero exit
- [ ] File-based logging to `~/Library/Logs/macwhisper-mcp.log` (NOT stdout)
- [ ] Manual smoke test: transcribe a 30-second test clip on Desktop
- [ ] Wire into Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`)
- [ ] Verify end-to-end: ask Claude to transcribe → summarize a file

## Phase 2 — Hardening (v0.2.0)

- [ ] Add file-extension allow-list (`.m4a`, `.mp3`, `.wav`, `.mp4`, `.mov`)
- [ ] Add `list_allowed_paths()` MCP tool for discoverability
- [ ] Unit tests: `test_config.py`, `test_transcribe.py` (mock `subprocess.run`)
- [ ] Integration test with a tiny sample audio file checked into `tests/fixtures/`
- [ ] GitHub Actions CI: lint (ruff) + tests on push/PR
- [ ] Pre-commit hooks: ruff, ruff-format
- [ ] Write proper README with install + config walkthrough + screenshots

## Phase 3 — Structured output (v0.3.0)

- [ ] Investigate `mw` CLI flags for JSON / SRT output → log findings in PRD §11
- [ ] If supported: add `transcribe_structured(path) -> dict` returning segments with timestamps
- [ ] If not supported: parse plain output into segments heuristically OR skip this phase

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
