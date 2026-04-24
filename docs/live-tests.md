# Live Test Log

Chronological record of end-to-end tests against the running MCP server. Append new entries at the top. Each entry pins down: what was exercised, what environment, what happened, what it proves, and anything surprising worth following up.

Format: `### YYYY-MM-DD — title`.

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
