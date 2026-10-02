"""Shared, exact-target lifecycle service for the configured MCP profiles."""

from __future__ import annotations

import math
import hashlib
import json
from copy import deepcopy
from typing import Any

import frappe
from frappe.model.delete_doc import get_dynamic_linked_docs, get_linked_docs
from frappe.utils import flt, get_datetime, getdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import logged_defined_error, new_error_reference
from ...public_errors import defined_error
from ...settings import WriteMode
from ..selling.payment_terms import set_native_payment_schedule
from ..selling.terms import apply_selling_terms
from ..buying.commercial_terms import (
    COMMERCIAL_FIELDS,
    commercial_fingerprint,
    commercial_preview,
    refresh_commercial,
    stale_commercial,
    template_snapshot,
    validate_choice,
)
from .write_policy import current_mode, disabled_failure, policy_failure

PROFILE_DOCTYPES = {
    "sales": frozenset({"Quotation", "Sales Order", "Customer", "Item"}),
    "purchase": frozenset({"Purchase Order", "Supplier", "Item"}),
    "accounts": frozenset(),
}
PROFILE_DOCTYPES["all"] = PROFILE_DOCTYPES["sales"] | PROFILE_DOCTYPES["purchase"]

# The legacy profile sets remain the baseline for already-supported doctypes.
SALES_INVOICE_MUTATION_DOCTYPES = frozenset({"Sales Invoice"})
LIFECYCLE_ACTION_DOCTYPES = {
    "sales": {
        "update": PROFILE_DOCTYPES["sales"] | SALES_INVOICE_MUTATION_DOCTYPES,
        "child_add": PROFILE_DOCTYPES["sales"] | SALES_INVOICE_MUTATION_DOCTYPES,
        "child_remove": frozenset({"Quotation", "Sales Order", "Sales Invoice"}),
        "submit": PROFILE_DOCTYPES["sales"]
        | frozenset({"Sales Invoice", "Delivery Note"}),
        "cancel": PROFILE_DOCTYPES["sales"]
        | frozenset({"Sales Invoice", "Delivery Note"}),
        "delete": PROFILE_DOCTYPES["sales"]
        | frozenset({"Sales Invoice", "Delivery Note"}),
    },
    "purchase": {
        "update": PROFILE_DOCTYPES["purchase"],
        "child_add": PROFILE_DOCTYPES["purchase"],
        "child_remove": frozenset({"Purchase Order"}),
        "submit": PROFILE_DOCTYPES["purchase"],
        "cancel": PROFILE_DOCTYPES["purchase"],
        "delete": PROFILE_DOCTYPES["purchase"],
    },
    "accounts": {
        "update": frozenset(),
        "child_add": frozenset(),
        "child_remove": frozenset(),
        "submit": frozenset({"Payment Entry"}),
        "cancel": frozenset({"Payment Entry"}),
        "delete": frozenset({"Payment Entry"}),
    },
}
LIFECYCLE_ACTION_DOCTYPES["all"] = {
    action: (
        LIFECYCLE_ACTION_DOCTYPES["sales"][action]
        | LIFECYCLE_ACTION_DOCTYPES["purchase"][action]
        | LIFECYCLE_ACTION_DOCTYPES["accounts"][action]
    )
    for action in ("update", "child_add", "child_remove", "submit", "cancel", "delete")
}


CHILD_ADD_TARGETS = {
    "sales": {
        "Quotation": ("items", "Quotation Item"),
        "Sales Order": ("items", "Sales Order Item"),
        "Sales Invoice": ("items", "Sales Invoice Item"),
    },
    "purchase": {"Purchase Order": ("items", "Purchase Order Item")},
}
CHILD_ADD_TARGETS["all"] = {
    **CHILD_ADD_TARGETS["sales"],
    **CHILD_ADD_TARGETS["purchase"],
}

CHILD_REMOVE_TARGETS = {
    "sales": {
        "Quotation": ("items", "Quotation Item"),
        "Sales Order": ("items", "Sales Order Item"),
        "Sales Invoice": ("items", "Sales Invoice Item"),
    },
    "purchase": {"Purchase Order": ("items", "Purchase Order Item")},
}
CHILD_REMOVE_TARGETS["all"] = {
    **CHILD_REMOVE_TARGETS["sales"],
    **CHILD_REMOVE_TARGETS["purchase"],
}
PURCHASE_ORDER_PARENT_UPDATE_FIELDS = frozenset(
    {
        "schedule_date",
        "supplier_address",
        "contact_person",
        "shipping_address",
        "project",
        "cost_center",
    }
)
SALES_INVOICE_PARENT_UPDATE_FIELDS = frozenset(
    {
        "remarks",
        "custom_remarks",
        "po_no",
        "po_date",
        "customer_address",
        "shipping_address_name",
        "contact_person",
        "tc_name",
        "payment_terms_template",
    }
)
SALES_INVOICE_ITEM_UPDATE_FIELDS = frozenset({"qty", "rate", "description"})

_SYSTEM_FIELDS = frozenset(
    {
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
        "parent",
        "parenttype",
        "parentfield",
    }
)


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _lifecycle_policy_failure(action: str) -> dict[str, Any] | None:
    """Return a stable denial unless current process policy enables the action."""
    failure = disabled_failure(action)
    return _error(failure.code, failure.message) if failure else None


def _write_mode(action: str) -> WriteMode:
    return current_mode(action)


def _direct_policy_failure(action: str) -> dict[str, Any] | None:
    failure = policy_failure(action, WriteMode.DIRECT)
    return _error(failure.code, failure.message) if failure else None


def _confirm_policy_failure(action: str) -> dict[str, Any] | None:
    failure = policy_failure(action, WriteMode.APPROVAL_REQUIRED)
    return _error(failure.code, failure.message) if failure else None


def _exact_write_mode_failure(
    action: str, expected: WriteMode
) -> dict[str, Any] | None:
    """Require the authorization path's mode at the native-write boundary."""
    failure = policy_failure(action, expected)
    return _error(failure.code, failure.message) if failure else None


def _cancel_delete_mode_failure(expected: WriteMode) -> dict[str, Any] | None:
    """Require Delete and its internal Cancel stage to use one exact mode."""
    return _exact_write_mode_failure("cancel", expected)


def is_action_allowed(profile: str, doctype: str, action: str) -> bool:
    """Return whether a profile may address a doctype for one lifecycle action."""
    return doctype in LIFECYCLE_ACTION_DOCTYPES.get(profile, {}).get(
        action, frozenset()
    )


def _target(
    target: dict[str, Any], profile: str, action: str | None = None
) -> tuple[str, str] | dict[str, Any]:
    doctype = target.get("doctype") if isinstance(target, dict) else None
    name = target.get("name") if isinstance(target, dict) else None
    if (
        not isinstance(doctype, str)
        or not doctype.strip()
        or not isinstance(name, str)
        or not name.strip()
    ):
        return _error(
            "INVALID_TARGET", "An exact document doctype and name are required."
        )
    allowed = (
        PROFILE_DOCTYPES.get(profile, frozenset())
        if action is None
        else LIFECYCLE_ACTION_DOCTYPES.get(profile, {}).get(action, frozenset())
    )
    if doctype not in allowed:
        return _error(
            "DOCTYPE_NOT_ALLOWED",
            f"{doctype} is not available in the {profile} MCP profile.",
        )
    return doctype, name.strip()


def _load(
    target: dict[str, Any],
    profile: str,
    permission: str = "read",
    action: str | None = None,
) -> tuple[Any, dict[str, Any] | None]:
    resolved = _target(target, profile, action)
    if isinstance(resolved, dict):
        return None, resolved
    doctype, name = resolved
    try:
        doc = frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None, _error("DOCUMENT_NOT_FOUND", f"{doctype} {name} was not found.")
    if not doc.has_permission(permission):
        return None, _error(
            "PERMISSION_DENIED",
            f"The authenticated user cannot {permission} {doctype} {name}.",
        )
    return doc, None


def _status(doc: Any) -> str:
    return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(
        int(doc.docstatus), str(doc.docstatus)
    )


def _json(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    return value


def _find_child(doc: Any, change: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
    table = change.get("child_table")
    selector = change.get("row") or {}
    if (
        not table
        or not doc.meta.has_field(table)
        or doc.meta.get_field(table).fieldtype != "Table"
    ):
        return None, _error(
            "INVALID_CHILD_TARGET",
            f"{table or 'Child table'} is not a child table on {doc.doctype}.",
        )
    matches = []
    for row in doc.get(table) or []:
        if selector.get("row_name") and row.name == selector["row_name"]:
            matches.append(row)
        elif (
            selector.get("item_code") and row.get("item_code") == selector["item_code"]
        ):
            matches.append(row)
        elif selector.get("idx") is not None and int(row.idx or 0) == selector["idx"]:
            matches.append(row)
    if len(matches) != 1:
        return None, _error(
            "AMBIGUOUS_CHILD_TARGET" if matches else "CHILD_ROW_NOT_FOUND",
            "The child-row selector did not identify exactly one row.",
        )
    return matches[0], None


def _validate_change(
    doc: Any, change: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    fieldname = change.get("field")
    if doc.doctype == "Purchase Order":
        if change.get("child_table") or fieldname not in (
            PURCHASE_ORDER_PARENT_UPDATE_FIELDS | COMMERCIAL_FIELDS
        ):
            return None, _error(
                "FIELD_NOT_WRITABLE",
                "This Purchase Order field is not available for MCP update.",
            )
    if doc.doctype == "Purchase Order" and fieldname in COMMERCIAL_FIELDS:
        failure = validate_choice(fieldname, change.get("value"), frappe_module=frappe)
        if failure:
            return None, failure
    if doc.doctype == "Sales Invoice":
        if change.get("child_table"):
            if (
                change["child_table"] != "items"
                or fieldname not in SALES_INVOICE_ITEM_UPDATE_FIELDS
            ):
                return None, _error(
                    "FIELD_NOT_WRITABLE",
                    "Only Sales Invoice item qty, rate, and description can be updated.",
                )
        elif fieldname not in SALES_INVOICE_PARENT_UPDATE_FIELDS:
            return None, _error(
                "FIELD_NOT_WRITABLE",
                "This Sales Invoice field is not available for MCP update.",
            )
    if fieldname in _SYSTEM_FIELDS:
        return None, _error(
            "FIELD_NOT_WRITABLE",
            f"{fieldname} is controlled by Frappe and cannot be updated directly.",
        )
    if not isinstance(fieldname, str):
        return None, _error("INVALID_FIELD", "Each change requires a field name.")
    if change.get("child_table"):
        row, failure = _find_child(doc, change)
        if failure:
            return None, failure
        meta = frappe.get_meta(row.doctype).get_field(fieldname) if row else None
        current = row.get(fieldname) if row else None
        path = f"{change['child_table']}[{row.name}].{fieldname}"
    else:
        meta = doc.meta.get_field(fieldname)
        current = doc.get(fieldname)
        path = fieldname
    if meta is None or meta.fieldname in _SYSTEM_FIELDS or meta.read_only:
        return None, _error("FIELD_NOT_WRITABLE", f"{path} is not a writable field.")
    if meta.fieldtype in {"Table", "Section Break", "Column Break", "HTML", "Button"}:
        return None, _error(
            "FIELD_NOT_WRITABLE", f"{path} cannot be updated as a scalar field."
        )
    value = change.get("value")
    if (
        meta.fieldtype == "Select"
        and value not in (None, "")
        and str(value) not in (meta.options or "").split("\n")
    ):
        return None, _error(
            "INVALID_FIELD_VALUE", f"{path} has an invalid Select value."
        )
    if meta.fieldtype == "Link" and value not in (None, ""):
        if not frappe.get_list(
            meta.options,
            filters={"name": value},
            fields=["name"],
            limit_page_length=1,
            ignore_permissions=False,
        ):
            return None, _error(
                "INVALID_LINK", f"{path} does not reference a permitted {meta.options}."
            )
    return {
        "path": path,
        "field": fieldname,
        "child_table": change.get("child_table"),
        "row_name": row.name if change.get("child_table") and row else None,
        "old": _json(current),
        "new": _json(value),
        "input": deepcopy(change),
    }, None


def _refresh_sales_invoice(
    doc: Any,
    *,
    terms_changed: bool = False,
    schedule_changed: bool = False,
    total_changed: bool = False,
    had_manual_schedule: bool = False,
) -> dict[str, Any] | None:
    """Apply only audited, non-persisting Sales Invoice controller seams."""
    if schedule_changed and had_manual_schedule:
        return _error(
            "PAYMENT_SCHEDULE_UNAVAILABLE",
            "A manual Payment Schedule cannot be replaced through this update.",
        )
    if hasattr(doc, "set_missing_values"):
        doc.set_missing_values()
    if terms_changed:
        doc.terms = ""
        failure = apply_selling_terms(doc, doc.get("tc_name"), frappe_module=frappe)
        if failure:
            return failure
    if hasattr(doc, "calculate_taxes_and_totals"):
        doc.calculate_taxes_and_totals()
    if schedule_changed:
        doc.set("payment_schedule", [])
    if schedule_changed or (total_changed and doc.get("payment_terms_template")):
        failure = set_native_payment_schedule(doc)
        if failure:
            return failure
    elif total_changed and doc.get("payment_schedule"):
        return _error(
            "PAYMENT_SCHEDULE_UNAVAILABLE",
            "A manual Payment Schedule cannot be safely preserved after this item change.",
        )
    return None


def _refresh_purchase_order(doc: Any) -> None:
    """Run ERPNext Buying defaults, totals, and controller validation in memory."""
    doc.ignore_default_payment_terms_template = 1
    if hasattr(doc, "set_missing_values"):
        doc.set_missing_values()
    if hasattr(doc, "calculate_taxes_and_totals"):
        doc.calculate_taxes_and_totals()
    if hasattr(doc, "run_method"):
        doc.run_method("validate")


def _base_preview(doc: Any, action: str) -> dict[str, Any]:
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "status": _status(doc),
        "docstatus": int(doc.docstatus),
        "action": action,
    }


def _payment_entry_submit_state(doc: Any) -> tuple[dict[str, Any], str]:
    """Build a bounded, fresh outstanding snapshot for Payment Entry submit approval."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import (
        get_outstanding_reference_documents,
    )

    references = list(doc.get("references") or [])
    vouchers = [
        frappe._dict(voucher_type=row.reference_doctype, voucher_no=row.reference_name)
        for row in references
        if row.reference_doctype and row.reference_name
    ]
    latest = (
        get_outstanding_reference_documents(
            {
                "posting_date": doc.posting_date,
                "company": doc.company,
                "party_type": doc.party_type,
                "payment_type": doc.payment_type,
                "party": doc.party,
                "party_account": (
                    doc.paid_from if doc.payment_type == "Receive" else doc.paid_to
                ),
                "get_outstanding_invoices": True,
                "get_orders_to_be_billed": True,
                "vouchers": vouchers,
                "book_advance_payments_in_separate_party_account": doc.book_advance_payments_in_separate_party_account,
            },
            validate=True,
        )
        or []
    )
    latest_by_key = {
        (row.voucher_type, row.voucher_no, row.get("payment_term")): flt(
            row.outstanding_amount
        )
        for row in latest
    }
    projected = []
    for row in references:
        key = (row.reference_doctype, row.reference_name, row.payment_term)
        projected.append(
            {
                "reference_doctype": row.reference_doctype,
                "reference_name": row.reference_name,
                "payment_term": row.payment_term,
                "current_outstanding": latest_by_key.get(key),
                "allocated_amount": flt(row.allocated_amount),
            }
        )
    preview = {
        "payment_entry": doc.name,
        "customer": doc.party,
        "company": doc.company,
        "payment_type": doc.payment_type,
        "posting_date": _json(doc.posting_date),
        "destination": doc.mode_of_payment
        or doc.bank_account
        or (doc.paid_to if doc.payment_type == "Receive" else doc.paid_from),
        "party_currency": (
            doc.paid_from_account_currency
            if doc.payment_type == "Receive"
            else doc.paid_to_account_currency
        ),
        "destination_currency": (
            doc.paid_to_account_currency
            if doc.payment_type == "Receive"
            else doc.paid_from_account_currency
        ),
        "paid_amount": flt(doc.paid_amount),
        "received_amount": flt(doc.received_amount),
        "references": projected,
        "total_allocated_amount": flt(doc.total_allocated_amount),
        "unallocated_amount": flt(doc.unallocated_amount),
        "difference_amount": flt(doc.difference_amount),
        "deductions": [
            {"account": row.account, "amount": flt(row.amount)}
            for row in (doc.get("deductions") or [])
        ],
        "taxes": [
            {"account": row.account_head, "amount": flt(row.tax_amount)}
            for row in (doc.get("taxes") or [])
        ],
        "warning": "Submitting creates native ledger entries and changes every referenced invoice outstanding amount.",
    }
    fingerprint = hashlib.sha256(
        json.dumps(preview, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return preview, fingerprint


def _create(
    action: str,
    doc: Any,
    profile: str,
    payload: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
    if (
        action in {"update", "child_add", "child_remove", "cancel", "delete"}
        and _write_mode(action) is WriteMode.DIRECT
    ):
        return {"status": "ready", "preview": preview}
    token = approvals.create(
        action=f"lifecycle_{action}",
        site=frappe.local.site,
        user=_user(),
        payload={
            **payload,
            "action": action,
            "doctype": doc.doctype,
            "name": doc.name,
            "profile": profile,
            "modified": str(doc.modified),
            "docstatus": int(doc.docstatus),
        },
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": preview,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def _plan_update(
    target: dict[str, Any],
    changes: list[dict[str, Any]],
    profile: str,
    *,
    copy_for_apply: bool = False,
) -> tuple[dict[str, Any] | None, Any | None, dict[str, Any] | None]:
    doc, failure = _load(target, profile, "write", "update")
    if failure:
        return None, None, failure
    if copy_for_apply:
        doc = deepcopy(doc)
    if doc.doctype in {"Sales Invoice", "Purchase Order"} and int(doc.docstatus) != 0:
        return (
            None,
            None,
            _error(
                "INVALID_DOCUMENT_STATE",
                f"{doc.doctype} {doc.name} is {_status(doc)} and cannot be updated.",
            ),
        )
    if doc.docstatus.is_cancelled():
        return (
            None,
            None,
            _error(
                "INVALID_DOCUMENT_STATE",
                f"{doc.doctype} {doc.name} is Cancelled and cannot be updated.",
            ),
        )
    validated = []
    commercial_payload = {}
    if doc.doctype == "Purchase Order":
        commercial_changes = [
            change["field"]
            for change in changes
            if change.get("field") in COMMERCIAL_FIELDS
        ]
        if len(commercial_changes) != len(set(commercial_changes)):
            return (
                None,
                None,
                _error(
                    "INVALID_FIELD_VALUE",
                    "Provide each commercial template change only once.",
                ),
            )
    for change in changes:
        item, failure = _validate_change(doc, change)
        if failure:
            return None, None, failure
        validated.append(item)
    if doc.doctype == "Sales Invoice":
        had_manual_schedule = bool(
            doc.get("payment_schedule") and not doc.get("payment_terms_template")
        )
        for item in validated:
            if item["child_table"]:
                row, _ = _find_child(doc, item["input"])
                row.set(item["field"], item["new"])
            else:
                doc.set(item["field"], item["new"])
        failure = _refresh_sales_invoice(
            doc,
            terms_changed=any(item["field"] == "tc_name" for item in validated),
            schedule_changed=any(
                item["field"] == "payment_terms_template" for item in validated
            ),
            total_changed=any(
                item["child_table"] and item["field"] in {"qty", "rate"}
                for item in validated
            ),
            had_manual_schedule=had_manual_schedule,
        )
        if failure:
            return None, None, failure
    elif doc.doctype == "Purchase Order":
        for item in validated:
            doc.set(item["field"], item["new"])
        try:
            if commercial_changes:
                templates, failure = template_snapshot(doc, frappe_module=frappe)
                if failure:
                    return None, None, failure
                refresh_commercial(
                    doc,
                    terms_changed="tc_name" in commercial_changes,
                    payment_changed="payment_terms_template" in commercial_changes,
                )
                commercial_payload = {
                    "commercial": {
                        "templates": templates,
                        "fingerprint": commercial_fingerprint(doc),
                    }
                }
            else:
                _refresh_purchase_order(doc)
        except Exception as error:
            if commercial_changes:
                return (
                    None,
                    None,
                    logged_defined_error(
                        "prepare_document_update",
                        "LIFECYCLE_VALIDATION_FAILED",
                        level="exception",
                    ),
                )
            return (
                None,
                None,
                logged_defined_error(
                    "prepare_document_update",
                    "LIFECYCLE_VALIDATION_FAILED",
                    level="exception",
                ),
            )
    preview = {
        **_base_preview(doc, "UPDATE"),
        "changes": [
            {key: item[key] for key in ("path", "old", "new")} for item in validated
        ],
    }
    if commercial_payload:
        preview["commercial_terms"] = commercial_preview(doc)
    return (
        {
            "action": "update",
            "doctype": doc.doctype,
            "name": doc.name,
            "profile": profile,
            "changes": validated,
            **commercial_payload,
        },
        doc,
        preview,
    )


def prepare_update(
    target: dict[str, Any], changes: list[dict[str, Any]], profile: str
) -> dict[str, Any]:
    policy_failure = _lifecycle_policy_failure("update")
    if policy_failure:
        return policy_failure
    payload, doc, preview = _plan_update(target, changes, profile)
    if doc is None:
        return preview
    return _create("update", doc, profile, payload, preview)


def _child_add_target(doc: Any, profile: str) -> tuple[Any, Any] | dict[str, Any]:
    configured = CHILD_ADD_TARGETS.get(profile, {}).get(doc.doctype)
    if not configured:
        return _error(
            "CHILD_TARGET_NOT_ALLOWED",
            f"Adding item rows is not allowed for {doc.doctype} in the {profile} MCP profile.",
        )
    table, expected_doctype = configured
    field = doc.meta.get_field(table) if doc.meta.has_field(table) else None
    if not field or field.fieldtype != "Table" or field.options != expected_doctype:
        return _error(
            "INVALID_CHILD_TARGET",
            f"The approved items table is not valid on {doc.doctype}.",
        )
    return field, frappe.get_meta(expected_doctype)


def _child_remove_target(doc: Any, profile: str) -> tuple[Any, Any] | dict[str, Any]:
    configured = CHILD_REMOVE_TARGETS.get(profile, {}).get(doc.doctype)
    if not configured:
        return _error(
            "CHILD_TARGET_NOT_ALLOWED",
            "Removing rows is not allowed for this document.",
        )
    table, expected = configured
    field = doc.meta.get_field(table) if doc.meta.has_field(table) else None
    if not field or field.fieldtype != "Table" or field.options != expected:
        return _error(
            "INVALID_CHILD_TARGET",
            "The approved items table is not valid on this document.",
        )
    return field, frappe.get_meta(expected)


def _item_for_child_add(
    item: dict[str, Any], profile: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    name = item.get("name") if isinstance(item, dict) else None
    if not isinstance(name, str) or not name.strip():
        return None, _error("INVALID_ITEM", "A resolved Item reference is required.")
    filters = {
        "disabled": ["!=", 1],
        "is_purchase_item" if profile == "purchase" else "is_sales_item": 1,
    }
    rows = frappe.get_list(
        "Item",
        filters={"name": name.strip(), **filters},
        fields=["name", "item_code", "item_name", "stock_uom", "modified"],
        limit_page_length=1,
        ignore_permissions=False,
    )
    if not rows:
        return None, _error(
            "INVALID_ITEM",
            f"Item {name.strip()} is not available to the authenticated user.",
        )
    return rows[0], None


def _child_row_values(row: Any, meta: Any) -> dict[str, Any]:
    values = {}
    for field in getattr(meta, "fields", []):
        if field.fieldname in _SYSTEM_FIELDS or field.fieldtype in {
            "Section Break",
            "Column Break",
            "HTML",
            "Button",
            "Table",
        }:
            continue
        value = row.get(field.fieldname)
        if value not in (None, "", 0, 0.0, []):
            values[field.fieldname] = _json(value)
    return values


def _restore_child_row_types(values: dict[str, Any], meta: Any) -> dict[str, Any]:
    """Restore typed date values before passing an approval payload to Frappe."""
    restored = deepcopy(values)
    for field in getattr(meta, "fields", []):
        value = restored.get(field.fieldname)
        if value in (None, ""):
            continue
        if field.fieldtype == "Date":
            restored[field.fieldname] = getdate(value)
        elif field.fieldtype == "Datetime":
            restored[field.fieldname] = get_datetime(value)
    return restored


def _plan_child_add(
    target: dict[str, Any],
    item: dict[str, Any],
    qty: Any,
    rate: Any,
    profile: str,
    *,
    copy_for_apply: bool = False,
) -> tuple[dict[str, Any] | None, Any | None, dict[str, Any] | None]:
    doc, failure = _load(target, profile, "write", "child_add")
    if failure:
        return None, None, failure
    if copy_for_apply:
        doc = deepcopy(doc)
    if int(doc.docstatus) != 0:
        return (
            None,
            None,
            _error(
                "INVALID_DOCUMENT_STATE",
                f"{doc.doctype} {doc.name} is {_status(doc)} and cannot receive a new item row.",
            ),
        )
    configured = _child_add_target(doc, profile)
    if isinstance(configured, dict):
        return None, None, configured
    field, child_meta = configured
    item_record, failure = _item_for_child_add(item, profile)
    if failure:
        return None, None, failure
    if (
        isinstance(qty, bool)
        or not isinstance(qty, (int, float))
        or not math.isfinite(qty)
        or qty <= 0
    ):
        return (
            None,
            None,
            _error("INVALID_ITEM_DETAILS", "Item quantity must be greater than zero."),
        )
    if rate is not None and (
        isinstance(rate, bool)
        or not isinstance(rate, (int, float))
        or not math.isfinite(rate)
        or rate < 0
    ):
        return (
            None,
            None,
            _error("INVALID_ITEM_DETAILS", "Item rate must be zero or greater."),
        )
    item_code = item_record["name"]
    duplicates = [
        row
        for row in doc.get(field.fieldname) or []
        if row.get("item_code") == item_code
    ]
    if duplicates:
        return (
            None,
            None,
            _error(
                "DUPLICATE_ITEM_ROW",
                f"Item {item_code} already exists in {doc.doctype} {doc.name}; no new row was prepared.",
            ),
        )
    row = {"item_code": item_code, "qty": qty}
    if rate is not None:
        row["rate"] = rate
    try:
        new_row = doc.append(field.fieldname, row)
        if doc.doctype == "Sales Invoice":
            failure = _refresh_sales_invoice(doc, total_changed=True)
            if failure:
                return None, None, failure
        elif doc.doctype == "Purchase Order":
            _refresh_purchase_order(doc)
        else:
            if hasattr(doc, "set_missing_values"):
                doc.set_missing_values()
            if hasattr(doc, "calculate_taxes_and_totals"):
                doc.calculate_taxes_and_totals()
            if hasattr(doc, "run_method"):
                doc.run_method("validate")
    except Exception as error:
        return (
            None,
            None,
            logged_defined_error(
                "prepare_child_add", "LIFECYCLE_VALIDATION_FAILED", level="exception"
            ),
        )
    prepared_row = _child_row_values(new_row, child_meta)
    preview = {
        **_base_preview(doc, "ADD_ITEM"),
        "new_row": prepared_row,
        "message": "This will add a new item row.",
    }
    return (
        {
            "action": "child_add",
            "doctype": doc.doctype,
            "name": doc.name,
            "profile": profile,
            "child_table": field.fieldname,
            "child_doctype": getattr(child_meta, "name", field.options),
            "row": prepared_row,
            "item_code": item_code,
            **(
                {"item_modified": item_record.get("modified")}
                if doc.doctype == "Purchase Order"
                else {}
            ),
        },
        doc,
        preview,
    )


def prepare_child_add(
    target: dict[str, Any], item: dict[str, Any], qty: Any, rate: Any, profile: str
) -> dict[str, Any]:
    policy_failure = _lifecycle_policy_failure("update")
    if policy_failure:
        return policy_failure
    payload, doc, preview = _plan_child_add(target, item, qty, rate, profile)
    if doc is None:
        return preview
    return _create("child_add", doc, profile, payload, preview)


def _row_preview(row: Any) -> dict[str, Any]:
    return {
        "row_name": row.name,
        "idx": int(row.idx or 0),
        "item_code": row.get("item_code"),
        "item_name": row.get("item_name"),
        "qty": _json(row.get("qty")),
        "rate": _json(row.get("rate")),
        "amount": _json(row.get("amount")),
    }


def _plan_child_remove(
    target: dict[str, Any],
    child_table: str,
    row: dict[str, Any],
    profile: str,
    *,
    copy_for_apply: bool = False,
) -> tuple[dict[str, Any] | None, Any | None, dict[str, Any] | None]:
    doc, failure = _load(target, profile, "write", "child_remove")
    if failure:
        return None, None, failure
    if copy_for_apply:
        doc = deepcopy(doc)
    if int(doc.docstatus) != 0:
        return (
            None,
            None,
            _error(
                "INVALID_DOCUMENT_STATE",
                f"{doc.doctype} {doc.name} is {_status(doc)} and cannot have an item row removed.",
            ),
        )
    configured = _child_remove_target(doc, profile)
    if isinstance(configured, dict):
        return None, None, configured
    field, _ = configured
    if child_table != field.fieldname:
        return (
            None,
            None,
            _error(
                "CHILD_TARGET_NOT_ALLOWED",
                "This child table cannot be removed through MCP.",
            ),
        )
    selected, failure = _find_child(doc, {"child_table": child_table, "row": row})
    if failure:
        return None, None, failure
    preview_row = _row_preview(selected)
    doc.remove(selected)
    if doc.doctype == "Sales Invoice":
        failure = _refresh_sales_invoice(doc, total_changed=True)
        if failure:
            return None, None, failure
    elif doc.doctype == "Purchase Order":
        try:
            _refresh_purchase_order(doc)
        except Exception as error:
            return (
                None,
                None,
                logged_defined_error(
                    "prepare_child_remove",
                    "LIFECYCLE_VALIDATION_FAILED",
                    level="exception",
                ),
            )
    elif hasattr(doc, "calculate_taxes_and_totals"):
        doc.calculate_taxes_and_totals()
    return (
        {
            "action": "child_remove",
            "doctype": doc.doctype,
            "name": doc.name,
            "profile": profile,
            "child_table": child_table,
            "row": preview_row,
        },
        doc,
        {
            **_base_preview(doc, "REMOVE_ITEM"),
            "removed_row": preview_row,
            "message": "This will remove the selected item row.",
        },
    )


def prepare_child_remove(
    target: dict[str, Any], child_table: str, row: dict[str, Any], profile: str
) -> dict[str, Any]:
    policy_failure = _lifecycle_policy_failure("update")
    if policy_failure:
        return policy_failure
    payload, doc, preview = _plan_child_remove(target, child_table, row, profile)
    if doc is None:
        return preview
    return _create("child_remove", doc, profile, payload, preview)


def _plan_action(
    action: str, target: dict[str, Any], profile: str
) -> tuple[dict[str, Any] | None, Any | None, dict[str, Any] | None]:
    if action in {"cancel", "delete"}:
        policy_failure = _lifecycle_policy_failure(action)
        if policy_failure:
            return None, None, policy_failure
    doc, failure = _load(target, profile, "read", action)
    if failure:
        return None, None, failure
    if action == "submit":
        if not doc.meta.is_submittable:
            return (
                None,
                None,
                _error(
                    "NOT_SUBMITTABLE", f"{doc.doctype} is not a submittable DocType."
                ),
            )
        if not doc.docstatus.is_draft():
            return (
                None,
                None,
                _error(
                    "INVALID_DOCUMENT_STATE",
                    f"{doc.doctype} {doc.name} is {_status(doc)} and cannot be submitted.",
                ),
            )
        permission = "submit"
    elif action == "cancel":
        if not doc.has_permission("cancel"):
            return (
                None,
                None,
                _error(
                    "PERMISSION_DENIED",
                    f"The authenticated user cannot cancel {doc.doctype} {doc.name}.",
                ),
            )
        if not doc.meta.is_submittable or not doc.docstatus.is_submitted():
            return (
                None,
                None,
                _error(
                    "INVALID_DOCUMENT_STATE",
                    f"{doc.doctype} {doc.name} must be Submitted before it can be cancelled.",
                ),
            )
        blockers = get_linked_docs(doc, method="Cancel") + get_dynamic_linked_docs(
            doc, method="Cancel"
        )
        if blockers:
            return None, None, _blocked(action, doc, blockers)
    else:
        if not doc.has_permission("delete"):
            return (
                None,
                None,
                _error(
                    "PERMISSION_DENIED",
                    f"The authenticated user cannot delete {doc.doctype} {doc.name}.",
                ),
            )
        if doc.meta.is_submittable and doc.docstatus.is_submitted():
            cancel_policy_failure = _lifecycle_policy_failure("cancel")
            if cancel_policy_failure:
                return None, None, cancel_policy_failure
            delete_mode = _write_mode("delete")
            cancel_mode_failure = _cancel_delete_mode_failure(delete_mode)
            if cancel_mode_failure:
                return None, None, cancel_mode_failure
            if not doc.has_permission("cancel"):
                return (
                    None,
                    None,
                    _error(
                        "PERMISSION_DENIED",
                        f"The authenticated user cannot cancel {doc.doctype} {doc.name} as part of deletion.",
                    ),
                )
            blockers = get_linked_docs(doc, method="Cancel") + get_dynamic_linked_docs(
                doc, method="Cancel"
            )
            if blockers:
                return None, None, _blocked(action, doc, blockers)
            delete_blockers = get_linked_docs(
                doc, method="Delete"
            ) + get_dynamic_linked_docs(doc, method="Delete")
            if delete_blockers:
                return None, None, _blocked(action, doc, delete_blockers)
            plan = "cancel_delete"
        else:
            plan = "delete"
            blockers = get_linked_docs(doc, method="Delete") + get_dynamic_linked_docs(
                doc, method="Delete"
            )
            if blockers:
                return None, None, _blocked(action, doc, blockers)
    if action == "submit" and not doc.has_permission(permission):
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
                f"The authenticated user cannot {permission} {doc.doctype} {doc.name}.",
            ),
        )
    preview = _base_preview(doc, action.upper())
    extra_payload: dict[str, Any] = {}
    if action == "submit" and doc.doctype == "Payment Entry":
        try:
            payment_preview, payment_fingerprint = _payment_entry_submit_state(doc)
        except Exception:
            return (
                None,
                None,
                _error(
                    "LIFECYCLE_VALIDATION_FAILED",
                    "ERPNext could not refresh Payment Entry references for submit review.",
                ),
            )
        preview["payment_entry_impact"] = payment_preview
        extra_payload["payment_entry_submit_fingerprint"] = payment_fingerprint
    if action == "delete" and plan == "cancel_delete":
        preview["plan"] = [
            f"Cancel {doc.doctype} {doc.name}",
            f"Delete {doc.doctype} {doc.name}",
        ]
    return (
        {
            "action": action,
            "doctype": doc.doctype,
            "name": doc.name,
            "profile": profile,
            "plan": locals().get("plan", action),
            **extra_payload,
        },
        doc,
        preview,
    )


def _blocked(action: str, doc: Any, blockers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "blocked",
        "code": "LINKED_DOCUMENT",
        "message": f"Cannot {action} {doc.doctype} {doc.name}; a linked document blocks this action.",
        "reference": new_error_reference(),
        "blockers": [
            {
                "doctype": item.get("reference_doctype"),
                "name": item.get("reference_docname"),
            }
            for item in blockers[:10]
        ],
        "preview": _base_preview(doc, action.upper()),
    }


def _revalidate(
    approval: Any, action: str, profile: str
) -> tuple[Any, dict[str, Any] | None]:
    if approval.payload.get("profile") != profile:
        return None, _error(
            "PROFILE_MISMATCH", "The prepared action belongs to another MCP profile."
        )
    if approval.payload.get("action") != action:
        return None, _error(
            "ACTION_MISMATCH", "The prepared action does not match this confirmation."
        )
    doc, failure = _load(
        {"doctype": approval.payload["doctype"], "name": approval.payload["name"]},
        profile,
        "read",
        action,
    )
    if failure:
        return None, failure
    if (
        str(doc.modified) != approval.payload["modified"]
        or int(doc.docstatus) != approval.payload["docstatus"]
    ):
        return None, _error(
            "STALE_CONFIRMATION",
            "The document changed after the preview was prepared. Please prepare the action again.",
        )
    if action == "submit" and doc.doctype == "Payment Entry":
        try:
            _, fingerprint = _payment_entry_submit_state(doc)
        except Exception:
            return None, _error(
                "STALE_CONFIRMATION",
                "Payment Entry reference state changed. Please prepare submit again.",
            )
        if fingerprint != approval.payload.get("payment_entry_submit_fingerprint"):
            return None, _error(
                "STALE_CONFIRMATION",
                "Payment Entry reference state changed. Please prepare submit again.",
            )
    return doc, None


def _apply_mutation(
    action: str, payload: dict[str, Any], doc: Any, profile: str
) -> dict[str, Any]:
    try:
        if action == "child_add":
            doc.check_permission("write")
            field_name = payload["child_table"]
            configured = _child_add_target(doc, profile)
            if isinstance(configured, dict) or configured[0].fieldname != field_name:
                return _error(
                    "CHILD_TARGET_NOT_ALLOWED",
                    "The prepared child-row target is no longer allowed.",
                )
            if doc.doctype == "Purchase Order":
                item_record, item_failure = _item_for_child_add(
                    {"name": payload["item_code"]}, profile
                )
                if item_failure:
                    return item_failure
                if item_record.get("modified") != payload.get("item_modified"):
                    return _error(
                        "STALE_CONFIRMATION",
                        "The Item changed after the preview was prepared. Please prepare the action again.",
                    )
            if any(
                row.get("item_code") == payload["item_code"]
                for row in doc.get(field_name) or []
            ):
                return _error(
                    "STALE_CONFIRMATION",
                    "The item already exists in the document. Please prepare the action again.",
                )
            _, child_meta = configured
            row_values = _restore_child_row_types(payload["row"], child_meta)
            doc.append(field_name, row_values)
            if doc.doctype == "Sales Invoice":
                failure = _refresh_sales_invoice(doc, total_changed=True)
                if failure:
                    frappe.db.rollback()
                    return failure
            elif doc.doctype == "Purchase Order":
                _refresh_purchase_order(doc)
            else:
                if hasattr(doc, "set_missing_values"):
                    doc.set_missing_values()
                if hasattr(doc, "calculate_taxes_and_totals"):
                    doc.calculate_taxes_and_totals()
            doc.save(ignore_permissions=False)
        elif action == "child_remove":
            doc.check_permission("write")
            configured = _child_remove_target(doc, profile)
            if (
                isinstance(configured, dict)
                or configured[0].fieldname != payload["child_table"]
            ):
                return _error(
                    "CHILD_TARGET_NOT_ALLOWED",
                    "The prepared child-row target is no longer allowed.",
                )
            selected, row_failure = _find_child(
                doc,
                {
                    "child_table": payload["child_table"],
                    "row": {"row_name": payload["row"]["row_name"]},
                },
            )
            if row_failure or _row_preview(selected) != payload["row"]:
                return _error(
                    "STALE_CONFIRMATION",
                    "The child row changed after the preview was prepared. Please prepare the removal again.",
                )
            doc.remove(selected)
            if doc.doctype == "Sales Invoice":
                failure = _refresh_sales_invoice(doc, total_changed=True)
                if failure:
                    frappe.db.rollback()
                    return failure
            elif doc.doctype == "Purchase Order":
                _refresh_purchase_order(doc)
            elif hasattr(doc, "calculate_taxes_and_totals"):
                doc.calculate_taxes_and_totals()
            doc.save(ignore_permissions=False)
        elif action == "update":
            policy_failure = _lifecycle_policy_failure("update")
            if policy_failure:
                return policy_failure
            if doc.doctype == "Purchase Order":
                doc.check_permission("write")
                if int(doc.docstatus) != 0:
                    return _error(
                        "INVALID_DOCUMENT_STATE",
                        "Only Draft Purchase Orders can be updated.",
                    )
                # Revalidate the dedicated domain policy as well as normal Link permissions.
                for change in payload["changes"]:
                    _, failure = _validate_change(doc, change["input"])
                    if failure:
                        return (
                            stale_commercial()
                            if change["field"] in COMMERCIAL_FIELDS
                            else failure
                        )
            had_manual_schedule = (
                bool(
                    doc.get("payment_schedule")
                    and not doc.get("payment_terms_template")
                )
                if doc.doctype == "Sales Invoice"
                else False
            )
            for change in payload["changes"]:
                if change["child_table"]:
                    row, row_failure = _find_child(doc, change["input"])
                    if row_failure or not row or row.name != change["row_name"]:
                        return _error(
                            "STALE_CONFIRMATION",
                            "The child row changed after the preview was prepared. Please prepare the update again.",
                        )
                    if _json(row.get(change["field"])) != change["old"]:
                        return _error(
                            "STALE_CONFIRMATION",
                            "The child row changed after the preview was prepared. Please prepare the update again.",
                        )
                    row.set(change["field"], change["new"])
                else:
                    if _json(doc.get(change["field"])) != change["old"]:
                        return _error(
                            "STALE_CONFIRMATION",
                            "The document changed after the preview was prepared. Please prepare the update again.",
                        )
                    doc.set(change["field"], change["new"])
            if doc.doctype == "Sales Invoice":
                failure = _refresh_sales_invoice(
                    doc,
                    terms_changed=any(
                        change["field"] == "tc_name" for change in payload["changes"]
                    ),
                    schedule_changed=any(
                        change["field"] == "payment_terms_template"
                        for change in payload["changes"]
                    ),
                    total_changed=any(
                        change["child_table"] and change["field"] in {"qty", "rate"}
                        for change in payload["changes"]
                    ),
                    had_manual_schedule=had_manual_schedule,
                )
                if failure:
                    frappe.db.rollback()
                    return failure
            elif doc.doctype == "Purchase Order":
                approved = payload.get("commercial")
                changed = {
                    change["field"] for change in payload["changes"]
                } & COMMERCIAL_FIELDS
                if changed and not payload.get("approval_revalidated"):
                    refresh_commercial(
                        doc,
                        terms_changed="tc_name" in changed,
                        payment_changed="payment_terms_template" in changed,
                    )
                elif changed:
                    if not approved:
                        return stale_commercial()
                    templates, failure = template_snapshot(doc, frappe_module=frappe)
                    if failure or templates != approved["templates"]:
                        return stale_commercial()
                    refresh_commercial(
                        doc,
                        terms_changed="tc_name" in changed,
                        payment_changed="payment_terms_template" in changed,
                    )
                    if commercial_fingerprint(doc) != approved["fingerprint"]:
                        frappe.db.rollback()
                        return stale_commercial()
                else:
                    _refresh_purchase_order(doc)
            doc.save(ignore_permissions=False)
            if doc.doctype == "Purchase Order" and payload.get("commercial"):
                approved = payload["commercial"]
                templates, failure = template_snapshot(doc, frappe_module=frappe)
                if (
                    failure
                    or templates != approved["templates"]
                    or commercial_fingerprint(doc) != approved["fingerprint"]
                ):
                    frappe.db.rollback()
                    return stale_commercial()
        elif action == "submit":
            doc.check_permission("submit")
            doc.submit()
        elif action == "cancel":
            doc.check_permission("cancel")
            policy_failure = _lifecycle_policy_failure("cancel")
            if policy_failure:
                return policy_failure
            doc.cancel()
        else:
            doc.check_permission("delete")
            if payload.get("plan") == "cancel_delete":
                policy_failure = _lifecycle_policy_failure("delete")
                if policy_failure:
                    return policy_failure
                policy_failure = _lifecycle_policy_failure("cancel")
                if policy_failure:
                    return policy_failure
                doc.cancel()
                doc = frappe.get_doc(doc.doctype, doc.name)
                if not doc.docstatus.is_cancelled():
                    frappe.db.rollback()
                    return _error(
                        "DELETE_BLOCKED",
                        "The target was not cancelled; nothing was deleted.",
                    )
                blockers = get_linked_docs(
                    doc, method="Delete"
                ) + get_dynamic_linked_docs(doc, method="Delete")
                if blockers:
                    frappe.db.rollback()
                    return _blocked("delete", doc, blockers)
            else:
                policy_failure = _lifecycle_policy_failure("delete")
                if policy_failure:
                    return policy_failure
            doc.delete(ignore_permissions=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED",
            f"The authenticated user cannot complete {action} on {doc.doctype} {doc.name}.",
        )
    except frappe.LinkExistsError as error:
        frappe.db.rollback()
        return logged_defined_error("lifecycle", "LINKED_DOCUMENT", level="warning")
    except Exception as error:
        frappe.db.rollback()
        if doc.doctype == "Purchase Order" and payload.get("commercial"):
            return logged_defined_error(
                "confirm_document_update",
                "LIFECYCLE_VALIDATION_FAILED",
                level="exception",
            )
        return logged_defined_error(
            "lifecycle", "LIFECYCLE_VALIDATION_FAILED", level="exception"
        )
    result_status = {
        "update": "updated",
        "child_add": "added",
        "child_remove": "removed",
        "submit": "submitted",
        "cancel": "cancelled",
        "delete": "deleted",
    }[action]
    return {
        "status": result_status,
        "document": {
            "doctype": doc.doctype,
            "name": doc.name,
            "docstatus": int(doc.docstatus),
        },
    }


def _apply_direct_mutation(
    action: str, payload: dict[str, Any], doc: Any, profile: str
) -> dict[str, Any]:
    """Apply only while the direct mode remains authorized at the write boundary."""
    failure = _exact_write_mode_failure(action, WriteMode.DIRECT)
    if failure:
        return failure
    if action == "delete" and payload.get("plan") == "cancel_delete":
        failure = _cancel_delete_mode_failure(WriteMode.DIRECT)
        if failure:
            return failure
    return _apply_mutation(action, payload, doc, profile)


def _apply_approved_mutation(
    action: str, payload: dict[str, Any], doc: Any, profile: str
) -> dict[str, Any]:
    """Apply only while approval-required mode remains authorized at the write boundary."""
    failure = _exact_write_mode_failure(action, WriteMode.APPROVAL_REQUIRED)
    if failure:
        return failure
    if action == "delete" and payload.get("plan") == "cancel_delete":
        failure = _cancel_delete_mode_failure(WriteMode.APPROVAL_REQUIRED)
        if failure:
            return failure
    return _apply_mutation(action, payload, doc, profile)


def confirm(action: str, token: str, confirm: bool, profile: str) -> dict[str, Any]:
    """Authorize and apply an approval-required lifecycle mutation."""
    user = _user()
    if not confirm:
        approvals.cancel(
            token, action=f"lifecycle_{action}", site=frappe.local.site, user=user
        )
        return _error(
            "CONFIRMATION_REQUIRED", "The prepared lifecycle action was not confirmed."
        )
    if action in {"update", "child_add", "child_remove", "cancel", "delete"}:
        policy_failure = _lifecycle_policy_failure(
            "update" if action in {"child_add", "child_remove"} else action
        )
        if not policy_failure:
            policy_failure = _confirm_policy_failure(action)
        if policy_failure:
            return policy_failure
    approval, state = approvals.claim_for_confirm_write(
        token, action=f"lifecycle_{action}", site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "lifecycle action")
        return _error(code, message, retryable=retryable)
    doc, failure = _revalidate(approval, action, profile)
    if failure:
        return failure
    payload = deepcopy(approval.payload)
    payload["approval_revalidated"] = True
    if action in {"update", "child_add", "child_remove", "cancel", "delete"}:
        return _apply_approved_mutation(action, payload, doc, profile)
    return _apply_mutation(action, payload, doc, profile)


def _prepare_action(
    action: str, target: dict[str, Any], profile: str
) -> dict[str, Any]:
    payload, doc, preview = _plan_action(action, target, profile)
    if doc is None:
        return preview
    return _create(action, doc, profile, payload, preview)


def prepare_submit(target: dict[str, Any], profile: str) -> dict[str, Any]:
    return _prepare_action("submit", target, profile)


def prepare_cancel(target: dict[str, Any], profile: str) -> dict[str, Any]:
    return _prepare_action("cancel", target, profile)


def prepare_delete(target: dict[str, Any], profile: str) -> dict[str, Any]:
    return _prepare_action("delete", target, profile)


def execute_update(
    target: dict[str, Any], changes: list[dict[str, Any]], profile: str
) -> dict[str, Any]:
    failure = _direct_policy_failure("update")
    if failure:
        return failure
    payload, doc, preview = _plan_update(target, changes, profile, copy_for_apply=True)
    if doc is None:
        return preview
    apply_doc, failure = _load(target, profile, "write", "update")
    if failure:
        return failure
    return _apply_direct_mutation("update", payload, apply_doc, profile)


def execute_child_add(
    target: dict[str, Any], item: dict[str, Any], qty: Any, rate: Any, profile: str
) -> dict[str, Any]:
    failure = _direct_policy_failure("child_add")
    if failure:
        return failure
    payload, doc, preview = _plan_child_add(
        target, item, qty, rate, profile, copy_for_apply=True
    )
    if doc is None:
        return preview
    apply_doc, failure = _load(target, profile, "write", "child_add")
    if failure:
        return failure
    return _apply_direct_mutation("child_add", payload, apply_doc, profile)


def execute_child_remove(
    target: dict[str, Any], child_table: str, row: dict[str, Any], profile: str
) -> dict[str, Any]:
    failure = _direct_policy_failure("child_remove")
    if failure:
        return failure
    payload, doc, preview = _plan_child_remove(
        target, child_table, row, profile, copy_for_apply=True
    )
    if doc is None:
        return preview
    apply_doc, failure = _load(target, profile, "write", "child_remove")
    if failure:
        return failure
    return _apply_direct_mutation("child_remove", payload, apply_doc, profile)


def execute_cancel(target: dict[str, Any], profile: str) -> dict[str, Any]:
    failure = _direct_policy_failure("cancel")
    if failure:
        return failure
    payload, doc, preview = _plan_action("cancel", target, profile)
    if doc is None:
        return preview
    return _apply_direct_mutation("cancel", payload, doc, profile)


def execute_delete(target: dict[str, Any], profile: str) -> dict[str, Any]:
    failure = _direct_policy_failure("delete")
    if failure:
        return failure
    payload, doc, preview = _plan_action("delete", target, profile)
    if doc is None:
        return preview
    if payload.get("plan") == "cancel_delete":
        cancel_failure = _direct_policy_failure("cancel")
        if cancel_failure:
            return cancel_failure
    return _apply_direct_mutation("delete", payload, doc, profile)
