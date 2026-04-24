# CLAUDE.md

Context for Claude Code working on this repo. Read this first.

## What this is

A local MCP server that exposes [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) transcription to Claude Desktop. Audio → MacWhisper → MCP → Claude. Fully local, fully private. See [PRD.md](./PRD.md) for the full spec and [TODO.md](./TODO.md) for the roadmap.

## Current status (2026-04-24)

**Scaffolded and wired into Claude Desktop. First live transcription not yet confirmed.**

Verified working:
- Python 3.13.13 venv at `.venv/` with `fastmcp==3.2.4`
- Package imports cleanly (`macwhisper_mcp.{config,transcribe,server}`)
- MacWhisper CLI at `/Applications/MacWhisper.app/Contents/MacOS/mw` — auto-detected by `config.py` (not on shell PATH; do not assume `mw` works bare)
- MCP `initialize` + `tools/list` handshake works over stdio — both `transcribe_audio` and `list_allowed_paths` are exposed
- 16/16 tests pass (`pytest -q`)
- Wired into Claude Desktop via console script `.venv/bin/macwhisper-mcp`; allowed paths: `~/Desktop` and `~/Downloads`

Not yet done:
- First real transcription via Claude Desktop
- CI has never run (repo exists at `github.com/docdyhr/macwhisper-mcp-server`, workflow is written but hasn't triggered yet)

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
└── server.py        # FastMCP entry point, tool definitions
tests/
├── conftest.py      # Fixtures: allowed_dir, audio_file, config
├── test_config.py   # 6 tests incl. symlink-escape
└── test_transcribe.py  # 9 tests, subprocess.run mocked
```

## Non-negotiable invariants

These are load-bearing for security. Do not loosen them without updating the PRD threat model:

1. **Argv list, never a shell.** `subprocess.run` is called with `[cli, "transcribe", path]` and no `shell=True`. There is a test that asserts this (`test_transcribe_uses_argv_list_not_shell`).
2. **Path allow-list with symlink resolution.** `Config.is_path_allowed` calls `Path.resolve(strict=True)` before the prefix check, so a symlink inside an allowed dir pointing outside is rejected. Test: `test_is_path_allowed_rejects_symlink_escape`.
3. **File-extension allow-list.** Only audio/video extensions in `ALLOWED_EXTENSIONS` reach the CLI.
4. **Logs go to a file, never stdout.** Stdout is reserved for MCP JSON-RPC. `server._setup_logging` uses `logging.basicConfig(filename=...)`. Never add `print()` to the server path.
5. **Pin `fastmcp` exactly.** FastMCP uses semver with breaking changes possible in minor releases. `requirements.txt` and `pyproject.toml` both pin `==3.2.4`.

## Known quirks

- `mw` binary is inside `/Applications/MacWhisper.app/Contents/MacOS/mw`, not on PATH. `config.py` auto-detects it; setting `MACWHISPER_CLI=mw` bare will fail unless the user has manually symlinked it.
- `mw transcribe <file>` prints the full transcript to stdout when `--stream` is not passed. We rely on this; do not add `--stream` without rewriting the stdout handling in `transcribe.py`.
- `FastMCP("macwhisper")` reports its own version (`3.2.4`) in `serverInfo`, not our package version. Cosmetic only — fix by passing `version=__version__` when we care about it.
- CI runs on `macos-latest` only — Linux runners don't have MacWhisper anyway, and mocks cover the subprocess layer.

## Conventions

- Formatting: `ruff format` (line length 100, target `py313`)
- Linting: `ruff check` with `E, F, W, I, B, UP, SIM, RUF`
- Tests: `pytest` with `pytest-mock`. Mock `subprocess.run` at `macwhisper_mcp.transcribe.subprocess.run`, never at the stdlib level.
- Commit style: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- When adding an MCP tool: define it inside `build_server()` so it closes over `config`. Always wrap user-facing errors in `TranscribeError` (or a new domain exception) — raw stdlib exceptions leak implementation details.

## Next actions for Claude Code

In priority order — check against TODO.md Phase 1:

1. ~~Initialize git and push to GitHub~~ — done. Repo at `github.com/docdyhr/macwhisper-mcp-server`.
2. ~~Wire into Claude Desktop config~~ — done. Console script wired, `~/Desktop` and `~/Downloads` allowed.
3. Run the first live transcription on a file in `~/Desktop` and log any rough edges here.
4. Add a test asserting `config.py` picks up `/Applications/MacWhisper.app/Contents/MacOS/mw` when the file exists (pair it with a `monkeypatch` of the `_BUNDLED_CLI` constant).
5. Move to TODO Phase 2 (hardening: extension allow-list already done, so focus on integration test with a real tiny audio fixture).

## Things to NOT do

- Do not add cloud fallback, telemetry, or any network call from the server process. Privacy is a hard requirement (PRD §7).
- Do not introduce `shell=True`, `os.system`, or string-based subprocess commands anywhere.
- Do not widen the default allow-list beyond `~/Desktop`. Users opt in per directory via env.
- Do not bump `fastmcp` to a new minor version without reading their upgrade notes and re-running the MCP handshake test.
- Do not commit `.env`, fixture audio files, or anything in `~/Library/Logs/`.
