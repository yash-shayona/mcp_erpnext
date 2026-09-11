"""Typed MCP wrappers for read-only Sales Order intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.registry import tool_meta
from ...contracts.selling.sales_order_read import (
    DocumentStatus,
    GetSalesOrderInput,
    GetSalesOrderOutput,
    GetSalesOrderResult,
    NonNegativeNumber,
    NonNegativeOffset,
    PositiveLimit,
    SalesOrderAggregateInput,
    SalesOrderAggregateOutput,
    SalesOrderGroupBy,
    SalesOrderHeaderField,
    SalesOrderHeaderFields,
    SalesOrderItemField,
    SalesOrderItemFields,
    SalesOrderItemGroupBy,
    SalesOrderItemMetric,
    SalesOrderItemQueryInput,
    SalesOrderItemQueryOutput,
    SalesOrderItemSortField,
    SalesOrderMetric,
    SalesOrderMetrics,
    SalesOrderQueryInput,
    SalesOrderQueryOutput,
    SalesOrderSortField,
    SortOrder,
)
from ...runtime import execute_tool_with_context
from ...services.selling import sales_order_read as service


def get_sales_order(
    sales_order: NonEmptyString,
    ctx: Context,
    fields: SalesOrderHeaderFields | None = None,
    include_items: bool = False,
    item_fields: SalesOrderItemFields | None = None,
) -> GetSalesOrderOutput:
    """Retrieve selected fields from one permitted Sales Order by exact reference."""
    request = GetSalesOrderInput(
        sales_order=sales_order,
        fields=fields or ["name"],
        include_items=include_items,
        item_fields=item_fields or ["item_code", "item_name", "qty", "rate", "amount"],
    )
    result = execute_tool_with_context(
        ctx, "get_sales_order", lambda: service.get_sales_order(**request.model_dump())
    )
    return GetSalesOrderOutput(
        root=TypeAdapter(GetSalesOrderResult).validate_python(result)
    )


def query_sales_orders(
    ctx: Context,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    delivery_date_from: date | None = None,
    delivery_date_to: date | None = None,
    customer: NonEmptyString | None = None,
    customer_group: NonEmptyString | None = None,
    territory: NonEmptyString | None = None,
    status: NonEmptyString | None = None,
    delivery_status: NonEmptyString | None = None,
    billing_status: NonEmptyString | None = None,
    docstatus: DocumentStatus | None = None,
    item_code: NonEmptyString | None = None,
    sales_person: NonEmptyString | None = None,
    owner: NonEmptyString | None = None,
    currency: NonEmptyString | None = None,
    min_grand_total: NonNegativeNumber | None = None,
    max_grand_total: NonNegativeNumber | None = None,
    limit: PositiveLimit = 20,
    offset: NonNegativeOffset = 0,
    sort_by: SalesOrderSortField = "transaction_date",
    sort_order: SortOrder = "desc",
    fields: SalesOrderHeaderFields | None = None,
) -> SalesOrderQueryOutput:
    """Query permitted Sales Orders using typed filters, projection, sorting, and pagination."""
    request = SalesOrderQueryInput(
        **{
            key: value
            for key, value in locals().items()
            if key != "ctx" and value is not None
        }
    )
    result = execute_tool_with_context(
        ctx,
        "query_sales_orders",
        lambda: service.query_sales_orders(request.model_dump()),
    )
    return SalesOrderQueryOutput.model_validate(result)


def aggregate_sales_orders(
    ctx: Context,
    metrics: SalesOrderMetrics,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    delivery_date_from: date | None = None,
    delivery_date_to: date | None = None,
    customer: NonEmptyString | None = None,
    customer_group: NonEmptyString | None = None,
    territory: NonEmptyString | None = None,
    status: NonEmptyString | None = None,
    delivery_status: NonEmptyString | None = None,
    billing_status: NonEmptyString | None = None,
    docstatus: DocumentStatus | None = None,
    owner: NonEmptyString | None = None,
    currency: NonEmptyString | None = None,
    min_grand_total: NonNegativeNumber | None = None,
    max_grand_total: NonNegativeNumber | None = None,
    group_by: SalesOrderGroupBy | None = None,
) -> SalesOrderAggregateOutput:
    """Calculate deterministic permission-aware Sales Order metrics on the server."""
    request = SalesOrderAggregateInput(
        **{
            key: value
            for key, value in locals().items()
            if key != "ctx" and value is not None
        }
    )
    result = execute_tool_with_context(
        ctx,
        "aggregate_sales_orders",
        lambda: service.aggregate_sales_orders(request.model_dump()),
    )
    return SalesOrderAggregateOutput.model_validate(result)


def query_sales_order_items(
    ctx: Context,
    customer: NonEmptyString | None = None,
    item_code: NonEmptyString | None = None,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    sales_order: NonEmptyString | None = None,
    sales_order_status: NonEmptyString | None = None,
    min_qty: NonNegativeNumber | None = None,
    max_qty: NonNegativeNumber | None = None,
    limit: PositiveLimit = 20,
    offset: NonNegativeOffset = 0,
    sort_by: SalesOrderItemSortField = "transaction_date",
    sort_order: SortOrder = "desc",
    fields: SalesOrderItemFields | None = None,
    metrics: list[SalesOrderItemMetric] | None = None,
    group_by: SalesOrderItemGroupBy | None = None,
) -> SalesOrderItemQueryOutput:
    """Query permitted Sales Order Item history and optional server-side item metrics."""
    values = {
        key: value
        for key, value in locals().items()
        if key != "ctx" and value is not None
    }
    request = SalesOrderItemQueryInput(**values)
    result = execute_tool_with_context(
        ctx,
        "query_sales_order_items",
        lambda: service.query_sales_order_items(request.model_dump()),
    )
    return SalesOrderItemQueryOutput.model_validate(result)


def register_sales_order_read_tools(mcp: Any) -> None:
    for tool in (
        get_sales_order,
        query_sales_orders,
        aggregate_sales_orders,
        query_sales_order_items,
    ):
        mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
