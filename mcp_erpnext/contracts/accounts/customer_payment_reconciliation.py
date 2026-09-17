"""Typed contracts for applying an existing Customer Payment Entry to an invoice."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, RootModel, field_validator

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class CustomerPaymentReconciliationPrepareInput(PublicContractModel):
    """The intentionally small one-payment/one-invoice public intent."""

    payment_entry: NonEmptyString
    sales_invoice: NonEmptyString
    amount: float = Field(gt=0, allow_inf_nan=False)

    @field_validator("amount", mode="before")
    @classmethod
    def reject_boolean_amounts(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("amount must be a positive finite number")
        return value


class CustomerPaymentReconciliationPreview(PublicContractModel):
    payment_entry: NonEmptyString
    sales_invoice: NonEmptyString
    customer: NonEmptyString
    company: NonEmptyString
    source_kind: Literal["unallocated", "sales_order_advance"]
    source_sales_order: NonEmptyString | None = None
    allocation_currency: NonEmptyString
    available_source_amount: float
    invoice_outstanding_before: float
    requested_amount: float
    effective_native_allocation: float
    projected_invoice_outstanding_after: float
    separate_advance_account_applies: bool
    effective_reconciliation_date: date | None = None
    payment_terms_supported: Literal[True] = True
    regional_adjustment_applies: bool = False
    regional_adjustment_warning: str | None = None
    exchange_or_gain_loss_warning: str | None = None
    projection_warning: NonEmptyString


class CustomerPaymentReconciliationReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: Annotated[
        NonEmptyString, Field(description="Opaque pending-operation handle.")
    ]
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: CustomerPaymentReconciliationPreview
    interaction: InteractionDirective


class CustomerPaymentReconciliationConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class CustomerPaymentReconciled(PublicContractModel):
    status: Literal["reconciled"]
    payment_entry: NonEmptyString
    sales_invoice: NonEmptyString
    customer: NonEmptyString
    company: NonEmptyString
    source_kind: Literal["unallocated", "sales_order_advance"]
    applied_amount: float
    allocation_currency: NonEmptyString
    invoice_outstanding_before: float
    invoice_outstanding_after: float | None = None
    source_available_before: float
    source_available_after: float | None = None
    separate_advance_account_applied: bool
    regional_adjustment_warning: str | None = None
    exchange_or_gain_loss_warning: str | None = None
    interaction: InteractionDirective = Field(
        default_factory=lambda: InteractionDirective(required=False)
    )


PrepareCustomerPaymentReconciliationResult = Annotated[
    CustomerPaymentReconciliationReady | ToolError, Field(discriminator="status")
]
ConfirmCustomerPaymentReconciliationResult = Annotated[
    CustomerPaymentReconciled | ToolError, Field(discriminator="status")
]


class PrepareCustomerPaymentReconciliationOutput(
    RootModel[PrepareCustomerPaymentReconciliationResult]
):
    pass


class ConfirmCustomerPaymentReconciliationOutput(
    RootModel[ConfirmCustomerPaymentReconciliationResult]
):
    pass
