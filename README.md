# macwhisper-mcp-server

Local MCP server that exposes [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) transcription to Claude Desktop.

```
Audio file  →  MacWhisper CLI  →  MCP server  →  Claude Desktop
```

Fully local. No cloud. No data leaves your Mac.

[![CI](https://github.com/docdyhr/macwhisper-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/docdyhr/macwhisper-mcp-server/actions/workflows/ci.yml)

---

## Requirements

- macOS (MacWhisper is macOS-only)
- [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) — installed, licensed, CLI enabled in Settings
- Python 3.13.x via [pyenv](https://github.com/pyenv/pyenv)
- [Claude Desktop](https://claude.ai/download)

---

## Install

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
/Applications/MacWhisper.app/Contents/MacOS/mw --help
```

If you get "command not found": open MacWhisper → Settings → enable CLI.

---

## Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "macwhisper": {
      "command": "/Users/<you>/macwhisper-mcp-server/.venv/bin/macwhisper-mcp",
      "args": [],
      "env": {
        "MACWHISPER_ALLOWED_PATHS": "/Users/<you>/Desktop:/Users/<you>/Downloads"
      }
    }
  }
}
```

Replace `<you>` with your macOS username. Restart Claude Desktop.

### Verify it works

In Claude Desktop, ask:

> Transcribe ~/Desktop/memo.m4a

You should see a `transcribe_audio` tool call appear, followed by the transcript.

---

## Available tools

| Tool | Description |
|------|-------------|
| `transcribe_audio(path)` | Transcribe an audio file and return the transcript as plain text |
| `list_allowed_paths()` | Return the directories the server is allowed to read from |

Supported audio formats: `.m4a` `.mp3` `.mp4` `.mov` `.wav` `.aiff` `.flac`

---

## Configuration

All configuration is via environment variables. Pass them through the `env` dict in `claude_desktop_config.json` (for Claude Desktop) or set them in `.env` for local development.

| Env var | Default | Description |
|---------|---------|-------------|
| `MACWHISPER_ALLOWED_PATHS` | `~/Desktop` | Colon-separated list of directories the server may read from |
| `MACWHISPER_CLI` | auto-detected | Path to the `mw` binary. Defaults to `/Applications/MacWhisper.app/Contents/MacOS/mw` if that file exists, otherwise `mw` on `PATH` |
| `MACWHISPER_LOG_PATH` | `~/Library/Logs/macwhisper-mcp.log` | Log file path (never stdout — that's reserved for MCP) |

**Local development:** copy `.env.example` to `.env` and adjust. With [direnv](https://direnv.net/), `.envrc` exports `.env` automatically. Without direnv: `source .env`.

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

- **Danish letter names:** Whisper may phonetically approximate letter names (e.g. "Æ, Ø, Å" → "E, Y, U") when they are spoken in isolation. Letters *inside words* transcribe correctly. This is a Whisper engine limitation, not a bug in this wrapper. See [PRD §12](./PRD.md).
- **Cold-start latency:** First transcription after MacWhisper launches takes ~13s (model load). Subsequent calls are ~2s.

---

## License

MIT — see [LICENSE](./LICENSE).
