"""Public tool inventory for the Accounts MCP profile."""

from __future__ import annotations

from typing import Any


def register_accounts_profile(mcp: Any) -> None:
    """Register only the V1 customer-payment and Payment Entry lifecycle tools."""
    from ..tools.accounts.sales_invoice_payment import register_sales_invoice_payment_tools
    from ..tools.lifecycle import register_lifecycle_tools

    register_sales_invoice_payment_tools(mcp)
    register_lifecycle_tools(mcp, "accounts")
