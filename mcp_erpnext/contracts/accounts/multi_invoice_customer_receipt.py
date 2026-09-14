"""Typed contracts for explicit multi-invoice Customer receipts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel, field_validator, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class CustomerReceiptAllocation(PublicContractModel):
    sales_invoice: NonEmptyString
    allocated_amount: float = Field(gt=0, allow_inf_nan=False)

    @field_validator("allocated_amount", mode="before")
    @classmethod
    def reject_boolean_amount(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("allocated_amount must be a positive finite number")
        return value


class MultiInvoiceCustomerReceiptPrepareInput(PublicContractModel):
    customer: NonEmptyString
    amount: float = Field(gt=0, allow_inf_nan=False)
    allocations: list[CustomerReceiptAllocation] = Field(min_length=2, max_length=20)
    mode_of_payment: NonEmptyString | None = None
    bank_account: NonEmptyString | None = None
    reference_no: NonEmptyString | None = None
    reference_date: date | None = None
    posting_date: date | None = None
    bank_amount: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    remarks: Annotated[str, Field(max_length=1000)] | None = None

    @field_validator("amount", "bank_amount", mode="before")
    @classmethod
    def reject_boolean_amounts(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("amounts must be positive finite numbers")
        return value

    @model_validator(mode="after")
    def validate_business_shape(self) -> "MultiInvoiceCustomerReceiptPrepareInput":
        names = [row.sales_invoice for row in self.allocations]
        if len(set(names)) != len(names):
            raise ValueError("each Sales Invoice may appear only once")
        if self.mode_of_payment and self.bank_account:
            raise ValueError("provide either mode_of_payment or bank_account")
        return self


class MultiInvoiceReceiptReference(PublicContractModel):
    sales_invoice: NonEmptyString
    posting_date: date | None = None
    due_date: date | None = None
    invoice_currency: NonEmptyString
    party_currency: NonEmptyString
    total_amount: float
    outstanding_amount: float
    allocated_amount: float


class MultiInvoiceCustomerReceiptPreview(PublicContractModel):
    doctype: Literal["Payment Entry"]
    docstatus: Literal[0]
    customer: NonEmptyString
    company: NonEmptyString
    payment_type: Literal["Receive"]
    posting_date: date
    reference_no: str | None = None
    reference_date: date | None = None
    destination_kind: Literal["Mode of Payment", "Bank Account"]
    destination: NonEmptyString
    party_account_currency: NonEmptyString
    destination_account_currency: NonEmptyString
    paid_amount: float
    received_amount: float
    source_exchange_rate: float | None = None
    target_exchange_rate: float | None = None
    references: list[MultiInvoiceReceiptReference]
    total_allocated_amount: float
    unallocated_amount: float
    difference_amount: float
    deductions: list[dict]
    remarks: str | None = None
    note: NonEmptyString


class MultiInvoiceCustomerReceiptReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: int = Field(gt=0)
    preview: MultiInvoiceCustomerReceiptPreview
    interaction: InteractionDirective


class MultiInvoiceCustomerReceiptConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class MultiInvoiceCustomerReceiptCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Payment Entry"]
    payment_entry: NonEmptyString
    docstatus: Literal[0]
    customer: NonEmptyString
    company: NonEmptyString
    source_sales_invoices: list[NonEmptyString]
    idempotent: bool = False


PrepareMultiInvoiceCustomerReceiptResult = MultiInvoiceCustomerReceiptReady | ToolError
ConfirmMultiInvoiceCustomerReceiptResult = MultiInvoiceCustomerReceiptCreated | ToolError


class PrepareMultiInvoiceCustomerReceiptOutput(RootModel[PrepareMultiInvoiceCustomerReceiptResult]):
    pass


class ConfirmMultiInvoiceCustomerReceiptOutput(RootModel[ConfirmMultiInvoiceCustomerReceiptResult]):
    pass
