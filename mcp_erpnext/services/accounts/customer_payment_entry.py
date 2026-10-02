"""Native, approval-bound standalone Customer receipt workflow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe
from frappe.utils import flt, getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import new_error_reference
from ..common.fingerprint import stable_fingerprint
from .multi_invoice_customer_receipt import _destination

_ACTION = "create_customer_payment_entry"


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
    return str(value)


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _load(
    doctype: str, name: str, code: str, label: str
) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        doc = frappe.get_doc(doctype, name)
        if not doc.has_permission("read"):
            raise frappe.PermissionError
        return doc, None
    except frappe.DoesNotExistError:
        return None, _error(code, f"{label} was not found.")
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED", f"The authenticated user cannot read {label}."
        )


def _preview(doc: Any, destination: dict[str, Any]) -> dict[str, Any]:
    return {
        "doctype": "Payment Entry",
        "docstatus": 0,
        "customer": str(_value(doc, "party")),
        "company": str(_value(doc, "company")),
        "payment_type": "Receive",
        "posting_date": _json(_value(doc, "posting_date")),
        "reference_no": _value(doc, "reference_no"),
        "reference_date": _json(_value(doc, "reference_date")),
        "destination_kind": destination["kind"],
        "destination": destination["identity"],
        "party_account_currency": str(_value(doc, "paid_from_account_currency")),
        "destination_account_currency": str(_value(doc, "paid_to_account_currency")),
        "paid_amount": flt(_value(doc, "paid_amount")),
        "received_amount": flt(_value(doc, "received_amount")),
        "source_exchange_rate": flt(_value(doc, "source_exchange_rate")),
        "target_exchange_rate": flt(_value(doc, "target_exchange_rate")),
        "references": [],
        "total_allocated_amount": flt(_value(doc, "total_allocated_amount")),
        "unallocated_amount": flt(_value(doc, "unallocated_amount")),
        "difference_amount": flt(_value(doc, "difference_amount")),
        "remarks": _value(doc, "remarks"),
        "note": "Draft only; no ledger posting occurs until the Payment Entry is separately submitted.",
    }


def _fingerprint(
    request: dict[str, Any],
    preview: dict[str, Any],
    doc: Any,
    destination: dict[str, Any],
) -> str:
    return stable_fingerprint(
        {
            "request": request,
            "preview": preview,
            "destination": destination,
            "native_party_account": _value(doc, "party_account"),
            "native_party_account_currency": _value(doc, "paid_from_account_currency"),
            "native_destination_account": _value(doc, "paid_to"),
            "native_destination_currency": _value(doc, "paid_to_account_currency"),
            "native_advance_policy": _value(
                doc, "book_advance_payments_in_separate_party_account"
            ),
        }
    )


def _build(
    request: dict[str, Any],
) -> tuple[Any | None, dict[str, Any] | None, dict[str, Any] | None]:
    request["posting_date"] = _json(getdate(request.get("posting_date") or nowdate()))
    customer, failure = _load(
        "Customer", str(request.get("customer", "")), "CUSTOMER_NOT_FOUND", "Customer"
    )
    if failure:
        return None, None, failure
    company, failure = _load(
        "Company", str(request.get("company", "")), "COMPANY_NOT_FOUND", "Company"
    )
    if failure:
        return None, None, failure
    destination, failure = _destination(str(_value(company, "name")), request)
    if failure:
        return None, None, failure
    if destination.get("account_type") == "Bank" and (
        not request.get("reference_no") or not request.get("reference_date")
    ):
        return (
            None,
            None,
            _error(
                "TRANSACTION_REFERENCE_REQUIRED",
                "Reference number and reference date are required for a Bank destination.",
            ),
        )
    try:
        frappe.has_permission("Payment Entry", "create", throw=True)
        doc = frappe.new_doc("Payment Entry")
        doc.update(
            {
                "company": _value(company, "name"),
                "payment_type": "Receive",
                "party_type": "Customer",
                "party": _value(customer, "name"),
                "posting_date": getdate(request["posting_date"]),
                "paid_to": destination["account"],
                "paid_amount": request["amount"],
                "received_amount": request.get("bank_amount") or request["amount"],
                "mode_of_payment": request.get("mode_of_payment"),
                "bank_account": request.get("bank_account"),
                "reference_no": request.get("reference_no"),
                "reference_date": (
                    getdate(request["reference_date"])
                    if request.get("reference_date")
                    else None
                ),
                "remarks": request.get("remarks"),
                "custom_remarks": 1 if request.get("remarks") is not None else 0,
            }
        )
        doc.setup_party_account_field()
        doc.set_missing_values()
        doc.run_method("validate")
        if (
            doc.paid_from_account_currency != destination["currency"]
            and request.get("bank_amount") is None
        ):
            return (
                None,
                None,
                _error(
                    "BANK_AMOUNT_REQUIRED",
                    "bank_amount is required when destination currency differs.",
                ),
            )
    except frappe.PermissionError:
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot create a Payment Entry.",
            ),
        )
    except Exception:
        return (
            None,
            None,
            _error(
                "NATIVE_PAYMENT_VALIDATION_FAILED",
                "ERPNext could not prepare this native Payment Entry.",
            ),
        )
    if _value(doc, "references", []) or flt(_value(doc, "total_allocated_amount")) != 0:
        return (
            None,
            None,
            _error(
                "UNEXPECTED_REFERENCE_STATE",
                "Native preparation produced an allocated Payment Entry state.",
            ),
        )
    if (
        flt(_value(doc, "unallocated_amount")) <= 0
        or flt(_value(doc, "difference_amount")) != 0
    ):
        return (
            None,
            None,
            _error(
                "UNEXPECTED_PAYMENT_STATE",
                "Native preparation produced an unsupported Payment Entry amount state.",
            ),
        )
    if (
        _value(doc, "deductions", [])
        or _value(doc, "taxes", [])
        or _value(doc, "tax_withholding_entries", [])
    ):
        return (
            None,
            None,
            _error(
                "UNEXPECTED_ACCOUNTING_STATE",
                "Native preparation produced unsupported tax, withholding, or deduction state.",
            ),
        )
    return doc, destination, None


def prepare_customer_payment_entry(request: dict[str, Any]) -> dict[str, Any]:
    approvals.prune_expired()
    normalized = deepcopy(request)
    doc, destination, failure = _build(normalized)
    if failure:
        return failure
    preview = _preview(doc, destination)
    token = approvals.create(
        action=_ACTION,
        site=getattr(frappe.local, "site", ""),
        user=_user(),
        payload={
            "request": normalized,
            "preview": preview,
            "fingerprint": _fingerprint(normalized, preview, doc, destination),
        },
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": preview,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def confirm_customer_payment_entry(
    approval_token: str, confirm: bool
) -> dict[str, Any]:
    user, site = _user(), getattr(frappe.local, "site", "")
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
            state, "standalone Customer receipt"
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
    doc, destination, failure = _build(deepcopy(request))
    if failure:
        return _error(
            "STALE_CONFIRMATION",
            "The native payment preview changed after preparation. Please prepare it again.",
        )
    preview = _preview(doc, destination)
    if _fingerprint(request, preview, doc, destination) != approved_fingerprint:
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
    except Exception:
        frappe.db.rollback()
        return _error(
            "PAYMENT_ENTRY_CREATION_FAILED",
            "ERPNext could not create the Draft Payment Entry.",
        )
    return {
        "status": "created",
        "doctype": "Payment Entry",
        "payment_entry": str(_value(doc, "name")),
        "docstatus": 0,
        "customer": str(_value(doc, "party")),
        "company": str(_value(doc, "company")),
        "payment_type": "Receive",
        "paid_amount": flt(_value(doc, "paid_amount")),
        "unallocated_amount": flt(_value(doc, "unallocated_amount")),
        "idempotent": False,
    }
