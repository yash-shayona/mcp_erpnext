"""Typed MCP wrappers for native Sales Order to Sales Invoice conversion."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.interaction import approval_directive
from ...contracts.registry import tool_meta
from ...contracts.selling.sales_order_to_sales_invoice import (
    ConfirmSalesOrderToSalesInvoiceOutput,
    ConfirmSalesOrderToSalesInvoiceResult,
    PrepareSalesOrderToSalesInvoiceOutput,
    PrepareSalesOrderToSalesInvoiceResult,
    SalesOrderToSalesInvoiceConfirmInput,
    SalesOrderToSalesInvoiceInput,
)
from ...runtime import execute_tool_with_context
from ...services.selling.sales_order_to_sales_invoice import (
    confirm_sales_order_to_sales_invoice as _confirm_sales_order_to_sales_invoice,
    prepare_sales_order_to_sales_invoice as _prepare_sales_order_to_sales_invoice,
)

_prepare_adapter = TypeAdapter(PrepareSalesOrderToSalesInvoiceResult)
_confirm_adapter = TypeAdapter(ConfirmSalesOrderToSalesInvoiceResult)


def _with_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") == "ready":
        return {**result, "interaction": approval_directive().model_dump(mode="json")}
    return result


def prepare_sales_order_to_sales_invoice(
    sales_order: str, ctx: Context
) -> PrepareSalesOrderToSalesInvoiceOutput:
    """Prepare a Draft Sales Invoice from a Submitted Sales Order using native mapping."""

    request = SalesOrderToSalesInvoiceInput(sales_order=sales_order)
    result = execute_tool_with_context(
        ctx,
		"prepare_sales_order_to_sales_invoice",
		lambda: _prepare_sales_order_to_sales_invoice(request.sales_order),
		rest_arguments=request.model_dump(mode="json"),
    )
    return PrepareSalesOrderToSalesInvoiceOutput(
        root=_prepare_adapter.validate_python(_with_interaction(result))
    )


def confirm_sales_order_to_sales_invoice(
    approval_token: str, confirm: bool, ctx: Context
) -> ConfirmSalesOrderToSalesInvoiceOutput:
    """Create the reviewed Draft Sales Invoice after the approval guard succeeds."""

    request = SalesOrderToSalesInvoiceConfirmInput(
        approval_token=approval_token, confirm=confirm
    )
    result = execute_tool_with_context(
        ctx,
        "confirm_sales_order_to_sales_invoice",
		lambda: _confirm_sales_order_to_sales_invoice(
			request.approval_token, request.confirm
		),
		rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmSalesOrderToSalesInvoiceOutput(root=_confirm_adapter.validate_python(result))


def register_sales_order_to_sales_invoice_tools(mcp: Any) -> None:
    """Register the pair-specific conversion tools in the Sales profile."""

    mcp.tool(
        meta=tool_meta("prepare_sales_order_to_sales_invoice"), structured_output=True
    )(prepare_sales_order_to_sales_invoice)
    mcp.tool(
        meta=tool_meta("confirm_sales_order_to_sales_invoice"), structured_output=True
    )(confirm_sales_order_to_sales_invoice)
