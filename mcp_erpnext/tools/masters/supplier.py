"""MCP wrappers for Supplier lookup in the Purchase profile."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import selection_directive
from ...contracts.masters.resolution import (
    SupplierResolutionOutput,
    SupplierResolutionResult,
    SupplierSearchOutput,
    SupplierSearchResultContract,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters.supplier import (
    resolve_supplier_for_workflow as _resolve_supplier,
    search_suppliers as _search_suppliers,
)


_resolution_adapter = TypeAdapter(SupplierResolutionResult)
_search_adapter = TypeAdapter(SupplierSearchResultContract)


def _with_selection_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") != "ambiguous":
        return result
    return {**result, "interaction": selection_directive().model_dump(mode="json")}


def search_suppliers(query: NonEmptyString, ctx: Context) -> SupplierSearchOutput:
    """Find permitted active Suppliers with explicit candidate references."""
    result = execute_tool_with_context(ctx, "search_suppliers", lambda: _search_suppliers(query), rest_arguments={"query": query})
    return SupplierSearchOutput(root=_search_adapter.validate_python(_with_selection_interaction(result)))


def resolve_supplier(query: NonEmptyString, ctx: Context) -> SupplierResolutionOutput:
    """Resolve one permitted Supplier or return a terminal selection state."""
    result = execute_tool_with_context(ctx, "resolve_supplier", lambda: _resolve_supplier(query), rest_arguments={"query": query})
    return SupplierResolutionOutput(root=_resolution_adapter.validate_python(_with_selection_interaction(result)))


def register_supplier_tools(mcp: Any) -> None:
    mcp.tool(meta=tool_meta("search_suppliers"), structured_output=True)(search_suppliers)
    mcp.tool(meta=tool_meta("resolve_supplier"), structured_output=True)(resolve_supplier)
