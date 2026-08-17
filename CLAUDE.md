# CLAUDE.md

Context for Claude Code working on this repo. Read this first.

## What this is

A local MCP server that exposes [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) transcription to Claude Desktop. Audio → MacWhisper → MCP → Claude. Fully local, fully private. An optional `whisper-cpp` engine is also available (`engine="whisper-cpp"`) that bypasses MacWhisper entirely — see PRD §3/§8. See [PRD.md](./PRD.md) for the full spec and [TODO.md](./TODO.md) for the roadmap.

## Current status (2026-08-11)

**v1.2.0 — 7 MCP tools, 96 tests green. Repo public. Published on PyPI, MCP Registry, and Homebrew tap (`docdyhr/tap`).**

Verified working:
- Python 3.13.13 venv at `.venv/` with `fastmcp==3.4.7`
- Package imports cleanly (`macwhisper_mcp.{config,transcribe,server,watcher}`)
- MacWhisper 14.6 (1472) installed via `brew install --cask macwhisper` (was 13.20/1410 — corrected 2026-08-11; `mw`'s CLI has grown `--language`, `--format json/srt/vtt/...`, `--timestamps`, `--speakers` since the last PRD investigation, see PRD §11)
- CLI at `/usr/local/bin/mw` (symlink → `/Applications/MacWhisper.app/Contents/MacOS/mw`); `mw` is on PATH. `config.py` auto-detects the app-bundle path and uses it directly.
- MCP `initialize` + `tools/list` handshake works over stdio.
- **Live transcription round-trip confirmed** via synthetic MCP client — 13.6s on a short Danish clip, UTF-8 clean. See [`docs/live-tests.md`](./docs/live-tests.md).
- 96/96 tests pass (`pytest -q`)
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
├── transcribe.py    # Validates the request, dispatches to engines.py
├── engines.py        # MacWhisper (`mw`) and whisper-cpp (`whisper-cli`) backends
├── watcher.py       # Background folder-watcher, FolderWatcher class (MacWhisper only)
└── server.py        # FastMCP entry point, all 7 tool definitions
tests/
├── conftest.py          # Fixtures: allowed_dir, audio_file, config
├── test_config.py       # Config + allow-list tests
├── test_transcribe.py   # transcribe() unit tests (MacWhisper path), Popen mocked
├── test_engines.py      # whisper-cpp engine unit tests, Popen mocked
├── test_watcher.py      # FolderWatcher tests, subprocess.run mocked
└── test_server.py       # MCP tool layer tests via FastMCP Client
```

## Non-negotiable invariants

These are load-bearing for security. Do not loosen them without updating the PRD threat model:

1. **Argv list, never a shell.** `subprocess.run` is called with `[cli, "transcribe", path]` and no `shell=True`. There is a test that asserts this (`test_transcribe_uses_argv_list_not_shell`).
2. **Path allow-list with symlink resolution.** `Config.is_path_allowed` calls `Path.resolve(strict=True)` before the prefix check, so a symlink inside an allowed dir pointing outside is rejected. Test: `test_is_path_allowed_rejects_symlink_escape`.
3. **File-extension allow-list.** Only audio/video extensions in `ALLOWED_EXTENSIONS` reach the CLI.
4. **Logs go to a file, never stdout.** Stdout is reserved for MCP JSON-RPC. `server._setup_logging` uses `logging.basicConfig(filename=...)`. Never add `print()` to the server path.
5. **Pin `fastmcp` exactly.** FastMCP uses semver with breaking changes possible in minor releases. `requirements.txt` and `pyproject.toml` both pin `==3.4.7`.
6. **whisper-cpp model paths must resolve inside `MACWHISPER_WHISPERCPP_MODEL_DIR`.** `Config.resolve_whispercpp_model` uses the same `resolve(strict=True)` + prefix-check pattern as invariant #2 — never accept a raw/absolute path for the `model` argument when `engine="whisper-cpp"`. Test: `test_resolve_whispercpp_model_rejects_symlink_escape`, `test_resolve_whispercpp_model_rejects_traversal`.

## Known quirks

- `mw` is on PATH at `/usr/local/bin/mw` (symlink → app bundle) when the CLI is installed via MacWhisper → Settings → Advanced → Install. `config.py` prefers the explicit app-bundle path; `MACWHISPER_CLI=mw` also works now. When MacWhisper is upgraded via `brew upgrade --cask macwhisper`, the symlink stays valid — no re-install needed.
- `mw transcribe <file>` prints the full transcript to stdout when `--stream` is not passed. We rely on this; do not add `--stream` without rewriting the stdout handling in `transcribe.py`.
- `mw models list` output is space-padded tabular text (not JSON). `list_models()` in `server.py` parses it with `re.split(r"\s{2,}", ...)`.
- `FastMCP("macwhisper")` reports fastmcp's own version in `serverInfo`, not our package version — currently `3.4.7`, tracking whatever `fastmcp` is pinned to. Cosmetic only — fix by passing `version=__version__` when we care about it.
- CI runs on `macos-latest` only — Linux runners don't have MacWhisper anyway, and mocks cover the subprocess layer.
- **whisper-cli (whisper.cpp) requires `-nt` for plain text.** Verified live against whisper-cli 1.9.2: without `-nt` every line is prefixed with `[00:00:00.000 --> 00:00:07.960]`; `_run_whispercpp` always passes `-np -nt`. Its noisy Metal/GGML init logs go to stderr, never stdout — confirmed by isolating each stream, same clean separation as `mw`.
- **whisper-cli's own default language is English (`en`), not auto-detect.** Unlike MacWhisper (which defers to the app's own selection when `--language` is omitted), whisper-cli defaults to `en` per its `--help`. Only relevant when neither an explicit `language` argument nor a `MACWHISPER_LANGUAGE_DEFAULTS` match applies.
- **whisper-cli only reads flac/mp3/ogg/wav natively** (per its own `--help`) — no m4a/mp4/mov/aiff. `WHISPERCPP_EXTENSIONS` in `config.py` is the intersection with this server's `ALLOWED_EXTENSIONS`: wav, mp3, flac. ffmpeg-based transcoding for the others is an explicit, not-yet-implemented follow-on (see TODO.md).
- **whisper-cli ships no models.** `brew install whisper-cpp` installs the binary only — GGML `.bin` model files must be downloaded separately (e.g. from https://huggingface.co/ggerganov/whisper.cpp) into `MACWHISPER_WHISPERCPP_MODEL_DIR`. The server never downloads them itself (no-network-calls invariant, see "Things to NOT do").

## Conventions

- Formatting: `ruff format` (line length 100, target `py313`)
- Linting: `ruff check` with `E, F, W, I, B, UP, SIM, RUF`
- Tests: `pytest` with `pytest-mock`. Mock `subprocess.Popen` at `macwhisper_mcp.engines.subprocess.Popen` (both MacWhisper and whisper-cpp engines run through `engines.py` since the v1.2 split — `transcribe.py` no longer calls `Popen` directly) and `subprocess.run` at `macwhisper_mcp.server.subprocess.run` / `macwhisper_mcp.watcher.subprocess.run` — always at the module that uses it, never at stdlib level. Module-level constants imported via `from .config import X` are a *separate* binding per importing module (Python copies the name, not a shared reference) — e.g. `MAX_OUTPUT_BYTES` must be patched at `macwhisper_mcp.engines.MAX_OUTPUT_BYTES`, patching it on `transcribe` has no effect since that module doesn't read it anymore.
- Commit style: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- When adding an MCP tool: define it inside `build_server()` so it closes over `config`. Always wrap user-facing errors in `TranscribeError` (or a new domain exception) — raw stdlib exceptions leak implementation details.
- After any user-facing change, bump the version (semver patch/minor) and run `/release`.
- **Live test logging protocol.** Any end-to-end test against the running server — synthetic client, Claude Desktop, future smoke-test script, anything — gets a new entry appended to [`docs/live-tests.md`](./docs/live-tests.md). One entry per distinct run. Do not overwrite old entries; they are the regression record.

## Things to NOT do

- Do not add cloud fallback, telemetry, or any network call from the server process. Privacy is a hard requirement (PRD §7).
- Do not introduce `shell=True`, `os.system`, or string-based subprocess commands anywhere.
- Do not widen the default allow-list beyond `~/Desktop`. Users opt in per directory via env.
- Do not bump `fastmcp` to a new minor version without reading their upgrade notes and re-running the MCP handshake test.
- Do not commit `.env`, fixture audio files, or anything in `~/Library/Logs/`.
