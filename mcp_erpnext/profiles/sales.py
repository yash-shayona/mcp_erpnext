"""Public tool inventory for the Sales MCP profile."""

from __future__ import annotations

from typing import Any


def register_sales_profile_tools(
    mcp: Any, shared_item_profile: str | None = None
) -> None:
    """Register Sales authoring tools, optionally reserving shared Item names."""
    from ..tools import register_sales_tools

    if shared_item_profile is None:
        register_sales_tools(mcp)
        return
    from ..tools.masters.contact import register_contact_tools
    from ..tools.masters.customer import register_customer_tools
    from ..tools.masters.customer_contact import register_customer_contact_tools
    from ..tools.selling.quotation import register_quotation_tools
    from ..tools.selling.terms import register_terms_tools
    from ..tools.selling.payment_terms import register_payment_terms_tools
    from ..tools.selling.quotation_to_sales_order import (
        register_quotation_to_sales_order_tools,
    )
    from ..tools.selling.sales_order import register_sales_order_tools
    from ..tools.selling.sales_order_to_sales_invoice import (
        register_sales_order_to_sales_invoice_tools,
    )
    from ..tools.selling.sales_invoice import register_sales_invoice_tools
    from ..tools.selling.delivery_note import register_delivery_note_tools
    from ..tools.selling.delivery_note_to_sales_invoice import (
        register_delivery_note_to_sales_invoice_tools,
    )
    from ..tools.selling.sales_invoice_to_delivery_note import (
        register_sales_invoice_to_delivery_note_tools,
    )

    register_customer_tools(mcp)
    register_customer_contact_tools(mcp)
    register_contact_tools(mcp)
    register_terms_tools(mcp)
    register_payment_terms_tools(mcp)
    register_sales_order_tools(mcp)
    register_quotation_tools(mcp)
    register_quotation_to_sales_order_tools(mcp)
    register_sales_order_to_sales_invoice_tools(mcp)
    register_sales_invoice_tools(mcp)
    register_delivery_note_tools(mcp)
    register_sales_invoice_to_delivery_note_tools(mcp)
    register_delivery_note_to_sales_invoice_tools(mcp)


def register_sales_profile(mcp: Any) -> None:
    """Register the existing Sales capability set without Purchase tools."""
    register_sales_profile_tools(mcp)
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
    from ..tools.selling.delivery_note_read import register_delivery_note_read_tools

    register_delivery_note_read_tools(mcp)
    from ..tools.pdf import register_document_pdf_tools

    register_document_pdf_tools(mcp, "sales")
    from ..tools.email import register_document_email_tools

    register_document_email_tools(mcp, "sales")
