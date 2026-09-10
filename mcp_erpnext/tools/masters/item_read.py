"""Typed MCP wrappers for read-only sales Item intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.masters.item_read import (
    ItemAggregateInput,
    ItemAggregateOutput,
    ItemFields,
    ItemGetInput,
    ItemGetOutput,
    ItemGroupBy,
    ItemMetrics,
    ItemQueryInput,
    ItemQueryOutput,
    ItemSortField,
    NonNegativeOffset,
    PositiveLimit,
    SortOrder,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters import item_read as service


def get_item(
    item: NonEmptyString,
    ctx: Context,
    fields: ItemFields | None = None,
) -> ItemGetOutput:
    """Read selected fields from one permitted Item by exact reference."""
    request = ItemGetInput(item=item, fields=fields or ["name"])
    result = execute_tool_with_context(
        ctx, "get_item", lambda: service.get_item(**request.model_dump())
    )
    return ItemGetOutput.model_validate(result)


def query_items(
    ctx: Context,
    name: NonEmptyString | None = None,
    item_code: NonEmptyString | None = None,
    item_name: NonEmptyString | None = None,
    item_group: NonEmptyString | None = None,
    stock_uom: NonEmptyString | None = None,
    disabled: bool | None = None,
    is_sales_item: bool | None = None,
    is_purchase_item: bool | None = None,
    is_stock_item: bool | None = None,
    brand: NonEmptyString | None = None,
    owner: NonEmptyString | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    modified_from: date | None = None,
    modified_to: date | None = None,
    limit: PositiveLimit = 20,
    offset: NonNegativeOffset = 0,
    sort_by: ItemSortField = "creation",
    sort_order: SortOrder = "desc",
    fields: ItemFields | None = None,
) -> ItemQueryOutput:
    """Query permitted Items with exact filters, projection, sorting, and pagination; never fuzzy-match."""
    values = {
        key: value
        for key, value in locals().items()
        if key != "ctx" and value is not None
    }
    request = ItemQueryInput(**values)
    result = execute_tool_with_context(
        ctx, "query_items", lambda: service.query_items(request.model_dump())
    )
    return ItemQueryOutput.model_validate(result)


def aggregate_items(
    ctx: Context,
    metrics: ItemMetrics | None = None,
    name: NonEmptyString | None = None,
    item_code: NonEmptyString | None = None,
    item_name: NonEmptyString | None = None,
    item_group: NonEmptyString | None = None,
    stock_uom: NonEmptyString | None = None,
    disabled: bool | None = None,
    is_sales_item: bool | None = None,
    is_purchase_item: bool | None = None,
    is_stock_item: bool | None = None,
    brand: NonEmptyString | None = None,
    owner: NonEmptyString | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    modified_from: date | None = None,
    modified_to: date | None = None,
    group_by: ItemGroupBy | None = None,
) -> ItemAggregateOutput:
    """Calculate deterministic permission-aware Item counts on the server."""
    values = {
        key: value
        for key, value in locals().items()
        if key != "ctx" and value is not None
    }
    request = ItemAggregateInput(**values)
    result = execute_tool_with_context(
        ctx, "aggregate_items", lambda: service.aggregate_items(request.model_dump())
    )
    return ItemAggregateOutput.model_validate(result)


def register_item_read_tools(mcp: Any) -> None:
    for tool in (get_item, query_items, aggregate_items):
        mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
