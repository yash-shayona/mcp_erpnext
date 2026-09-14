"""Typed MCP wrappers for Sales Invoice to Delivery Note conversion."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.registry import tool_meta
from ...contracts.selling.sales_invoice_to_delivery_note import (
    ConfirmSalesInvoiceToDeliveryNoteOutput,
    ConfirmSalesInvoiceToDeliveryNoteResult,
    PrepareSalesInvoiceToDeliveryNoteOutput,
    PrepareSalesInvoiceToDeliveryNoteResult,
    SalesInvoiceToDeliveryNoteConfirmInput,
    SalesInvoiceToDeliveryNoteInput,
)
from ...runtime import execute_tool_with_context
from ...services.selling import sales_invoice_to_delivery_note as service

_prepare = TypeAdapter(PrepareSalesInvoiceToDeliveryNoteResult)
_confirm = TypeAdapter(ConfirmSalesInvoiceToDeliveryNoteResult)


def prepare_sales_invoice_to_delivery_note(
    sales_invoice: str, ctx: Context
) -> PrepareSalesInvoiceToDeliveryNoteOutput:
    request = SalesInvoiceToDeliveryNoteInput(sales_invoice=sales_invoice)
    result = execute_tool_with_context(
        ctx,
        "prepare_sales_invoice_to_delivery_note",
        lambda: service.prepare_sales_invoice_to_delivery_note(request.sales_invoice),
        rest_arguments=request.model_dump(mode="json"),
    )
    return PrepareSalesInvoiceToDeliveryNoteOutput(root=_prepare.validate_python(result))


def confirm_sales_invoice_to_delivery_note(
    approval_token: str, confirm: bool, ctx: Context
) -> ConfirmSalesInvoiceToDeliveryNoteOutput:
    request = SalesInvoiceToDeliveryNoteConfirmInput(
        approval_token=approval_token, confirm=confirm
    )
    result = execute_tool_with_context(
        ctx,
        "confirm_sales_invoice_to_delivery_note",
        lambda: service.confirm_sales_invoice_to_delivery_note(
            request.approval_token, request.confirm
        ),
        rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmSalesInvoiceToDeliveryNoteOutput(root=_confirm.validate_python(result))


def register_sales_invoice_to_delivery_note_tools(mcp: Any) -> None:
    mcp.tool(
        name="prepare_sales_invoice_to_delivery_note",
        description="Prepare a native Draft Delivery Note preview from a submitted Sales Invoice that still has deliverable quantity.",
        meta=tool_meta("prepare_sales_invoice_to_delivery_note"),
        structured_output=True,
    )(prepare_sales_invoice_to_delivery_note)
    mcp.tool(
        name="confirm_sales_invoice_to_delivery_note",
        description="Create the approved native Draft Delivery Note from the reviewed Sales Invoice conversion.",
        meta=tool_meta("confirm_sales_invoice_to_delivery_note"),
        structured_output=True,
    )(confirm_sales_invoice_to_delivery_note)
