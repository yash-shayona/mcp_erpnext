"""MCP adapters for bounded Shayona capabilities."""

from typing import Any

from .credentials import register_shayona_credential_tools
from .credential_email import register_shayona_credential_email_tools
from .tea_entries import register_shayona_tea_entry_tools


def register_shayona_tools(mcp: Any) -> None:
    register_shayona_credential_tools(mcp)
    register_shayona_credential_email_tools(mcp)
    register_shayona_tea_entry_tools(mcp)


__all__ = ["register_shayona_tools"]
