"""Permission-aware, standalone Contact creation workflow."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import validate_email_address, validate_phone_number

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import new_error_reference
from ..common.fingerprint import stable_fingerprint
from .customer_contact import (
	_projection,
	_search_contacts,
)

_ACTION = "contact_create"
_PROFILE = "sales"


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


def _permission_error() -> dict[str, Any]:
	return _error("PERMISSION_DENIED", "The authenticated user cannot create this Contact.")


def _validate_input(values: dict[str, Any]) -> dict[str, Any] | None:
	if not any(values.get(fieldname) for fieldname in ("first_name", "last_name", "company_name")):
		return _error(
			"CONTACT_INVALID_IDENTITY",
			"A standalone Contact needs first_name, last_name, or company_name.",
		)
	if values.get("email"):
		parsed = validate_email_address(values["email"], throw=False)
		if not parsed or "," in parsed:
			return _error("CONTACT_INVALID_EMAIL", "The Contact email is invalid.")
		values["email"] = parsed
	for fieldname in ("mobile", "phone"):
		if values.get(fieldname) and not validate_phone_number(values[fieldname], throw=False):
			return _error("CONTACT_INVALID_PHONE", "The Contact phone number is invalid.")
	return None


def _full_name(values: dict[str, Any]) -> str:
	person_name = " ".join(
		value
		for fieldname in ("first_name", "middle_name", "last_name")
		if (value := values.get(fieldname))
	)
	return person_name or str(values["company_name"])


def _contact_payload(values: dict[str, Any]) -> dict[str, Any]:
	payload: dict[str, Any] = {"doctype": "Contact"}
	for fieldname in (
		"first_name",
		"middle_name",
		"last_name",
		"company_name",
		"designation",
		"department",
	):
		if values.get(fieldname):
			payload[fieldname] = values[fieldname]
	if values.get("email"):
		payload["email_ids"] = [{"email_id": values["email"], "is_primary": 1}]
	if values.get("mobile"):
		payload.setdefault("phone_nos", []).append(
			{"phone": values["mobile"], "is_primary_mobile_no": 1, "is_primary_phone": 0}
		)
	if values.get("phone"):
		payload.setdefault("phone_nos", []).append(
			{"phone": values["phone"], "is_primary_phone": 1, "is_primary_mobile_no": 0}
		)
	return payload


def _duplicate_contacts(values: dict[str, Any]) -> list[dict[str, Any]]:
	candidates: dict[str, Any] = {}
	for fieldname, match in (("email", "email"), ("mobile", "phone"), ("phone", "phone")):
		value = values.get(fieldname)
		if not value:
			continue
		for contact in _search_contacts(value, None, match):
			candidates[str(contact.get("name"))] = contact
	return [_projection(contact) for contact in candidates.values()]


def _preview(values: dict[str, Any]) -> dict[str, Any]:
	return {
		"action": "create",
		"full_name": _full_name(values),
		"company_name": values.get("company_name"),
		"designation": values.get("designation"),
		"department": values.get("department"),
		"email": values.get("email"),
		"mobile": values.get("mobile"),
		"phone": values.get("phone"),
		"linked_to_customer": False,
		"link_count": 0,
	}


def _confirmation_failure(state: str) -> dict[str, Any]:
	code, message, retryable = confirmation_failure(state, "standalone Contact")
	return _error(code, message, retryable=retryable)


def prepare_contact(request: dict[str, Any]) -> dict[str, Any]:
	"""Prepare a standalone Contact without constructing or validating a Document."""
	approvals.prune_expired()
	user = _current_user()
	if not frappe.has_permission("Contact", "create"):
		return _permission_error()
	input_values = request.get("contact") or {}
	values = {
		fieldname: _clean(input_values.get(fieldname))
		for fieldname in (
			"first_name",
			"middle_name",
			"last_name",
			"company_name",
			"designation",
			"department",
			"email",
			"mobile",
			"phone",
		)
	}
	if validation_failure := _validate_input(values):
		return validation_failure
	if duplicates := _duplicate_contacts(values):
		return _error(
			"CONTACT_DUPLICATE_SUSPECTED",
			"An exact visible Contact already matches this identity.",
		) | {"candidates": duplicates}
	fingerprint = stable_fingerprint(
		{
			"action": _ACTION,
			"profile": _PROFILE,
			"input": values,
			"duplicates": [],
		}
	)
	approval_payload = {
		"action": _ACTION,
		"profile": _PROFILE,
		"values": values,
		"fingerprint": fingerprint,
	}
	token = approvals.create(action=_ACTION, site=frappe.local.site, user=user, payload=approval_payload)
	return {
		"status": "ready",
		"approval_token": token,
		"expires_in_seconds": APPROVAL_TTL_SECONDS,
		"preview": _preview(values),
		"interaction": approval_directive().model_dump(mode="json"),
	}


def confirm_contact(approval_token: str, confirm: bool) -> dict[str, Any]:
	"""Claim and execute exactly one approved native standalone Contact insert."""
	user = _current_user()
	if not confirm:
		approvals.cancel(approval_token, action=_ACTION, site=frappe.local.site, user=user)
		return _error("CONFIRMATION_REQUIRED", "Review the Contact operation before confirming it.")
	approval, state = approvals.claim_for_confirm_write(
		approval_token, action=_ACTION, site=frappe.local.site, user=user
	)
	if state != "available" or approval is None:
		return _confirmation_failure(state)
	payload = approval.payload
	if payload.get("profile") != _PROFILE or payload.get("action") != _ACTION:
		return _error("PROFILE_MISMATCH", "The prepared Contact operation belongs to another profile.")
	if not frappe.has_permission("Contact", "create"):
		return _permission_error()
	values = dict(payload.get("values") or {})
	if validation_failure := _validate_input(values):
		return validation_failure
	if duplicates := _duplicate_contacts(values):
		return _error(
			"CONTACT_DUPLICATE_SUSPECTED",
			"An exact visible Contact appeared after preparation.",
		) | {"candidates": duplicates}
	try:
		contact = frappe.get_doc(_contact_payload(values))
		contact.insert(ignore_permissions=False)
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		return _permission_error()
	except Exception:
		frappe.db.rollback()
		return _error("CONTACT_CREATE_FAILED", "Native Contact creation failed.", retryable=True)
	return {"status": "created", "contact": _projection(contact), "idempotent": False}
