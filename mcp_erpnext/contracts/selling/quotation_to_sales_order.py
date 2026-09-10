"""Explicit contracts for native Quotation to Sales Order conversion."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class QuotationToSalesOrderInput(PublicContractModel):
    """An exact source Quotation name; target data is never client supplied."""

    quotation: NonEmptyString


class QuotationConversionSource(PublicContractModel):
    doctype: Literal["Quotation"]
    quotation: NonEmptyString


class QuotationConversionItem(PublicContractModel):
    item_code: NonEmptyString
    item_name: str | None = None
    qty: float
    uom: str | None = None
    rate: float | None = None
    discount_percentage: float | None = None
    discount_amount: float | None = None
    amount: float | None = None
    net_amount: float | None = None
    warehouse: str | None = None
    delivery_date: date | None = None
    quotation_item: NonEmptyString
    prevdoc_docname: NonEmptyString


class QuotationConversionTax(PublicContractModel):
    charge_type: str | None = None
    account_head: str | None = None
    rate: float | None = None
    tax_amount: float | None = None
    total: float | None = None


class QuotationConversionTotals(PublicContractModel):
    net_total: float | None = None
    total_taxes_and_charges: float | None = None
    additional_discount_percentage: float | None = None
    discount_amount: float | None = None
    grand_total: float | None = None


class QuotationConversionSalesOrder(PublicContractModel):
    customer: NonEmptyString | None = None
    customer_name: str | None = None
    company: NonEmptyString | None = None
    transaction_date: date | None = None
    delivery_date: date | None = None
    currency: NonEmptyString | None = None
    selling_price_list: NonEmptyString | None = None
    items: list[QuotationConversionItem]
    taxes: list[QuotationConversionTax]
    totals: QuotationConversionTotals
    tc_name: str | None = None
    terms: str | None = None


class QuotationToSalesOrderPreview(PublicContractModel):
    source: QuotationConversionSource
    sales_order: QuotationConversionSalesOrder


class QuotationToSalesOrderReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: Annotated[
        NonEmptyString,
        Field(description="Opaque pending-operation handle; it is not proof of approval."),
    ]
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: QuotationToSalesOrderPreview
    interaction: InteractionDirective


PrepareQuotationToSalesOrderResult = Annotated[
    QuotationToSalesOrderReady | ToolError,
    Field(discriminator="status"),
]


class PrepareQuotationToSalesOrderOutput(RootModel[PrepareQuotationToSalesOrderResult]):
    """Root-shaped typed output for the conversion prepare tool."""

    model_config = ConfigDict(json_schema_extra={"type": "object"})


class QuotationToSalesOrderConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class QuotationToSalesOrderCreated(PublicContractModel):
    status: Literal["created"]
    sales_order: NonEmptyString
    docstatus: Literal[0]
    source_quotation: NonEmptyString
    idempotent: bool = False


ConfirmQuotationToSalesOrderResult = Annotated[
    QuotationToSalesOrderCreated | ToolError,
    Field(discriminator="status"),
]


class ConfirmQuotationToSalesOrderOutput(RootModel[ConfirmQuotationToSalesOrderResult]):
    """Root-shaped typed output for the conversion confirm tool."""

    model_config = ConfigDict(json_schema_extra={"type": "object"})
