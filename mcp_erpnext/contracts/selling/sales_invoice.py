"""Typed contracts for standalone Draft Sales Invoice creation."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import (
    CustomerReference,
    ItemReference,
    NonEmptyString,
    PublicContractModel,
    ToolError,
)
from ..interaction import InteractionDirective


class SalesInvoiceItemInput(PublicContractModel):
    """One resolved sales Item and its bounded commercial inputs."""

    item: ItemReference
    qty: Annotated[float, Field(gt=0)]
    rate: Annotated[float, Field(ge=0)] | None = None


class SalesInvoicePrepareInput(PublicContractModel):
    """Bounded, source-free inputs for a direct Draft Sales Invoice."""

    customer: CustomerReference
    items: Annotated[list[SalesInvoiceItemInput], Field(min_length=1)]
    company: NonEmptyString | None = None
    posting_date: date | None = None
    selling_price_list: NonEmptyString | None = None
    customer_address: NonEmptyString | None = None
    shipping_address_name: NonEmptyString | None = None
    contact_person: NonEmptyString | None = None


class SalesInvoicePreviewItem(PublicContractModel):
    item_code: NonEmptyString
    item_name: str | None = None
    description: str | None = None
    qty: float
    stock_uom: str | None = None
    uom: str | None = None
    conversion_factor: float | None = None
    rate: float | None = None
    amount: float | None = None
    net_rate: float | None = None
    net_amount: float | None = None
    warehouse: str | None = None
    income_account: str | None = None


class SalesInvoicePreviewTax(PublicContractModel):
    charge_type: str | None = None
    account_head: str | None = None
    rate: float | None = None
    tax_amount: float | None = None
    total: float | None = None


class SalesInvoicePreviewPaymentSchedule(PublicContractModel):
    due_date: date | None = None
    payment_term: str | None = None
    invoice_portion: float | None = None
    payment_amount: float | None = None


class SalesInvoicePreviewTotals(PublicContractModel):
    total_qty: float | None = None
    net_total: float | None = None
    total_taxes_and_charges: float | None = None
    grand_total: float | None = None
    rounded_total: float | None = None
    outstanding_amount: float | None = None
    base_net_total: float | None = None
    base_grand_total: float | None = None


class SalesInvoicePreview(PublicContractModel):
    doctype: Literal["Sales Invoice"]
    docstatus: Literal[0]
    customer: NonEmptyString
    customer_name: str | None = None
    company: NonEmptyString
    posting_date: date
    due_date: date | None = None
    currency: NonEmptyString
    selling_price_list: NonEmptyString
    contact_person: str | None = None
    customer_address: str | None = None
    shipping_address_name: str | None = None
    debit_to: NonEmptyString
    items: list[SalesInvoicePreviewItem]
    taxes: list[SalesInvoicePreviewTax]
    payment_schedule: list[SalesInvoicePreviewPaymentSchedule]
    totals: SalesInvoicePreviewTotals


class SalesInvoiceReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: Annotated[
        NonEmptyString,
        Field(description="Opaque pending-operation handle; it is not proof of approval."),
    ]
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: SalesInvoicePreview
    interaction: InteractionDirective


class SalesInvoiceNeedsInput(PublicContractModel):
    status: Literal["needs_input"]
    missing: list[NonEmptyString]
    message: str | None = None
    interaction: InteractionDirective


class SalesInvoiceBlocked(PublicContractModel):
    status: Literal["blocked"]
    code: NonEmptyString
    message: NonEmptyString
    prerequisites: list[Literal["Sales Order", "Delivery Note"]]


PrepareSalesInvoiceResult = Annotated[
    SalesInvoiceReady | SalesInvoiceNeedsInput | SalesInvoiceBlocked | ToolError,
    Field(discriminator="status"),
]


class PrepareSalesInvoiceOutput(RootModel[PrepareSalesInvoiceResult]):
    """Root-shaped typed output for standalone Sales Invoice preparation."""

    model_config = ConfigDict(json_schema_extra={"type": "object"})


class SalesInvoiceConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class SalesInvoiceCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Sales Invoice"]
    sales_invoice: NonEmptyString
    docstatus: Literal[0]
    customer: NonEmptyString
    company: NonEmptyString
    currency: NonEmptyString
    grand_total: float | None = None
    idempotent: bool = False


ConfirmSalesInvoiceResult = Annotated[
    SalesInvoiceCreated | ToolError,
    Field(discriminator="status"),
]


class ConfirmSalesInvoiceOutput(RootModel[ConfirmSalesInvoiceResult]):
    """Root-shaped typed output for standalone Sales Invoice confirmation."""

    model_config = ConfigDict(json_schema_extra={"type": "object"})
