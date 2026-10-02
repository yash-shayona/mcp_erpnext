"""Typed MCP wrappers for Purchase Order intelligence reads."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.read import DocumentReadInput
from ...contracts.registry import tool_meta
from ...contracts.buying.purchase_order_read import (
    DocumentStatus,
    GetPurchaseOrderInput,
    GetPurchaseOrderOutput,
    GetPurchaseOrderResult,
    NonNegativeNumber,
    NonNegativeOffset,
    PositiveLimit,
    PurchaseOrderAggregateInput,
    PurchaseOrderAggregateOutput,
    PurchaseOrderGroupBy,
    PurchaseOrderHeaderFields,
    PurchaseOrderItemFields,
    PurchaseOrderItemGroupBy,
    PurchaseOrderItemMetric,
    PurchaseOrderItemQueryInput,
    PurchaseOrderItemQueryOutput,
    PurchaseOrderItemSortField,
    PurchaseOrderMetrics,
    PurchaseOrderQueryInput,
    PurchaseOrderQueryOutput,
    PurchaseOrderSortField,
    SortOrder,
)
from ...runtime import execute_tool_with_context
from ...services.buying import purchase_order_read as service
from ...services.common import read as legacy_read


def get_purchase_order(
    ctx: Context,
    purchase_order: NonEmptyString | None = None,
    fields: PurchaseOrderHeaderFields | None = None,
    include_items: bool = False,
    item_fields: PurchaseOrderItemFields | None = None,
    request: DocumentReadInput | None = None,
) -> GetPurchaseOrderOutput:
    typed_request = GetPurchaseOrderInput(
        purchase_order=purchase_order,
        request=request,
        fields=fields or ["name"],
        include_items=include_items,
        item_fields=item_fields or ["item_code", "item_name", "qty", "rate", "amount"],
    )
    if typed_request.request is not None:
        legacy_request = typed_request.request
        result = execute_tool_with_context(
            ctx,
            "get_purchase_order",
            lambda: legacy_read.get_document(legacy_request.target.model_dump(), "purchase"),
            rest_arguments={"request": legacy_request.model_dump(mode="json")},
        )
    else:
        result = execute_tool_with_context(
            ctx,
            "get_purchase_order",
            lambda: service.get_purchase_order(
                typed_request.purchase_order,
                typed_request.fields,
                typed_request.include_items,
                typed_request.item_fields,
            ),
            rest_arguments=typed_request.model_dump(mode="json", exclude={"request"}),
        )
    return GetPurchaseOrderOutput(
        root=TypeAdapter(GetPurchaseOrderResult).validate_python(result)
    )


def query_purchase_orders(
    ctx: Context,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    schedule_date_from: date | None = None,
    schedule_date_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    supplier: NonEmptyString | None = None,
    company: NonEmptyString | None = None,
    status: NonEmptyString | None = None,
    docstatus: DocumentStatus | None = None,
    item_code: NonEmptyString | None = None,
    owner: NonEmptyString | None = None,
    currency: NonEmptyString | None = None,
    buying_price_list: NonEmptyString | None = None,
    min_grand_total: NonNegativeNumber | None = None,
    max_grand_total: NonNegativeNumber | None = None,
    limit: PositiveLimit = 20,
    offset: NonNegativeOffset = 0,
    sort_by: PurchaseOrderSortField = "transaction_date",
    sort_order: SortOrder = "desc",
    fields: PurchaseOrderHeaderFields | None = None,
) -> PurchaseOrderQueryOutput:
    request = PurchaseOrderQueryInput(
        **{
            key: value
            for key, value in locals().items()
            if key != "ctx" and value is not None
        }
    )
    return PurchaseOrderQueryOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "query_purchase_orders",
            lambda: service.query_purchase_orders(request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def aggregate_purchase_orders(
    ctx: Context,
    metrics: PurchaseOrderMetrics,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    schedule_date_from: date | None = None,
    schedule_date_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    supplier: NonEmptyString | None = None,
    company: NonEmptyString | None = None,
    status: NonEmptyString | None = None,
    docstatus: DocumentStatus | None = None,
    owner: NonEmptyString | None = None,
    currency: NonEmptyString | None = None,
    buying_price_list: NonEmptyString | None = None,
    min_grand_total: NonNegativeNumber | None = None,
    max_grand_total: NonNegativeNumber | None = None,
    group_by: PurchaseOrderGroupBy | None = None,
) -> PurchaseOrderAggregateOutput:
    request = PurchaseOrderAggregateInput(
        **{
            key: value
            for key, value in locals().items()
            if key != "ctx" and value is not None
        }
    )
    return PurchaseOrderAggregateOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "aggregate_purchase_orders",
            lambda: service.aggregate_purchase_orders(request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def query_purchase_order_items(
    ctx: Context,
    supplier: NonEmptyString | None = None,
    item_code: NonEmptyString | None = None,
    transaction_date_from: date | None = None,
    transaction_date_to: date | None = None,
    purchase_order: NonEmptyString | None = None,
    purchase_order_status: NonEmptyString | None = None,
    min_qty: NonNegativeNumber | None = None,
    max_qty: NonNegativeNumber | None = None,
    limit: PositiveLimit = 20,
    offset: NonNegativeOffset = 0,
    sort_by: PurchaseOrderItemSortField = "transaction_date",
    sort_order: SortOrder = "desc",
    fields: PurchaseOrderItemFields | None = None,
    metrics: list[PurchaseOrderItemMetric] | None = None,
    group_by: PurchaseOrderItemGroupBy | None = None,
) -> PurchaseOrderItemQueryOutput:
    request = PurchaseOrderItemQueryInput(
        **{
            key: value
            for key, value in locals().items()
            if key != "ctx" and value is not None
        }
    )
    return PurchaseOrderItemQueryOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "query_purchase_order_items",
            lambda: service.query_purchase_order_items(request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def register_purchase_order_read_tools(mcp: Any) -> None:
    for tool in (
        get_purchase_order,
        query_purchase_orders,
        aggregate_purchase_orders,
        query_purchase_order_items,
    ):
        mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
