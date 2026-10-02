"""Native, approval-bound reconciliation of an existing Customer receipt."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import frappe
from frappe.utils import flt, getdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import public_error
from ..common.fingerprint import stable_fingerprint

_ACTION = "reconcile_customer_payment_to_sales_invoice"
_PAYMENT_ENTRY = "Payment Entry"
_SALES_INVOICE = "Sales Invoice"
_RECONCILIATION = "Payment Reconciliation"
_MAX_DISCOVERY_ROWS = 50


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return public_error(code, message=message, retryable=retryable)


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _value(doc: Any, field: str, default: Any = None) -> Any:
    getter = getattr(doc, "get", None)
    return getter(field, default) if callable(getter) else getattr(doc, field, default)


def _set_value(doc: Any, field: str, value: Any) -> None:
    setter = getattr(doc, "set", None)
    if callable(setter):
        setter(field, value)
    else:
        setattr(doc, field, value)


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


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    return {
        key: _value(row, key)
        for key in (
            "reference_type",
            "reference_name",
            "reference_row",
            "against_order",
            "posting_date",
            "remarks",
            "currency",
            "exchange_rate",
            "amount",
            "book_advance_payments_in_separate_party_account",
            "invoice_type",
            "invoice_number",
            "invoice_date",
            "invoice_amount",
            "outstanding_amount",
            "account",
        )
    }


def _valid_amount(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _precision() -> int:
    try:
        return int(frappe.get_precision(_SALES_INVOICE, "outstanding_amount") or 2)
    except Exception:
        return 2


def _tolerance(precision: int) -> float:
    return 0.5 / (10**precision)


def _has_permission(doctype: str, permission: str, name: str | None = None) -> bool:
    try:
        return bool(frappe.has_permission(doctype, permission, doc=name))
    except TypeError:
        # A small compatibility seam for test doubles and older Frappe wrappers.
        return bool(frappe.has_permission(doctype, permission, name))
    except frappe.PermissionError:
        return False


def _document_has_permission(doc: Any, permission: str) -> bool:
    checker = getattr(doc, "has_permission", None)
    if callable(checker):
        try:
            return bool(checker(permission))
        except frappe.PermissionError:
            return False
    return _has_permission(
        str(_value(doc, "doctype", "")), permission, _value(doc, "name")
    )


def _load_document(
    doctype: str, name: str | None, not_found_code: str, label: str
) -> tuple[Any | None, dict[str, Any] | None]:
    if not isinstance(name, str) or not name.strip():
        return None, _error(not_found_code, f"An exact {label} name is required.")
    name = name.strip()
    try:
        doc = frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None, _error(not_found_code, f"The {label} was not found.")
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED",
            f"The authenticated user cannot read the {label}.",
        )

    if not _document_has_permission(doc, "read"):
        return None, _error(
            "PERMISSION_DENIED",
            f"The authenticated user cannot read the {label}.",
        )
    return doc, None


def _load_and_authorize_documents(
    payment_name: str | None, invoice_name: str | None
) -> tuple[Any | None, Any | None, dict[str, Any] | None]:
    payment, failure = _load_document(
        _PAYMENT_ENTRY,
        payment_name,
        "PAYMENT_ENTRY_NOT_FOUND",
        "Payment Entry",
    )
    if failure:
        return None, None, failure
    if not _document_has_permission(payment, "write"):
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot reconcile the Payment Entry.",
            ),
        )

    invoice, failure = _load_document(
        _SALES_INVOICE,
        invoice_name,
        "SALES_INVOICE_NOT_FOUND",
        "Sales Invoice",
    )
    if failure:
        return None, None, failure

    if not _has_permission(_RECONCILIATION, "write"):
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot use Payment Reconciliation.",
            ),
        )
    return payment, invoice, None


def _link_permissions(
    payment: Any, invoice: Any, account: str | None, advance: str | None
):
    links = {
        "Customer": _value(invoice, "customer") or _value(payment, "party"),
        "Company": _value(invoice, "company"),
        "Account": account,
    }
    source_account = _value(payment, "paid_from") or _value(payment, "party_account")
    if source_account:
        links["Account"] = account
        if source_account != account and source_account != advance:
            return _error(
                "ACCOUNT_MISMATCH",
                "The Payment Entry account is not compatible with the Sales Invoice reconciliation account.",
            )
        links[f"Account:{source_account}"] = source_account
    if advance:
        links[f"Account:{advance}"] = advance

    for key, name in links.items():
        doctype = key.split(":", 1)[0]
        if name and not _has_permission(doctype, "read", str(name)):
            return _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot read the accounting context for this reconciliation.",
            )
    return None


def _effective_receivable(invoice: Any) -> str | None:
    try:
        from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import (
            get_party_account_based_on_invoice_discounting,
        )

        return get_party_account_based_on_invoice_discounting(
            _value(invoice, "name")
        ) or _value(invoice, "debit_to")
    except Exception:
        return _value(invoice, "debit_to")


def _party_accounts(
    invoice: Any,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    try:
        from erpnext.accounts.party import get_party_account

        accounts = get_party_account(
            "Customer",
            party=_value(invoice, "customer"),
            company=_value(invoice, "company"),
            include_advance=True,
        )
    except frappe.PermissionError:
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                "The authenticated user cannot read the Customer accounting context.",
            ),
        )
    except Exception:
        return (
            None,
            None,
            _error(
                "ACCOUNT_MISMATCH",
                "ERPNext could not resolve the Customer accounting context.",
            ),
        )

    if isinstance(accounts, str):
        accounts = [accounts]
    accounts = list(accounts or [])
    return (
        str(accounts[0]) if accounts and accounts[0] else None,
        str(accounts[1]) if len(accounts) > 1 and accounts[1] else None,
        None,
    )


def _cached_company_value(company: str, field: str) -> Any:
    try:
        return frappe.get_cached_value("Company", company, field)
    except Exception:
        try:
            return frappe.db.get_value("Company", company, field)
        except Exception:
            return None


def _term_allocation_enabled(invoice: Any) -> bool:
    template = _value(invoice, "payment_terms_template")
    if not template:
        return False
    try:
        return bool(
            frappe.db.get_value(
                "Payment Terms Template",
                template,
                "allocate_payment_based_on_payment_terms",
            )
        )
    except Exception:
        return False


def _regional_state() -> dict[str, Any]:
    state = {"region": None, "discovery_override": None, "allocation_override": None}
    try:
        import erpnext

        state["region"] = erpnext.get_region()
        overrides = frappe.get_hooks("regional_overrides", {}).get(state["region"], {})
        state["discovery_override"] = overrides.get(
            "erpnext.controllers.accounts_controller.get_advance_payment_entries_for_regional"
        )
        state["allocation_override"] = overrides.get(
            "erpnext.accounts.doctype.payment_reconciliation.payment_reconciliation.adjust_allocations_for_taxes"
        )
    except Exception:
        pass
    return state


def _regional_warning(regional: dict[str, Any]) -> str | None:
    if regional.get("discovery_override") or regional.get("allocation_override"):
        return "Regional ERPNext reconciliation adjustments will be re-evaluated natively during confirmation."
    return None


def _exchange_warning(
    payment: Any, invoice: Any, allocation_currency: str
) -> str | None:
    company_currency = _cached_company_value(
        _value(invoice, "company"), "default_currency"
    )
    source_rate = flt(_value(payment, "source_exchange_rate") or 1)
    invoice_currency = _value(invoice, "currency")
    if (
        (company_currency and allocation_currency != company_currency)
        or (invoice_currency and invoice_currency != company_currency)
        or source_rate != 1
    ):
        return "ERPNext will derive exchange differences, rounding, and gain/loss behavior natively."
    return None


def _new_reconciliation() -> Any:
    """Instantiate the virtual native coordinator without persisting it."""
    return frappe.new_doc(_RECONCILIATION)


def _configure_reconciliation(
    payment: Any,
    invoice: Any,
    receivable_account: str,
    default_advance_account: str | None,
) -> Any:
    reconciliation = _new_reconciliation()
    for field, value in {
        "company": _value(invoice, "company"),
        "party_type": "Customer",
        "party": _value(invoice, "customer"),
        "receivable_payable_account": receivable_account,
        "default_advance_account": default_advance_account,
        "payment_name": _value(payment, "name"),
        "invoice_name": _value(invoice, "name"),
        "payment_limit": _MAX_DISCOVERY_ROWS,
        "invoice_limit": _MAX_DISCOVERY_ROWS,
    }.items():
        _set_value(reconciliation, field, value)
    # get_invoice_entries assumes this list was populated by the wider native fetch flow.
    _set_value(reconciliation, "return_invoices", [])
    return reconciliation


def _native_discovery(
    reconciliation: Any, payment_name: str, invoice_name: str
) -> tuple[list[Any], list[Any], dict[str, Any] | None]:
    try:
        payment_rows = list(reconciliation.get_payment_entries() or [])
        reconciliation.get_invoice_entries()
        invoice_rows = list(_value(reconciliation, "invoices", []) or [])
    except frappe.PermissionError:
        return (
            [],
            [],
            _error(
                "PERMISSION_DENIED",
                "ERPNext denied native payment reconciliation discovery.",
            ),
        )
    except AttributeError:
        return (
            [],
            [],
            _error(
                "NATIVE_RECONCILIATION_UNAVAILABLE",
                "The installed ERPNext Payment Reconciliation seam is unavailable.",
            ),
        )
    except Exception:
        return (
            [],
            [],
            _error(
                "NATIVE_RECONCILIATION_UNAVAILABLE",
                "ERPNext could not discover the current reconciliation state.",
            ),
        )

    exact_payments = [
        row
        for row in payment_rows
        if _value(row, "reference_type") == _PAYMENT_ENTRY
        and str(_value(row, "reference_name", "")) == payment_name
        and flt(_value(row, "amount")) > _tolerance(_precision())
    ]
    exact_invoices = [
        row
        for row in invoice_rows
        if _value(row, "invoice_type") == _SALES_INVOICE
        and str(_value(row, "invoice_number", "")) == invoice_name
        and flt(_value(row, "outstanding_amount")) > _tolerance(_precision())
    ]
    return exact_payments, exact_invoices, None


def _source_from_rows(
    payment: Any, rows: list[Any]
) -> tuple[Any | None, str | None, str | None, float | None, dict[str, Any] | None]:
    if len(rows) > 1:
        return (
            None,
            None,
            None,
            None,
            _error(
                "AMBIGUOUS_PAYMENT_SOURCE",
                "The Payment Entry has multiple eligible native source buckets; V1 will not choose one automatically.",
            ),
        )
    if not rows:
        return (
            None,
            None,
            None,
            None,
            _error(
                "INVALID_PAYMENT_ENTRY_STATE",
                "The submitted Customer Payment Entry has no eligible unallocated or Sales Order advance amount.",
            ),
        )

    row = rows[0]
    amount = flt(_value(row, "amount"), _precision())
    reference_row = _value(row, "reference_row")
    if reference_row:
        source_order = _value(row, "against_order")
        matching = [
            reference
            for reference in (_value(payment, "references", []) or [])
            if _value(reference, "name") == reference_row
            and _value(reference, "reference_doctype") == "Sales Order"
            and flt(_value(reference, "allocated_amount")) > _tolerance(_precision())
        ]
        if not source_order or len(matching) != 1:
            return (
                None,
                None,
                None,
                None,
                _error(
                    "INVALID_PAYMENT_ENTRY_STATE",
                    "The native Sales Order advance reference is no longer eligible.",
                ),
            )
        return row, "sales_order_advance", str(source_order), amount, None
    return row, "unallocated", None, amount, None


def _build_allocation(
    reconciliation: Any,
    source_row: Any,
    invoice_row: Any,
    source_available: float,
    invoice_outstanding: float,
    requested_amount: float,
) -> tuple[Any | None, dict[str, Any] | None]:
    """Use native allocation calculation, then restore source-state guards.

    ERPNext's allocator naturally allocates the complete amount supplied to it.
    Supplying the approved amount lets it calculate native exchange/difference
    fields; restoring the native source amount keeps its stale-reference guard
    authoritative for partial allocations.
    """
    source = _row_dict(source_row)
    source["amount"] = requested_amount
    invoice = _row_dict(invoice_row)
    invoice["outstanding_amount"] = invoice_outstanding
    invoice["invoice_type"] = _SALES_INVOICE
    try:
        reconciliation.add_payment_entries([source])
        reconciliation.add_invoice_entries([invoice])
        reconciliation.allocate_entries({"payments": [source], "invoices": [invoice]})
    except AttributeError:
        return None, _error(
            "NATIVE_RECONCILIATION_UNAVAILABLE",
            "The installed ERPNext allocation seam is unavailable.",
        )
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED",
            "ERPNext denied native allocation discovery.",
        )
    except Exception:
        return None, _error(
            "NATIVE_RECONCILIATION_UNAVAILABLE",
            "ERPNext could not project the requested native allocation.",
        )

    allocations = list(_value(reconciliation, "allocation", []) or [])
    if len(allocations) != 1:
        return None, _error(
            "NATIVE_RECONCILIATION_UNAVAILABLE",
            "ERPNext did not produce exactly one native reconciliation allocation.",
        )
    allocation = allocations[0]
    for field, value in {
        "unreconciled_amount": source_available,
        "amount": source_available,
        "allocated_amount": requested_amount,
        "reference_row": _value(source_row, "reference_row") or None,
        "is_advance": bool(
            _value(source_row, "book_advance_payments_in_separate_party_account")
        ),
    }.items():
        _set_value(allocation, field, value)
    return reconciliation, None


def _effective_reconciliation_date(payment: Any, invoice: Any) -> Any:
    if not bool(_value(payment, "book_advance_payments_in_separate_party_account")):
        return None
    try:
        from erpnext.accounts.utils import get_reconciliation_effect_date

        return getdate(
            get_reconciliation_effect_date(
                _SALES_INVOICE,
                _value(invoice, "name"),
                _value(invoice, "company"),
                _value(payment, "posting_date"),
            )
        )
    except Exception:
        return None


def _build(
    request: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not _valid_amount(request.get("amount")):
        return None, _error(
            "INVALID_ALLOCATION_AMOUNT",
            "Allocation amount must be a positive finite number.",
        )

    payment_name = request.get("payment_entry")
    invoice_name = request.get("sales_invoice")
    payment, invoice, failure = _load_and_authorize_documents(
        payment_name, invoice_name
    )
    if failure:
        return None, failure

    if int(_value(payment, "docstatus", 0) or 0) != 1:
        return None, _error(
            "INVALID_PAYMENT_ENTRY_STATE",
            "Only a submitted Payment Entry can be reconciled.",
        )
    if (
        _value(payment, "party_type") != "Customer"
        or _value(payment, "payment_type") != "Receive"
    ):
        return None, _error(
            "INVALID_PAYMENT_ENTRY_STATE",
            "V1 supports only a submitted Customer Receive Payment Entry.",
        )
    if int(_value(invoice, "docstatus", 0) or 0) != 1:
        return None, _error(
            "INVOICE_NOT_OUTSTANDING",
            "Only a submitted Sales Invoice can be reconciled.",
        )
    if int(_value(invoice, "is_return", 0) or 0) == 1 or _value(
        invoice, "return_against"
    ):
        return None, _error(
            "INVOICE_NOT_OUTSTANDING",
            "Return or credit-note Sales Invoices are outside this reconciliation capability.",
        )
    if _value(payment, "party") != _value(invoice, "customer"):
        return None, _error(
            "PARTY_MISMATCH",
            "The Payment Entry and Sales Invoice must belong to the same Customer.",
        )
    if _value(payment, "company") != _value(invoice, "company"):
        return None, _error(
            "COMPANY_MISMATCH",
            "The Payment Entry and Sales Invoice must belong to the same Company.",
        )

    receivable_account = _effective_receivable(invoice)
    if not receivable_account:
        return None, _error(
            "ACCOUNT_MISMATCH",
            "The Sales Invoice has no usable native receivable account.",
        )
    _party_account, advance_account, failure = _party_accounts(invoice)
    if failure:
        return None, failure
    failure = _link_permissions(
        payment, invoice, str(receivable_account), advance_account
    )
    if failure:
        return None, failure
    if _term_allocation_enabled(invoice):
        return None, _error(
            "PAYMENT_TERMS_UNSUPPORTED",
            "Payment-term-specific allocation is outside this V1 reconciliation capability.",
        )

    reconciliation = _configure_reconciliation(
        payment, invoice, str(receivable_account), advance_account
    )
    try:
        from erpnext.accounts.doctype.process_payment_reconciliation.process_payment_reconciliation import (
            is_any_doc_running,
        )

        if frappe.get_single_value(
            "Accounts Settings", "auto_reconcile_payments"
        ) and is_any_doc_running(
            {
                "company": _value(invoice, "company"),
                "party_type": "Customer",
                "party": _value(invoice, "customer"),
                "receivable_payable_account": str(receivable_account),
            }
        ):
            return None, _error(
                "RECONCILIATION_ALREADY_RUNNING",
                "A native Payment Reconciliation job is already running for this Customer and Company.",
            )
    except frappe.PermissionError:
        return None, _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot inspect native reconciliation jobs.",
        )
    except Exception:
        # The pinned native seam is optional at the site configuration boundary;
        # absence of the background guard must not replace native reconciliation.
        pass

    payment_rows, invoice_rows, failure = _native_discovery(
        reconciliation, str(_value(payment, "name")), str(_value(invoice, "name"))
    )
    if failure:
        return None, failure
    source_row, source_kind, source_sales_order, source_available, failure = (
        _source_from_rows(payment, payment_rows)
    )
    if failure:
        return None, failure
    if len(invoice_rows) != 1:
        return None, _error(
            "INVOICE_NOT_OUTSTANDING",
            "The native Payment Ledger has no single positive outstanding row for this Sales Invoice.",
        )
    invoice_row = invoice_rows[0]
    invoice_outstanding = flt(_value(invoice_row, "outstanding_amount"), _precision())
    requested_amount = flt(request.get("amount"), _precision())
    tolerance = _tolerance(_precision())
    if requested_amount <= tolerance:
        return None, _error(
            "INVALID_ALLOCATION_AMOUNT",
            "Allocation amount is below the native currency precision.",
        )
    if (
        requested_amount - float(source_available) > tolerance
        or requested_amount - invoice_outstanding > tolerance
    ):
        return None, _error(
            "AMOUNT_EXCEEDS_AVAILABLE",
            "The requested allocation exceeds the current native source or invoice availability.",
        )

    allocation_currency = (
        _value(source_row, "currency")
        or _value(payment, "paid_from_account_currency")
        or _value(invoice_row, "currency")
        or _value(invoice, "party_account_currency")
        or _cached_company_value(_value(invoice, "company"), "default_currency")
    )
    invoice_currency = _value(invoice_row, "currency")
    if (
        allocation_currency
        and invoice_currency
        and allocation_currency != invoice_currency
    ):
        return None, _error(
            "ACCOUNT_MISMATCH",
            "The native Payment Ledger source and invoice currencies are incompatible for V1.",
        )
    if not allocation_currency:
        return None, _error(
            "NATIVE_RECONCILIATION_UNAVAILABLE",
            "ERPNext did not provide a native reconciliation currency.",
        )

    reconciliation, failure = _build_allocation(
        reconciliation,
        source_row,
        invoice_row,
        float(source_available),
        invoice_outstanding,
        requested_amount,
    )
    if failure:
        return None, failure
    allocation = list(_value(reconciliation, "allocation", []) or [])[0]
    regional = _regional_state()
    separate = bool(_value(payment, "book_advance_payments_in_separate_party_account"))
    state = {
        "payment": payment,
        "invoice": invoice,
        "reconciliation": reconciliation,
        "source": source_row,
        "invoice_row": invoice_row,
        "allocation": allocation,
        "source_kind": source_kind,
        "source_sales_order": source_sales_order,
        "source_available": float(source_available),
        "invoice_outstanding": invoice_outstanding,
        "requested_amount": requested_amount,
        "allocation_currency": str(allocation_currency),
        "receivable_account": str(receivable_account),
        "default_advance_account": advance_account,
        "separate_advance_account": separate,
        "effective_reconciliation_date": _effective_reconciliation_date(
            payment, invoice
        ),
        "regional": regional,
    }
    return state, None


def _preview(state: dict[str, Any]) -> dict[str, Any]:
    regional_warning = _regional_warning(state["regional"])
    effective = flt(_value(state["allocation"], "allocated_amount"), _precision())
    projected_after = max(0.0, state["invoice_outstanding"] - effective)
    return {
        "payment_entry": str(_value(state["payment"], "name")),
        "sales_invoice": str(_value(state["invoice"], "name")),
        "customer": str(_value(state["invoice"], "customer")),
        "company": str(_value(state["invoice"], "company")),
        "source_kind": state["source_kind"],
        "source_sales_order": state["source_sales_order"],
        "allocation_currency": state["allocation_currency"],
        "available_source_amount": state["source_available"],
        "invoice_outstanding_before": state["invoice_outstanding"],
        "requested_amount": state["requested_amount"],
        "effective_native_allocation": effective,
        "projected_invoice_outstanding_after": projected_after,
        "separate_advance_account_applies": state["separate_advance_account"],
        "effective_reconciliation_date": _json(state["effective_reconciliation_date"]),
        "payment_terms_supported": True,
        "regional_adjustment_applies": bool(
            state["regional"].get("discovery_override")
            or state["regional"].get("allocation_override")
        ),
        "regional_adjustment_warning": regional_warning,
        "exchange_or_gain_loss_warning": _exchange_warning(
            state["payment"], state["invoice"], state["allocation_currency"]
        ),
        "projection_warning": "Current native reconciliation projection only; no submitted Payment Entry or ledger mutation occurs during prepare.",
    }


def _fingerprint_material(
    state: dict[str, Any], request: dict[str, Any], preview: dict[str, Any]
) -> dict[str, Any]:
    payment = state["payment"]
    invoice = state["invoice"]
    return {
        "request": request,
        "preview": preview,
        "payment": {
            key: _json(_value(payment, key))
            for key in (
                "name",
                "docstatus",
                "modified",
                "party_type",
                "party",
                "company",
                "payment_type",
                "party_account",
                "paid_from",
                "paid_from_account_currency",
                "source_exchange_rate",
                "posting_date",
                "unallocated_amount",
                "book_advance_payments_in_separate_party_account",
            )
        }
        | {
            "references": [
                {
                    key: _json(_value(reference, key))
                    for key in (
                        "name",
                        "reference_doctype",
                        "reference_name",
                        "allocated_amount",
                        "total_amount",
                        "outstanding_amount",
                        "exchange_rate",
                        "payment_term",
                        "advance_voucher_type",
                        "advance_voucher_no",
                    )
                }
                for reference in (_value(payment, "references", []) or [])
            ]
        },
        "invoice": {
            key: _json(_value(invoice, key))
            for key in (
                "name",
                "docstatus",
                "modified",
                "customer",
                "company",
                "debit_to",
                "currency",
                "conversion_rate",
                "payment_terms_template",
                "is_return",
                "return_against",
            )
        },
        "native_source": {
            key: _json(_value(state["source"], key))
            for key in (
                "reference_type",
                "reference_name",
                "reference_row",
                "against_order",
                "amount",
                "currency",
                "exchange_rate",
                "book_advance_payments_in_separate_party_account",
            )
        },
        "native_invoice": {
            key: _json(_value(state["invoice_row"], key))
            for key in (
                "invoice_type",
                "invoice_number",
                "posting_date",
                "invoice_amount",
                "outstanding_amount",
                "currency",
                "account",
            )
        },
        "policy": {
            "receivable_account": state["receivable_account"],
            "default_advance_account": state["default_advance_account"],
            "separate_advance_account": state["separate_advance_account"],
            "reconciliation_takes_effect_on": _cached_company_value(
                _value(invoice, "company"), "reconciliation_takes_effect_on"
            ),
            "effective_reconciliation_date": _json(
                state["effective_reconciliation_date"]
            ),
            "regional": state["regional"],
        },
    }


def _fingerprint(
    state: dict[str, Any], request: dict[str, Any], preview: dict[str, Any]
) -> str:
    return stable_fingerprint(_fingerprint_material(state, request, preview))


def prepare_customer_payment_reconciliation(request: dict[str, Any]) -> dict[str, Any]:
    approvals.prune_expired()
    user = _user()
    normalized = {
        "payment_entry": request.get("payment_entry"),
        "sales_invoice": request.get("sales_invoice"),
        "amount": request.get("amount"),
    }
    if isinstance(normalized["payment_entry"], str):
        normalized["payment_entry"] = normalized["payment_entry"].strip()
    if isinstance(normalized["sales_invoice"], str):
        normalized["sales_invoice"] = normalized["sales_invoice"].strip()
    state, failure = _build(normalized)
    if failure:
        return failure
    preview = _preview(state)
    token = approvals.create(
        action=_ACTION,
        site=getattr(frappe.local, "site", ""),
        user=user,
        payload={
            "request": normalized,
            "preview": preview,
            "fingerprint": _fingerprint(state, normalized, preview),
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
        "The native reconciliation state changed after preparation. Please prepare it again.",
    )


def _safe_rollback() -> None:
    try:
        frappe.db.rollback()
    except Exception:
        pass


def _native_post_state(
    payment: Any, invoice: Any, receivable_account: str, advance_account: str | None
) -> tuple[float | None, float | None]:
    try:
        reconciliation = _configure_reconciliation(
            payment, invoice, receivable_account, advance_account
        )
        payment_rows = list(reconciliation.get_payment_entries() or [])
        source_rows = [
            row
            for row in payment_rows
            if _value(row, "reference_type") == _PAYMENT_ENTRY
            and str(_value(row, "reference_name", "")) == str(_value(payment, "name"))
            and flt(_value(row, "amount")) > _tolerance(_precision())
        ]
        source_after = (
            flt(_value(source_rows[0], "amount"), _precision())
            if len(source_rows) == 1
            else (0.0 if not source_rows else None)
        )

        reconciliation.get_invoice_entries()
        invoice_rows = [
            row
            for row in (_value(reconciliation, "invoices", []) or [])
            if _value(row, "invoice_type") == _SALES_INVOICE
            and str(_value(row, "invoice_number", "")) == str(_value(invoice, "name"))
        ]
        invoice_after = (
            flt(_value(invoice_rows[0], "outstanding_amount"), _precision())
            if len(invoice_rows) == 1
            else (0.0 if not invoice_rows else None)
        )
        return source_after, invoice_after
    except Exception:
        return None, None


def confirm_customer_payment_reconciliation(
    approval_token: str, confirm: bool
) -> dict[str, Any]:
    user = _user()
    site = getattr(frappe.local, "site", "")
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=site, user=user)
        return _error(
            "CONFIRMATION_REQUIRED",
            "The pending reconciliation was declined and no accounting mutation was performed.",
        )

    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(
            state, "Customer Payment Entry reconciliation"
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
            "This reconciliation confirmation is unavailable.",
        )

    current, failure = _build(deepcopy(request))
    if failure:
        if failure.get("code") in {
            "PERMISSION_DENIED",
            "RECONCILIATION_ALREADY_RUNNING",
            "NATIVE_RECONCILIATION_UNAVAILABLE",
        }:
            return failure
        return _stale()
    current_preview = _preview(current)
    if _fingerprint(current, request, current_preview) != approved_fingerprint:
        return _stale()

    reconciliation = current["reconciliation"]
    try:
        # This native validation only checks the exact in-memory allocation;
        # the submitted Payment Entry and ledgers remain ERPNext's authority.
        reconciliation.validate_allocation()
        reconciliation.reconcile_allocations()
        applied_amount = flt(
            _value(
                list(_value(reconciliation, "allocation", []) or [])[0],
                "allocated_amount",
            ),
            _precision(),
        )
    except frappe.PermissionError:
        _safe_rollback()
        return _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot complete this reconciliation.",
        )
    except frappe.ValidationError as error:
        _safe_rollback()
        if "india_compliance" in type(error).__module__:
            return _error(
                "REGIONAL_VALIDATION_FAILED",
                "A regional ERPNext validation rejected this reconciliation.",
            )
        return _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected this reconciliation during final validation.",
        )
    except Exception:
        _safe_rollback()
        return _error(
            "RECONCILIATION_FAILED",
            "ERPNext could not complete the reconciliation. Inspect the exact Payment Entry and Sales Invoice before retrying.",
        )

    try:
        fresh_payment = frappe.get_doc(_PAYMENT_ENTRY, request["payment_entry"])
        fresh_invoice = frappe.get_doc(_SALES_INVOICE, request["sales_invoice"])
    except Exception:
        return _error(
            "RECONCILIATION_FAILED",
            "Reconciliation completed but the resulting documents could not be reloaded safely.",
        )
    source_after, invoice_after = _native_post_state(
        fresh_payment,
        fresh_invoice,
        current["receivable_account"],
        current["default_advance_account"],
    )
    return {
        "status": "reconciled",
        "payment_entry": str(_value(fresh_payment, "name")),
        "sales_invoice": str(_value(fresh_invoice, "name")),
        "customer": str(_value(fresh_invoice, "customer")),
        "company": str(_value(fresh_invoice, "company")),
        "source_kind": current["source_kind"],
        "applied_amount": applied_amount,
        "allocation_currency": current["allocation_currency"],
        "invoice_outstanding_before": current["invoice_outstanding"],
        "invoice_outstanding_after": invoice_after,
        "source_available_before": current["source_available"],
        "source_available_after": source_after,
        "separate_advance_account_applied": current["separate_advance_account"],
        "regional_adjustment_warning": _regional_warning(current["regional"]),
        "exchange_or_gain_loss_warning": _exchange_warning(
            fresh_payment, fresh_invoice, current["allocation_currency"]
        ),
        "interaction": {"required": False},
    }
