"""MCP wrapper for Customer lookup."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import selection_directive
from ...contracts.masters.resolution import (
	CustomerResolutionOutput,
	CustomerResolutionResult,
	CustomerSearchOutput,
	CustomerSearchResultContract,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters.customer import (
	confirm_customer as _confirm_customer,
	prepare_customer as _prepare_customer,
	resolve_customer_for_workflow as _resolve_customer_for_workflow,
	search_customers as _search_customers,
)


_resolution_adapter = TypeAdapter(CustomerResolutionResult)
_search_adapter = TypeAdapter(CustomerSearchResultContract)


def _with_selection_interaction(result: dict[str, Any]) -> dict[str, Any]:
	"""Add semantic selection guidance without changing resolver business payloads."""
	if result.get("status") != "ambiguous":
		return result
	return {**result, "interaction": selection_directive().model_dump(mode="json")}


def search_customers(query: NonEmptyString, ctx: Context) -> CustomerSearchOutput:
	"""Find permitted active Customers with explicit candidate references."""
	result = execute_tool_with_context(ctx, "search_customers", lambda: _search_customers(query))
	return CustomerSearchOutput(root=_search_adapter.validate_python(_with_selection_interaction(result)))


def resolve_customer(query: NonEmptyString, ctx: Context) -> CustomerResolutionOutput:
	"""Resolve one permitted Customer or return a terminal selection state."""
	result = execute_tool_with_context(
		ctx, "resolve_customer", lambda: _resolve_customer_for_workflow(query)
	)
	return CustomerResolutionOutput(root=_resolution_adapter.validate_python(_with_selection_interaction(result)))


def register_customer_tools(mcp: Any) -> None:
	"""Register narrow Customer resolution and two-phase creation tools."""

	mcp.tool(meta=tool_meta("search_customers"), structured_output=True)(search_customers)

	mcp.tool(meta=tool_meta("resolve_customer"), structured_output=True)(resolve_customer)

	@mcp.tool(meta=tool_meta("prepare_customer"))
	def prepare_customer(customer: dict[str, Any], ctx: Context) -> dict[str, Any]:
		"""Validate a new Customer and return a private confirmation token without writing."""
		return execute_tool_with_context(ctx, "prepare_customer", lambda: _prepare_customer(customer))

	@mcp.tool(meta=tool_meta("confirm_customer"))
	def confirm_customer(approval_token: str, confirm: bool, ctx: Context) -> dict[str, Any]:
		"""Create a prepared Customer only after explicit confirmation."""
		return execute_tool_with_context(
			ctx, "confirm_customer", lambda: _confirm_customer(approval_token, confirm)
		)
