"""Typed MCP wrappers for the two-phase Purchase Order workflow."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.buying.purchase_order import (
    ConfirmPurchaseOrderOutput,
    ConfirmPurchaseOrderResult,
    PreparePurchaseOrderOutput,
    PreparePurchaseOrderResult,
    PurchaseOrderConfirmInput,
    PurchaseOrderItemInput,
    PurchaseOrderPrepareInput,
)
from ...contracts.common import NonEmptyString, SupplierReference
from ...contracts.interaction import approval_directive, input_directive
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.buying.purchase_order import (
    confirm_purchase_order as _confirm_purchase_order,
    prepare_purchase_order as _prepare_purchase_order,
)


_prepare_adapter = TypeAdapter(PreparePurchaseOrderResult)
_confirm_adapter = TypeAdapter(ConfirmPurchaseOrderResult)


def _with_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") == "ready":
        return {**result, "interaction": approval_directive().model_dump(mode="json")}
    if result.get("status") == "needs_input":
        return {**result, "interaction": input_directive().model_dump(mode="json")}
    return result


def prepare_purchase_order(
    supplier: SupplierReference,
    items: list[PurchaseOrderItemInput],
    ctx: Context,
    company: NonEmptyString | None = None,
    transaction_date: date | None = None,
    schedule_date: date | None = None,
    buying_price_list: NonEmptyString | None = None,
    taxes_and_charges: NonEmptyString | None = None,
) -> PreparePurchaseOrderOutput:
    """Prepare an ERPNext-calculated Purchase Order preview without writing."""
    request = PurchaseOrderPrepareInput(
        supplier=supplier,
        items=items,
        company=company,
        transaction_date=transaction_date,
        schedule_date=schedule_date,
        buying_price_list=buying_price_list,
        taxes_and_charges=taxes_and_charges,
    )
    result = execute_tool_with_context(
        ctx,
        "prepare_purchase_order",
		lambda: _prepare_purchase_order(
            request.supplier.model_dump(),
            [item.to_service_payload() for item in request.items],
            request.company,
            request.transaction_date.isoformat() if request.transaction_date else None,
            request.schedule_date.isoformat() if request.schedule_date else None,
            request.buying_price_list,
            request.taxes_and_charges,
		),
		rest_arguments=request.model_dump(mode="json"),
    )
    return PreparePurchaseOrderOutput(root=_prepare_adapter.validate_python(_with_interaction(result)))


def confirm_purchase_order(
    approval_token: NonEmptyString, confirm: bool, ctx: Context
) -> ConfirmPurchaseOrderOutput:
    """Create a prepared Draft Purchase Order after explicit confirmation."""
    request = PurchaseOrderConfirmInput(approval_token=approval_token, confirm=confirm)
    result = execute_tool_with_context(
        ctx,
		"confirm_purchase_order",
		lambda: _confirm_purchase_order(request.approval_token, request.confirm),
		rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmPurchaseOrderOutput(root=_confirm_adapter.validate_python(result))


def register_purchase_order_tools(mcp: Any) -> None:
    mcp.tool(meta=tool_meta("prepare_purchase_order"), structured_output=True)(prepare_purchase_order)
    mcp.tool(meta=tool_meta("confirm_purchase_order"), structured_output=True)(confirm_purchase_order)
