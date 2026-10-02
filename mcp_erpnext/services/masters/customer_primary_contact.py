"""Safe, Customer-scoped promotion of an existing native Contact."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.contacts.doctype.contact.contact import get_contacts_linking_to

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...observability import new_error_reference
from ..common.fingerprint import stable_fingerprint
from .customer_contact import _customer_reference, _error, _load_contact, _load_customer, _projection

_ACTION = "customer_primary_contact"


def _stale(message: str = "The Customer primary Contact state changed after preparation. Please prepare again.") -> dict[str, Any]:
	return _error("CUSTOMER_PRIMARY_CONTACT_STALE", message, retryable=True)


def _permission(doctype: str, action: str) -> dict[str, Any]:
	return _error("PERMISSION_DENIED", f"The authenticated user cannot {action} this {doctype}.")


def _current_user() -> str:
	user = getattr(frappe.session, "user", None)
	if not user or user in {"Guest", "guest"}:
		frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
	return user


def _value(document: Any, fieldname: str, default: Any = None) -> Any:
	getter = getattr(document, "get", None)
	if callable(getter):
		return getter(fieldname, default)
	return getattr(document, fieldname, default)


def _links(contact: Any) -> list[tuple[str, str]]:
	return sorted(
		(str(_value(row, "link_doctype", "")), str(_value(row, "link_name", "")))
		for row in list(_value(contact, "links", []) or [])
	)


def _single_customer_link(contact: Any, customer_name: str) -> bool:
	return _links(contact) == [("Customer", customer_name)]


def _contact_snapshot(contact: Any) -> dict[str, Any]:
	return {
		"name": str(_value(contact, "name")),
		"modified": str(_value(contact, "modified", "")),
		"is_primary_contact": bool(_value(contact, "is_primary_contact", 0)),
		"links": _links(contact),
	}


def _linked_contacts(customer: Any) -> tuple[list[Any], dict[str, Any] | None]:
	"""Load all Customer-linked Contacts through the permission-aware list path."""
	try:
		rows = get_contacts_linking_to("Customer", customer.name, fields=["name"])
	except frappe.PermissionError:
		return [], _permission("Contact", "read")
	contacts = []
	for row in rows:
		name = _value(row, "name")
		contact, failure = _load_contact(str(name), "read")
		if failure:
			return [], failure
		assert contact is not None
		contacts.append(contact)
	return contacts, None


def _primary_state(customer: Any, contacts: list[Any]) -> tuple[list[Any], str]:
	primaries = [contact for contact in contacts if bool(_value(contact, "is_primary_contact", 0))]
	state = stable_fingerprint(
		{
			"customer": {
				"name": str(_value(customer, "name")),
				"modified": str(_value(customer, "modified", "")),
				"customer_primary_contact": _value(customer, "customer_primary_contact"),
			},
			"contacts": [_contact_snapshot(contact) for contact in sorted(contacts, key=lambda item: str(_value(item, "name")))],
		}
	)
	return primaries, state


def _validate_state(customer: Any, selected: Any, contacts: list[Any]) -> tuple[Any | None, bool, dict[str, Any] | None]:
	customer_name = str(_value(customer, "name"))
	selected_name = str(_value(selected, "name"))
	if not selected.has_link("Customer", customer_name):
		return None, False, _error("CONTACT_NOT_LINKED_TO_CUSTOMER", "The selected Contact is not linked to this Customer.")
	if not _single_customer_link(selected, customer_name):
		return None, False, _error("CONTACT_SHARED_WITH_OTHER_PARTIES", "The selected Contact has additional relationships and cannot be promoted in V1.")

	primaries, _ = _primary_state(customer, contacts)
	pointer = _value(customer, "customer_primary_contact")
	by_name = {str(_value(contact, "name")): contact for contact in contacts}
	if len(primaries) > 1:
		return None, False, _error("CONTACT_PRIMARY_STATE_INCONSISTENT", "The Customer has multiple primary Contacts.", retryable=True)
	if not pointer:
		if primaries:
			return None, False, _error("CONTACT_PRIMARY_STATE_INCONSISTENT", "The Customer has a primary Contact but no primary pointer.", retryable=True)
		return None, False, None
	if pointer == selected_name:
		if by_name.get(pointer) is not selected or not bool(_value(selected, "is_primary_contact", 0)) or len(primaries) != 1:
			return None, False, _error("CONTACT_PRIMARY_STATE_INCONSISTENT", "The Customer primary pointer and Contact primary flag disagree.", retryable=True)
		return None, True, None

	old = by_name.get(str(pointer))
	if old is None or not old.has_link("Customer", customer_name) or not bool(_value(old, "is_primary_contact", 0)) or len(primaries) != 1:
		return None, False, _error("CONTACT_PRIMARY_STATE_INCONSISTENT", "The Customer primary pointer does not identify a coherent linked primary Contact.", retryable=True)
	if not _single_customer_link(old, customer_name):
		return None, False, _error("PRIMARY_CONTACT_PROMOTION_UNSAFE", "The current primary Contact has additional relationships and cannot be safely demoted in V1.", retryable=True)
	return old, False, None


def _confirm_failure(state: str) -> dict[str, Any]:
	code, message, retryable = confirmation_failure(state, "Customer primary Contact")
	return _error(code, message, retryable=retryable)


def _result(customer: Any, selected: Any, old: Any | None, *, idempotent: bool) -> dict[str, Any]:
	return {
		"status": "already_primary" if idempotent else "promoted",
		"customer": _customer_reference(customer),
		"primary_contact": _projection(selected, customer.name),
		"previous_primary_contact": {"doctype": "Contact", "name": str(_value(old, "name"))} if old else None,
		"customer_primary_contact": {"doctype": "Contact", "name": str(_value(selected, "name"))},
		"email_id": _value(customer, "email_id"),
		"mobile_no": _value(customer, "mobile_no"),
		"first_name": _value(customer, "first_name"),
		"last_name": _value(customer, "last_name"),
		"idempotent": idempotent,
	}


def prepare_customer_primary_contact(request: dict[str, Any]) -> dict[str, Any]:
	"""Prepare an existing single-Customer Contact promotion without writing."""
	approvals.prune_expired()
	user = _current_user()
	if request.get("customer", {}).get("doctype") != "Customer" or request.get("contact", {}).get("doctype") != "Contact":
		return _error("CUSTOMER_NOT_FOUND", "Customer and Contact references are required.")
	customer, failure = _load_customer(request["customer"].get("name", ""))
	if failure:
		return failure
	assert customer is not None
	if not customer.has_permission("write"):
		return _permission("Customer", "write")
	selected, failure = _load_contact(request["contact"].get("name", ""), "read")
	if failure:
		return failure
	assert selected is not None
	if not selected.has_permission("write"):
		return _permission("Contact", "write")
	contacts, failure = _linked_contacts(customer)
	if failure:
		return failure
	if str(_value(selected, "name")) not in {str(_value(contact, "name")) for contact in contacts}:
		contacts.append(selected)
	old, already, failure = _validate_state(customer, selected, contacts)
	if failure:
		return failure
	if old is not None and not old.has_permission("read"):
		return _permission("Contact", "read")
	_, state_fingerprint = _primary_state(customer, contacts)
	approval_payload = {
		"customer": {"name": str(_value(customer, "name")), "modified": str(_value(customer, "modified", "")), "primary": _value(customer, "customer_primary_contact")},
		"selected": _contact_snapshot(selected),
		"old": _contact_snapshot(old) if old else None,
		"primary_state_fingerprint": state_fingerprint,
	}
	token = approvals.create(action=_ACTION, site=frappe.local.site, user=user, payload=approval_payload)
	return {
		"status": "ready",
		"approval_token": token,
		"expires_in_seconds": APPROVAL_TTL_SECONDS,
		"preview": {
			"action": "promote_customer_primary_contact",
			"customer": _customer_reference(customer),
			"contact": {"doctype": "Contact", "name": str(_value(selected, "name"))},
			"current_primary_contact": {"doctype": "Contact", "name": str(_value(old, "name"))} if old else None,
			"selected_contact_already_primary": already,
			"customer_pointer_is_selected": _value(customer, "customer_primary_contact") == _value(selected, "name"),
			"selected_additional_link_count": 0,
			"old_primary_relationship_safe": True,
			"native_side_effect_note": "Native Contact save demotes linked primary Contacts; native Customer save refreshes Customer Contact projections.",
		},
	}


def confirm_customer_primary_contact(approval_token: str, confirm: bool) -> dict[str, Any]:
	"""Apply one approved promotion in a single Contact-then-Customer transaction."""
	user = _current_user()
	if not confirm:
		approvals.cancel(approval_token, action=_ACTION, site=frappe.local.site, user=user)
		return _error("CONFIRMATION_REQUIRED", "Review the Customer primary Contact operation before confirming it.")
	approval, state = approvals.claim_for_confirm_write(approval_token, action=_ACTION, site=frappe.local.site, user=user)
	if state != "available" or approval is None:
		return _confirm_failure(state)
	payload = approval.payload
	customer, failure = _load_customer(payload["customer"]["name"])
	if failure:
		return failure
	assert customer is not None
	if not customer.has_permission("write"):
		return _permission("Customer", "write")
	selected, failure = _load_contact(payload["selected"]["name"], "read")
	if failure:
		return failure
	assert selected is not None
	if not selected.has_permission("write"):
		return _permission("Contact", "write")
	contacts, failure = _linked_contacts(customer)
	if failure:
		return failure
	if str(_value(selected, "name")) not in {str(_value(contact, "name")) for contact in contacts}:
		contacts.append(selected)
	old, already, failure = _validate_state(customer, selected, contacts)
	if failure:
		return failure
	_, current_state = _primary_state(customer, contacts)
	current_old = _contact_snapshot(old) if old else None
	if (
		str(_value(customer, "modified", "")) != payload["customer"]["modified"]
		or _value(customer, "customer_primary_contact") != payload["customer"]["primary"]
		or _contact_snapshot(selected) != payload["selected"]
		or current_old != payload["old"]
		or current_state != payload["primary_state_fingerprint"]
	):
		return _stale()
	if already:
		return _result(customer, selected, None, idempotent=True)
	try:
		selected.is_primary_contact = 1
		selected.save(ignore_permissions=False)
		if old is not None:
			fresh_old, old_failure = _load_contact(old.name, "read")
			if old_failure or fresh_old is None or bool(_value(fresh_old, "is_primary_contact", 0)):
				frappe.db.rollback()
				return _error("PRIMARY_CONTACT_PROMOTION_UNSAFE", "Native Contact promotion did not demote the previous primary Contact.", retryable=True)
		customer.customer_primary_contact = selected.name
		customer.save(ignore_permissions=False)
		if not bool(_value(selected, "is_primary_contact", 0)) or _value(customer, "customer_primary_contact") != selected.name:
			frappe.db.rollback()
			return _error("PRIMARY_CONTACT_PROMOTION_UNSAFE", "Native promotion did not produce the expected primary state.", retryable=True)
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		return _permission("Contact", "write")
	except Exception:
		frappe.db.rollback()
		return _error("PRIMARY_CONTACT_PROMOTION_FAILED", "Native Customer primary Contact promotion failed.", retryable=True)
	return _result(customer, selected, old, idempotent=False)
