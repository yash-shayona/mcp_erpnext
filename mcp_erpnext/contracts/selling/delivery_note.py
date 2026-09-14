"""Explicit contracts for native Sales Order to Delivery Note conversion."""

from __future__ import annotations

from typing import Annotated, Literal
from pydantic import ConfigDict, Field, RootModel
from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class SalesOrderToDeliveryNoteInput(PublicContractModel):
    sales_order: NonEmptyString


class SalesOrderToDeliveryNoteConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class DeliveryNoteItemPreview(PublicContractModel):
    item_code: str | None = None
    item_name: str | None = None
    qty: float | None = None
    uom: str | None = None
    rate: float | None = None
    amount: float | None = None
    warehouse: str | None = None
    against_sales_order: str | None = None
    so_detail: str | None = None

class DeliveryNoteSourcePreview(PublicContractModel):
    doctype: Literal["Sales Order"]
    name: NonEmptyString
    docstatus: int
    status: str | None = None
    customer: str | None = None
    company: str | None = None
    currency: str | None = None
    per_delivered: float | None = None

class DeliveryNoteTotals(PublicContractModel):
    total_qty: float | None = None
    net_total: float | None = None
    total_taxes_and_charges: float | None = None
    grand_total: float | None = None

class DeliveryNoteTargetPreview(PublicContractModel):
    target_doctype: Literal["Delivery Note"]
    customer: str | None = None
    customer_name: str | None = None
    company: str | None = None
    posting_date: str | None = None
    posting_time: str | None = None
    currency: str | None = None
    items: list[DeliveryNoteItemPreview]
    packed_item_count: int = 0
    has_serial_batch_requirements: bool = False
    totals: DeliveryNoteTotals
    warning: str


class DeliveryNotePreview(PublicContractModel):
    source: DeliveryNoteSourcePreview
    delivery_note: DeliveryNoteTargetPreview


class DeliveryNoteReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: DeliveryNotePreview
    interaction: InteractionDirective


PrepareDeliveryNoteResult = Annotated[
    DeliveryNoteReady | ToolError, Field(discriminator="status")
]


class PrepareDeliveryNoteOutput(RootModel[PrepareDeliveryNoteResult]):
    model_config = ConfigDict(json_schema_extra={"type": "object"})


class DeliveryNoteCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Delivery Note"]
    delivery_note: NonEmptyString
    docstatus: Literal[0]
    source_sales_order: NonEmptyString
    customer: str | None = None
    company: str | None = None
    currency: str | None = None
    grand_total: float | None = None
    item_count: int = 0


ConfirmDeliveryNoteResult = Annotated[
    DeliveryNoteCreated | ToolError, Field(discriminator="status")
]


class ConfirmDeliveryNoteOutput(RootModel[ConfirmDeliveryNoteResult]):
    model_config = ConfigDict(json_schema_extra={"type": "object"})
