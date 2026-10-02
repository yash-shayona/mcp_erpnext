"""Typed, permission-safe public contracts for Supplier intelligence reads."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError

PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
SortOrder = Literal["asc", "desc"]
SupplierField = Literal[
    "name",
    "supplier_name",
    "supplier_group",
    "supplier_type",
    "country",
    "default_currency",
    "disabled",
    "owner",
    "creation",
    "modified",
]
SupplierSortField = Literal[
    "name",
    "supplier_name",
    "supplier_group",
    "supplier_type",
    "country",
    "disabled",
    "creation",
    "modified",
]
SupplierGroupBy = Literal["supplier_group", "supplier_type", "country", "disabled"]
SupplierMetric = Literal["count"]
SupplierFields = Annotated[list[SupplierField], Field(min_length=1)]
SupplierMetrics = Annotated[list[SupplierMetric], Field(min_length=1)]


class SupplierFilters(PublicContractModel):
    """Exact, non-PII Supplier filters and bounded date ranges."""

    name: NonEmptyString | None = None
    supplier_name: NonEmptyString | None = None
    supplier_group: NonEmptyString | None = None
    supplier_type: NonEmptyString | None = None
    country: NonEmptyString | None = None
    default_currency: NonEmptyString | None = None
    disabled: bool | None = None
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


class SupplierGetInput(PublicContractModel):
    supplier: NonEmptyString
    fields: SupplierFields = Field(default_factory=lambda: ["name"])


class SupplierQueryInput(SupplierFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: SupplierSortField = "creation"
    sort_order: SortOrder = "desc"
    fields: SupplierFields = Field(default_factory=lambda: ["name", "supplier_name"])


class SupplierAggregateInput(SupplierFilters):
    metrics: SupplierMetrics = Field(default_factory=lambda: ["count"])
    group_by: SupplierGroupBy | None = None


class SupplierDocument(PublicContractModel):
    name: str | None = None
    supplier_name: str | None = None
    supplier_group: str | None = None
    supplier_type: str | None = None
    country: str | None = None
    default_currency: str | None = None
    disabled: int | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None


class SupplierNotFound(PublicContractModel):
    status: Literal["not_found"]
    supplier: NonEmptyString


class SupplierGetOk(PublicContractModel):
    status: Literal["ok"]
    document: SupplierDocument


SupplierGetResult = Annotated[
    SupplierGetOk | SupplierNotFound | ToolError, Field(discriminator="status")
]


class SupplierGetOutput(RootModel[SupplierGetResult]):
    model_config = {"json_schema_extra": {"type": "object"}}


class SupplierQueryOk(PublicContractModel):
    status: Literal["ok"]
    suppliers: list[SupplierDocument]
    count: int
    limit: int
    offset: int


class SupplierQueryOutput(
    RootModel[Annotated[SupplierQueryOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class SupplierAggregateRow(PublicContractModel):
    group_value: str | int | None = None
    count: int | None = None


class SupplierAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[SupplierMetric]
    group_by: SupplierGroupBy | None = None
    results: list[SupplierAggregateRow]


class SupplierAggregateOutput(
    RootModel[Annotated[SupplierAggregateOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}
