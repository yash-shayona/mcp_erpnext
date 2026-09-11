"""Typed, permission-safe public contracts for Sales Invoice reads and analytics."""

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

SalesInvoiceStatus = Literal[
	"Draft",
	"Return",
	"Credit Note Issued",
	"Submitted",
	"Paid",
	"Partly Paid",
	"Unpaid",
	"Unpaid and Discounted",
	"Partly Paid and Discounted",
	"Overdue and Discounted",
	"Overdue",
	"Cancelled",
	"Internal Transfer",
]

SalesInvoiceField = Literal[
	"name",
	"customer",
	"customer_name",
	"posting_date",
	"due_date",
	"docstatus",
	"status",
	"company",
	"is_return",
	"return_against",
	"is_debit_note",
	"currency",
	"conversion_rate",
	"selling_price_list",
	"price_list_currency",
	"total_qty",
	"base_total",
	"base_net_total",
	"total",
	"net_total",
	"base_grand_total",
	"grand_total",
	"base_total_taxes_and_charges",
	"total_taxes_and_charges",
	"total_advance",
	"outstanding_amount",
	"base_paid_amount",
	"paid_amount",
	"write_off_amount",
	"cost_center",
	"project",
	"territory",
	"customer_group",
	"sales_partner",
	"update_stock",
	"po_no",
	"po_date",
	"owner",
	"creation",
	"modified",
]
SalesInvoiceSortField = Literal[
	"name",
	"customer",
	"customer_name",
	"posting_date",
	"due_date",
	"status",
	"company",
	"currency",
	"grand_total",
	"outstanding_amount",
	"creation",
	"modified",
]
SalesInvoiceGroupBy = Literal[
	"customer",
	"customer_name",
	"status",
	"company",
	"currency",
	"is_return",
	"posting_date",
	"due_date",
	"customer_group",
	"territory",
	"docstatus",
]
SalesInvoiceMetric = Literal[
	"count",
	"sum_grand_total",
	"avg_grand_total",
	"min_grand_total",
	"max_grand_total",
	"sum_outstanding_amount",
	"sum_net_total",
	"sum_total_qty",
]
SalesInvoiceFields = Annotated[list[SalesInvoiceField], Field(min_length=1)]
SalesInvoiceMetrics = Annotated[list[SalesInvoiceMetric], Field(min_length=1)]


class SalesInvoiceFilters(PublicContractModel):
	"""Allowlisted Sales Invoice filters shared by query and aggregate tools."""

	name: NonEmptyString | None = None
	customer: NonEmptyString | None = None
	customer_name: NonEmptyString | None = None
	company: NonEmptyString | None = None
	docstatus: DocumentStatus | None = None
	status: SalesInvoiceStatus | None = None
	currency: NonEmptyString | None = None
	is_return: bool | None = None
	return_against: NonEmptyString | None = None
	is_debit_note: bool | None = None
	selling_price_list: NonEmptyString | None = None
	price_list_currency: NonEmptyString | None = None
	cost_center: NonEmptyString | None = None
	project: NonEmptyString | None = None
	customer_group: NonEmptyString | None = None
	territory: NonEmptyString | None = None
	sales_partner: NonEmptyString | None = None
	owner: NonEmptyString | None = None
	posting_date_from: date | None = None
	posting_date_to: date | None = None
	due_date_from: date | None = None
	due_date_to: date | None = None
	created_from: date | None = None
	created_to: date | None = None
	modified_from: date | None = None
	modified_to: date | None = None
	min_grand_total: Number | None = None
	max_grand_total: Number | None = None
	min_outstanding_amount: Number | None = None
	max_outstanding_amount: Number | None = None
	min_net_total: Number | None = None
	max_net_total: Number | None = None

	@model_validator(mode="after")
	def validate_ranges(self):
		for start, end, label in (
			(self.posting_date_from, self.posting_date_to, "posting date"),
			(self.due_date_from, self.due_date_to, "due date"),
			(self.created_from, self.created_to, "creation date"),
			(self.modified_from, self.modified_to, "modified date"),
		):
			if start and end and start > end:
				raise ValueError(f"{label.title()} start must not be after its end.")
		for minimum, maximum, label in (
			(self.min_grand_total, self.max_grand_total, "grand total"),
			(self.min_outstanding_amount, self.max_outstanding_amount, "outstanding amount"),
			(self.min_net_total, self.max_net_total, "net total"),
		):
			if minimum is not None and maximum is not None and minimum > maximum:
				raise ValueError(f"Minimum {label} must not exceed maximum {label}.")
		return self


class SalesInvoiceQueryInput(SalesInvoiceFilters):
	limit: PositiveLimit = 20
	offset: NonNegativeOffset = 0
	sort_by: SalesInvoiceSortField = "posting_date"
	sort_order: SortOrder = "desc"
	fields: SalesInvoiceFields = Field(
		default_factory=lambda: [
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
	)


class SalesInvoiceGetInput(PublicContractModel):
	sales_invoice: NonEmptyString
	fields: SalesInvoiceFields = Field(
		default_factory=lambda: [
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
		]
	)


class SalesInvoiceAggregateInput(SalesInvoiceFilters):
	metrics: SalesInvoiceMetrics = Field(default_factory=lambda: ["count"])
	group_by: SalesInvoiceGroupBy | None = None


class SalesInvoiceDocument(PublicContractModel):
	name: str | None = None
	customer: str | None = None
	customer_name: str | None = None
	posting_date: date | None = None
	due_date: date | None = None
	docstatus: int | None = None
	status: str | None = None
	company: str | None = None
	is_return: int | None = None
	return_against: str | None = None
	is_debit_note: int | None = None
	currency: str | None = None
	conversion_rate: float | None = None
	selling_price_list: str | None = None
	price_list_currency: str | None = None
	total_qty: float | None = None
	base_total: float | None = None
	base_net_total: float | None = None
	total: float | None = None
	net_total: float | None = None
	base_grand_total: float | None = None
	grand_total: float | None = None
	base_total_taxes_and_charges: float | None = None
	total_taxes_and_charges: float | None = None
	total_advance: float | None = None
	outstanding_amount: float | None = None
	base_paid_amount: float | None = None
	paid_amount: float | None = None
	write_off_amount: float | None = None
	cost_center: str | None = None
	project: str | None = None
	territory: str | None = None
	customer_group: str | None = None
	sales_partner: str | None = None
	update_stock: int | None = None
	po_no: str | None = None
	po_date: date | None = None
	owner: str | None = None
	creation: str | None = None
	modified: str | None = None


class SalesInvoiceNotFound(PublicContractModel):
	status: Literal["not_found"]
	sales_invoice: NonEmptyString


class SalesInvoiceGetOk(PublicContractModel):
	status: Literal["ok"]
	document: SalesInvoiceDocument


SalesInvoiceGetResult = Annotated[
	SalesInvoiceGetOk | SalesInvoiceNotFound | ToolError, Field(discriminator="status")
]


class SalesInvoiceGetOutput(RootModel[SalesInvoiceGetResult]):
	model_config = {"json_schema_extra": {"type": "object"}}


class SalesInvoiceQueryOk(PublicContractModel):
	status: Literal["ok"]
	sales_invoices: list[SalesInvoiceDocument]
	count: int
	limit: int
	offset: int


class SalesInvoiceQueryOutput(
	RootModel[Annotated[SalesInvoiceQueryOk | ToolError, Field(discriminator="status")]]
):
	model_config = {"json_schema_extra": {"type": "object"}}


class SalesInvoiceAggregateRow(PublicContractModel):
	group_value: str | int | date | None = None
	currency: str | None = None
	count: int | None = None
	sum_grand_total: float | None = None
	avg_grand_total: float | None = None
	min_grand_total: float | None = None
	max_grand_total: float | None = None
	sum_outstanding_amount: float | None = None
	sum_net_total: float | None = None
	sum_total_qty: float | None = None


class SalesInvoiceAggregateOk(PublicContractModel):
	status: Literal["ok"]
	metrics: list[SalesInvoiceMetric]
	group_by: SalesInvoiceGroupBy | None = None
	results: list[SalesInvoiceAggregateRow]


class SalesInvoiceAggregateOutput(
	RootModel[Annotated[SalesInvoiceAggregateOk | ToolError, Field(discriminator="status")]]
):
	model_config = {"json_schema_extra": {"type": "object"}}
