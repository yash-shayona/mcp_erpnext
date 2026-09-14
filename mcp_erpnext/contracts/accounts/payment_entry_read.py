"""Typed, bounded public contracts for Payment Entry reads and analytics."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError


def _reject_boolean(value: object) -> object:
	if isinstance(value, bool):
		raise ValueError("Boolean values are not valid numeric filters.")
	return value


PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
Number = Annotated[float, BeforeValidator(_reject_boolean)]
DocumentStatus = Annotated[int, Field(ge=0, le=2)]
SortOrder = Literal["asc", "desc"]

PaymentEntryType = Literal["Receive", "Pay", "Internal Transfer"]
PaymentEntryStatus = Literal["Draft", "Submitted", "Cancelled"]
PaymentEntryReferenceDoctype = Literal[
	"Sales Invoice",
	"Purchase Invoice",
	"Sales Order",
	"Purchase Order",
]

PaymentEntryField = Literal[
	"name",
	"docstatus",
	"status",
	"payment_type",
	"company",
	"posting_date",
	"party_type",
	"party",
	"party_name",
	"mode_of_payment",
	"paid_from",
	"paid_from_account_currency",
	"paid_to",
	"paid_to_account_currency",
	"paid_amount",
	"received_amount",
	"total_allocated_amount",
	"unallocated_amount",
	"difference_amount",
	"reference_no",
	"reference_date",
	"project",
	"remarks",
	"owner",
	"creation",
	"modified",
]
PaymentEntrySortField = Literal[
	"posting_date",
	"name",
	"modified",
	"paid_amount",
	"received_amount",
	"status",
	"payment_type",
]
PaymentEntryGroupBy = Literal[
	"docstatus",
	"status",
	"payment_type",
	"company",
	"party_type",
	"party",
	"mode_of_payment",
	"paid_from_account_currency",
	"paid_to_account_currency",
	"posting_date",
]
PaymentEntryMetric = Literal[
	"count",
	"sum_paid_amount",
	"sum_received_amount",
	"sum_total_allocated_amount",
	"sum_unallocated_amount",
]
PaymentEntryFields = Annotated[list[PaymentEntryField], Field(min_length=1)]
PaymentEntryMetrics = Annotated[list[PaymentEntryMetric], Field(min_length=1)]


class PaymentEntryFilters(PublicContractModel):
	"""Allowlisted Payment Entry filters shared by query and aggregate tools."""

	name: NonEmptyString | None = None
	docstatus: DocumentStatus | None = None
	status: PaymentEntryStatus | None = None
	payment_type: PaymentEntryType | None = None
	company: NonEmptyString | None = None
	party_type: NonEmptyString | None = None
	party: NonEmptyString | None = None
	mode_of_payment: NonEmptyString | None = None
	paid_from_account_currency: NonEmptyString | None = None
	paid_to_account_currency: NonEmptyString | None = None
	reference_no: NonEmptyString | None = None
	posting_date_from: date | None = None
	posting_date_to: date | None = None
	created_from: date | None = None
	created_to: date | None = None
	modified_from: date | None = None
	modified_to: date | None = None
	paid_amount: Number | None = None
	paid_amount_min: Number | None = None
	paid_amount_max: Number | None = None
	received_amount: Number | None = None
	received_amount_min: Number | None = None
	received_amount_max: Number | None = None
	reference_doctype: PaymentEntryReferenceDoctype | None = None
	reference_name: NonEmptyString | None = None

	@model_validator(mode="after")
	def validate_ranges_and_references(self):
		for start, end, label in (
			(self.posting_date_from, self.posting_date_to, "posting date"),
			(self.created_from, self.created_to, "creation date"),
			(self.modified_from, self.modified_to, "modified date"),
		):
			if start and end and start > end:
				raise ValueError(f"{label.title()} start must not be after its end.")
		for minimum, maximum, label in (
			(self.paid_amount_min, self.paid_amount_max, "paid amount"),
			(self.received_amount_min, self.received_amount_max, "received amount"),
		):
			if minimum is not None and maximum is not None and minimum > maximum:
				raise ValueError(f"Minimum {label} must not exceed maximum {label}.")
		if (self.reference_doctype is None) != (self.reference_name is None):
			raise ValueError("reference_doctype and reference_name must be provided together.")
		return self


class PaymentEntryGetInput(PublicContractModel):
	name: NonEmptyString
	fields: PaymentEntryFields = Field(
		default_factory=lambda: [
			"name",
			"docstatus",
			"status",
			"payment_type",
			"company",
			"posting_date",
			"party_type",
			"party",
			"party_name",
			"mode_of_payment",
			"paid_from",
			"paid_from_account_currency",
			"paid_to",
			"paid_to_account_currency",
			"paid_amount",
			"received_amount",
			"total_allocated_amount",
			"unallocated_amount",
			"difference_amount",
			"reference_no",
			"reference_date",
			"remarks",
			"modified",
		]
	)


class PaymentEntryQueryInput(PaymentEntryFilters):
	limit: PositiveLimit = 20
	offset: NonNegativeOffset = 0
	sort_by: PaymentEntrySortField = "posting_date"
	sort_order: SortOrder = "desc"
	fields: PaymentEntryFields = Field(
		default_factory=lambda: [
			"name",
			"docstatus",
			"status",
			"payment_type",
			"company",
			"posting_date",
			"party_type",
			"party",
			"party_name",
			"mode_of_payment",
			"paid_from_account_currency",
			"paid_to_account_currency",
			"paid_amount",
			"received_amount",
			"total_allocated_amount",
			"unallocated_amount",
		]
	)


class PaymentEntryAggregateInput(PaymentEntryFilters):
	metrics: PaymentEntryMetrics = Field(default_factory=lambda: ["count"])
	group_by: PaymentEntryGroupBy | None = None


class PaymentEntryReference(PublicContractModel):
	# Existing ERPNext Payment Entries may reference native DocTypes beyond the
	# bounded filter allowlist; the row remains a non-dereferenced identifier.
	reference_doctype: str | None = None
	reference_name: str | None = None
	bill_no: str | None = None
	due_date: date | None = None
	payment_term: str | None = None
	total_amount: float | None = None
	outstanding_amount: float | None = None
	allocated_amount: float | None = None
	exchange_rate: float | None = None


class PaymentEntryDocument(PublicContractModel):
	name: str | None = None
	docstatus: int | None = None
	status: str | None = None
	payment_type: str | None = None
	company: str | None = None
	posting_date: date | None = None
	party_type: str | None = None
	party: str | None = None
	party_name: str | None = None
	mode_of_payment: str | None = None
	paid_from: str | None = None
	paid_from_account_currency: str | None = None
	paid_to: str | None = None
	paid_to_account_currency: str | None = None
	paid_amount: float | None = None
	received_amount: float | None = None
	total_allocated_amount: float | None = None
	unallocated_amount: float | None = None
	difference_amount: float | None = None
	reference_no: str | None = None
	reference_date: date | None = None
	project: str | None = None
	remarks: str | None = None
	owner: str | None = None
	creation: str | None = None
	modified: str | None = None
	references: list[PaymentEntryReference] = Field(default_factory=list)


class PaymentEntryQueryDocument(PublicContractModel):
	name: str | None = None
	docstatus: int | None = None
	status: str | None = None
	payment_type: str | None = None
	company: str | None = None
	posting_date: date | None = None
	party_type: str | None = None
	party: str | None = None
	party_name: str | None = None
	mode_of_payment: str | None = None
	paid_from: str | None = None
	paid_from_account_currency: str | None = None
	paid_to: str | None = None
	paid_to_account_currency: str | None = None
	paid_amount: float | None = None
	received_amount: float | None = None
	total_allocated_amount: float | None = None
	unallocated_amount: float | None = None
	difference_amount: float | None = None
	reference_no: str | None = None
	reference_date: date | None = None
	project: str | None = None
	remarks: str | None = None
	owner: str | None = None
	creation: str | None = None
	modified: str | None = None


class PaymentEntryNotFound(PublicContractModel):
	status: Literal["not_found"]
	name: NonEmptyString


class PaymentEntryGetOk(PublicContractModel):
	status: Literal["ok"]
	document: PaymentEntryDocument


PaymentEntryGetResult = Annotated[
	PaymentEntryGetOk | PaymentEntryNotFound | ToolError,
	Field(discriminator="status"),
]


class PaymentEntryGetOutput(RootModel[PaymentEntryGetResult]):
	model_config = {"json_schema_extra": {"type": "object"}}


class PaymentEntryQueryOk(PublicContractModel):
	status: Literal["ok"]
	payment_entries: list[PaymentEntryQueryDocument]
	count: int
	limit: int
	offset: int


class PaymentEntryQueryOutput(
	RootModel[Annotated[PaymentEntryQueryOk | ToolError, Field(discriminator="status")]]
):
	model_config = {"json_schema_extra": {"type": "object"}}


class PaymentEntryAggregateRow(PublicContractModel):
	group_value: str | int | date | None = None
	paid_from_account_currency: str | None = None
	paid_to_account_currency: str | None = None
	count: int | None = None
	sum_paid_amount: float | None = None
	sum_received_amount: float | None = None
	sum_total_allocated_amount: float | None = None
	sum_unallocated_amount: float | None = None


class PaymentEntryAggregateOk(PublicContractModel):
	status: Literal["ok"]
	metrics: list[PaymentEntryMetric]
	group_by: PaymentEntryGroupBy | None = None
	results: list[PaymentEntryAggregateRow]


class PaymentEntryAggregateOutput(
	RootModel[Annotated[PaymentEntryAggregateOk | ToolError, Field(discriminator="status")]]
):
	model_config = {"json_schema_extra": {"type": "object"}}
