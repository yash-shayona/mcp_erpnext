"""Shared, exact-target lifecycle service for the configured MCP profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe
from frappe.model.delete_doc import get_dynamic_linked_docs, get_linked_docs

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import new_error_reference

PROFILE_DOCTYPES = {
	"sales": frozenset({"Quotation", "Sales Order", "Customer", "Item"}),
	"purchase": frozenset({"Purchase Order", "Supplier", "Item"}),
}

_SYSTEM_FIELDS = frozenset(
	{"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "parent", "parenttype", "parentfield"}
)


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
	return {"status": "error", "code": code, "message": message, "reference": new_error_reference(), "retryable": retryable}


def _user() -> str:
	user = getattr(frappe.session, "user", None)
	if not user or user in {"Guest", "guest"}:
		frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
	return user


def _target(target: dict[str, Any], profile: str) -> tuple[str, str] | dict[str, Any]:
	doctype = target.get("doctype") if isinstance(target, dict) else None
	name = target.get("name") if isinstance(target, dict) else None
	if not isinstance(doctype, str) or not doctype.strip() or not isinstance(name, str) or not name.strip():
		return _error("INVALID_TARGET", "An exact document doctype and name are required.")
	if doctype not in PROFILE_DOCTYPES.get(profile, frozenset()):
		return _error("DOCTYPE_NOT_ALLOWED", f"{doctype} is not available in the {profile} MCP profile.")
	return doctype.strip(), name.strip()


def _load(target: dict[str, Any], profile: str, permission: str = "read") -> tuple[Any, dict[str, Any] | None]:
	resolved = _target(target, profile)
	if isinstance(resolved, dict):
		return None, resolved
	doctype, name = resolved
	try:
		doc = frappe.get_doc(doctype, name)
	except frappe.DoesNotExistError:
		return None, _error("DOCUMENT_NOT_FOUND", f"{doctype} {name} was not found.")
	if not doc.has_permission(permission):
		return None, _error("PERMISSION_DENIED", f"The authenticated user cannot {permission} {doctype} {name}.")
	return doc, None


def _status(doc: Any) -> str:
	return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(int(doc.docstatus), str(doc.docstatus))


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
	if not table or not doc.meta.has_field(table) or doc.meta.get_field(table).fieldtype != "Table":
		return None, _error("INVALID_CHILD_TARGET", f"{table or 'Child table'} is not a child table on {doc.doctype}.")
	matches = []
	for row in doc.get(table) or []:
		if selector.get("row_name") and row.name == selector["row_name"]:
			matches.append(row)
		elif selector.get("item_code") and row.get("item_code") == selector["item_code"]:
			matches.append(row)
		elif selector.get("idx") is not None and int(row.idx or 0) == selector["idx"]:
			matches.append(row)
	if len(matches) != 1:
		return None, _error("AMBIGUOUS_CHILD_TARGET" if matches else "CHILD_ROW_NOT_FOUND", "The child-row selector did not identify exactly one row.")
	return matches[0], None


def _validate_change(doc: Any, change: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
	fieldname = change.get("field")
	if fieldname in _SYSTEM_FIELDS:
		return None, _error("FIELD_NOT_WRITABLE", f"{fieldname} is controlled by Frappe and cannot be updated directly.")
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
		return None, _error("FIELD_NOT_WRITABLE", f"{path} cannot be updated as a scalar field.")
	value = change.get("value")
	if meta.fieldtype == "Select" and value not in (None, "") and str(value) not in (meta.options or "").split("\n"):
		return None, _error("INVALID_FIELD_VALUE", f"{path} has an invalid Select value.")
	if meta.fieldtype == "Link" and value not in (None, ""):
		if not frappe.get_list(meta.options, filters={"name": value}, fields=["name"], limit_page_length=1, ignore_permissions=False):
			return None, _error("INVALID_LINK", f"{path} does not reference a permitted {meta.options}.")
	return {"path": path, "field": fieldname, "child_table": change.get("child_table"), "row_name": row.name if change.get("child_table") and row else None, "old": _json(current), "new": _json(value), "input": deepcopy(change)}, None


def _base_preview(doc: Any, action: str) -> dict[str, Any]:
	return {"doctype": doc.doctype, "name": doc.name, "status": _status(doc), "docstatus": int(doc.docstatus), "action": action}


def _create(action: str, doc: Any, profile: str, payload: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
	token = approvals.create(action=f"lifecycle_{action}", site=frappe.local.site, user=_user(), payload={**payload, "doctype": doc.doctype, "name": doc.name, "profile": profile, "modified": str(doc.modified), "docstatus": int(doc.docstatus)})
	return {"status": "ready", "approval_token": token, "expires_in_seconds": APPROVAL_TTL_SECONDS, "preview": preview, "interaction": approval_directive().model_dump(mode="json")}


def prepare_update(target: dict[str, Any], changes: list[dict[str, Any]], profile: str) -> dict[str, Any]:
	doc, failure = _load(target, profile, "write")
	if failure:
		return failure
	if doc.docstatus.is_cancelled():
		return _error("INVALID_DOCUMENT_STATE", f"{doc.doctype} {doc.name} is Cancelled and cannot be updated.")
	validated = []
	for change in changes:
		item, failure = _validate_change(doc, change)
		if failure:
			return failure
		validated.append(item)
	preview = {**_base_preview(doc, "UPDATE"), "changes": [{key: item[key] for key in ("path", "old", "new")} for item in validated]}
	return _create("update", doc, profile, {"changes": validated}, preview)


def _prepare_action(action: str, target: dict[str, Any], profile: str) -> dict[str, Any]:
	doc, failure = _load(target, profile, "read")
	if failure:
		return failure
	if action == "submit":
		if not doc.meta.is_submittable:
			return _error("NOT_SUBMITTABLE", f"{doc.doctype} is not a submittable DocType.")
		if not doc.docstatus.is_draft():
			return _error("INVALID_DOCUMENT_STATE", f"{doc.doctype} {doc.name} is {_status(doc)} and cannot be submitted.")
		permission = "submit"
	elif action == "cancel":
		if not doc.meta.is_submittable or not doc.docstatus.is_submitted():
			return _error("INVALID_DOCUMENT_STATE", f"{doc.doctype} {doc.name} must be Submitted before it can be cancelled.")
		permission = "cancel"
		blockers = get_linked_docs(doc, method="Cancel") + get_dynamic_linked_docs(doc, method="Cancel")
		if blockers:
			return _blocked(action, doc, blockers)
	else:
		permission = "delete"
		if doc.meta.is_submittable and doc.docstatus.is_submitted():
			if not doc.has_permission("cancel"):
				return _error("PERMISSION_DENIED", f"The authenticated user cannot cancel {doc.doctype} {doc.name} as part of deletion.")
			blockers = get_linked_docs(doc, method="Cancel") + get_dynamic_linked_docs(doc, method="Cancel")
			if blockers:
				return _blocked(action, doc, blockers)
			delete_blockers = get_linked_docs(doc, method="Delete") + get_dynamic_linked_docs(doc, method="Delete")
			if delete_blockers:
				return _blocked(action, doc, delete_blockers)
			plan = "cancel_delete"
		else:
			plan = "delete"
			blockers = get_linked_docs(doc, method="Delete") + get_dynamic_linked_docs(doc, method="Delete")
			if blockers:
				return _blocked(action, doc, blockers)
	if not doc.has_permission(permission):
		return _error("PERMISSION_DENIED", f"The authenticated user cannot {permission} {doc.doctype} {doc.name}.")
	preview = _base_preview(doc, action.upper())
	if action == "delete" and plan == "cancel_delete":
		preview["plan"] = [f"Cancel {doc.doctype} {doc.name}", f"Delete {doc.doctype} {doc.name}"]
	return _create(action, doc, profile, {"plan": locals().get("plan", action)}, preview)


def _blocked(action: str, doc: Any, blockers: list[dict[str, Any]]) -> dict[str, Any]:
	return {"status": "blocked", "code": "LINKED_DOCUMENT", "message": f"Cannot {action} {doc.doctype} {doc.name}; a linked document blocks this action.", "reference": new_error_reference(), "blockers": [{"doctype": item.get("reference_doctype"), "name": item.get("reference_docname")} for item in blockers[:10]], "preview": _base_preview(doc, action.upper())}


def _revalidate(approval: Any, profile: str) -> tuple[Any, dict[str, Any] | None]:
	doc, failure = _load({"doctype": approval.payload["doctype"], "name": approval.payload["name"]}, profile, "read")
	if failure:
		return None, failure
	if str(doc.modified) != approval.payload["modified"] or int(doc.docstatus) != approval.payload["docstatus"]:
		return None, _error("STALE_CONFIRMATION", "The document changed after the preview was prepared. Please prepare the action again.")
	return doc, None


def confirm(action: str, token: str, confirm: bool, profile: str) -> dict[str, Any]:
	user = _user()
	if not confirm:
		approvals.cancel(token, action=f"lifecycle_{action}", site=frappe.local.site, user=user)
		return _error("CONFIRMATION_REQUIRED", "The prepared lifecycle action was not confirmed.")
	approval, state = approvals.claim_for_confirm_write(token, action=f"lifecycle_{action}", site=frappe.local.site, user=user)
	if state != "available" or approval is None:
		code, message, retryable = confirmation_failure(state, "lifecycle action")
		return _error(code, message, retryable=retryable)
	doc, failure = _revalidate(approval, profile)
	if failure:
		return failure
	try:
		if action == "update":
			for change in approval.payload["changes"]:
				if change["child_table"]:
					row, row_failure = _find_child(doc, change["input"])
					if row_failure or not row or row.name != change["row_name"]:
						return _error("STALE_CONFIRMATION", "The child row changed after the preview was prepared. Please prepare the update again.")
					row.set(change["field"], change["new"])
				else:
					if _json(doc.get(change["field"])) != change["old"]:
						return _error("STALE_CONFIRMATION", "The document changed after the preview was prepared. Please prepare the update again.")
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
					return _error("DELETE_BLOCKED", "The target was not cancelled; nothing was deleted.")
				blockers = get_linked_docs(doc, method="Delete") + get_dynamic_linked_docs(doc, method="Delete")
				if blockers:
					frappe.db.rollback()
					return _blocked("delete", doc, blockers)
			doc.delete(ignore_permissions=False)
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		return _error("PERMISSION_DENIED", f"The authenticated user cannot complete {action} on {doc.doctype} {doc.name}.")
	except frappe.LinkExistsError as error:
		frappe.db.rollback()
		return _error("LINKED_DOCUMENT", str(error))
	except Exception as error:
		frappe.db.rollback()
		return _error("LIFECYCLE_VALIDATION_FAILED", str(error))
	result_status = {"update": "updated", "submit": "submitted", "cancel": "cancelled", "delete": "deleted"}[action]
	return {"status": result_status, "document": {"doctype": doc.doctype, "name": doc.name, "docstatus": int(doc.docstatus)}}


def prepare_submit(target: dict[str, Any], profile: str) -> dict[str, Any]:
	return _prepare_action("submit", target, profile)


def prepare_cancel(target: dict[str, Any], profile: str) -> dict[str, Any]:
	return _prepare_action("cancel", target, profile)


def prepare_delete(target: dict[str, Any], profile: str) -> dict[str, Any]:
	return _prepare_action("delete", target, profile)
