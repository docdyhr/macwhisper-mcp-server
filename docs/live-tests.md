# Live Test Log

Chronological record of end-to-end tests against the running MCP server. Append new entries at the top. Each entry pins down: what was exercised, what environment, what happened, what it proves, and anything surprising worth following up.

Format: `### YYYY-MM-DD — title`.

---

### 2026-08-17 — fastmcp 3.4.7 upgrade validation (stdio handshake, no transcription)

**Exercised:** MCP `initialize` + `notifications/initialized` + `tools/list` over real stdio against `python -m macwhisper_mcp.server` run as a subprocess. Handshake only — no `tools/call`, so no audio and no `mw` invocation. Purpose was to gate the Dependabot bump in PR #19 (`fastmcp==3.4.6` → `==3.4.7`) against invariant #5.

**Environment:**
- Python 3.13.13, repo venv at `.venv/`
- `fastmcp` tested at both `3.4.6` (baseline) and `3.4.7` (candidate), installed via `pip install 'fastmcp==3.4.7'`
- `MACWHISPER_LOG_PATH` pointed at a throwaway file under `~/Library/Logs/` (a scratchpad path under `/private/tmp` is correctly *rejected* by `Config.from_env` — the log path must live under `$HOME`)
- Working tree at `main` (a58a13c), clean

**Result:** ✅ Success on both versions — behaviour identical.

| | fastmcp 3.4.6 | fastmcp 3.4.7 |
|---|---|---|
| `pytest -q` | 96 passed | 96 passed |
| `protocolVersion` | `2025-06-18` | `2025-06-18` |
| `serverInfo` | `macwhisper 3.4.6` | `macwhisper 3.4.7` |
| `tools/list` | 7 tools | 7 tools (same names) |
| stdout purity | clean JSON-RPC only | clean JSON-RPC only |
| `ruff check` / `format --check` | — | All checks passed / 16 files formatted |

Tools declared on both: `cancel_transcription`, `get_watch_results`, `list_allowed_paths`, `list_models`, `start_watch`, `stop_watch`, `transcribe_audio`.

**What this proves:**

| Layer | Status |
|---|---|
| FastMCP 3.4.7 stdio transport | ✅ handshake unchanged from 3.4.6 |
| Tool registration through `build_server()` | ✅ all 7 tools survive the bump |
| Invariant #4 (logs to file, never stdout) | ✅ stdout carried only JSON-RPC; fastmcp's banner went to stderr on both versions |
| Log-path containment check | ✅ `$HOME`-escape rejected with a clear error |

**Observations / follow-ups:**

- **The 3.4.7 release is irrelevant to this server.** Upstream describes it as a single security fix — CIMD `private_key_jwt` assertion audience validation for `OAuthProxy` deployments. This server is stdio-only with no OAuth and no network calls, so none of the changed code is reachable from our path. Low-risk bump.
- **`serverInfo.version` still tracks fastmcp, not us** — now reports `3.4.7`. Same known cosmetic quirk as the 2026-08-11 entries; still fixed by passing `version=__version__` to `FastMCP()`.
- **Editable-install metadata conflicts during the test.** `pip check` reports `macwhisper-mcp-server 1.2.0.dev0 has requirement fastmcp==3.4.6, but you have fastmcp 3.4.7` until `pyproject.toml` is updated. Expected, harmless for the test, resolves when PR #19 merges.
- **Venv restored to `fastmcp==3.4.6`** after the run, since PR #19 was not merged in this session.

**How to reproduce:**

```bash
source .venv/bin/activate
pip install 'fastmcp==3.4.7'
pytest -q
# then drive `python -m macwhisper_mcp.server` over stdio with initialize + tools/list
```

Still no committed harness for this — the script was a one-off. `scripts/smoke_test.py` remains the standing Phase 2 ask (see TODO.md); this entry is the third time a throwaway client has been written from scratch.

---

### 2026-08-11 — First live transcription via the whisper-cpp engine (synthetic MCP client)

**Exercised:** Full pipeline through the new independent backend — `build_server()` → synthetic FastMCP `Client` → `tools/call transcribe_audio` (`engine="whisper-cpp"`) → `transcribe.py` validation → `engines.py::run_whispercpp` → real `whisper-cli` subprocess → transcript returned.

**Environment:**
- `whisper-cpp` 1.9.2 installed via `brew install whisper-cpp` for this session (binary: `whisper-cli`)
- Model: `ggml-tiny.en.bin`, downloaded to a temp dir for this test (not committed, not auto-downloaded by the server — user is expected to provide their own model per `MACWHISPER_WHISPERCPP_MODEL_DIR`)
- Audio: `jfk.wav`, whisper.cpp's own bundled sample (`/opt/homebrew/Cellar/whisper-cpp/1.9.2/share/whisper-cpp/jfk.wav`), copied into a temp allow-listed dir
- `Config(allowed_paths=(<temp audio dir>,), whispercpp_binary="whisper-cli", whispercpp_model_dir=<temp model dir>)`
- All temp files (model, audio copy, log) deleted after the test — nothing committed

**Result:** ✅ Success.

- `is_error: False`
- Wall time: **0.32s** (tiny model, ~11s clip, Apple M3 Max with Metal acceleration — not representative of larger models/clips)
- Transcript: *"And so my fellow Americans ask not what your country can do for you, ask what you can do for your country."* — byte-identical to the raw `whisper-cli -np -nt` invocation used to verify the CLI contract before writing `engines.py` (see PRD §11)

**What this proves:**

| Layer | Status |
|---|---|
| `engine="whisper-cpp"` dispatch in `transcribe.py`/`engines.py` | ✅ real subprocess, not mocked |
| `Config.resolve_whispercpp_model` (symlink-safe model resolution) | ✅ resolved `ggml-tiny.en.bin` correctly from the configured dir |
| `-np -nt` flags produce clean plain-text stdout | ✅ matches the raw CLI verification exactly |
| Path allow-list applies identically to both engines | ✅ same `transcribe.py` validation path as MacWhisper |
| End-to-end via the synthetic MCP client (not just unit-mocked tests) | ✅ first real proof the whisper-cpp engine works through the actual server, not just `pytest` mocks |

**Follow-ups:** None new. Larger models and longer clips will be slower than this 0.32s tiny-model result — not yet measured. ffmpeg transcoding for non-wav/mp3/flac input remains unimplemented (TODO.md backlog).

---

### 2026-04-24 — smoke_test.py against tears_in_rain.wav (English, Blade Runner)

**Exercised:** `scripts/smoke_test.py` — first run of the reusable harness against a real English fixture.

**Environment:**
- `python scripts/smoke_test.py tests/fixtures/tears_in_rain.wav`
- Python 3.13.13, `fastmcp==3.2.4`, CLI auto-detected, allow-list set to fixture parent dir

**Result:** ✅ Success.

- Tools listed: `transcribe_audio`, `list_allowed_paths`
- Time: **1.79s** (warm)
- Chars: **232**
- Transcript:
  > I've seen things you people wouldn't believe.
  > Attack ships on fire off the shoulder of Orion.
  > I watched sea beams glitter in the dark near the Tannhosser Gate.
  > All those moments will be lost in time, like tears in rain.
  > Time to die.

**Known engine quirks (PRD §12):** "C-beams" → "sea beams"; "Tannhäuser" → "Tannhosser". Both are Whisper mishearings, not wrapper bugs.

**What this proves:** `scripts/smoke_test.py` is a working replacement for the `/tmp/` one-off pattern. English transcription clean, timing consistent with prior warm runs.

---

### 2026-04-24 — First live transcription from inside Claude Desktop

**Exercised:** Full user-facing path — Claude Desktop → MCP tool call → `transcribe_audio` → transcript returned inline in Claude Desktop UI.

**Environment:**
- Claude Desktop (macwhisper MCP server wired via `claude_desktop_config.json`)
- Python 3.13.13, `fastmcp==3.2.4`, CLI auto-detected
- Allow-list: `~/Desktop:~/Downloads`
- Audio: `~/Downloads/Test.m4a` — same short Danish voice memo as entries #1/#2

**Result:** ✅ Success.

- Two `CallToolRequest`s logged at 21:26 (first likely `list_allowed_paths`, second `transcribe_audio`).
- Transcription completed in **~1.9s** (warm; consistent with entry #2).
- Transcript (corrected): *"Dette er en test. Blåbærgrød. Blåbærgrød smager godt. Det indeholder også de danske karakterer Æ, Ø og Å. Tak."*
- Note: MacWhisper rendered the Danish letter names as `E, Y og U` (phonetic approximations); corrected to `Æ, Ø og Å` by the user. Consistent with engine-level limitation documented in PRD §12.
- `macwhisper-mcp.log` confirms: `Transcribing /Users/thomas/Downloads/Test.m4a` → `Transcribed 110 chars`.

**What this proves:**

| Layer | Status |
|---|---|
| Claude Desktop MCP tool invocation | ✅ real tool call, not synthetic client |
| `claude_desktop_config.json` env var injection | ✅ allow-list picked up correctly |
| Warm-run latency via Claude Desktop | ✅ ~1.9s, matches synthetic-client warm run |
| File logging from Claude Desktop subprocess | ✅ server log written correctly |

**Phase 1 verdict:** MVP complete. All TODO Phase 1 items checked off.

---

### 2026-04-24 — Warm-run repeat via synthetic MCP client

**Exercised:** Same pipeline as entry #1, rerun shortly after the cold run to measure warm-start latency. Server spawned fresh; MacWhisper app already resident.

**Environment:** Identical to entry #1 (Python 3.13.13, `fastmcp==3.2.4`, CLI auto-detected, allow-list `~/Desktop:~/Downloads`, same audio file).

**Result:** ✅ Success.

- `tools/call transcribe_audio` returned in **1.90s wall time** (vs. 13.6s cold).
- Transcript byte-identical to entry #1 — deterministic as expected for the same input.
- No warnings, clean shutdown.

**What this proves:**

- Cold-start latency on entry #1 was dominated by MacWhisper model load, not by our wrapper or FastMCP. The MCP stack itself adds **negligible** overhead (sub-100ms for initialize + tools/call round-trip on a 10s clip).
- Once MacWhisper is warm, end-to-end latency is gated by model inference speed and audio duration only. For short clips this is effectively interactive.

**Follow-ups:** None new. Same two open items from entry #1 (Danish letter-name quirk, `serverInfo.version` cosmetic) still stand.

---

### 2026-04-24 — First end-to-end Danish transcription via MCP

**Exercised:** Full pipeline — spawn `macwhisper_mcp.server` over stdio → MCP `initialize` → `notifications/initialized` → `tools/call transcribe_audio` → receive transcript → clean shutdown.

**Environment:**
- Python 3.13.13 (`.venv/bin/python`)
- `fastmcp==3.2.4`
- MacWhisper CLI auto-detected at `/Applications/MacWhisper.app/Contents/MacOS/mw`
- Allow-list: `~/Desktop:~/Downloads` (set via `MACWHISPER_ALLOWED_PATHS`)
- Audio: `~/Downloads/Test.m4a` — short Danish voice memo, ~10s

**Result:** ✅ Success.

- `initialize` response: returned in < 1s with correct `protocolVersion` and both tools declared (`transcribe_audio`, `list_allowed_paths`).
- `tools/call transcribe_audio`: returned a populated `content[].text` block with the full transcript in **13.6s wall time** (cold; model load time included).
- Transcript: *"Dette er en test. Blåbærgrød. Blåbærgrød smager godt. Det indeholder også de danske karakterer E, Y og U. Tak."*
- UTF-8 end-to-end: clean. `Blåbærgrød` round-tripped with both `å` and `æ` intact through stdio JSON-RPC.
- No crashes, no warnings, clean terminate.

**What this proves:**

| Layer | Status |
|---|---|
| FastMCP 3.2.4 stdio transport | ✅ multi-turn JSON-RPC works |
| Path allow-list (expanded via env var) | ✅ `~/Downloads` accepted when added; would still block anything outside |
| `subprocess.run` argv-list invocation | ✅ no shell, mw binary resolved correctly |
| Auto-detected CLI path (`config.py` fallback) | ✅ no `MACWHISPER_CLI` env var needed |
| UTF-8 through full pipeline | ✅ Danish diacritics intact |
| Python 3.13.13 + `fastmcp==3.2.4` | ✅ no runtime warnings |

**Observations / follow-ups:**

- **Danish letter-name quirk.** Speaker said the letter *names* `æ, ø, å`; Whisper transliterated them to `E, Y, U`. Inside words the letters transcribe correctly (see `Blåbærgrød`). Documented in PRD §12 as an engine-level limitation. Not a bug in this wrapper.
- **Server `serverInfo.version`** reports `3.2.4` (fastmcp's version) because `FastMCP("macwhisper")` is called without a `version=` argument. Harmless but cosmetically wrong. Low-priority fix: pass `version=macwhisper_mcp.__version__`.
- **Cold-start latency.** ~13s for a 10s clip is dominated by MacWhisper model load/inference, not by our wrapper. Warm runs will likely be faster — worth a second data point.

**How to reproduce:**

```bash
# From repo root, with MacWhisper.app installed and venv ready:
MACWHISPER_ALLOWED_PATHS="$HOME/Desktop:$HOME/Downloads" \
  .venv/bin/python -m macwhisper_mcp.server
# In a second process, drive it with a JSON-RPC client over stdio.
# See tests/ for patterns, or use the one-off script kept at /tmp/mcp_live_transcribe.py.
```

A reusable CLI smoke-test harness would be a good Phase 2 addition — something like `scripts/smoke_test.py <audio-file>` that does the handshake + tool call + prints the transcript. Put it in TODO.md Phase 2 if not already there.
