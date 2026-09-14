"""Native, approval-bound explicit multi-invoice Customer receipt workflow."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import frappe
from frappe.utils import flt, getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import new_error_reference

_ACTION = "create_multi_invoice_customer_receipt"


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {"status": "error", "code": code, "message": message, "reference": new_error_reference(), "retryable": retryable}


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
        frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
    return user


def _load(doctype: str, name: str, code: str, label: str) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        doc = frappe.get_doc(doctype, name)
        if not doc.has_permission("read"):
            raise frappe.PermissionError
        return doc, None
    except frappe.DoesNotExistError:
        return None, _error(code, f"{label} was not found.")
    except frappe.PermissionError:
        return None, _error("PERMISSION_DENIED", f"The authenticated user cannot read {label}.")


def _destination(company: str, request: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    mode = request.get("mode_of_payment")
    bank = request.get("bank_account")
    if mode and bank:
        return None, _error("CONTRADICTORY_DESTINATION", "Provide either Mode of Payment or Bank Account, not both.")
    if not mode and not bank:
        return None, _error("DESTINATION_REQUIRED", "Provide one Mode of Payment or Bank Account.")
    if bank:
        bank_doc, failure = _load("Bank Account", str(bank), "INVALID_BANK_ACCOUNT", "Bank Account")
        if failure:
            return None, failure
        if _value(bank_doc, "company") not in (None, "", company) or not _value(bank_doc, "account"):
            return None, _error("INVALID_BANK_ACCOUNT", "The Bank Account has no usable Company ledger account.")
        account = str(_value(bank_doc, "account"))
        kind = "Bank Account"
        identity = str(bank)
    else:
        from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account

        account = None
        for account_type in ("Bank", "Cash"):
            resolved = get_default_bank_cash_account(company, account_type, mode_of_payment=mode, fetch_balance=False)
            if resolved and resolved.get("account"):
                account = str(resolved.account)
                break
        if not account:
            return None, _error("INVALID_MODE_OF_PAYMENT", "The Mode of Payment has no usable Company bank or cash account.")
        kind = "Mode of Payment"
        identity = str(mode)
    try:
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_account_details

        details = get_account_details(account, getdate(request["posting_date"]), None)
    except Exception:
        return None, _error("INVALID_DESTINATION_ACCOUNT", "ERPNext could not validate the destination ledger account.")
    return {"kind": kind, "identity": identity, "account": account, "currency": str(details.account_currency), "account_type": _value(details, "account_type")}, None


def _effective_receivable(invoice: Any) -> str | None:
    from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import get_party_account_based_on_invoice_discounting

    return get_party_account_based_on_invoice_discounting(_value(invoice, "name")) or _value(invoice, "debit_to")


def _is_early_discount_eligible(invoice: Any, posting_date: Any, party_currency: str) -> bool:
    from erpnext.accounts.doctype.payment_entry.payment_entry import apply_early_payment_discount

    _, _, discount, _ = apply_early_payment_discount(0, 0, invoice, party_currency, getdate(posting_date))
    return bool(flt(discount))


def _term_allocation_enabled(invoice: Any) -> bool:
    template = _value(invoice, "payment_terms_template")
    return bool(template and frappe.db.get_value("Payment Terms Template", template, "allocate_payment_based_on_payment_terms"))


def _reference_preview(row: Any, invoice: Any, party_currency: str) -> dict[str, Any]:
    return {
        "sales_invoice": str(_value(row, "reference_name")),
        "posting_date": _json(_value(row, "posting_date") or _value(invoice, "posting_date")),
        "due_date": _json(_value(row, "due_date") or _value(invoice, "due_date")),
        "invoice_currency": str(_value(invoice, "currency")),
        "party_currency": party_currency,
        "total_amount": flt(_value(row, "total_amount")),
        "outstanding_amount": flt(_value(row, "outstanding_amount")),
        "allocated_amount": flt(_value(row, "allocated_amount")),
    }


def _deduction_preview(doc: Any) -> list[dict[str, Any]]:
    return [{"account": _value(row, "account"), "amount": flt(_value(row, "amount")), "description": _value(row, "description")} for row in (_value(doc, "deductions", []) or [])]


def _preview(doc: Any, invoices: dict[str, Any], destination: dict[str, Any]) -> dict[str, Any]:
    party_currency = str(_value(doc, "paid_from_account_currency"))
    references = [_reference_preview(row, invoices[str(_value(row, "reference_name"))], party_currency) for row in (_value(doc, "references", []) or [])]
    return {
        "doctype": "Payment Entry", "docstatus": 0, "customer": str(_value(doc, "party")), "company": str(_value(doc, "company")),
        "payment_type": "Receive", "posting_date": _json(_value(doc, "posting_date")), "reference_no": _value(doc, "reference_no"),
        "reference_date": _json(_value(doc, "reference_date")), "destination_kind": destination["kind"], "destination": destination["identity"],
        "party_account_currency": party_currency, "destination_account_currency": str(_value(doc, "paid_to_account_currency")),
        "paid_amount": flt(_value(doc, "paid_amount")), "received_amount": flt(_value(doc, "received_amount")),
        "source_exchange_rate": flt(_value(doc, "source_exchange_rate")), "target_exchange_rate": flt(_value(doc, "target_exchange_rate")),
        "references": references, "total_allocated_amount": flt(_value(doc, "total_allocated_amount")),
        "unallocated_amount": flt(_value(doc, "unallocated_amount")), "difference_amount": flt(_value(doc, "difference_amount")),
        "deductions": _deduction_preview(doc), "remarks": _value(doc, "remarks"),
        "note": "Draft only; no ledger or invoice outstanding effect occurs until separately approved submit.",
    }


def _fingerprint(request: dict[str, Any], preview: dict[str, Any], invoices: dict[str, Any], destination: dict[str, Any]) -> str:
    sources = []
    by_name = {row["sales_invoice"]: row for row in preview["references"]}
    for name in sorted(invoices):
        invoice = invoices[name]
        sources.append({
            "name": name, "docstatus": int(_value(invoice, "docstatus", 0) or 0), "modified": str(_value(invoice, "modified")),
            "customer": _value(invoice, "customer"), "company": _value(invoice, "company"), "account": _effective_receivable(invoice),
            "currency": _value(invoice, "currency"), "party_currency": _value(invoice, "party_account_currency"),
            "posting_date": _json(_value(invoice, "posting_date")), "due_date": _json(_value(invoice, "due_date")),
            "grand_total": _value(invoice, "grand_total"), "outstanding": by_name[name]["outstanding_amount"],
            "allocated": by_name[name]["allocated_amount"], "payment_terms_template": _value(invoice, "payment_terms_template"),
            "allocate_by_terms": _term_allocation_enabled(invoice),
        })
    material = {"request": request, "preview": preview, "sources": sources, "destination": destination}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _build(request: dict[str, Any]) -> tuple[Any | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    allocations = request.get("allocations") or []
    if not 2 <= len(allocations) <= 20:
        return None, None, None, _error("INVALID_REFERENCE_COUNT", "Provide 2-20 Sales Invoice allocations.")
    names = [str(row.get("sales_invoice", "")).strip() for row in allocations]
    if len(set(names)) != len(names):
        return None, None, None, _error("DUPLICATE_SALES_INVOICE", "Each Sales Invoice may appear only once.")
    request["posting_date"] = _json(getdate(request.get("posting_date") or nowdate()))
    customer, failure = _load("Customer", str(request.get("customer", "")), "CUSTOMER_NOT_FOUND", "Customer")
    if failure:
        return None, None, None, failure
    invoices: dict[str, Any] = {}
    for name in names:
        invoice, failure = _load("Sales Invoice", name, "SOURCE_NOT_FOUND", f"Sales Invoice {name}")
        if failure:
            return None, None, None, failure
        invoices[name] = invoice
    if any(int(_value(invoice, "docstatus", 0) or 0) != 1 for invoice in invoices.values()):
        return None, None, None, _error("SOURCE_NOT_READY", "Every Sales Invoice must be Submitted.")
    if any(bool(_value(invoice, "is_return", False)) for invoice in invoices.values()):
        return None, None, None, _error("RETURN_REFERENCE_UNSUPPORTED", "Return Sales Invoices are not supported.")
    if any(_value(invoice, "customer") != _value(customer, "name") for invoice in invoices.values()):
        return None, None, None, _error("CUSTOMER_MISMATCH", "Every Sales Invoice must belong to the explicit Customer.")
    companies = {_value(invoice, "company") for invoice in invoices.values()}
    accounts = {_effective_receivable(invoice) for invoice in invoices.values()}
    currencies = {_value(invoice, "currency") for invoice in invoices.values()}
    party_currencies = {_value(invoice, "party_account_currency") for invoice in invoices.values()}
    if len(companies) != 1:
        return None, None, None, _error("COMPANY_MISMATCH", "Every Sales Invoice must belong to one Company.")
    if len(accounts) != 1 or None in accounts:
        return None, None, None, _error("RECEIVABLE_ACCOUNT_MISMATCH", "Every Sales Invoice must use one effective receivable account.")
    if len(party_currencies) != 1:
        return None, None, None, _error("PARTY_CURRENCY_MISMATCH", "Every Sales Invoice must use one party-account currency.")
    if len(currencies) != 1:
        return None, None, None, _error("MIXED_INVOICE_CURRENCY_UNSUPPORTED", "Mixed Sales Invoice transaction currencies are unsupported.")
    company, account, party_currency = str(next(iter(companies))), str(next(iter(accounts))), str(next(iter(party_currencies)))
    if any(_term_allocation_enabled(invoice) for invoice in invoices.values()):
        return None, None, None, _error("PAYMENT_TERMS_UNSUPPORTED", "Payment-term allocation is unsupported for this receipt.")
    if any(_is_early_discount_eligible(invoice, request["posting_date"], party_currency) for invoice in invoices.values()):
        return None, None, None, _error("EARLY_PAYMENT_DISCOUNT_UNSUPPORTED", "A selected invoice is eligible for an early-payment discount.")
    destination, failure = _destination(company, request)
    if failure:
        return None, None, None, failure
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_outstanding_reference_documents

    rows = get_outstanding_reference_documents({
        "posting_date": request["posting_date"], "company": company, "party_type": "Customer", "payment_type": "Receive",
        "party": str(_value(customer, "name")), "party_account": account, "get_outstanding_invoices": True,
        "get_orders_to_be_billed": False, "vouchers": [frappe._dict(voucher_type="Sales Invoice", voucher_no=name) for name in names],
        "book_advance_payments_in_separate_party_account": bool(frappe.db.get_value("Company", company, "book_advance_payments_in_separate_party_account")),
    }, validate=False) or []
    by_name: dict[str, Any] = {}
    for row in rows:
        if _value(row, "voucher_type") == "Sales Invoice" and _value(row, "voucher_no") in invoices:
            if _value(row, "payment_term"):
                return None, None, None, _error("PAYMENT_TERMS_UNSUPPORTED", "Term-specific outstanding rows are unsupported.")
            by_name[str(_value(row, "voucher_no"))] = row
    if set(by_name) != set(names):
        return None, None, None, _error("NO_OUTSTANDING", "Every selected Sales Invoice must have a fresh positive native outstanding row.")
    from erpnext.accounts.utils import get_currency_precision

    precision = get_currency_precision() or 2
    requested = {str(row["sales_invoice"]): flt(row["allocated_amount"], precision) for row in allocations}
    amount = flt(request.get("amount"), precision)
    total = flt(sum(requested.values()), precision)
    if total > amount:
        return None, None, None, _error("ALLOCATION_TOTAL_MISMATCH", "Allocations exceed the receipt amount.")
    if total < amount:
        return None, None, None, _error("UNALLOCATED_RECEIPT_UNSUPPORTED", "The receipt amount must equal the explicit allocations.")
    if any(value <= 0 or value > flt(_value(by_name[name], "outstanding_amount"), precision) for name, value in requested.items()):
        return None, None, None, _error("ALLOCATION_EXCEEDS_OUTSTANDING", "Each allocation must be positive and no greater than fresh native outstanding.")
    if destination["currency"] != party_currency and request.get("bank_amount") is None:
        return None, None, None, _error("BANK_AMOUNT_REQUIRED", "bank_amount is required when destination currency differs.")
    if destination.get("account_type") == "Bank" and (not request.get("reference_no") or not request.get("reference_date")):
        return None, None, None, _error("TRANSACTION_REFERENCE_REQUIRED", "Reference number and reference date are required for a Bank destination.")
    try:
        frappe.has_permission("Payment Entry", "create", throw=True)
        doc = frappe.new_doc("Payment Entry")
        doc.update({"company": company, "payment_type": "Receive", "party_type": "Customer", "party": str(_value(customer, "name")),
                    "posting_date": getdate(request["posting_date"]), "paid_from": account, "paid_to": destination["account"],
                    "paid_amount": amount, "received_amount": flt(request.get("bank_amount")) if request.get("bank_amount") is not None else amount,
                    "mode_of_payment": request.get("mode_of_payment"), "bank_account": request.get("bank_account"),
                    "reference_no": request.get("reference_no"), "reference_date": getdate(request["reference_date"]) if request.get("reference_date") else None,
                    "remarks": request.get("remarks"), "custom_remarks": 1 if request.get("remarks") is not None else 0})
        for name in sorted(names):
            native = by_name[name]
            doc.append("references", {"reference_doctype": "Sales Invoice", "reference_name": name, "total_amount": _value(native, "invoice_amount"),
                                      "outstanding_amount": _value(native, "outstanding_amount"), "allocated_amount": requested[name],
                                      "due_date": _value(native, "due_date"), "exchange_rate": _value(native, "exchange_rate"), "payment_term": None})
        doc.setup_party_account_field()
        doc.set_missing_values()
        doc.set_missing_ref_details(force=True)
        doc.set_exchange_rate()
        doc.set_amounts()
        doc.run_method("validate")
    except frappe.PermissionError:
        return None, None, None, _error("PERMISSION_DENIED", "The authenticated user cannot create a Payment Entry.")
    except Exception:
        return None, None, None, _error("NATIVE_PAYMENT_VALIDATION_FAILED", "ERPNext could not prepare this native Payment Entry.")
    if _value(doc, "taxes", []) or _value(doc, "tax_withholding_entries", []):
        return None, None, None, _error("UNEXPECTED_TAX_STATE", "Native preparation produced unsupported tax or withholding state.")
    deductions = _deduction_preview(doc)
    if deductions and destination["currency"] == party_currency:
        return None, None, None, _error("UNEXPECTED_DEDUCTION_STATE", "Native preparation produced an unsupported deduction.")
    if flt(_value(doc, "unallocated_amount"), precision) != 0:
        return None, None, None, _error("UNALLOCATED_RECEIPT_UNSUPPORTED", "Native preparation produced an unallocated amount.")
    if flt(_value(doc, "difference_amount"), precision) != 0:
        return None, None, None, _error("NONZERO_DIFFERENCE", "Native preparation produced a nonzero difference amount.")
    return doc, invoices, destination, None


def prepare_multi_invoice_customer_receipt(request: dict[str, Any]) -> dict[str, Any]:
    approvals.prune_expired()
    normalized = deepcopy(request)
    doc, invoices, destination, failure = _build(normalized)
    if failure:
        return failure
    preview = _preview(doc, invoices, destination)
    token = approvals.create(action=_ACTION, site=getattr(frappe.local, "site", ""), user=_user(), payload={"request": normalized, "preview": preview, "fingerprint": _fingerprint(normalized, preview, invoices, destination)})
    return {"status": "ready", "approval_token": token, "expires_in_seconds": APPROVAL_TTL_SECONDS, "preview": preview, "interaction": approval_directive().model_dump(mode="json")}


def confirm_multi_invoice_customer_receipt(approval_token: str, confirm: bool) -> dict[str, Any]:
    user, site = _user(), getattr(frappe.local, "site", "")
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=site, user=user)
        return _error("CONFIRMATION_REQUIRED", "Review the Draft Payment Entry preview before confirming it.")
    approval, state = approvals.claim_for_confirm_write(approval_token, action=_ACTION, site=site, user=user)
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "multi-invoice Customer receipt")
        return _error(code, message, retryable=retryable)
    request = approval.payload.get("request")
    if not isinstance(request, dict):
        return _error("CONFIRMATION_UNAVAILABLE", "This receipt confirmation is unavailable.")
    doc, invoices, destination, failure = _build(deepcopy(request))
    if failure:
        return _error("STALE_CONFIRMATION", "The receipt changed after preparation. Please prepare it again.")
    preview = _preview(doc, invoices, destination)
    if _fingerprint(request, preview, invoices, destination) != approval.payload.get("fingerprint"):
        return _error("STALE_CONFIRMATION", "The receipt changed after preparation. Please prepare it again.")
    try:
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error("PERMISSION_DENIED", "The authenticated user cannot create a Payment Entry.")
    except Exception:
        frappe.db.rollback()
        return _error("PAYMENT_ENTRY_CREATION_FAILED", "ERPNext could not create the Draft Payment Entry.")
    return {"status": "created", "doctype": "Payment Entry", "payment_entry": str(_value(doc, "name")), "docstatus": 0,
            "customer": str(_value(doc, "party")), "company": str(_value(doc, "company")), "source_sales_invoices": sorted(invoices), "idempotent": False}
