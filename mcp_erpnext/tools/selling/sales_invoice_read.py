"""Typed MCP wrappers for read-only Sales Invoice intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.registry import tool_meta
from ...contracts.selling.sales_invoice_read import (
	DocumentStatus,
	Number,
	NonNegativeOffset,
	PositiveLimit,
	SalesInvoiceAggregateInput,
	SalesInvoiceAggregateOutput,
	SalesInvoiceFields,
	SalesInvoiceGetInput,
	SalesInvoiceGetOutput,
	SalesInvoiceGroupBy,
	SalesInvoiceMetrics,
	SalesInvoiceQueryInput,
	SalesInvoiceQueryOutput,
	SalesInvoiceSortField,
	SalesInvoiceStatus,
	SortOrder,
)
from ...runtime import execute_tool_with_context
from ...services.selling import sales_invoice_read as service


def get_sales_invoice(
	sales_invoice: NonEmptyString,
	ctx: Context,
	fields: SalesInvoiceFields | None = None,
) -> SalesInvoiceGetOutput:
	"""Retrieve selected fields from one permitted Sales Invoice by exact reference."""
	request = SalesInvoiceGetInput(
		sales_invoice=sales_invoice,
		fields=fields
		or [
			"name",
			"customer",
			"customer_name",
			"posting_date",
			"due_date",
			"docstatus",
			"status",
			"currency",
			"grand_total",
			"outstanding_amount",
			"is_return",
			"return_against",
		],
	)
	result = execute_tool_with_context(
		ctx, "get_sales_invoice", lambda: service.get_sales_invoice(**request.model_dump())
	)
	return SalesInvoiceGetOutput.model_validate(result)


def query_sales_invoices(
	ctx: Context,
	name: NonEmptyString | None = None,
	customer: NonEmptyString | None = None,
	customer_name: NonEmptyString | None = None,
	company: NonEmptyString | None = None,
	docstatus: DocumentStatus | None = None,
	status: SalesInvoiceStatus | None = None,
	currency: NonEmptyString | None = None,
	is_return: bool | None = None,
	return_against: NonEmptyString | None = None,
	is_debit_note: bool | None = None,
	selling_price_list: NonEmptyString | None = None,
	price_list_currency: NonEmptyString | None = None,
	cost_center: NonEmptyString | None = None,
	project: NonEmptyString | None = None,
	customer_group: NonEmptyString | None = None,
	territory: NonEmptyString | None = None,
	sales_partner: NonEmptyString | None = None,
	owner: NonEmptyString | None = None,
	posting_date_from: date | None = None,
	posting_date_to: date | None = None,
	due_date_from: date | None = None,
	due_date_to: date | None = None,
	created_from: date | None = None,
	created_to: date | None = None,
	modified_from: date | None = None,
	modified_to: date | None = None,
	min_grand_total: Number | None = None,
	max_grand_total: Number | None = None,
	min_outstanding_amount: Number | None = None,
	max_outstanding_amount: Number | None = None,
	min_net_total: Number | None = None,
	max_net_total: Number | None = None,
	limit: PositiveLimit = 20,
	offset: NonNegativeOffset = 0,
	sort_by: SalesInvoiceSortField = "posting_date",
	sort_order: SortOrder = "desc",
	fields: SalesInvoiceFields | None = None,
) -> SalesInvoiceQueryOutput:
	"""Query permitted Sales Invoices with typed filters, projection, and pagination."""
	values = {
		key: value
		for key, value in locals().items()
		if key not in {"ctx", "fields"} and value is not None
	}
	values["fields"] = fields or [
		"name",
		"customer",
		"customer_name",
		"posting_date",
		"due_date",
		"status",
		"currency",
		"grand_total",
		"outstanding_amount",
	]
	request = SalesInvoiceQueryInput(**values)
	result = execute_tool_with_context(
		ctx,
		"query_sales_invoices",
		lambda: service.query_sales_invoices(request.model_dump()),
	)
	return SalesInvoiceQueryOutput.model_validate(result)


def aggregate_sales_invoices(
	ctx: Context,
	metrics: SalesInvoiceMetrics | None = None,
	name: NonEmptyString | None = None,
	customer: NonEmptyString | None = None,
	customer_name: NonEmptyString | None = None,
	company: NonEmptyString | None = None,
	docstatus: DocumentStatus | None = None,
	status: SalesInvoiceStatus | None = None,
	currency: NonEmptyString | None = None,
	is_return: bool | None = None,
	return_against: NonEmptyString | None = None,
	is_debit_note: bool | None = None,
	selling_price_list: NonEmptyString | None = None,
	price_list_currency: NonEmptyString | None = None,
	cost_center: NonEmptyString | None = None,
	project: NonEmptyString | None = None,
	customer_group: NonEmptyString | None = None,
	territory: NonEmptyString | None = None,
	sales_partner: NonEmptyString | None = None,
	owner: NonEmptyString | None = None,
	posting_date_from: date | None = None,
	posting_date_to: date | None = None,
	due_date_from: date | None = None,
	due_date_to: date | None = None,
	created_from: date | None = None,
	created_to: date | None = None,
	modified_from: date | None = None,
	modified_to: date | None = None,
	min_grand_total: Number | None = None,
	max_grand_total: Number | None = None,
	min_outstanding_amount: Number | None = None,
	max_outstanding_amount: Number | None = None,
	min_net_total: Number | None = None,
	max_net_total: Number | None = None,
	group_by: SalesInvoiceGroupBy | None = None,
) -> SalesInvoiceAggregateOutput:
	"""Calculate deterministic permission-aware Sales Invoice metrics on the server."""
	values = {
		key: value
		for key, value in locals().items()
		if key not in {"ctx", "metrics", "group_by"} and value is not None
	}
	validated = SalesInvoiceAggregateInput(
		**values,
		metrics=metrics or ["count"],
		group_by=group_by,
	)
	result = execute_tool_with_context(
		ctx,
		"aggregate_sales_invoices",
		lambda: service.aggregate_sales_invoices(validated.model_dump()),
	)
	return SalesInvoiceAggregateOutput.model_validate(result)


def register_sales_invoice_read_tools(mcp: Any) -> None:
	for tool in (get_sales_invoice, query_sales_invoices, aggregate_sales_invoices):
		mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
