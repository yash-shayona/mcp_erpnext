"""Typed MCP wrappers for standalone Customer receipt Payment Entries."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.accounts.customer_payment_entry import (
    ConfirmCustomerPaymentEntryOutput,
    ConfirmCustomerPaymentEntryResult,
    CustomerPaymentEntryConfirmInput,
    CustomerPaymentEntryPrepareInput,
    PrepareCustomerPaymentEntryOutput,
    PrepareCustomerPaymentEntryResult,
)
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.accounts.customer_payment_entry import (
    confirm_customer_payment_entry as _confirm,
    prepare_customer_payment_entry as _prepare,
)


def prepare_customer_payment_entry(
    request: CustomerPaymentEntryPrepareInput, ctx: Context
) -> PrepareCustomerPaymentEntryOutput:
    arguments = request.model_dump(mode="json")
    result = execute_tool_with_context(
        ctx,
        "prepare_customer_payment_entry",
        lambda: _prepare(arguments),
        rest_arguments=arguments,
    )
    return PrepareCustomerPaymentEntryOutput(
        root=TypeAdapter(PrepareCustomerPaymentEntryResult).validate_python(result)
    )


def confirm_customer_payment_entry(
    request: CustomerPaymentEntryConfirmInput, ctx: Context
) -> ConfirmCustomerPaymentEntryOutput:
    result = execute_tool_with_context(
        ctx,
        "confirm_customer_payment_entry",
        lambda: _confirm(request.approval_token, request.confirm),
        rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmCustomerPaymentEntryOutput(
        root=TypeAdapter(ConfirmCustomerPaymentEntryResult).validate_python(result)
    )


def register_customer_payment_entry_tools(mcp: Any) -> None:
    mcp.tool(
        description="Prepare a native standalone Draft Customer receipt Payment Entry with no invoice allocation.",
        meta=tool_meta("prepare_customer_payment_entry"),
        structured_output=True,
    )(prepare_customer_payment_entry)
    mcp.tool(
        description="Create the reviewed standalone Draft Customer receipt Payment Entry.",
        meta=tool_meta("confirm_customer_payment_entry"),
        structured_output=True,
    )(confirm_customer_payment_entry)
