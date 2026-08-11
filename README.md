<div align="right">

<a href="https://railway.com?referralCode=QhjuBc">

  <img width="160" src="https://raw.githubusercontent.com/docdyhr/.github/main/assets/railway-corner-v2@2x.png" alt="Deploy on Railway — $20 free credits">

</a>

</div>

# macwhisper-mcp-server
<!-- mcp-name: io.github.docdyhr/macwhisper-mcp-server -->

Local MCP server that connects [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) to [Claude Desktop](https://claude.ai/download).

**What it does:** Drop an audio file on your Desktop, then ask Claude to transcribe it, summarise it, or pull out action items — in one step. MacWhisper does the transcription on your Mac; Claude does the thinking. Nothing leaves your machine. No cloud APIs. No data ever leaves your Mac.

```
Audio file  →  MacWhisper CLI  →  MCP server  →  Claude Desktop
```

[![CI](https://github.com/docdyhr/macwhisper-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/docdyhr/macwhisper-mcp-server/actions/workflows/ci.yml)
[![CodeQL](https://github.com/docdyhr/macwhisper-mcp-server/actions/workflows/codeql.yml/badge.svg)](https://github.com/docdyhr/macwhisper-mcp-server/actions/workflows/codeql.yml)
[![PyPI version](https://img.shields.io/pypi/v/macwhisper-mcp-server)](https://pypi.org/project/macwhisper-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

![Claude Desktop transcribing an audio file](images/MacWhisper-MCP-server.png)

---

## Requirements

- macOS (MacWhisper is macOS-only)
- [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) — installed and licensed
- MacWhisper CLI enabled: open MacWhisper → Settings → Advanced → Command-Line Tool → Install. This places `mw` at `/usr/local/bin/mw`.
- Python 3.13.x via [pyenv](https://github.com/pyenv/pyenv)
- [Claude Desktop](https://claude.ai/download)

**Installing MacWhisper via Homebrew:**
```bash
brew install --cask macwhisper
```
After installation, enable the CLI in MacWhisper Settings as above. When you later run `brew upgrade --cask macwhisper`, the CLI symlink updates automatically — no re-install needed.

---

## Install

### Option A — Homebrew (recommended)

```bash
brew tap docdyhr/tap
brew install docdyhr/tap/macwhisper-mcp-server
```

This installs the `macwhisper-mcp` binary into your Homebrew prefix. Upgrade later with `brew upgrade docdyhr/tap/macwhisper-mcp-server`.

### Option B — pip / source

```bash
pip install macwhisper-mcp-server
```

Or from source:

```bash
git clone https://github.com/docdyhr/macwhisper-mcp-server.git
cd macwhisper-mcp-server

pyenv install 3.13.13   # skip if already installed
pyenv local 3.13.13
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify the MacWhisper CLI is reachable:

```bash
mw version
```

---

## Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "macwhisper": {
      "command": "macwhisper-mcp",
      "args": [],
      "env": {
        "MACWHISPER_ALLOWED_PATHS": "~/Desktop:~/Downloads",
        "FASTMCP_CHECK_FOR_UPDATES": "off"
      }
    }
  }
}
```

Restart Claude Desktop.

> **Note:** Audio files must be saved to your Mac's filesystem (Desktop, Downloads, or another allow-listed folder) before asking Claude to transcribe them. Files uploaded directly to the Claude chat window live in Claude's container and are not accessible to the local MacWhisper CLI.

### Verify it works

In Claude Desktop, ask:

> Transcribe ~/Desktop/memo.m4a

You should see a `transcribe_audio` tool call appear, followed by the transcript.

---

## Available tools

| Tool | Description |
|------|-------------|
| `transcribe_audio(path, model?, language?, persist?, engine?)` | Transcribe an audio file and return the transcript as plain text. `language` is an ISO 639-1 code (e.g. `da`) or `auto`; overrides any per-directory default. `persist=true` saves to MacWhisper history (MacWhisper engine only). `engine` is `"macwhisper"` (default) or `"whisper-cpp"` — see [Alternative engine](#alternative-engine-whispercpp) below. |
| `list_models()` | List transcription models installed in MacWhisper, plus whisper-cpp models if `MACWHISPER_WHISPERCPP_MODEL_DIR` is configured; active MacWhisper model is marked |
| `cancel_transcription()` | Cancel the currently running transcription |
| `list_allowed_paths()` | Return the directories the server is allowed to read from |
| `start_watch(folder)` | Watch a folder and auto-transcribe new audio files into `../done/` |
| `stop_watch()` | Stop the active folder watcher |
| `get_watch_results()` | Return completed watch-folder transcriptions and clear the queue |

Supported audio formats: `.m4a` `.mp3` `.mp4` `.mov` `.wav` `.aiff` `.flac`

---

## Configuration

All configuration is via environment variables. Pass them through the `env` dict in `claude_desktop_config.json` (for Claude Desktop) or set them in `.env` for local development.

| Env var | Default | Description |
|---------|---------|-------------|
| `MACWHISPER_ALLOWED_PATHS` | `~/Desktop` | Colon-separated list of directories the server may read from |
| `MACWHISPER_CLI` | auto-detected | Path to the `mw` binary. Defaults to `/Applications/MacWhisper.app/Contents/MacOS/mw` if that file exists, otherwise `mw` on `PATH` |
| `MACWHISPER_LOG_PATH` | `~/Library/Logs/macwhisper-mcp.log` | Log file path (never stdout — that's reserved for MCP) |
| `MACWHISPER_LANGUAGE_DEFAULTS` | none | Colon-separated `dir=lang` pairs (ISO 639-1, or `auto`) — files in a matching directory get `--language` automatically. Most specific directory wins; an explicit `language` argument always overrides. |
| `MACWHISPER_WHISPERCPP_BINARY` | `whisper-cli` on `PATH` | Path to the `whisper-cli` binary, if not on `PATH`. Only used when `engine="whisper-cpp"`. |
| `MACWHISPER_WHISPERCPP_MODEL_DIR` | none | Directory containing your GGML `.bin` model files. Required to use `engine="whisper-cpp"` at all — see below. |

**Local development:** copy `.env.example` to `.env` and adjust. With [direnv](https://direnv.net/), `.envrc` exports `.env` automatically. Without direnv: `source .env`.

### Per-directory language defaults

If you regularly transcribe recordings in a specific language, map a subfolder to
it instead of passing `language` on every call:

```json
"MACWHISPER_LANGUAGE_DEFAULTS": "~/Desktop/DK=da:~/Desktop/DE=de"
```

Drop a file in `~/Desktop/DK/` and `transcribe_audio` passes `--language da`
automatically. An explicit `language` argument on the tool call always wins over
the directory default.

### Alternative engine: whisper.cpp

`transcribe_audio(..., engine="whisper-cpp")` transcribes using a standalone
[whisper.cpp](https://github.com/ggml-org/whisper.cpp) binary instead of
MacWhisper — useful if you don't have a MacWhisper license, or want a fully
open-source local path. It does not touch MacWhisper in any way.

**Setup:**

```bash
brew install whisper-cpp
```

Homebrew installs the `whisper-cli` binary only — no models. Download a GGML
model yourself (this server never downloads anything over the network) from
[huggingface.co/ggerganov/whisper.cpp](https://huggingface.co/ggerganov/whisper.cpp/tree/main),
e.g. `ggml-base.en.bin`, into a directory of your choice, then point the server at it:

```json
"MACWHISPER_WHISPERCPP_MODEL_DIR": "~/whisper-models"
```

Then call the tool with the model's filename (not a MacWhisper `engine:model-id`
string):

> Transcribe ~/Desktop/memo.wav using the whisper-cpp engine with model ggml-base.en.bin

**Limitations (v1):**
- Input formats: `.wav`, `.mp3`, `.flac` only — not `.m4a`/`.mp4`/`.mov`/`.aiff`. This
  is whisper.cpp's own native format support; convert other formats first (e.g. with
  `ffmpeg`) or use the default MacWhisper engine, which handles all supported formats.
- `persist=true` is not supported — whisper.cpp has no history mechanism.
- Default language is English (`en`) if neither `language` nor a directory default
  is set — unlike MacWhisper, which defers to the app's own language selection.

---

## Development

```bash
source .venv/bin/activate
pip install -e ".[dev]"

# Tests
pytest -q

# Lint + format
ruff check .
ruff format .

# Pre-commit hooks (one-time setup)
pip install pre-commit
pre-commit install

# Smoke-test against a real audio file (server must not be running in Claude Desktop)
python scripts/smoke_test.py ~/Downloads/Test.m4a
```

### Logs

```bash
tail -f ~/Library/Logs/macwhisper-mcp.log
```

---

## Security

- All file paths are resolved (symlinks followed) and checked against the `MACWHISPER_ALLOWED_PATHS` allow-list before anything reaches the CLI.
- `subprocess.run` is always called with an argv list — never `shell=True`.
- No network calls. Ever.

See [PRD §7](./PRD.md) for the full threat model.

---

## Known limitations

- **Uploaded files:** Files dragged into the Claude chat window live in Claude's container and are not accessible to the local MacWhisper CLI. Save the file to your Desktop or Downloads folder (or another allow-listed directory), then ask Claude to transcribe it from there.
- **Danish letter names:** Whisper may phonetically approximate letter names (e.g. "Æ, Ø, Å" → "E, Y, U") when they are spoken in isolation. Letters *inside words* transcribe correctly. This is a Whisper engine limitation, not a bug in this wrapper. See [PRD §12](./PRD.md).
- **Cold-start latency:** First transcription after MacWhisper launches takes ~13s (model load). Subsequent calls are ~2s.

---

## License

MIT — see [LICENSE](./LICENSE).
