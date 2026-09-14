"""Native, approval-bound Sales Invoice customer Payment Entry workflow."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

import frappe
from frappe.utils import flt, getdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import new_error_reference

_ACTION = "create_sales_invoice_payment"
_MAX_REMARKS = 1000


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": retryable,
    }


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
    return user


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


def _resolve_bank_account(invoice: Any, requested: str | None) -> tuple[str | None, str | None, dict[str, Any] | None]:
    """Resolve a public Bank Account name to its native Account input."""
    if not requested:
        return None, None, None
    account_doc = frappe.get_doc("Bank Account", requested)
    if not account_doc.has_permission("read"):
        return None, None, _error("INVALID_BANK_ACCOUNT", "The Bank Account is not available to the authenticated user.")
    if _value(account_doc, "company") not in (None, "", _value(invoice, "company")):
        return None, None, _error("INVALID_BANK_ACCOUNT", "The Bank Account does not belong to the Sales Invoice Company.")
    account = _value(account_doc, "account")
    if not account:
        return None, None, _error("INVALID_BANK_ACCOUNT", "The Bank Account has no usable native account.")
    return str(account), str(requested), None


def _resolve_mode_account(invoice: Any, mode: str | None) -> tuple[str | None, dict[str, Any] | None]:
    if not mode:
        return None, None
    # This is ERPNext's own destination resolver; MCP does not select a fallback.
    from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account

    for account_type in ("Bank", "Cash"):
        resolved = get_default_bank_cash_account(
            _value(invoice, "company"), account_type, mode_of_payment=mode, fetch_balance=False
        )
        if resolved and resolved.get("account"):
            return str(resolved.account), None
    return None, _error("MODE_OF_PAYMENT_ACCOUNT_MISSING", "The Mode of Payment has no usable Company bank or cash account.")


def _reference_preview(row: Any) -> dict[str, Any]:
    return {
        "reference_doctype": _value(row, "reference_doctype"),
        "reference_name": _value(row, "reference_name"),
        "total_amount": _value(row, "total_amount"),
        "outstanding_amount": _value(row, "outstanding_amount"),
        "allocated_amount": _value(row, "allocated_amount"),
        "payment_term": _value(row, "payment_term"),
    }


def _preview(doc: Any, source: Any, destination: str | None) -> dict[str, Any]:
    references = [_reference_preview(row) for row in _value(doc, "references", []) or []]
    return {
        "doctype": "Payment Entry",
        "docstatus": int(_value(doc, "docstatus", 0) or 0),
        "source_sales_invoice": _value(source, "name"),
        "source_status": "Submitted" if int(_value(source, "docstatus", 0) or 0) == 1 else str(_value(source, "status", "Unknown")),
        "customer": _value(doc, "party"),
        "company": _value(doc, "company"),
        "payment_type": "Receive",
        "posting_date": _json(_value(doc, "posting_date")),
        "mode_of_payment": _value(doc, "mode_of_payment"),
        "destination": destination,
        "party_currency": _value(doc, "paid_from_account_currency"),
        "bank_currency": _value(doc, "paid_to_account_currency"),
        "paid_amount": _value(doc, "paid_amount"),
        "received_amount": _value(doc, "received_amount"),
        "current_invoice_outstanding": _value(source, "outstanding_amount"),
        "allocated_amount": sum(flt(row.get("allocated_amount")) for row in references),
        "unallocated_amount": _value(doc, "unallocated_amount"),
        "reference_no": _value(doc, "reference_no"),
        "reference_date": _json(_value(doc, "reference_date")),
        "references": references,
        "remarks": _value(doc, "remarks"),
        "note": "Draft only; no General Ledger, Payment Ledger, or Sales Invoice outstanding effect occurs until separate submit.",
    }


def _fingerprint(request: dict[str, Any], preview: dict[str, Any], native_account: str | None) -> str:
    material = {"request": request, "preview": preview, "resolved_destination_account": native_account}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _build(request: dict[str, Any]) -> tuple[Any | None, Any | None, dict[str, Any] | None, str | None]:
    invoice_name = request.get("sales_invoice")
    if not isinstance(invoice_name, str) or not invoice_name.strip():
        return None, None, _error("INVALID_SALES_INVOICE", "An exact Sales Invoice name is required."), None
    try:
        invoice = frappe.get_doc("Sales Invoice", invoice_name.strip())
        invoice.check_permission()
    except frappe.DoesNotExistError:
        return None, None, _error("SALES_INVOICE_NOT_FOUND", "The Sales Invoice was not found."), None
    except frappe.PermissionError:
        return None, None, _error("PERMISSION_DENIED", "The authenticated user cannot read the Sales Invoice."), None

    if int(_value(invoice, "docstatus", 0) or 0) != 1:
        return None, None, _error("SALES_INVOICE_NOT_SUBMITTED", "Customer payment V1 requires a submitted Sales Invoice."), None
    outstanding = flt(_value(invoice, "outstanding_amount"))
    if outstanding <= 0:
        return None, None, _error("SALES_INVOICE_NOT_OUTSTANDING", "The Sales Invoice has no outstanding amount to receive."), None
    amount = request.get("amount")
    if amount is not None and (isinstance(amount, bool) or not math.isfinite(float(amount)) or float(amount) <= 0):
        return None, None, _error("INVALID_PAYMENT_AMOUNT", "Payment amount must be greater than zero."), None
    if amount is not None and flt(amount) > outstanding:
        return None, None, _error("AMOUNT_EXCEEDS_OUTSTANDING", "Overpayment or advance receipt is outside this V1 Sales Invoice payment capability."), None
    if request.get("mode_of_payment") and request.get("bank_account"):
        return None, None, _error("CONTRADICTORY_DESTINATION", "Provide either Mode of Payment or Bank Account, not both."), None
    native_account, destination, failure = _resolve_bank_account(invoice, request.get("bank_account"))
    if failure:
        return None, None, failure, None
    if request.get("mode_of_payment"):
        native_account, failure = _resolve_mode_account(invoice, request["mode_of_payment"])
        if failure:
            return None, None, failure, None
        destination = request["mode_of_payment"]
    try:
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

        doc = get_payment_entry(
            "Sales Invoice", invoice_name.strip(), party_amount=amount,
            bank_account=native_account, bank_amount=request.get("bank_amount"),
            reference_date=getdate(request["reference_date"]) if request.get("reference_date") else None,
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
        doc.set_missing_values()
        doc.set_missing_ref_details()
        # The factory has already performed native defaulting. Full Payment
        # Entry validation is intentionally deferred to Draft insert so a
        # missing transaction reference can be reviewed without inventing one.
    except frappe.PermissionError:
        return None, None, _error("PERMISSION_DENIED", "The authenticated user cannot create a Payment Entry."), None
    except Exception:
        return None, None, _error("NATIVE_PAYMENT_VALIDATION_FAILED", "ERPNext could not prepare this native Payment Entry."), None
    if int(_value(doc, "docstatus", 0) or 0) != 0:
        return None, None, _error("NATIVE_PAYMENT_VALIDATION_FAILED", "ERPNext did not return a Draft Payment Entry."), None
    return doc, invoice, None, native_account


def prepare_sales_invoice_payment(request: dict[str, Any]) -> dict[str, Any]:
    approvals.prune_expired()
    user = _user()
    normalized = deepcopy(request)
    doc, invoice, failure, native_account = _build(normalized)
    if failure:
        return failure
    preview = _preview(doc, invoice, normalized.get("mode_of_payment") or normalized.get("bank_account"))
    token = approvals.create(
        action=_ACTION, site=getattr(frappe.local, "site", ""), user=user,
        payload={"request": normalized, "preview": preview, "fingerprint": _fingerprint(normalized, preview, native_account)},
    )
    return {"status": "ready", "approval_token": token, "expires_in_seconds": APPROVAL_TTL_SECONDS, "preview": preview, "interaction": approval_directive().model_dump(mode="json")}


def confirm_sales_invoice_payment(approval_token: str, confirm: bool) -> dict[str, Any]:
    user = _user()
    site = getattr(frappe.local, "site", "")
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=site, user=user)
        return _error("CONFIRMATION_REQUIRED", "Review the Payment Entry Draft preview before confirming it.")
    approval, state = approvals.claim_for_confirm_write(approval_token, action=_ACTION, site=site, user=user)
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Sales Invoice payment")
        return _error(code, message, retryable=retryable)
    request = approval.payload.get("request")
    approved_preview = approval.payload.get("preview")
    approved_fingerprint = approval.payload.get("fingerprint")
    if not isinstance(request, dict) or not isinstance(approved_preview, dict) or not isinstance(approved_fingerprint, str):
        return _error("CONFIRMATION_UNAVAILABLE", "This Payment Entry confirmation is unavailable.")
    doc, invoice, failure, native_account = _build(request)
    if failure:
        return _error("STALE_CONFIRMATION", "The native payment preview changed after preparation. Please prepare it again.")
    preview = _preview(doc, invoice, request.get("mode_of_payment") or request.get("bank_account"))
    if _fingerprint(request, preview, native_account) != approved_fingerprint:
        return _error("STALE_CONFIRMATION", "The native payment preview changed after preparation. Please prepare it again.")
    try:
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error("PERMISSION_DENIED", "The authenticated user cannot create a Payment Entry.")
    except Exception:
        frappe.db.rollback()
        return _error("PAYMENT_ENTRY_CREATION_FAILED", "ERPNext could not create the Draft Payment Entry.")
    return {"status": "created", "doctype": "Payment Entry", "payment_entry": _value(doc, "name"), "docstatus": 0, "source_sales_invoice": _value(invoice, "name"), "customer": _value(doc, "party"), "company": _value(doc, "company"), "idempotent": False}
