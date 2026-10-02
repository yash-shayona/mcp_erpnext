"""Safe, two-phase Draft Quotation service for the controlled MCP capability."""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

import frappe
from frappe.utils import getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...config.business_defaults import (
    BusinessDefaultsConfigurationError,
    get_quotation_validity_days,
)
from ...contracts.interaction import approval_directive, input_directive
from ...public_errors import defined_error
from ..common.fingerprint import stable_fingerprint
from ..common.write_policy import (
    approval_entry_failure,
    current_mode,
    direct_entry_failure,
    disabled_failure,
    exact_mode_failure,
)
from ...settings import WriteMode
from .payment_terms import apply_payment_terms_template, set_native_payment_schedule
from .terms import apply_selling_terms

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


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


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
            "INVALID_QUOTATION_DETAILS"
        )
    name = value.strip()
    if not _permitted_record(doctype, name, [], filters):
        return None, _error(
            "INVALID_QUOTATION_DETAILS",
        )
    return name, None


def _number(
    value: Any, *, field: str, positive: bool = False
) -> tuple[float | None, dict[str, Any] | None]:
    if isinstance(value, bool) or value in (None, ""):
        return None, _error("INVALID_QUOTATION_DETAILS")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, _error("INVALID_QUOTATION_DETAILS")
    if (
        not math.isfinite(number)
        or (positive and number <= 0)
        or (not positive and number < 0)
    ):
        constraint = "greater than zero" if positive else "zero or greater"
        return None, _error(
            "INVALID_QUOTATION_DETAILS"
        )
    return number, None


def _date(value: Any, *, field: str) -> tuple[Any | None, dict[str, Any] | None]:
    if not isinstance(value, str) or not value.strip():
        return None, _needs_input([field])
    try:
        return getdate(value), None
    except Exception:
        return None, _error(
            "INVALID_QUOTATION_DETAILS"
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
                "INVALID_QUOTATION_DETAILS"
            )
        item_name = _reference_name(raw.get("item"), "Item")
        if not item_name:
            return None, _error(
                "INVALID_QUOTATION_DETAILS",
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
        if "description" in raw and raw["description"] is not None:
            if not isinstance(raw["description"], str):
                return None, _error(
                    "INVALID_QUOTATION_DETAILS",
                )
            row["description"] = raw["description"]
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
                "description": getattr(row, "description", None),
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
        "payment_terms_template": doc.get("payment_terms_template"),
        "payment_schedule": [
            {
                "payment_term": row.get("payment_term"),
                "due_date": str(row.get("due_date")) if row.get("due_date") else None,
                "invoice_portion": row.get("invoice_portion"),
                "payment_amount": row.get("payment_amount"),
                "description": row.get("description"),
            }
            for row in doc.get("payment_schedule", []) or []
        ],
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
    payment_terms_template: str | None = None,
    *,
    _create_approval: bool = True,
) -> dict[str, Any]:
    """Prepare an ERPNext-calculated Quotation preview without creating a record."""
    if failure := disabled_failure("create"):
        return _error(failure.code)
    if current_mode("create") is WriteMode.APPROVAL_REQUIRED and _create_approval:
        approvals.prune_expired()
    user = _current_user()
    request = {
        "customer": customer,
        "items": items,
        "valid_till": valid_till,
        "company": company,
        "transaction_date": transaction_date,
        "selling_price_list": selling_price_list,
        "taxes_and_charges": taxes_and_charges,
        "additional_discount_percentage": additional_discount_percentage,
        "discount_amount": discount_amount,
        "tc_name": tc_name,
        "payment_terms_template": payment_terms_template,
    }
    if not frappe.has_permission("Quotation", "create"):
        return _permission_denied()
    customer_name = _reference_name(customer, "Customer")
    if not customer_name:
        return _error("INVALID_CUSTOMER")
    if not _permitted_record(
        "Customer", customer_name, ["customer_name"], {"disabled": ["!=", 1]}
    ):
        return _error(
            "INVALID_CUSTOMER"
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
        try:
            quotation_validity_days = get_quotation_validity_days(
                frappe_module=frappe
            )
        except BusinessDefaultsConfigurationError:
            return _error(
                "INVALID_BUSINESS_DEFAULTS",
            )
        validity = transaction + timedelta(days=quotation_validity_days)
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
    if additional_discount_percentage is not None and discount_amount is not None:
        return _error(
            "INVALID_QUOTATION_DETAILS",
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
    if additional_discount is not None:
        doc.additional_discount_percentage = additional_discount
    if discount_amount is not None:
        doc.discount_amount = discount_amount
    for item in prepared_items or []:
        doc.append("items", item)

    if failure := apply_payment_terms_template(
        doc, payment_terms_template, frappe_module=frappe
    ):
        return _error("INVALID_QUOTATION_DETAILS")

    doc.set_missing_values()
    for prepared_item, row in zip(prepared_items or [], doc.items, strict=True):
        if "description" in prepared_item:
            row.description = prepared_item["description"]
    if failure := apply_selling_terms(doc, tc_name, frappe_module=frappe):
        return _error("INVALID_QUOTATION_DETAILS")
    missing_defaults = [
        fieldname for fieldname in _COMMERCIAL_DEFAULTS if not doc.get(fieldname)
    ]
    if missing_defaults:
        return _needs_input(
            missing_defaults,
            "ERPNext could not determine all commercial defaults for this Quotation.",
        )
    doc.calculate_taxes_and_totals()
    if failure := set_native_payment_schedule(doc):
        return _error("INVALID_QUOTATION_DETAILS")
    try:
        # Use the native controller seam without dispatching document-event
        # webhooks/server scripts during non-persisting preparation.
        doc.validate()
    except frappe.ValidationError:
        return _error(
            "NATIVE_VALIDATION_FAILED",
        )
    preview = _preview(doc)
    document = _safe_doc_data(doc)
    fingerprint = stable_fingerprint(
        {
            "request": request,
            "preview": preview,
            "naming_series": document.get("naming_series"),
        }
    )
    if not _create_approval:
        return {"status": "ready", "preview": preview, "_doc": doc}
    if current_mode("create") is WriteMode.DIRECT:
        return {"status": "preview", "preview": preview}
    token = approvals.create(
        action=_ACTION,
        site=frappe.local.site,
        user=user,
        payload={
            **document,
            "_mcp_request": request,
            "_mcp_preview": preview,
            "_mcp_fingerprint": fingerprint,
            "_mcp_document_fingerprint": stable_fingerprint(document),
        },
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": preview,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def confirm_quotation(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Create the reviewed Draft Quotation using only signed server-side prepared data."""
    if failure := approval_entry_failure("create"):
        return _error(failure.code)
    user = _current_user()
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
        code, message, retryable = confirmation_failure(state, "Quotation")
        return _error(code, retryable=retryable)
    if not frappe.has_permission("Quotation", "create"):
        return _permission_denied()
    payload = approval.payload
    request = payload.get("_mcp_request")
    approved_preview = payload.get("_mcp_preview")
    approved_fingerprint = payload.get("_mcp_fingerprint")
    approved_document_fingerprint = payload.get("_mcp_document_fingerprint")
    document = {
        key: value for key, value in payload.items() if not key.startswith("_mcp_")
    }
    if (
        payload.get("doctype") != "Quotation"
        or not payload.get("party_name")
        or not payload.get("items")
        or not isinstance(request, dict)
        or not isinstance(approved_preview, dict)
        or not isinstance(approved_fingerprint, str)
        or not isinstance(approved_document_fingerprint, str)
        or stable_fingerprint(document) != approved_document_fingerprint
        or stable_fingerprint(
            {
                "request": request,
                "preview": approved_preview,
                "naming_series": document.get("naming_series"),
            }
        )
        != approved_fingerprint
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE",
        )

    rebuilt = prepare_quotation(**request, _create_approval=False)
    if rebuilt.get("status") != "ready" or "_doc" not in rebuilt:
        return _error(
            "STALE_CONFIRMATION",
        )
    doc = rebuilt["_doc"]
    current_preview = rebuilt["preview"]
    current_document = _safe_doc_data(doc)
    if stable_fingerprint(
        {
            "request": request,
            "preview": current_preview,
            "naming_series": current_document.get("naming_series"),
        }
    ) != approved_fingerprint:
        return _error(
            "STALE_CONFIRMATION",
        )

    try:
        if failure := exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED):
            return _error(failure.code)
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


def execute_quotation(
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
    payment_terms_template: str | None = None,
) -> dict[str, Any]:
    """Create a Draft Quotation through the direct policy path."""
    if failure := direct_entry_failure("create"):
        return _error(failure.code)
    planned = prepare_quotation(
        customer,
        items,
        valid_till,
        company,
        transaction_date,
        selling_price_list,
        taxes_and_charges,
        additional_discount_percentage,
        discount_amount,
        tc_name,
        payment_terms_template,
        _create_approval=False,
    )
    if planned.get("status") != "ready" or "_doc" not in planned:
        return planned
    doc = planned["_doc"]
    try:
        if failure := exact_mode_failure("create", WriteMode.DIRECT):
            return _error(failure.code)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _permission_denied()
    except Exception:
        frappe.db.rollback()
        raise
    return {"status": "created", "quotation": doc.name, "docstatus": doc.docstatus, "idempotent": False}
