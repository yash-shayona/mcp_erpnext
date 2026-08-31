"""MCP wrapper for Customer lookup."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from ...runtime import execute_tool_with_context
from ...services.masters.customer import (
	confirm_customer as _confirm_customer,
	prepare_customer as _prepare_customer,
	resolve_customer_for_workflow as _resolve_customer_for_workflow,
	search_customers as _search_customers,
)


def register_customer_tools(mcp: Any) -> None:
	"""Register narrow Customer resolution and two-phase creation tools."""

	@mcp.tool()
	def search_customers(query: str, ctx: Context) -> dict[str, Any]:
		"""Find permitted, active ERPNext customers matching a name or identifier."""
		return execute_tool_with_context(ctx, "search_customers", lambda: _search_customers(query))

	@mcp.tool()
	def resolve_customer(query: str, ctx: Context) -> dict[str, Any]:
		"""Resolve one permitted Customer or return a selection/creation state."""
		return execute_tool_with_context(ctx, "resolve_customer", lambda: _resolve_customer_for_workflow(query))

	@mcp.tool()
	def prepare_customer(customer: dict[str, Any], ctx: Context) -> dict[str, Any]:
		"""Validate a new Customer and return a private confirmation token without writing."""
		return execute_tool_with_context(ctx, "prepare_customer", lambda: _prepare_customer(customer))

	@mcp.tool()
	def confirm_customer(approval_token: str, confirm: bool, ctx: Context) -> dict[str, Any]:
		"""Create a prepared Customer only after explicit confirmation."""
		return execute_tool_with_context(
			ctx, "confirm_customer", lambda: _confirm_customer(approval_token, confirm)
		)
