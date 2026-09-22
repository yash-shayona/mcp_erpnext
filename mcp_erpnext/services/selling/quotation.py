"""Safe, two-phase Draft Quotation service for the controlled MCP capability."""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

import frappe
from frappe.utils import getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive, input_directive
from ...observability import new_error_reference
from ...settings import MCPSettings

_ACTION = "create_quotation"
_COMMERCIAL_DEFAULTS = (
    "selling_price_list",
    "price_list_currency",
    "currency",
    "conversion_rate",
    "plc_conversion_rate",
)


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required for Quotation creation.",
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
    """Keep existing missing-field payloads while exposing the shared input directive."""
    return {
        "status": "needs_input",
        "missing": missing,
        **({"message": message} if message else {}),
        "interaction": input_directive().model_dump(mode="json"),
    }


def _permission_denied() -> dict[str, Any]:
    return {
        "status": "permission_denied",
        "missing_permissions": ["Quotation"],
        "message": "The authenticated user cannot create Quotations.",
    }


def _reference_name(reference: Any, doctype: str) -> str | None:
    if not isinstance(reference, dict) or reference.get("doctype") != doctype:
        return None
    name = reference.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


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


def _resolve_company(company: Any) -> str | None:
    if company is not None and (not isinstance(company, str) or not company.strip()):
        return None
    resolved = (
        company.strip()
        if isinstance(company, str)
        else frappe.defaults.get_user_default("Company")
    )
    if not resolved:
        return None
    return resolved if _permitted_record("Company", resolved, []) else None


def _permitted_link(
    doctype: str, value: Any, *, label: str, filters: dict[str, Any] | None = None
) -> tuple[str | None, dict[str, Any] | None]:
    """Accept an optional commercial setting only when the actor may read it."""
    if value is None:
        return None, None
    if not isinstance(value, str) or not value.strip():
        return None, _error(
            "INVALID_QUOTATION_DETAILS", f"{label} must be a non-empty name."
        )
    name = value.strip()
    if not _permitted_record(doctype, name, [], filters):
        return None, _error(
            "INVALID_QUOTATION_DETAILS",
            f"{label} is not available to the authenticated user.",
        )
    return name, None


def _number(
    value: Any, *, field: str, positive: bool = False
) -> tuple[float | None, dict[str, Any] | None]:
    if isinstance(value, bool) or value in (None, ""):
        return None, _error("INVALID_QUOTATION_DETAILS", f"{field} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, _error("INVALID_QUOTATION_DETAILS", f"{field} must be a number.")
    if (
        not math.isfinite(number)
        or (positive and number <= 0)
        or (not positive and number < 0)
    ):
        constraint = "greater than zero" if positive else "zero or greater"
        return None, _error(
            "INVALID_QUOTATION_DETAILS", f"{field} must be {constraint}."
        )
    return number, None


def _date(value: Any, *, field: str) -> tuple[Any | None, dict[str, Any] | None]:
    if not isinstance(value, str) or not value.strip():
        return None, _needs_input([field])
    try:
        return getdate(value), None
    except Exception:
        return None, _error(
            "INVALID_QUOTATION_DETAILS", f"{field} must be a valid date."
        )


def _prepare_items(
    items: Any,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    if not isinstance(items, list) or not items:
        return None, _needs_input(["items"])

    prepared: list[dict[str, Any]] = []
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            return None, _error(
                "INVALID_QUOTATION_DETAILS", f"Item row {index} must be an object."
            )
        item_name = _reference_name(raw.get("item"), "Item")
        if not item_name:
            return None, _error(
                "INVALID_QUOTATION_DETAILS",
                f"Item row {index} requires a resolved Item reference.",
            )
        item = _permitted_record(
            "Item",
            item_name,
            ["item_code", "item_name", "stock_uom"],
            {"disabled": ["!=", 1], "is_sales_item": 1},
        )
        if not item:
            return None, _error(
                "INVALID_ITEM",
                f"Item row {index} is not available to the authenticated user.",
            )
        quantity, failure = _number(
            raw.get("qty"), field=f"Item row {index} quantity", positive=True
        )
        if failure:
            return None, failure
        row = {"item_code": item["name"], "qty": quantity}
        for fieldname, label in (
            ("rate", "rate"),
            ("discount_percentage", "discount percentage"),
            ("discount_amount", "discount amount"),
        ):
            if fieldname not in raw:
                continue
            value, failure = _number(raw[fieldname], field=f"Item row {index} {label}")
            if failure:
                return None, failure
            row[fieldname] = value
        prepared.append(row)
    return prepared, None


def _safe_doc_data(doc: Any) -> dict[str, Any]:
    data = doc.as_dict()
    for fieldname in ("__islocal", "owner", "creation", "modified", "modified_by"):
        data.pop(fieldname, None)
    return data


def _preview(doc: Any) -> dict[str, Any]:
    return {
        "customer": {
            "doctype": "Customer",
            "name": doc.party_name,
            "customer_name": doc.customer_name,
        },
        "company": doc.company,
        "transaction_date": str(doc.transaction_date),
        "valid_till": str(doc.valid_till),
        "currency": doc.currency,
        "selling_price_list": doc.selling_price_list,
        "items": [
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "qty": row.qty,
                "uom": row.uom,
                "rate": row.rate,
                "discount_percentage": row.discount_percentage,
                "discount_amount": row.discount_amount,
                "amount": row.amount,
                "net_amount": row.net_amount,
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
        # ERPNext leaves these unset when no additional discount applies. The public
        # preview contract represents that business state as its numeric zero value.
        "additional_discount_percentage": doc.additional_discount_percentage or 0,
        "discount_amount": doc.discount_amount or 0,
        "grand_total": doc.grand_total,
        "tc_name": doc.tc_name,
        "terms": doc.terms,
    }


def prepare_quotation(
    customer: dict[str, str],
    items: list[dict[str, Any]],
    valid_till: str | None = None,
    company: str | None = None,
    transaction_date: str | None = None,
    selling_price_list: str | None = None,
    taxes_and_charges: str | None = None,
    additional_discount_percentage: float | None = None,
    discount_amount: float | None = None,
    tc_name: str | None = None,
) -> dict[str, Any]:
    """Prepare an ERPNext-calculated Quotation preview without creating a record."""
    approvals.prune_expired()
    user = _current_user()
    if not frappe.has_permission("Quotation", "create"):
        return _permission_denied()
    customer_name = _reference_name(customer, "Customer")
    if not customer_name:
        return _error("INVALID_CUSTOMER", "A resolved Customer reference is required.")
    if not _permitted_record(
        "Customer", customer_name, ["customer_name"], {"disabled": ["!=", 1]}
    ):
        return _error(
            "INVALID_CUSTOMER", "Customer is not available to the authenticated user."
        )
    prepared_items, failure = _prepare_items(items)
    if failure:
        return failure
    transaction = getdate(nowdate())
    if transaction_date is not None:
        transaction, failure = _date(transaction_date, field="transaction_date")
        if failure:
            return failure
    if valid_till is None:
        # Treat the configured period as days from the effective transaction date,
        # so an explicit backdated transaction still passes ERPNext's native rule.
        validity = transaction + timedelta(
            days=MCPSettings.from_environment().quotation_validity_days
        )
    else:
        validity, failure = _date(valid_till, field="valid_till")
        if failure:
            return failure
    resolved_company = _resolve_company(company)
    if not resolved_company:
        return _needs_input(["company"], "No permitted Company is available.")
    resolved_price_list, failure = _permitted_link(
        "Price List", selling_price_list, label="Selling price list"
    )
    if failure:
        return failure
    resolved_taxes, failure = _permitted_link(
        "Sales Taxes and Charges Template",
        taxes_and_charges,
        label="Sales taxes and charges template",
        filters={"company": resolved_company, "disabled": ["!=", 1]},
    )
    if failure:
        return failure
    resolved_terms, failure = _permitted_link(
        "Terms and Conditions", tc_name, label="Terms and conditions"
    )
    if failure:
        return failure
    if additional_discount_percentage is not None and discount_amount is not None:
        return _error(
            "INVALID_QUOTATION_DETAILS",
            "Provide either a discount percentage or discount amount, not both.",
        )
    additional_discount = None
    if additional_discount_percentage is not None:
        additional_discount, failure = _number(
            additional_discount_percentage, field="Additional discount percentage"
        )
        if failure:
            return failure
    if discount_amount is not None:
        discount_amount, failure = _number(discount_amount, field="Discount amount")
        if failure:
            return failure

    doc = frappe.new_doc("Quotation")
    doc.quotation_to = "Customer"
    doc.party_name = customer_name
    # India Compliance's Quotation hooks still read this transient party alias.
    # Frappe omits non-DocField values from persistence while the hooks execute.
    doc.customer = customer_name
    doc.company = resolved_company
    doc.transaction_date = transaction
    doc.valid_till = validity
    doc.order_type = "Sales"
    if resolved_price_list:
        doc.selling_price_list = resolved_price_list
    if resolved_taxes:
        doc.taxes_and_charges = resolved_taxes
    if resolved_terms:
        doc.tc_name = resolved_terms
    if additional_discount is not None:
        doc.additional_discount_percentage = additional_discount
    if discount_amount is not None:
        doc.discount_amount = discount_amount
    for item in prepared_items or []:
        doc.append("items", item)

    doc.set_missing_values()
    missing_defaults = [
        fieldname for fieldname in _COMMERCIAL_DEFAULTS if not doc.get(fieldname)
    ]
    if missing_defaults:
        return _needs_input(
            missing_defaults,
            "ERPNext could not determine all commercial defaults for this Quotation.",
        )
    doc.calculate_taxes_and_totals()
    try:
        # Use the native controller seam without dispatching document-event
        # webhooks/server scripts during non-persisting preparation.
        doc.validate()
    except frappe.ValidationError:
        return _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected the Quotation during preparation.",
        )
    token = approvals.create(
        action=_ACTION, site=frappe.local.site, user=user, payload=_safe_doc_data(doc)
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": _preview(doc),
        "interaction": approval_directive().model_dump(mode="json"),
    }


def confirm_quotation(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Create the reviewed Draft Quotation using only signed server-side prepared data."""
    user = _current_user()
    if not confirm:
        approvals.cancel(
            approval_token, action=_ACTION, site=frappe.local.site, user=user
        )
        return _error(
            "CONFIRMATION_REQUIRED",
            "Review the Quotation preview before confirming it.",
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Quotation")
        return _error(code, message, retryable=retryable)
    if not frappe.has_permission("Quotation", "create"):
        return _permission_denied()
    if (
        approval.payload.get("doctype") != "Quotation"
        or not approval.payload.get("party_name")
        or not approval.payload.get("items")
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE",
            "This Quotation confirmation is not available in the current session.",
        )

    try:
        doc = frappe.get_doc(approval.payload)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _permission_denied()
    except Exception:
        frappe.db.rollback()
        raise
    return {
        "status": "created",
        "quotation": doc.name,
        "docstatus": doc.docstatus,
        "idempotent": False,
    }
