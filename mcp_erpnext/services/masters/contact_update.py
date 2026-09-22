"""Customer-scoped, approval-bound updates for existing native Contacts."""

from __future__ import annotations

import copy
from typing import Any

import frappe
from frappe.utils import validate_email_address, validate_phone_number

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...observability import new_error_reference
from ..common.fingerprint import stable_fingerprint
from .customer_contact import (
	_customer_reference,
	_load_contact,
	_load_customer,
	_links,
	_projection,
	_value,
	_has_customer_link,
	_search_contacts,
)

_ACTION = "customer_contact_update"
_PROFILE = "sales"
_DETAIL_FIELDS = ("first_name", "middle_name", "last_name", "company_name", "designation", "department")
_COMMUNICATION_ACTIONS = {
	"add_email", "replace_primary_email", "set_primary_email",
	"add_phone", "replace_primary_phone", "replace_primary_mobile",
	"set_primary_phone", "set_primary_mobile",
}


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
	return {"status": "error", "code": code, "message": message, "reference": new_error_reference(), "retryable": retryable}


def _current_user() -> str:
	user = getattr(frappe.session, "user", None)
	if not user or user in {"Guest", "guest"}:
		frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
	return user


def _clean(value: Any) -> str | None:
	if not isinstance(value, str):
		return None
	value = value.strip()
	return value or None


def _set_value(document: Any, fieldname: str, value: Any) -> None:
	if isinstance(document, dict):
		document[fieldname] = value
	else:
		setattr(document, fieldname, value)


def _customer_primary(customer: Any, contact: Any) -> bool:
	return _value(customer, "customer_primary_contact") == _value(contact, "name")


def _relationship_state(contact: Any, customer_name: str) -> list[dict[str, str]]:
	return [
		{"doctype": str(_value(link, "link_doctype") or ""), "name": str(_value(link, "link_name") or "")}
		for link in _links(contact)
		if not (
			_value(link, "link_doctype") == "Customer"
			and _value(link, "link_name") == customer_name
		)
	]


def _shared_failure(contact: Any, customer_name: str) -> dict[str, Any] | None:
	if _relationship_state(contact, customer_name):
		return _error("CONTACT_SHARED_WITH_OTHER_PARTIES", "The selected Contact is shared with another party and cannot be updated in V1.")
	return None


def _rows(contact: Any, fieldname: str) -> list[Any]:
	return list(_value(contact, fieldname, []) or [])


def _row_state(row: Any, doctype: str, parentfield: str, value_field: str, flags: tuple[str, ...]) -> dict[str, Any]:
	return {
		"parent": str(_value(row, "parent") or ""),
		"child_doctype": doctype,
		"parentfield": parentfield,
		"name": str(_value(row, "name") or ""),
		"value": _clean(_value(row, value_field)),
		**{flag: bool(_value(row, flag, 0)) for flag in flags},
	}


def _email_state(contact: Any) -> list[dict[str, Any]]:
	return [_row_state(row, "Contact Email", "email_ids", "email_id", ("is_primary",)) for row in _rows(contact, "email_ids")]


def _phone_state(contact: Any) -> list[dict[str, Any]]:
	return [_row_state(row, "Contact Phone", "phone_nos", "phone", ("is_primary_phone", "is_primary_mobile_no")) for row in _rows(contact, "phone_nos")]


def _affected_state(contact: Any, action: str) -> list[dict[str, Any]]:
	if action in {"add_email", "replace_primary_email", "set_primary_email"}:
		return _email_state(contact)
	if action in _COMMUNICATION_ACTIONS:
		return _phone_state(contact)
	return []


def _find_rows(rows: list[Any], value: str, *, flag: str | None = None) -> list[Any]:
	return [
		row for row in rows
		if _clean(_value(row, "email_id" if flag == "is_primary" else "phone")) == value
		and (flag is None or bool(_value(row, flag, 0)))
	]


def _find_email_rows(contact: Any, value: str, *, primary: bool | None = None) -> list[Any]:
	return [
		row for row in _rows(contact, "email_ids")
		if (_clean(_value(row, "email_id")) or "").casefold() == value.casefold()
		and (primary is None or bool(_value(row, "is_primary", 0)) == primary)
	]


def _find_phone_rows(contact: Any, value: str, *, flag: str | None = None) -> list[Any]:
	normalized = "".join(c for c in value if c.isalnum()).casefold()
	return [
		row for row in _rows(contact, "phone_nos")
		if "".join(c for c in str(_value(row, "phone") or "") if c.isalnum()).casefold() == normalized
		and (flag is None or bool(_value(row, flag, 0)))
	]


def _permission_error(doctype: str, action: str) -> dict[str, Any]:
	return _error("PERMISSION_DENIED", f"The authenticated user cannot {action} this {doctype}.")


def _validate_email(value: str) -> dict[str, Any] | None:
	parsed = validate_email_address(value, throw=False)
	if not parsed or "," in parsed:
		return _error("CONTACT_INVALID_EMAIL", "The Contact email is invalid.")
	return None


def _validate_phone(value: str) -> dict[str, Any] | None:
	if not validate_phone_number(value, throw=False):
		return _error("CONTACT_INVALID_PHONE", "The Contact phone is invalid.")
	return None


def _duplicate_failure(customer: Any, contact: Any, value: str, match: str) -> dict[str, Any] | None:
	for candidate in _search_contacts(value, customer, match):
		if _value(candidate, "name") != _value(contact, "name"):
			return _error("CONTACT_DUPLICATE_SUSPECTED", "A visible Contact in this Customer scope already matches the requested communication value.")
	return None


def _primary_values(contact: Any) -> dict[str, str | None]:
	emails = [row for row in _rows(contact, "email_ids") if _value(row, "is_primary", 0)]
	phones = [row for row in _rows(contact, "phone_nos") if _value(row, "is_primary_phone", 0)]
	mobiles = [row for row in _rows(contact, "phone_nos") if _value(row, "is_primary_mobile_no", 0)]
	return {
		"resulting_primary_email": _clean(_value(emails[0], "email_id")) if emails else None,
		"resulting_primary_phone": _clean(_value(phones[0], "phone")) if phones else None,
		"resulting_primary_mobile": _clean(_value(mobiles[0], "phone")) if mobiles else None,
	}


def _full_name(contact: Any, values: dict[str, Any] | None = None) -> str:
	values = values or {}
	parts = [values.get(field, _value(contact, field)) for field in ("first_name", "middle_name", "last_name", "company_name")]
	return " ".join(str(value).strip() for value in parts if _clean(value)) or str(_value(contact, "name"))


def _operation_preview(contact: Any, customer: Any, operation: dict[str, Any], *, idempotent: bool = False, selected: Any = None, proposed: str | None = None) -> dict[str, Any]:
	action = operation["action"]
	changed = {
		field: operation[field]
		for field in _DETAIL_FIELDS
		if field in operation and operation[field] is not None and operation[field] != _value(contact, field)
	}
	proposed_contact = copy.deepcopy(contact)
	if not idempotent:
		_apply_operation(proposed_contact, operation)
	return {
		"action": action,
		"customer": _customer_reference(customer),
		"contact": {"doctype": "Contact", "name": str(_value(contact, "name"))},
		"full_name_before": _clean(_value(contact, "full_name")) or str(_value(contact, "name")),
		"full_name_after": _full_name(proposed_contact),
		"changed_fields": changed,
		"selected_current_value": _clean(_value(selected, "email_id" if "email" in action else "phone")) if selected is not None else None,
		"proposed_value": proposed,
		"selected_row_is_primary": bool(_value(selected, "is_primary", 0)) if selected is not None and "email" in action else (bool(_value(selected, "is_primary_phone", 0) or _value(selected, "is_primary_mobile_no", 0)) if selected is not None else None),
		**_primary_values(proposed_contact),
		"customer_projection_refresh_required": _customer_primary(customer, contact),
		"crm_snapshot_refresh_may_occur": True,
		"other_party_link_count": 0,
		"idempotent": idempotent,
	}


def _prepare_operation(contact: Any, customer: Any, operation: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, Any | None, str | None]:
	action = operation.get("action")
	if action == "set_details":
		if not any(field in operation and operation[field] is not None for field in _DETAIL_FIELDS):
			return _error("CONTACT_INVALID_REQUEST", "At least one Contact detail field is required."), None, None, None
		invalid = {field: operation[field] for field in _DETAIL_FIELDS if field in operation and operation[field] is not None and operation[field] == _value(contact, field)}
		changed = {field: value for field, value in operation.items() if field in _DETAIL_FIELDS and value is not None and value != _value(contact, field)}
		return None, _operation_preview(contact, customer, operation, idempotent=not changed), None, None

	value_field = "email_id" if "email" in action else "phone"
	requested = operation.get("email") or operation.get("phone")
	if "email" in action:
		if failure := _validate_email(requested):
			return failure, None, None, None
	else:
		if failure := _validate_phone(requested):
			return failure, None, None, None

	selected = None
	if action == "add_email":
		if failure := _duplicate_failure(customer, contact, requested, "email"):
			return failure, None, None, None
		matches = _find_email_rows(contact, requested)
		if len(matches) > 1:
			return _error("CONTACT_EMAIL_AMBIGUOUS", "More than one matching Contact email exists."), None, None, None
		selected = matches[0] if matches else None
		idempotent = selected is not None and (not operation.get("make_primary") or bool(_value(selected, "is_primary", 0)))
	elif action == "add_phone":
		if failure := _duplicate_failure(customer, contact, requested, "phone"):
			return failure, None, None, None
		matches = _find_phone_rows(contact, requested)
		if len(matches) > 1:
			return _error("CONTACT_PHONE_AMBIGUOUS", "More than one matching Contact phone exists."), None, None, None
		selected = matches[0] if matches else None
		idempotent = selected is not None and (not operation.get("make_primary") or bool(_value(selected, "is_primary_phone" if operation["kind"] == "phone" else "is_primary_mobile_no", 0)))
	else:
		if action == "replace_primary_email":
			matches = _find_email_rows(contact, operation["current_email"], primary=True)
		elif action == "set_primary_email":
			matches = _find_email_rows(contact, requested)
		elif action == "replace_primary_phone":
			matches = _find_phone_rows(contact, operation["current_phone"], flag="is_primary_phone")
		elif action == "replace_primary_mobile":
			matches = _find_phone_rows(contact, operation["current_mobile"], flag="is_primary_mobile_no")
		elif action == "set_primary_phone":
			matches = _find_phone_rows(contact, requested)
		else:
			matches = _find_phone_rows(contact, requested)
		if not matches:
			code = "CONTACT_EMAIL_NOT_FOUND" if "email" in action else "CONTACT_PHONE_NOT_FOUND"
			return _error(code, "The selected Contact communication row was not found."), None, None, None
		if len(matches) > 1:
			code = "CONTACT_EMAIL_AMBIGUOUS" if "email" in action else "CONTACT_PHONE_AMBIGUOUS"
			return _error(code, "More than one matching Contact communication row exists."), None, None, None
		selected = matches[0]
		if failure := _duplicate_failure(customer, contact, requested, "email" if "email" in action else "phone"):
			return failure, None, None, None
		if action.startswith("replace_"):
			idempotent = _clean(_value(selected, value_field)) == requested
		else:
			flag = "is_primary" if action == "set_primary_email" else ("is_primary_phone" if action == "set_primary_phone" else "is_primary_mobile_no")
			idempotent = bool(_value(selected, flag, 0))
	return None, _operation_preview(contact, customer, operation, idempotent=idempotent, selected=selected, proposed=requested), selected, value_field


def _apply_operation(contact: Any, operation: dict[str, Any]) -> None:
	action = operation["action"]
	if action == "set_details":
		for field in _DETAIL_FIELDS:
			if operation.get(field) is not None:
				_set_value(contact, field, operation[field])
		return
	if action == "add_email":
		matches = _find_email_rows(contact, operation["email"])
		if matches:
			row = matches[0]
		else:
			rows = _rows(contact, "email_ids")
			row = {"doctype": "Contact Email", "email_id": operation["email"], "is_primary": 1 if not rows or operation.get("make_primary") else 0}
			if hasattr(contact, "append"):
				appended = contact.append("email_ids", row)
				if appended is not None:
					row = appended
			else:
				_rows(contact, "email_ids").append(row)
		if operation.get("make_primary"):
			for existing in _rows(contact, "email_ids"):
				_set_value(existing, "is_primary", 1 if existing is row else 0)
		return
	if action == "add_phone":
		matches = _find_phone_rows(contact, operation["phone"])
		if matches:
			row = matches[0]
		else:
			row = {"doctype": "Contact Phone", "phone": operation["phone"]}
			if operation.get("make_primary"):
				_set_value(row, "is_primary_phone" if operation["kind"] == "phone" else "is_primary_mobile_no", 1)
			if hasattr(contact, "append"):
				appended = contact.append("phone_nos", row)
				if appended is not None:
					row = appended
			else:
				_rows(contact, "phone_nos").append(row)
		if operation.get("make_primary"):
			flag = "is_primary_phone" if operation["kind"] == "phone" else "is_primary_mobile_no"
			for existing in _rows(contact, "phone_nos"):
				_set_value(existing, flag, 1 if existing is row else 0)
		return
	if action in {"replace_primary_email", "replace_primary_phone", "replace_primary_mobile"}:
		matches = _find_email_rows(contact, operation["current_email"], primary=True) if action == "replace_primary_email" else _find_phone_rows(contact, operation.get("current_phone") or operation.get("current_mobile"), flag="is_primary_phone" if action == "replace_primary_phone" else "is_primary_mobile_no")
		if matches:
			_set_value(matches[0], "email_id" if "email" in action else "phone", operation.get("email") or operation["phone"])
		return
	if action == "set_primary_email":
		for row in _rows(contact, "email_ids"):
			_set_value(row, "is_primary", 1 if row is _find_email_rows(contact, operation["email"])[0] else 0)
		return
	flag = "is_primary_phone" if action == "set_primary_phone" else "is_primary_mobile_no"
	selected = _find_phone_rows(contact, operation["phone"])[0]
	for row in _rows(contact, "phone_nos"):
		_set_value(row, flag, 1 if row is selected else 0)


def _confirmation_failure(state: str) -> dict[str, Any]:
	code, message, retryable = confirmation_failure(state, "Customer Contact update")
	return _error(code, message, retryable=retryable)


def _stale(message: str = "The Contact or Customer changed after preparation. Please prepare again.") -> dict[str, Any]:
	return _error("CONTACT_STALE_STATE", message, retryable=True)


def prepare_contact_update(request: dict[str, Any]) -> dict[str, Any]:
	approvals.prune_expired()
	user = _current_user()
	customer_ref = request.get("customer") or {}
	contact_ref = request.get("contact") or {}
	if customer_ref.get("doctype") != "Customer":
		return _error("CUSTOMER_NOT_FOUND", "Only Customer references are supported.")
	if contact_ref.get("doctype") != "Contact":
		return _error("CONTACT_NOT_FOUND", "Only Contact references are supported.")
	customer, failure = _load_customer(customer_ref.get("name", ""))
	if failure:
		return failure
	contact, failure = _load_contact(contact_ref.get("name", ""), "read")
	if failure:
		return failure
	assert customer is not None and contact is not None
	if not contact.has_permission("write"):
		return _permission_error("Contact", "write")
	if not _has_customer_link(contact, _value(customer, "name")):
		return _error("CONTACT_NOT_LINKED_TO_CUSTOMER", "The selected Contact is not linked to the selected Customer.")
	if shared := _shared_failure(contact, _value(customer, "name")):
		return shared
	primary = _customer_primary(customer, contact)
	if primary and not customer.has_permission("write"):
		return _error("CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED", "Customer write permission is required to refresh its Contact projections.")
	operation = dict(request.get("operation") or {})
	failure, preview, selected, _value_field = _prepare_operation(contact, customer, operation)
	if failure:
		return failure
	assert preview is not None
	row_state = _affected_state(contact, operation["action"])
	payload = {
		"profile": _PROFILE,
		"customer_name": str(_value(customer, "name")),
		"customer_modified": str(_value(customer, "modified")),
		"contact_name": str(_value(contact, "name")),
		"contact_modified": str(_value(contact, "modified")),
		"relationship_state": _relationship_state(contact, _value(customer, "name")),
		"customer_primary": primary,
		"operation": operation,
		"affected_rows": row_state,
		"child_fingerprint": stable_fingerprint(row_state),
		"duplicate_fingerprint": stable_fingerprint({"action": operation["action"], "target": operation.get("email") or operation.get("phone")}),
	}
	token = approvals.create(action=_ACTION, site=frappe.local.site, user=user, payload=payload)
	return {
		"status": "ready",
		"approval_token": token,
		"expires_in_seconds": APPROVAL_TTL_SECONDS,
		"preview": preview,
	}


def confirm_contact_update(approval_token: str, confirm: bool) -> dict[str, Any]:
	if not confirm:
		return _error("CONFIRMATION_REQUIRED", "Review the Contact update before confirming it.")
	user = _current_user()
	approval, state = approvals.claim_for_confirm_write(approval_token, action=_ACTION, site=frappe.local.site, user=user)
	if state != "available" or approval is None:
		return _confirmation_failure(state)
	payload = approval.payload
	if payload.get("profile") != _PROFILE:
		return _error("CONFIRMATION_UNAVAILABLE", "This Contact update belongs to another profile.")
	customer, failure = _load_customer(payload.get("customer_name", ""))
	if failure:
		return failure
	contact, failure = _load_contact(payload.get("contact_name", ""), "read")
	if failure:
		return failure
	assert customer is not None and contact is not None
	if not contact.has_permission("write"):
		return _permission_error("Contact", "write")
	if not _has_customer_link(contact, payload["customer_name"]):
		return _stale("The Customer link was removed after preparation.")
	if shared := _shared_failure(contact, payload["customer_name"]):
		return _stale("The Contact became shared after preparation.") | {"reference": shared["reference"]}
	primary = _customer_primary(customer, contact)
	if primary != payload.get("customer_primary"):
		return _stale("The Customer primary Contact changed after preparation.")
	if primary and not customer.has_permission("write"):
		return _error("CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED", "Customer write permission is required to refresh its Contact projections.")
	if str(_value(customer, "modified")) != payload.get("customer_modified") or str(_value(contact, "modified")) != payload.get("contact_modified"):
		return _stale()
	if stable_fingerprint(_relationship_state(contact, payload["customer_name"])) != stable_fingerprint(payload["relationship_state"]):
		return _stale()
	if stable_fingerprint(_affected_state(contact, payload["operation"]["action"])) != payload.get("child_fingerprint"):
		return _error("CONTACT_CHILD_STALE_STATE", "The selected Contact communication rows changed after preparation.", retryable=True)
	failure, preview, _selected, _value_field = _prepare_operation(contact, customer, payload["operation"])
	if failure:
		return _stale("The approved Contact update is no longer applicable.") if failure.get("code") in {"CONTACT_DUPLICATE_SUSPECTED", "CONTACT_EMAIL_AMBIGUOUS", "CONTACT_PHONE_AMBIGUOUS"} else failure
	assert preview is not None
	try:
		if not preview["idempotent"]:
			_apply_operation(contact, payload["operation"])
			contact.save(ignore_permissions=False)
			if primary:
				customer.save(ignore_permissions=False)
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		return _permission_error("Contact", "write")
	except Exception:
		frappe.db.rollback()
		return _error("CONTACT_UPDATE_FAILED", "Native Contact update failed.", retryable=True)
	preview["full_name_after"] = _clean(_value(contact, "full_name")) or str(_value(contact, "name"))
	preview.update(_primary_values(contact))
	return {"status": "updated", "customer": _customer_reference(customer), "contact": _projection(contact, _value(customer, "name")), "preview": preview, "idempotent": bool(preview["idempotent"])}
