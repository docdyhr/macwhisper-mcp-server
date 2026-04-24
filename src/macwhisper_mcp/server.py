"""FastMCP server entry point.

Run via `python -m macwhisper_mcp.server` or the `macwhisper-mcp` console script.
Communicates over stdio — do NOT print to stdout anywhere. All logs go to a file.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from .config import Config
from .transcribe import TranscribeError, transcribe


def _setup_logging(config: Config) -> None:
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(config.log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_server(config: Config | None = None) -> FastMCP:
    config = config or Config.from_env()
    _setup_logging(config)
    log = logging.getLogger(__name__)
    log.info("Starting macwhisper-mcp-server, allow-list=%s", config.allowed_paths)

    mcp = FastMCP("macwhisper")

    @mcp.tool()
    def transcribe_audio(path: str, model: str | None = None) -> str:
        """Transcribe a local audio file using MacWhisper and return the transcript.

        Args:
            path: Absolute path to an audio file inside the configured allow-list.
                Supported formats: m4a, mp3, mp4, mov, wav, aiff, flac.
            model: Optional model override in MacWhisper engine:model-id format,
                e.g. "whisperkit:openai_whisper-large-v3-v20240930" or
                "parakeet-pro:nvidia_parakeet-v3_494MB". Defaults to the model
                currently selected in MacWhisper.

        Returns:
            The full transcript as plain text.
        """
        try:
            return transcribe(path, config, model=model)
        except TranscribeError as e:
            log.warning("transcribe_audio failed: %s", e)
            # Re-raise so FastMCP returns a proper tool error to the client.
            raise

    @mcp.tool()
    def list_allowed_paths() -> list[str]:
        """Return the directories this server is allowed to read audio from."""
        return [str(p) for p in config.allowed_paths]

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
