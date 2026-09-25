"""Source-controlled MCP instruction composition."""

from __future__ import annotations

from .base import BASE_INSTRUCTIONS
from .sales import SALES_INSTRUCTIONS


def get_mcp_instructions(profile: object) -> str:
    """Return common guidance plus real guidance for the selected profile."""
    profile_value = getattr(profile, "value", profile)
    if profile_value == "sales":
        return f"{BASE_INSTRUCTIONS}\n\n{SALES_INSTRUCTIONS}"
    return BASE_INSTRUCTIONS
