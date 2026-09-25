"""MCP wrappers for the two-phase Sales Order workflow."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import CustomerReference, NonEmptyString
from ...contracts.interaction import approval_directive, input_directive
from ...contracts.registry import tool_meta
from ...contracts.selling.sales_order import (
	ConfirmSalesOrderOutput,
	PrepareSalesOrderOutput,
	SalesOrderConfirmInput,
	SalesOrderConfirmResult,
	SalesOrderItemInput,
	SalesOrderPrepareInput,
	SalesOrderPrepareResult,
)
from ...runtime import execute_tool_with_context
from ...services.selling.sales_order import (
	confirm_sales_order as _confirm_sales_order,
	prepare_sales_order as _prepare_sales_order,
)


_prepare_adapter = TypeAdapter(SalesOrderPrepareResult)
_confirm_adapter = TypeAdapter(SalesOrderConfirmResult)


def _with_interaction(result: dict[str, Any]) -> dict[str, Any]:
	"""Attach shared continuation guidance to preparation states only."""
	if result.get("status") == "ready":
		return {**result, "interaction": approval_directive().model_dump(mode="json")}
	if result.get("status") == "needs_input":
		return {**result, "interaction": input_directive().model_dump(mode="json")}
	return result


def prepare_sales_order(
	customer: CustomerReference,
	items: list[SalesOrderItemInput],
	ctx: Context,
	company: NonEmptyString | None = None,
	delivery_date: date | None = None,
	selling_price_list: NonEmptyString | None = None,
	tc_name: NonEmptyString | None = None,
	custom_remarks: str | None = None,
) -> PrepareSalesOrderOutput:
	"""Resolve inputs and return a Sales Order preview without writing anything."""
	request = SalesOrderPrepareInput(
		customer=customer,
		items=items,
		company=company,
		delivery_date=delivery_date,
		selling_price_list=selling_price_list,
		tc_name=tc_name,
		custom_remarks=custom_remarks,
	)
	result = execute_tool_with_context(
		ctx,
		"prepare_sales_order",
		lambda: _prepare_sales_order(
			request.customer.name,
			[item.to_service_payload() for item in request.items],
			request.company,
			request.delivery_date.isoformat() if request.delivery_date else None,
			request.selling_price_list,
			request.tc_name,
			request.custom_remarks,
		),
		rest_arguments=request.model_dump(mode="json"),
	)
	return PrepareSalesOrderOutput(
		root=_prepare_adapter.validate_python(_with_interaction(result))
	)


def confirm_sales_order(
	approval_token: NonEmptyString, confirm: bool, ctx: Context
) -> ConfirmSalesOrderOutput:
	"""Create the prepared Draft Sales Order after explicit confirmation."""
	request = SalesOrderConfirmInput(approval_token=approval_token, confirm=confirm)
	result = execute_tool_with_context(
		ctx,
		"confirm_sales_order",
		lambda: _confirm_sales_order(request.approval_token, request.confirm),
		rest_arguments=request.model_dump(mode="json"),
	)
	return ConfirmSalesOrderOutput(root=_confirm_adapter.validate_python(result))


def register_sales_order_tools(mcp: Any) -> None:
	"""Register the two public Selling capability tools."""

	mcp.tool(meta=tool_meta("prepare_sales_order"), structured_output=True)(prepare_sales_order)
	mcp.tool(meta=tool_meta("confirm_sales_order"), structured_output=True)(confirm_sales_order)
