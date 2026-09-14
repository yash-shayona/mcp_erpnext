"""MCP wrapper for sales-enabled Item lookup."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import approval_directive, input_directive, selection_directive
from ...contracts.masters.item import (
	ConfirmItemOutput,
	ItemConfirmInput,
	ItemConfirmResult,
	ItemPrepareInput,
	ItemPrepareResult,
	PrepareItemOutput,
)
from ...contracts.masters.resolution import (
	ItemResolutionOutput,
	ItemResolutionResult,
	ItemSearchOutput,
	ItemSearchResultContract,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters.item import (
	confirm_item as _confirm_item,
	prepare_item as _prepare_item,
	resolve_item_for_workflow as _resolve_item_for_workflow,
	search_items as _search_items,
)


_resolution_adapter = TypeAdapter(ItemResolutionResult)
_search_adapter = TypeAdapter(ItemSearchResultContract)
_prepare_adapter = TypeAdapter(ItemPrepareResult)
_confirm_adapter = TypeAdapter(ItemConfirmResult)


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


def search_items(query: NonEmptyString, ctx: Context) -> ItemSearchOutput:
	"""Find permitted sales Items with explicit candidate references."""
	result = execute_tool_with_context(ctx, "search_items", lambda: _search_items(query), rest_arguments={"query": query})
	return ItemSearchOutput(root=_search_adapter.validate_python(_with_selection_interaction(result)))


def resolve_item(query: NonEmptyString, ctx: Context) -> ItemResolutionOutput:
	"""Resolve one permitted sales Item or return a terminal selection state."""
	result = execute_tool_with_context(ctx, "resolve_item", lambda: _resolve_item_for_workflow(query), rest_arguments={"query": query})
	return ItemResolutionOutput(root=_resolution_adapter.validate_python(_with_selection_interaction(result)))


def prepare_item(item: ItemPrepareInput, ctx: Context) -> PrepareItemOutput:
	"""Validate a new sales Item and return a private confirmation token without writing."""
	request = ItemPrepareInput.model_validate(item)
	result = execute_tool_with_context(
		ctx, "prepare_item", lambda: _prepare_item(request.to_service_payload()), rest_arguments=request.model_dump(mode="json")
	)
	return PrepareItemOutput(
		root=_prepare_adapter.validate_python(_with_creation_interaction(result))
	)


def confirm_item(
	approval_token: NonEmptyString, confirm: bool, ctx: Context
) -> ConfirmItemOutput:
	"""Create a prepared Item only after explicit confirmation."""
	request = ItemConfirmInput(approval_token=approval_token, confirm=confirm)
	result = execute_tool_with_context(
		ctx,
		"confirm_item",
		lambda: _confirm_item(request.approval_token, request.confirm),
		rest_arguments=request.model_dump(mode="json"),
	)
	return ConfirmItemOutput(root=_confirm_adapter.validate_python(result))


def register_item_tools(mcp: Any) -> None:
	"""Register narrow Item resolution and two-phase creation tools."""

	mcp.tool(meta=tool_meta("search_items"), structured_output=True)(search_items)

	mcp.tool(meta=tool_meta("resolve_item"), structured_output=True)(resolve_item)

	mcp.tool(meta=tool_meta("prepare_item"), structured_output=True)(prepare_item)
	mcp.tool(meta=tool_meta("confirm_item"), structured_output=True)(confirm_item)
