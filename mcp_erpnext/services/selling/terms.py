"""Small native ERPNext adapter for Selling Terms during non-Desk preparation."""

from __future__ import annotations

from typing import Any

import frappe

from ...observability import new_error_reference
from ..common.entity_resolution import (
    find_candidates,
    rank_candidates,
    resolve_ranked_candidates,
)

TERMS_SEARCH_FILTERS = {"selling": 1, "disabled": 0}
TERMS_SEARCH_FIELDS = ("name", "title")
TERMS_DISPLAY_FIELDS = ("title",)
# The typo fallback is deliberately bounded: it ranks at most this many
# permission-visible Selling templates when token/LIKE discovery finds none.
TERMS_TYPO_FALLBACK_SCAN_LIMIT = 100


def _error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "code": code, "message": message, "reference": new_error_reference(), "retryable": False}


def _permitted_terms(name: str, frappe_module: Any) -> bool:
    return bool(
        frappe_module.get_list(
            "Terms and Conditions", filters={"name": name}, fields=["name"],
            limit_page_length=1, ignore_permissions=False,
        )
    )


def _reference(candidate: dict[str, Any]) -> dict[str, str | None]:
    return {
        "doctype": "Terms and Conditions",
        "name": candidate.get("value"),
        "title": candidate.get("title") or candidate.get("label"),
    }


def _candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference": _reference(candidate),
        "label": candidate.get("label") or candidate.get("value"),
        "score": candidate.get("score", 0.0),
    }


def _fallback_candidates(query: str, get_list: Any) -> list[dict[str, Any]]:
    """Rank a bounded safe scan after all normal search tokens miss."""
    rows = get_list(
        "Terms and Conditions",
        filters=TERMS_SEARCH_FILTERS,
        fields=["name", "title"],
        order_by="name asc",
        limit_page_length=TERMS_TYPO_FALLBACK_SCAN_LIMIT,
        ignore_permissions=False,
    )
    displayed = [
        {
            "value": row.get("name"),
            "label": row.get("title") or row.get("name"),
            **({"title": row.get("title")} if row.get("title") else {}),
        }
        for row in rows
    ]
    return rank_candidates(query, displayed, ("value", "title"))


def resolve_terms_and_conditions(query: str, *, get_list: Any = None) -> dict[str, Any]:
    """Resolve one enabled, permission-visible Selling Terms template."""
    permitted_get_list = get_list or frappe.get_list
    candidates = find_candidates(
        "Terms and Conditions",
        query,
        TERMS_SEARCH_FILTERS,
        TERMS_SEARCH_FIELDS,
        TERMS_DISPLAY_FIELDS,
        get_list=permitted_get_list,
    )
    if not candidates:
        candidates = _fallback_candidates(query, permitted_get_list)

    resolution = resolve_ranked_candidates(query, candidates)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "doctype": "Terms and Conditions",
            "reference": _reference(resolution["candidate"]),
            "match_type": resolution["match_type"],
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "ambiguous",
            "doctype": "Terms and Conditions",
            "query": query,
            "candidates": [
                _candidate(candidate) for candidate in resolution.get("candidates", [])
            ],
        }
    return {
        "status": "not_found",
        "doctype": "Terms and Conditions",
        "query": query,
        "candidates": [],
    }


def apply_selling_terms(
    doc: Any, explicit_tc_name: str | None, *, frappe_module: Any = frappe
) -> dict[str, Any] | None:
    """Apply exact input or the native Company default, then render natively."""
    if explicit_tc_name is not None:
        if not isinstance(explicit_tc_name, str) or not explicit_tc_name.strip():
            return _error("INVALID_TERMS", "Terms and conditions must be an exact non-empty name.")
        tc_name = explicit_tc_name.strip()
        if not _permitted_terms(tc_name, frappe_module):
            return _error("INVALID_TERMS", "Terms and conditions are not available to the authenticated user.")
        doc.tc_name = tc_name
    elif not doc.get("tc_name"):
        # This intentionally mirrors SellingController.onload's source field.
        default_terms = getattr(frappe_module, "get_value", lambda *_: None)(
            "Company", doc.company, "default_selling_terms"
        )
        if default_terms:
            doc.tc_name = default_terms

    if doc.get("tc_name") and not doc.get("terms"):
        try:
            doc.set_missing_terms()
        except Exception:
            return _error("TERMS_UNAVAILABLE", "ERPNext could not render the selected Terms and Conditions.")
    return None
