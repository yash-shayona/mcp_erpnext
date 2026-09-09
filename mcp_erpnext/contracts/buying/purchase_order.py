"""Explicit public contracts for the controlled Purchase Order workflow."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, ConfigDict, Field, RootModel

from ..common import (
    ItemReference,
    NonEmptyString,
    PublicContractModel,
    SupplierReference,
    ToolError,
)
from ..interaction import InteractionDirective


def _reject_boolean(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid quantities.")
    return value


PositiveNumber = Annotated[float, Field(gt=0), BeforeValidator(_reject_boolean)]


class PurchaseOrderItemInput(PublicContractModel):
    """One resolved purchase-enabled Item row for a Purchase Order preview."""

    item: ItemReference
    qty: PositiveNumber
    rate: Annotated[float, Field(ge=0), BeforeValidator(_reject_boolean)] | None = None

    def to_service_payload(self) -> dict[str, object]:
        return {
            "item": self.item.model_dump(),
            "qty": self.qty,
            **({"rate": self.rate} if self.rate is not None else {}),
        }


class PurchaseOrderPrepareInput(PublicContractModel):
    """Public, non-persistent Purchase Order preparation request."""

    supplier: SupplierReference
    items: list[PurchaseOrderItemInput]
    company: NonEmptyString | None = None
    transaction_date: date | None = None
    schedule_date: date | None = None
    buying_price_list: NonEmptyString | None = None
    taxes_and_charges: NonEmptyString | None = None


class PurchaseOrderPreviewSupplier(PublicContractModel):
    doctype: Literal["Supplier"]
    name: NonEmptyString
    supplier_name: str | None = None


class PurchaseOrderPreviewItem(PublicContractModel):
    item_code: NonEmptyString
    item_name: str | None = None
    qty: float
    schedule_date: date | None = None
    uom: str | None = None
    rate: float | None = None
    amount: float | None = None


class PurchaseOrderPreviewTax(PublicContractModel):
    charge_type: str | None = None
    account_head: str | None = None
    rate: float | None = None
    tax_amount: float | None = None
    total: float | None = None


class PurchaseOrderPreview(PublicContractModel):
    supplier: PurchaseOrderPreviewSupplier
    company: NonEmptyString
    transaction_date: date
    schedule_date: date
    currency: NonEmptyString
    buying_price_list: str | None = None
    items: list[PurchaseOrderPreviewItem]
    taxes: list[PurchaseOrderPreviewTax]
    net_total: float
    total_taxes_and_charges: float
    grand_total: float


class PurchaseOrderReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: PurchaseOrderPreview
    interaction: InteractionDirective


class PurchaseOrderNeedsInput(PublicContractModel):
    status: Literal["needs_input"]
    missing: list[NonEmptyString]
    message: str | None = None
    interaction: InteractionDirective


class PurchaseOrderPermissionDenied(PublicContractModel):
    status: Literal["permission_denied"]
    missing_permissions: list[Literal["Purchase Order"]]
    message: NonEmptyString


PreparePurchaseOrderResult = Annotated[
    PurchaseOrderReady
    | PurchaseOrderNeedsInput
    | PurchaseOrderPermissionDenied
    | ToolError,
    Field(discriminator="status"),
]


class PreparePurchaseOrderOutput(RootModel[PreparePurchaseOrderResult]):
    model_config = ConfigDict(json_schema_extra={"type": "object"})


class PurchaseOrderConfirmInput(PublicContractModel):
    """Requested execution of a pending PO, never a human-approval grant."""

    approval_token: NonEmptyString
    confirm: Annotated[
        bool,
        Field(
            description="Requested confirmation only; server policy remains authoritative."
        ),
    ]


class PurchaseOrderCreated(PublicContractModel):
    status: Literal["created"]
    purchase_order: NonEmptyString
    docstatus: int


ConfirmPurchaseOrderResult = Annotated[
    PurchaseOrderCreated | PurchaseOrderPermissionDenied | ToolError,
    Field(discriminator="status"),
]


class ConfirmPurchaseOrderOutput(RootModel[ConfirmPurchaseOrderResult]):
    model_config = ConfigDict(json_schema_extra={"type": "object"})
