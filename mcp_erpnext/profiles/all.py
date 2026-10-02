"""Deliberate, deduplicated union inventory for the bounded all MCP profile."""

from __future__ import annotations
from typing import Any


def register_all_profile(mcp: Any) -> None:
    """Register only the currently approved Sales, Purchase, and Accounts union."""
    from ..tools.accounts.customer_payment_entry import (
        register_customer_payment_entry_tools,
    )
    from ..tools.accounts.customer_payment_reconciliation import (
        register_customer_payment_reconciliation_tools,
    )
    from ..tools.accounts.multi_invoice_customer_receipt import (
        register_multi_invoice_customer_receipt_tools,
    )
    from ..tools.accounts.payment_entry_read import register_payment_entry_read_tools
    from ..tools.accounts.sales_invoice_payment import (
        register_sales_invoice_payment_tools,
    )
    from ..tools.accounts.sales_order_advance_payment import (
        register_sales_order_advance_payment_tools,
    )
    from ..tools.buying.purchase_order import register_purchase_order_tools
    from ..tools.buying.purchase_receipt import register_purchase_receipt_tools
    from ..tools.buying.purchase_receipt_read import (
        register_purchase_receipt_read_tools,
    )
    from ..tools.email import register_document_email_tools
    from ..tools.lifecycle import register_lifecycle_tools
    from ..tools.masters.customer_read import register_customer_read_tools
    from ..tools.masters.item import register_all_item_tools
    from ..tools.masters.item_read import register_item_read_tools
    from ..tools.masters.selection import register_selection_tools
    from ..tools.masters.supplier import register_supplier_tools
    from ..tools.masters.supplier_read import register_supplier_read_tools
    from ..tools.buying.purchase_order_read import register_purchase_order_read_tools
    from ..tools.pdf import register_document_pdf_tools
    from ..tools.read import register_purchase_read_tools
    from ..tools.selling.delivery_note_read import register_delivery_note_read_tools
    from ..tools.selling.quotation_read import register_quotation_read_tools
    from ..tools.selling.sales_invoice_read import register_sales_invoice_read_tools
    from ..tools.selling.sales_order_read import register_sales_order_read_tools
    from ..tools.shayona import register_shayona_tools
    from .sales import register_sales_profile_tools

    register_sales_profile_tools(mcp, shared_item_profile="all")
    register_supplier_tools(mcp)
    register_supplier_read_tools(mcp)
    register_purchase_order_tools(mcp)
    register_purchase_receipt_tools(mcp)
    register_purchase_receipt_read_tools(mcp)
    from ..tools.buying.terms import register_buying_terms_tools

    register_buying_terms_tools(mcp)
    register_purchase_order_read_tools(mcp)
    register_sales_invoice_payment_tools(mcp)
    register_multi_invoice_customer_receipt_tools(mcp)
    register_customer_payment_entry_tools(mcp)
    register_sales_order_advance_payment_tools(mcp)
    register_customer_payment_reconciliation_tools(mcp)
    register_payment_entry_read_tools(mcp)
    register_all_item_tools(mcp)
    register_selection_tools(mcp, profile="all")
    register_lifecycle_tools(mcp, "all")
    register_sales_order_read_tools(mcp)
    register_customer_read_tools(mcp)
    register_item_read_tools(mcp)
    register_quotation_read_tools(mcp)
    register_sales_invoice_read_tools(mcp)
    register_delivery_note_read_tools(mcp)
    register_purchase_read_tools(mcp)
    register_document_pdf_tools(mcp, "all")
    register_document_email_tools(mcp, "all")
    register_shayona_tools(mcp)
