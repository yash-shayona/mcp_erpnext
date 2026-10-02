"""Small native ERPNext adapter for Selling Terms during non-Desk preparation."""

from __future__ import annotations

from typing import Any

import frappe

from ...config.business_defaults import (
    BusinessDefaultKey,
    BusinessDefaultsConfigurationError,
    get_document_business_default,
)
from ...observability import new_error_reference
from ..common.terms_resolution import TERMS_TYPO_FALLBACK_SCAN_LIMIT, resolve_terms

TERMS_SEARCH_FILTERS = {"selling": 1, "disabled": 0}
TERMS_SEARCH_FIELDS = ("name", "title")
TERMS_DISPLAY_FIELDS = ("title",)


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": False,
    }


def _permitted_terms(name: str, frappe_module: Any) -> bool:
    return bool(
        frappe_module.get_list(
            "Terms and Conditions",
            filters={"name": name, **TERMS_SEARCH_FILTERS},
            fields=["name"],
            limit_page_length=1,
            ignore_permissions=False,
        )
    )


def resolve_terms_and_conditions(query: str, *, get_list: Any = None) -> dict[str, Any]:
    """Resolve one enabled, permission-visible Selling Terms template."""
    return resolve_terms(query, filters=TERMS_SEARCH_FILTERS, get_list=get_list or frappe.get_list)


def apply_selling_terms(
    doc: Any, explicit_tc_name: str | None, *, frappe_module: Any = frappe
) -> dict[str, Any] | None:
    """Apply explicit/configured/native Selling Terms, then render natively."""
    configured_tc_name = None
    if explicit_tc_name is None:
        try:
            configured_tc_name = get_document_business_default(
                doc.doctype,
                BusinessDefaultKey.TERMS_AND_CONDITIONS_TEMPLATE,
                doc.company,
                frappe_module=frappe_module,
            )
        except BusinessDefaultsConfigurationError:
            return _error(
                "INVALID_BUSINESS_DEFAULTS",
                "The site's document business-default configuration is invalid.",
            )

    selected_tc_name = explicit_tc_name or configured_tc_name
    if selected_tc_name is not None:
        if not isinstance(selected_tc_name, str) or not selected_tc_name.strip():
            return _error(
                "INVALID_TERMS", "Terms and conditions must be an exact non-empty name."
            )
        tc_name = selected_tc_name.strip()
        if not _permitted_terms(tc_name, frappe_module):
            source = "configured " if configured_tc_name is not None else ""
            return _error(
                "INVALID_TERMS",
                f"The {source}Terms and Conditions template is not available to the authenticated user.",
            )
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
            return _error(
                "TERMS_UNAVAILABLE",
                "ERPNext could not render the selected Terms and Conditions.",
            )
    return None
