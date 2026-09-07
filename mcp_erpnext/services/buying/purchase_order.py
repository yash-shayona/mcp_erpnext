"""Safe, two-phase Purchase Order service using native ERPNext defaults."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import input_directive
from ...observability import new_error_reference

_ACTION = "create_purchase_order"
_COMMERCIAL_DEFAULTS = ("price_list_currency", "currency", "conversion_rate", "plc_conversion_rate")


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required for Purchase Order creation.",
            frappe.PermissionError,
        )
    return user


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": retryable,
    }


def _needs_input(missing: list[str], message: str | None = None) -> dict[str, Any]:
    return {
        "status": "needs_input",
        "missing": missing,
        **({"message": message} if message else {}),
        "interaction": input_directive().model_dump(mode="json"),
    }


def _permitted_record(
    doctype: str, name: str, fields: list[str], filters: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    rows = frappe.get_list(
        doctype,
        filters={"name": name, **(filters or {})},
        fields=["name", *fields],
        limit_page_length=1,
        ignore_permissions=False,
    )
    return rows[0] if rows else None


def _reference_name(reference: Any, doctype: str) -> str | None:
    if not isinstance(reference, dict) or reference.get("doctype") != doctype:
        return None
    name = reference.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def _resolve_company(company: str | None) -> str | None:
    resolved = company or frappe.defaults.get_user_default("Company")
    if not resolved:
        return None
    return resolved if _permitted_record("Company", resolved, []) else None


def _permitted_link(
    doctype: str, value: str | None, *, label: str, filters: dict[str, Any] | None = None
) -> tuple[str | None, dict[str, Any] | None]:
    """Accept optional commercial links only when they are permission-visible."""
    if value is None:
        return None, None
    if not value.strip():
        return None, _error("INVALID_PURCHASE_ORDER_DETAILS", f"{label} must be a non-empty name.")
    if not _permitted_record(doctype, value, [], filters):
        return None, _error(
            "INVALID_PURCHASE_ORDER_DETAILS", f"{label} is not available to the authenticated user."
        )
    return value, None


def _prepare_items(items: Any, schedule_date: Any) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    if not isinstance(items, list) or not items:
        return None, _needs_input(["items"])
    prepared: list[dict[str, Any]] = []
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            return None, _error("INVALID_PURCHASE_ORDER_DETAILS", f"Item row {index} must be an object.")
        item_name = _reference_name(raw.get("item"), "Item")
        if not item_name:
            return None, _error(
                "INVALID_PURCHASE_ORDER_DETAILS",
                f"Item row {index} requires a resolved Item reference.",
            )
        item = _permitted_record(
            "Item",
            item_name,
            ["item_code", "item_name", "stock_uom"],
            {"disabled": ["!=", 1], "is_purchase_item": 1},
        )
        if not item:
            return None, _error(
                "INVALID_ITEM",
                f"Item row {index} is not available to the authenticated user.",
            )
        qty = raw.get("qty")
        if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
            return None, _error(
                "INVALID_PURCHASE_ORDER_DETAILS", f"Item row {index} quantity must be greater than zero."
            )
        row: dict[str, Any] = {"item_code": item["name"], "qty": qty, "schedule_date": schedule_date}
        if raw.get("rate") is not None:
            row["rate"] = raw["rate"]
        prepared.append(row)
    return prepared, None


def _safe_doc_data(doc: Any) -> dict[str, Any]:
    data = doc.as_dict()
    for field in ("__islocal", "owner", "creation", "modified", "modified_by"):
        data.pop(field, None)
    return data


def _preview(doc: Any) -> dict[str, Any]:
    return {
        "supplier": {
            "doctype": "Supplier",
            "name": doc.supplier,
            "supplier_name": doc.supplier_name,
        },
        "company": doc.company,
        "transaction_date": str(doc.transaction_date),
        "schedule_date": str(doc.schedule_date),
        "currency": doc.currency,
        "buying_price_list": doc.buying_price_list,
        "items": [
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "qty": row.qty,
                "schedule_date": str(row.schedule_date) if row.schedule_date else None,
                "uom": row.uom,
                "rate": row.rate,
                "amount": row.amount,
            }
            for row in doc.items
        ],
        "taxes": [
            {
                "charge_type": row.charge_type,
                "account_head": row.account_head,
                "rate": row.rate,
                "tax_amount": row.tax_amount,
                "total": row.total,
            }
            for row in doc.taxes
        ],
        "net_total": doc.net_total,
        "total_taxes_and_charges": doc.total_taxes_and_charges,
        "grand_total": doc.grand_total,
    }


def prepare_purchase_order(
    supplier: dict[str, Any],
    items: list[dict[str, Any]],
    company: str | None = None,
    transaction_date: str | None = None,
    schedule_date: str | None = None,
    buying_price_list: str | None = None,
    taxes_and_charges: str | None = None,
) -> dict[str, Any]:
    """Prepare an ERPNext-calculated Purchase Order preview without writing."""
    approvals.prune_expired()
    user = _current_user()
    supplier_name = _reference_name(supplier, "Supplier")
    if not supplier_name:
        return _error("INVALID_PURCHASE_ORDER_DETAILS", "A resolved Supplier reference is required.")
    permitted_supplier = _permitted_record(
        "Supplier", supplier_name, ["supplier_name"], {"disabled": ["!=", 1]}
    )
    if not permitted_supplier:
        return _error("INVALID_SUPPLIER", "Supplier is not available to the authenticated user.")
    resolved_company = _resolve_company(company)
    if not resolved_company:
        return _needs_input(["company"], "No permitted Company is available.")
    resolved_price_list, failure = _permitted_link(
        "Price List", buying_price_list, label="Buying price list"
    )
    if failure:
        return failure
    resolved_taxes, failure = _permitted_link(
        "Purchase Taxes and Charges Template",
        taxes_and_charges,
        label="Purchase taxes and charges template",
        filters={"company": resolved_company, "disabled": ["!=", 1]},
    )
    if failure:
        return failure
    try:
        resolved_transaction_date = getdate(transaction_date or nowdate())
        resolved_schedule_date = getdate(schedule_date or resolved_transaction_date)
    except Exception:
        return _error("INVALID_PURCHASE_ORDER_DETAILS", "Dates must be valid ISO dates.")
    if resolved_schedule_date < resolved_transaction_date:
        return _error(
            "INVALID_PURCHASE_ORDER_DETAILS", "Required-by date cannot be before the transaction date."
        )
    prepared_items, failure = _prepare_items(items, resolved_schedule_date)
    if failure:
        return failure
    assert prepared_items is not None
    if not frappe.has_permission("Purchase Order", "create"):
        return {
            "status": "permission_denied",
            "missing_permissions": ["Purchase Order"],
            "message": "The authenticated user cannot create Purchase Orders.",
        }

    doc = frappe.new_doc("Purchase Order")
    doc.supplier = permitted_supplier["name"]
    doc.company = resolved_company
    doc.transaction_date = resolved_transaction_date
    doc.schedule_date = resolved_schedule_date
    if resolved_price_list:
        doc.buying_price_list = resolved_price_list
    if resolved_taxes:
        doc.taxes_and_charges = resolved_taxes
    for item in prepared_items:
        doc.append("items", item)
    doc.set_missing_values()
    missing_defaults = [field for field in _COMMERCIAL_DEFAULTS if not doc.get(field)]
    if missing_defaults:
        return _needs_input(
            missing_defaults,
            "ERPNext could not determine all commercial defaults for this purchase order.",
        )
    doc.calculate_taxes_and_totals()
    doc.run_method("validate")
    token = approvals.create(
        action=_ACTION,
        site=frappe.local.site,
        user=user,
        payload=_safe_doc_data(doc),
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": _preview(doc),
    }


def confirm_purchase_order(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Insert a reviewed Draft Purchase Order through normal Frappe permissions."""
    user = _current_user()
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=frappe.local.site, user=user)
        return _error(
            "CONFIRMATION_REQUIRED", "Review the Purchase Order preview before confirming it."
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Purchase Order")
        return _error(code, message, retryable=retryable)
    if not frappe.has_permission("Purchase Order", "create"):
        return {
            "status": "permission_denied",
            "missing_permissions": ["Purchase Order"],
            "message": "The authenticated user cannot create Purchase Orders.",
        }
    try:
        doc = frappe.get_doc(approval.payload)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    return {"status": "created", "purchase_order": doc.name, "docstatus": doc.docstatus}
