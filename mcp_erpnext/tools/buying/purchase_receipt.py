"""Typed MCP wrappers for Purchase Receipt draft conversion."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.buying.purchase_receipt import (
    ConfirmPurchaseReceiptOutput,
    ConfirmPurchaseReceiptResult,
    PreparePurchaseReceiptOutput,
    PreparePurchaseReceiptResult,
    PurchaseReceiptConfirmInput,
    PurchaseReceiptLineInput,
    PurchaseReceiptPrepareInput,
)
from ...contracts.common import NonEmptyString
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.buying import purchase_order_to_purchase_receipt as service


def prepare_purchase_order_to_purchase_receipt(
    purchase_order: NonEmptyString,
    lines: list[PurchaseReceiptLineInput],
    ctx: Context,
    posting_date: date | None = None,
    supplier_delivery_note: str | None = None,
) -> PreparePurchaseReceiptOutput:
    request = PurchaseReceiptPrepareInput(
        purchase_order=purchase_order,
        lines=lines,
        posting_date=posting_date,
        supplier_delivery_note=supplier_delivery_note,
    )
    result = execute_tool_with_context(
        ctx,
        "prepare_purchase_order_to_purchase_receipt",
        lambda: service.prepare_purchase_order_to_purchase_receipt(
            request.purchase_order,
            [line.model_dump() for line in request.lines],
            request.posting_date.isoformat() if request.posting_date else None,
            request.supplier_delivery_note,
        ),
        rest_arguments=request.model_dump(mode="json"),
    )
    return PreparePurchaseReceiptOutput(
        root=TypeAdapter(PreparePurchaseReceiptResult).validate_python(result)
    )


def confirm_purchase_order_to_purchase_receipt(
    approval_token: NonEmptyString, confirm: bool, ctx: Context
) -> ConfirmPurchaseReceiptOutput:
    request = PurchaseReceiptConfirmInput(approval_token=approval_token, confirm=confirm)
    result = execute_tool_with_context(
        ctx,
        "confirm_purchase_order_to_purchase_receipt",
        lambda: service.confirm_purchase_order_to_purchase_receipt(
            request.approval_token, request.confirm
        ),
        rest_arguments=request.model_dump(mode="json"),
    )
    return ConfirmPurchaseReceiptOutput(
        root=TypeAdapter(ConfirmPurchaseReceiptResult).validate_python(result)
    )


def execute_purchase_order_to_purchase_receipt(request: PurchaseReceiptPrepareInput, ctx: Context) -> ConfirmPurchaseReceiptOutput:
	request = PurchaseReceiptPrepareInput.model_validate(request)
	result = execute_tool_with_context(
		ctx, "execute_purchase_order_to_purchase_receipt",
		lambda: service.execute_purchase_order_to_purchase_receipt(
			request.purchase_order, [row.model_dump() for row in request.lines],
			request.posting_date.isoformat() if request.posting_date else None,
			request.supplier_delivery_note,
		),
		rest_arguments=request.model_dump(mode="json"),
	)
	return ConfirmPurchaseReceiptOutput(root=TypeAdapter(ConfirmPurchaseReceiptResult).validate_python(result))


def register_purchase_receipt_tools(mcp: Any) -> None:
    mcp.tool(
        meta=tool_meta("prepare_purchase_order_to_purchase_receipt"),
        structured_output=True,
    )(prepare_purchase_order_to_purchase_receipt)
    mcp.tool(
        meta=tool_meta("confirm_purchase_order_to_purchase_receipt"),
        structured_output=True,
    )(confirm_purchase_order_to_purchase_receipt)
    mcp.tool(meta=tool_meta("execute_purchase_order_to_purchase_receipt"), structured_output=True)(execute_purchase_order_to_purchase_receipt)
