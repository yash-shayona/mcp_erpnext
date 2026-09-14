"""Permission-safe native Delivery Note to Draft Sales Invoice conversion."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import public_error

_ACTION = "convert_delivery_note_to_sales_invoice"
_SOURCE = "Delivery Note"
_TARGET = "Sales Invoice"


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return public_error(code, message=message, retryable=retryable)


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _field(doc: Any, name: str) -> Any:
    value = doc.get(name)
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _load(name: str):
    try:
        doc = frappe.get_doc(_SOURCE, name)
    except frappe.DoesNotExistError:
        return None, _error(
            "SOURCE_NOT_FOUND", "The requested Delivery Note was not found."
        )
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot read that Delivery Note.",
        )
    if not doc.has_permission("read"):
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot read that Delivery Note.",
        )
    if int(doc.docstatus) != 1:
        return None, _error(
            "SOURCE_NOT_READY",
            "Only a Submitted Delivery Note can be converted to a Sales Invoice.",
        )
    if not frappe.has_permission(_TARGET, "create"):
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot create the converted Sales Invoice.",
        )
    return doc, None


def _native(name: str) -> Any:
    from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

    return make_sales_invoice(name, target_doc=None, args={})


def _row(row: Any) -> dict[str, Any]:
    return {
        key: _field(row, key)
        for key in (
            "item_code",
            "item_name",
            "qty",
            "uom",
            "conversion_factor",
            "rate",
            "amount",
            "warehouse",
            "delivery_note",
            "dn_detail",
            "sales_order",
            "so_detail",
        )
    }


def _tax(row: Any) -> dict[str, Any]:
    return {
        key: _field(row, key)
        for key in ("charge_type", "account_head", "rate", "tax_amount", "total")
    }


def _schedule(row: Any) -> dict[str, Any]:
    return {
        key: _field(row, key)
        for key in (
            "due_date",
            "payment_term",
            "invoice_portion",
            "payment_amount",
            "discount_type",
            "discount_date",
            "discount",
        )
    }


def _preview(source: Any, target: Any) -> dict[str, Any]:
    return {
        "source": {
            key: _field(source, key)
            for key in (
                "status",
                "customer",
                "customer_name",
                "company",
                "currency",
                "posting_date",
                "is_return",
                "total_qty",
                "net_total",
                "grand_total",
            )
        },
        "sales_invoice": {
            "target_doctype": _TARGET,
            "customer": _field(target, "customer"),
            "customer_name": _field(target, "customer_name"),
            "company": _field(target, "company"),
            "posting_date": _field(target, "posting_date"),
            "due_date": _field(target, "due_date"),
            "currency": _field(target, "currency"),
            "items": [_row(row) for row in target.get("items") or []],
            "taxes": [_tax(row) for row in target.get("taxes") or []],
            "payment_schedule": [
                _schedule(row) for row in target.get("payment_schedule") or []
            ],
            "totals": {
                key: _field(target, key)
                for key in (
                    "net_total",
                    "total_taxes_and_charges",
                    "grand_total",
                    "rounded_total",
                    "outstanding_amount",
                    "total_qty",
                )
            },
            "doctype": _SOURCE,
            "name": source.name,
            "docstatus": int(source.docstatus),
        },
    }


def _fingerprint(preview: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(preview, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _map(source: Any):
    try:
        target = _native(source.name)
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
                "NO_MAPPABLE_ITEMS",
                "No remaining invoiceable Delivery Note items are available for a Sales Invoice.",
            ),
        )
    except Exception:
        return (
            None,
            None,
            _error(
                "CONVERSION_UNAVAILABLE",
                "ERPNext could not prepare this Delivery Note conversion.",
            ),
        )
    if int(target.docstatus or 0) != 0:
        return (
            None,
            None,
            _error(
                "CONVERSION_UNAVAILABLE", "The mapped Sales Invoice is not a Draft."
            ),
        )
    if not target.get("items"):
        return (
            None,
            None,
            _error(
                "NO_MAPPABLE_ITEMS",
                "No remaining invoiceable Delivery Note items are available for a Sales Invoice.",
            ),
        )
    return target, _preview(source, target), None


def prepare_delivery_note_to_sales_invoice(delivery_note: str) -> dict[str, Any]:
    approvals.prune_expired()
    user = _user()
    source, failure = _load(
        delivery_note.strip() if isinstance(delivery_note, str) else ""
    )
    if failure:
        return failure
    target, preview, failure = _map(source)
    if failure:
        return failure
    token = approvals.create(
        action=_ACTION,
        site=frappe.local.site,
        user=user,
        payload={
            "source_doctype": _SOURCE,
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


def _stale():
    return _error(
        "STALE_CONFIRMATION",
        "The Delivery Note conversion changed after the preview was prepared. Please prepare it again.",
    )


def confirm_delivery_note_to_sales_invoice(
    approval_token: str, confirm: bool
) -> dict[str, Any]:
    user = _user()
    if not confirm:
        approvals.cancel(
            approval_token, action=_ACTION, site=frappe.local.site, user=user
        )
        return _error(
            "CONFIRMATION_REQUIRED",
            "Review the conversion preview before confirming it.",
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(
            state, "Sales Invoice conversion"
        )
        return _error(code, message, retryable=retryable)
    payload = approval.payload
    if (
        payload.get("source_doctype") != _SOURCE
        or not payload.get("source_name")
        or not payload.get("fingerprint")
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE", "This conversion confirmation is not available."
        )
    source, failure = _load(payload["source_name"])
    if failure:
        return failure if failure.get("code") == "PERMISSION_DENIED" else _stale()
    target, preview, failure = _map(source)
    if failure or _fingerprint(preview) != payload["fingerprint"]:
        return (
            failure
            if failure and failure.get("code") == "PERMISSION_DENIED"
            else _stale()
        )
    try:
        target.insert(
            ignore_permissions=False, ignore_links=False, ignore_mandatory=False
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
            "CONVERSION_FAILED", "ERPNext could not create the converted Sales Invoice."
        )
    return {
        "status": "created",
        "doctype": _TARGET,
        "sales_invoice": target.name,
        "docstatus": int(target.docstatus),
        "source_delivery_note": source.name,
        "customer": _field(target, "customer"),
        "company": _field(target, "company"),
        "currency": _field(target, "currency"),
        "grand_total": _field(target, "grand_total"),
        "item_count": len(target.get("items") or []),
    }
