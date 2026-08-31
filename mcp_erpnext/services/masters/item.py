"""Permission-aware, two-phase sales Item operations for approved workflows."""

from __future__ import annotations

from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals
from ...config.masters import item as item_config
from ...observability import new_error_reference
from ..common.creation_contract import missing_input_response, resolve_creation_contract
from ..common.entity_resolution import find_candidates, resolve_candidate, search_status
from ..common.field_value_resolver import resolve_contract_values

_ACTION = "create_item"


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required for Item creation.",
            frappe.PermissionError,
        )
    return user


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _confirmation_error(code: str, message: str, *, retryable: bool) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": retryable,
    }


def _reference(candidate: dict[str, Any]) -> dict[str, str | None]:
    """Return only the Item identity a future deterministic workflow needs."""
    return {
        "doctype": "Item",
        "name": candidate.get("value"),
        "item_code": candidate.get("item_code") or candidate.get("value"),
        "item_name": candidate.get("item_name") or candidate.get("label"),
        "stock_uom": candidate.get("stock_uom"),
    }


def search_items(query: str) -> dict[str, Any]:
    candidates = find_candidates(
        "Item",
        query,
        item_config.SEARCH_FILTERS,
        item_config.SEARCH_FIELDS,
        item_config.DISPLAY_FIELDS,
    )
    return {
        "status": search_status(query, candidates),
        "doctype": "Item",
        "query": query,
        "candidates": candidates,
    }


def resolve_sales_item(query: str) -> dict[str, Any]:
    return resolve_candidate(
        "Item",
        query,
        item_config.SEARCH_FILTERS,
        item_config.SEARCH_FIELDS,
        item_config.DISPLAY_FIELDS,
    )


def resolve_item_for_workflow(query: str) -> dict[str, Any]:
    """Translate the existing sales-Item lookup into a parent-workflow contract."""
    resolution = resolve_sales_item(query)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "item": _reference(resolution["candidate"]),
            "match_type": resolution.get("match_type"),
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "needs_selection",
            "query": query,
            "candidates": resolution.get("candidates", []),
        }
    return {"status": "needs_item_creation", "query": query, "candidates": []}


def _item_data(item: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Map the intentionally narrow, non-pricing Item creation contract."""
    if not isinstance(item, dict):
        return None, _confirmation_error(
            "INVALID_ITEM_DETAILS", "Item details must be an object.", retryable=False
        )

    provided = {
        fieldname: item[fieldname]
        for fieldname in item_config.CREATION_FIELDS
        if fieldname != "is_sales_item"
        and fieldname in item
        and item[fieldname] not in (None, "")
    }

    contract = resolve_creation_contract(
        doctype="Item",
        input_values=provided,
        creation_fields=item_config.CREATION_FIELDS,
        policy_values=item_config.POLICY_VALUES,
        path_prefix="item",
        get_meta=frappe.get_meta,
        new_document=frappe.new_doc,
    )
    if contract["missing"]:
        return None, missing_input_response(contract)
    resolved_fields = resolve_contract_values(
        contract=contract,
        creation_fields=item_config.CREATION_FIELDS,
        path_prefix="item",
        reference_filters=item_config.REFERENCE_FILTERS,
        get_list=frappe.get_list,
    )
    if resolved_fields["status"] != "resolved":
        return None, resolved_fields
    return {"doctype": "Item", **resolved_fields["values"]}, None


def _duplicate_matches(item_code: str) -> list[dict[str, Any]]:
    """Find visible Item-code duplicates; disabled Items still block a unique code."""
    rows = frappe.get_list(
        "Item",
        filters={"item_code": item_code},
        fields=["name", "item_code", "item_name", "stock_uom", "disabled"],
        limit_page_length=10,
        ignore_permissions=False,
    )
    if not rows:
        return []
    return [
        {
            "identifier": "item_code",
            "candidates": [
                {
                    "value": row.get("name"),
                    "label": row.get("item_name")
                    or row.get("item_code")
                    or row.get("name"),
                    "item_code": row.get("item_code"),
                    "item_name": row.get("item_name"),
                    "stock_uom": row.get("stock_uom"),
                    "disabled": row.get("disabled"),
                }
                for row in rows
            ],
        }
    ]


def _permission_denied() -> dict[str, Any]:
    return {
        "status": "permission_denied",
        "missing_permissions": ["Item"],
        "message": "The authenticated user cannot create Items.",
    }


def _preview(data: dict[str, Any]) -> dict[str, Any]:
    """Never surface price, valuation, accounting, or tax information here."""
    return {
        "item_code": data["item_code"],
        "item_name": data.get("item_name") or data["item_code"],
        "item_group": data["item_group"],
        "stock_uom": data["stock_uom"],
        "is_stock_item": data.get("is_stock_item"),
        "is_sales_item": True,
    }


def prepare_item(item: dict[str, Any]) -> dict[str, Any]:
    """Validate a new sales Item and issue a private confirmation token without a write."""
    approvals.prune_expired()
    _current_user()
    data, failure = _item_data(item)
    if failure:
        return failure
    assert data is not None
    if not frappe.has_permission("Item", "create"):
        return _permission_denied()
    if duplicates := _duplicate_matches(data["item_code"]):
        return {"status": "duplicate_suspected", "duplicates": duplicates}

    # Item.validate can update derived Item Group defaults on certain sites.  Keep
    # preparation side-effect-free; Frappe runs the complete document validation
    # during the normal, permission-enforced insert after confirmation.
    token = approvals.create(
        action=_ACTION, site=frappe.local.site, user=_current_user(), payload=data
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": _preview(data),
    }


def confirm_item(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Create the prepared Item only for the original site and authenticated user."""
    approvals.prune_expired()
    if not confirm:
        return _confirmation_error(
            "CONFIRMATION_REQUIRED",
            "Review the Item preview before confirming it.",
            retryable=False,
        )
    approval, state = approvals.lookup(
        approval_token, action=_ACTION, site=frappe.local.site, user=_current_user()
    )
    if state == "expired":
        return _confirmation_error(
            "CONFIRMATION_EXPIRED",
            "This Item confirmation has expired. Please prepare it again.",
            retryable=True,
        )
    if state == "unavailable" or approval is None:
        return _confirmation_error(
            "CONFIRMATION_UNAVAILABLE",
            "This Item confirmation is not available in the current session.",
            retryable=False,
        )
    if approval.result_document:
        return {
            "status": "created",
            "item": {
                "doctype": "Item",
                "name": approval.result_document,
                "item_code": approval.payload["item_code"],
                "item_name": approval.payload.get("item_name")
                or approval.payload["item_code"],
                "stock_uom": approval.payload["stock_uom"],
            },
            "idempotent": True,
        }
    if not frappe.has_permission("Item", "create"):
        return _permission_denied()
    if duplicates := _duplicate_matches(approval.payload["item_code"]):
        return {"status": "duplicate_suspected", "duplicates": duplicates}

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
    approval.result_document = doc.name
    return {
        "status": "created",
        "item": {
            "doctype": "Item",
            "name": doc.name,
            "item_code": doc.item_code,
            "item_name": doc.item_name,
            "stock_uom": doc.stock_uom,
        },
        "idempotent": False,
    }
