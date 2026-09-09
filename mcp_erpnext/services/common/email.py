"""Permission-safe, approval-bound email of existing transactional documents."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import frappe
from frappe.contacts.doctype.contact.contact import get_contacts_linking_to
from frappe.utils import validate_email_address

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import InteractionAction, InteractionDirective, InteractionKind, approval_directive
from ...observability import new_error_reference
from . import pdf as pdf_service
from .read import _DOCUMENTS, _profile_doctypes

EMAIL_ACTION = "document_email"
PDF_MIME_TYPE = "application/pdf"
_MAX_CONTACTS = 50


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
		frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
	return user


def _target(doctype: str, name: str, profile: str) -> tuple[str, str] | dict[str, Any]:
	if doctype not in _DOCUMENTS or doctype not in _profile_doctypes(profile):
		return _error("DOCTYPE_NOT_ALLOWED", f"{doctype} is not available in the {profile} MCP profile.")
	if not name.strip():
		return _error("INVALID_TARGET", "An exact document name is required.")
	return doctype, name.strip()


def _load(doctype: str, name: str, profile: str) -> tuple[Any, dict[str, Any] | None]:
	resolved = _target(doctype, name, profile)
	if isinstance(resolved, dict):
		return None, resolved
	try:
		doc = frappe.get_doc(doctype, name)
	except frappe.DoesNotExistError:
		return None, {"status": "not_found", "doctype": doctype, "name": name}
	for permission in ("read", "email", "print"):
		if not doc.has_permission(permission):
			return None, _error("PERMISSION_DENIED", f"The authenticated user cannot {permission} that document.")
	return doc, None


def _party_reference(doc: Any) -> tuple[str | None, str | None]:
	if doc.doctype == "Quotation":
		return doc.get("quotation_to"), doc.get("party_name")
	if doc.doctype == "Sales Order":
		return "Customer", doc.get("customer")
	if doc.doctype == "Purchase Order":
		return "Supplier", doc.get("supplier")
	return None, None


def _valid_email(value: Any) -> str | None:
	if not isinstance(value, str) or not value.strip():
		return None
	parsed = validate_email_address(value.strip(), throw=False)
	if not parsed or "," in parsed:
		return None
	return parsed


def _candidate(email: Any, label: Any = None) -> dict[str, str] | None:
	parsed = _valid_email(email)
	if not parsed:
		return None
	result = {"email": parsed}
	if isinstance(label, str) and label.strip():
		result["label"] = label.strip()
	return result


def _unique(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
	result: list[dict[str, str]] = []
	seen: set[str] = set()
	for item in candidates:
		key = item["email"].casefold()
		if key not in seen:
			seen.add(key)
			result.append(item)
	return result


def _party_email(party_type: str, party_name: str) -> dict[str, str] | None:
	"""Use a party's native read-only email only after normal read permission."""
	try:
		party = frappe.get_doc(party_type, party_name)
	except (frappe.DoesNotExistError, frappe.PermissionError):
		return None
	if not party.has_permission("read"):
		return None
	return _candidate(party.get("email_id"), party.get("name") or party_name)


def _contact_candidates(
	party_type: str, party_name: str, selected_contact: str | None = None
) -> list[dict[str, str]]:
	"""Read only Contact email fields linked to the document party."""
	try:
		contacts = get_contacts_linking_to(
			party_type,
			party_name,
			fields=["name", "full_name", "email_id", "is_primary_contact"],
		)[:_MAX_CONTACTS]
	except frappe.PermissionError:
		return []

	result: list[dict[str, str]] = []
	for row in contacts:
		contact_name = row.get("name")
		if selected_contact and contact_name != selected_contact:
			continue
		label = row.get("full_name") or contact_name
		contact = None
		if contact_name:
			try:
				contact = frappe.get_doc("Contact", contact_name)
			except (frappe.DoesNotExistError, frappe.PermissionError):
				contact = None
			if contact is not None and not contact.has_permission("read"):
				contact = None
		if contact is not None:
				emails = [contact.get("email_id")]
				if not selected_contact:
					emails.extend(contact.get("email_ids") or [])
				for email in emails:
					if isinstance(email, dict):
						email = email.get("email_id")
					elif hasattr(email, "get"):
						email = email.get("email_id")
					item = _candidate(email, label)
					if item:
						result.append(item)
				continue
		item = _candidate(row.get("email_id"), label)
		if item:
			result.append(item)
	return _unique(result)


def _resolve_recipient(doc: Any, requested: str | None) -> tuple[dict[str, str] | None, list[dict[str, str]], dict[str, Any] | None]:
	"""Resolve only native document/party contacts and reject unrelated addresses."""
	party_type, party_name = _party_reference(doc)
	if not party_type or not party_name:
		return None, [], _error("RECIPIENT_NOT_FOUND", "The document has no associated business party email.")

	# ERPNext copies the selected Contact's email into the transaction. This is
	# authoritative and avoids silently switching to another party contact.
	native_contact_email = doc.get("contact_email")
	if native_contact_email:
		candidate = _candidate(native_contact_email, doc.get("contact_display") or doc.get("contact_person"))
		if not candidate:
			return None, [], _error("INVALID_EMAIL", "The document's associated contact email is invalid.")
		candidates = [candidate]
	else:
		# Customer/Supplier expose the native primary-contact email as a
		# read-only party field. Treat that field as the authoritative default;
		# only enumerate Contacts when the party has no such default. A selected
		# Contact is authoritative before falling back to the party field.
		selected_contact = doc.get("contact_person") or None
		party_candidate = _party_email(party_type, party_name)
		if selected_contact:
			selected_candidates = _contact_candidates(party_type, party_name, selected_contact)
			candidates = selected_candidates or ([party_candidate] if party_candidate else _contact_candidates(party_type, party_name))
		else:
			candidates = [party_candidate] if party_candidate else _contact_candidates(party_type, party_name)
		candidates = _unique(candidates)

	if requested is not None:
		requested_candidate = _candidate(requested)
		if not requested_candidate:
			return None, candidates, _error("INVALID_EMAIL", "recipient_email must contain one valid email address.")
		if not any(item["email"].casefold() == requested_candidate["email"].casefold() for item in candidates):
			return None, candidates, _error("INVALID_RECIPIENT", "The requested recipient is not associated with this document's business party.")
		return requested_candidate, candidates, None

	if len(candidates) == 1:
		return candidates[0], candidates, None
	if len(candidates) > 1:
		return None, candidates, None
	return None, [], _error("RECIPIENT_NOT_FOUND", "No valid email recipient is associated with this document's business party.")


def _recipient_input(doc: Any, candidates: list[dict[str, str]]) -> dict[str, Any]:
	return {
		"status": "needs_input",
		"doctype": doc.doctype,
		"name": doc.name,
		"candidates": candidates,
		"message": "Multiple associated email recipients were found. Choose exactly one.",
		"interaction": InteractionDirective(
			required=True,
			kind=InteractionKind.INPUT,
			allowed_actions=[InteractionAction.PROVIDE_INPUT, InteractionAction.CANCEL],
			reason_code="RECIPIENT_AMBIGUOUS",
			instructions="Provide exactly one email from the listed associated recipients.",
		).model_dump(mode="json"),
	}


def _default_subject(doctype: str, name: str) -> str:
	return f"{doctype} {name}"


def _default_message(doctype: str, name: str) -> str:
	return f"Please find attached {doctype} {name}."


def _check_email_account(doctype: str) -> dict[str, Any] | None:
	try:
		from frappe.email.doctype.email_account.email_account import EmailAccount

		if not EmailAccount.find_outgoing(match_by_doctype=doctype, _raise_error=True):
			return _error("EMAIL_ACCOUNT_NOT_CONFIGURED", "No outgoing Frappe Email Account is configured.")
	except Exception as error:
		if error.__class__.__name__ == "OutgoingEmailError":
			return _error("EMAIL_ACCOUNT_NOT_CONFIGURED", "No outgoing Frappe Email Account is configured.")
		return _error("EMAIL_PREPARE_FAILED", "Frappe could not validate the outgoing Email Account.")
	return None


def _render(doctype: str, name: str, profile: str, print_format: str | None, letterhead: str | None, language: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
	result = pdf_service.render_document_pdf(doctype, name, profile, print_format, letterhead, language)
	if result.get("status") == "not_found":
		return None, result
	if result.get("status") != "ok":
		return None, _error(result.get("code", "PDF_RENDER_FAILED"), result.get("message", "Frappe could not render the PDF."))
	return result, None


def prepare_document_email(
	doctype: str,
	name: str,
	profile: str,
	recipient_email: str | None = None,
	subject: str | None = None,
	message: str | None = None,
	print_format: str | None = None,
	letterhead: str | None = None,
	language: str | None = None,
) -> dict[str, Any]:
	doc, failure = _load(doctype, name, profile)
	if failure:
		return failure
	recipient, candidates, recipient_failure = _resolve_recipient(doc, recipient_email)
	if recipient_failure:
		return recipient_failure
	if recipient is None:
		return _recipient_input(doc, candidates)
	if (subject is not None and (not isinstance(subject, str) or not subject.strip())) or (message is not None and (not isinstance(message, str) or not message.strip())):
		return _error("INVALID_EMAIL", "Subject and message must be non-empty text when provided.")
	subject = subject or _default_subject(doctype, name)
	message = message or _default_message(doctype, name)
	if len(subject) > 255 or len(message) > 10_000:
		return _error("INVALID_EMAIL", "Subject or message exceeds the supported length.")
	if account_failure := _check_email_account(doctype):
		return account_failure
	pdf, pdf_failure = _render(doctype, name, profile, print_format, letterhead, language)
	if pdf_failure:
		return pdf_failure
	payload = {
		"profile": profile,
		"doctype": doctype,
		"name": name,
		"modified": str(doc.modified),
		"docstatus": int(doc.docstatus),
		"recipient_email": recipient["email"],
		"subject": subject,
		"message": message,
		"print_format": print_format,
		"print_format_used": pdf["print_format_used"],
		"letterhead": letterhead,
		"language": language,
		"attachment_filename": pdf["filename"],
		"attachment_mime_type": pdf["mime_type"],
		"attachment_sha256": sha256(pdf["_pdf"]).hexdigest(),
	}
	token = approvals.create(action=EMAIL_ACTION, site=frappe.local.site, user=_user(), payload=payload)
	return {
		"status": "ready_for_approval",
		"preview": {
			"doctype": doctype,
			"name": name,
			"recipient": recipient["email"],
			"subject": subject,
			"message": message,
			"attachment_filename": pdf["filename"],
			"print_format_used": pdf["print_format_used"],
			"mime_type": PDF_MIME_TYPE,
		},
		"approval_token": token,
		"expires_in_seconds": APPROVAL_TTL_SECONDS,
		"interaction": approval_directive().model_dump(mode="json"),
	}


def _confirm_error(state: str) -> dict[str, Any]:
	code, message, retryable = confirmation_failure(state, "document email")
	return _error(code, message, retryable=retryable)


def confirm_document_email(approval_token: str, profile: str) -> dict[str, Any]:
	user = _user()
	approval, state = approvals.claim_for_confirm_write(
		approval_token, action=EMAIL_ACTION, site=frappe.local.site, user=user
	)
	if state != "available" or approval is None:
		return _confirm_error(state)
	payload = approval.payload
	if payload.get("profile") != profile:
		return _error("PROFILE_MISMATCH", "The prepared email belongs to another MCP profile.")
	doc, failure = _load(payload["doctype"], payload["name"], profile)
	if failure:
		return failure
	if str(doc.modified) != payload["modified"] or int(doc.docstatus) != payload["docstatus"]:
		return _error("PREPARED_STATE_CHANGED", "The document changed after the email preview. Prepare it again.")
	recipient, _, recipient_failure = _resolve_recipient(doc, payload["recipient_email"])
	if recipient_failure or recipient is None or recipient["email"].casefold() != payload["recipient_email"].casefold():
		return _error("PREPARED_STATE_CHANGED", "The approved recipient is no longer associated with the document. Prepare it again.")
	pdf, pdf_failure = _render(
		payload["doctype"],
		payload["name"],
		profile,
		payload.get("print_format"),
		payload.get("letterhead"),
		payload.get("language"),
	)
	if pdf_failure:
		return pdf_failure
	if (
		pdf["print_format_used"] != payload["print_format_used"]
		or pdf["filename"] != payload["attachment_filename"]
		or pdf["mime_type"] != payload["attachment_mime_type"]
		or sha256(pdf["_pdf"]).hexdigest() != payload["attachment_sha256"]
	):
		return _error("PREPARED_STATE_CHANGED", "The approved PDF changed after the email preview. Prepare it again.")
	if account_failure := _check_email_account(payload["doctype"]):
		return account_failure
	try:
		queue = frappe.sendmail(
			recipients=[payload["recipient_email"]],
			subject=payload["subject"],
			message=payload["message"],
			attachments=[
				{
					"fname": payload["attachment_filename"],
					"fcontent": pdf["_pdf"],
					"content_type": payload["attachment_mime_type"],
				}
			],
			doctype=payload["doctype"],
			name=payload["name"],
		)
		# Frappe v16 creates the Email Queue row but does not commit this
		# transaction. Match the existing confirm-write boundary here.
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		return _error("PERMISSION_DENIED", "The authenticated user cannot queue this email.")
	except Exception:
		frappe.db.rollback()
		return _error("EMAIL_QUEUE_FAILED", "Frappe could not queue the document email.")
	return {
		"status": "queued",
		"doctype": payload["doctype"],
		"name": payload["name"],
		"recipient": payload["recipient_email"],
		"queue_reference": getattr(queue, "name", None),
		"message": "Email accepted by Frappe's Email Queue.",
	}
