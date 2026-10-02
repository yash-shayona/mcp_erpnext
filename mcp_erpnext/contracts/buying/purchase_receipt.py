"""Bounded public contracts for Purchase Order to Purchase Receipt drafts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, RootModel, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


def _reject_bool(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid quantities.")
    return value


NonNegativeQuantity = Annotated[float, Field(ge=0), BeforeValidator(_reject_bool)]
WarehouseName = Annotated[NonEmptyString, Field(max_length=140)]
SupplierDeliveryNote = Annotated[NonEmptyString, Field(max_length=140)]


class PurchaseReceiptLineInput(PublicContractModel):
    purchase_order_item: NonEmptyString
    accepted_qty: NonNegativeQuantity
    rejected_qty: NonNegativeQuantity = 0
    warehouse: WarehouseName | None = None
    rejected_warehouse: WarehouseName | None = None

    @model_validator(mode="after")
    def require_quantity(self):
        if self.accepted_qty + self.rejected_qty <= 0:
            raise ValueError("Accepted or rejected quantity must be greater than zero.")
        if self.warehouse and self.rejected_warehouse and self.warehouse == self.rejected_warehouse:
            raise ValueError("Accepted and rejected warehouses must be different.")
        return self


class PurchaseReceiptPrepareInput(PublicContractModel):
    purchase_order: NonEmptyString
    lines: list[PurchaseReceiptLineInput] = Field(min_length=1)
    posting_date: date | None = None
    supplier_delivery_note: SupplierDeliveryNote | None = None

    @model_validator(mode="after")
    def unique_rows(self):
        names = [line.purchase_order_item for line in self.lines]
        if len(names) != len(set(names)):
            raise ValueError("Each Purchase Order Item row may be selected only once.")
        return self


class PurchaseReceiptConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class PurchaseReceiptReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: dict[str, Any]
    interaction: InteractionDirective


class PurchaseReceiptPreviewOnly(PublicContractModel):
	status: Literal["preview"]
	preview: dict[str, Any]


class PurchaseReceiptCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Purchase Receipt"]
    purchase_receipt: NonEmptyString
    docstatus: Literal[0]
    source_purchase_order: NonEmptyString
    supplier: str | None = None
    company: str | None = None
    item_count: int


PreparePurchaseReceiptResult = Annotated[
    PurchaseReceiptReady | PurchaseReceiptPreviewOnly | ToolError,
    Field(discriminator="status"),
]


class PreparePurchaseReceiptOutput(RootModel[PreparePurchaseReceiptResult]):
    pass


ConfirmPurchaseReceiptResult = Annotated[
    PurchaseReceiptCreated | ToolError,
    Field(discriminator="status"),
]


class ConfirmPurchaseReceiptOutput(RootModel[ConfirmPurchaseReceiptResult]):
    pass
