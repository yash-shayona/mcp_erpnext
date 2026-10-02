"""Safe, two-phase Purchase Order service using native ERPNext defaults."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import input_directive
from ...public_errors import defined_error
from ..common.write_policy import approval_entry_failure, current_mode, direct_entry_failure, disabled_failure, exact_mode_failure
from ...settings import WriteMode
from .commercial_terms import (
    apply_creation_choices, commercial_fingerprint, commercial_preview,
    stale_commercial, template_snapshot,
)

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


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


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
        return None, _error("INVALID_PURCHASE_ORDER_DETAILS")
    if not _permitted_record(doctype, value, [], filters):
        return None, _error(
            "INVALID_PURCHASE_ORDER_DETAILS"
        )
    return value, None


def _prepare_items(items: Any, schedule_date: Any) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    if not isinstance(items, list) or not items:
        return None, _needs_input(["items"])
    prepared: list[dict[str, Any]] = []
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            return None, _error("INVALID_PURCHASE_ORDER_DETAILS")
        item_name = _reference_name(raw.get("item"), "Item")
        if not item_name:
            return None, _error(
                "INVALID_PURCHASE_ORDER_DETAILS",
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
            )
        qty = raw.get("qty")
        if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
            return None, _error(
                "INVALID_PURCHASE_ORDER_DETAILS"
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
        **commercial_preview(doc),
    }


def prepare_purchase_order(
    supplier: dict[str, Any],
    items: list[dict[str, Any]],
    company: str | None = None,
    transaction_date: str | None = None,
    schedule_date: str | None = None,
    buying_price_list: str | None = None,
    taxes_and_charges: str | None = None,
    tc_name: str | None = None,
    payment_terms_template: str | None = None,
    *,
    _direct_execution: bool = False,
) -> dict[str, Any]:
    """Prepare an ERPNext-calculated Purchase Order preview without writing."""
    if not _direct_execution and (failure := disabled_failure("create")):
        return _error(failure.code)
    user = _current_user()
    supplier_name = _reference_name(supplier, "Supplier")
    if not supplier_name:
        return _error("INVALID_PURCHASE_ORDER_DETAILS")
    permitted_supplier = _permitted_record(
        "Supplier", supplier_name, ["supplier_name"], {"disabled": ["!=", 1]}
    )
    if not permitted_supplier:
        return _error("INVALID_SUPPLIER")
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
        return _error("INVALID_PURCHASE_ORDER_DETAILS")
    if resolved_schedule_date < resolved_transaction_date:
        return _error(
            "INVALID_PURCHASE_ORDER_DETAILS"
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
    failure = apply_creation_choices(doc, tc_name, payment_terms_template, frappe_module=frappe)
    if failure:
        return failure
    doc.set_missing_values()
    templates, failure = template_snapshot(doc, frappe_module=frappe)
    if failure:
        return failure
    # Freeze resolved party defaults for the reviewed transaction and confirmation.
    doc.ignore_default_payment_terms_template = 1
    missing_defaults = [field for field in _COMMERCIAL_DEFAULTS if not doc.get(field)]
    if missing_defaults:
        return _needs_input(
            missing_defaults,
            "ERPNext could not determine all commercial defaults for this purchase order.",
        )
    doc.calculate_taxes_and_totals()
    doc.set_missing_terms()
    doc.set("payment_schedule", [])
    doc.set_payment_schedule()
    doc.run_method("validate")
    # Direct execution reuses planning without ever entering approval storage.
    if _direct_execution:
        return {"status": "ready", "preview": _preview(doc), "_doc": doc}
    if current_mode("create") is WriteMode.DIRECT:
        preview = _preview(doc)
        return {"status": "preview", "preview": preview}
    approvals.prune_expired()
    token = approvals.create(
        action=_ACTION,
        site=frappe.local.site,
        user=user,
        payload={**_safe_doc_data(doc), "_mcp_commercial": {
            "templates": templates, "fingerprint": commercial_fingerprint(doc),
        }},
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": _preview(doc),
    }


def confirm_purchase_order(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Insert a reviewed Draft Purchase Order through normal Frappe permissions."""
    if failure := approval_entry_failure("create"):
        return _error(failure.code)
    user = _current_user()
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=frappe.local.site, user=user)
        return _error(
            "CONFIRMATION_REQUIRED"
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Purchase Order")
        return _error(code, retryable=retryable)
    if not frappe.has_permission("Purchase Order", "create"):
        return {
            "status": "permission_denied",
            "missing_permissions": ["Purchase Order"],
            "message": "The authenticated user cannot create Purchase Orders.",
        }
    try:
        payload = dict(approval.payload)
        approved = payload.pop("_mcp_commercial", None)
        if approved is None:
            return stale_commercial()
        doc = frappe.get_doc(payload)
        templates, failure = template_snapshot(doc, frappe_module=frappe)
        if failure or templates != approved["templates"]:
            return stale_commercial()
        doc.ignore_default_payment_terms_template = 1
        doc.run_method("validate")
        if commercial_fingerprint(doc) != approved["fingerprint"]:
            frappe.db.rollback()
            return stale_commercial()
        if failure := exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED):
            return _error(failure.code)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        # Hooks must not silently substitute the approved commercial state.
        templates, failure = template_snapshot(doc, frappe_module=frappe)
        if failure or templates != approved["templates"] or commercial_fingerprint(doc) != approved["fingerprint"]:
            frappe.db.rollback()
            return stale_commercial()
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    return {"status": "created", "purchase_order": doc.name, "docstatus": doc.docstatus}


def execute_purchase_order(
    supplier: dict[str, Any],
    items: list[dict[str, Any]],
    company: str | None = None,
    transaction_date: str | None = None,
    schedule_date: str | None = None,
    buying_price_list: str | None = None,
    taxes_and_charges: str | None = None,
    tc_name: str | None = None,
    payment_terms_template: str | None = None,
) -> dict[str, Any]:
    if failure := direct_entry_failure("create"):
        return _error(failure.code)
    result = prepare_purchase_order(
        supplier, items, company, transaction_date, schedule_date,
        buying_price_list, taxes_and_charges, tc_name, payment_terms_template,
        _direct_execution=True,
    )
    if result.get("status") != "ready" or "_doc" not in result:
        return result
    doc = result["_doc"]
    try:
        if failure := exact_mode_failure("create", WriteMode.DIRECT):
            return _error(failure.code)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    return {"status": "created", "purchase_order": doc.name, "docstatus": doc.docstatus}
