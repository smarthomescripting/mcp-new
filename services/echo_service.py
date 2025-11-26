"""Echo service for MCP."""
from __future__ import annotations

from fastmcp import FastMCP

from mcp_framework import log_interaction


def register_echo_service(mcp: FastMCP) -> None:
    """Register a simple echo tool that returns the provided text."""

    @mcp.tool()
    def echo(message: str) -> dict[str, str]:
        """Return the same message that was provided."""

        response = {"echo": message}
        log_interaction("echo", {"message": message}, response)
        return response
