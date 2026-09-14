"""Permission-safe native Sales Order to Draft Sales Invoice conversion."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import public_error
from ..common.fingerprint import stable_fingerprint

_ACTION = "convert_sales_order_to_sales_invoice"
_SOURCE_DOCTYPE = "Sales Order"
_TARGET_DOCTYPE = "Sales Invoice"


def _native_make_sales_invoice(source_name: str) -> Any:
    """Use ERPNext's installed mapper with its normal permission behavior."""

    from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

    return make_sales_invoice(
        source_name,
        target_doc=None,
        args={},
        ignore_permissions=False,
    )


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return public_error(code, message=message, retryable=retryable)


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _load_source(name: str) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        sales_order = frappe.get_doc(_SOURCE_DOCTYPE, name)
    except frappe.DoesNotExistError:
        return None, _error(
            "SOURCE_NOT_FOUND", "The requested Sales Order was not found."
        )
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot read that Sales Order.",
        )

    if not sales_order.has_permission("read"):
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot read that Sales Order.",
        )
    if int(sales_order.docstatus) != 1:
        return None, _error(
            "SOURCE_NOT_READY",
            "Only a Submitted Sales Order can be converted to a Sales Invoice.",
        )
    if not frappe.has_permission(_TARGET_DOCTYPE, "create"):
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot create the converted Sales Invoice.",
        )
    return sales_order, None


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _field(doc: Any, fieldname: str) -> Any:
    return _json_value(doc.get(fieldname))


def _stable_rows(
    doc: Any, table_field: str, fieldnames: tuple[str, ...]
) -> list[dict[str, Any]]:
    return [
        {fieldname: _field(row, fieldname) for fieldname in fieldnames}
        for row in doc.get(table_field) or []
    ]


def _source_item_preview(row: Any) -> dict[str, Any]:
    return {
        "name": _field(row, "name"),
        "item_code": _field(row, "item_code"),
        "uom": _field(row, "uom"),
        "stock_uom": _field(row, "stock_uom"),
        "conversion_factor": _field(row, "conversion_factor"),
        "qty": _field(row, "qty"),
        "delivered_qty": _field(row, "delivered_qty"),
        "returned_qty": _field(row, "returned_qty"),
        "billed_qty": _field(row, "billed_qty"),
        "billed_amt": _field(row, "billed_amt"),
        "rate": _field(row, "rate"),
        "amount": _field(row, "amount"),
        "warehouse": _field(row, "warehouse"),
        "project": _field(row, "project"),
    }


def _target_item_preview(row: Any) -> dict[str, Any]:
    return {
        "item_code": _field(row, "item_code"),
        "item_name": _field(row, "item_name"),
        "qty": _field(row, "qty"),
        "uom": _field(row, "uom"),
        "conversion_factor": _field(row, "conversion_factor"),
        "rate": _field(row, "rate"),
        "amount": _field(row, "amount"),
        "warehouse": _field(row, "warehouse"),
        "project": _field(row, "project"),
        "sales_order": _field(row, "sales_order"),
        "so_detail": _field(row, "so_detail"),
    }


def _tax_preview(row: Any) -> dict[str, Any]:
    return {
        "charge_type": _field(row, "charge_type"),
        "account_head": _field(row, "account_head"),
        "rate": _field(row, "rate"),
        "tax_amount": _field(row, "tax_amount"),
        "total": _field(row, "total"),
    }


def _payment_schedule_preview(row: Any) -> dict[str, Any]:
    return {
        "due_date": _field(row, "due_date"),
        "payment_term": _field(row, "payment_term"),
        "invoice_portion": _field(row, "invoice_portion"),
        "payment_amount": _field(row, "payment_amount"),
        "discount_type": _field(row, "discount_type"),
        "discount_date": _field(row, "discount_date"),
        "discount": _field(row, "discount"),
    }


def _preview(sales_order: Any, sales_invoice: Any) -> dict[str, Any]:
    return {
        "source": {
            "doctype": _SOURCE_DOCTYPE,
            "name": sales_order.name,
            "docstatus": int(sales_order.docstatus),
            "status": _field(sales_order, "status"),
            "customer": _field(sales_order, "customer"),
            "customer_name": _field(sales_order, "customer_name"),
            "company": _field(sales_order, "company"),
            "currency": _field(sales_order, "currency"),
            "transaction_date": _field(sales_order, "transaction_date"),
            "delivery_date": _field(sales_order, "delivery_date"),
            "per_billed": _field(sales_order, "per_billed"),
            "per_delivered": _field(sales_order, "per_delivered"),
            "per_returned": _field(sales_order, "per_returned"),
            "total_qty": _field(sales_order, "total_qty"),
            "net_total": _field(sales_order, "net_total"),
            "total_taxes_and_charges": _field(sales_order, "total_taxes_and_charges"),
            "grand_total": _field(sales_order, "grand_total"),
            "items": [
                _source_item_preview(row) for row in sales_order.get("items") or []
            ],
        },
        "sales_invoice": {
            "target_doctype": _TARGET_DOCTYPE,
            "customer": _field(sales_invoice, "customer"),
            "customer_name": _field(sales_invoice, "customer_name"),
            "company": _field(sales_invoice, "company"),
            "posting_date": _field(sales_invoice, "posting_date"),
            "due_date": _field(sales_invoice, "due_date"),
            "currency": _field(sales_invoice, "currency"),
            "selling_price_list": _field(sales_invoice, "selling_price_list"),
            "debit_to": _field(sales_invoice, "debit_to"),
            "billing_address": _field(sales_invoice, "billing_address"),
            "shipping_address": _field(sales_invoice, "shipping_address"),
            "company_address": _field(sales_invoice, "company_address"),
            "items": [
                _target_item_preview(row) for row in sales_invoice.get("items") or []
            ],
            "taxes": [_tax_preview(row) for row in sales_invoice.get("taxes") or []],
            "payment_schedule": [
                _payment_schedule_preview(row)
                for row in sales_invoice.get("payment_schedule") or []
            ],
            "totals": {
                "net_total": _field(sales_invoice, "net_total"),
                "total_taxes_and_charges": _field(
                    sales_invoice, "total_taxes_and_charges"
                ),
                "grand_total": _field(sales_invoice, "grand_total"),
                "rounded_total": _field(sales_invoice, "rounded_total"),
                "outstanding_amount": _field(sales_invoice, "outstanding_amount"),
                "base_net_total": _field(sales_invoice, "base_net_total"),
                "base_grand_total": _field(sales_invoice, "base_grand_total"),
                "total_qty": _field(sales_invoice, "total_qty"),
            },
        },
    }


def _fingerprint(preview: dict[str, Any]) -> str:
    """Hash stable source state and the effective native target projection."""

    return stable_fingerprint(preview)


def _map_and_preview(
    sales_order: Any,
) -> tuple[Any | None, dict[str, Any] | None, dict[str, Any] | None]:
    try:
        sales_invoice = _native_make_sales_invoice(sales_order.name)
    except frappe.PermissionError:
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot perform that conversion.",
            ),
        )
    except frappe.ValidationError:
        return (
            None,
            None,
            _error(
                "NATIVE_VALIDATION_FAILED",
                "ERPNext rejected the Sales Order to Sales Invoice conversion.",
            ),
        )
    except Exception:
        return (
            None,
            None,
            _error(
                "CONVERSION_UNAVAILABLE",
                "ERPNext could not prepare this Sales Order conversion.",
            ),
        )

    if int(sales_invoice.docstatus or 0) != 0:
        return (
            None,
            None,
            _error(
                "CONVERSION_UNAVAILABLE",
                "The mapped Sales Invoice is not a Draft.",
            ),
        )
    if not sales_invoice.get("items"):
        return (
            None,
            None,
            _error(
                "NO_MAPPABLE_ITEMS",
                "No remaining billable Sales Order items are available for a Sales Invoice.",
            ),
        )
    return sales_invoice, _preview(sales_order, sales_invoice), None


def prepare_sales_order_to_sales_invoice(sales_order: str) -> dict[str, Any]:
    """Prepare a native Draft Sales Invoice preview without persisting it."""

    approvals.prune_expired()
    user = _current_user()
    source, failure = _load_source(
        sales_order.strip() if isinstance(sales_order, str) else ""
    )
    if failure:
        return failure

    target, preview, failure = _map_and_preview(source)
    if failure:
        return failure
    assert target is not None and preview is not None and source is not None
    token = approvals.create(
        action=_ACTION,
        site=frappe.local.site,
        user=user,
        payload={
            "source_doctype": _SOURCE_DOCTYPE,
            "source_name": source.name,
            "fingerprint": _fingerprint(preview),
            "projection": preview,
        },
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": preview,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def _stale() -> dict[str, Any]:
    return _error(
        "STALE_CONFIRMATION",
        "The Sales Order conversion changed after the preview was prepared. Please prepare it again.",
    )


def confirm_sales_order_to_sales_invoice(
    approval_token: str, confirm: bool
) -> dict[str, Any]:
    """Create one freshly revalidated native mapped Draft Sales Invoice."""

    user = _current_user()
    if not confirm:
        approvals.cancel(
            approval_token,
            action=_ACTION,
            site=frappe.local.site,
            user=user,
        )
        return _error(
            "CONFIRMATION_REQUIRED",
            "Review the conversion preview before confirming it.",
        )

    approval, state = approvals.claim_for_confirm_write(
        approval_token,
        action=_ACTION,
        site=frappe.local.site,
        user=user,
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(
            state, "Sales Invoice conversion"
        )
        return _error(code, message, retryable=retryable)

    payload = approval.payload
    if (
        payload.get("source_doctype") != _SOURCE_DOCTYPE
        or not payload.get("source_name")
        or not payload.get("fingerprint")
        or not isinstance(payload.get("projection"), dict)
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE",
            "This conversion confirmation is not available.",
        )

    source, failure = _load_source(payload["source_name"])
    if failure:
        if failure.get("code") == "PERMISSION_DENIED":
            return failure
        return _stale()

    target, preview, failure = _map_and_preview(source)
    if failure or target is None or preview is None:
        if failure and failure.get("code") == "PERMISSION_DENIED":
            return failure
        return _stale()
    if _fingerprint(preview) != payload["fingerprint"]:
        return _stale()

    try:
        target.insert(
            ignore_permissions=False,
            ignore_links=False,
            ignore_mandatory=False,
        )
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot create the converted Sales Invoice.",
        )
    except frappe.ValidationError:
        frappe.db.rollback()
        return _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected the converted Sales Invoice during final validation.",
        )
    except Exception:
        frappe.db.rollback()
        return _error(
            "CONVERSION_FAILED",
            "ERPNext could not create the converted Sales Invoice.",
        )

    return {
        "status": "created",
        "doctype": _TARGET_DOCTYPE,
        "sales_invoice": target.name,
        "docstatus": int(target.docstatus),
        "source_sales_order": source.name,
        "customer": _field(target, "customer"),
        "company": _field(target, "company"),
        "currency": _field(target, "currency"),
        "grand_total": _field(target, "grand_total"),
        "idempotent": False,
    }
