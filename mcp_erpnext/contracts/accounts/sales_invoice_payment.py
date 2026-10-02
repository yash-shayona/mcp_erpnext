"""Typed contracts for a narrow Sales Invoice customer receipt workflow."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class SalesInvoicePaymentPrepareInput(PublicContractModel):
    sales_invoice: NonEmptyString
    amount: float | None = Field(default=None, gt=0)
    mode_of_payment: NonEmptyString | None = None
    bank_account: NonEmptyString | None = None
    reference_no: NonEmptyString | None = None
    reference_date: date | None = None
    bank_amount: float | None = Field(default=None, gt=0)
    remarks: Annotated[str, Field(max_length=1000)] | None = None


class SalesInvoicePaymentReference(PublicContractModel):
    reference_doctype: NonEmptyString
    reference_name: NonEmptyString
    total_amount: float | None = None
    outstanding_amount: float | None = None
    allocated_amount: float | None = None
    payment_term: str | None = None


class SalesInvoicePaymentPreview(PublicContractModel):
    doctype: Literal["Payment Entry"]
    docstatus: Literal[0]
    source_sales_invoice: NonEmptyString
    source_status: NonEmptyString
    customer: NonEmptyString
    company: NonEmptyString
    payment_type: Literal["Receive"]
    posting_date: date | None = None
    mode_of_payment: str | None = None
    destination: str | None = None
    party_currency: str | None = None
    bank_currency: str | None = None
    paid_amount: float | None = None
    received_amount: float | None = None
    current_invoice_outstanding: float | None = None
    allocated_amount: float | None = None
    unallocated_amount: float | None = None
    reference_no: str | None = None
    reference_date: date | None = None
    references: list[SalesInvoicePaymentReference]
    remarks: str | None = None
    note: NonEmptyString


class SalesInvoicePaymentReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: int = Field(gt=0)
    preview: SalesInvoicePaymentPreview
    interaction: InteractionDirective


class SalesInvoicePaymentConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class SalesInvoicePaymentCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Payment Entry"]
    payment_entry: NonEmptyString
    docstatus: Literal[0]
    source_sales_invoice: NonEmptyString
    customer: NonEmptyString
    company: NonEmptyString
    idempotent: bool = False


PrepareSalesInvoicePaymentResult = SalesInvoicePaymentReady | ToolError
ConfirmSalesInvoicePaymentResult = SalesInvoicePaymentCreated | ToolError


class PrepareSalesInvoicePaymentOutput(RootModel[PrepareSalesInvoicePaymentResult]):
    pass


class ConfirmSalesInvoicePaymentOutput(RootModel[ConfirmSalesInvoicePaymentResult]):
    pass
