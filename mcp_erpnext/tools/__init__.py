"""MCP tool registrations.

Tool wrappers belong here; business rules remain in ``services`` so a future
HTTP or Frappe API transport can reuse the same workflow safely.
"""

from __future__ import annotations

from typing import Any

from ..settings import MCPProfile
from .registration import GovernedMCP


def register_tools(mcp: Any, profile: MCPProfile | str = MCPProfile.SALES) -> None:
    """Register exactly one domain profile's public MCP inventory."""
    profile = MCPProfile(profile)
    mcp = GovernedMCP(mcp)
    if profile == MCPProfile.SALES:
        from ..profiles.sales import register_sales_profile

        register_sales_profile(mcp)
        return
    if profile == MCPProfile.PURCHASE:
        from ..profiles.purchase import register_purchase_profile

        register_purchase_profile(mcp)
        return
    if profile == MCPProfile.ACCOUNTS:
        from ..profiles.accounts import register_accounts_profile

        register_accounts_profile(mcp)
        return
    raise RuntimeError("MCP_PROFILE must be either 'sales', 'purchase', or 'accounts'.")


def register_sales_tools(mcp: Any) -> None:
    """Backward-compatible Sales registration entrypoint for static callers."""
    from .masters.customer import register_customer_tools
    from .masters.customer_contact import register_customer_contact_tools
    from .masters.contact import register_contact_tools
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
    from .selling.sales_invoice_to_delivery_note import (
        register_sales_invoice_to_delivery_note_tools,
    )

    register_customer_tools(mcp)
    register_customer_contact_tools(mcp)
    register_contact_tools(mcp)
    register_item_tools(mcp)
    register_selection_tools(mcp)
    register_sales_order_tools(mcp)
    register_quotation_tools(mcp)
    register_quotation_to_sales_order_tools(mcp)
    register_sales_order_to_sales_invoice_tools(mcp)
    register_sales_invoice_tools(mcp)
    register_delivery_note_tools(mcp)
    register_sales_invoice_to_delivery_note_tools(mcp)
    register_delivery_note_to_sales_invoice_tools(mcp)
