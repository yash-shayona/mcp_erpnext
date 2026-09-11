"""Public tool inventory for the Sales MCP profile."""

from __future__ import annotations

from typing import Any


def register_sales_profile(mcp: Any) -> None:
    """Register the existing Sales capability set without Purchase tools."""
    from ..tools import register_sales_tools

    register_sales_tools(mcp)
    from ..tools.lifecycle import register_lifecycle_tools

    register_lifecycle_tools(mcp, "sales")
    from ..tools.selling.sales_order_read import register_sales_order_read_tools

    register_sales_order_read_tools(mcp)
    from ..tools.masters.customer_read import register_customer_read_tools

    register_customer_read_tools(mcp)
    from ..tools.masters.item_read import register_item_read_tools

    register_item_read_tools(mcp)
    from ..tools.selling.quotation_read import register_quotation_read_tools

    register_quotation_read_tools(mcp)
    from ..tools.selling.sales_invoice_read import register_sales_invoice_read_tools

    register_sales_invoice_read_tools(mcp)
    from ..tools.pdf import register_document_pdf_tools

    register_document_pdf_tools(mcp, "sales")
    from ..tools.email import register_document_email_tools

    register_document_email_tools(mcp, "sales")
