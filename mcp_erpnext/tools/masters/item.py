"""MCP wrapper for sales-enabled Item lookup."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import selection_directive
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


def _with_selection_interaction(result: dict[str, Any]) -> dict[str, Any]:
	"""Add semantic selection guidance without changing resolver business payloads."""
	if result.get("status") != "ambiguous":
		return result
	return {**result, "interaction": selection_directive().model_dump(mode="json")}


def search_items(query: NonEmptyString, ctx: Context) -> ItemSearchOutput:
	"""Find permitted sales Items with explicit candidate references."""
	result = execute_tool_with_context(ctx, "search_items", lambda: _search_items(query))
	return ItemSearchOutput(root=_search_adapter.validate_python(_with_selection_interaction(result)))


def resolve_item(query: NonEmptyString, ctx: Context) -> ItemResolutionOutput:
	"""Resolve one permitted sales Item or return a terminal selection state."""
	result = execute_tool_with_context(ctx, "resolve_item", lambda: _resolve_item_for_workflow(query))
	return ItemResolutionOutput(root=_resolution_adapter.validate_python(_with_selection_interaction(result)))


def register_item_tools(mcp: Any) -> None:
	"""Register narrow Item resolution and two-phase creation tools."""

	mcp.tool(meta=tool_meta("search_items"), structured_output=True)(search_items)

	mcp.tool(meta=tool_meta("resolve_item"), structured_output=True)(resolve_item)

	@mcp.tool(meta=tool_meta("prepare_item"))
	def prepare_item(item: dict[str, Any], ctx: Context) -> dict[str, Any]:
		"""Validate a new sales Item and return a private confirmation token without writing."""
		return execute_tool_with_context(ctx, "prepare_item", lambda: _prepare_item(item))

	@mcp.tool(meta=tool_meta("confirm_item"))
	def confirm_item(approval_token: str, confirm: bool, ctx: Context) -> dict[str, Any]:
		"""Create a prepared Item only after explicit confirmation."""
		return execute_tool_with_context(ctx, "confirm_item", lambda: _confirm_item(approval_token, confirm))
