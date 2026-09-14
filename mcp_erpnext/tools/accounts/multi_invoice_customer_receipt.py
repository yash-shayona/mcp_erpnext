"""Typed MCP wrappers for explicit multi-invoice Customer receipts."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.accounts.multi_invoice_customer_receipt import (
    ConfirmMultiInvoiceCustomerReceiptOutput,
    ConfirmMultiInvoiceCustomerReceiptResult,
    MultiInvoiceCustomerReceiptConfirmInput,
    MultiInvoiceCustomerReceiptPrepareInput,
    PrepareMultiInvoiceCustomerReceiptOutput,
    PrepareMultiInvoiceCustomerReceiptResult,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.accounts.multi_invoice_customer_receipt import (
    confirm_multi_invoice_customer_receipt as _confirm,
    prepare_multi_invoice_customer_receipt as _prepare,
)


def prepare_multi_invoice_customer_receipt(request: MultiInvoiceCustomerReceiptPrepareInput, ctx: Context) -> PrepareMultiInvoiceCustomerReceiptOutput:
    arguments = request.model_dump(mode="json")
    result = execute_tool_with_context(ctx, "prepare_multi_invoice_customer_receipt", lambda: _prepare(arguments), rest_arguments=arguments)
    return PrepareMultiInvoiceCustomerReceiptOutput(root=TypeAdapter(PrepareMultiInvoiceCustomerReceiptResult).validate_python(result))


def confirm_multi_invoice_customer_receipt(request: MultiInvoiceCustomerReceiptConfirmInput, ctx: Context) -> ConfirmMultiInvoiceCustomerReceiptOutput:
    result = execute_tool_with_context(ctx, "confirm_multi_invoice_customer_receipt", lambda: _confirm(request.approval_token, request.confirm), rest_arguments=request.model_dump(mode="json"))
    return ConfirmMultiInvoiceCustomerReceiptOutput(root=TypeAdapter(ConfirmMultiInvoiceCustomerReceiptResult).validate_python(result))


def register_multi_invoice_customer_receipt_tools(mcp: Any) -> None:
    mcp.tool(description="Prepare one explicit Customer receipt allocated across 2-20 submitted Sales Invoices.", meta=tool_meta("prepare_multi_invoice_customer_receipt"), structured_output=True)(prepare_multi_invoice_customer_receipt)
    mcp.tool(description="Create the reviewed multi-invoice Customer receipt as one Draft Payment Entry.", meta=tool_meta("confirm_multi_invoice_customer_receipt"), structured_output=True)(confirm_multi_invoice_customer_receipt)
