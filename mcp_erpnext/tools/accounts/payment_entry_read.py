"""Typed MCP wrappers for read-only Payment Entry intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.accounts.payment_entry_read import (
	DocumentStatus,
	NonNegativeOffset,
	PaymentEntryAggregateInput,
	PaymentEntryAggregateOutput,
	PaymentEntryFields,
	PaymentEntryGetInput,
	PaymentEntryGetOutput,
	PaymentEntryGroupBy,
	PaymentEntryMetrics,
	PaymentEntryQueryInput,
	PaymentEntryQueryOutput,
	PaymentEntryReferenceDoctype,
	PaymentEntrySortField,
	PaymentEntryStatus,
	PaymentEntryType,
	PositiveLimit,
	SortOrder,
)
from ...contracts.common import NonEmptyString
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.accounts import payment_entry_read as service


def get_payment_entry(
	name: NonEmptyString,
	ctx: Context,
	fields: PaymentEntryFields | None = None,
) -> PaymentEntryGetOutput:
	"""Retrieve selected fields and bounded native references from one Payment Entry."""
	request = PaymentEntryGetInput(
		name=name,
		fields=fields if fields is not None else PaymentEntryGetInput(name=name).fields,
	)
	result = execute_tool_with_context(
		ctx,
		"get_payment_entry",
		lambda: service.get_payment_entry(**request.model_dump()),
		rest_arguments=request.model_dump(mode="json"),
	)
	return PaymentEntryGetOutput.model_validate(result)


def query_payment_entries(
	ctx: Context,
	name: NonEmptyString | None = None,
	docstatus: DocumentStatus | None = None,
	status: PaymentEntryStatus | None = None,
	payment_type: PaymentEntryType | None = None,
	company: NonEmptyString | None = None,
	party_type: NonEmptyString | None = None,
	party: NonEmptyString | None = None,
	mode_of_payment: NonEmptyString | None = None,
	paid_from_account_currency: NonEmptyString | None = None,
	paid_to_account_currency: NonEmptyString | None = None,
	reference_no: NonEmptyString | None = None,
	posting_date_from: date | None = None,
	posting_date_to: date | None = None,
	created_from: date | None = None,
	created_to: date | None = None,
	modified_from: date | None = None,
	modified_to: date | None = None,
	paid_amount: float | None = None,
	paid_amount_min: float | None = None,
	paid_amount_max: float | None = None,
	received_amount: float | None = None,
	received_amount_min: float | None = None,
	received_amount_max: float | None = None,
	reference_doctype: PaymentEntryReferenceDoctype | None = None,
	reference_name: NonEmptyString | None = None,
	limit: PositiveLimit = 20,
	offset: NonNegativeOffset = 0,
	sort_by: PaymentEntrySortField = "posting_date",
	sort_order: SortOrder = "desc",
	fields: PaymentEntryFields | None = None,
) -> PaymentEntryQueryOutput:
	"""Query permitted Payment Entries with typed filters and bounded pagination."""
	values = {
		key: value
		for key, value in locals().items()
		if key not in {"ctx", "fields"} and value is not None
	}
	if fields is not None:
		values["fields"] = fields
	request = PaymentEntryQueryInput(**values)
	result = execute_tool_with_context(
		ctx,
		"query_payment_entries",
		lambda: service.query_payment_entries(request.model_dump()),
		rest_arguments=request.model_dump(mode="json"),
	)
	return PaymentEntryQueryOutput.model_validate(result)


def aggregate_payment_entries(
	ctx: Context,
	metrics: PaymentEntryMetrics | None = None,
	name: NonEmptyString | None = None,
	docstatus: DocumentStatus | None = None,
	status: PaymentEntryStatus | None = None,
	payment_type: PaymentEntryType | None = None,
	company: NonEmptyString | None = None,
	party_type: NonEmptyString | None = None,
	party: NonEmptyString | None = None,
	mode_of_payment: NonEmptyString | None = None,
	paid_from_account_currency: NonEmptyString | None = None,
	paid_to_account_currency: NonEmptyString | None = None,
	reference_no: NonEmptyString | None = None,
	posting_date_from: date | None = None,
	posting_date_to: date | None = None,
	created_from: date | None = None,
	created_to: date | None = None,
	modified_from: date | None = None,
	modified_to: date | None = None,
	paid_amount: float | None = None,
	paid_amount_min: float | None = None,
	paid_amount_max: float | None = None,
	received_amount: float | None = None,
	received_amount_min: float | None = None,
	received_amount_max: float | None = None,
	reference_doctype: PaymentEntryReferenceDoctype | None = None,
	reference_name: NonEmptyString | None = None,
	group_by: PaymentEntryGroupBy | None = None,
) -> PaymentEntryAggregateOutput:
	"""Calculate bounded, permission-aware Payment Entry metrics."""
	values = {
		key: value
		for key, value in locals().items()
		if key not in {"ctx", "metrics", "group_by"} and value is not None
	}
	request = PaymentEntryAggregateInput(
		**values,
		metrics=metrics if metrics is not None else ["count"],
		group_by=group_by,
	)
	result = execute_tool_with_context(
		ctx,
		"aggregate_payment_entries",
		lambda: service.aggregate_payment_entries(request.model_dump()),
		rest_arguments=request.model_dump(mode="json"),
	)
	return PaymentEntryAggregateOutput.model_validate(result)


def register_payment_entry_read_tools(mcp: Any) -> None:
	for tool in (get_payment_entry, query_payment_entries, aggregate_payment_entries):
		mcp.tool(meta=tool_meta(tool.__name__), structured_output=True)(tool)
