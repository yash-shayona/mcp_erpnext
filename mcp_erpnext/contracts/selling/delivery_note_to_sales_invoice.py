"""Contracts for native Delivery Note to Sales Invoice conversion."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class DeliveryNoteToSalesInvoiceInput(PublicContractModel):
    delivery_note: NonEmptyString


class DeliveryNoteToSalesInvoiceConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class DeliveryNoteConversionItem(PublicContractModel):
    item_code: str | None = None
    item_name: str | None = None
    qty: float | None = None
    uom: str | None = None
    conversion_factor: float | None = None
    rate: float | None = None
    amount: float | None = None
    warehouse: str | None = None
    delivery_note: str | None = None
    dn_detail: str | None = None
    sales_order: str | None = None
    so_detail: str | None = None


class DeliveryNoteConversionTax(PublicContractModel):
    charge_type: str | None = None
    account_head: str | None = None
    rate: float | None = None
    tax_amount: float | None = None
    total: float | None = None


class DeliveryNoteConversionPaymentSchedule(PublicContractModel):
    due_date: date | None = None
    payment_term: str | None = None
    invoice_portion: float | None = None
    payment_amount: float | None = None
    discount_type: str | None = None
    discount_date: date | None = None
    discount: float | None = None


class DeliveryNoteConversionTotals(PublicContractModel):
    net_total: float | None = None
    total_taxes_and_charges: float | None = None
    grand_total: float | None = None
    rounded_total: float | None = None
    outstanding_amount: float | None = None
    total_qty: float | None = None


class DeliveryNoteConversionSource(PublicContractModel):
    doctype: Literal["Delivery Note"]
    name: NonEmptyString
    docstatus: Literal[1]
    status: str | None = None
    customer: str | None = None
    customer_name: str | None = None
    company: str | None = None
    currency: str | None = None
    posting_date: date | None = None
    is_return: int | None = None
    total_qty: float | None = None
    net_total: float | None = None
    grand_total: float | None = None


class DeliveryNoteToSalesInvoicePreview(PublicContractModel):
    source: DeliveryNoteConversionSource
    sales_invoice: "DeliveryNoteConversionSalesInvoice"


class DeliveryNoteConversionSalesInvoice(PublicContractModel):
    target_doctype: Literal["Sales Invoice"]
    customer: str | None = None
    customer_name: str | None = None
    company: str | None = None
    posting_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    items: list[DeliveryNoteConversionItem]
    taxes: list[DeliveryNoteConversionTax]
    payment_schedule: list[DeliveryNoteConversionPaymentSchedule]
    totals: DeliveryNoteConversionTotals


class DeliveryNoteToSalesInvoiceReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: Annotated[
        NonEmptyString, Field(description="Opaque pending-operation handle.")
    ]
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: DeliveryNoteToSalesInvoicePreview
    interaction: InteractionDirective


PrepareDeliveryNoteToSalesInvoiceResult = Annotated[
    DeliveryNoteToSalesInvoiceReady | ToolError, Field(discriminator="status")
]


class PrepareDeliveryNoteToSalesInvoiceOutput(
    RootModel[PrepareDeliveryNoteToSalesInvoiceResult]
):
    model_config = ConfigDict(json_schema_extra={"type": "object"})


class DeliveryNoteToSalesInvoiceCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Sales Invoice"]
    sales_invoice: NonEmptyString
    docstatus: Literal[0]
    source_delivery_note: NonEmptyString
    customer: str | None = None
    company: str | None = None
    currency: str | None = None
    grand_total: float | None = None
    item_count: int = 0


ConfirmDeliveryNoteToSalesInvoiceResult = Annotated[
    DeliveryNoteToSalesInvoiceCreated | ToolError, Field(discriminator="status")
]


class ConfirmDeliveryNoteToSalesInvoiceOutput(
    RootModel[ConfirmDeliveryNoteToSalesInvoiceResult]
):
    model_config = ConfigDict(json_schema_extra={"type": "object"})
