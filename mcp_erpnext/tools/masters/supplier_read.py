"""Typed MCP wrappers for Supplier intelligence reads."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.masters.supplier_read import (
    SupplierAggregateInput,
    SupplierAggregateOutput,
    SupplierFields,
    SupplierGetInput,
    SupplierGetOutput,
    SupplierGroupBy,
    SupplierMetrics,
    SupplierQueryInput,
    SupplierQueryOutput,
    SupplierSortField,
    PositiveLimit,
    NonNegativeOffset,
    SortOrder,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters import supplier_read as service


def get_supplier(
    supplier: NonEmptyString, ctx: Context, fields: SupplierFields | None = None
) -> SupplierGetOutput:
    request = SupplierGetInput(supplier=supplier, fields=fields or ["name"])
    return SupplierGetOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "get_supplier",
            lambda: service.get_supplier(**request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def query_suppliers(
    ctx: Context,
    name: NonEmptyString | None = None,
    supplier_name: NonEmptyString | None = None,
    supplier_group: NonEmptyString | None = None,
    supplier_type: NonEmptyString | None = None,
    country: NonEmptyString | None = None,
    default_currency: NonEmptyString | None = None,
    disabled: bool | None = None,
    owner: NonEmptyString | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    modified_from: date | None = None,
    modified_to: date | None = None,
    limit: PositiveLimit = 20,
    offset: NonNegativeOffset = 0,
    sort_by: SupplierSortField = "creation",
    sort_order: SortOrder = "desc",
    fields: SupplierFields | None = None,
) -> SupplierQueryOutput:
    request = SupplierQueryInput(
        **{
            key: value
            for key, value in locals().items()
            if key != "ctx" and value is not None
        }
    )
    return SupplierQueryOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "query_suppliers",
            lambda: service.query_suppliers(request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def aggregate_suppliers(
    ctx: Context,
    metrics: SupplierMetrics | None = None,
    name: NonEmptyString | None = None,
    supplier_name: NonEmptyString | None = None,
    supplier_group: NonEmptyString | None = None,
    supplier_type: NonEmptyString | None = None,
    country: NonEmptyString | None = None,
    default_currency: NonEmptyString | None = None,
    disabled: bool | None = None,
    owner: NonEmptyString | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    modified_from: date | None = None,
    modified_to: date | None = None,
    group_by: SupplierGroupBy | None = None,
) -> SupplierAggregateOutput:
    request = SupplierAggregateInput(
        **{
            key: value
            for key, value in locals().items()
            if key != "ctx" and value is not None
        }
    )
    return SupplierAggregateOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "aggregate_suppliers",
            lambda: service.aggregate_suppliers(request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def register_supplier_read_tools(mcp: Any) -> None:
    for tool in (get_supplier, query_suppliers, aggregate_suppliers):
        mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
