"""Typed, permission-safe public contracts for Item reads and queries."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError


PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
SortOrder = Literal["asc", "desc"]

ItemField = Literal[
    "name",
    "item_code",
    "item_name",
    "item_group",
    "stock_uom",
    "disabled",
    "is_sales_item",
    "is_purchase_item",
    "is_stock_item",
    "brand",
    "description",
    "sales_uom",
    "owner",
    "creation",
    "modified",
]
ItemSortField = Literal[
    "name",
    "item_code",
    "item_name",
    "item_group",
    "disabled",
    "creation",
    "modified",
]
ItemGroupBy = Literal[
    "item_group",
    "brand",
    "disabled",
    "is_sales_item",
    "is_purchase_item",
    "is_stock_item",
]
ItemMetric = Literal["count"]
ItemFields = Annotated[list[ItemField], Field(min_length=1)]
ItemMetrics = Annotated[list[ItemMetric], Field(min_length=1)]


class ItemFilters(PublicContractModel):
    """Exact Item filters and explicit creation/modified date ranges."""

    name: NonEmptyString | None = None
    item_code: NonEmptyString | None = None
    item_name: NonEmptyString | None = None
    item_group: NonEmptyString | None = None
    stock_uom: NonEmptyString | None = None
    disabled: bool | None = None
    is_sales_item: bool | None = None
    is_purchase_item: bool | None = None
    is_stock_item: bool | None = None
    brand: NonEmptyString | None = None
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


class ItemGetInput(PublicContractModel):
    item: NonEmptyString
    fields: ItemFields = Field(default_factory=lambda: ["name"])


class ItemQueryInput(ItemFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: ItemSortField = "creation"
    sort_order: SortOrder = "desc"
    fields: ItemFields = Field(default_factory=lambda: ["name", "item_code", "item_name"])


class ItemAggregateInput(ItemFilters):
    metrics: ItemMetrics = Field(default_factory=lambda: ["count"])
    group_by: ItemGroupBy | None = None


class ItemDocument(PublicContractModel):
    name: str | None = None
    item_code: str | None = None
    item_name: str | None = None
    item_group: str | None = None
    stock_uom: str | None = None
    disabled: int | None = None
    is_sales_item: int | None = None
    is_purchase_item: int | None = None
    is_stock_item: int | None = None
    brand: str | None = None
    description: str | None = None
    sales_uom: str | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None


class ItemNotFound(PublicContractModel):
    status: Literal["not_found"]
    item: NonEmptyString


class ItemGetOk(PublicContractModel):
    status: Literal["ok"]
    document: ItemDocument


ItemGetResult = Annotated[ItemGetOk | ItemNotFound | ToolError, Field(discriminator="status")]


class ItemGetOutput(RootModel[ItemGetResult]):
    model_config = {"json_schema_extra": {"type": "object"}}


class ItemQueryOk(PublicContractModel):
    status: Literal["ok"]
    items: list[ItemDocument]
    count: int
    limit: int
    offset: int


class ItemQueryOutput(
    RootModel[Annotated[ItemQueryOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class ItemAggregateRow(PublicContractModel):
    group_value: str | int | None = None
    count: int | None = None


class ItemAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[ItemMetric]
    group_by: ItemGroupBy | None = None
    results: list[ItemAggregateRow]


class ItemAggregateOutput(
    RootModel[Annotated[ItemAggregateOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}
