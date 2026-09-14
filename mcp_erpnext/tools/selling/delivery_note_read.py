"""Typed MCP wrappers for Delivery Note reads and analytics."""

from __future__ import annotations
from typing import Any
from mcp.server.fastmcp import Context
from ...contracts.common import NonEmptyString
from ...contracts.registry import tool_meta
from ...contracts.selling.delivery_note_read import *
from ...runtime import execute_tool_with_context
from ...services.selling import delivery_note_read as service


def get_delivery_note(
    delivery_note: NonEmptyString,
    ctx: Context,
    fields: DeliveryNoteFields | None = None,
) -> DeliveryNoteGetOutput:
    request = DeliveryNoteGetInput(
        delivery_note=delivery_note,
        fields=fields
        or [
            "name",
            "customer",
            "customer_name",
            "posting_date",
            "docstatus",
            "status",
            "currency",
            "grand_total",
        ],
    )
    return DeliveryNoteGetOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "get_delivery_note",
            lambda: service.get_delivery_note(**request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def query_delivery_notes(
    request: DeliveryNoteQueryInput, ctx: Context
) -> DeliveryNoteQueryOutput:
    return DeliveryNoteQueryOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "query_delivery_notes",
            lambda: service.query_delivery_notes(request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def aggregate_delivery_notes(
    request: DeliveryNoteAggregateInput, ctx: Context
) -> DeliveryNoteAggregateOutput:
    return DeliveryNoteAggregateOutput.model_validate(
        execute_tool_with_context(
            ctx,
            "aggregate_delivery_notes",
            lambda: service.aggregate_delivery_notes(request.model_dump()),
            rest_arguments=request.model_dump(mode="json"),
        )
    )


def register_delivery_note_read_tools(mcp: Any) -> None:
    descriptions = {
        "get_delivery_note": "Retrieve selected fields from one permitted Delivery Note.",
        "query_delivery_notes": "Query permitted Delivery Notes with typed filters, projections, sorting, and pagination.",
        "aggregate_delivery_notes": "Calculate permission-aware aggregate metrics for Delivery Notes.",
    }
    for tool in (get_delivery_note, query_delivery_notes, aggregate_delivery_notes):
        mcp.tool(name=tool.__name__, description=descriptions[tool.__name__], meta=tool_meta(tool.__name__), structured_output=True)(tool)
