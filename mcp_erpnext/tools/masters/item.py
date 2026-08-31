"""MCP wrapper for sales-enabled Item lookup."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from ...runtime import execute_tool_with_context
from ...services.masters.item import (
	confirm_item as _confirm_item,
	prepare_item as _prepare_item,
	resolve_item_for_workflow as _resolve_item_for_workflow,
	search_items as _search_items,
)


def register_item_tools(mcp: Any) -> None:
	"""Register narrow Item resolution and two-phase creation tools."""

	@mcp.tool()
	def search_items(query: str, ctx: Context) -> dict[str, Any]:
		"""Find permitted, active, sales-enabled ERPNext items."""
		return execute_tool_with_context(ctx, "search_items", lambda: _search_items(query))

	@mcp.tool()
	def resolve_item(query: str, ctx: Context) -> dict[str, Any]:
		"""Resolve one permitted sales Item or return a selection/creation state."""
		return execute_tool_with_context(ctx, "resolve_item", lambda: _resolve_item_for_workflow(query))

	@mcp.tool()
	def prepare_item(item: dict[str, Any], ctx: Context) -> dict[str, Any]:
		"""Validate a new sales Item and return a private confirmation token without writing."""
		return execute_tool_with_context(ctx, "prepare_item", lambda: _prepare_item(item))

	@mcp.tool()
	def confirm_item(approval_token: str, confirm: bool, ctx: Context) -> dict[str, Any]:
		"""Create a prepared Item only after explicit confirmation."""
		return execute_tool_with_context(ctx, "confirm_item", lambda: _confirm_item(approval_token, confirm))
