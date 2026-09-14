"""Typed MCP wrappers for read-only Customer intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.masters.customer_read import (
    CustomerAggregateInput,
    CustomerAggregateOutput,
    CustomerFields,
    CustomerGetInput,
    CustomerGetOutput,
    CustomerGroupBy,
    CustomerMetrics,
    CustomerQueryInput,
    CustomerQueryOutput,
    CustomerSortField,
    PositiveLimit,
    NonNegativeOffset,
    SortOrder,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters import customer_read as service


def get_customer(
    customer: NonEmptyString,
    ctx: Context,
    fields: CustomerFields | None = None,
) -> CustomerGetOutput:
    """Retrieve selected fields from one permitted Customer by exact reference."""
    request = CustomerGetInput(customer=customer, fields=fields or ["name"])
    result = execute_tool_with_context(
        ctx, "get_customer", lambda: service.get_customer(**request.model_dump()), rest_arguments=request.model_dump(mode="json")
    )
    return CustomerGetOutput.model_validate(result)


def query_customers(
    ctx: Context,
    name: NonEmptyString | None = None,
    customer_name: NonEmptyString | None = None,
    customer_type: NonEmptyString | None = None,
    customer_group: NonEmptyString | None = None,
    territory: NonEmptyString | None = None,
    email_id: NonEmptyString | None = None,
    mobile_no: NonEmptyString | None = None,
    tax_id: NonEmptyString | None = None,
    disabled: bool | None = None,
    is_frozen: bool | None = None,
    account_manager: NonEmptyString | None = None,
    owner: NonEmptyString | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    modified_from: date | None = None,
    modified_to: date | None = None,
    limit: PositiveLimit = 20,
    offset: NonNegativeOffset = 0,
    sort_by: CustomerSortField = "creation",
    sort_order: SortOrder = "desc",
    fields: CustomerFields | None = None,
) -> CustomerQueryOutput:
    """Query permitted Customers with exact filters, projection, sorting, and pagination."""
    values = {
        key: value
        for key, value in locals().items()
        if key != "ctx" and value is not None
    }
    request = CustomerQueryInput(**values)
    result = execute_tool_with_context(
        ctx, "query_customers", lambda: service.query_customers(request.model_dump()), rest_arguments=request.model_dump(mode="json")
    )
    return CustomerQueryOutput.model_validate(result)


def aggregate_customers(
    ctx: Context,
    metrics: CustomerMetrics | None = None,
    name: NonEmptyString | None = None,
    customer_name: NonEmptyString | None = None,
    customer_type: NonEmptyString | None = None,
    customer_group: NonEmptyString | None = None,
    territory: NonEmptyString | None = None,
    email_id: NonEmptyString | None = None,
    mobile_no: NonEmptyString | None = None,
    tax_id: NonEmptyString | None = None,
    disabled: bool | None = None,
    is_frozen: bool | None = None,
    account_manager: NonEmptyString | None = None,
    owner: NonEmptyString | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    modified_from: date | None = None,
    modified_to: date | None = None,
    group_by: CustomerGroupBy | None = None,
) -> CustomerAggregateOutput:
    """Calculate deterministic permission-aware Customer counts on the server."""
    values = {
        key: value
        for key, value in locals().items()
        if key != "ctx" and value is not None
    }
    request = CustomerAggregateInput(**values)
    result = execute_tool_with_context(
        ctx, "aggregate_customers", lambda: service.aggregate_customers(request.model_dump()), rest_arguments=request.model_dump(mode="json")
    )
    return CustomerAggregateOutput.model_validate(result)


def register_customer_read_tools(mcp: Any) -> None:
    for tool in (get_customer, query_customers, aggregate_customers):
        mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
