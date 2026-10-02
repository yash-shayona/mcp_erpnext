"""Permission-aware Customer-linked Contact search and two-phase writes."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.contacts.doctype.contact.contact import get_contacts_linking_to
from frappe.utils import validate_email_address, validate_phone_number

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...observability import new_error_reference
from ..common.entity_resolution import normalize
from ..common.fingerprint import stable_fingerprint
from ..common.write_policy import approval_entry_failure, current_mode, direct_entry_failure, disabled_failure, exact_mode_failure
from ...settings import WriteMode

_CREATE_ACTION = "customer_contact_create"
_LINK_ACTION = "customer_contact_link"
_MAX_SEARCH_ROWS = 200
_CONTACT_FIELDS = ["name", "full_name", "company_name", "email_id", "mobile_no", "phone", "is_primary_contact"]


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
	return {
		"status": "error",
		"code": code,
		"message": message,
		"reference": new_error_reference(),
		"retryable": retryable,
	}


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


def _value(document: Any, fieldname: str, default: Any = None) -> Any:
	getter = getattr(document, "get", None)
	if callable(getter):
		return getter(fieldname, default)
	return getattr(document, fieldname, default)


def _customer_reference(customer: Any) -> dict[str, str]:
	return {"doctype": "Customer", "name": str(_value(customer, "name"))}


def _load_customer(name: str) -> tuple[Any | None, dict[str, Any] | None]:
	try:
		customer = frappe.get_doc("Customer", name)
	except frappe.DoesNotExistError:
		return None, _error("CUSTOMER_NOT_FOUND", "The selected Customer was not found.")
	except frappe.PermissionError:
		return None, _error("PERMISSION_DENIED", "The authenticated user cannot read this Customer.")
	if not customer or not customer.has_permission("read"):
		return None, _error("PERMISSION_DENIED", "The authenticated user cannot read this Customer.")
	return customer, None


def _load_contact(name: str, permission: str = "read") -> tuple[Any | None, dict[str, Any] | None]:
	try:
		contact = frappe.get_doc("Contact", name)
	except frappe.DoesNotExistError:
		return None, _error("CONTACT_NOT_FOUND", "The selected Contact was not found.")
	except frappe.PermissionError:
		return None, _error("PERMISSION_DENIED", "The authenticated user cannot read this Contact.")
	if not contact or not contact.has_permission(permission):
		return None, _error("PERMISSION_DENIED", "The authenticated user cannot access this Contact.")
	return contact, None


def _links(contact: Any) -> list[Any]:
	return list(_value(contact, "links", []) or [])


def _link_value(link: Any, fieldname: str) -> Any:
	return _value(link, fieldname)


def _has_customer_link(contact: Any, customer_name: str) -> bool:
	return any(
		_link_value(link, "link_doctype") == "Customer"
		and _link_value(link, "link_name") == customer_name
		for link in _links(contact)
	)


def _projection(contact: Any, customer_name: str | None = None) -> dict[str, Any]:
	links = _links(contact)
	linked = bool(customer_name and _has_customer_link(contact, customer_name))
	other_party_link_count = sum(
		1
		for link in links
		if not (
			customer_name
			and _link_value(link, "link_doctype") == "Customer"
			and _link_value(link, "link_name") == customer_name
		)
	)
	name = _clean(_value(contact, "name")) or "Contact"
	return {
		"doctype": "Contact",
		"name": name,
		"full_name": _clean(_value(contact, "full_name")) or name,
		"company_name": _clean(_value(contact, "company_name")),
		"email_id": _clean(_value(contact, "email_id")),
		"mobile_no": _clean(_value(contact, "mobile_no")),
		"phone": _clean(_value(contact, "phone")),
		"is_primary_contact": bool(_value(contact, "is_primary_contact", 0)),
		"linked_to_target_customer": linked,
		"other_party_link_count": other_party_link_count,
	}


def _normalised_phone(value: Any) -> str:
	return "".join(character for character in str(value or "") if character.isalnum()).casefold()


def _child_values(contact: Any, fieldname: str, value_field: str) -> list[str]:
	return [
		str(_value(row, value_field)).strip()
		for row in list(_value(contact, fieldname, []) or [])
		if _clean(_value(row, value_field))
	]


def _matches(contact: Any, query: str, match: str, *, customer_scoped: bool) -> bool:
	query_text = query.strip()
	query_normalized = normalize(query_text)
	name_values = [str(_value(contact, "name", "")), str(_value(contact, "full_name", ""))]
	emails = [_value(contact, "email_id")] + _child_values(contact, "email_ids", "email_id")
	phones = [_value(contact, "mobile_no"), _value(contact, "phone")]
	phones.extend(_child_values(contact, "phone_nos", "phone"))

	name_match = (
		any(query_normalized in normalize(value) for value in name_values if value)
		if customer_scoped
		else any(query_text.casefold() == value.casefold() for value in name_values if value)
	)
	email_match = any(str(value or "").strip().casefold() == query_text.casefold() for value in emails)
	phone_match = any(_normalised_phone(value) == _normalised_phone(query_text) for value in phones)

	if match == "name":
		return name_match
	if match == "email":
		return email_match
	if match == "phone":
		return phone_match
	return name_match or email_match or phone_match if customer_scoped else email_match or phone_match or name_match


def _child_parent_names(
	doctype: str, fieldname: str, query: str, *, phone: bool = False
) -> set[str]:
	filters: dict[str, Any]
	if phone:
		filters = {fieldname: ["like", f"%{query.strip()}%"]}
	else:
		filters = {fieldname: query.strip()}
	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=["parent", fieldname],
		parent_doctype="Contact",
		limit_page_length=_MAX_SEARCH_ROWS,
		ignore_permissions=False,
	)
	result = set()
	for row in rows:
		value = row.get(fieldname)
		matches = (
			_normalised_phone(value) == _normalised_phone(query)
			if phone
			else str(value or "").strip().casefold() == query.strip().casefold()
		)
		if matches and row.get("parent"):
			result.add(row["parent"])
	return result


def _search_contacts(
	query: str,
	customer: Any | None,
	match: str,
) -> list[Any]:
	if customer is not None:
		rows = get_contacts_linking_to("Customer", customer.name, fields=_CONTACT_FIELDS)
		contacts: list[Any] = []
		for row in rows[:_MAX_SEARCH_ROWS]:
			name = _clean(row.get("name"))
			if not name:
				continue
			contact, failure = _load_contact(name)
			if contact is not None and failure is None and _matches(contact, query, match, customer_scoped=True):
				contacts.append(contact)
		return contacts

	parent_names: set[str] = set()
	if match in {"auto", "name"}:
		parent_names.update(
			row.get("name")
			for row in frappe.get_list(
				"Contact",
				filters={"name": query.strip()},
				fields=["name"],
				limit_page_length=1,
				ignore_permissions=False,
			)
			if row.get("name")
		)
	if match in {"auto", "email"}:
		parent_names.update(_child_parent_names("Contact Email", "email_id", query))
	if match in {"auto", "phone"}:
		parent_names.update(_child_parent_names("Contact Phone", "phone", query, phone=True))

	contacts = []
	for name in sorted(parent_names):
		contact, failure = _load_contact(name)
		if contact is not None and failure is None and _matches(contact, query, match, customer_scoped=False):
			contacts.append(contact)
	return contacts


def search_contacts(
	query: str,
	customer: dict[str, Any] | None = None,
	match: str = "auto",
	limit: int = 20,
	offset: int = 0,
) -> dict[str, Any]:
	"""Search only permission-visible Contacts; fuzzy names require Customer context."""
	_current_user()
	customer_doc = None
	if customer is not None:
		if customer.get("doctype") != "Customer":
			return _error("CUSTOMER_NOT_FOUND", "Only Customer references are supported.")
		customer_doc, failure = _load_customer(customer.get("name", ""))
		if failure:
			return failure
	if customer_doc is None and match == "name":
		# Global name search is intentionally exact to prevent personal-data enumeration.
		pass
	contacts = _search_contacts(query, customer_doc, match)
	contacts.sort(key=lambda contact: str(_value(contact, "name", "")))
	projected = [_projection(contact, _value(customer_doc, "name") if customer_doc else None) for contact in contacts]
	return {
		"status": "ok",
		"doctype": "Contact",
		"query": query,
		"contacts": projected[offset : offset + limit],
		"count": len(projected),
		"limit": limit,
		"offset": offset,
	}


def _permission_error(doctype: str, action: str) -> dict[str, Any]:
	return _error("PERMISSION_DENIED", f"The authenticated user cannot {action} this {doctype}.")


def _validate_new_contact(values: dict[str, Any]) -> dict[str, Any] | None:
	if not any(values.get(fieldname) for fieldname in ("first_name", "last_name", "company_name")):
		return _error(
			"CONTACT_INVALID_IDENTITY",
			"A new Contact needs first_name, last_name, or company_name.",
		)
	if values.get("email"):
		parsed = validate_email_address(values["email"], throw=False)
		if not parsed or "," in parsed:
			return _error("CONTACT_INVALID_EMAIL", "The Contact email is invalid.")
		values["email"] = parsed
	if values.get("mobile") and not validate_phone_number(values["mobile"], throw=False):
		return _error("CONTACT_INVALID_PHONE", "The Contact mobile number is invalid.")
	return None


def _new_contact_payload(customer_name: str, values: dict[str, Any]) -> dict[str, Any]:
	payload: dict[str, Any] = {
		"doctype": "Contact",
		"links": [{"link_doctype": "Customer", "link_name": customer_name}],
	}
	for fieldname in ("first_name", "middle_name", "last_name", "company_name"):
		if values.get(fieldname):
			payload[fieldname] = values[fieldname]
	if values.get("email"):
		payload["email_ids"] = [{"email_id": values["email"], "is_primary": 1}]
	if values.get("mobile"):
		payload["phone_nos"] = [{"phone": values["mobile"], "is_primary_mobile_no": 1}]
	return payload


def _duplicate_contacts(customer: Any, values: dict[str, Any]) -> list[dict[str, Any]]:
	candidates: dict[str, Any] = {}
	for match, fieldname in (("email", "email"), ("phone", "mobile")):
		value = values.get(fieldname)
		if not value:
			continue
		for contact in _search_contacts(value, customer, match):
			candidates[str(_value(contact, "name"))] = contact
	return [_projection(contact, customer.name) for contact in candidates.values()]


def _stale(code: str, message: str) -> dict[str, Any]:
	return _error(code, message, retryable=True)


def _confirmation_failure(state: str) -> dict[str, Any]:
	code, message, retryable = confirmation_failure(state, "Customer Contact")
	return _error(code, message, retryable=retryable)


def prepare_customer_contact(request: dict[str, Any], *, _direct_execution: bool = False) -> dict[str, Any]:
	"""Prepare a bounded native Contact create or explicit link without writing."""
	mode = request.get("mode")
	if mode == "create" and not _direct_execution and (failure := disabled_failure("create")):
		return _error(failure.code, failure.message)
	user = _current_user()
	if request.get("customer", {}).get("doctype") != "Customer":
		return _error("CUSTOMER_NOT_FOUND", "Only Customer references are supported.")
	customer, failure = _load_customer(request["customer"].get("name", ""))
	if failure:
		return failure
	assert customer is not None
	if mode == "link":
		approvals.prune_expired()
	if request.get("make_primary"):
		return _error(
			"CONTACT_PRIMARY_UNSUPPORTED",
			"Primary Contact promotion is deferred; create or link the Contact without make_primary.",
		)
	if mode == "create":
		if request.get("existing_contact") is not None or request.get("new_contact") is None:
			return _error("CONTACT_INVALID_REQUEST", "Create mode requires only new_contact.")
		if not frappe.has_permission("Contact", "create"):
			return _permission_error("Contact", "create")
		values = {
			fieldname: _clean(request["new_contact"].get(fieldname))
			for fieldname in ("first_name", "middle_name", "last_name", "company_name", "email", "mobile")
		}
		if validation_failure := _validate_new_contact(values):
			return validation_failure
		if duplicates := _duplicate_contacts(customer, values):
			return _error("CONTACT_DUPLICATE_SUSPECTED", "An exact visible Contact already matches this identity.") | {"candidates": duplicates}
		payload = _new_contact_payload(customer.name, values)
		# Native validation derives full_name and the parent email/phone projections without a write.
		try:
			preview_doc = frappe.get_doc(payload)
			preview_doc.run_method("validate")
		except Exception:
			return _error("CONTACT_INVALID_DATA", "Native Contact validation rejected the proposed Contact.")
		fingerprint = stable_fingerprint(
			{
				"mode": mode,
				"customer": {"name": customer.name, "modified": str(customer.modified)},
				"new_contact": values,
				"duplicates": [],
			}
		)
		approval_payload = {
			"mode": mode,
			"customer_name": customer.name,
			"customer_modified": str(customer.modified),
			"new_contact": values,
			"fingerprint": fingerprint,
		}
		preview = {
			"action": "create",
			"customer": _customer_reference(customer),
			"customer_name": customer.customer_name,
			"new_contact": values,
			"make_primary": False,
		}
		# Internal direct planning never enters the approval-backed prepare branch.
		if _direct_execution:
			return {"status": "ready", "preview": preview, "_direct_values": values, "_customer_name": customer.name}
		if current_mode("create") is WriteMode.DIRECT:
			return {"status": "preview", "preview": preview}
	else:
		if mode != "link" or request.get("new_contact") is not None or request.get("existing_contact") is None:
			return _error("CONTACT_INVALID_REQUEST", "Link mode requires only existing_contact.")
		if not frappe.has_permission("Contact", "write"):
			return _permission_error("Contact", "write")
		existing = request["existing_contact"]
		if existing.get("doctype") != "Contact":
			return _error("CONTACT_NOT_FOUND", "Only Contact references are supported.")
		contact, failure = _load_contact(existing.get("name", ""), "read")
		if failure:
			return failure
		assert contact is not None
		if not contact.has_permission("write"):
			return _permission_error("Contact", "write")
		already_linked = _has_customer_link(contact, customer.name)
		approval_payload = {
			"mode": mode,
			"customer_name": customer.name,
			"customer_modified": str(customer.modified),
			"contact_name": contact.name,
			"contact_modified": str(contact.modified),
			"already_linked": already_linked,
			"fingerprint": stable_fingerprint(
				{
					"mode": mode,
					"customer": {"name": customer.name, "modified": str(customer.modified)},
					"contact": {"name": contact.name, "modified": str(contact.modified), "linked": already_linked},
				}
			),
		}
		preview = {
			"action": "link",
			"customer": _customer_reference(customer),
			"customer_name": customer.customer_name,
			"contact": _projection(contact, customer.name),
			"already_linked": already_linked,
		}

	action = _CREATE_ACTION if mode == "create" else _LINK_ACTION
	if mode == "create":
		approvals.prune_expired()
	token = approvals.create(action=action, site=frappe.local.site, user=user, payload=approval_payload)
	return {
		"status": "ready",
		"approval_token": token,
		"expires_in_seconds": APPROVAL_TTL_SECONDS,
		"preview": preview,
	}


def _link_result(customer: Any, contact: Any, *, idempotent: bool) -> dict[str, Any]:
	return {
		"status": "linked",
		"customer": _customer_reference(customer),
		"contact": _projection(contact, customer.name),
		"idempotent": idempotent,
		"primary": None,
	}


def confirm_customer_contact(approval_token: str, confirm: bool) -> dict[str, Any]:
	"""Execute exactly one approved native Contact operation."""
	user = _current_user()
	create_approval, create_state = approvals.lookup(
		approval_token, action=_CREATE_ACTION, site=frappe.local.site, user=user
	)
	link_approval, link_state = approvals.lookup(
		approval_token, action=_LINK_ACTION, site=frappe.local.site, user=user
	)
	is_create = create_approval is not None and create_state == "available"
	if is_create:
		if failure := approval_entry_failure("create"):
			return _error(failure.code, failure.message)
	elif link_approval is None or link_state != "available":
		return _confirmation_failure(create_state if create_state != "unavailable" else link_state)
	action = _CREATE_ACTION if is_create else _LINK_ACTION
	if not confirm:
		approvals.cancel(approval_token, action=action, site=frappe.local.site, user=user)
		return _error("CONFIRMATION_REQUIRED", "Review the Contact operation before confirming it.")
	approval, state = approvals.claim_for_confirm_write(
		approval_token, action=action, site=frappe.local.site, user=user
	)
	if state != "available" or approval is None:
		return _confirmation_failure(state)
	payload = approval.payload
	customer, failure = _load_customer(payload.get("customer_name", ""))
	if failure:
		return failure
	assert customer is not None
	if payload.get("mode") == "create":
		if not frappe.has_permission("Contact", "create"):
			return _permission_error("Contact", "create")
		if str(customer.modified) != payload.get("customer_modified"):
			return _stale("CONTACT_STALE_STATE", "The Customer changed after Contact preparation. Please prepare again.")
		values = dict(payload.get("new_contact") or {})
		if duplicates := _duplicate_contacts(customer, values):
			return _error("CONTACT_DUPLICATE_SUSPECTED", "An exact visible Contact appeared after preparation.") | {"candidates": duplicates}
		try:
			contact = frappe.get_doc(_new_contact_payload(customer.name, values))
			if failure := exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED):
				return _error(failure.code, failure.message)
			contact.insert(ignore_permissions=False)
			frappe.db.commit()
		except frappe.PermissionError:
			frappe.db.rollback()
			return _permission_error("Contact", "create")
		except Exception:
			frappe.db.rollback()
			return _error("CONTACT_CREATE_FAILED", "Native Contact creation failed.", retryable=True)
		return {
			"status": "created",
			"customer": _customer_reference(customer),
			"contact": _projection(contact, customer.name),
			"idempotent": False,
			"primary": {"requested": False, "applied": False, "customer_primary_contact_updated": False},
		}

	contact, failure = _load_contact(payload.get("contact_name", ""), "read")
	if failure:
		return failure
	assert contact is not None
	if not contact.has_permission("write"):
		return _permission_error("Contact", "write")
	if _has_customer_link(contact, customer.name):
		return _link_result(customer, contact, idempotent=True)
	if str(customer.modified) != payload.get("customer_modified"):
		return _stale("CONTACT_STALE_STATE", "The Customer changed after Contact preparation. Please prepare again.")
	if str(contact.modified) != payload.get("contact_modified"):
		return _stale("CONTACT_LINK_STALE_STATE", "The Contact changed after link preparation. Please prepare again.")
	try:
		contact.append("links", {"link_doctype": "Customer", "link_name": customer.name})
		contact.save(ignore_permissions=False)
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		return _permission_error("Contact", "write")
	except Exception:
		frappe.db.rollback()
		return _error("CONTACT_LINK_FAILED", "Native Contact linking failed.", retryable=True)
	return _link_result(customer, contact, idempotent=False)


def execute_customer_contact(request: dict[str, Any]) -> dict[str, Any]:
	"""Directly create a new Customer-linked Contact after fresh bounded planning."""
	if request.get("mode") != "create":
		return _error("DIRECT_EXECUTION_REQUIRED", "Direct execution is available only for Customer Contact creation.")
	if failure := direct_entry_failure("create"):
		return _error(failure.code, failure.message)
	planned = prepare_customer_contact(request, _direct_execution=True)
	if planned.get("status") != "ready" or "_direct_values" not in planned:
		return planned
	values = planned["_direct_values"]
	customer_name = planned["_customer_name"]
	try:
		contact = frappe.get_doc(_new_contact_payload(customer_name, values))
		if failure := exact_mode_failure("create", WriteMode.DIRECT):
			return _error(failure.code, failure.message)
		contact.insert(ignore_permissions=False)
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		return _permission_error("Contact", "create")
	except Exception:
		frappe.db.rollback()
		return _error("CONTACT_CREATE_FAILED", "Native Contact creation failed.", retryable=True)
	return {
		"status": "created",
		"customer": {"doctype": "Customer", "name": customer_name},
		"contact": _projection(contact, customer_name),
		"idempotent": False,
		"primary": {"requested": False, "applied": False, "customer_primary_contact_updated": False},
	}
