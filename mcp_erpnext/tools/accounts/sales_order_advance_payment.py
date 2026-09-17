"""Typed MCP wrappers for Sales Order Customer advance Payment Entries."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.accounts.sales_order_advance_payment import (
    ConfirmSalesOrderAdvancePaymentOutput,
    ConfirmSalesOrderAdvancePaymentResult,
    PrepareSalesOrderAdvancePaymentOutput,
    PrepareSalesOrderAdvancePaymentResult,
    SalesOrderAdvancePaymentConfirmInput,
    SalesOrderAdvancePaymentPrepareInput,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.accounts.sales_order_advance_payment import (
    confirm_sales_order_advance_payment as _confirm,
    prepare_sales_order_advance_payment as _prepare,
)


def prepare_sales_order_advance_payment(
    request: SalesOrderAdvancePaymentPrepareInput, ctx: Context
) -> PrepareSalesOrderAdvancePaymentOutput:
    arguments = request.model_dump(mode="json")
    result = execute_tool_with_context(
        ctx,
        "prepare_sales_order_advance_payment",
        lambda: _prepare(arguments),
        rest_arguments=arguments,
    )
    return PrepareSalesOrderAdvancePaymentOutput(
        root=TypeAdapter(PrepareSalesOrderAdvancePaymentResult).validate_python(result)
    )


def confirm_sales_order_advance_payment(
    request: SalesOrderAdvancePaymentConfirmInput, ctx: Context
) -> ConfirmSalesOrderAdvancePaymentOutput:
    result = execute_tool_with_context(
        ctx,
        "confirm_sales_order_advance_payment",
        lambda: _confirm(request.approval_token, request.confirm),
        rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmSalesOrderAdvancePaymentOutput(
        root=TypeAdapter(ConfirmSalesOrderAdvancePaymentResult).validate_python(result)
    )


def register_sales_order_advance_payment_tools(mcp: Any) -> None:
    mcp.tool(
        description="Prepare a native Draft Customer advance Payment Entry for one submitted Sales Order.",
        meta=tool_meta("prepare_sales_order_advance_payment"),
        structured_output=True,
    )(prepare_sales_order_advance_payment)
    mcp.tool(
        description="Create the reviewed native Draft Customer advance Payment Entry.",
        meta=tool_meta("confirm_sales_order_advance_payment"),
        structured_output=True,
    )(confirm_sales_order_advance_payment)
