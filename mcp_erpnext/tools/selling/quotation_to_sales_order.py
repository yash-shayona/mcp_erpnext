"""Typed MCP wrappers for native Quotation to Sales Order conversion."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.interaction import approval_directive
from ...contracts.registry import tool_meta
from ...contracts.selling.quotation_to_sales_order import (
    ConfirmQuotationToSalesOrderOutput,
    ConfirmQuotationToSalesOrderResult,
    PrepareQuotationToSalesOrderOutput,
    PrepareQuotationToSalesOrderResult,
    QuotationToSalesOrderConfirmInput,
    QuotationToSalesOrderInput,
)
from ...runtime import execute_tool_with_context
from ...services.selling.quotation_to_sales_order import (
    confirm_quotation_to_sales_order as _confirm_quotation_to_sales_order,
    prepare_quotation_to_sales_order as _prepare_quotation_to_sales_order,
)

_prepare_adapter = TypeAdapter(PrepareQuotationToSalesOrderResult)
_confirm_adapter = TypeAdapter(ConfirmQuotationToSalesOrderResult)


def _with_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") == "ready":
        return {**result, "interaction": approval_directive().model_dump(mode="json")}
    return result


def prepare_quotation_to_sales_order(
    quotation: str, ctx: Context
) -> PrepareQuotationToSalesOrderOutput:
    """Prepare a Draft Sales Order from a Submitted Customer Quotation using ERPNext native mapping."""

    request = QuotationToSalesOrderInput(quotation=quotation)
    result = execute_tool_with_context(
        ctx,
        "prepare_quotation_to_sales_order",
        lambda: _prepare_quotation_to_sales_order(request.quotation),
    )
    return PrepareQuotationToSalesOrderOutput(
        root=_prepare_adapter.validate_python(_with_interaction(result))
    )


def confirm_quotation_to_sales_order(
    approval_token: str, confirm: bool, ctx: Context
) -> ConfirmQuotationToSalesOrderOutput:
    """Create the reviewed Draft Sales Order after the configured approval guard succeeds."""

    request = QuotationToSalesOrderConfirmInput(
        approval_token=approval_token, confirm=confirm
    )
    result = execute_tool_with_context(
        ctx,
        "confirm_quotation_to_sales_order",
        lambda: _confirm_quotation_to_sales_order(request.approval_token, request.confirm),
    )
    return ConfirmQuotationToSalesOrderOutput(
        root=_confirm_adapter.validate_python(result)
    )


def register_quotation_to_sales_order_tools(mcp: Any) -> None:
    """Register the pair-specific conversion tools in the Sales profile."""

    mcp.tool(
        meta=tool_meta("prepare_quotation_to_sales_order"), structured_output=True
    )(prepare_quotation_to_sales_order)
    mcp.tool(
        meta=tool_meta("confirm_quotation_to_sales_order"), structured_output=True
    )(confirm_quotation_to_sales_order)

