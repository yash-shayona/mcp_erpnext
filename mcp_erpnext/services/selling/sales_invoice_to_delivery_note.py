"""Permission-safe native Sales Invoice to Draft Delivery Note conversion."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import public_error
from ..common.fingerprint import stable_fingerprint

_ACTION = "convert_sales_invoice_to_delivery_note"
_SOURCE = "Sales Invoice"
_TARGET = "Delivery Note"


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return public_error(code, message=message, retryable=retryable)


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
    return user


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    return value


def _field(doc: Any, name: str) -> Any:
    return _value(doc.get(name))


def _load(name: str) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        source = frappe.get_doc(_SOURCE, name)
    except frappe.DoesNotExistError:
        return None, _error("SOURCE_NOT_FOUND", "The requested Sales Invoice was not found.")
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot read that Sales Invoice.",
        )

    if not source.has_permission("read"):
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot read that Sales Invoice.",
        )
    if int(source.docstatus) != 1:
        return None, _error(
            "SOURCE_NOT_READY",
            "Only a Submitted Sales Invoice can be converted to a Delivery Note.",
        )
    if int(source.get("is_return") or 0) == 1:
        return None, _error(
            "SOURCE_NOT_ELIGIBLE",
            "A return Sales Invoice is not eligible for normal Delivery Note conversion.",
        )
    if int(source.get("update_stock") or 0) == 1:
        return None, _error(
            "SOURCE_NOT_ELIGIBLE",
            "A Sales Invoice with Update Stock already performs its stock delivery path and is not eligible for a separate Delivery Note.",
        )
    if not frappe.has_permission(_TARGET, "create"):
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot create the converted Delivery Note.",
        )
    return source, None


def _native(name: str) -> Any:
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note

    return make_delivery_note(name, target_doc=None)


def _item(row: Any) -> dict[str, Any]:
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
            "against_sales_invoice",
            "si_detail",
            "against_sales_order",
            "so_detail",
        )
    }


def _preview(source: Any, target: Any) -> dict[str, Any]:
    rows = target.get("items") or []
    return {
        "source": {
            "doctype": _SOURCE,
            "name": source.name,
            "docstatus": int(source.docstatus),
            "status": _field(source, "status"),
            "customer": _field(source, "customer"),
            "customer_name": _field(source, "customer_name"),
            "company": _field(source, "company"),
            "posting_date": _field(source, "posting_date"),
            "currency": _field(source, "currency"),
            "update_stock": int(source.get("update_stock") or 0),
            "is_return": int(source.get("is_return") or 0),
            "total_qty": _field(source, "total_qty"),
            "grand_total": _field(source, "grand_total"),
        },
        "delivery_note": {
            "target_doctype": _TARGET,
            "customer": _field(target, "customer"),
            "customer_name": _field(target, "customer_name"),
            "company": _field(target, "company"),
            "posting_date": _field(target, "posting_date"),
            "posting_time": _field(target, "posting_time"),
            "currency": _field(target, "currency"),
            "items": [_item(row) for row in rows],
            "packed_item_count": len(target.get("packed_items") or []),
            "has_serial_batch_requirements": any(
                bool(row.get("has_serial_no") or row.get("has_batch_no")) for row in rows
            ),
            "totals": {
                key: _field(target, key)
                for key in ("total_qty", "net_total", "total_taxes_and_charges", "grand_total")
            },
            "warning": "Submitting may create stock and, depending on ERPNext configuration and item types, accounting effects.",
        },
    }


def _map(source: Any) -> tuple[Any | None, dict[str, Any] | None, dict[str, Any] | None]:
    try:
        target = _native(source.name)
    except frappe.PermissionError:
        return None, None, _error(
            "PERMISSION_DENIED", "The authenticated user cannot perform that conversion."
        )
    except frappe.ValidationError:
        return None, None, _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected the Sales Invoice to Delivery Note conversion.",
        )
    except Exception:
        return None, None, _error(
            "CONVERSION_UNAVAILABLE",
            "ERPNext could not prepare this Sales Invoice conversion.",
        )

    if int(target.docstatus or 0) != 0:
        return None, None, _error("CONVERSION_UNAVAILABLE", "The mapped Delivery Note is not a Draft.")
    if not target.get("items"):
        return None, None, _error(
            "NO_MAPPABLE_ITEMS",
            "No remaining deliverable Sales Invoice items are available for a Delivery Note.",
        )
    return target, _preview(source, target), None


def _fingerprint(preview: dict[str, Any]) -> str:
    return stable_fingerprint(preview, ignored_paths={("delivery_note", "posting_time")})


def prepare_sales_invoice_to_delivery_note(sales_invoice: str) -> dict[str, Any]:
    approvals.prune_expired()
    user = _user()
    source, failure = _load(sales_invoice.strip() if isinstance(sales_invoice, str) else "")
    if failure:
        return failure
    target, preview, failure = _map(source)
    if failure:
        return failure
    assert target is not None and preview is not None and source is not None
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


def _stale() -> dict[str, Any]:
    return _error(
        "STALE_CONFIRMATION",
        "The Sales Invoice conversion changed after the preview was prepared. Please prepare it again.",
    )


def confirm_sales_invoice_to_delivery_note(
    approval_token: str, confirm: bool
) -> dict[str, Any]:
    user = _user()
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=frappe.local.site, user=user)
        return _error(
            "CONFIRMATION_REQUIRED",
            "Review the conversion preview before confirming it.",
        )

    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Delivery Note conversion")
        return _error(code, message, retryable=retryable)

    payload = approval.payload
    if (
        payload.get("source_doctype") != _SOURCE
        or not payload.get("source_name")
        or not payload.get("fingerprint")
    ):
        return _error("CONFIRMATION_UNAVAILABLE", "This conversion confirmation is not available.")

    source, failure = _load(payload["source_name"])
    if failure:
        return failure if failure.get("code") == "PERMISSION_DENIED" else _stale()
    target, preview, failure = _map(source)
    if failure or _fingerprint(preview) != payload["fingerprint"]:
        return failure if failure and failure.get("code") == "PERMISSION_DENIED" else _stale()

    try:
        target.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot create the converted Delivery Note.",
        )
    except frappe.ValidationError:
        frappe.db.rollback()
        return _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected the converted Delivery Note during final validation.",
        )
    except Exception:
        frappe.db.rollback()
        return _error("CONVERSION_FAILED", "ERPNext could not create the converted Delivery Note.")

    return {
        "status": "created",
        "doctype": _TARGET,
        "delivery_note": target.name,
        "docstatus": int(target.docstatus),
        "source_sales_invoice": source.name,
        "customer": _field(target, "customer"),
        "company": _field(target, "company"),
        "currency": _field(target, "currency"),
        "grand_total": _field(target, "grand_total"),
        "item_count": len(target.get("items") or []),
    }
