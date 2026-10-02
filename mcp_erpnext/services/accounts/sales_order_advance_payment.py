"""Native, approval-bound Sales Order Customer advance workflow."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import frappe
from frappe.utils import flt, getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import new_error_reference
from ..common.fingerprint import stable_fingerprint
from .multi_invoice_customer_receipt import _destination

_ACTION = "create_sales_order_advance_payment"
_SOURCE = "Sales Order"
_TARGET = "Payment Entry"
_MAX_REFERENCES = 50
_MAX_REMARKS = 1000


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": retryable,
    }


def _value(doc: Any, field: str, default: Any = None) -> Any:
    getter = getattr(doc, "get", None)
    return getter(field, default) if callable(getter) else getattr(doc, field, default)


def _json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    return str(value)


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _source_name(request: dict[str, Any]) -> str | None:
    value = request.get("sales_order")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _native_factory():
    """Load ERPNext's factory lazily so the service remains import-safe."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    return get_payment_entry


def _valid_amount(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _load_source(name: str | None) -> tuple[Any | None, dict[str, Any] | None]:
    if not name:
        return None, _error(
            "INVALID_SALES_ORDER", "An exact Sales Order name is required."
        )
    try:
        source = frappe.get_doc(_SOURCE, name)
    except frappe.DoesNotExistError:
        return None, _error("SALES_ORDER_NOT_FOUND", "The Sales Order was not found.")
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED", "The authenticated user cannot read the Sales Order."
        )

    if not source.has_permission("read"):
        return None, _error(
            "PERMISSION_DENIED", "The authenticated user cannot read the Sales Order."
        )
    if int(_value(source, "docstatus", 0) or 0) != 1:
        return None, _error(
            "SALES_ORDER_NOT_SUBMITTED",
            "Customer advance V1 requires a submitted Sales Order.",
        )
    if str(_value(source, "status", "")) in {"Closed", "Cancelled"}:
        return None, _error(
            "SALES_ORDER_NOT_ELIGIBLE",
            "The Sales Order is no longer eligible for a Customer advance.",
        )
    if not _value(source, "customer") or not _value(source, "company"):
        return None, _error(
            "SALES_ORDER_NOT_ELIGIBLE",
            "The Sales Order does not have a valid Customer and Company.",
        )
    try:
        if not frappe.has_permission(_TARGET, "create"):
            return None, _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot create a Payment Entry.",
            )
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot create a Payment Entry.",
        )
    return source, None


def _reference_preview(row: Any) -> dict[str, Any]:
    return {
        "reference_doctype": _value(row, "reference_doctype"),
        "reference_name": _value(row, "reference_name"),
        "due_date": _json(_value(row, "due_date")),
        "total_amount": flt(_value(row, "total_amount")),
        "outstanding_amount": flt(_value(row, "outstanding_amount")),
        "allocated_amount": flt(_value(row, "allocated_amount")),
        "payment_term": _value(row, "payment_term"),
    }


def _preview(doc: Any, source: Any, destination: dict[str, Any]) -> dict[str, Any]:
    return {
        "doctype": _TARGET,
        "docstatus": int(_value(doc, "docstatus", 0) or 0),
        "source_sales_order": str(_value(source, "name")),
        "source_status": str(_value(source, "status", "Submitted")),
        "customer": str(_value(doc, "party")),
        "company": str(_value(doc, "company")),
        "payment_type": "Receive",
        "posting_date": _json(_value(doc, "posting_date")),
        "mode_of_payment": _value(doc, "mode_of_payment"),
        "destination_kind": destination["kind"],
        "destination": destination["identity"],
        "party_account_currency": str(_value(doc, "paid_from_account_currency")),
        "destination_account_currency": str(_value(doc, "paid_to_account_currency")),
        "paid_amount": flt(_value(doc, "paid_amount")),
        "received_amount": flt(_value(doc, "received_amount")),
        "source_exchange_rate": flt(_value(doc, "source_exchange_rate")),
        "target_exchange_rate": flt(_value(doc, "target_exchange_rate")),
        "order_total": _value(source, "grand_total"),
        "existing_advance_paid": _value(source, "advance_paid"),
        "payment_terms_template": _value(source, "payment_terms_template"),
        "references": [
            _reference_preview(row) for row in (_value(doc, "references", []) or [])
        ],
        "total_allocated_amount": flt(_value(doc, "total_allocated_amount")),
        "unallocated_amount": flt(_value(doc, "unallocated_amount")),
        "difference_amount": flt(_value(doc, "difference_amount")),
        "reference_no": _value(doc, "reference_no"),
        "reference_date": _json(_value(doc, "reference_date")),
        "separate_advance_account": bool(
            _value(doc, "book_advance_payments_in_separate_party_account", False)
        ),
        "remarks": _value(doc, "remarks"),
        "note": "Draft only; no ledger or Sales Order advance effect occurs until the Payment Entry is separately submitted.",
    }


def _source_fingerprint_material(source: Any) -> dict[str, Any]:
    return {
        "name": _value(source, "name"),
        "docstatus": int(_value(source, "docstatus", 0) or 0),
        "modified": _value(source, "modified"),
        "status": _value(source, "status"),
        "customer": _value(source, "customer"),
        "company": _value(source, "company"),
        "currency": _value(source, "currency"),
        "grand_total": _value(source, "grand_total"),
        "rounded_total": _value(source, "rounded_total"),
        "base_grand_total": _value(source, "base_grand_total"),
        "base_rounded_total": _value(source, "base_rounded_total"),
        "advance_paid": _value(source, "advance_paid"),
        "payment_terms_template": _value(source, "payment_terms_template"),
        "payment_schedule": [
            {
                key: _json(_value(row, key))
                for key in (
                    "payment_term",
                    "due_date",
                    "payment_amount",
                    "outstanding",
                    "paid_amount",
                    "discount",
                    "discount_type",
                )
            }
            for row in (_value(source, "payment_schedule", []) or [])
        ],
    }


def _native_fingerprint_material(doc: Any) -> dict[str, Any]:
    return {
        "party": _value(doc, "party"),
        "company": _value(doc, "company"),
        "payment_type": _value(doc, "payment_type"),
        "party_account": _value(doc, "party_account"),
        "paid_from": _value(doc, "paid_from"),
        "paid_to": _value(doc, "paid_to"),
        "paid_from_account_currency": _value(doc, "paid_from_account_currency"),
        "paid_to_account_currency": _value(doc, "paid_to_account_currency"),
        "paid_amount": _value(doc, "paid_amount"),
        "received_amount": _value(doc, "received_amount"),
        "source_exchange_rate": _value(doc, "source_exchange_rate"),
        "target_exchange_rate": _value(doc, "target_exchange_rate"),
        "book_advance_payments_in_separate_party_account": _value(
            doc, "book_advance_payments_in_separate_party_account"
        ),
        "references": [
            {
                key: _json(_value(row, key))
                for key in (
                    "reference_doctype",
                    "reference_name",
                    "due_date",
                    "total_amount",
                    "outstanding_amount",
                    "allocated_amount",
                    "payment_term",
                    "payment_request",
                )
            }
            for row in (_value(doc, "references", []) or [])
        ],
    }


def _fingerprint(
    request: dict[str, Any],
    source: Any,
    doc: Any,
    destination: dict[str, Any],
    preview: dict[str, Any],
) -> str:
    return stable_fingerprint(
        {
            "request": request,
            "source": _source_fingerprint_material(source),
            "native": _native_fingerprint_material(doc),
            "destination": destination,
            "preview": preview,
        }
    )


def _build(
    request: dict[str, Any],
) -> tuple[Any | None, Any | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not _valid_amount(request.get("amount")):
        return (
            None,
            None,
            None,
            _error(
                "INVALID_PAYMENT_AMOUNT",
                "Payment amount must be a positive finite number.",
            ),
        )
    if request.get("mode_of_payment") and request.get("bank_account"):
        return (
            None,
            None,
            None,
            _error(
                "CONTRADICTORY_DESTINATION",
                "Provide either Mode of Payment or Bank Account, not both.",
            ),
        )
    if not request.get("mode_of_payment") and not request.get("bank_account"):
        return (
            None,
            None,
            None,
            _error(
                "DESTINATION_REQUIRED", "Provide one Mode of Payment or Bank Account."
            ),
        )
    if request.get("bank_amount") is not None and not _valid_amount(
        request.get("bank_amount")
    ):
        return (
            None,
            None,
            None,
            _error(
                "INVALID_BANK_AMOUNT", "bank_amount must be a positive finite number."
            ),
        )

    name = _source_name(request)
    source, failure = _load_source(name)
    if failure:
        return None, None, None, failure

    request["posting_date"] = _json(getdate(request.get("posting_date") or nowdate()))
    try:
        destination, failure = _destination(str(_value(source, "company")), request)
    except frappe.PermissionError:
        return (
            None,
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot use the selected payment destination.",
            ),
        )
    except Exception:
        return (
            None,
            None,
            None,
            _error(
                "INVALID_PAYMENT_DESTINATION",
                "ERPNext could not validate the selected payment destination.",
            ),
        )
    if failure:
        return None, None, None, failure
    if destination.get("account_type") == "Bank" and (
        not request.get("reference_no") or not request.get("reference_date")
    ):
        return (
            None,
            None,
            None,
            _error(
                "TRANSACTION_REFERENCE_REQUIRED",
                "Reference number and reference date are required for a Bank destination.",
            ),
        )

    try:
        doc = _native_factory()(
            _SOURCE,
            str(_value(source, "name")),
            party_amount=request["amount"],
            bank_account=destination["account"],
            bank_amount=request.get("bank_amount"),
            party_type="Customer",
            payment_type="Receive",
            reference_date=(
                getdate(request["reference_date"])
                if request.get("reference_date")
                else None
            ),
        )
        if request.get("mode_of_payment"):
            doc.mode_of_payment = request["mode_of_payment"]
        if request.get("bank_account"):
            doc.bank_account = request["bank_account"]
        if request.get("reference_no") is not None:
            doc.reference_no = request["reference_no"]
        if request.get("reference_date") is not None:
            doc.reference_date = getdate(request["reference_date"])
        if request.get("remarks") is not None:
            doc.remarks = request["remarks"][:_MAX_REMARKS]
            doc.custom_remarks = 1
        doc.run_method("validate")
    except frappe.PermissionError:
        return (
            None,
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot create a Payment Entry.",
            ),
        )
    except frappe.ValidationError:
        return (
            None,
            None,
            None,
            _error(
                "NATIVE_VALIDATION_FAILED",
                "ERPNext rejected the Sales Order advance Payment Entry.",
            ),
        )
    except Exception:
        return (
            None,
            None,
            None,
            _error(
                "NATIVE_PAYMENT_VALIDATION_FAILED",
                "ERPNext could not prepare this native Payment Entry.",
            ),
        )

    if int(_value(doc, "docstatus", 0) or 0) != 0:
        return (
            None,
            None,
            None,
            _error(
                "NATIVE_PAYMENT_STATE_INVALID",
                "Native preparation did not produce a Draft Payment Entry.",
            ),
        )
    references = _value(doc, "references", []) or []
    if not 1 <= len(references) <= _MAX_REFERENCES:
        return (
            None,
            None,
            None,
            _error(
                "PAYMENT_TERMS_UNSUPPORTED",
                "Native Payment Entry references cannot be represented safely by V1.",
            ),
        )
    if any(
        _value(row, "reference_doctype") != _SOURCE
        or _value(row, "reference_name") != _value(source, "name")
        for row in references
    ):
        return (
            None,
            None,
            None,
            _error(
                "UNEXPECTED_REFERENCE_STATE",
                "Native preparation produced an unsupported Payment Entry reference.",
            ),
        )
    if any(
        _value(doc, field, [])
        for field in ("deductions", "taxes", "tax_withholding_entries")
    ):
        return (
            None,
            None,
            None,
            _error(
                "UNSUPPORTED_NATIVE_PAYMENT_STATE",
                "Native preparation produced tax, withholding, or deduction state outside this V1 capability.",
            ),
        )
    if (
        destination["currency"] != _value(doc, "paid_from_account_currency")
        and request.get("bank_amount") is None
    ):
        return (
            None,
            None,
            None,
            _error(
                "BANK_AMOUNT_REQUIRED",
                "bank_amount is required when destination currency differs from the Customer account currency.",
            ),
        )
    return doc, source, destination, None


def prepare_sales_order_advance_payment(request: dict[str, Any]) -> dict[str, Any]:
    approvals.prune_expired()
    user = _user()
    normalized = deepcopy(request)
    doc, source, destination, failure = _build(normalized)
    if failure:
        return failure
    preview = _preview(doc, source, destination)
    token = approvals.create(
        action=_ACTION,
        site=getattr(frappe.local, "site", ""),
        user=user,
        payload={
            "request": normalized,
            "preview": preview,
            "fingerprint": _fingerprint(normalized, source, doc, destination, preview),
        },
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": preview,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def confirm_sales_order_advance_payment(
    approval_token: str, confirm: bool
) -> dict[str, Any]:
    user = _user()
    site = getattr(frappe.local, "site", "")
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=site, user=user)
        return _error(
            "CONFIRMATION_REQUIRED",
            "Review the Draft Payment Entry preview before confirming it.",
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(
            state, "Sales Order Customer advance payment"
        )
        return _error(code, message, retryable=retryable)

    request = approval.payload.get("request")
    approved_preview = approval.payload.get("preview")
    approved_fingerprint = approval.payload.get("fingerprint")
    if (
        not isinstance(request, dict)
        or not isinstance(approved_preview, dict)
        or not isinstance(approved_fingerprint, str)
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE",
            "This Payment Entry confirmation is unavailable.",
        )
    doc, source, destination, failure = _build(deepcopy(request))
    if failure:
        return _error(
            "STALE_CONFIRMATION",
            "The native payment preview changed after preparation. Please prepare it again.",
        )
    preview = _preview(doc, source, destination)
    if _fingerprint(request, source, doc, destination, preview) != approved_fingerprint:
        return _error(
            "STALE_CONFIRMATION",
            "The native payment preview changed after preparation. Please prepare it again.",
        )
    try:
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED", "The authenticated user cannot create a Payment Entry."
        )
    except frappe.ValidationError:
        frappe.db.rollback()
        return _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected the Draft Payment Entry during final validation.",
        )
    except Exception:
        frappe.db.rollback()
        return _error(
            "PAYMENT_ENTRY_CREATION_FAILED",
            "ERPNext could not create the Draft Payment Entry.",
        )
    return {
        "status": "created",
        "doctype": _TARGET,
        "payment_entry": str(_value(doc, "name")),
        "docstatus": 0,
        "source_sales_order": str(_value(source, "name")),
        "customer": str(_value(doc, "party")),
        "company": str(_value(doc, "company")),
        "payment_type": "Receive",
        "paid_amount": flt(_value(doc, "paid_amount")),
        "unallocated_amount": flt(_value(doc, "unallocated_amount")),
        "idempotent": False,
    }
