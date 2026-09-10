"""Typed, permission-safe public contracts for Customer reads and queries."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError


PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
SortOrder = Literal["asc", "desc"]

CustomerField = Literal[
    "name",
    "customer_name",
    "customer_type",
    "customer_group",
    "territory",
    "email_id",
    "mobile_no",
    "tax_id",
    "disabled",
    "is_frozen",
    "account_manager",
    "default_currency",
    "default_price_list",
    "owner",
    "creation",
    "modified",
]
CustomerSortField = Literal[
    "name",
    "customer_name",
    "customer_type",
    "customer_group",
    "territory",
    "disabled",
    "creation",
    "modified",
]
CustomerGroupBy = Literal["customer_group", "territory", "customer_type", "disabled"]
CustomerMetric = Literal["count"]
CustomerFields = Annotated[list[CustomerField], Field(min_length=1)]
CustomerMetrics = Annotated[list[CustomerMetric], Field(min_length=1)]


class CustomerFilters(PublicContractModel):
    """Exact Customer filters and explicit creation/modified date ranges."""

    name: NonEmptyString | None = None
    customer_name: NonEmptyString | None = None
    customer_type: NonEmptyString | None = None
    customer_group: NonEmptyString | None = None
    territory: NonEmptyString | None = None
    email_id: NonEmptyString | None = None
    mobile_no: NonEmptyString | None = None
    tax_id: NonEmptyString | None = None
    disabled: bool | None = None
    is_frozen: bool | None = None
    account_manager: NonEmptyString | None = None
    owner: NonEmptyString | None = None
    created_from: date | None = None
    created_to: date | None = None
    modified_from: date | None = None
    modified_to: date | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        for start, end, label in (
            (self.created_from, self.created_to, "creation date"),
            (self.modified_from, self.modified_to, "modified date"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label.title()} start must not be after its end.")
        return self


class CustomerGetInput(PublicContractModel):
    customer: NonEmptyString
    fields: CustomerFields = Field(default_factory=lambda: ["name"])


class CustomerQueryInput(CustomerFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: CustomerSortField = "creation"
    sort_order: SortOrder = "desc"
    fields: CustomerFields = Field(default_factory=lambda: ["name", "customer_name"])


class CustomerAggregateInput(CustomerFilters):
    metrics: CustomerMetrics = Field(default_factory=lambda: ["count"])
    group_by: CustomerGroupBy | None = None


class CustomerDocument(PublicContractModel):
    name: str | None = None
    customer_name: str | None = None
    customer_type: str | None = None
    customer_group: str | None = None
    territory: str | None = None
    email_id: str | None = None
    mobile_no: str | None = None
    tax_id: str | None = None
    disabled: int | None = None
    is_frozen: int | None = None
    account_manager: str | None = None
    default_currency: str | None = None
    default_price_list: str | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None


class CustomerNotFound(PublicContractModel):
    status: Literal["not_found"]
    customer: NonEmptyString


class CustomerGetOk(PublicContractModel):
    status: Literal["ok"]
    document: CustomerDocument


CustomerGetResult = Annotated[CustomerGetOk | CustomerNotFound | ToolError, Field(discriminator="status")]


class CustomerGetOutput(RootModel[CustomerGetResult]):
    model_config = {"json_schema_extra": {"type": "object"}}


class CustomerQueryOk(PublicContractModel):
    status: Literal["ok"]
    customers: list[CustomerDocument]
    count: int
    limit: int
    offset: int


class CustomerQueryOutput(RootModel[Annotated[CustomerQueryOk | ToolError, Field(discriminator="status")]]):
    model_config = {"json_schema_extra": {"type": "object"}}


class CustomerAggregateRow(PublicContractModel):
    group_value: str | int | None = None
    count: int | None = None


class CustomerAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[CustomerMetric]
    group_by: CustomerGroupBy | None = None
    results: list[CustomerAggregateRow]


class CustomerAggregateOutput(
    RootModel[Annotated[CustomerAggregateOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}
