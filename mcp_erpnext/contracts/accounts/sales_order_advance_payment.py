"""Typed contracts for a Sales Order Customer advance Payment Entry."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel, field_validator, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class SalesOrderAdvancePaymentPrepareInput(PublicContractModel):
    sales_order: NonEmptyString
    amount: float = Field(gt=0, allow_inf_nan=False)
    mode_of_payment: NonEmptyString | None = None
    bank_account: NonEmptyString | None = None
    reference_no: NonEmptyString | None = None
    reference_date: date | None = None
    bank_amount: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    remarks: Annotated[str, Field(max_length=1000)] | None = None

    @field_validator("amount", "bank_amount", mode="before")
    @classmethod
    def reject_boolean_amounts(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("amounts must be positive finite numbers")
        return value

    @model_validator(mode="after")
    def validate_destination(self) -> "SalesOrderAdvancePaymentPrepareInput":
        if bool(self.mode_of_payment) == bool(self.bank_account):
            raise ValueError("provide exactly one of mode_of_payment or bank_account")
        return self


class SalesOrderAdvancePaymentReference(PublicContractModel):
    """Bounded native reference summary; callers cannot supply these rows."""

    reference_doctype: Literal["Sales Order"]
    reference_name: NonEmptyString
    due_date: date | None = None
    total_amount: float | None = None
    outstanding_amount: float | None = None
    allocated_amount: float | None = None
    payment_term: str | None = None


class SalesOrderAdvancePaymentPreview(PublicContractModel):
    doctype: Literal["Payment Entry"]
    docstatus: Literal[0]
    source_sales_order: NonEmptyString
    source_status: NonEmptyString
    customer: NonEmptyString
    company: NonEmptyString
    payment_type: Literal["Receive"]
    posting_date: date
    mode_of_payment: str | None = None
    destination_kind: Literal["Mode of Payment", "Bank Account"]
    destination: NonEmptyString
    party_account_currency: NonEmptyString
    destination_account_currency: NonEmptyString
    paid_amount: float
    received_amount: float
    source_exchange_rate: float | None = None
    target_exchange_rate: float | None = None
    order_total: float | None = None
    existing_advance_paid: float | None = None
    payment_terms_template: str | None = None
    references: list[SalesOrderAdvancePaymentReference] = Field(
        min_length=1, max_length=50
    )
    total_allocated_amount: float
    unallocated_amount: float
    difference_amount: float
    reference_no: str | None = None
    reference_date: date | None = None
    separate_advance_account: bool
    remarks: str | None = None
    note: NonEmptyString


class SalesOrderAdvancePaymentReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: int = Field(gt=0)
    preview: SalesOrderAdvancePaymentPreview
    interaction: InteractionDirective


class SalesOrderAdvancePaymentConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class SalesOrderAdvancePaymentCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Payment Entry"]
    payment_entry: NonEmptyString
    docstatus: Literal[0]
    source_sales_order: NonEmptyString
    customer: NonEmptyString
    company: NonEmptyString
    payment_type: Literal["Receive"]
    paid_amount: float
    unallocated_amount: float
    idempotent: bool = False


PrepareSalesOrderAdvancePaymentResult = SalesOrderAdvancePaymentReady | ToolError
ConfirmSalesOrderAdvancePaymentResult = SalesOrderAdvancePaymentCreated | ToolError


class PrepareSalesOrderAdvancePaymentOutput(
    RootModel[PrepareSalesOrderAdvancePaymentResult]
):
    pass


class ConfirmSalesOrderAdvancePaymentOutput(
    RootModel[ConfirmSalesOrderAdvancePaymentResult]
):
    pass
