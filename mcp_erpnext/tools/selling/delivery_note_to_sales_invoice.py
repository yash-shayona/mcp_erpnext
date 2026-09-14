"""Typed MCP wrappers for Delivery Note to Sales Invoice conversion."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.registry import tool_meta
from ...contracts.selling.delivery_note_to_sales_invoice import (
    ConfirmDeliveryNoteToSalesInvoiceOutput,
    ConfirmDeliveryNoteToSalesInvoiceResult,
    DeliveryNoteToSalesInvoiceConfirmInput,
    DeliveryNoteToSalesInvoiceInput,
    PrepareDeliveryNoteToSalesInvoiceOutput,
    PrepareDeliveryNoteToSalesInvoiceResult,
)
from ...runtime import execute_tool_with_context
from ...services.selling import delivery_note_to_sales_invoice as service

_prepare = TypeAdapter(PrepareDeliveryNoteToSalesInvoiceResult)
_confirm = TypeAdapter(ConfirmDeliveryNoteToSalesInvoiceResult)


def prepare_delivery_note_to_sales_invoice(
    delivery_note: str, ctx: Context
) -> PrepareDeliveryNoteToSalesInvoiceOutput:
    request = DeliveryNoteToSalesInvoiceInput(delivery_note=delivery_note)
    result = execute_tool_with_context(
        ctx,
        "prepare_delivery_note_to_sales_invoice",
        lambda: service.prepare_delivery_note_to_sales_invoice(request.delivery_note),
        rest_arguments=request.model_dump(mode="json"),
    )
    return PrepareDeliveryNoteToSalesInvoiceOutput(
        root=_prepare.validate_python(result)
    )


def confirm_delivery_note_to_sales_invoice(
    approval_token: str, confirm: bool, ctx: Context
) -> ConfirmDeliveryNoteToSalesInvoiceOutput:
    request = DeliveryNoteToSalesInvoiceConfirmInput(
        approval_token=approval_token, confirm=confirm
    )
    result = execute_tool_with_context(
        ctx,
        "confirm_delivery_note_to_sales_invoice",
        lambda: service.confirm_delivery_note_to_sales_invoice(
            request.approval_token, request.confirm
        ),
        rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmDeliveryNoteToSalesInvoiceOutput(
        root=_confirm.validate_python(result)
    )


def register_delivery_note_to_sales_invoice_tools(mcp: Any) -> None:
    mcp.tool(
        name="prepare_delivery_note_to_sales_invoice",
        description="Prepare a native Draft Sales Invoice preview from an exact Submitted Delivery Note.",
        meta=tool_meta("prepare_delivery_note_to_sales_invoice"),
        structured_output=True,
    )(prepare_delivery_note_to_sales_invoice)
    mcp.tool(
        name="confirm_delivery_note_to_sales_invoice",
        description="Create the approved native Draft Sales Invoice from a Delivery Note conversion.",
        meta=tool_meta("confirm_delivery_note_to_sales_invoice"),
        structured_output=True,
    )(confirm_delivery_note_to_sales_invoice)
