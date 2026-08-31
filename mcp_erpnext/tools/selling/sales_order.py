"""MCP wrappers for the two-phase Sales Order workflow."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from ...runtime import execute_tool_with_context
from ...services.selling.sales_order import (
	confirm_sales_order as _confirm_sales_order,
	prepare_sales_order as _prepare_sales_order,
)


def register_sales_order_tools(mcp: Any) -> None:
	"""Register the two public Selling capability tools."""

	@mcp.tool()
	def prepare_sales_order(
		customer: str,
		items: list[dict[str, Any]],
		ctx: Context,
		company: str | None = None,
		delivery_date: str | None = None,
		selling_price_list: str | None = None,
	) -> dict[str, Any]:
		"""Resolve inputs and return a Sales Order preview without writing anything."""
		return execute_tool_with_context(
			ctx,
			"prepare_sales_order",
			lambda: _prepare_sales_order(customer, items, company, delivery_date, selling_price_list),
		)

	@mcp.tool()
	def confirm_sales_order(approval_token: str, confirm: bool, ctx: Context) -> dict[str, Any]:
		"""Create the prepared Draft Sales Order after explicit confirmation."""
		return execute_tool_with_context(
			ctx, "confirm_sales_order", lambda: _confirm_sales_order(approval_token, confirm)
		)
