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
    from ..tools.lifecycle import register_lifecycle_tools

    register_lifecycle_tools(mcp, "purchase")
    from ..tools.read import register_purchase_read_tools

    register_purchase_read_tools(mcp)
    from ..tools.pdf import register_document_pdf_tools

    register_document_pdf_tools(mcp, "purchase")
    from ..tools.email import register_document_email_tools

    register_document_email_tools(mcp, "purchase")
