"""Typed, permission-safe public contracts for Quotation reads and analytics."""

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
NonNegativeNumber = Annotated[float, Field(ge=0), BeforeValidator(_reject_boolean)]
DocumentStatus = Annotated[int, Field(ge=0, le=2)]
SortOrder = Literal["asc", "desc"]

QuotationField = Literal[
	"name",
	"quotation_to",
	"party_name",
	"customer_name",
	"transaction_date",
	"valid_till",
	"order_type",
	"company",
	"docstatus",
	"status",
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
	"additional_discount_percentage",
	"discount_amount",
	"referral_sales_partner",
	"customer_group",
	"territory",
	"owner",
	"creation",
	"modified",
]
QuotationSortField = Literal[
	"name",
	"party_name",
	"customer_name",
	"transaction_date",
	"valid_till",
	"order_type",
	"status",
	"company",
	"grand_total",
	"net_total",
	"total_qty",
	"creation",
	"modified",
]
QuotationGroupBy = Literal[
	"quotation_to",
	"party_name",
	"customer_name",
	"status",
	"company",
	"currency",
	"order_type",
	"customer_group",
	"territory",
	"transaction_date",
]
QuotationMetric = Literal[
	"count",
	"sum_grand_total",
	"avg_grand_total",
	"min_grand_total",
	"max_grand_total",
	"sum_net_total",
	"sum_total_qty",
]
QuotationFields = Annotated[list[QuotationField], Field(min_length=1)]
QuotationMetrics = Annotated[list[QuotationMetric], Field(min_length=1)]


class QuotationFilters(PublicContractModel):
	"""Allowlisted Quotation header filters shared by query and aggregate tools."""

	name: NonEmptyString | None = None
	quotation_to: NonEmptyString | None = None
	party_name: NonEmptyString | None = None
	customer_name: NonEmptyString | None = None
	order_type: NonEmptyString | None = None
	company: NonEmptyString | None = None
	docstatus: DocumentStatus | None = None
	status: NonEmptyString | None = None
	currency: NonEmptyString | None = None
	selling_price_list: NonEmptyString | None = None
	price_list_currency: NonEmptyString | None = None
	referral_sales_partner: NonEmptyString | None = None
	customer_group: NonEmptyString | None = None
	territory: NonEmptyString | None = None
	owner: NonEmptyString | None = None
	transaction_date_from: date | None = None
	transaction_date_to: date | None = None
	valid_till_from: date | None = None
	valid_till_to: date | None = None
	created_from: date | None = None
	created_to: date | None = None
	modified_from: date | None = None
	modified_to: date | None = None
	min_grand_total: NonNegativeNumber | None = None
	max_grand_total: NonNegativeNumber | None = None
	min_net_total: NonNegativeNumber | None = None
	max_net_total: NonNegativeNumber | None = None
	min_total_qty: NonNegativeNumber | None = None
	max_total_qty: NonNegativeNumber | None = None

	@model_validator(mode="after")
	def validate_ranges(self):
		for start, end, label in (
			(self.transaction_date_from, self.transaction_date_to, "transaction date"),
			(self.valid_till_from, self.valid_till_to, "valid till date"),
			(self.created_from, self.created_to, "creation date"),
			(self.modified_from, self.modified_to, "modified date"),
		):
			if start and end and start > end:
				raise ValueError(f"{label.title()} start must not be after its end.")
		for minimum, maximum, label in (
			(self.min_grand_total, self.max_grand_total, "grand total"),
			(self.min_net_total, self.max_net_total, "net total"),
			(self.min_total_qty, self.max_total_qty, "total quantity"),
		):
			if minimum is not None and maximum is not None and minimum > maximum:
				raise ValueError(f"Minimum {label} must not exceed maximum {label}.")
		return self


class QuotationQueryInput(QuotationFilters):
	limit: PositiveLimit = 20
	offset: NonNegativeOffset = 0
	sort_by: QuotationSortField = "transaction_date"
	sort_order: SortOrder = "desc"
	fields: QuotationFields = Field(
		default_factory=lambda: [
			"name",
			"party_name",
			"customer_name",
			"transaction_date",
			"valid_till",
			"status",
			"currency",
			"grand_total",
		]
	)


class QuotationGetInput(PublicContractModel):
	quotation: NonEmptyString
	fields: QuotationFields = Field(
		default_factory=lambda: [
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
		]
	)


class QuotationAggregateInput(QuotationFilters):
	metrics: QuotationMetrics = Field(default_factory=lambda: ["count"])
	group_by: QuotationGroupBy | None = None


class QuotationDocument(PublicContractModel):
	name: str | None = None
	quotation_to: str | None = None
	party_name: str | None = None
	customer_name: str | None = None
	transaction_date: date | None = None
	valid_till: date | None = None
	order_type: str | None = None
	company: str | None = None
	docstatus: int | None = None
	status: str | None = None
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
	additional_discount_percentage: float | None = None
	discount_amount: float | None = None
	referral_sales_partner: str | None = None
	customer_group: str | None = None
	territory: str | None = None
	owner: str | None = None
	creation: str | None = None
	modified: str | None = None


class QuotationNotFound(PublicContractModel):
	status: Literal["not_found"]
	quotation: NonEmptyString


class QuotationGetOk(PublicContractModel):
	status: Literal["ok"]
	document: QuotationDocument


QuotationGetResult = Annotated[QuotationGetOk | QuotationNotFound | ToolError, Field(discriminator="status")]


class QuotationGetOutput(RootModel[QuotationGetResult]):
	model_config = {"json_schema_extra": {"type": "object"}}


class QuotationQueryOk(PublicContractModel):
	status: Literal["ok"]
	quotations: list[QuotationDocument]
	count: int
	limit: int
	offset: int


class QuotationQueryOutput(
	RootModel[Annotated[QuotationQueryOk | ToolError, Field(discriminator="status")]]
):
	model_config = {"json_schema_extra": {"type": "object"}}


class QuotationAggregateRow(PublicContractModel):
	group_value: str | date | None = None
	currency: str | None = None
	count: int | None = None
	sum_grand_total: float | None = None
	avg_grand_total: float | None = None
	min_grand_total: float | None = None
	max_grand_total: float | None = None
	sum_net_total: float | None = None
	sum_total_qty: float | None = None


class QuotationAggregateOk(PublicContractModel):
	status: Literal["ok"]
	metrics: list[QuotationMetric]
	group_by: QuotationGroupBy | None = None
	results: list[QuotationAggregateRow]


class QuotationAggregateOutput(
	RootModel[Annotated[QuotationAggregateOk | ToolError, Field(discriminator="status")]]
):
	model_config = {"json_schema_extra": {"type": "object"}}
