"""Safe, two-phase standalone Draft Sales Invoice creation."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import frappe
from frappe.utils import getdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...config.masters import customer as customer_config
from ...config.masters import item as item_config
from ...contracts.interaction import approval_directive, input_directive
from ...observability import new_error_reference
from ..common.entity_resolution import revalidate_exact_candidate

_ACTION = "create_sales_invoice"
_REQUIRED_DEFAULTS = (
    "company",
    "posting_date",
    "currency",
    "selling_price_list",
    "debit_to",
)
_OPTIONAL_LINKS = (
    ("customer_address", "Address", "Customer address"),
    ("shipping_address_name", "Address", "Shipping address"),
    ("contact_person", "Contact", "Contact person"),
)


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required for Sales Invoice creation.",
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


def _permission_denied() -> dict[str, Any]:
    return {
        "status": "error",
        "code": "PERMISSION_DENIED",
        "message": "The authenticated user cannot create Sales Invoices.",
        "reference": new_error_reference(),
        "retryable": False,
    }


def _reference_name(reference: Any, doctype: str) -> str | None:
    if not isinstance(reference, dict) or reference.get("doctype") != doctype:
        return None
    name = reference.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def _number(value: Any, *, field: str, positive: bool = False) -> tuple[float | None, dict[str, Any] | None]:
    if isinstance(value, bool) or value in (None, ""):
        return None, _error("INVALID_SALES_INVOICE_DETAILS", f"{field} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, _error("INVALID_SALES_INVOICE_DETAILS", f"{field} must be a number.")
    if not math.isfinite(number) or (positive and number <= 0) or (not positive and number < 0):
        constraint = "greater than zero" if positive else "zero or greater"
        return None, _error(
            "INVALID_SALES_INVOICE_DETAILS", f"{field} must be {constraint}."
        )
    return number, None


def _optional_name(value: Any, *, field: str) -> tuple[str | None, dict[str, Any] | None]:
    if value is None:
        return None, None
    if not isinstance(value, str) or not value.strip():
        return None, _error("INVALID_SALES_INVOICE_DETAILS", f"{field} must be a non-empty name.")
    return value.strip(), None


def _normalise_request(
    customer: Any,
    items: Any,
    company: Any,
    posting_date: Any,
    selling_price_list: Any,
    customer_address: Any,
    shipping_address_name: Any,
    contact_person: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    customer_name = _reference_name(customer, "Customer")
    if not customer_name:
        return None, _needs_input(["customer"])
    if not isinstance(items, list) or not items:
        return None, _needs_input(["items"])

    normalized_items: list[dict[str, Any]] = []
    for index, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, dict):
            return None, _error(
                "INVALID_SALES_INVOICE_DETAILS", f"Item row {index} must be an object."
            )
        item_name = _reference_name(raw_item.get("item"), "Item")
        if not item_name:
            return None, _error(
                "INVALID_SALES_INVOICE_DETAILS",
                f"Item row {index} requires a resolved Item reference.",
            )
        if "qty" not in raw_item:
            return None, _needs_input([f"items[{index}].qty"])
        quantity, failure = _number(
            raw_item.get("qty"), field=f"Item row {index} quantity", positive=True
        )
        if failure:
            return None, failure
        row: dict[str, Any] = {"item": item_name, "qty": quantity}
        if "rate" in raw_item and raw_item.get("rate") is not None:
            rate, failure = _number(raw_item.get("rate"), field=f"Item row {index} rate")
            if failure:
                return None, failure
            row["rate"] = rate
        normalized_items.append(row)

    normalized: dict[str, Any] = {
        "customer": customer_name,
        "items": normalized_items,
    }
    for fieldname, value in (
        ("company", company),
        ("posting_date", posting_date),
        ("selling_price_list", selling_price_list),
        ("customer_address", customer_address),
        ("shipping_address_name", shipping_address_name),
        ("contact_person", contact_person),
    ):
        if value is not None:
            normalized_value, failure = _optional_name(value, field=fieldname)
            if failure:
                return None, failure
            normalized[fieldname] = normalized_value
        else:
            normalized[fieldname] = None
    return normalized, None


def _revalidate_customer(name: str) -> dict[str, Any] | None:
    result = revalidate_exact_candidate(
        "Customer",
        name,
        customer_config.SEARCH_FILTERS,
        customer_config.DISPLAY_FIELDS,
    )
    return result.get("candidate") if result.get("status") == "resolved" else None


def _revalidate_item(name: str) -> dict[str, Any] | None:
    result = revalidate_exact_candidate(
        "Item",
        name,
        item_config.SEARCH_FILTERS,
        item_config.DISPLAY_FIELDS,
    )
    return result.get("candidate") if result.get("status") == "resolved" else None


def _permitted_link(doctype: str, name: str) -> bool:
    rows = frappe.get_list(
        doctype,
        filters={"name": name},
        fields=["name"],
        limit_page_length=1,
        ignore_permissions=False,
    )
    return bool(rows)


def _resolve_company(request: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    supplied = request.get("company")
    resolved = supplied or frappe.defaults.get_user_default("Company")
    if not resolved:
        return None, _needs_input(
            ["company"], "No permitted Company is available for the authenticated user."
        )
    if not _permitted_link("Company", resolved):
        return None, _error(
            "INVALID_SALES_INVOICE_DETAILS",
            "Company is not available to the authenticated user.",
        )
    return resolved, None


def _resolve_optional_links(request: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any] | None]:
    resolved: dict[str, str] = {}
    for fieldname, doctype, label in _OPTIONAL_LINKS:
        value = request.get(fieldname)
        if value is None:
            continue
        if not _permitted_link(doctype, value):
            return {}, _error(
                "INVALID_SALES_INVOICE_DETAILS",
                f"{label} is not available to the authenticated user.",
            )
        resolved[fieldname] = value
    return resolved, None


def _blocked(prerequisites: list[str]) -> dict[str, Any]:
    if len(prerequisites) == 1:
        prerequisite_text = prerequisites[0]
        code = (
            "SALES_ORDER_REQUIRED"
            if prerequisite_text == "Sales Order"
            else "DELIVERY_NOTE_REQUIRED"
        )
    else:
        prerequisite_text = " and ".join(prerequisites)
        code = "SALES_INVOICE_PREREQUISITES_REQUIRED"
    return {
        "status": "blocked",
        "code": code,
        "message": (
            f"ERPNext configuration requires {prerequisite_text} before a direct Sales Invoice."
        ),
        "prerequisites": prerequisites,
    }


def _value(document: Any, fieldname: str, default: Any = None) -> Any:
    getter = getattr(document, "get", None)
    if callable(getter):
        return getter(fieldname, default)
    return getattr(document, fieldname, default)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def _preview(doc: Any) -> dict[str, Any]:
    return {
        "doctype": "Sales Invoice",
        "docstatus": int(_value(doc, "docstatus", 0) or 0),
        "customer": _value(doc, "customer"),
        "customer_name": _value(doc, "customer_name"),
        "company": _value(doc, "company"),
        "posting_date": _json_value(_value(doc, "posting_date")),
        "due_date": _json_value(_value(doc, "due_date")),
        "currency": _value(doc, "currency"),
        "selling_price_list": _value(doc, "selling_price_list"),
        "contact_person": _value(doc, "contact_person"),
        "customer_address": _value(doc, "customer_address"),
        "shipping_address_name": _value(doc, "shipping_address_name"),
        "debit_to": _value(doc, "debit_to"),
        "items": [
            {
                "item_code": _value(row, "item_code"),
                "item_name": _value(row, "item_name"),
                "description": _value(row, "description"),
                "qty": _value(row, "qty"),
                "stock_uom": _value(row, "stock_uom"),
                "uom": _value(row, "uom"),
                "conversion_factor": _value(row, "conversion_factor"),
                "rate": _value(row, "rate"),
                "amount": _value(row, "amount"),
                "net_rate": _value(row, "net_rate"),
                "net_amount": _value(row, "net_amount"),
                "warehouse": _value(row, "warehouse"),
                "income_account": _value(row, "income_account"),
            }
            for row in _value(doc, "items", []) or []
        ],
        "taxes": [
            {
                "charge_type": _value(row, "charge_type"),
                "account_head": _value(row, "account_head"),
                "rate": _value(row, "rate"),
                "tax_amount": _value(row, "tax_amount"),
                "total": _value(row, "total"),
            }
            for row in _value(doc, "taxes", []) or []
        ],
        "payment_schedule": [
            {
                "due_date": _json_value(_value(row, "due_date")),
                "payment_term": _value(row, "payment_term"),
                "invoice_portion": _value(row, "invoice_portion"),
                "payment_amount": _value(row, "payment_amount"),
            }
            for row in _value(doc, "payment_schedule", []) or []
        ],
        "totals": {
            "total_qty": _value(doc, "total_qty"),
            "net_total": _value(doc, "net_total"),
            "total_taxes_and_charges": _value(doc, "total_taxes_and_charges"),
            "grand_total": _value(doc, "grand_total"),
            "rounded_total": _value(doc, "rounded_total"),
            "outstanding_amount": _value(doc, "outstanding_amount"),
            "base_net_total": _value(doc, "base_net_total"),
            "base_grand_total": _value(doc, "base_grand_total"),
        },
    }


def _fingerprint(request: dict[str, Any], preview: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"request": request, "preview": preview},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build(
    request: dict[str, Any],
) -> tuple[Any | None, dict[str, Any] | None, dict[str, Any] | None]:
    customer = _revalidate_customer(request["customer"])
    if not customer:
        return None, None, _error(
            "INVALID_CUSTOMER", "Customer is not available to the authenticated user."
        )

    for index, row in enumerate(request["items"], start=1):
        item = _revalidate_item(row["item"])
        if not item:
            return None, None, _error(
                "INVALID_ITEM",
                f"Item row {index} is not available to the authenticated user.",
            )
    resolved_company, failure = _resolve_company(request)
    if failure:
        return None, None, failure
    resolved_links, failure = _resolve_optional_links(request)
    if failure:
        return None, None, failure

    doc = frappe.new_doc("Sales Invoice")
    doc.customer = request["customer"]
    doc.company = resolved_company
    doc.is_pos = 0
    doc.is_return = 0
    doc.is_debit_note = 0
    doc.update_stock = 0
    if request.get("posting_date"):
        try:
            doc.posting_date = getdate(request["posting_date"])
        except Exception:
            return None, None, _error(
                "INVALID_SALES_INVOICE_DETAILS", "posting_date must be a valid date."
            )
    if request.get("selling_price_list"):
        if not _permitted_link("Price List", request["selling_price_list"]):
            return None, None, _error(
                "INVALID_SALES_INVOICE_DETAILS",
                "Selling price list is not available to the authenticated user.",
            )
        doc.selling_price_list = request["selling_price_list"]
    for fieldname, value in resolved_links.items():
        setattr(doc, fieldname, value)
    for request_row in request["items"]:
        row = {"item_code": request_row["item"], "qty": request_row["qty"]}
        if "rate" in request_row:
            row["rate"] = request_row["rate"]
        doc.append("items", row)

    # These are the audited non-persisting native defaults/calculation seams.
    # Full Sales Invoice validation is intentionally deferred to final insert.
    doc.set_missing_values()
    doc.calculate_taxes_and_totals()
    try:
        # ERPNext owns the SO/DN prerequisite rule. Calling this narrow native
        # seam avoids the broader validation hooks during non-persisting prepare.
        doc.so_dn_required()
    except frappe.ValidationError as error:
        # Keep the public response stable without exposing native traceback/text.
        native_message = str(error)
        if "Sales Order" in native_message:
            return None, None, _blocked(["Sales Order"])
        if "Delivery Note" in native_message:
            return None, None, _blocked(["Delivery Note"])
        return None, None, _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected the Sales Invoice during preparation.",
        )
    preview = _preview(doc)
    missing_defaults = [
        fieldname for fieldname in _REQUIRED_DEFAULTS if not preview.get(fieldname)
    ]
    if missing_defaults:
        return None, None, _needs_input(
            missing_defaults,
            "ERPNext could not determine all required Sales Invoice defaults.",
        )
    return doc, preview, None


def prepare_sales_invoice(
    customer: dict[str, str] | None,
    items: list[dict[str, Any]] | None,
    company: str | None = None,
    posting_date: str | None = None,
    selling_price_list: str | None = None,
    customer_address: str | None = None,
    shipping_address_name: str | None = None,
    contact_person: str | None = None,
) -> dict[str, Any]:
    """Prepare a native Draft Sales Invoice without persisting it."""
    approvals.prune_expired()
    user = _current_user()
    if not frappe.has_permission("Sales Invoice", "create"):
        return _permission_denied()
    request, failure = _normalise_request(
        customer,
        items,
        company,
        posting_date,
        selling_price_list,
        customer_address,
        shipping_address_name,
        contact_person,
    )
    if failure:
        return failure
    assert request is not None
    doc, preview, failure = _build(request)
    if failure:
        return failure
    assert doc is not None and preview is not None
    token = approvals.create(
        action=_ACTION,
        site=getattr(frappe.local, "site", ""),
        user=user,
        payload={
            "doctype": "Sales Invoice",
            "request": request,
            "preview": preview,
            "fingerprint": _fingerprint(request, preview),
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
        "The effective Sales Invoice changed after the preview was prepared. Please prepare it again.",
    )


def confirm_sales_invoice(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Rebuild and insert the reviewed Draft Sales Invoice after approval."""
    user = _current_user()
    site = getattr(frappe.local, "site", "")
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=site, user=user)
        return _error(
            "CONFIRMATION_REQUIRED",
            "Review the Sales Invoice preview before confirming it.",
        )

    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Sales Invoice")
        return _error(code, message, retryable=retryable)
    if not frappe.has_permission("Sales Invoice", "create"):
        return _permission_denied()

    payload = approval.payload
    request = payload.get("request")
    approved_preview = payload.get("preview")
    approved_fingerprint = payload.get("fingerprint")
    if (
        payload.get("doctype") != "Sales Invoice"
        or not isinstance(request, dict)
        or not isinstance(approved_preview, dict)
        or not isinstance(approved_fingerprint, str)
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE",
            "This Sales Invoice confirmation is not available in the current session.",
        )

    doc, preview, failure = _build(request)
    if failure:
        if failure.get("status") == "blocked":
            return failure
        return _stale()
    assert doc is not None and preview is not None
    if _fingerprint(request, preview) != approved_fingerprint:
        return _stale()

    try:
        doc.insert(
            ignore_permissions=False,
            ignore_links=False,
            ignore_mandatory=False,
        )
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _permission_denied()
    except frappe.ValidationError:
        frappe.db.rollback()
        return _error(
            "NATIVE_VALIDATION_FAILED",
            "ERPNext rejected the Sales Invoice during final validation.",
        )
    except Exception:
        frappe.db.rollback()
        return _error(
            "SALES_INVOICE_CREATION_FAILED",
            "ERPNext could not create the Sales Invoice.",
        )

    return {
        "status": "created",
        "doctype": "Sales Invoice",
        "sales_invoice": _value(doc, "name"),
        "docstatus": int(_value(doc, "docstatus", 0) or 0),
        "customer": _value(doc, "customer"),
        "company": _value(doc, "company"),
        "currency": _value(doc, "currency"),
        "grand_total": _value(doc, "grand_total"),
        "idempotent": False,
    }
