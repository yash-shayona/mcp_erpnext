"""Safe, two-phase Sales Order service for the controlled MCP capability."""

from __future__ import annotations

import math
from typing import Any

import frappe
from frappe.utils import getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...observability import new_error_reference
from ...public_errors import defined_error
from ..common.fingerprint import stable_fingerprint
from ..common.write_policy import approval_entry_failure, current_mode, direct_entry_failure, disabled_failure, exact_mode_failure
from ...settings import WriteMode
from ..masters.customer import resolve_customer
from ..masters.item import resolve_sales_item
from .payment_terms import apply_payment_terms_template, set_native_payment_schedule
from .terms import apply_selling_terms

_ACTION = "create_sales_order"


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required for Sales Order creation.",
            frappe.PermissionError,
        )
    return user


def _resolve_company(company: str | None) -> str | None:
    """Use only an explicit or permission-visible default Company."""
    resolved = company or frappe.defaults.get_user_default("Company")
    if not resolved:
        return None
    if not frappe.get_list(
        "Company",
        filters={"name": resolved},
        fields=["name"],
        limit_page_length=1,
        ignore_permissions=False,
    ):
        frappe.throw(
            f"Company {resolved} was not found or is not permitted.",
            frappe.PermissionError,
        )
    return resolved


def _set_sales_order_delivery_date(doc: Any, delivery_date: Any = None) -> bool:
    """Apply the standalone Sales Order delivery-date default before validation."""
    transaction_date = getdate(doc.transaction_date)
    resolved_delivery_date = getdate(
        delivery_date or doc.get("delivery_date") or transaction_date
    )
    if resolved_delivery_date < transaction_date:
        return False
    doc.delivery_date = resolved_delivery_date
    return True


def _coerce_quantity(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        frappe.throw("Item quantity must be a positive number.", frappe.ValidationError)
    try:
        quantity = float(value)
    except (TypeError, ValueError) as exc:
        raise frappe.ValidationError(
            "Item quantity must be a positive number."
        ) from exc
    if not math.isfinite(quantity) or quantity <= 0:
        frappe.throw("Item quantity must be a positive number.", frappe.ValidationError)
    return quantity


def _prepare_items(items: Any) -> dict[str, Any]:
    if not isinstance(items, list) or not items:
        return {"status": "needs_input", "missing": ["items"], "items": []}

    resolved_items: list[dict[str, Any]] = []
    missing_quantities: list[dict[str, Any]] = []
    for index, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, dict):
            return defined_error(
                "INVALID_ORDER_DETAILS",
            )
        query = (
            raw_item.get("item")
            or raw_item.get("item_code")
            or raw_item.get("item_name")
        )
        if not query:
            return {
                "status": "needs_input",
                "missing": [f"items[{index}].item"],
                "items": [],
            }

        resolution = resolve_sales_item(str(query))
        if resolution["status"] != "resolved":
            return {
                "status": resolution["status"],
                "field": f"items[{index}].item",
                "query": query,
                "candidates": resolution.get("candidates", []),
            }
        quantity = _coerce_quantity(raw_item.get("qty", raw_item.get("quantity")))
        if quantity is None:
            missing_quantities.append(
                {
                    "index": index,
                    "item_code": resolution["candidate"]["value"],
                    "item_name": resolution["candidate"].get("item_name"),
                }
            )
        prepared_item = {
            "item_code": resolution["candidate"]["value"],
            "item_name": resolution["candidate"].get("item_name"),
            "qty": quantity,
            "match_type": resolution.get("match_type"),
        }
        if "description" in raw_item and raw_item["description"] is not None:
            if not isinstance(raw_item["description"], str):
                return defined_error(
                    "INVALID_ORDER_DETAILS",
                )
            prepared_item["description"] = raw_item["description"]
        resolved_items.append(prepared_item)

    if missing_quantities:
        return {
            "status": "needs_input",
            "missing_quantities": missing_quantities,
            "items": resolved_items,
        }
    return {"status": "resolved", "items": resolved_items}


def _safe_doc_data(doc: Any) -> dict[str, Any]:
    """Keep only JSON-safe data required to create the reviewed Draft later."""
    data = doc.as_dict()
    for field in ("__islocal", "owner", "creation", "modified", "modified_by"):
        data.pop(field, None)
    return data


def _preview(doc: Any) -> dict[str, Any]:
    return {
        "customer": doc.customer,
        "customer_name": doc.customer_name,
        "company": doc.company,
        "order_type": doc.order_type,
        "transaction_date": str(doc.transaction_date),
        "delivery_date": str(doc.delivery_date),
        "currency": doc.currency,
        "selling_price_list": doc.selling_price_list,
        "items": [
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "description": row.description,
                "qty": row.qty,
                "uom": row.uom,
                "rate": row.rate,
                "amount": row.amount,
                "warehouse": row.warehouse,
                "delivery_date": str(row.delivery_date) if row.delivery_date else None,
            }
            for row in doc.items
        ],
        "grand_total": doc.grand_total,
        "tc_name": doc.get("tc_name"),
        "terms": doc.get("terms"),
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
        "custom_remarks": doc.get("custom_remarks"),
    }


def prepare_sales_order(
    customer: str,
    items: list[dict[str, Any]],
    company: str | None = None,
    delivery_date: str | None = None,
    selling_price_list: str | None = None,
    tc_name: str | None = None,
    payment_terms_template: str | None = None,
    custom_remarks: str | None = None,
    *,
    _create_approval: bool = True,
) -> dict[str, Any]:
    """Resolve inputs and return a preview without writing a Sales Order."""
    if failure := disabled_failure("create"):
        return _confirmation_error(failure.code, retryable=False)
    if current_mode("create") is WriteMode.APPROVAL_REQUIRED and _create_approval:
        approvals.prune_expired()
    user = _current_user()
    request = {
        "customer": customer,
        "items": items,
        "company": company,
        "delivery_date": delivery_date,
        "selling_price_list": selling_price_list,
        "tc_name": tc_name,
        "payment_terms_template": payment_terms_template,
        "custom_remarks": custom_remarks,
    }
    if not customer or not str(customer).strip():
        return {"status": "needs_input", "missing": ["customer"]}

    customer_resolution = resolve_customer(customer)
    if customer_resolution["status"] != "resolved":
        return {
            "status": customer_resolution["status"],
            "field": "customer",
            "query": customer,
            "candidates": customer_resolution.get("candidates", []),
        }
    item_result = _prepare_items(items)
    if item_result["status"] != "resolved":
        return item_result

    resolved_company = _resolve_company(company)
    if not resolved_company:
        return {
            "status": "needs_input",
            "missing": ["company"],
            "message": "No default Company is configured for the authenticated service user.",
        }
    transaction_date = getdate(nowdate())

    doc = frappe.new_doc("Sales Order")
    doc.customer = customer_resolution["candidate"]["value"]
    doc.company = resolved_company
    doc.order_type = "Sales"
    doc.transaction_date = transaction_date
    if not _set_sales_order_delivery_date(doc, delivery_date):
        return defined_error(
            "INVALID_ORDER_DETAILS",
        )
    if selling_price_list:
        doc.selling_price_list = selling_price_list
    for item in item_result["items"]:
        row = {"item_code": item["item_code"], "qty": item["qty"]}
        if "description" in item:
            row["description"] = item["description"]
        doc.append("items", row)
    if custom_remarks is not None:
        if not frappe.get_meta("Sales Order").has_field("custom_remarks"):
            return defined_error(
                "CUSTOM_REMARKS_UNAVAILABLE",
            )
        doc.custom_remarks = custom_remarks

    if failure := apply_payment_terms_template(
        doc, payment_terms_template, frappe_module=frappe
    ):
        return failure

    doc.set_missing_values()
    for prepared_item, row in zip(item_result["items"], doc.items, strict=True):
        if "description" in prepared_item:
            row.description = prepared_item["description"]
    if failure := apply_selling_terms(doc, tc_name, frappe_module=frappe):
        return failure
    missing_defaults = [
        field
        for field in (
            "selling_price_list",
            "price_list_currency",
            "currency",
            "conversion_rate",
            "plc_conversion_rate",
        )
        if not doc.get(field)
    ]
    if missing_defaults:
        return {
            "status": "needs_input",
            "missing": missing_defaults,
            "message": "ERPNext could not determine all commercial defaults for this order.",
        }
    doc.calculate_taxes_and_totals()
    if failure := set_native_payment_schedule(doc):
        return failure
    doc.run_method("validate")
    if not doc.selling_price_list:
        return {
            "status": "needs_input",
            "missing": ["selling_price_list"],
            "message": "ERPNext could not determine a selling price list for this customer.",
        }

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
        "corrections": {
            "customer": customer_resolution.get("match_type") == "spelling_correction",
            "items": [
                item["match_type"]
                for item in item_result["items"]
                if item.get("match_type")
            ],
        },
        "preview": preview,
    }


def _confirmation_error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def confirm_sales_order(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Create the reviewed Draft only for the original site, user, and action."""
    if failure := approval_entry_failure("create"):
        return _confirmation_error(failure.code, retryable=False)
    user = _current_user()
    if not confirm:
        approvals.cancel(
            approval_token, action=_ACTION, site=frappe.local.site, user=user
        )
        return {
            "status": "confirmation_required",
            "code": "CONFIRMATION_REQUIRED",
            "message": "Review the Sales Order preview before confirming it.",
            "reference": new_error_reference(),
            "retryable": False,
        }
    approval, state = approvals.claim_for_confirm_write(
        approval_token,
        action=_ACTION,
        site=frappe.local.site,
        user=user,
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Sales Order")
        return _confirmation_error(code, retryable=retryable)
    if not frappe.has_permission("Sales Order", "create"):
        return _confirmation_error(
            "PERMISSION_DENIED",
            retryable=False,
        )

    payload = approval.payload
    request = payload.get("_mcp_request")
    approved_preview = payload.get("_mcp_preview")
    approved_fingerprint = payload.get("_mcp_fingerprint")
    approved_document_fingerprint = payload.get("_mcp_document_fingerprint")
    document = {
        key: value for key, value in payload.items() if not key.startswith("_mcp_")
    }
    if (
        payload.get("doctype") != "Sales Order"
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
        return _confirmation_error(
            "CONFIRMATION_UNAVAILABLE",
            retryable=False,
        )

    rebuilt = prepare_sales_order(**request, _create_approval=False)
    if rebuilt.get("status") != "ready" or "_doc" not in rebuilt:
        return _confirmation_error(
            "STALE_CONFIRMATION",
            retryable=False,
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
        return _confirmation_error(
            "STALE_CONFIRMATION",
            retryable=False,
        )

    try:
        if failure := exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED):
            return _confirmation_error(failure.code, retryable=False)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        raise
    except Exception:
        frappe.db.rollback()
        raise
    return {"status": "created", "sales_order": doc.name, "docstatus": doc.docstatus}


def execute_sales_order(**request: Any) -> dict[str, Any]:
    """Create a Sales Order using fresh planning and the direct policy path."""
    if failure := direct_entry_failure("create"):
        return _confirmation_error(failure.code, retryable=False)
    planned = prepare_sales_order(**request, _create_approval=False)
    if planned.get("status") != "ready" or "_doc" not in planned:
        return planned
    doc = planned["_doc"]
    try:
        if failure := exact_mode_failure("create", WriteMode.DIRECT):
            return _confirmation_error(failure.code, retryable=False)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    return {"status": "created", "sales_order": doc.name, "docstatus": doc.docstatus}
