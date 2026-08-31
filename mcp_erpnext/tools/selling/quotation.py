"""MCP wrappers for the two-phase Draft Quotation workflow."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from ...runtime import execute_tool_with_context
from ...services.selling.quotation import (
	confirm_quotation as _confirm_quotation,
	prepare_quotation as _prepare_quotation,
)


def register_quotation_tools(mcp: Any) -> None:
	"""Register only the explicit Quotation prepare/confirm tools."""

	@mcp.tool()
	def prepare_quotation(
		customer: dict[str, str],
		items: list[dict[str, Any]],
		valid_till: str,
		ctx: Context,
		company: str | None = None,
		transaction_date: str | None = None,
		selling_price_list: str | None = None,
		taxes_and_charges: str | None = None,
		additional_discount_percentage: float | None = None,
		discount_amount: float | None = None,
		tc_name: str | None = None,
	) -> dict[str, Any]:
		"""Prepare an ERPNext-calculated Draft Quotation preview without writing."""
		return execute_tool_with_context(
			ctx,
			"prepare_quotation",
			lambda: _prepare_quotation(
				customer,
				items,
				valid_till,
				company,
				transaction_date,
				selling_price_list,
				taxes_and_charges,
				additional_discount_percentage,
				discount_amount,
				tc_name,
			),
		)

	@mcp.tool()
	def confirm_quotation(approval_token: str, confirm: bool, ctx: Context) -> dict[str, Any]:
		"""Create the prepared Draft Quotation after explicit confirmation."""
		return execute_tool_with_context(
			ctx, "confirm_quotation", lambda: _confirm_quotation(approval_token, confirm)
		)
