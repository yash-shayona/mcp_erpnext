"""Typed, allowlisted Delivery Note read and analytics contracts."""

from __future__ import annotations
from datetime import date
from typing import Annotated, Literal
from pydantic import BeforeValidator, Field, RootModel, model_validator
from ..common import NonEmptyString, PublicContractModel, ToolError


def _number(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid numeric filters.")
    return value


PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
Number = Annotated[float, BeforeValidator(_number)]
DocumentStatus = Annotated[int, Field(ge=0, le=2)]
SortOrder = Literal["asc", "desc"]
DeliveryNoteField = Literal[
    "name",
    "customer",
    "customer_name",
    "posting_date",
    "posting_time",
    "docstatus",
    "status",
    "company",
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
    "total_taxes_and_charges",
    "base_total_taxes_and_charges",
    "is_return",
    "return_against",
    "per_billed",
    "per_installed",
    "owner",
    "creation",
    "modified",
]
DeliveryNoteSortField = Literal[
    "name",
    "customer",
    "customer_name",
    "posting_date",
    "status",
    "company",
    "currency",
    "grand_total",
    "total_qty",
    "creation",
    "modified",
]
DeliveryNoteGroupBy = Literal[
    "customer",
    "customer_name",
    "status",
    "company",
    "currency",
    "is_return",
    "posting_date",
    "docstatus",
]
DeliveryNoteMetric = Literal[
    "count",
    "sum_grand_total",
    "avg_grand_total",
    "min_grand_total",
    "max_grand_total",
    "sum_net_total",
    "sum_total_qty",
]
DeliveryNoteFields = Annotated[list[DeliveryNoteField], Field(min_length=1)]
DeliveryNoteMetrics = Annotated[list[DeliveryNoteMetric], Field(min_length=1)]


class DeliveryNoteFilters(PublicContractModel):
    name: NonEmptyString | None = None
    customer: NonEmptyString | None = None
    customer_name: NonEmptyString | None = None
    company: NonEmptyString | None = None
    docstatus: DocumentStatus | None = None
    status: NonEmptyString | None = None
    currency: NonEmptyString | None = None
    selling_price_list: NonEmptyString | None = None
    price_list_currency: NonEmptyString | None = None
    is_return: bool | None = None
    return_against: NonEmptyString | None = None
    owner: NonEmptyString | None = None
    posting_date_from: date | None = None
    posting_date_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    modified_from: date | None = None
    modified_to: date | None = None
    min_grand_total: Number | None = None
    max_grand_total: Number | None = None
    min_net_total: Number | None = None
    max_net_total: Number | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        for start, end, label in (
            (self.posting_date_from, self.posting_date_to, "posting date"),
            (self.created_from, self.created_to, "creation date"),
            (self.modified_from, self.modified_to, "modified date"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label.title()} start must not be after its end.")
        for minimum, maximum, label in (
            (self.min_grand_total, self.max_grand_total, "grand total"),
            (self.min_net_total, self.max_net_total, "net total"),
        ):
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"Minimum {label} must not exceed maximum {label}.")
        return self


class DeliveryNoteQueryInput(DeliveryNoteFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: DeliveryNoteSortField = "posting_date"
    sort_order: SortOrder = "desc"
    fields: DeliveryNoteFields = Field(
        default_factory=lambda: [
            "name",
            "customer",
            "customer_name",
            "posting_date",
            "status",
            "currency",
            "grand_total",
        ]
    )


class DeliveryNoteGetInput(PublicContractModel):
    delivery_note: NonEmptyString
    fields: DeliveryNoteFields = Field(
        default_factory=lambda: [
            "name",
            "customer",
            "customer_name",
            "posting_date",
            "docstatus",
            "status",
            "currency",
            "grand_total",
        ]
    )


class DeliveryNoteAggregateInput(DeliveryNoteFilters):
    metrics: DeliveryNoteMetrics = Field(default_factory=lambda: ["count"])
    group_by: DeliveryNoteGroupBy | None = None


class DeliveryNoteDocument(PublicContractModel):
    name: str | None = None
    customer: str | None = None
    customer_name: str | None = None
    posting_date: date | None = None
    posting_time: str | None = None
    docstatus: int | None = None
    status: str | None = None
    company: str | None = None
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
    total_taxes_and_charges: float | None = None
    base_total_taxes_and_charges: float | None = None
    is_return: int | bool | None = None
    return_against: str | None = None
    per_billed: float | None = None
    per_installed: float | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None


class DeliveryNoteNotFound(PublicContractModel):
    status: Literal["not_found"]
    delivery_note: NonEmptyString


class DeliveryNoteGetOk(PublicContractModel):
    status: Literal["ok"]
    document: DeliveryNoteDocument


class DeliveryNoteGetOutput(
    RootModel[
        Annotated[
            DeliveryNoteGetOk | DeliveryNoteNotFound | ToolError,
            Field(discriminator="status"),
        ]
    ]
):
    pass


class DeliveryNoteQueryOk(PublicContractModel):
    status: Literal["ok"]
    delivery_notes: list[DeliveryNoteDocument]
    count: int
    limit: int
    offset: int


class DeliveryNoteQueryOutput(
    RootModel[Annotated[DeliveryNoteQueryOk | ToolError, Field(discriminator="status")]]
):
    pass


class DeliveryNoteAggregateRow(PublicContractModel):
    group_value: str | date | None = None
    currency: str | None = None
    count: int | None = None
    sum_grand_total: float | None = None
    avg_grand_total: float | None = None
    min_grand_total: float | None = None
    max_grand_total: float | None = None
    sum_net_total: float | None = None
    sum_total_qty: float | None = None


class DeliveryNoteAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[str]
    group_by: str | None = None
    results: list[DeliveryNoteAggregateRow]


class DeliveryNoteAggregateOutput(
    RootModel[
        Annotated[DeliveryNoteAggregateOk | ToolError, Field(discriminator="status")]
    ]
):
    pass
