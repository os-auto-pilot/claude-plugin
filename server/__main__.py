"""Entry point for the Oniesoft MCP server.

Run as a module:  python -m server      (from the plugin root)
or directly:      python server/__main__.py

Speaks MCP over stdio, which is how Claude Code's bundled-plugin MCP launcher
connects to it.
"""

from __future__ import annotations

import os
import sys

# Allow running as a loose script (python server/__main__.py) by making the
# parent directory importable so `from server import ...` style works either way.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server.tools import mcp  # type: ignore
else:
    from .tools import mcp


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
