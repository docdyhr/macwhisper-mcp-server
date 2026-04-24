#!/usr/bin/env python3
"""End-to-end smoke test for the macwhisper MCP server.

Spawns the server as a subprocess, runs the full MCP handshake, calls
transcribe_audio, and prints the transcript. Use this to verify the
server works against a real audio file without opening Claude Desktop.

Usage:
    python scripts/smoke_test.py <audio-file>
    python scripts/smoke_test.py ~/Downloads/Test.m4a

Exit 0 on success, 1 on any failure.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def run(audio_path: Path) -> None:
    server_params = StdioServerParameters(
        command=str(Path(__file__).parent.parent / ".venv" / "bin" / "macwhisper-mcp"),
        args=[],
        env={
            "MACWHISPER_ALLOWED_PATHS": str(audio_path.parent.resolve()),
        },
    )

    print(f"Server : {server_params.command}")
    print(f"File   : {audio_path.resolve()}")
    print()

    async with stdio_client(server_params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = await session.list_tools()
        tool_names = [t.name for t in tools.tools]
        print(f"Tools  : {', '.join(tool_names)}")

        t0 = time.perf_counter()
        result = await session.call_tool("transcribe_audio", {"path": str(audio_path.resolve())})
        elapsed = time.perf_counter() - t0

        if result.isError:
            print(f"\nERROR  : {result.content}")
            sys.exit(1)

        transcript = result.content[0].text if result.content else ""
        print(f"Time   : {elapsed:.2f}s")
        print(f"Chars  : {len(transcript)}")
        print()
        print("--- transcript ---")
        print(transcript)
        print("------------------")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/smoke_test.py <audio-file>", file=sys.stderr)
        sys.exit(1)

    audio_path = Path(sys.argv[1]).expanduser().resolve()
    if not audio_path.exists():
        print(f"File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run(audio_path))


if __name__ == "__main__":
    main()
