"""Contracts for native Sales Invoice to Delivery Note conversion."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class SalesInvoiceToDeliveryNoteInput(PublicContractModel):
    sales_invoice: NonEmptyString


class SalesInvoiceToDeliveryNoteConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class SalesInvoiceToDeliveryNoteItemPreview(PublicContractModel):
    item_code: str | None = None
    item_name: str | None = None
    qty: float | None = None
    uom: str | None = None
    conversion_factor: float | None = None
    rate: float | None = None
    amount: float | None = None
    warehouse: str | None = None
    against_sales_invoice: str | None = None
    si_detail: str | None = None
    against_sales_order: str | None = None
    so_detail: str | None = None


class SalesInvoiceToDeliveryNoteSourcePreview(PublicContractModel):
    doctype: Literal["Sales Invoice"]
    name: NonEmptyString
    docstatus: Literal[1]
    status: str | None = None
    customer: str | None = None
    customer_name: str | None = None
    company: str | None = None
    posting_date: str | None = None
    currency: str | None = None
    update_stock: int | None = None
    is_return: int | None = None
    total_qty: float | None = None
    grand_total: float | None = None


class SalesInvoiceToDeliveryNoteTotals(PublicContractModel):
    total_qty: float | None = None
    net_total: float | None = None
    total_taxes_and_charges: float | None = None
    grand_total: float | None = None


class SalesInvoiceToDeliveryNoteTargetPreview(PublicContractModel):
    target_doctype: Literal["Delivery Note"]
    customer: str | None = None
    customer_name: str | None = None
    company: str | None = None
    posting_date: str | None = None
    posting_time: str | None = None
    currency: str | None = None
    items: list[SalesInvoiceToDeliveryNoteItemPreview]
    packed_item_count: int = 0
    has_serial_batch_requirements: bool = False
    totals: SalesInvoiceToDeliveryNoteTotals
    warning: str


class SalesInvoiceToDeliveryNotePreview(PublicContractModel):
    source: SalesInvoiceToDeliveryNoteSourcePreview
    delivery_note: SalesInvoiceToDeliveryNoteTargetPreview


class SalesInvoiceToDeliveryNoteReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: Annotated[NonEmptyString, Field(description="Opaque pending-operation handle.")]
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: SalesInvoiceToDeliveryNotePreview
    interaction: InteractionDirective


PrepareSalesInvoiceToDeliveryNoteResult = Annotated[
    SalesInvoiceToDeliveryNoteReady | ToolError, Field(discriminator="status")
]


class PrepareSalesInvoiceToDeliveryNoteOutput(
    RootModel[PrepareSalesInvoiceToDeliveryNoteResult]
):
    model_config = ConfigDict(json_schema_extra={"type": "object"})


class SalesInvoiceToDeliveryNoteCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Delivery Note"]
    delivery_note: NonEmptyString
    docstatus: Literal[0]
    source_sales_invoice: NonEmptyString
    customer: str | None = None
    company: str | None = None
    currency: str | None = None
    grand_total: float | None = None
    item_count: int = 0


ConfirmSalesInvoiceToDeliveryNoteResult = Annotated[
    SalesInvoiceToDeliveryNoteCreated | ToolError, Field(discriminator="status")
]


class ConfirmSalesInvoiceToDeliveryNoteOutput(
    RootModel[ConfirmSalesInvoiceToDeliveryNoteResult]
):
    model_config = ConfigDict(json_schema_extra={"type": "object"})
