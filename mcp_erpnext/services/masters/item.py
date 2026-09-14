"""Permission-aware, two-phase sales Item operations for approved workflows."""

from __future__ import annotations

from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...config.masters import item as item_config
from ...observability import new_error_reference
from ..common.creation_contract import missing_input_response, resolve_creation_contract
from ..common.entity_resolution import (
    find_candidates,
    normalize,
    resolve_ranked_candidates,
)
from ..common.effective_requirements import (
    EffectiveRequirementContext,
    RequirementResult,
    RequirementStatus,
    run_effective_requirements,
)
from ..common.field_value_resolver import resolve_contract_values, resolve_field_value
from ..integrations.india_compliance_item import india_compliance_item_preflight

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


def _candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Expose an ambiguity candidate only through a reusable typed reference."""
    return {
        "reference": _reference(candidate),
        "label": candidate.get("label") or candidate.get("value"),
        "score": candidate.get("score", 0.0),
    }


def _search_items(query: str, filters: dict[str, Any]) -> dict[str, Any]:
    candidates = find_candidates(
        "Item",
        query,
        filters,
        item_config.SEARCH_FIELDS,
        item_config.DISPLAY_FIELDS,
    )
    classification = _classify_item_candidates(query, candidates)
    if classification["status"] == "not_found":
        candidates = []
    return {
        "status": classification["status"],
        "doctype": "Item",
        "query": query,
        "candidates": [_candidate(candidate) for candidate in candidates],
    }


def _resolve_item(query: str, filters: dict[str, Any]) -> dict[str, Any]:
    candidates = find_candidates(
        "Item",
        query,
        filters,
        item_config.SEARCH_FIELDS,
        item_config.DISPLAY_FIELDS,
    )
    return _classify_item_candidates(query, candidates)


def _classify_item_candidates(query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep weak related Items out of the explicit-selection state.

    The shared resolver remains authoritative for exact matches, strong spelling
    corrections, and credible ambiguity. Item-only weak candidates are treated
    as discovery noise so a missing Item can reach controlled creation.
    """
    result = resolve_ranked_candidates(query, candidates)
    if result["status"] == "ambiguous" and candidates:
        normalized_query = normalize(query)
        exact = [
            candidate
            for candidate in candidates
            if normalized_query
            in {normalize(candidate.get("value")), normalize(candidate.get("label"))}
        ]
        if len(exact) > 1:
            return result
        if max(candidate.get("score", 0.0) for candidate in candidates) < item_config.MIN_CREDIBLE_AMBIGUITY_SCORE:
            return {"status": "not_found", "query": query, "candidates": []}
    return result


def search_items(query: str) -> dict[str, Any]:
    """Search sales-enabled Items through the shared resolver implementation."""
    return _search_items(query, item_config.SEARCH_FILTERS)


def search_purchase_items(query: str) -> dict[str, Any]:
    """Search purchase-enabled Items without duplicating resolver behavior."""
    return _search_items(query, item_config.PURCHASE_SEARCH_FILTERS)


def resolve_sales_item(query: str) -> dict[str, Any]:
    return _resolve_item(query, item_config.SEARCH_FILTERS)


def resolve_purchase_item(query: str) -> dict[str, Any]:
    return _resolve_item(query, item_config.PURCHASE_SEARCH_FILTERS)


def resolve_item_for_workflow(query: str) -> dict[str, Any]:
    """Return one terminal public resolution state for sales-Item lookup."""
    resolution = resolve_sales_item(query)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "doctype": "Item",
            "reference": _reference(resolution["candidate"]),
            "match_type": resolution.get("match_type"),
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "ambiguous",
            "doctype": "Item",
            "query": query,
            "candidates": [
                _candidate(candidate) for candidate in resolution.get("candidates", [])
            ],
        }
    return {"status": "not_found", "doctype": "Item", "query": query, "candidates": []}


def resolve_purchase_item_for_workflow(query: str) -> dict[str, Any]:
    """Return purchase-enabled Item resolution in the same public shape."""
    resolution = resolve_purchase_item(query)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "doctype": "Item",
            "reference": _reference(resolution["candidate"]),
            "match_type": resolution.get("match_type"),
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "ambiguous",
            "doctype": "Item",
            "query": query,
            "candidates": [_candidate(candidate) for candidate in resolution.get("candidates", [])],
        }
    return {"status": "not_found", "doctype": "Item", "query": query, "candidates": []}


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
    data = {"doctype": "Item", **resolved_fields["values"]}

    runtime_requirements = run_effective_requirements(
        EffectiveRequirementContext(
            doctype="Item",
            site=getattr(frappe.local, "site", ""),
            values=data,
            input_values=item,
            fields=contract["fields"],
            get_installed_apps=getattr(frappe, "get_installed_apps", lambda: []),
            get_cached_value=getattr(frappe, "get_cached_value", None),
            get_meta=frappe.get_meta,
            get_list=frappe.get_list,
        ),
        (india_compliance_item_preflight,),
    )
    if runtime_requirements.status in {
        RequirementStatus.MISSING,
        RequirementStatus.INVALID,
        RequirementStatus.UNAVAILABLE,
    }:
        return None, _runtime_requirement_response(runtime_requirements)

    for fieldname, value in runtime_requirements.values.items():
        field_result = resolve_field_value(
            fieldname=fieldname,
            field=contract["fields"].get(fieldname),
            path_prefix="item",
            value=value,
            source="runtime_requirement",
            resolved_values=data,
            link_filters={},
            get_list=frappe.get_list,
        )
        if field_result["status"] != "resolved":
            return None, field_result
        data[fieldname] = field_result["value"]
    return data, None


def _runtime_requirement_response(result: RequirementResult) -> dict[str, Any]:
    """Map internal provider outcomes to the frozen legacy Item result shape."""
    if result.status in {RequirementStatus.MISSING, RequirementStatus.INVALID}:
        requirement = result.requirement
        assert requirement is not None
        path = f"item.{requirement.fieldname}"
        return {
            "status": "needs_input",
            "missing": [path],
            "missing_fields": [
                {
                    "doctype": requirement.doctype,
                    "fieldname": requirement.fieldname,
                    "path": path,
                    "label": requirement.label,
                    "fieldtype": "Link",
                    "reason": requirement.reason,
                    "source": "runtime_requirement",
                }
            ],
            "message": requirement.guidance,
        }
    return _confirmation_error(
        "ITEM_RUNTIME_REQUIREMENT_UNAVAILABLE",
        "Item creation requirements could not be safely determined. Ask an authorized administrator or support team to check the site configuration.",
        retryable=True,
    )


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
        "custom_slug": data.get("custom_slug"),
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
    user = _current_user()
    if not confirm:
        approvals.cancel(
            approval_token, action=_ACTION, site=frappe.local.site, user=user
        )
        return _confirmation_error(
            "CONFIRMATION_REQUIRED",
            "Review the Item preview before confirming it.",
            retryable=False,
        )
    approval, state = approvals.claim_for_confirm_write(
        approval_token, action=_ACTION, site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Item")
        return _confirmation_error(code, message, retryable=retryable)
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
