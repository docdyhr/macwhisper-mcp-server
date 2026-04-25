# Product Requirements Document — MacWhisper MCP Server

**Status:** Draft
**Owner:** Thomas
**Last updated:** 2026-04-25

---

## 1. Problem

Transcribing audio locally with MacWhisper produces high-quality output (especially for Danish), but the workflow is disconnected from the LLM tools where the transcript is actually useful. Today: record → open MacWhisper → copy transcript → paste into Claude → prompt for summary/structure. This is manual, slow, and breaks the reasoning loop.

## 2. Goal

Expose MacWhisper as a local MCP tool so Claude Desktop can transcribe audio and post-process the result (summarize, structure, extract facts) in a single conversation — without data leaving the machine.

**Outcome:** `Transcribe ~/Desktop/memo.m4a and give me a Danish summary with action items` becomes one message instead of a five-step manual workflow.

## 3. Non-goals

- Cloud transcription or remote hosting
- Replacing MacWhisper's UI (it remains the engine; this is a thin wrapper)
- Supporting non-macOS platforms (MacWhisper is macOS-only)
- Real-time / streaming transcription (batch files only, v1)
- Multi-user / shared server deployment

## 4. Users

Primary: the author (personal productivity tool).
Secondary: other macOS MacWhisper licensees who use Claude Desktop and want a private transcription pipeline.

## 5. Use cases

1. **Meeting memo** — transcribe a recorded meeting, get a structured summary with decisions and action items.
2. **Danish voice note** — transcribe a Danish dictation, translate or summarize in English.
3. **Interview / research** — transcribe long-form audio, extract quotes, build notes.
4. **Legal / documentation** — transcribe a recorded statement, produce a structured transcript with timestamps (future).

## 6. Functional requirements

### Must have (v1)
- [F1] MCP tool `transcribe_audio(path: str) -> str` that accepts a local file path and returns the transcript as text.
- [F2] Path allow-list: only paths within configured directories (default `~/Desktop`, `~/Transcriptions`) are accepted; all others return an access-denied error.
- [F3] Configurable via environment variables (see `.env.example`).
- [F4] Stdio transport for local Claude Desktop use.
- [F5] Clear error messages for: missing `mw` CLI, missing file, denied path, transcription failure. Denied-path errors must name the configured allow-list directories and, where applicable, guide the user to save the file locally (e.g. when a Claude-container path is detected).

### Should have (v1.1)
- [F6] MCP tool `transcribe_and_summarize(path: str, language: str = "en") -> dict` — transcribe + let Claude summarize (server just returns transcript; Claude handles summarization).
- [F7] Tool `list_allowed_paths() -> list[str]` so Claude can tell the user where it's allowed to read from.
- [F8] Optional file-extension allow-list (`.m4a`, `.mp3`, `.wav`, `.mp4`, `.mov`).

### Nice to have (v2+)
- [F9] Structured output (JSON with segments, timestamps, speaker labels if MacWhisper supports them).
- [F10] Watch-folder mode: auto-transcribe new files in a given directory.
- [F11] Language selection passed through to `mw` CLI.

## 7. Non-functional requirements

- **Privacy:** all processing local; no network calls from the server itself.
- **Security:** no shell injection (never pass user input through a shell; always use `subprocess.run` with a list argv). Path traversal blocked via `Path.resolve()` + prefix check.
- **Performance:** server startup < 1s. Transcription time is bounded by MacWhisper itself.
- **Reliability:** server should not crash on bad input — all errors caught and returned as MCP tool errors.
- **Observability:** log to file (not stdout — stdio is reserved for MCP protocol). Default log path `~/Library/Logs/macwhisper-mcp.log`.

## 8. Architecture

```
Claude Desktop
    ↓ MCP (stdio, JSON-RPC)
macwhisper-mcp-server (Python, fastmcp)
    ↓ subprocess (argv list, no shell)
mw CLI (MacWhisper)
    ↓
Transcript (stdout) → Claude
```

**Stack:**
- Python 3.13.13 (managed by pyenv)
- `fastmcp==3.2.4` (pinned; FastMCP uses semver with breaking changes possible in minor releases)
- stdlib only for everything else (`subprocess`, `pathlib`, `os`)

## 9. Success criteria

- [ ] Claude Desktop can call `transcribe_audio` on a file in `~/Desktop` and receive the transcript.
- [ ] A path outside the allow-list is rejected with a clear error.
- [ ] Danish audio transcription quality matches the MacWhisper app directly (it should — same engine).
- [ ] Full round-trip (record → transcribe → summarize in Claude) under 2 minutes for a 5-minute audio file.
- [ ] Zero crashes across 20 consecutive transcriptions during dogfooding.

## 10. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `mw` CLI breaks on MacWhisper update | Medium | High | Pin MacWhisper version; document tested version in README |
| fastmcp 3.x breaking changes | Medium | Medium | Pin exact version; test upgrades in branch |
| Path allow-list bypassed via symlink | Low | High | Resolve symlinks with `Path.resolve(strict=True)` before prefix check |
| Large audio files exceed MCP response size | Low | Medium | Return transcript as file reference if > N chars (v2) |
| Claude Desktop loses connection mid-transcription | Low | Low | MCP handles reconnect; log and move on |

## 11. Open questions

### `mw` CLI capabilities (investigated 2026-04-24)

`mw transcribe <file>` supports the following flags:

| Flag | Effect |
|------|--------|
| `--model <id>` | Override the active model. ID format: `engine:model-id` (e.g. `whisperkit:openai_whisper-large-v3-v20240930`). |
| `--stream` | Emit transcript segments to stdout as they finalise rather than all at once. Same plain-text format — no timestamps, no JSON. |
| `--persist` | Save the transcription to MacWhisper's internal history. |

**No JSON output. No SRT output. No timestamps.** Structured output (segments with start/end times, speaker labels) is not available via the CLI as of v0.3.0. Achieving it would require parsing MacWhisper's internal SQLite database directly — out of scope for now.

`--stream` is intentionally **not** used: our wrapper reads `stdout` after the process exits (`capture_output=True`), which is simpler and avoids the streaming-parse complexity. See `CLAUDE.md` quirks.

### Remaining open questions

- ~~Should we expose a `cancel_transcription` tool for long-running jobs?~~ **Resolved:** `cancel_transcription()` implemented in v0.4.0 — kills the running subprocess.
- ~~How to handle concurrent transcription requests — queue or reject?~~ **Resolved:** reject strategy via `threading.Lock` in v0.4.0.

## 12. Known limitations (engine-level, not fixable in this wrapper)

- **Uploaded files in Claude Desktop.** Files dragged into the Claude chat window are placed in Claude's sandboxed container (a path outside the user's home directory). The MacWhisper CLI runs on the host Mac and cannot reach container paths. The `transcribe_audio` tool will return an access-denied error and instruct the user to save the file to Desktop, Downloads, or another allow-listed directory before retrying. Claude is also directed in the tool schema not to attempt alternative transcription methods (model download, external API) in this case.

- **Danish letter-name transliteration.** When a speaker *names* the special Danish letters ("æ, ø, å"), Whisper tends to transliterate them to their closest Latin-alphabet equivalents (`E, Y, U` or similar) rather than writing the actual characters. Letters appearing *inside* words are transcribed correctly — e.g. `Blåbærgrød` renders with both `å` and `æ`. This is a MacWhisper/Whisper model behavior; document it in the README so users don't file it as a bug.
