"""Typed, permission-safe public contracts for Purchase Order intelligence."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..read import DocumentReadInput


def _reject_boolean(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid numeric filters.")
    return value


NonNegativeNumber = Annotated[float, Field(ge=0), BeforeValidator(_reject_boolean)]
PositiveLimit = Annotated[int, Field(ge=1, le=100)]
NonNegativeOffset = Annotated[int, Field(ge=0)]
DocumentStatus = Annotated[int, Field(ge=0, le=2)]
SortOrder = Literal["asc", "desc"]
PurchaseOrderHeaderField = Literal[
    "name",
    "transaction_date",
    "schedule_date",
    "supplier",
    "supplier_name",
    "company",
    "status",
    "currency",
    "grand_total",
    "rounded_total",
    "total_qty",
    "per_received",
    "per_billed",
    "buying_price_list",
    "owner",
    "creation",
    "modified",
]
PurchaseOrderSortField = Literal[
    "name", "transaction_date", "schedule_date", "creation", "modified", "grand_total"
]
PurchaseOrderMetric = Literal[
    "count",
    "sum_grand_total",
    "avg_grand_total",
    "min_grand_total",
    "max_grand_total",
    "sum_total_qty",
]
PurchaseOrderGroupBy = Literal["status", "supplier", "company", "transaction_date"]
PurchaseOrderItemField = Literal[
    "purchase_order",
    "transaction_date",
    "supplier",
    "supplier_name",
    "company",
    "currency",
    "purchase_order_status",
    "item_code",
    "item_name",
    "qty",
    "rate",
    "amount",
    "received_qty",
    "billed_amt",
    "schedule_date",
    "warehouse",
]
PurchaseOrderItemSortField = Literal[
    "purchase_order",
    "transaction_date",
    "creation",
    "modified",
    "qty",
    "rate",
    "amount",
    "schedule_date",
]
PurchaseOrderItemMetric = Literal[
    "count_rows",
    "count_distinct_orders",
    "sum_qty",
    "sum_amount",
    "min_rate",
    "max_rate",
    "avg_rate",
]
PurchaseOrderItemGroupBy = Literal["item_code", "supplier", "transaction_date"]
PurchaseOrderHeaderFields = Annotated[
    list[PurchaseOrderHeaderField], Field(min_length=1)
]
PurchaseOrderItemFields = Annotated[list[PurchaseOrderItemField], Field(min_length=1)]
PurchaseOrderMetrics = Annotated[list[PurchaseOrderMetric], Field(min_length=1)]


class PurchaseOrderFilters(PublicContractModel):
    transaction_date_from: date | None = None
    transaction_date_to: date | None = None
    schedule_date_from: date | None = None
    schedule_date_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    supplier: NonEmptyString | None = None
    company: NonEmptyString | None = None
    status: NonEmptyString | None = None
    docstatus: DocumentStatus | None = None
    item_code: NonEmptyString | None = None
    owner: NonEmptyString | None = None
    currency: NonEmptyString | None = None
    buying_price_list: NonEmptyString | None = None
    min_grand_total: NonNegativeNumber | None = None
    max_grand_total: NonNegativeNumber | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        for start, end, label in (
            (self.transaction_date_from, self.transaction_date_to, "transaction date"),
            (self.schedule_date_from, self.schedule_date_to, "schedule date"),
            (self.created_from, self.created_to, "creation date"),
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


class PurchaseOrderQueryInput(PurchaseOrderFilters):
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: PurchaseOrderSortField = "transaction_date"
    sort_order: SortOrder = "desc"
    fields: PurchaseOrderHeaderFields = Field(default_factory=lambda: ["name"])


class GetPurchaseOrderInput(PublicContractModel):
    """Current typed request plus the original generic exact-target request."""

    purchase_order: NonEmptyString | None = None
    request: DocumentReadInput | None = None
    fields: PurchaseOrderHeaderFields = Field(default_factory=lambda: ["name"])
    include_items: bool = False
    item_fields: PurchaseOrderItemFields = Field(
        default_factory=lambda: ["item_code", "item_name", "qty", "rate", "amount"]
    )

    @model_validator(mode="after")
    def validate_target(self):
        if (self.purchase_order is None) == (self.request is None):
            raise ValueError("Provide either purchase_order or the legacy request target.")
        if self.request is not None and self.request.target.doctype != "Purchase Order":
            raise ValueError("The legacy request target must be a Purchase Order.")
        if self.request is not None and (
            self.fields != ["name"] or self.include_items or self.item_fields != ["item_code", "item_name", "qty", "rate", "amount"]
        ):
            raise ValueError("Projection options cannot be combined with a legacy request.")
        return self


class PurchaseOrderAggregateInput(PurchaseOrderFilters):
    item_code: None = Field(default=None, exclude=True)
    metrics: PurchaseOrderMetrics
    group_by: PurchaseOrderGroupBy | None = None


class PurchaseOrderItemQueryInput(PublicContractModel):
    supplier: NonEmptyString | None = None
    item_code: NonEmptyString | None = None
    transaction_date_from: date | None = None
    transaction_date_to: date | None = None
    purchase_order: NonEmptyString | None = None
    purchase_order_status: NonEmptyString | None = None
    min_qty: NonNegativeNumber | None = None
    max_qty: NonNegativeNumber | None = None
    limit: PositiveLimit = 20
    offset: NonNegativeOffset = 0
    sort_by: PurchaseOrderItemSortField = "transaction_date"
    sort_order: SortOrder = "desc"
    fields: PurchaseOrderItemFields | None = None
    metrics: list[PurchaseOrderItemMetric] = Field(default_factory=list)
    group_by: PurchaseOrderItemGroupBy | None = None

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


class PurchaseOrderHeader(PublicContractModel):
    name: str | None = None
    transaction_date: date | None = None
    schedule_date: date | None = None
    supplier: str | None = None
    supplier_name: str | None = None
    company: str | None = None
    status: str | None = None
    currency: str | None = None
    grand_total: float | None = None
    rounded_total: float | None = None
    total_qty: float | None = None
    per_received: float | None = None
    per_billed: float | None = None
    buying_price_list: str | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None


class PurchaseOrderLegacyItem(PublicContractModel):
    item_code: str | None = None
    item_name: str | None = None
    qty: float | None = None
    rate: float | None = None
    amount: float | None = None


class PurchaseOrderLegacyDocument(PublicContractModel):
    doctype: Literal["Purchase Order"]
    name: NonEmptyString
    docstatus: int
    status: str | None = None
    party: str | None = None
    transaction_date: date | None = None
    secondary_date: date | None = None
    currency: str | None = None
    grand_total: float | None = None
    items: list[PurchaseOrderLegacyItem] | None = None


class PurchaseOrderItem(PublicContractModel):
    purchase_order: str | None = None
    transaction_date: date | None = None
    supplier: str | None = None
    supplier_name: str | None = None
    company: str | None = None
    currency: str | None = None
    purchase_order_status: str | None = None
    item_code: str | None = None
    item_name: str | None = None
    qty: float | None = None
    rate: float | None = None
    amount: float | None = None
    received_qty: float | None = None
    billed_amt: float | None = None
    schedule_date: date | None = None
    warehouse: str | None = None


class PurchaseOrderNotFound(PublicContractModel):
    status: Literal["not_found"]
    purchase_order: NonEmptyString | None = None
    doctype: Literal["Purchase Order"] | None = None
    name: NonEmptyString | None = None


class PurchaseOrderGetOk(PublicContractModel):
    status: Literal["ok"]
    document: PurchaseOrderHeader | PurchaseOrderLegacyDocument
    items: list[PurchaseOrderItem] | None = None


GetPurchaseOrderResult = Annotated[
    PurchaseOrderGetOk | PurchaseOrderNotFound | ToolError,
    Field(discriminator="status"),
]


class GetPurchaseOrderOutput(RootModel[GetPurchaseOrderResult]):
    model_config = {"json_schema_extra": {"type": "object"}}


class PurchaseOrderQueryOk(PublicContractModel):
    status: Literal["ok"]
    purchase_orders: list[PurchaseOrderHeader]
    count: int
    limit: int
    offset: int


class PurchaseOrderQueryOutput(
    RootModel[
        Annotated[PurchaseOrderQueryOk | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class PurchaseOrderAggregateRow(PublicContractModel):
    group_value: str | date | None = None
    currency: str | None = None
    count: int | None = None
    sum_grand_total: float | None = None
    avg_grand_total: float | None = None
    min_grand_total: float | None = None
    max_grand_total: float | None = None
    sum_total_qty: float | None = None


class PurchaseOrderAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[PurchaseOrderMetric]
    group_by: PurchaseOrderGroupBy | None = None
    results: list[PurchaseOrderAggregateRow]


class PurchaseOrderAggregateOutput(
    RootModel[
        Annotated[PurchaseOrderAggregateOk | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class PurchaseOrderItemAggregateRow(PublicContractModel):
    group_value: str | date | None = None
    currency: str | None = None
    count_rows: int | None = None
    count_distinct_orders: int | None = None
    sum_qty: float | None = None
    sum_amount: float | None = None
    min_rate: float | None = None
    max_rate: float | None = None
    avg_rate: float | None = None


class PurchaseOrderItemQueryOk(PublicContractModel):
    status: Literal["ok"]
    items: list[PurchaseOrderItem]
    count: int
    limit: int
    offset: int
    metrics: list[PurchaseOrderItemMetric]
    group_by: PurchaseOrderItemGroupBy | None = None
    aggregates: list[PurchaseOrderItemAggregateRow]


class PurchaseOrderItemQueryOutput(
    RootModel[
        Annotated[PurchaseOrderItemQueryOk | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}
