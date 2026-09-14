"""MCP wrapper for Customer lookup."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import approval_directive, input_directive, selection_directive
from ...contracts.masters.customer import (
	CustomerConfirmInput,
	CustomerConfirmResult,
	CustomerPrepareInput,
	CustomerPrepareResult,
	ConfirmCustomerOutput,
	PrepareCustomerOutput,
)
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
_prepare_adapter = TypeAdapter(CustomerPrepareResult)


def _with_selection_interaction(result: dict[str, Any]) -> dict[str, Any]:
	"""Add semantic selection guidance without changing resolver business payloads."""
	if result.get("status") != "ambiguous":
		return result
	return {**result, "interaction": selection_directive().model_dump(mode="json")}


def _with_creation_interaction(result: dict[str, Any]) -> dict[str, Any]:
	"""Attach shared continuation guidance to creation states only."""
	if result.get("status") == "ready":
		return {**result, "interaction": approval_directive().model_dump(mode="json")}
	if result.get("status") == "needs_input":
		return {**result, "interaction": input_directive().model_dump(mode="json")}
	if result.get("status") == "needs_selection":
		return {**result, "interaction": selection_directive().model_dump(mode="json")}
	return result


def search_customers(query: NonEmptyString, ctx: Context) -> CustomerSearchOutput:
	"""Find permitted active Customers with explicit candidate references."""
	result = execute_tool_with_context(ctx, "search_customers", lambda: _search_customers(query), rest_arguments={"query": query})
	return CustomerSearchOutput(root=_search_adapter.validate_python(_with_selection_interaction(result)))


def resolve_customer(query: NonEmptyString, ctx: Context) -> CustomerResolutionOutput:
	"""Resolve one permitted Customer or return a terminal selection state."""
	result = execute_tool_with_context(
		ctx, "resolve_customer", lambda: _resolve_customer_for_workflow(query), rest_arguments={"query": query}
	)
	return CustomerResolutionOutput(root=_resolution_adapter.validate_python(_with_selection_interaction(result)))


def prepare_customer(customer: CustomerPrepareInput, ctx: Context) -> PrepareCustomerOutput:
	"""Validate a new Customer and return a private confirmation token without writing."""
	request = CustomerPrepareInput.model_validate(customer)
	result = execute_tool_with_context(
		ctx,
		"prepare_customer",
		lambda: _prepare_customer(request.to_service_payload()),
		rest_arguments=request.model_dump(mode="json"),
	)
	return PrepareCustomerOutput(
		root=_prepare_adapter.validate_python(_with_creation_interaction(result))
	)


def confirm_customer(
	approval_token: NonEmptyString, confirm: bool, ctx: Context
) -> ConfirmCustomerOutput:
	"""Create a prepared Customer only after explicit confirmation."""
	request = CustomerConfirmInput(approval_token=approval_token, confirm=confirm)
	result = execute_tool_with_context(
		ctx,
		"confirm_customer",
		lambda: _confirm_customer(request.approval_token, request.confirm),
		rest_arguments=request.model_dump(mode="json"),
	)
	return ConfirmCustomerOutput(root=TypeAdapter(CustomerConfirmResult).validate_python(result))


def register_customer_tools(mcp: Any) -> None:
	"""Register narrow Customer resolution and two-phase creation tools."""

	mcp.tool(meta=tool_meta("search_customers"), structured_output=True)(search_customers)

	mcp.tool(meta=tool_meta("resolve_customer"), structured_output=True)(resolve_customer)

	mcp.tool(meta=tool_meta("prepare_customer"), structured_output=True)(prepare_customer)
	mcp.tool(meta=tool_meta("confirm_customer"), structured_output=True)(confirm_customer)
