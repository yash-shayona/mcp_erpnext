"""Typed, permission-safe public contracts for Sales Order intelligence reads."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError


def _reject_boolean(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid numeric filters.")
    return value


NonNegativeNumber = Annotated[float, Field(ge=0), BeforeValidator(_reject_boolean)]
PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
DocumentStatus = Annotated[int, Field(ge=0, le=2)]

SalesOrderHeaderField = Literal[
    "name",
    "transaction_date",
    "customer",
    "customer_name",
    "status",
    "delivery_status",
    "billing_status",
    "delivery_date",
    "currency",
    "grand_total",
    "total_qty",
    "per_delivered",
    "per_billed",
    "customer_group",
    "territory",
    "owner",
    "creation",
    "modified",
]
SalesOrderSortField = Literal[
    "name", "transaction_date", "creation", "modified", "delivery_date", "grand_total"
]
SortOrder = Literal["asc", "desc"]
SalesOrderMetric = Literal[
    "count",
    "sum_grand_total",
    "avg_grand_total",
    "min_grand_total",
    "max_grand_total",
    "sum_total_qty",
]
SalesOrderGroupBy = Literal[
    "status", "customer", "customer_group", "territory", "transaction_date"
]
SalesOrderItemField = Literal[
    "sales_order",
    "transaction_date",
    "customer",
    "customer_name",
    "currency",
    "sales_order_status",
    "item_code",
    "item_name",
    "qty",
    "rate",
    "amount",
    "discount_percentage",
    "discount_amount",
    "delivered_qty",
    "delivery_date",
]
SalesOrderItemSortField = Literal[
    "sales_order",
    "transaction_date",
    "creation",
    "modified",
    "qty",
    "rate",
    "amount",
    "delivery_date",
]
SalesOrderItemMetric = Literal[
    "count_rows",
    "count_distinct_orders",
    "sum_qty",
    "sum_amount",
    "min_rate",
    "max_rate",
    "avg_rate",
]
SalesOrderItemGroupBy = Literal["item_code", "customer", "transaction_date"]
SalesOrderHeaderFields = Annotated[list[SalesOrderHeaderField], Field(min_length=1)]
SalesOrderItemFields = Annotated[list[SalesOrderItemField], Field(min_length=1)]
SalesOrderMetrics = Annotated[list[SalesOrderMetric], Field(min_length=1)]


class SalesOrderFilters(PublicContractModel):
    """Allowlisted Sales Order filters shared by search and aggregate tools."""

    transaction_date_from: date | None = None
    transaction_date_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    delivery_date_from: date | None = None
    delivery_date_to: date | None = None
    customer: NonEmptyString | None = None
    customer_group: NonEmptyString | None = None
    territory: NonEmptyString | None = None
    status: NonEmptyString | None = None
    delivery_status: NonEmptyString | None = None
    billing_status: NonEmptyString | None = None
    docstatus: DocumentStatus | None = None
    item_code: NonEmptyString | None = None
    sales_person: NonEmptyString | None = None
    owner: NonEmptyString | None = None
    currency: NonEmptyString | None = None
    min_grand_total: NonNegativeNumber | None = None
    max_grand_total: NonNegativeNumber | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        for start, end, label in (
            (self.transaction_date_from, self.transaction_date_to, "transaction date"),
            (self.created_from, self.created_to, "creation date"),
            (self.delivery_date_from, self.delivery_date_to, "delivery date"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label.title()} start must not be after its end.")
        if (
            self.min_grand_total is not None
            and self.max_grand_total is not None
            and self.min_grand_total > self.max_grand_total
        ):
            raise ValueError("Minimum grand total must not exceed maximum grand total.")
        return self


class SalesOrderSearchInput(SalesOrderFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: SalesOrderSortField = "transaction_date"
    sort_order: SortOrder = "desc"
    fields: SalesOrderHeaderFields = Field(default_factory=lambda: ["name"])


class GetSalesOrderInput(PublicContractModel):
    sales_order: NonEmptyString
    fields: SalesOrderHeaderFields = Field(default_factory=lambda: ["name"])
    include_items: bool = False
    item_fields: SalesOrderItemFields = Field(
        default_factory=lambda: ["item_code", "item_name", "qty", "rate", "amount"]
    )


class SalesOrderAggregateInput(SalesOrderFilters):
    """Server-side metrics over permission-filtered Sales Orders.

    Item and Sales Team joins are deliberately not accepted here: joining either
    child table can duplicate a header and make monetary metrics incorrect.
    Use the item-history tool for item analytics.
    """

    item_code: None = Field(default=None, exclude=True)
    sales_person: None = Field(default=None, exclude=True)
    metrics: SalesOrderMetrics
    group_by: SalesOrderGroupBy | None = None


class SalesOrderItemQueryInput(PublicContractModel):
    customer: NonEmptyString | None = None
    item_code: NonEmptyString | None = None
    transaction_date_from: date | None = None
    transaction_date_to: date | None = None
    sales_order: NonEmptyString | None = None
    sales_order_status: NonEmptyString | None = None
    min_qty: NonNegativeNumber | None = None
    max_qty: NonNegativeNumber | None = None
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: SalesOrderItemSortField = "transaction_date"
    sort_order: SortOrder = "desc"
    fields: SalesOrderItemFields | None = None
    metrics: list[SalesOrderItemMetric] = Field(default_factory=list)
    group_by: SalesOrderItemGroupBy | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        if (
            self.transaction_date_from
            and self.transaction_date_to
            and self.transaction_date_from > self.transaction_date_to
        ):
            raise ValueError("Transaction date start must not be after its end.")
        if (
            self.min_qty is not None
            and self.max_qty is not None
            and self.min_qty > self.max_qty
        ):
            raise ValueError("Minimum quantity must not exceed maximum quantity.")
        return self


class SalesOrderHeader(PublicContractModel):
    name: str | None = None
    transaction_date: date | None = None
    customer: str | None = None
    customer_name: str | None = None
    status: str | None = None
    delivery_status: str | None = None
    billing_status: str | None = None
    delivery_date: date | None = None
    currency: str | None = None
    grand_total: float | None = None
    total_qty: float | None = None
    per_delivered: float | None = None
    per_billed: float | None = None
    customer_group: str | None = None
    territory: str | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None


class SalesOrderItem(PublicContractModel):
    sales_order: str | None = None
    transaction_date: date | None = None
    customer: str | None = None
    customer_name: str | None = None
    currency: str | None = None
    sales_order_status: str | None = None
    item_code: str | None = None
    item_name: str | None = None
    qty: float | None = None
    rate: float | None = None
    amount: float | None = None
    discount_percentage: float | None = None
    discount_amount: float | None = None
    delivered_qty: float | None = None
    delivery_date: date | None = None


class SalesOrderNotFound(PublicContractModel):
    status: Literal["not_found"]
    sales_order: NonEmptyString


class SalesOrderGetOk(PublicContractModel):
    status: Literal["ok"]
    document: SalesOrderHeader
    items: list[SalesOrderItem] | None = None


GetSalesOrderResult = Annotated[
    SalesOrderGetOk | SalesOrderNotFound | ToolError, Field(discriminator="status")
]


class GetSalesOrderOutput(RootModel[GetSalesOrderResult]):
    model_config = {"json_schema_extra": {"type": "object"}}


class SalesOrderSearchOk(PublicContractModel):
    status: Literal["ok"]
    sales_orders: list[SalesOrderHeader]
    count: int
    limit: int
    offset: int


class SalesOrderSearchOutput(
    RootModel[Annotated[SalesOrderSearchOk | ToolError, Field(discriminator="status")]]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class SalesOrderAggregateRow(PublicContractModel):
    group_value: str | date | None = None
    currency: str | None = None
    count: int | None = None
    sum_grand_total: float | None = None
    avg_grand_total: float | None = None
    min_grand_total: float | None = None
    max_grand_total: float | None = None
    sum_total_qty: float | None = None


class SalesOrderAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[SalesOrderMetric]
    group_by: SalesOrderGroupBy | None = None
    results: list[SalesOrderAggregateRow]


class SalesOrderAggregateOutput(
    RootModel[
        Annotated[SalesOrderAggregateOk | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class SalesOrderItemAggregateRow(PublicContractModel):
    group_value: str | date | None = None
    currency: str | None = None
    count_rows: int | None = None
    count_distinct_orders: int | None = None
    sum_qty: float | None = None
    sum_amount: float | None = None
    min_rate: float | None = None
    max_rate: float | None = None
    avg_rate: float | None = None


class SalesOrderItemQueryOk(PublicContractModel):
    status: Literal["ok"]
    items: list[SalesOrderItem]
    count: int
    limit: int
    offset: int
    metrics: list[SalesOrderItemMetric]
    group_by: SalesOrderItemGroupBy | None = None
    aggregates: list[SalesOrderItemAggregateRow]


class SalesOrderItemQueryOutput(
    RootModel[
        Annotated[SalesOrderItemQueryOk | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}
