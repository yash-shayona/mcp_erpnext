"""Typed MCP wrapper for exact Purchase Receipt reads."""

from __future__ import annotations

from typing import Any
from datetime import date

from mcp.server.fastmcp import Context

from ...contracts.buying.purchase_receipt_read import (
    GetPurchaseReceiptInput,
    GetPurchaseReceiptOutput,
    PurchaseReceiptHeaderFields,
    PurchaseReceiptItemFields,
    ReceiptQueryInput, ReceiptQueryOutput, ReceiptAggregateInput, ReceiptAggregateOutput, ReceiptItemQueryInput, ReceiptItemQueryOutput,
    HeaderFields, HeaderMetrics, HeaderGroup, HeaderSort, ItemFields, ItemMetric, ItemGroup, ItemSort, Limit, Offset, Number, Docstatus, SortOrder,
)
from ...contracts.common import NonEmptyString
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.buying import purchase_receipt_read as service


def get_purchase_receipt(
    purchase_receipt: NonEmptyString,
    ctx: Context,
    fields: PurchaseReceiptHeaderFields | None = None,
    include_items: bool = False,
    item_fields: PurchaseReceiptItemFields | None = None,
) -> GetPurchaseReceiptOutput:
    request = GetPurchaseReceiptInput(
        purchase_receipt=purchase_receipt,
        fields=fields or ["name"],
        include_items=include_items,
        item_fields=item_fields
        or ["name", "item_code", "purchase_order", "purchase_order_item", "qty", "rejected_qty"],
    )
    result = execute_tool_with_context(
        ctx,
        "get_purchase_receipt",
        lambda: service.get_purchase_receipt(**request.model_dump()),
        rest_arguments=request.model_dump(mode="json"),
    )
    return GetPurchaseReceiptOutput.model_validate(result)


def query_purchase_receipts(
    ctx: Context,
    name: NonEmptyString | None = None, supplier: NonEmptyString | None = None,
    company: NonEmptyString | None = None, docstatus: Docstatus | None = None,
    status: NonEmptyString | None = None, currency: NonEmptyString | None = None,
    owner: NonEmptyString | None = None, is_return: bool | None = None,
    return_against: NonEmptyString | None = None, posting_date_from: date | None = None,
    posting_date_to: date | None = None, created_from: date | None = None,
    created_to: date | None = None, modified_from: date | None = None,
    modified_to: date | None = None, min_grand_total: Number | None = None,
    max_grand_total: Number | None = None, item_code: NonEmptyString | None = None,
    purchase_order: NonEmptyString | None = None, limit: Limit = 20, offset: Offset = 0,
    sort_by: HeaderSort = "posting_date", sort_order: SortOrder = "desc",
    fields: HeaderFields | None = None,
) -> ReceiptQueryOutput:
    request = ReceiptQueryInput(**{key: value for key, value in locals().items() if key != "ctx" and value is not None})
    return ReceiptQueryOutput.model_validate(execute_tool_with_context(ctx, "query_purchase_receipts", lambda: service.query_purchase_receipts(request.model_dump()), rest_arguments=request.model_dump(mode="json")))


def aggregate_purchase_receipts(
    ctx: Context, metrics: HeaderMetrics,
    name: NonEmptyString | None = None, supplier: NonEmptyString | None = None,
    company: NonEmptyString | None = None, docstatus: Docstatus | None = None,
    status: NonEmptyString | None = None, currency: NonEmptyString | None = None,
    owner: NonEmptyString | None = None, is_return: bool | None = None,
    return_against: NonEmptyString | None = None, posting_date_from: date | None = None,
    posting_date_to: date | None = None, created_from: date | None = None,
    created_to: date | None = None, modified_from: date | None = None,
    modified_to: date | None = None, min_grand_total: Number | None = None,
    max_grand_total: Number | None = None, group_by: HeaderGroup | None = None,
) -> ReceiptAggregateOutput:
    request = ReceiptAggregateInput(**{key: value for key, value in locals().items() if key != "ctx" and value is not None})
    return ReceiptAggregateOutput.model_validate(execute_tool_with_context(ctx, "aggregate_purchase_receipts", lambda: service.aggregate_purchase_receipts(request.model_dump()), rest_arguments=request.model_dump(mode="json")))


def query_purchase_receipt_items(
    ctx: Context, purchase_receipt: NonEmptyString | None = None,
    purchase_order: NonEmptyString | None = None, supplier: NonEmptyString | None = None,
    company: NonEmptyString | None = None, item_code: NonEmptyString | None = None,
    purchase_receipt_status: NonEmptyString | None = None, docstatus: Docstatus | None = None,
    is_return: bool | None = None, warehouse: NonEmptyString | None = None,
    rejected_warehouse: NonEmptyString | None = None, posting_date_from: date | None = None,
    posting_date_to: date | None = None, min_qty: Number | None = None,
    max_qty: Number | None = None, min_received_qty: Number | None = None,
    max_received_qty: Number | None = None, min_rejected_qty: Number | None = None,
    max_rejected_qty: Number | None = None, limit: Limit = 20, offset: Offset = 0,
    sort_by: ItemSort = "posting_date", sort_order: SortOrder = "desc",
    fields: ItemFields | None = None, metrics: list[ItemMetric] | None = None,
    group_by: ItemGroup | None = None,
) -> ReceiptItemQueryOutput:
    request = ReceiptItemQueryInput(**{key: value for key, value in locals().items() if key != "ctx" and value is not None})
    return ReceiptItemQueryOutput.model_validate(execute_tool_with_context(ctx, "query_purchase_receipt_items", lambda: service.query_purchase_receipt_items(request.model_dump()), rest_arguments=request.model_dump(mode="json")))


def register_purchase_receipt_read_tools(mcp: Any) -> None:
    mcp.tool(
        name="get_purchase_receipt",
        meta=tool_meta("get_purchase_receipt"),
        structured_output=True,
    )(get_purchase_receipt)
    for tool in (query_purchase_receipts, aggregate_purchase_receipts, query_purchase_receipt_items):
        mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
