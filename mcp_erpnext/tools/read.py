"""Profile-scoped public wrappers for existing-document reads."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ..contracts.read import DocumentReadInput, DocumentReadOutput, DocumentReadResult, DocumentSearchInput, DocumentSearchOutput
from ..contracts.registry import tool_meta
from ..runtime import execute_tool_with_context
from ..services.common import read


def _get(request: DocumentReadInput, ctx: Context, profile: str) -> DocumentReadOutput:
	result = execute_tool_with_context(ctx, f"get_{request.target.doctype.lower().replace(' ', '_')}", lambda: read.get_document(request.target.model_dump(), profile))
	return DocumentReadOutput(root=TypeAdapter(DocumentReadResult).validate_python(result))


def _search(request: DocumentSearchInput, ctx: Context, doctype: str, profile: str) -> DocumentSearchOutput:
	result = execute_tool_with_context(ctx, f"search_{doctype.lower().replace(' ', '_')}s", lambda: read.search_documents(doctype, request.model_dump(), profile))
	return DocumentSearchOutput.model_validate(result)


def register_sales_read_tools(mcp: Any) -> None:
	@mcp.tool(name="get_quotation", description="Retrieve one permitted Quotation summary by exact document name.", meta=tool_meta("get_quotation"), structured_output=True)
	def get_quotation(request: DocumentReadInput, ctx: Context) -> DocumentReadOutput:
		return _get(request, ctx, "sales")

	@mcp.tool(name="search_quotations", description="Search permitted Quotations with bounded business filters.", meta=tool_meta("search_quotations"), structured_output=True)
	def search_quotations(request: DocumentSearchInput, ctx: Context) -> DocumentSearchOutput:
		return _search(request, ctx, "Quotation", "sales")


def register_purchase_read_tools(mcp: Any) -> None:
	@mcp.tool(name="get_purchase_order", description="Retrieve one permitted Purchase Order summary by exact document name.", meta=tool_meta("get_purchase_order"), structured_output=True)
	def get_purchase_order(request: DocumentReadInput, ctx: Context) -> DocumentReadOutput:
		return _get(request, ctx, "purchase")

	@mcp.tool(name="search_purchase_orders", description="Search permitted Purchase Orders with bounded business filters.", meta=tool_meta("search_purchase_orders"), structured_output=True)
	def search_purchase_orders(request: DocumentSearchInput, ctx: Context) -> DocumentSearchOutput:
		return _search(request, ctx, "Purchase Order", "purchase")
