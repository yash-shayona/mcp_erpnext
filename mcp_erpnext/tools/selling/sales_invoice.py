"""Typed MCP wrappers for standalone Draft Sales Invoice creation."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.interaction import approval_directive, input_directive
from ...contracts.registry import tool_meta
from ...contracts.common import CustomerReference
from ...contracts.selling.sales_invoice import (
    ConfirmSalesInvoiceOutput,
    ConfirmSalesInvoiceResult,
    PrepareSalesInvoiceOutput,
    PrepareSalesInvoiceResult,
    SalesInvoiceConfirmInput,
    SalesInvoiceItemInput,
    SalesInvoicePrepareInput,
)
from ...runtime import execute_tool_with_context
from ...services.selling.sales_invoice import (
    confirm_sales_invoice as _confirm_sales_invoice,
    prepare_sales_invoice as _prepare_sales_invoice,
)

_prepare_adapter = TypeAdapter(PrepareSalesInvoiceResult)
_confirm_adapter = TypeAdapter(ConfirmSalesInvoiceResult)


def _with_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") == "ready":
        return {**result, "interaction": approval_directive().model_dump(mode="json")}
    if result.get("status") == "needs_input":
        return {**result, "interaction": input_directive().model_dump(mode="json")}
    return result


def prepare_sales_invoice(
    customer: CustomerReference,
    items: list[SalesInvoiceItemInput],
    ctx: Context,
    company: str | None = None,
    posting_date: date | None = None,
    selling_price_list: str | None = None,
    customer_address: str | None = None,
    shipping_address_name: str | None = None,
    contact_person: str | None = None,
    tc_name: str | None = None,
    custom_remarks: str | None = None,
) -> PrepareSalesInvoiceOutput:
    """Prepare an ERPNext-calculated standalone Draft Sales Invoice preview."""
    request = SalesInvoicePrepareInput(
        customer=customer,
        items=items,
        company=company,
        posting_date=posting_date,
        selling_price_list=selling_price_list,
        customer_address=customer_address,
        shipping_address_name=shipping_address_name,
        contact_person=contact_person,
        tc_name=tc_name,
        custom_remarks=custom_remarks,
    )
    result = execute_tool_with_context(
        ctx,
        "prepare_sales_invoice",
		lambda: _prepare_sales_invoice(
            request.customer.model_dump(),
            [item.model_dump() for item in request.items],
            request.company,
            request.posting_date.isoformat() if request.posting_date else None,
            request.selling_price_list,
            request.customer_address,
            request.shipping_address_name,
            request.contact_person,
            request.tc_name,
            request.custom_remarks,
		),
		rest_arguments=request.model_dump(mode="json"),
    )
    return PrepareSalesInvoiceOutput(
        root=_prepare_adapter.validate_python(_with_interaction(result))
    )


def confirm_sales_invoice(
    approval_token: str, confirm: bool, ctx: Context
) -> ConfirmSalesInvoiceOutput:
    """Create the reviewed standalone Draft Sales Invoice after approval."""
    request = SalesInvoiceConfirmInput(
        approval_token=approval_token, confirm=confirm
    )
    result = execute_tool_with_context(
        ctx,
		"confirm_sales_invoice",
		lambda: _confirm_sales_invoice(request.approval_token, request.confirm),
		rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmSalesInvoiceOutput(
        root=_confirm_adapter.validate_python(result)
    )


def register_sales_invoice_tools(mcp: Any) -> None:
    """Register standalone Sales Invoice creation only in the Sales profile."""
    mcp.tool(
        meta=tool_meta("prepare_sales_invoice"), structured_output=True
    )(prepare_sales_invoice)
    mcp.tool(
        meta=tool_meta("confirm_sales_invoice"), structured_output=True
    )(confirm_sales_invoice)
