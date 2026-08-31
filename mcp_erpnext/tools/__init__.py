"""MCP tool registrations.

Tool wrappers belong here; business rules remain in ``services`` so a future
HTTP or Frappe API transport can reuse the same workflow safely.
"""

from __future__ import annotations

from typing import Any


def register_tools(mcp: Any) -> None:
	"""Register all MCP tools on a FastMCP instance."""
	from .masters.customer import register_customer_tools
	from .masters.item import register_item_tools
	from .selling.quotation import register_quotation_tools
	from .selling.sales_order import register_sales_order_tools

	register_customer_tools(mcp)
	register_item_tools(mcp)
	register_sales_order_tools(mcp)
	register_quotation_tools(mcp)
