"""Typed MCP wrappers for Delivery Note conversion."""

from __future__ import annotations
from typing import Any
from mcp.server.fastmcp import Context
from pydantic import TypeAdapter
from ...contracts.registry import tool_meta
from ...contracts.selling.delivery_note import *
from ...runtime import execute_tool_with_context
from ...services.selling import sales_order_to_delivery_note as service

_prepare = TypeAdapter(PrepareDeliveryNoteResult)
_confirm = TypeAdapter(ConfirmDeliveryNoteResult)


def prepare_sales_order_to_delivery_note(
    sales_order: str, ctx: Context
) -> PrepareDeliveryNoteOutput:
    request = SalesOrderToDeliveryNoteInput(sales_order=sales_order)
    result = execute_tool_with_context(
        ctx,
        "prepare_sales_order_to_delivery_note",
        lambda: service.prepare_sales_order_to_delivery_note(request.sales_order),
        rest_arguments=request.model_dump(mode="json"),
    )
    return PrepareDeliveryNoteOutput(root=_prepare.validate_python(result))


def confirm_sales_order_to_delivery_note(
    approval_token: str, confirm: bool, ctx: Context
) -> ConfirmDeliveryNoteOutput:
    request = SalesOrderToDeliveryNoteConfirmInput(
        approval_token=approval_token, confirm=confirm
    )
    result = execute_tool_with_context(
        ctx,
        "confirm_sales_order_to_delivery_note",
        lambda: service.confirm_sales_order_to_delivery_note(
            request.approval_token, request.confirm
        ),
        rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmDeliveryNoteOutput(root=_confirm.validate_python(result))


def register_delivery_note_tools(mcp: Any) -> None:
    mcp.tool(
        name="prepare_sales_order_to_delivery_note",
        description="Prepare a native Draft Delivery Note preview from an exact Submitted Sales Order.",
        meta=tool_meta("prepare_sales_order_to_delivery_note"), structured_output=True
    )(prepare_sales_order_to_delivery_note)
    mcp.tool(
        name="confirm_sales_order_to_delivery_note",
        description="Create the approved native Draft Delivery Note from a Sales Order conversion.",
        meta=tool_meta("confirm_sales_order_to_delivery_note"), structured_output=True
    )(confirm_sales_order_to_delivery_note)
