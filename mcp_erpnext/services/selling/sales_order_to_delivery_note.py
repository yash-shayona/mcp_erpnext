"""Permission-safe native Sales Order to Draft Delivery Note conversion."""

from __future__ import annotations
from decimal import Decimal
from typing import Any
import frappe
from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...public_errors import defined_error
from ..common.fingerprint import stable_fingerprint
from ..common.write_policy import (
    approval_entry_failure,
    current_mode,
    disabled_failure,
    direct_entry_failure,
    exact_mode_failure,
)
from ...settings import WriteMode

_ACTION = "convert_sales_order_to_delivery_note"
_SOURCE = "Sales Order"
_TARGET = "Delivery Note"


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _user():
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _value(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_value(v) for v in value]
    return value


def _field(doc, name):
    return _value(doc.get(name))


def _load(name):
    try:
        doc = frappe.get_doc(_SOURCE, name)
    except frappe.DoesNotExistError:
        return None, _error(
            "SOURCE_NOT_FOUND"
        )
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED"
        )
    if not doc.has_permission("read"):
        return None, _error(
            "PERMISSION_DENIED"
        )
    if int(doc.docstatus) != 1:
        return None, _error(
            "SOURCE_NOT_READY",
        )
    if not frappe.has_permission(_TARGET, "create"):
        return None, _error(
            "PERMISSION_DENIED",
        )
    return doc, None


def _native(name):
    from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

    return make_delivery_note(name, target_doc=None, kwargs={})


def _item(row):
    return {
        k: _field(row, k)
        for k in (
            "item_code",
            "item_name",
            "qty",
            "uom",
            "rate",
            "amount",
            "warehouse",
            "against_sales_order",
            "so_detail",
        )
    }


def _preview(source, target):
    return {
        "source": {
            "doctype": _SOURCE,
            "name": source.name,
            "docstatus": int(source.docstatus),
            "status": _field(source, "status"),
            "customer": _field(source, "customer"),
            "company": _field(source, "company"),
            "currency": _field(source, "currency"),
            "per_delivered": _field(source, "per_delivered"),
        },
        "delivery_note": {
            "target_doctype": _TARGET,
            "customer": _field(target, "customer"),
            "customer_name": _field(target, "customer_name"),
            "company": _field(target, "company"),
            "posting_date": _field(target, "posting_date"),
            "posting_time": _field(target, "posting_time"),
            "currency": _field(target, "currency"),
            "items": [_item(r) for r in target.get("items") or []],
            "packed_item_count": len(target.get("packed_items") or []),
            "has_serial_batch_requirements": any(
                bool(r.get("has_serial_no") or r.get("has_batch_no"))
                for r in target.get("items") or []
            ),
            "totals": {
                k: _field(target, k)
                for k in (
                    "total_qty",
                    "net_total",
                    "total_taxes_and_charges",
                    "grand_total",
                )
            },
            "warning": "Submitting may create stock and, depending on ERPNext configuration and item types, accounting effects.",
        },
    }


def _map(source):
    try:
        target = _native(source.name)
    except frappe.PermissionError:
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
            ),
        )
    except frappe.ValidationError:
        return (
            None,
            None,
            _error(
                "NATIVE_VALIDATION_FAILED",
            ),
        )
    except Exception:
        return (
            None,
            None,
            _error(
                "CONVERSION_UNAVAILABLE",
            ),
        )
    if int(target.docstatus or 0) != 0:
        return (
            None,
            None,
            _error(
                "CONVERSION_UNAVAILABLE"
            ),
        )
    if not target.get("items"):
        return (
            None,
            None,
            _error(
                "NO_MAPPABLE_ITEMS",
            ),
        )
    return target, _preview(source, target), None


def _fingerprint(preview):
    return stable_fingerprint(
        preview, ignored_paths={("delivery_note", "posting_time")}
    )


def prepare_sales_order_to_delivery_note(sales_order):
    if failure := disabled_failure("create"):
        return _error(failure.code)
    user = _user()
    source, failure = _load(sales_order.strip() if isinstance(sales_order, str) else "")
    if failure:
        return failure
    target, preview, failure = _map(source)
    if failure:
        return failure
    if current_mode("create") is WriteMode.DIRECT:
        return {"status": "preview", "preview": preview}
    approvals.prune_expired()
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
    )


def confirm_sales_order_to_delivery_note(approval_token, confirm):
    if failure := approval_entry_failure("create"):
        return _error(failure.code)
    user = _user()
    if not confirm:
        approvals.cancel(
            approval_token, action=_ACTION, site=frappe.local.site, user=user
        )
        return _error(
            "CONFIRMATION_REQUIRED",
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(
            state, "Delivery Note conversion"
        )
        return _error(code, retryable=retryable)
    payload = approval.payload
    if (
        payload.get("source_doctype") != _SOURCE
        or not payload.get("source_name")
        or not payload.get("fingerprint")
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE"
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
        if failure := exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED):
            return _error(failure.code)
        target.insert(
            ignore_permissions=False, ignore_links=False, ignore_mandatory=False
        )
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED",
        )
    except frappe.ValidationError:
        frappe.db.rollback()
        return _error(
            "NATIVE_VALIDATION_FAILED",
        )
    except Exception:
        frappe.db.rollback()
        return _error(
            "CONVERSION_FAILED"
        )
    return {
        "status": "created",
        "doctype": _TARGET,
        "delivery_note": target.name,
        "docstatus": int(target.docstatus),
        "source_sales_order": source.name,
        "customer": _field(target, "customer"),
        "company": _field(target, "company"),
        "currency": _field(target, "currency"),
        "grand_total": _field(target, "grand_total"),
        "item_count": len(target.get("items") or []),
    }


def execute_sales_order_to_delivery_note(sales_order):
    """Create a fresh mapped Delivery Note only when CREATE policy is direct."""
    if failure := direct_entry_failure("create"):
        return _error(failure.code)
    _user()
    source, failure = _load(sales_order.strip() if isinstance(sales_order, str) else "")
    if failure:
        return failure
    target, _preview_data, failure = _map(source)
    if failure or target is None:
        return failure or _error(
            "CONVERSION_UNAVAILABLE"
        )
    try:
        if failure := exact_mode_failure("create", WriteMode.DIRECT):
            return _error(failure.code)
        target.insert(
            ignore_permissions=False, ignore_links=False, ignore_mandatory=False
        )
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED",
        )
    except frappe.ValidationError:
        frappe.db.rollback()
        return _error(
            "NATIVE_VALIDATION_FAILED",
        )
    except Exception:
        frappe.db.rollback()
        return _error(
            "CONVERSION_FAILED"
        )
    return {
        "status": "created",
        "doctype": _TARGET,
        "delivery_note": target.name,
        "docstatus": int(target.docstatus),
        "source_sales_order": source.name,
        "customer": _field(target, "customer"),
        "company": _field(target, "company"),
        "currency": _field(target, "currency"),
        "grand_total": _field(target, "grand_total"),
        "item_count": len(target.get("items") or []),
    }
