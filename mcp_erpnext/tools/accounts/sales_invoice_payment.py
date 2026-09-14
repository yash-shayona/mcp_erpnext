"""Typed MCP wrappers for Sales Invoice customer receipts."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.accounts.sales_invoice_payment import (
    ConfirmSalesInvoicePaymentOutput,
    ConfirmSalesInvoicePaymentResult,
    PrepareSalesInvoicePaymentOutput,
    PrepareSalesInvoicePaymentResult,
    SalesInvoicePaymentConfirmInput,
    SalesInvoicePaymentPrepareInput,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.accounts.sales_invoice_payment import (
    confirm_sales_invoice_payment as _confirm,
    prepare_sales_invoice_payment as _prepare,
)


def prepare_sales_invoice_payment(request: SalesInvoicePaymentPrepareInput, ctx: Context) -> PrepareSalesInvoicePaymentOutput:
    result = execute_tool_with_context(
        ctx, "prepare_sales_invoice_payment",
        lambda: _prepare(request.model_dump(mode="json")),
        rest_arguments=request.model_dump(mode="json"),
    )
    return PrepareSalesInvoicePaymentOutput(root=TypeAdapter(PrepareSalesInvoicePaymentResult).validate_python(result))


def confirm_sales_invoice_payment(request: SalesInvoicePaymentConfirmInput, ctx: Context) -> ConfirmSalesInvoicePaymentOutput:
    result = execute_tool_with_context(
        ctx, "confirm_sales_invoice_payment",
        lambda: _confirm(request.approval_token, request.confirm),
        rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmSalesInvoicePaymentOutput(root=TypeAdapter(ConfirmSalesInvoicePaymentResult).validate_python(result))


def register_sales_invoice_payment_tools(mcp: Any) -> None:
    mcp.tool(description="Prepare a native Draft customer Payment Entry for one submitted Sales Invoice.", meta=tool_meta("prepare_sales_invoice_payment"), structured_output=True)(prepare_sales_invoice_payment)
    mcp.tool(description="Create the reviewed native Draft customer Payment Entry.", meta=tool_meta("confirm_sales_invoice_payment"), structured_output=True)(confirm_sales_invoice_payment)
