"""Explicit contracts for native Sales Order to Sales Invoice conversion."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective


class SalesOrderToSalesInvoiceInput(PublicContractModel):
    """An exact source Sales Order name; target data is never client supplied."""

    sales_order: NonEmptyString


class SalesOrderConversionSourceItem(PublicContractModel):
    name: NonEmptyString | None = None
    item_code: str | None = None
    uom: str | None = None
    stock_uom: str | None = None
    conversion_factor: float | None = None
    qty: float | None = None
    delivered_qty: float | None = None
    returned_qty: float | None = None
    billed_qty: float | None = None
    billed_amt: float | None = None
    rate: float | None = None
    amount: float | None = None
    warehouse: str | None = None
    project: str | None = None


class SalesInvoiceConversionItem(PublicContractModel):
    item_code: str | None = None
    item_name: str | None = None
    qty: float | None = None
    uom: str | None = None
    conversion_factor: float | None = None
    rate: float | None = None
    amount: float | None = None
    warehouse: str | None = None
    project: str | None = None
    sales_order: str | None = None
    so_detail: str | None = None


class SalesInvoiceConversionTax(PublicContractModel):
    charge_type: str | None = None
    account_head: str | None = None
    rate: float | None = None
    tax_amount: float | None = None
    total: float | None = None


class SalesInvoiceConversionPaymentSchedule(PublicContractModel):
    due_date: date | None = None
    payment_term: str | None = None
    invoice_portion: float | None = None
    payment_amount: float | None = None
    discount_type: str | None = None
    discount_date: date | None = None
    discount: float | None = None


class SalesInvoiceConversionTotals(PublicContractModel):
    net_total: float | None = None
    total_taxes_and_charges: float | None = None
    grand_total: float | None = None
    rounded_total: float | None = None
    outstanding_amount: float | None = None
    base_net_total: float | None = None
    base_grand_total: float | None = None
    total_qty: float | None = None


class SalesOrderConversionSource(PublicContractModel):
    doctype: Literal["Sales Order"]
    name: NonEmptyString
    docstatus: Literal[1]
    status: str | None = None
    customer: str | None = None
    customer_name: str | None = None
    company: str | None = None
    currency: str | None = None
    transaction_date: date | None = None
    delivery_date: date | None = None
    per_billed: float | None = None
    per_delivered: float | None = None
    per_returned: float | None = None
    total_qty: float | None = None
    net_total: float | None = None
    total_taxes_and_charges: float | None = None
    grand_total: float | None = None
    items: list[SalesOrderConversionSourceItem]


class SalesOrderConversionSalesInvoice(PublicContractModel):
    target_doctype: Literal["Sales Invoice"]
    customer: str | None = None
    customer_name: str | None = None
    company: str | None = None
    posting_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    selling_price_list: str | None = None
    debit_to: str | None = None
    billing_address: str | None = None
    shipping_address: str | None = None
    company_address: str | None = None
    items: list[SalesInvoiceConversionItem]
    taxes: list[SalesInvoiceConversionTax]
    payment_schedule: list[SalesInvoiceConversionPaymentSchedule]
    totals: SalesInvoiceConversionTotals


class SalesOrderToSalesInvoicePreview(PublicContractModel):
    source: SalesOrderConversionSource
    sales_invoice: SalesOrderConversionSalesInvoice


class SalesOrderToSalesInvoiceReady(PublicContractModel):
    status: Literal["ready"]
    approval_token: Annotated[
        NonEmptyString,
        Field(description="Opaque pending-operation handle; it is not proof of approval."),
    ]
    expires_in_seconds: Annotated[int, Field(gt=0)]
    preview: SalesOrderToSalesInvoicePreview
    interaction: InteractionDirective


PrepareSalesOrderToSalesInvoiceResult = Annotated[
    SalesOrderToSalesInvoiceReady | ToolError,
    Field(discriminator="status"),
]


class PrepareSalesOrderToSalesInvoiceOutput(RootModel[PrepareSalesOrderToSalesInvoiceResult]):
    """Root-shaped typed output for the conversion prepare tool."""

    model_config = ConfigDict(json_schema_extra={"type": "object"})


class SalesOrderToSalesInvoiceConfirmInput(PublicContractModel):
    approval_token: NonEmptyString
    confirm: bool


class SalesOrderToSalesInvoiceCreated(PublicContractModel):
    status: Literal["created"]
    doctype: Literal["Sales Invoice"]
    sales_invoice: NonEmptyString
    docstatus: Literal[0]
    source_sales_order: NonEmptyString
    customer: str | None = None
    company: str | None = None
    currency: str | None = None
    grand_total: float | None = None
    idempotent: bool = False


ConfirmSalesOrderToSalesInvoiceResult = Annotated[
    SalesOrderToSalesInvoiceCreated | ToolError,
    Field(discriminator="status"),
]


class ConfirmSalesOrderToSalesInvoiceOutput(
    RootModel[ConfirmSalesOrderToSalesInvoiceResult]
):
    """Root-shaped typed output for the conversion confirm tool."""

    model_config = ConfigDict(json_schema_extra={"type": "object"})
