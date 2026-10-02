"""Permission-aware Payment Terms Template selection and native application."""

from __future__ import annotations

from typing import Any

import frappe

from ...config.business_defaults import (
    BusinessDefaultKey,
    BusinessDefaultsConfigurationError,
    get_document_business_default,
)
from ...public_errors import defined_error
from ..common.entity_resolution import (
    find_candidates,
    rank_candidates,
    resolve_ranked_candidates,
)

PAYMENT_TERMS_SEARCH_FILTERS: dict[str, Any] = {}
PAYMENT_TERMS_SEARCH_FIELDS = ("name", "template_name")
PAYMENT_TERMS_DISPLAY_FIELDS = ("template_name",)
PAYMENT_TERMS_TYPO_FALLBACK_SCAN_LIMIT = 100


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _permitted_template(name: str, frappe_module: Any) -> bool:
    return bool(
        frappe_module.get_list(
            "Payment Terms Template",
            filters={"name": name},
            fields=["name"],
            limit_page_length=1,
            ignore_permissions=False,
        )
    )


def _reference(candidate: dict[str, Any]) -> dict[str, str | None]:
    return {
        "doctype": "Payment Terms Template",
        "name": candidate.get("value"),
        "template_name": candidate.get("template_name") or candidate.get("label"),
    }


def _candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference": _reference(candidate),
        "label": candidate.get("label") or candidate.get("value"),
        "score": candidate.get("score", 0.0),
    }


def _fallback_candidates(query: str, get_list: Any) -> list[dict[str, Any]]:
    rows = get_list(
        "Payment Terms Template",
        filters=PAYMENT_TERMS_SEARCH_FILTERS,
        fields=["name", "template_name"],
        order_by="name asc",
        limit_page_length=PAYMENT_TERMS_TYPO_FALLBACK_SCAN_LIMIT,
        ignore_permissions=False,
    )
    displayed = [
        {
            "value": row.get("name"),
            "label": row.get("template_name") or row.get("name"),
            **(
                {"template_name": row.get("template_name")}
                if row.get("template_name")
                else {}
            ),
        }
        for row in rows
    ]
    return rank_candidates(query, displayed, ("value", "template_name"))


def resolve_payment_terms_template(
    query: str, *, get_list: Any = None
) -> dict[str, Any]:
    """Resolve one permission-visible Payment Terms Template."""
    permitted_get_list = get_list or frappe.get_list
    candidates = find_candidates(
        "Payment Terms Template",
        query,
        PAYMENT_TERMS_SEARCH_FILTERS,
        PAYMENT_TERMS_SEARCH_FIELDS,
        PAYMENT_TERMS_DISPLAY_FIELDS,
        get_list=permitted_get_list,
    )
    if not candidates:
        candidates = _fallback_candidates(query, permitted_get_list)

    resolution = resolve_ranked_candidates(query, candidates)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "doctype": "Payment Terms Template",
            "reference": _reference(resolution["candidate"]),
            "match_type": resolution["match_type"],
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "ambiguous",
            "doctype": "Payment Terms Template",
            "query": query,
            "candidates": [
                _candidate(candidate) for candidate in resolution.get("candidates", [])
            ],
        }
    return {
        "status": "not_found",
        "doctype": "Payment Terms Template",
        "query": query,
        "candidates": [],
    }


def apply_payment_terms_template(
    doc: Any,
    explicit_template: str | None,
    *,
    frappe_module: Any = frappe,
) -> dict[str, Any] | None:
    """Apply an explicit/configured template before ERPNext party defaulting."""
    template = explicit_template
    configured = False
    if template is None:
        try:
            template = get_document_business_default(
                doc.doctype,
                BusinessDefaultKey.PAYMENT_TERMS_TEMPLATE,
                doc.company,
                frappe_module=frappe_module,
            )
        except BusinessDefaultsConfigurationError:
            return _error(
                "INVALID_BUSINESS_DEFAULTS",
            )
        configured = template is not None

    if template is None:
        return None
    if not isinstance(template, str) or not template.strip():
        return _error(
            "INVALID_PAYMENT_TERMS_TEMPLATE",
        )
    template = template.strip()
    if not _permitted_template(template, frappe_module):
        source = "configured " if configured else ""
        return _error(
            "INVALID_PAYMENT_TERMS_TEMPLATE",
        )
    doc.payment_terms_template = template
    return None


def set_native_payment_schedule(doc: Any) -> dict[str, Any] | None:
    """Generate the effective schedule through ERPNext's installed controller."""
    try:
        doc.set_payment_schedule()
    except Exception:
        return _error(
            "PAYMENT_SCHEDULE_UNAVAILABLE",
        )
    return None
