"""Bounded exact Purchase Receipt read contracts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError

PurchaseReceiptHeaderField = Literal[
    "name", "supplier", "supplier_name", "company", "posting_date", "posting_time",
    "docstatus", "status", "currency", "total_qty", "grand_total", "per_billed",
    "is_return", "return_against", "supplier_delivery_note", "owner", "creation", "modified",
]
PurchaseReceiptItemField = Literal[
    "name", "item_code", "item_name", "purchase_order", "purchase_order_item", "qty",
    "rejected_qty", "received_qty", "uom", "stock_uom", "conversion_factor", "warehouse",
    "rejected_warehouse", "rate", "amount", "quality_inspection",
]
PurchaseReceiptHeaderFields = Annotated[list[PurchaseReceiptHeaderField], Field(min_length=1)]
PurchaseReceiptItemFields = Annotated[list[PurchaseReceiptItemField], Field(min_length=1)]


class GetPurchaseReceiptInput(PublicContractModel):
    purchase_receipt: NonEmptyString
    fields: PurchaseReceiptHeaderFields = Field(default_factory=lambda: ["name"])
    include_items: bool = False
    item_fields: PurchaseReceiptItemFields = Field(
        default_factory=lambda: ["name", "item_code", "purchase_order", "purchase_order_item", "qty", "rejected_qty"]
    )


class PurchaseReceiptItem(PublicContractModel):
    name: str | None = None
    item_code: str | None = None
    item_name: str | None = None
    purchase_order: str | None = None
    purchase_order_item: str | None = None
    qty: float | None = None
    rejected_qty: float | None = None
    received_qty: float | None = None
    uom: str | None = None
    stock_uom: str | None = None
    conversion_factor: float | None = None
    warehouse: str | None = None
    rejected_warehouse: str | None = None
    rate: float | None = None
    amount: float | None = None
    quality_inspection: str | None = None


class PurchaseReceiptDocument(PublicContractModel):
    name: str | None = None
    supplier: str | None = None
    supplier_name: str | None = None
    company: str | None = None
    posting_date: date | None = None
    posting_time: str | None = None
    docstatus: int | None = None
    status: str | None = None
    currency: str | None = None
    total_qty: float | None = None
    grand_total: float | None = None
    per_billed: float | None = None
    is_return: int | bool | None = None
    return_against: str | None = None
    supplier_delivery_note: str | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None
    items: list[PurchaseReceiptItem] | None = None


class PurchaseReceiptNotFound(PublicContractModel):
    status: Literal["not_found"]
    purchase_receipt: NonEmptyString


class PurchaseReceiptGetOk(PublicContractModel):
    status: Literal["ok"]
    document: PurchaseReceiptDocument


class GetPurchaseReceiptOutput(RootModel[Annotated[PurchaseReceiptGetOk | PurchaseReceiptNotFound | ToolError, Field(discriminator="status")]]):
    pass


# Structured reads use a separate projection from the frozen exact-read API.
def _number(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numeric filter")
    return value

Number = Annotated[float, Field(ge=0), BeforeValidator(_number)]
Limit = Annotated[int, Field(ge=1, le=100)]
Offset = Annotated[int, Field(ge=0)]
Docstatus = Annotated[int, Field(ge=0, le=2)]
SortOrder = Literal["asc", "desc"]
HeaderField = Literal["name", "supplier", "supplier_name", "posting_date", "posting_time", "docstatus", "status", "company", "currency", "conversion_rate", "buying_price_list", "price_list_currency", "total_qty", "grand_total", "per_billed", "per_returned", "is_return", "return_against", "supplier_delivery_note", "owner", "creation", "modified"]
HeaderSort = Literal["name", "posting_date", "creation", "modified", "grand_total", "total_qty", "supplier", "status"]
HeaderMetric = Literal["count", "sum_grand_total", "avg_grand_total", "min_grand_total", "max_grand_total", "sum_total_qty"]
HeaderGroup = Literal["status", "supplier", "company", "posting_date", "docstatus", "is_return", "currency"]
ItemField = Literal["name", "purchase_receipt", "posting_date", "supplier", "supplier_name", "company", "currency", "purchase_receipt_status", "docstatus", "is_return", "return_against", "item_code", "item_name", "purchase_order", "purchase_order_item", "qty", "rejected_qty", "received_qty", "stock_qty", "uom", "stock_uom", "conversion_factor", "rate", "amount", "net_rate", "net_amount", "billed_amt", "warehouse", "rejected_warehouse", "schedule_date", "quality_inspection", "is_fixed_asset"]
ItemSort = Literal["purchase_receipt", "posting_date", "creation", "modified", "qty", "received_qty", "rejected_qty", "rate", "amount"]
ItemMetric = Literal["count_rows", "count_distinct_receipts", "sum_qty", "sum_received_qty", "sum_rejected_qty", "sum_amount", "min_rate", "max_rate", "avg_rate"]
ItemGroup = Literal["item_code", "supplier", "posting_date", "warehouse", "purchase_order"]
HeaderFields = Annotated[list[HeaderField], Field(min_length=1)]
ItemFields = Annotated[list[ItemField], Field(min_length=1)]
HeaderMetrics = Annotated[list[HeaderMetric], Field(min_length=1)]


class ReceiptFilters(PublicContractModel):
    name: NonEmptyString | None = None
    supplier: NonEmptyString | None = None
    company: NonEmptyString | None = None
    docstatus: Docstatus | None = None
    status: NonEmptyString | None = None
    currency: NonEmptyString | None = None
    owner: NonEmptyString | None = None
    is_return: bool | None = None
    return_against: NonEmptyString | None = None
    posting_date_from: date | None = None
    posting_date_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    modified_from: date | None = None
    modified_to: date | None = None
    min_grand_total: Number | None = None
    max_grand_total: Number | None = None

    @model_validator(mode="after")
    def ranges(self):
        for start, end in ((self.posting_date_from, self.posting_date_to), (self.created_from, self.created_to), (self.modified_from, self.modified_to), (self.min_grand_total, self.max_grand_total)):
            if start is not None and end is not None and start > end:
                raise ValueError("Range start must not exceed end")
        return self


class ReceiptQueryInput(ReceiptFilters):
    item_code: NonEmptyString | None = None
    purchase_order: NonEmptyString | None = None
    limit: Limit = 20
    offset: Offset = 0
    sort_by: HeaderSort = "posting_date"
    sort_order: SortOrder = "desc"
    fields: HeaderFields = Field(default_factory=lambda: ["name"])


class ReceiptAggregateInput(ReceiptFilters):
    metrics: HeaderMetrics
    group_by: HeaderGroup | None = None


class ReceiptItemQueryInput(PublicContractModel):
    purchase_receipt: NonEmptyString | None = None
    purchase_order: NonEmptyString | None = None
    supplier: NonEmptyString | None = None
    company: NonEmptyString | None = None
    item_code: NonEmptyString | None = None
    purchase_receipt_status: NonEmptyString | None = None
    docstatus: Docstatus | None = None
    is_return: bool | None = None
    warehouse: NonEmptyString | None = None
    rejected_warehouse: NonEmptyString | None = None
    posting_date_from: date | None = None
    posting_date_to: date | None = None
    min_qty: Number | None = None
    max_qty: Number | None = None
    min_received_qty: Number | None = None
    max_received_qty: Number | None = None
    min_rejected_qty: Number | None = None
    max_rejected_qty: Number | None = None
    limit: Limit = 20
    offset: Offset = 0
    sort_by: ItemSort = "posting_date"
    sort_order: SortOrder = "desc"
    fields: ItemFields | None = None
    metrics: list[ItemMetric] = Field(default_factory=list)
    group_by: ItemGroup | None = None

    @model_validator(mode="after")
    def ranges(self):
        for start, end in ((self.posting_date_from, self.posting_date_to), (self.min_qty, self.max_qty), (self.min_received_qty, self.max_received_qty), (self.min_rejected_qty, self.max_rejected_qty)):
            if start is not None and end is not None and start > end:
                raise ValueError("Range start must not exceed end")
        return self


class ReceiptQueryDocument(PublicContractModel):
    name: str | None = None
    supplier: str | None = None
    supplier_name: str | None = None
    posting_date: date | None = None
    posting_time: str | None = None
    docstatus: int | None = None
    status: str | None = None
    company: str | None = None
    currency: str | None = None
    conversion_rate: float | None = None
    buying_price_list: str | None = None
    price_list_currency: str | None = None
    total_qty: float | None = None
    grand_total: float | None = None
    per_billed: float | None = None
    per_returned: float | None = None
    is_return: int | bool | None = None
    return_against: str | None = None
    supplier_delivery_note: str | None = None
    owner: str | None = None
    creation: str | None = None
    modified: str | None = None


class ReceiptQueryOk(PublicContractModel):
    status: Literal["ok"]
    purchase_receipts: list[ReceiptQueryDocument]
    count: int
    limit: int
    offset: int


class ReceiptQueryOutput(RootModel[Annotated[ReceiptQueryOk | ToolError, Field(discriminator="status")]]):
    pass


class ReceiptAggregateRow(PublicContractModel):
    group_value: str | date | int | bool | None = None
    currency: str | None = None
    count: int | None = None
    sum_grand_total: float | None = None
    avg_grand_total: float | None = None
    min_grand_total: float | None = None
    max_grand_total: float | None = None
    sum_total_qty: float | None = None


class ReceiptAggregateOk(PublicContractModel):
    status: Literal["ok"]
    metrics: list[HeaderMetric]
    group_by: HeaderGroup | None = None
    results: list[ReceiptAggregateRow]


class ReceiptAggregateOutput(RootModel[Annotated[ReceiptAggregateOk | ToolError, Field(discriminator="status")]]):
    pass


class ReceiptHistoryItem(PublicContractModel):
    name: str | None = None
    purchase_receipt: str | None = None
    posting_date: date | None = None
    supplier: str | None = None
    supplier_name: str | None = None
    company: str | None = None
    currency: str | None = None
    purchase_receipt_status: str | None = None
    docstatus: int | None = None
    is_return: int | bool | None = None
    return_against: str | None = None
    item_code: str | None = None
    item_name: str | None = None
    purchase_order: str | None = None
    purchase_order_item: str | None = None
    qty: float | None = None
    rejected_qty: float | None = None
    received_qty: float | None = None
    stock_qty: float | None = None
    uom: str | None = None
    stock_uom: str | None = None
    conversion_factor: float | None = None
    rate: float | None = None
    amount: float | None = None
    net_rate: float | None = None
    net_amount: float | None = None
    billed_amt: float | None = None
    warehouse: str | None = None
    rejected_warehouse: str | None = None
    schedule_date: date | None = None
    quality_inspection: str | None = None
    is_fixed_asset: int | bool | None = None


class ReceiptItemAggregateRow(PublicContractModel):
    group_value: str | date | None = None
    currency: str | None = None
    count_rows: int | None = None
    count_distinct_receipts: int | None = None
    sum_qty: float | None = None
    sum_received_qty: float | None = None
    sum_rejected_qty: float | None = None
    sum_amount: float | None = None
    min_rate: float | None = None
    max_rate: float | None = None
    avg_rate: float | None = None


class ReceiptItemQueryOk(PublicContractModel):
    status: Literal["ok"]
    items: list[ReceiptHistoryItem]
    count: int
    limit: int
    offset: int
    metrics: list[ItemMetric]
    group_by: ItemGroup | None = None
    aggregates: list[ReceiptItemAggregateRow]


class ReceiptItemQueryOutput(RootModel[Annotated[ReceiptItemQueryOk | ToolError, Field(discriminator="status")]]):
    pass
