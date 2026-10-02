"""Typed contracts for standalone Customer receipt Payment Entries."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel, field_validator, model_validator

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class CustomerPaymentEntryPrepareInput(PublicContractModel):
    customer: NonEmptyString
    company: NonEmptyString
    amount: float = Field(gt=0, allow_inf_nan=False)
    posting_date: date | None = None
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
    def validate_destination(self) -> "CustomerPaymentEntryPrepareInput":
        if bool(self.mode_of_payment) == bool(self.bank_account):
            raise ValueError("provide exactly one of mode_of_payment or bank_account")
        return self


class CustomerPaymentEntryReference(PublicContractModel):
    """Bounded reference shape; standalone V1 always returns an empty list."""

    reference_doctype: NonEmptyString
    reference_name: NonEmptyString


class CustomerPaymentEntryPreview(PublicContractModel):
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
    references: list[CustomerPaymentEntryReference] = Field(default_factory=list)
    total_allocated_amount: float
    unallocated_amount: float
    difference_amount: float
    remarks: str | None = None
    note: NonEmptyString


class CustomerPaymentEntryReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: NonEmptyString
    expires_in_seconds: int = Field(gt=0)
    preview: CustomerPaymentEntryPreview
    interaction: InteractionDirective


class CustomerPaymentEntryConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class CustomerPaymentEntryCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Payment Entry"]
    payment_entry: NonEmptyString
    docstatus: Literal[0]
    customer: NonEmptyString
    company: NonEmptyString
    payment_type: Literal["Receive"]
    paid_amount: float
    unallocated_amount: float
    idempotent: bool = False


PrepareCustomerPaymentEntryResult = CustomerPaymentEntryReady | ToolError
ConfirmCustomerPaymentEntryResult = CustomerPaymentEntryCreated | ToolError


class PrepareCustomerPaymentEntryOutput(RootModel[PrepareCustomerPaymentEntryResult]):
    pass


class ConfirmCustomerPaymentEntryOutput(RootModel[ConfirmCustomerPaymentEntryResult]):
    pass
