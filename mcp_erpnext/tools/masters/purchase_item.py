"""Purchase-profile wrappers that reuse the shared Item resolver."""

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
    resolve_purchase_item_for_workflow as _resolve_purchase_item,
    search_purchase_items as _search_purchase_items,
)


_resolution_adapter = TypeAdapter(ItemResolutionResult)
_search_adapter = TypeAdapter(ItemSearchResultContract)


def _with_selection_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") != "ambiguous":
        return result
    return {**result, "interaction": selection_directive().model_dump(mode="json")}


def search_items(query: NonEmptyString, ctx: Context) -> ItemSearchOutput:
    """Find permitted purchase-enabled Items with explicit candidate references."""
    result = execute_tool_with_context(ctx, "search_items", lambda: _search_purchase_items(query), rest_arguments={"query": query})
    return ItemSearchOutput(root=_search_adapter.validate_python(_with_selection_interaction(result)))


def resolve_item(query: NonEmptyString, ctx: Context) -> ItemResolutionOutput:
    """Resolve one permitted purchase-enabled Item or require selection."""
    result = execute_tool_with_context(ctx, "resolve_item", lambda: _resolve_purchase_item(query), rest_arguments={"query": query})
    return ItemResolutionOutput(root=_resolution_adapter.validate_python(_with_selection_interaction(result)))


def register_purchase_item_tools(mcp: Any) -> None:
    mcp.tool(meta=tool_meta("search_items"), structured_output=True)(search_items)
    mcp.tool(meta=tool_meta("resolve_item"), structured_output=True)(resolve_item)
