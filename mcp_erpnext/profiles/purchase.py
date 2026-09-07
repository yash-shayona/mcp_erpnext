"""Public tool inventory for the Purchase MCP profile."""

from __future__ import annotations

from typing import Any


def register_purchase_profile(mcp: Any) -> None:
    """Register only resolution and Purchase Order capabilities."""
    from ..tools.buying.purchase_order import register_purchase_order_tools
    from ..tools.masters.purchase_item import register_purchase_item_tools
    from ..tools.masters.supplier import register_supplier_tools

    register_supplier_tools(mcp)
    register_purchase_item_tools(mcp)
    register_purchase_order_tools(mcp)
