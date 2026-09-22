"""Fixed remote-operation registry for the REST backend.

The handlers deliberately call the existing Frappe-native services.  This is
the only code allowed to bridge REST request data to those services.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from .contracts.buying.purchase_order import (
    PurchaseOrderConfirmInput,
    PurchaseOrderPrepareInput,
)
from .contracts.email import DocumentEmailConfirmInput, DocumentEmailPrepareInput
from .contracts.accounts.sales_invoice_payment import (
    SalesInvoicePaymentConfirmInput,
    SalesInvoicePaymentPrepareInput,
)
from .contracts.accounts.multi_invoice_customer_receipt import (
    MultiInvoiceCustomerReceiptConfirmInput,
    MultiInvoiceCustomerReceiptPrepareInput,
)
from .contracts.accounts.payment_entry_read import (
    PaymentEntryAggregateInput,
    PaymentEntryGetInput,
    PaymentEntryQueryInput,
)
from .contracts.accounts.sales_order_advance_payment import (
    SalesOrderAdvancePaymentConfirmInput,
    SalesOrderAdvancePaymentPrepareInput,
)
from .contracts.accounts.customer_payment_reconciliation import (
    CustomerPaymentReconciliationConfirmInput,
    CustomerPaymentReconciliationPrepareInput,
)
from .contracts.lifecycle import (
    LifecycleConfirmInput,
    PrepareActionInput,
    PrepareChildAddInput,
    PrepareUpdateInput,
)
from .contracts.masters.customer import CustomerConfirmInput, CustomerPrepareInput
from .contracts.masters.contact import (
	ContactConfirmInput,
	ContactPrepareInput,
	ContactUpdateConfirmInput,
	ContactUpdatePrepareInput,
	ContactSearchInput,
	CustomerContactConfirmInput,
	CustomerContactPrepareInput,
	CustomerPrimaryContactConfirmInput,
	CustomerPrimaryContactPrepareInput,
)
from .contracts.masters.customer_read import (
    CustomerAggregateInput,
    CustomerGetInput,
    CustomerQueryInput,
)
from .contracts.masters.item import ItemConfirmInput, ItemPrepareInput
from .contracts.masters.item_read import (
    ItemAggregateInput,
    ItemGetInput,
    ItemQueryInput,
)
from .contracts.masters.resolution import EntityResolveInput, SelectedCandidateInput
from .contracts.pdf import RenderDocumentPdfInput
from .contracts.read import DocumentReadInput, DocumentSearchInput
from .contracts.selling.quotation import QuotationConfirmInput, QuotationPrepareInput
from .contracts.selling.quotation_read import (
    QuotationAggregateInput,
    QuotationGetInput,
    QuotationQueryInput,
)
from .contracts.selling.quotation_to_sales_order import (
    QuotationToSalesOrderConfirmInput,
    QuotationToSalesOrderInput,
)
from .contracts.selling.sales_invoice import (
    SalesInvoiceConfirmInput,
    SalesInvoicePrepareInput,
)
from .contracts.selling.sales_invoice_read import (
    SalesInvoiceAggregateInput,
    SalesInvoiceGetInput,
    SalesInvoiceQueryInput,
)
from .contracts.selling.sales_order import (
    SalesOrderConfirmInput,
    SalesOrderPrepareInput,
)
from .contracts.selling.sales_order_read import (
    GetSalesOrderInput,
    SalesOrderAggregateInput,
    SalesOrderItemQueryInput,
    SalesOrderQueryInput,
)
from .contracts.selling.sales_order_to_sales_invoice import (
    SalesOrderToSalesInvoiceConfirmInput,
    SalesOrderToSalesInvoiceInput,
)
from .contracts.selling.delivery_note import (
    SalesOrderToDeliveryNoteInput,
    SalesOrderToDeliveryNoteConfirmInput,
)
from .contracts.selling.delivery_note_to_sales_invoice import (
    DeliveryNoteToSalesInvoiceInput,
    DeliveryNoteToSalesInvoiceConfirmInput,
)
from .contracts.selling.sales_invoice_to_delivery_note import (
    SalesInvoiceToDeliveryNoteInput,
    SalesInvoiceToDeliveryNoteConfirmInput,
)
from .contracts.selling.delivery_note_read import (
    DeliveryNoteGetInput,
    DeliveryNoteQueryInput,
    DeliveryNoteAggregateInput,
)
from .services.buying import purchase_order
from .services.accounts import sales_invoice_payment
from .services.accounts import multi_invoice_customer_receipt
from .services.accounts import payment_entry_read
from .services.accounts import sales_order_advance_payment
from .services.accounts import customer_payment_reconciliation
from .services.common import email, lifecycle, pdf, read
from .services.masters import (
    customer,
    customer_contact,
    customer_primary_contact,
    contact_update as customer_contact_update,
    contact as standalone_contact,
    customer_read,
    item,
    item_read,
    selection,
    supplier,
)
from .services.selling import (
    quotation,
    quotation_read,
    quotation_to_sales_order,
    sales_invoice,
    sales_invoice_read,
    sales_order,
    sales_order_read,
    sales_order_to_sales_invoice,
)
from .services.selling import (
    sales_order_to_delivery_note,
    delivery_note_read,
    delivery_note_to_sales_invoice,
    sales_invoice_to_delivery_note,
)

RemoteHandler = Callable[[Any, str], dict[str, Any]]


class RemoteOperationError(RuntimeError):
    """A bounded REST bridge request was invalid or not permitted."""


def _model(model: type[Any], arguments: dict[str, Any]) -> Any:
    try:
        return model.model_validate(arguments)
    except ValidationError as error:
        raise RemoteOperationError(
            "The remote operation request is invalid."
        ) from error


def _sales_search_items(request: EntityResolveInput, _profile: str) -> dict[str, Any]:
    return item.search_items(request.query)


def _purchase_search_items(
    request: EntityResolveInput, _profile: str
) -> dict[str, Any]:
    return item.search_purchase_items(request.query)


def _sales_resolve_items(request: EntityResolveInput, _profile: str) -> dict[str, Any]:
    return item.resolve_item_for_workflow(request.query)


def _purchase_resolve_items(
    request: EntityResolveInput, _profile: str
) -> dict[str, Any]:
    return item.resolve_purchase_item_for_workflow(request.query)


def _prepare_sales_order(
    request: SalesOrderPrepareInput, _profile: str
) -> dict[str, Any]:
    return sales_order.prepare_sales_order(
        request.customer.name,
        [row.to_service_payload() for row in request.items],
        request.company,
        request.delivery_date.isoformat() if request.delivery_date else None,
        request.selling_price_list,
    )


def _prepare_quotation(request: QuotationPrepareInput, _profile: str) -> dict[str, Any]:
    return quotation.prepare_quotation(
        request.customer.model_dump(),
        [row.to_service_payload() for row in request.items],
        request.valid_till.isoformat() if request.valid_till else None,
        request.company,
        request.transaction_date.isoformat() if request.transaction_date else None,
        request.selling_price_list,
        request.taxes_and_charges,
        request.additional_discount_percentage,
        request.discount_amount,
        request.tc_name,
    )


def _prepare_purchase_order(
    request: PurchaseOrderPrepareInput, _profile: str
) -> dict[str, Any]:
    return purchase_order.prepare_purchase_order(
        request.supplier.model_dump(),
        [row.to_service_payload() for row in request.items],
        request.company,
        request.transaction_date.isoformat() if request.transaction_date else None,
        request.schedule_date.isoformat() if request.schedule_date else None,
        request.buying_price_list,
        request.taxes_and_charges,
    )


def _prepare_sales_invoice(
    request: SalesInvoicePrepareInput, _profile: str
) -> dict[str, Any]:
    return sales_invoice.prepare_sales_invoice(
        request.customer.model_dump(),
        [row.model_dump() for row in request.items],
        request.company,
        request.posting_date.isoformat() if request.posting_date else None,
        request.selling_price_list,
        request.customer_address,
        request.shipping_address_name,
        request.contact_person,
    )


def _prepare_email(request: DocumentEmailPrepareInput, profile: str) -> dict[str, Any]:
    return email.prepare_document_email(
        request.doctype,
        request.name,
        profile,
        request.recipient_email,
        request.subject,
        request.message,
        request.print_format,
        request.letterhead,
        request.language,
    )


def _render_pdf(request: RenderDocumentPdfInput, profile: str) -> dict[str, Any]:
    return pdf.render_document_pdf(
        request.doctype,
        request.name,
        profile,
        request.print_format,
        request.letterhead,
        request.language,
    )


def _prepare_child_add(request: PrepareChildAddInput, profile: str) -> dict[str, Any]:
    return lifecycle.prepare_child_add(
        request.target.model_dump(),
        request.item.model_dump(),
        request.qty,
        request.rate,
        profile,
    )


def _prepare_update(request: PrepareUpdateInput, profile: str) -> dict[str, Any]:
    return lifecycle.prepare_update(
        request.target.model_dump(),
        [row.model_dump() for row in request.changes],
        profile,
    )


def _prepare_lifecycle(action: str) -> RemoteHandler:
    return lambda request, profile: getattr(lifecycle, f"prepare_{action}")(
        request.target.model_dump(), profile
    )


def _confirm_lifecycle(action: str) -> RemoteHandler:
    return lambda request, profile: lifecycle.confirm(
        action, request.approval_token, request.confirm, profile
    )


_SHARED_HANDLERS: dict[str, tuple[type[Any], RemoteHandler]] = {
    "prepare_document_update": (PrepareUpdateInput, _prepare_update),
    "confirm_document_update": (LifecycleConfirmInput, _confirm_lifecycle("update")),
    "prepare_document_child_add": (PrepareChildAddInput, _prepare_child_add),
    "confirm_document_child_add": (
        LifecycleConfirmInput,
        _confirm_lifecycle("child_add"),
    ),
    "prepare_document_submit": (PrepareActionInput, _prepare_lifecycle("submit")),
    "confirm_document_submit": (LifecycleConfirmInput, _confirm_lifecycle("submit")),
    "prepare_document_cancel": (PrepareActionInput, _prepare_lifecycle("cancel")),
    "confirm_document_cancel": (LifecycleConfirmInput, _confirm_lifecycle("cancel")),
    "prepare_document_delete": (PrepareActionInput, _prepare_lifecycle("delete")),
    "confirm_document_delete": (LifecycleConfirmInput, _confirm_lifecycle("delete")),
    "render_document_pdf": (RenderDocumentPdfInput, _render_pdf),
    "prepare_document_email": (DocumentEmailPrepareInput, _prepare_email),
    "confirm_document_email": (
        DocumentEmailConfirmInput,
        lambda request, profile: email.confirm_document_email(
            request.approval_token, profile
        ),
    ),
}

_SALES_HANDLERS: dict[str, tuple[type[Any], RemoteHandler]] = {
    "search_customers": (
        EntityResolveInput,
        lambda request, _profile: customer.search_customers(request.query),
    ),
    "resolve_customer": (
        EntityResolveInput,
        lambda request, _profile: customer.resolve_customer_for_workflow(request.query),
    ),
    "prepare_customer": (
        CustomerPrepareInput,
        lambda request, _profile: customer.prepare_customer(
            request.to_service_payload()
        ),
    ),
    "confirm_customer": (
        CustomerConfirmInput,
        lambda request, _profile: customer.confirm_customer(
            request.approval_token, request.confirm
        ),
    ),
    "search_contacts": (
        ContactSearchInput,
        lambda request, _profile: customer_contact.search_contacts(
            **request.model_dump(mode="json")
        ),
    ),
    "prepare_customer_contact": (
        CustomerContactPrepareInput,
        lambda request, _profile: customer_contact.prepare_customer_contact(
            request.model_dump(mode="json")
        ),
    ),
    "confirm_customer_contact": (
        CustomerContactConfirmInput,
        lambda request, _profile: customer_contact.confirm_customer_contact(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_customer_primary_contact": (
        CustomerPrimaryContactPrepareInput,
        lambda request, _profile: customer_primary_contact.prepare_customer_primary_contact(
            request.model_dump(mode="json")
        ),
    ),
    "confirm_customer_primary_contact": (
        CustomerPrimaryContactConfirmInput,
        lambda request, _profile: customer_primary_contact.confirm_customer_primary_contact(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_contact": (
		ContactPrepareInput,
		lambda request, _profile: standalone_contact.prepare_contact(
			request.model_dump(mode="json")
		),
	),
    "confirm_contact": (
		ContactConfirmInput,
		lambda request, _profile: standalone_contact.confirm_contact(
			request.approval_token, request.confirm
		),
	),
	"prepare_contact_update": (
		ContactUpdatePrepareInput,
		lambda request, _profile: customer_contact_update.prepare_contact_update(
			request.model_dump(mode="json")
		),
	),
	"confirm_contact_update": (
		ContactUpdateConfirmInput,
		lambda request, _profile: customer_contact_update.confirm_contact_update(
			request.approval_token, request.confirm
		),
	),
    "search_items": (EntityResolveInput, _sales_search_items),
    "resolve_item": (EntityResolveInput, _sales_resolve_items),
    "prepare_item": (
        ItemPrepareInput,
        lambda request, _profile: item.prepare_item(request.to_service_payload()),
    ),
    "confirm_item": (
        ItemConfirmInput,
        lambda request, _profile: item.confirm_item(
            request.approval_token, request.confirm
        ),
    ),
    "select_resolved_candidate": (
        SelectedCandidateInput,
        lambda request, _profile: selection.select_resolved_candidate(
            request.doctype, request.name
        ),
    ),
    "prepare_sales_order": (SalesOrderPrepareInput, _prepare_sales_order),
    "confirm_sales_order": (
        SalesOrderConfirmInput,
        lambda request, _profile: sales_order.confirm_sales_order(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_quotation": (QuotationPrepareInput, _prepare_quotation),
    "confirm_quotation": (
        QuotationConfirmInput,
        lambda request, _profile: quotation.confirm_quotation(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_quotation_to_sales_order": (
        QuotationToSalesOrderInput,
        lambda request, _profile: quotation_to_sales_order.prepare_quotation_to_sales_order(
            request.quotation
        ),
    ),
    "confirm_quotation_to_sales_order": (
        QuotationToSalesOrderConfirmInput,
        lambda request, _profile: quotation_to_sales_order.confirm_quotation_to_sales_order(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_sales_order_to_sales_invoice": (
        SalesOrderToSalesInvoiceInput,
        lambda request, _profile: sales_order_to_sales_invoice.prepare_sales_order_to_sales_invoice(
            request.sales_order
        ),
    ),
    "confirm_sales_order_to_sales_invoice": (
        SalesOrderToSalesInvoiceConfirmInput,
        lambda request, _profile: sales_order_to_sales_invoice.confirm_sales_order_to_sales_invoice(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_sales_invoice": (SalesInvoicePrepareInput, _prepare_sales_invoice),
    "confirm_sales_invoice": (
        SalesInvoiceConfirmInput,
        lambda request, _profile: sales_invoice.confirm_sales_invoice(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_sales_order_to_delivery_note": (
        SalesOrderToDeliveryNoteInput,
        lambda request, _profile: sales_order_to_delivery_note.prepare_sales_order_to_delivery_note(
            request.sales_order
        ),
    ),
    "confirm_sales_order_to_delivery_note": (
        SalesOrderToDeliveryNoteConfirmInput,
        lambda request, _profile: sales_order_to_delivery_note.confirm_sales_order_to_delivery_note(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_delivery_note_to_sales_invoice": (
        DeliveryNoteToSalesInvoiceInput,
        lambda request, _profile: delivery_note_to_sales_invoice.prepare_delivery_note_to_sales_invoice(
            request.delivery_note
        ),
    ),
    "confirm_delivery_note_to_sales_invoice": (
        DeliveryNoteToSalesInvoiceConfirmInput,
        lambda request, _profile: delivery_note_to_sales_invoice.confirm_delivery_note_to_sales_invoice(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_sales_invoice_to_delivery_note": (
        SalesInvoiceToDeliveryNoteInput,
        lambda request, _profile: sales_invoice_to_delivery_note.prepare_sales_invoice_to_delivery_note(
            request.sales_invoice
        ),
    ),
    "confirm_sales_invoice_to_delivery_note": (
        SalesInvoiceToDeliveryNoteConfirmInput,
        lambda request, _profile: sales_invoice_to_delivery_note.confirm_sales_invoice_to_delivery_note(
            request.approval_token, request.confirm
        ),
    ),
    "get_sales_order": (
        GetSalesOrderInput,
        lambda request, _profile: sales_order_read.get_sales_order(
            **request.model_dump()
        ),
    ),
    "query_sales_orders": (
        SalesOrderQueryInput,
        lambda request, _profile: sales_order_read.query_sales_orders(
            request.model_dump()
        ),
    ),
    "aggregate_sales_orders": (
        SalesOrderAggregateInput,
        lambda request, _profile: sales_order_read.aggregate_sales_orders(
            request.model_dump()
        ),
    ),
    "query_sales_order_items": (
        SalesOrderItemQueryInput,
        lambda request, _profile: sales_order_read.query_sales_order_items(
            request.model_dump()
        ),
    ),
    "get_customer": (
        CustomerGetInput,
        lambda request, _profile: customer_read.get_customer(**request.model_dump()),
    ),
    "query_customers": (
        CustomerQueryInput,
        lambda request, _profile: customer_read.query_customers(request.model_dump()),
    ),
    "aggregate_customers": (
        CustomerAggregateInput,
        lambda request, _profile: customer_read.aggregate_customers(
            request.model_dump()
        ),
    ),
    "get_item": (
        ItemGetInput,
        lambda request, _profile: item_read.get_item(**request.model_dump()),
    ),
    "query_items": (
        ItemQueryInput,
        lambda request, _profile: item_read.query_items(request.model_dump()),
    ),
    "aggregate_items": (
        ItemAggregateInput,
        lambda request, _profile: item_read.aggregate_items(request.model_dump()),
    ),
    "get_quotation": (
        QuotationGetInput,
        lambda request, _profile: quotation_read.get_quotation(**request.model_dump()),
    ),
    "query_quotations": (
        QuotationQueryInput,
        lambda request, _profile: quotation_read.query_quotations(request.model_dump()),
    ),
    "aggregate_quotations": (
        QuotationAggregateInput,
        lambda request, _profile: quotation_read.aggregate_quotations(
            request.model_dump()
        ),
    ),
    "get_sales_invoice": (
        SalesInvoiceGetInput,
        lambda request, _profile: sales_invoice_read.get_sales_invoice(
            **request.model_dump()
        ),
    ),
    "query_sales_invoices": (
        SalesInvoiceQueryInput,
        lambda request, _profile: sales_invoice_read.query_sales_invoices(
            request.model_dump()
        ),
    ),
    "aggregate_sales_invoices": (
        SalesInvoiceAggregateInput,
        lambda request, _profile: sales_invoice_read.aggregate_sales_invoices(
            request.model_dump()
        ),
    ),
    "get_delivery_note": (
        DeliveryNoteGetInput,
        lambda request, _profile: delivery_note_read.get_delivery_note(
            **request.model_dump()
        ),
    ),
    "query_delivery_notes": (
        DeliveryNoteQueryInput,
        lambda request, _profile: delivery_note_read.query_delivery_notes(
            request.model_dump()
        ),
    ),
    "aggregate_delivery_notes": (
        DeliveryNoteAggregateInput,
        lambda request, _profile: delivery_note_read.aggregate_delivery_notes(
            request.model_dump()
        ),
    ),
}

_PURCHASE_HANDLERS: dict[str, tuple[type[Any], RemoteHandler]] = {
    "search_suppliers": (
        EntityResolveInput,
        lambda request, _profile: supplier.search_suppliers(request.query),
    ),
    "resolve_supplier": (
        EntityResolveInput,
        lambda request, _profile: supplier.resolve_supplier_for_workflow(request.query),
    ),
    "search_items": (EntityResolveInput, _purchase_search_items),
    "resolve_item": (EntityResolveInput, _purchase_resolve_items),
    "prepare_purchase_order": (PurchaseOrderPrepareInput, _prepare_purchase_order),
    "confirm_purchase_order": (
        PurchaseOrderConfirmInput,
        lambda request, _profile: purchase_order.confirm_purchase_order(
            request.approval_token, request.confirm
        ),
    ),
    "get_purchase_order": (
        DocumentReadInput,
        lambda request, profile: read.get_document(
            request.target.model_dump(), profile
        ),
    ),
    "search_purchase_orders": (
        DocumentSearchInput,
        lambda request, profile: read.search_documents(
            "Purchase Order", request.model_dump(), profile
        ),
    ),
}

_ACCOUNTS_HANDLERS: dict[str, tuple[type[Any], RemoteHandler]] = {
    "prepare_sales_order_advance_payment": (
        SalesOrderAdvancePaymentPrepareInput,
        lambda request, _profile: sales_order_advance_payment.prepare_sales_order_advance_payment(
            request.model_dump(mode="json")
        ),
    ),
    "confirm_sales_order_advance_payment": (
        SalesOrderAdvancePaymentConfirmInput,
        lambda request, _profile: sales_order_advance_payment.confirm_sales_order_advance_payment(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_customer_payment_reconciliation": (
        CustomerPaymentReconciliationPrepareInput,
        lambda request, _profile: customer_payment_reconciliation.prepare_customer_payment_reconciliation(
            request.model_dump(mode="json")
        ),
    ),
    "confirm_customer_payment_reconciliation": (
        CustomerPaymentReconciliationConfirmInput,
        lambda request, _profile: customer_payment_reconciliation.confirm_customer_payment_reconciliation(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_multi_invoice_customer_receipt": (
        MultiInvoiceCustomerReceiptPrepareInput,
        lambda request, _profile: multi_invoice_customer_receipt.prepare_multi_invoice_customer_receipt(
            request.model_dump(mode="json")
        ),
    ),
    "confirm_multi_invoice_customer_receipt": (
        MultiInvoiceCustomerReceiptConfirmInput,
        lambda request, _profile: multi_invoice_customer_receipt.confirm_multi_invoice_customer_receipt(
            request.approval_token, request.confirm
        ),
    ),
    "prepare_sales_invoice_payment": (
        SalesInvoicePaymentPrepareInput,
        lambda request, _profile: sales_invoice_payment.prepare_sales_invoice_payment(
            request.model_dump(mode="json")
        ),
    ),
    "confirm_sales_invoice_payment": (
        SalesInvoicePaymentConfirmInput,
        lambda request, _profile: sales_invoice_payment.confirm_sales_invoice_payment(
            request.approval_token, request.confirm
        ),
    ),
    "get_payment_entry": (
        PaymentEntryGetInput,
        lambda request, _profile: payment_entry_read.get_payment_entry(
            **request.model_dump()
        ),
    ),
    "query_payment_entries": (
        PaymentEntryQueryInput,
        lambda request, _profile: payment_entry_read.query_payment_entries(
            request.model_dump()
        ),
    ),
    "aggregate_payment_entries": (
        PaymentEntryAggregateInput,
        lambda request, _profile: payment_entry_read.aggregate_payment_entries(
            request.model_dump()
        ),
    ),
}


def execute_remote_operation(
    operation: str, profile: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Validate and execute one statically registered public operation."""
    if profile not in {"sales", "purchase", "accounts"} or not isinstance(
        arguments, dict
    ):
        raise RemoteOperationError("The remote operation request is invalid.")
    handlers = {
        "sales": _SALES_HANDLERS,
        "purchase": _PURCHASE_HANDLERS,
        "accounts": _ACCOUNTS_HANDLERS,
    }[profile]
    definition = handlers.get(operation) or _SHARED_HANDLERS.get(operation)
    if definition is None:
        raise RemoteOperationError("The requested remote operation is unavailable.")
    model, handler = definition
    return handler(_model(model, arguments), profile)
