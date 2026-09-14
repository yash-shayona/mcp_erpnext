"""Public tool inventory for the Accounts MCP profile."""

from __future__ import annotations

from typing import Any


def register_accounts_profile(mcp: Any) -> None:
    """Register only the Accounts customer-payment and Payment Entry tools."""
    from ..tools.accounts.sales_invoice_payment import register_sales_invoice_payment_tools
    from ..tools.accounts.multi_invoice_customer_receipt import register_multi_invoice_customer_receipt_tools
    from ..tools.accounts.customer_payment_entry import register_customer_payment_entry_tools
    from ..tools.accounts.payment_entry_read import register_payment_entry_read_tools
    from ..tools.lifecycle import register_lifecycle_tools

    register_sales_invoice_payment_tools(mcp)
    register_multi_invoice_customer_receipt_tools(mcp)
    register_customer_payment_entry_tools(mcp)
    register_payment_entry_read_tools(mcp)
    register_lifecycle_tools(mcp, "accounts")
