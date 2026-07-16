"""macwhisper-mcp-server — local MCP server exposing MacWhisper transcription."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

try:
    # Single source of truth: the installed distribution metadata, which is set
    # from pyproject.toml at build/install time. Avoids a hardcoded literal that
    # drifts from pyproject on every semantic-release bump.
    __version__ = _dist_version("macwhisper-mcp-server")
except PackageNotFoundError:  # running from a source checkout that isn't installed
    __version__ = "0.0.0.dev0"

del _dist_version, PackageNotFoundError
