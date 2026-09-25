"""Small native ERPNext adapter for Selling Terms during non-Desk preparation."""

from __future__ import annotations

from typing import Any

import frappe

from ...observability import new_error_reference


def _error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "code": code, "message": message, "reference": new_error_reference(), "retryable": False}


def _permitted_terms(name: str, frappe_module: Any) -> bool:
    return bool(
        frappe_module.get_list(
            "Terms and Conditions", filters={"name": name}, fields=["name"],
            limit_page_length=1, ignore_permissions=False,
        )
    )


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
