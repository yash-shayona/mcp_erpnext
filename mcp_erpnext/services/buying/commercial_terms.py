"""Bounded PO commercial selection, native refresh, and approval snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ...config.business_defaults import (
    BusinessDefaultKey,
    BusinessDefaultsConfigurationError,
    get_document_business_default,
)
from ...contracts.interaction import input_directive
from ...public_errors import defined_error
from ..selling.payment_terms import apply_payment_terms_template
from .terms import BUYING_TERMS_FILTERS

COMMERCIAL_FIELDS = frozenset({"tc_name", "payment_terms_template"})
SCHEDULE_PREVIEW_FIELDS = (
    "payment_term", "description", "due_date", "invoice_portion", "payment_amount",
    "base_payment_amount", "discount_type", "discount", "discount_date", "mode_of_payment",
)


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _needs_template(field: str) -> dict[str, Any]:
    return {
        "status": "needs_input", "missing": [field],
        "message": "The selected or configured template is unavailable. Resolve a permitted template explicitly or have the operator correct the site default.",
        "interaction": input_directive().model_dump(mode="json"),
    }


def validate_choice(field: str, value: Any, *, frappe_module: Any) -> dict[str, Any] | None:
    """Accept an exact permission-visible template name, or an explicit clear."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 140:
        return _error("INVALID_COMMERCIAL_TEMPLATE")
    doctype = "Terms and Conditions" if field == "tc_name" else "Payment Terms Template"
    filters = BUYING_TERMS_FILTERS if field == "tc_name" else {}
    if not frappe_module.get_list(
        doctype, filters={"name": value, **filters}, fields=["name"],
        limit_page_length=1, ignore_permissions=False,
    ):
        return _needs_template(field)
    return None


def apply_creation_choices(doc: Any, tc_name: str | None, payment_template: str | None, *, frappe_module: Any) -> dict[str, Any] | None:
    """Explicit > configured company/site > native; no new required defaults."""
    selected = tc_name
    if selected is None:
        try:
            selected = get_document_business_default(
                "Purchase Order", BusinessDefaultKey.TERMS_AND_CONDITIONS_TEMPLATE,
                doc.company, frappe_module=frappe_module,
            )
        except BusinessDefaultsConfigurationError:
            return _error("INVALID_BUSINESS_DEFAULTS")
        if selected is None:
            selected = doc.get("tc_name") or getattr(frappe_module, "get_value", lambda *_: None)(
                "Company", doc.company, "default_buying_terms"
            ) or None
    if selected is not None:
        if selected == "":
            return _error("INVALID_COMMERCIAL_TEMPLATE")
        failure = validate_choice("tc_name", selected, frappe_module=frappe_module)
        if failure:
            return failure
        doc.tc_name = selected
        # A native new-document default must not retain a different template's body.
        doc.terms = ""
    if payment_template is not None:
        if not isinstance(payment_template, str) or not payment_template.strip() or len(payment_template) > 140:
            return _error("INVALID_COMMERCIAL_TEMPLATE")
    # This existing helper has no Selling policy: only site/DocType config and read permission.
    failure = apply_payment_terms_template(doc, payment_template, frappe_module=frappe_module)
    if failure and failure.get("code") == "INVALID_PAYMENT_TERMS_TEMPLATE":
        return _needs_template("payment_terms_template")
    return failure


def template_snapshot(doc: Any, *, frappe_module: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Recheck eligibility and bind native master versions without exposing bodies."""
    snapshot = {}
    for field, doctype in (("tc_name", "Terms and Conditions"), ("payment_terms_template", "Payment Terms Template")):
        name = doc.get(field)
        if not name:
            continue
        failure = validate_choice(field, name, frappe_module=frappe_module)
        if failure:
            return {}, failure
        filters = BUYING_TERMS_FILTERS if field == "tc_name" else {}
        rows = frappe_module.get_list(
            doctype, filters={"name": name, **filters}, fields=["name", "modified"],
            limit_page_length=1, ignore_permissions=False,
        )
        if not rows:
            return {}, _needs_template(field)
        snapshot[field] = {"name": name, "modified": str(rows[0].get("modified"))}
    return snapshot, None


def commercial_preview(doc: Any) -> dict[str, Any]:
    return {
        "tc_name": doc.get("tc_name") or None,
        "terms": doc.get("terms") or None,
        "payment_terms_template": doc.get("payment_terms_template") or None,
        "payment_schedule": [
            {field: (str(row.get(field)) if field in {"due_date", "discount_date"} and row.get(field) else row.get(field))
             for field in SCHEDULE_PREVIEW_FIELDS}
            for row in (doc.get("payment_schedule") or [])
        ],
    }


def commercial_fingerprint(doc: Any) -> str:
    state = commercial_preview(doc)
    # Totals/currency and date determine the meaning of the reviewed schedule.
    state.update({field: doc.get(field) for field in (
        "currency", "conversion_rate", "transaction_date", "grand_total", "base_grand_total",
        "rounded_total", "base_rounded_total",
    )})
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def refresh_commercial(doc: Any, *, terms_changed: bool, payment_changed: bool) -> None:
    """Rebuild only the explicitly selected native commercial state in memory."""
    # Buying defaults must not resurrect an explicitly cleared payment template.
    doc.ignore_default_payment_terms_template = 1
    if terms_changed:
        doc.terms = ""
    if payment_changed:
        doc.set("payment_schedule", [])
    doc.set_missing_values()
    doc.calculate_taxes_and_totals()
    doc.set_missing_terms()
    doc.set_payment_schedule()
    doc.run_method("validate")


def stale_commercial() -> dict[str, Any]:
    return _error("STALE_CONFIRMATION")
