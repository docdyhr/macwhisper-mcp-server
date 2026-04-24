# macwhisper-mcp-server

Local MCP server that exposes [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) transcription to Claude Desktop. Audio → MacWhisper → MCP → Claude — fully local, fully private.

## Status

🚧 Early development. See [PRD.md](./PRD.md) and [TODO.md](./TODO.md).

## Requirements

- macOS
- [MacWhisper](https://goodsnooze.gumroad.com/l/macwhisper) installed + licensed, with CLI enabled in settings
- Python 3.13.x (managed with [pyenv](https://github.com/pyenv/pyenv))
- [Claude Desktop](https://claude.ai/download)

## Install

```bash
git clone https://github.com/<you>/macwhisper-mcp-server.git
cd macwhisper-mcp-server

pyenv install 3.13.13   # if not already installed
pyenv local 3.13.13
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify MacWhisper CLI:

```bash
mw --help
```

If `mw` is not found: open MacWhisper → Settings → enable CLI, then confirm `mw` is on your `PATH`.

## Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "macwhisper": {
      "command": "/Users/<you>/Programming/macwhisper-mcp-server/.venv/bin/macwhisper-mcp",
      "args": [],
      "env": {
        "MACWHISPER_ALLOWED_PATHS": "/Users/<you>/Desktop:/Users/<you>/Downloads"
      }
    }
  }
}
```

Restart Claude Desktop. Ask: *"Transcribe ~/Desktop/memo.m4a and summarize in Danish."*

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `MACWHISPER_ALLOWED_PATHS` | `~/Desktop` | Colon-separated directory allow-list |
| `MACWHISPER_CLI` | `mw` | Path to MacWhisper CLI |
| `MACWHISPER_LOG_PATH` | `~/Library/Logs/macwhisper-mcp.log` | Log file path |

**Local development:** copy `.env.example` to `.env` and adjust. If you use [direnv](https://direnv.net/), `.envrc` loads `.env` automatically via `dotenv_if_exists`. Without direnv, run `source .env` before starting the server manually.

**Claude Desktop:** env vars are passed directly via the `env` dict in `claude_desktop_config.json` — `.env` is not read by the server process.

## Development

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check .
```

## Security

- File paths are resolved and checked against an allow-list before any subprocess call.
- `subprocess.run` is invoked with an argv list (never `shell=True`).
- No network calls made by the server itself.

See [PRD §7](./PRD.md) for the full threat model.

## License

MIT — see [LICENSE](./LICENSE).
