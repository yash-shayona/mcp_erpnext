"""MCP tool registrations.

Tool wrappers belong here; business rules remain in ``services`` so a future
HTTP or Frappe API transport can reuse the same workflow safely.
"""

from __future__ import annotations

from typing import Any

from ..settings import MCPProfile


def register_tools(mcp: Any, profile: MCPProfile | str = MCPProfile.SALES) -> None:
    """Register exactly one domain profile's public MCP inventory."""
    profile = MCPProfile(profile)
    if profile == MCPProfile.SALES:
        from ..profiles.sales import register_sales_profile

        register_sales_profile(mcp)
        return
    if profile == MCPProfile.PURCHASE:
        from ..profiles.purchase import register_purchase_profile

        register_purchase_profile(mcp)
        return
    raise RuntimeError("MCP_PROFILE must be either 'sales' or 'purchase'.")


def register_sales_tools(mcp: Any) -> None:
    """Backward-compatible Sales registration entrypoint for static callers."""
    from .masters.customer import register_customer_tools
    from .masters.item import register_item_tools
    from .masters.selection import register_selection_tools
    from .selling.quotation import register_quotation_tools
    from .selling.quotation_to_sales_order import (
        register_quotation_to_sales_order_tools,
    )
    from .selling.sales_order import register_sales_order_tools
    from .selling.sales_order_to_sales_invoice import (
        register_sales_order_to_sales_invoice_tools,
    )
    from .selling.sales_invoice import register_sales_invoice_tools
    from .selling.delivery_note import register_delivery_note_tools
    from .selling.delivery_note_to_sales_invoice import (
        register_delivery_note_to_sales_invoice_tools,
    )

    register_customer_tools(mcp)
    register_item_tools(mcp)
    register_selection_tools(mcp)
    register_sales_order_tools(mcp)
    register_quotation_tools(mcp)
    register_quotation_to_sales_order_tools(mcp)
    register_sales_order_to_sales_invoice_tools(mcp)
    register_sales_invoice_tools(mcp)
    register_delivery_note_tools(mcp)
    register_delivery_note_to_sales_invoice_tools(mcp)
