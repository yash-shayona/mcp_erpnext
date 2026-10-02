"""Typed MCP wrappers for existing Customer Payment Entry reconciliation."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.accounts.customer_payment_reconciliation import (
    ConfirmCustomerPaymentReconciliationOutput,
    ConfirmCustomerPaymentReconciliationResult,
    CustomerPaymentReconciliationConfirmInput,
    CustomerPaymentReconciliationPrepareInput,
    PrepareCustomerPaymentReconciliationOutput,
    PrepareCustomerPaymentReconciliationResult,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.accounts.customer_payment_reconciliation import (
    confirm_customer_payment_reconciliation as _confirm,
    prepare_customer_payment_reconciliation as _prepare,
)


def prepare_customer_payment_reconciliation(
    request: CustomerPaymentReconciliationPrepareInput, ctx: Context
) -> PrepareCustomerPaymentReconciliationOutput:
    arguments = request.model_dump(mode="json")
    result = execute_tool_with_context(
        ctx,
        "prepare_customer_payment_reconciliation",
        lambda: _prepare(arguments),
        rest_arguments=arguments,
    )
    return PrepareCustomerPaymentReconciliationOutput(
        root=TypeAdapter(PrepareCustomerPaymentReconciliationResult).validate_python(
            result
        )
    )


def confirm_customer_payment_reconciliation(
    request: CustomerPaymentReconciliationConfirmInput, ctx: Context
) -> ConfirmCustomerPaymentReconciliationOutput:
    arguments = request.model_dump(mode="json")
    result = execute_tool_with_context(
        ctx,
        "confirm_customer_payment_reconciliation",
        lambda: _confirm(request.approval_token, request.confirm),
        rest_arguments=arguments,
    )
    return ConfirmCustomerPaymentReconciliationOutput(
        root=TypeAdapter(ConfirmCustomerPaymentReconciliationResult).validate_python(
            result
        )
    )


def register_customer_payment_reconciliation_tools(mcp: Any) -> None:
    mcp.tool(
        description="Prepare applying an existing submitted Customer Payment Entry to one submitted Sales Invoice through native reconciliation.",
        meta=tool_meta("prepare_customer_payment_reconciliation"),
        structured_output=True,
    )(prepare_customer_payment_reconciliation)
    mcp.tool(
        description="Apply the approved existing submitted Customer Payment Entry to a Sales Invoice through native ERPNext reconciliation.",
        meta=tool_meta("confirm_customer_payment_reconciliation"),
        structured_output=True,
    )(confirm_customer_payment_reconciliation)
