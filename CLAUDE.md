# CLAUDE.md

Context for Claude Code working on this repo. Read this first.

## What this is

A local MCP server that exposes [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) transcription to Claude Desktop. Audio → MacWhisper → MCP → Claude. Fully local, fully private. See [PRD.md](./PRD.md) for the full spec and [TODO.md](./TODO.md) for the roadmap.

## Current status (2026-06-23)

**v1.1.1 — 8 MCP tools, 48 tests green. Repo public. Published on PyPI, MCP Registry, and Homebrew tap (`docdyhr/tap`). Next: v1.2.0.dev0.**

Verified working:
- Python 3.13.13 venv at `.venv/` with `fastmcp==3.4.2`
- Package imports cleanly (`macwhisper_mcp.{config,transcribe,server,watcher}`)
- MacWhisper 13.20 (1410) installed via `brew install --cask macwhisper`
- CLI at `/usr/local/bin/mw` (symlink → `/Applications/MacWhisper.app/Contents/MacOS/mw`); `mw` is on PATH. `config.py` auto-detects the app-bundle path and uses it directly.
- MCP `initialize` + `tools/list` handshake works over stdio.
- **Live transcription round-trip confirmed** via synthetic MCP client — 13.6s on a short Danish clip, UTF-8 clean. See [`docs/live-tests.md`](./docs/live-tests.md).
- 48/48 tests pass (`pytest -q`)
- CI green on every push (GitHub Actions, `macos-latest`, Python 3.13)
- CodeQL SAST scan enabled and clean
- Published: PyPI (`pip install macwhisper-mcp-server`) and MCP Registry (`io.github.docdyhr/macwhisper-mcp-server`)
- awesome-mcp-servers PR #5397 open (waiting on maintainer)

## Dev commands

```bash
source .venv/bin/activate

# Tests + lint
pytest -q
ruff check .
ruff format .

# Run the server standalone (stdio — it will sit idle waiting for MCP traffic)
python -m macwhisper_mcp.server

# Smoke-test the MCP handshake without Claude Desktop
# (pattern lives in git history / this file's discussion)
```

## Layout

```
src/macwhisper_mcp/
├── config.py        # Env loading, path allow-list, CLI auto-detection
├── transcribe.py    # Subprocess wrapper around `mw transcribe <file>`
├── watcher.py       # Background folder-watcher, FolderWatcher class
└── server.py        # FastMCP entry point, all 8 tool definitions
tests/
├── conftest.py          # Fixtures: allowed_dir, audio_file, config
├── test_config.py       # Config + allow-list tests
├── test_transcribe.py   # transcribe() unit tests, Popen mocked
├── test_watcher.py      # FolderWatcher tests, subprocess.run mocked
└── test_server.py       # MCP tool layer tests via FastMCP Client
```

## Non-negotiable invariants

These are load-bearing for security. Do not loosen them without updating the PRD threat model:

1. **Argv list, never a shell.** `subprocess.run` is called with `[cli, "transcribe", path]` and no `shell=True`. There is a test that asserts this (`test_transcribe_uses_argv_list_not_shell`).
2. **Path allow-list with symlink resolution.** `Config.is_path_allowed` calls `Path.resolve(strict=True)` before the prefix check, so a symlink inside an allowed dir pointing outside is rejected. Test: `test_is_path_allowed_rejects_symlink_escape`.
3. **File-extension allow-list.** Only audio/video extensions in `ALLOWED_EXTENSIONS` reach the CLI.
4. **Logs go to a file, never stdout.** Stdout is reserved for MCP JSON-RPC. `server._setup_logging` uses `logging.basicConfig(filename=...)`. Never add `print()` to the server path.
5. **Pin `fastmcp` exactly.** FastMCP uses semver with breaking changes possible in minor releases. `requirements.txt` and `pyproject.toml` both pin `==3.2.4`.

## Known quirks

- `mw` is on PATH at `/usr/local/bin/mw` (symlink → app bundle) when the CLI is installed via MacWhisper → Settings → Advanced → Install. `config.py` prefers the explicit app-bundle path; `MACWHISPER_CLI=mw` also works now. When MacWhisper is upgraded via `brew upgrade --cask macwhisper`, the symlink stays valid — no re-install needed.
- `mw transcribe <file>` prints the full transcript to stdout when `--stream` is not passed. We rely on this; do not add `--stream` without rewriting the stdout handling in `transcribe.py`.
- `mw models list` output is space-padded tabular text (not JSON). `list_models()` in `server.py` parses it with `re.split(r"\s{2,}", ...)`.
- `FastMCP("macwhisper")` reports its own version (`3.2.4`) in `serverInfo`, not our package version. Cosmetic only — fix by passing `version=__version__` when we care about it.
- CI runs on `macos-latest` only — Linux runners don't have MacWhisper anyway, and mocks cover the subprocess layer.

## Conventions

- Formatting: `ruff format` (line length 100, target `py313`)
- Linting: `ruff check` with `E, F, W, I, B, UP, SIM, RUF`
- Tests: `pytest` with `pytest-mock`. Mock `subprocess.Popen` at `macwhisper_mcp.transcribe.subprocess.Popen` and `subprocess.run` at `macwhisper_mcp.server.subprocess.run` / `macwhisper_mcp.watcher.subprocess.run` — always at the module that uses it, never at stdlib level.
- Commit style: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- When adding an MCP tool: define it inside `build_server()` so it closes over `config`. Always wrap user-facing errors in `TranscribeError` (or a new domain exception) — raw stdlib exceptions leak implementation details.

## Next actions for Claude Code

1. Run the first live transcription **from inside Claude Desktop** on a file in `~/Desktop` or `~/Downloads`. Log the result as a new entry in `docs/live-tests.md` using the same format.
2. After any user-facing change, bump the version (semver patch/minor) and run `/release`.

**Live test logging protocol.** Any end-to-end test against the running server — synthetic client, Claude Desktop, future smoke-test script, anything — gets a new entry appended to [`docs/live-tests.md`](./docs/live-tests.md). One entry per distinct run. Do not overwrite old entries; they are the regression record.

## Things to NOT do

- Do not add cloud fallback, telemetry, or any network call from the server process. Privacy is a hard requirement (PRD §7).
- Do not introduce `shell=True`, `os.system`, or string-based subprocess commands anywhere.
- Do not widen the default allow-list beyond `~/Desktop`. Users opt in per directory via env.
- Do not bump `fastmcp` to a new minor version without reading their upgrade notes and re-running the MCP handshake test.
- Do not commit `.env`, fixture audio files, or anything in `~/Library/Logs/`.
