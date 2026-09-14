"""MCP wrappers for the two-phase Draft Quotation workflow."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import CustomerReference, NonEmptyString
from ...contracts.interaction import approval_directive, input_directive
from ...contracts.registry import tool_meta
from ...contracts.selling.quotation import (
	ConfirmQuotationOutput,
	ConfirmQuotationResult,
	NonNegativeNumber,
	PrepareQuotationOutput,
	PrepareQuotationResult,
	QuotationConfirmInput,
	QuotationItemInput,
	QuotationItems,
	QuotationPrepareInput,
)
from ...runtime import execute_tool_with_context
from ...services.selling.quotation import (
	confirm_quotation as _confirm_quotation,
	prepare_quotation as _prepare_quotation,
)


_prepare_result_adapter = TypeAdapter(PrepareQuotationResult)
_confirm_result_adapter = TypeAdapter(ConfirmQuotationResult)


def _with_interaction(result: dict[str, Any]) -> dict[str, Any]:
	"""Attach client-neutral continuation guidance at the typed MCP boundary."""
	if result.get("status") == "ready":
		return {**result, "interaction": approval_directive().model_dump(mode="json")}
	if result.get("status") == "needs_input":
		return {**result, "interaction": input_directive().model_dump(mode="json")}
	return result


def prepare_quotation(
	customer: CustomerReference,
	items: QuotationItems,
	valid_till: date,
	ctx: Context,
	company: NonEmptyString | None = None,
	transaction_date: date | None = None,
	selling_price_list: NonEmptyString | None = None,
	taxes_and_charges: NonEmptyString | None = None,
	additional_discount_percentage: NonNegativeNumber | None = None,
	discount_amount: NonNegativeNumber | None = None,
	tc_name: NonEmptyString | None = None,
) -> PrepareQuotationOutput:
	"""Prepare an ERPNext-calculated Draft Quotation preview without writing."""
	request = QuotationPrepareInput(
		customer=customer,
		items=items,
		valid_till=valid_till,
		company=company,
		transaction_date=transaction_date,
		selling_price_list=selling_price_list,
		taxes_and_charges=taxes_and_charges,
		additional_discount_percentage=additional_discount_percentage,
		discount_amount=discount_amount,
		tc_name=tc_name,
	)
	result = execute_tool_with_context(
		ctx,
		"prepare_quotation",
		lambda: _prepare_quotation(
			request.customer.model_dump(),
			[item.to_service_payload() for item in request.items],
			request.valid_till.isoformat(),
			request.company,
			request.transaction_date.isoformat() if request.transaction_date else None,
			request.selling_price_list,
			request.taxes_and_charges,
			request.additional_discount_percentage,
			request.discount_amount,
			request.tc_name,
		),
		rest_arguments=request.model_dump(mode="json"),
	)
	return PrepareQuotationOutput(root=_prepare_result_adapter.validate_python(_with_interaction(result)))


def confirm_quotation(approval_token: str, confirm: bool, ctx: Context) -> ConfirmQuotationOutput:
	"""Create the prepared Draft Quotation after explicit confirmation."""
	request = QuotationConfirmInput(approval_token=approval_token, confirm=confirm)
	result = execute_tool_with_context(
		ctx, "confirm_quotation", lambda: _confirm_quotation(request.approval_token, request.confirm), rest_arguments=request.model_dump(mode="json")
	)
	return ConfirmQuotationOutput(root=_confirm_result_adapter.validate_python(result))


def register_quotation_tools(mcp: Any) -> None:
	"""Register only the explicit Quotation prepare/confirm tools."""

	mcp.tool(meta=tool_meta("prepare_quotation"), structured_output=True)(prepare_quotation)
	mcp.tool(meta=tool_meta("confirm_quotation"), structured_output=True)(confirm_quotation)
