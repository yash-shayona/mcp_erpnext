"""Typed MCP wrappers for read-only Quotation intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.registry import tool_meta
from ...contracts.selling.quotation_read import (
	DocumentStatus,
	NonNegativeNumber,
	NonNegativeOffset,
	PositiveLimit,
	QuotationAggregateInput,
	QuotationAggregateOutput,
	QuotationFields,
	QuotationGetInput,
	QuotationGetOutput,
	QuotationGroupBy,
	QuotationMetrics,
	QuotationQueryInput,
	QuotationQueryOutput,
	QuotationSortField,
	SortOrder,
)
from ...runtime import execute_tool_with_context
from ...services.selling import quotation_read as service


def get_quotation(
	quotation: NonEmptyString,
	ctx: Context,
	fields: QuotationFields | None = None,
) -> QuotationGetOutput:
	"""Retrieve selected fields from one permitted Quotation by exact reference."""
	request = QuotationGetInput(
		quotation=quotation,
		fields=fields
		or [
			"name",
			"quotation_to",
			"party_name",
			"customer_name",
			"transaction_date",
			"valid_till",
			"docstatus",
			"status",
			"currency",
			"grand_total",
		],
	)
	result = execute_tool_with_context(
		ctx, "get_quotation", lambda: service.get_quotation(**request.model_dump())
	)
	return QuotationGetOutput.model_validate(result)


def query_quotations(
	ctx: Context,
	name: NonEmptyString | None = None,
	quotation_to: NonEmptyString | None = None,
	party_name: NonEmptyString | None = None,
	customer_name: NonEmptyString | None = None,
	order_type: NonEmptyString | None = None,
	company: NonEmptyString | None = None,
	docstatus: DocumentStatus | None = None,
	status: NonEmptyString | None = None,
	currency: NonEmptyString | None = None,
	selling_price_list: NonEmptyString | None = None,
	price_list_currency: NonEmptyString | None = None,
	referral_sales_partner: NonEmptyString | None = None,
	customer_group: NonEmptyString | None = None,
	territory: NonEmptyString | None = None,
	owner: NonEmptyString | None = None,
	transaction_date_from: date | None = None,
	transaction_date_to: date | None = None,
	valid_till_from: date | None = None,
	valid_till_to: date | None = None,
	created_from: date | None = None,
	created_to: date | None = None,
	modified_from: date | None = None,
	modified_to: date | None = None,
	min_grand_total: NonNegativeNumber | None = None,
	max_grand_total: NonNegativeNumber | None = None,
	min_net_total: NonNegativeNumber | None = None,
	max_net_total: NonNegativeNumber | None = None,
	min_total_qty: NonNegativeNumber | None = None,
	max_total_qty: NonNegativeNumber | None = None,
	limit: PositiveLimit = 20,
	offset: NonNegativeOffset = 0,
	sort_by: QuotationSortField = "transaction_date",
	sort_order: SortOrder = "desc",
	fields: QuotationFields | None = None,
) -> QuotationQueryOutput:
	"""Query permitted Quotations with typed filters, projection, sorting, and pagination."""
	values = {
		key: value
		for key, value in locals().items()
		if key != "ctx" and value is not None
	}
	request = QuotationQueryInput(**values)
	result = execute_tool_with_context(
		ctx,
		"query_quotations",
		lambda: service.query_quotations(request.model_dump()),
	)
	return QuotationQueryOutput.model_validate(result)


def aggregate_quotations(
	ctx: Context,
	metrics: QuotationMetrics | None = None,
	name: NonEmptyString | None = None,
	quotation_to: NonEmptyString | None = None,
	party_name: NonEmptyString | None = None,
	customer_name: NonEmptyString | None = None,
	order_type: NonEmptyString | None = None,
	company: NonEmptyString | None = None,
	docstatus: DocumentStatus | None = None,
	status: NonEmptyString | None = None,
	currency: NonEmptyString | None = None,
	selling_price_list: NonEmptyString | None = None,
	price_list_currency: NonEmptyString | None = None,
	referral_sales_partner: NonEmptyString | None = None,
	customer_group: NonEmptyString | None = None,
	territory: NonEmptyString | None = None,
	owner: NonEmptyString | None = None,
	transaction_date_from: date | None = None,
	transaction_date_to: date | None = None,
	valid_till_from: date | None = None,
	valid_till_to: date | None = None,
	created_from: date | None = None,
	created_to: date | None = None,
	modified_from: date | None = None,
	modified_to: date | None = None,
	min_grand_total: NonNegativeNumber | None = None,
	max_grand_total: NonNegativeNumber | None = None,
	min_net_total: NonNegativeNumber | None = None,
	max_net_total: NonNegativeNumber | None = None,
	min_total_qty: NonNegativeNumber | None = None,
	max_total_qty: NonNegativeNumber | None = None,
	group_by: QuotationGroupBy | None = None,
) -> QuotationAggregateOutput:
	"""Calculate deterministic permission-aware Quotation metrics on the server."""
	values = {
		key: value
		for key, value in locals().items()
		if key != "ctx" and value is not None
	}
	request = QuotationAggregateInput(**values)
	result = execute_tool_with_context(
		ctx,
		"aggregate_quotations",
		lambda: service.aggregate_quotations(request.model_dump()),
	)
	return QuotationAggregateOutput.model_validate(result)


def register_quotation_read_tools(mcp: Any) -> None:
	for tool in (get_quotation, query_quotations, aggregate_quotations):
		mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
