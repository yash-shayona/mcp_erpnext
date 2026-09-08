"""Public tool inventory for the Sales MCP profile."""

from __future__ import annotations

from typing import Any


def register_sales_profile(mcp: Any) -> None:
    """Register the existing Sales capability set without Purchase tools."""
    from ..tools import register_sales_tools

    register_sales_tools(mcp)
    from ..tools.lifecycle import register_lifecycle_tools

    register_lifecycle_tools(mcp, "sales")
    from ..tools.read import register_sales_read_tools

    register_sales_read_tools(mcp)
