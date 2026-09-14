"""Shared, exact-target lifecycle service for the configured MCP profiles."""

from __future__ import annotations

import math
import hashlib
import json
from copy import deepcopy
from typing import Any

import frappe
from frappe.model.delete_doc import get_dynamic_linked_docs, get_linked_docs
from frappe.utils import get_datetime, getdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import new_error_reference

PROFILE_DOCTYPES = {
    "sales": frozenset({"Quotation", "Sales Order", "Customer", "Item"}),
    "purchase": frozenset({"Purchase Order", "Supplier", "Item"}),
    "accounts": frozenset(),
}

# The legacy profile sets remain the baseline for already-supported doctypes.
# Sales Invoice is intentionally exposed only for its safe V1 lifecycle actions.
LIFECYCLE_ACTION_DOCTYPES = {
    "sales": {
        "update": PROFILE_DOCTYPES["sales"],
        "child_add": PROFILE_DOCTYPES["sales"],
        "submit": PROFILE_DOCTYPES["sales"] | frozenset({"Sales Invoice", "Delivery Note"}),
        "cancel": PROFILE_DOCTYPES["sales"] | frozenset({"Sales Invoice", "Delivery Note"}),
        "delete": PROFILE_DOCTYPES["sales"] | frozenset({"Sales Invoice", "Delivery Note"}),
    },
    "purchase": {
        "update": PROFILE_DOCTYPES["purchase"],
        "child_add": PROFILE_DOCTYPES["purchase"],
        "submit": PROFILE_DOCTYPES["purchase"],
        "cancel": PROFILE_DOCTYPES["purchase"],
        "delete": PROFILE_DOCTYPES["purchase"],
    },
    "accounts": {
        "update": frozenset(),
        "child_add": frozenset(),
        "submit": frozenset({"Payment Entry"}),
        "cancel": frozenset({"Payment Entry"}),
        "delete": frozenset({"Payment Entry"}),
    },
}

CHILD_ADD_TARGETS = {
    "sales": {
        "Quotation": ("items", "Quotation Item"),
        "Sales Order": ("items", "Sales Order Item"),
    },
    "purchase": {"Purchase Order": ("items", "Purchase Order Item")},
}

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
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": retryable,
    }


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


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
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_outstanding_reference_documents

    references = list(doc.get("references") or [])
    vouchers = [frappe._dict(voucher_type=row.reference_doctype, voucher_no=row.reference_name) for row in references if row.reference_doctype and row.reference_name]
    latest = get_outstanding_reference_documents({
        "posting_date": doc.posting_date,
        "company": doc.company,
        "party_type": doc.party_type,
        "payment_type": doc.payment_type,
        "party": doc.party,
        "party_account": doc.paid_from if doc.payment_type == "Receive" else doc.paid_to,
        "get_outstanding_invoices": True,
        "get_orders_to_be_billed": True,
        "vouchers": vouchers,
        "book_advance_payments_in_separate_party_account": doc.book_advance_payments_in_separate_party_account,
    }, validate=True) or []
    latest_by_key = {(row.voucher_type, row.voucher_no, row.get("payment_term")): flt(row.outstanding_amount) for row in latest}
    projected = []
    for row in references:
        key = (row.reference_doctype, row.reference_name, row.payment_term)
        projected.append({
            "reference_doctype": row.reference_doctype,
            "reference_name": row.reference_name,
            "payment_term": row.payment_term,
            "current_outstanding": latest_by_key.get(key),
            "allocated_amount": flt(row.allocated_amount),
        })
    preview = {
        "payment_entry": doc.name, "customer": doc.party, "company": doc.company,
        "payment_type": doc.payment_type, "posting_date": _json(doc.posting_date),
        "destination": doc.mode_of_payment or doc.bank_account or (doc.paid_to if doc.payment_type == "Receive" else doc.paid_from),
        "party_currency": doc.paid_from_account_currency if doc.payment_type == "Receive" else doc.paid_to_account_currency,
        "destination_currency": doc.paid_to_account_currency if doc.payment_type == "Receive" else doc.paid_from_account_currency,
        "paid_amount": flt(doc.paid_amount), "received_amount": flt(doc.received_amount),
        "references": projected, "total_allocated_amount": flt(doc.total_allocated_amount),
        "unallocated_amount": flt(doc.unallocated_amount), "difference_amount": flt(doc.difference_amount),
        "deductions": [{"account": row.account, "amount": flt(row.amount)} for row in (doc.get("deductions") or [])],
        "taxes": [{"account": row.account_head, "amount": flt(row.tax_amount)} for row in (doc.get("taxes") or [])],
        "warning": "Submitting creates native ledger entries and changes every referenced invoice outstanding amount.",
    }
    fingerprint = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return preview, fingerprint


def _create(
    action: str,
    doc: Any,
    profile: str,
    payload: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
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


def prepare_update(
    target: dict[str, Any], changes: list[dict[str, Any]], profile: str
) -> dict[str, Any]:
    doc, failure = _load(target, profile, "write", "update")
    if failure:
        return failure
    if doc.docstatus.is_cancelled():
        return _error(
            "INVALID_DOCUMENT_STATE",
            f"{doc.doctype} {doc.name} is Cancelled and cannot be updated.",
        )
    validated = []
    for change in changes:
        item, failure = _validate_change(doc, change)
        if failure:
            return failure
        validated.append(item)
    preview = {
        **_base_preview(doc, "UPDATE"),
        "changes": [
            {key: item[key] for key in ("path", "old", "new")} for item in validated
        ],
    }
    return _create("update", doc, profile, {"changes": validated}, preview)


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
        fields=["name", "item_code", "item_name", "stock_uom"],
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


def prepare_child_add(
    target: dict[str, Any], item: dict[str, Any], qty: Any, rate: Any, profile: str
) -> dict[str, Any]:
    doc, failure = _load(target, profile, "write", "child_add")
    if failure:
        return failure
    if int(doc.docstatus) != 0:
        return _error(
            "INVALID_DOCUMENT_STATE",
            f"{doc.doctype} {doc.name} is {_status(doc)} and cannot receive a new item row.",
        )
    configured = _child_add_target(doc, profile)
    if isinstance(configured, dict):
        return configured
    field, child_meta = configured
    item_record, failure = _item_for_child_add(item, profile)
    if failure:
        return failure
    if (
        isinstance(qty, bool)
        or not isinstance(qty, (int, float))
        or not math.isfinite(qty)
        or qty <= 0
    ):
        return _error(
            "INVALID_ITEM_DETAILS", "Item quantity must be greater than zero."
        )
    if rate is not None and (
        isinstance(rate, bool)
        or not isinstance(rate, (int, float))
        or not math.isfinite(rate)
        or rate < 0
    ):
        return _error("INVALID_ITEM_DETAILS", "Item rate must be zero or greater.")
    item_code = item_record["name"]
    duplicates = [
        row
        for row in doc.get(field.fieldname) or []
        if row.get("item_code") == item_code
    ]
    if duplicates:
        return _error(
            "DUPLICATE_ITEM_ROW",
            f"Item {item_code} already exists in {doc.doctype} {doc.name}; no new row was prepared.",
        )
    row = {"item_code": item_code, "qty": qty}
    if rate is not None:
        row["rate"] = rate
    try:
        new_row = doc.append(field.fieldname, row)
        if hasattr(doc, "set_missing_values"):
            doc.set_missing_values()
        if hasattr(doc, "calculate_taxes_and_totals"):
            doc.calculate_taxes_and_totals()
        if hasattr(doc, "run_method"):
            doc.run_method("validate")
    except Exception as error:
        return _error("LIFECYCLE_VALIDATION_FAILED", str(error))
    prepared_row = _child_row_values(new_row, child_meta)
    preview = {
        **_base_preview(doc, "ADD_ITEM"),
        "new_row": prepared_row,
        "message": "This will add a new item row.",
    }
    return _create(
        "child_add",
        doc,
        profile,
        {
            "child_table": field.fieldname,
            "child_doctype": getattr(child_meta, "name", field.options),
            "row": prepared_row,
            "item_code": item_code,
        },
        preview,
    )


def _prepare_action(
    action: str, target: dict[str, Any], profile: str
) -> dict[str, Any]:
    doc, failure = _load(target, profile, "read", action)
    if failure:
        return failure
    if action == "submit":
        if not doc.meta.is_submittable:
            return _error(
                "NOT_SUBMITTABLE", f"{doc.doctype} is not a submittable DocType."
            )
        if not doc.docstatus.is_draft():
            return _error(
                "INVALID_DOCUMENT_STATE",
                f"{doc.doctype} {doc.name} is {_status(doc)} and cannot be submitted.",
            )
        permission = "submit"
    elif action == "cancel":
        if not doc.meta.is_submittable or not doc.docstatus.is_submitted():
            return _error(
                "INVALID_DOCUMENT_STATE",
                f"{doc.doctype} {doc.name} must be Submitted before it can be cancelled.",
            )
        permission = "cancel"
        blockers = get_linked_docs(doc, method="Cancel") + get_dynamic_linked_docs(
            doc, method="Cancel"
        )
        if blockers:
            return _blocked(action, doc, blockers)
    else:
        permission = "delete"
        if doc.meta.is_submittable and doc.docstatus.is_submitted():
            if not doc.has_permission("cancel"):
                return _error(
                    "PERMISSION_DENIED",
                    f"The authenticated user cannot cancel {doc.doctype} {doc.name} as part of deletion.",
                )
            blockers = get_linked_docs(doc, method="Cancel") + get_dynamic_linked_docs(
                doc, method="Cancel"
            )
            if blockers:
                return _blocked(action, doc, blockers)
            delete_blockers = get_linked_docs(
                doc, method="Delete"
            ) + get_dynamic_linked_docs(doc, method="Delete")
            if delete_blockers:
                return _blocked(action, doc, delete_blockers)
            plan = "cancel_delete"
        else:
            plan = "delete"
            blockers = get_linked_docs(doc, method="Delete") + get_dynamic_linked_docs(
                doc, method="Delete"
            )
            if blockers:
                return _blocked(action, doc, blockers)
    if not doc.has_permission(permission):
        return _error(
            "PERMISSION_DENIED",
            f"The authenticated user cannot {permission} {doc.doctype} {doc.name}.",
        )
    preview = _base_preview(doc, action.upper())
    extra_payload: dict[str, Any] = {}
    if action == "submit" and doc.doctype == "Payment Entry":
        try:
            payment_preview, payment_fingerprint = _payment_entry_submit_state(doc)
        except Exception:
            return _error("LIFECYCLE_VALIDATION_FAILED", "ERPNext could not refresh Payment Entry references for submit review.")
        preview["payment_entry_impact"] = payment_preview
        extra_payload["payment_entry_submit_fingerprint"] = payment_fingerprint
    if action == "delete" and plan == "cancel_delete":
        preview["plan"] = [
            f"Cancel {doc.doctype} {doc.name}",
            f"Delete {doc.doctype} {doc.name}",
        ]
    return _create(
        action, doc, profile, {"plan": locals().get("plan", action), **extra_payload}, preview
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
            return None, _error("STALE_CONFIRMATION", "Payment Entry reference state changed. Please prepare submit again.")
        if fingerprint != approval.payload.get("payment_entry_submit_fingerprint"):
            return None, _error("STALE_CONFIRMATION", "Payment Entry reference state changed. Please prepare submit again.")
    return doc, None


def confirm(action: str, token: str, confirm: bool, profile: str) -> dict[str, Any]:
    user = _user()
    if not confirm:
        approvals.cancel(
            token, action=f"lifecycle_{action}", site=frappe.local.site, user=user
        )
        return _error(
            "CONFIRMATION_REQUIRED", "The prepared lifecycle action was not confirmed."
        )
    approval, state = approvals.claim_for_confirm_write(
        token, action=f"lifecycle_{action}", site=frappe.local.site, user=user
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "lifecycle action")
        return _error(code, message, retryable=retryable)
    doc, failure = _revalidate(approval, action, profile)
    if failure:
        return failure
    try:
        if action == "child_add":
            doc.check_permission("write")
            field_name = approval.payload["child_table"]
            configured = _child_add_target(doc, profile)
            if isinstance(configured, dict) or configured[0].fieldname != field_name:
                return _error(
                    "CHILD_TARGET_NOT_ALLOWED",
                    "The prepared child-row target is no longer allowed.",
                )
            if any(
                row.get("item_code") == approval.payload["item_code"]
                for row in doc.get(field_name) or []
            ):
                return _error(
                    "STALE_CONFIRMATION",
                    "The item already exists in the document. Please prepare the action again.",
                )
            _, child_meta = configured
            row_values = _restore_child_row_types(approval.payload["row"], child_meta)
            doc.append(field_name, row_values)
            if hasattr(doc, "set_missing_values"):
                doc.set_missing_values()
            if hasattr(doc, "calculate_taxes_and_totals"):
                doc.calculate_taxes_and_totals()
            doc.save(ignore_permissions=False)
        elif action == "update":
            for change in approval.payload["changes"]:
                if change["child_table"]:
                    row, row_failure = _find_child(doc, change["input"])
                    if row_failure or not row or row.name != change["row_name"]:
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
            doc.save(ignore_permissions=False)
        elif action == "submit":
            doc.check_permission("submit")
            doc.submit()
        elif action == "cancel":
            doc.check_permission("cancel")
            doc.cancel()
        else:
            doc.check_permission("delete")
            if approval.payload.get("plan") == "cancel_delete":
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
        return _error("LINKED_DOCUMENT", str(error))
    except Exception as error:
        frappe.db.rollback()
        return _error("LIFECYCLE_VALIDATION_FAILED", str(error))
    result_status = {
        "update": "updated",
        "child_add": "added",
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


def prepare_submit(target: dict[str, Any], profile: str) -> dict[str, Any]:
    return _prepare_action("submit", target, profile)


def prepare_cancel(target: dict[str, Any], profile: str) -> dict[str, Any]:
    return _prepare_action("cancel", target, profile)


def prepare_delete(target: dict[str, Any], profile: str) -> dict[str, Any]:
    return _prepare_action("delete", target, profile)
