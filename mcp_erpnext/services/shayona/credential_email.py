"""Approval-bound, secret-safe Customer Service Credential email."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.utils import validate_email_address

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...observability import logged_public_error, new_error_reference
from . import credentials
from .config import BusinessConfigError, load_business_defaults

CREDENTIAL_EMAIL_ACTION = "customer_service_credential_email"
_SECRET_SUBJECT_FIELDS = re.compile(r"\b(?:username|password)\b")
_USERNAME_SENTINEL = "__MCP_CREDENTIAL_SECRET_USERNAME__"
_PASSWORD_SENTINEL = "__MCP_CREDENTIAL_SECRET_PASSWORD__"

_MESSAGES = {
    "CREDENTIAL_SCHEMA_UNAVAILABLE": "The Customer Service Credential schema is unavailable.",
    "CREDENTIAL_NOT_FOUND": "The requested credential was not found.",
    "CREDENTIAL_INACTIVE": "The requested credential is inactive.",
    "CREDENTIAL_READ_FAILED": "The credential could not be read.",
    "PERMISSION_DENIED": "The authenticated user cannot use that credential.",
    "INVALID_RECIPIENT": "recipient_email must contain one valid email address.",
    "CUSTOMER_EMAIL_UNAVAILABLE": "The Customer primary email is unavailable.",
    "OPERATOR_EMAIL_UNAVAILABLE": "The authenticated user email is unavailable.",
    "EMAIL_TEMPLATE_NOT_CONFIGURED": "The credential email template is not configured.",
    "EMAIL_TEMPLATE_NOT_FOUND": "The configured credential email template was not found.",
    "EMAIL_TEMPLATE_INVALID": "The configured credential email template is invalid.",
    "EMAIL_TEMPLATE_UNSAFE": "The configured credential email template is unsafe.",
    "EMAIL_ACCOUNT_NOT_CONFIGURED": "No outgoing Frappe Email Account is configured.",
    "CREDENTIAL_SECRET_UNAVAILABLE": "The credential secrets are unavailable.",
    "EMAIL_RENDER_FAILED": "Frappe could not render the credential email.",
    "EMAIL_QUEUE_FAILED": "Frappe could not queue the credential email.",
    "PREPARED_STATE_CHANGED": "The approved credential email state changed. Please prepare it again.",
    "CONFIRMATION_EXPIRED": "This credential email confirmation has expired. Please prepare it again.",
    "CONFIRMATION_CONSUMED": "This credential email confirmation has already been used. Please prepare it again.",
    "CONFIRMATION_UNAVAILABLE": "This credential email confirmation is unavailable.",
    "TRUSTED_APPROVAL_UNAVAILABLE": "A trusted approval is required before confirmation.",
}


class CredentialEmailError(RuntimeError):
    def __init__(self, public_code: str):
        super().__init__(public_code)
        self.public_code = public_code


def _error(code: str, *, retryable: bool = False) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": _MESSAGES.get(code, "The credential email operation failed."),
        "reference": new_error_reference(),
        "retryable": retryable,
    }


def _fail(code: str) -> None:
    raise CredentialEmailError(code)


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or str(user).casefold() in {"guest", ""}:
        _fail("PERMISSION_DENIED")
    return str(user)


def _value(doc: Any, fieldname: str) -> Any:
    getter = getattr(doc, "get", None)
    return getter(fieldname) if callable(getter) else getattr(doc, fieldname, None)


def _valid_email(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = validate_email_address(value.strip(), throw=False)
    return parsed.strip() if isinstance(parsed, str) and "," not in parsed else None


def _snapshot(doc: Any) -> dict[str, Any]:
    fields = (
        "customer",
        "domain_name",
        "credential_type",
        "account_name",
        "account_identity",
        "control_panel_url",
    )
    values = {field: _value(doc, field) or None for field in fields}
    if not all(
        isinstance(values[field], str) and values[field].strip() for field in fields[:4]
    ):
        _fail("CREDENTIAL_READ_FAILED")
    return {
        "credential_name": str(_value(doc, "name") or ""),
        **values,
        "is_active": bool(_value(doc, "is_active")),
        "credential_modified": str(_value(doc, "modified") or ""),
    }


def _load_credential(name: str) -> Any:
    try:
        credentials.credential_schema()
    except credentials.CredentialSchemaUnavailableError as error:
        raise CredentialEmailError("CREDENTIAL_SCHEMA_UNAVAILABLE") from error
    try:
        doc = frappe.get_doc(credentials.CREDENTIAL_DOCTYPE, name)
    except frappe.DoesNotExistError as error:
        raise CredentialEmailError("CREDENTIAL_NOT_FOUND") from error
    if not doc.has_permission("read"):
        _fail("PERMISSION_DENIED")
    if not _value(doc, "is_active"):
        _fail("CREDENTIAL_INACTIVE")
    return doc


def _customer_email(name: str) -> str:
    try:
        customer = frappe.get_doc("Customer", name)
    except (frappe.DoesNotExistError, frappe.PermissionError) as error:
        raise CredentialEmailError("CUSTOMER_EMAIL_UNAVAILABLE") from error
    if not customer.has_permission("read") or not _valid_email(
        _value(customer, "email_id")
    ):
        _fail("CUSTOMER_EMAIL_UNAVAILABLE")
    return _valid_email(_value(customer, "email_id")) or ""


def _operator_email(user: str) -> str:
    try:
        row = frappe.db.get_value("User", user, ["email", "enabled"], as_dict=True)
    except Exception as error:
        raise CredentialEmailError("OPERATOR_EMAIL_UNAVAILABLE") from error
    email = row.get("email") if isinstance(row, dict) else getattr(row, "email", None)
    enabled = (
        row.get("enabled") if isinstance(row, dict) else getattr(row, "enabled", None)
    )
    if not enabled or not _valid_email(email):
        _fail("OPERATOR_EMAIL_UNAVAILABLE")
    return _valid_email(email) or ""


def _cc(recipient: str, customer: str, operator: str) -> list[str]:
    seen = {recipient.casefold()}
    result = []
    for value in (customer, operator):
        if value.casefold() not in seen:
            result.append(value)
            seen.add(value.casefold())
    return result


def _template_sources(template: Any) -> tuple[str, str]:
    subject = getattr(template, "subject", None)
    body = (
        getattr(template, "response_html", None)
        if getattr(template, "use_html", False)
        else getattr(template, "response", None)
    )
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or not isinstance(body, str)
        or not body.strip()
    ):
        _fail("EMAIL_TEMPLATE_INVALID")
    return subject, body


def _template_state(template: Any) -> dict[str, str]:
    subject, body = _template_sources(template)
    return {
        "template_name": str(getattr(template, "name", "")),
        "template_modified": str(getattr(template, "modified", "") or ""),
        "template_subject_source_digest": sha256(subject.encode()).hexdigest(),
        "template_body_source_digest": sha256(body.encode()).hexdigest(),
    }


def _load_template(name: str, note_variable: str) -> tuple[Any, dict[str, str]]:
    try:
        template = frappe.get_doc("Email Template", name)
    except (frappe.DoesNotExistError, frappe.PermissionError) as error:
        raise CredentialEmailError("EMAIL_TEMPLATE_NOT_FOUND") from error
    if not template.has_permission("read"):
        _fail("EMAIL_TEMPLATE_NOT_FOUND")
    state = _template_state(template)
    _, body = _template_sources(template)
    if not re.search(r"{{-?\s*" + re.escape(note_variable) + r"\b", body):
        _fail("EMAIL_TEMPLATE_INVALID")
    subject, _ = _template_sources(template)
    if _SECRET_SUBJECT_FIELDS.search(subject):
        _fail("EMAIL_TEMPLATE_UNSAFE")
    return template, state


def _context(
    snapshot: dict[str, Any], note_variable: str, note: str | None
) -> dict[str, Any]:
    note_value = note or ""
    return {
        "doctype": credentials.CREDENTIAL_DOCTYPE,
        **{
            key: snapshot[key]
            for key in (
                "credential_name",
                "customer",
                "domain_name",
                "credential_type",
                "account_name",
                "account_identity",
                "control_panel_url",
            )
        },
        "additional_note": note_value,
        note_variable: note_value,
        "username": _USERNAME_SENTINEL,
        "password": _PASSWORD_SENTINEL,
    }


def _safe_subject(
    template: Any, snapshot: dict[str, Any], note_variable: str, note: str | None
) -> str:
    try:
        subject = template.get_formatted_subject(
            _context(snapshot, note_variable, note)
        )
    except Exception as error:
        raise CredentialEmailError("EMAIL_TEMPLATE_INVALID") from error
    if not isinstance(subject, str) or not subject.strip():
        _fail("EMAIL_TEMPLATE_INVALID")
    if _USERNAME_SENTINEL in subject or _PASSWORD_SENTINEL in subject:
        _fail("EMAIL_TEMPLATE_UNSAFE")
    return subject.strip()


def _outgoing_account() -> None:
    try:
        account = EmailAccount.find_outgoing(
            match_by_doctype=credentials.CREDENTIAL_DOCTYPE, _raise_error=True
        )
    except Exception as error:
        raise CredentialEmailError("EMAIL_ACCOUNT_NOT_CONFIGURED") from error
    if not account:
        _fail("EMAIL_ACCOUNT_NOT_CONFIGURED")


def _queue_reference(queue: Any, payload: dict[str, Any]) -> str | None:
    if queue is None or isinstance(queue, (dict, list, tuple, set)):
        return None
    name = getattr(queue, "name", None)
    to = getattr(queue, "to", None)
    cc = getattr(queue, "cc", None)
    if (
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(to, (list, tuple, set))
        or not isinstance(cc, (list, tuple, set))
    ):
        return None
    to_set = {item.casefold() for item in to if isinstance(item, str) and item.strip()}
    cc_set = {item.casefold() for item in cc if isinstance(item, str) and item.strip()}
    required = {item.casefold() for item in payload.get("cc", [])}
    recipient = str(payload.get("recipient_email", "")).casefold()
    return (
        name.strip()
        if recipient in to_set and recipient not in cc_set and required.issubset(cc_set)
        else None
    )


def _prepare(
    credential_name: str,
    recipient_email: str,
    subject: str | None = None,
    additional_note: str | None = None,
) -> dict[str, Any]:
    doc = _load_credential(credential_name)
    snapshot = _snapshot(doc)
    if not snapshot["is_active"]:
        _fail("CREDENTIAL_INACTIVE")
    recipient = _valid_email(recipient_email)
    if not recipient:
        _fail("INVALID_RECIPIENT")
    user = _current_user()
    customer_email = _customer_email(snapshot["customer"])
    operator_email = _operator_email(user)
    if additional_note is not None and len(additional_note) > 10_000:
        _fail("EMAIL_TEMPLATE_INVALID")
    try:
        config = load_business_defaults(frappe_module=frappe)
    except BusinessConfigError as error:
        raise CredentialEmailError(error.public_code) from error
    try:
        template_name = config.template_for(snapshot["credential_type"])
    except BusinessConfigError as error:
        raise CredentialEmailError(error.public_code) from error
    template, template_state = _load_template(
        template_name, config.additional_note_variable
    )
    template_subject = _safe_subject(
        template, snapshot, config.additional_note_variable, additional_note
    )
    _outgoing_account()
    if subject is not None and len(subject.strip()) > 255:
        _fail("EMAIL_TEMPLATE_INVALID")
    approved_subject = subject.strip() if subject is not None else template_subject
    cc = _cc(recipient, customer_email, operator_email)
    payload = {
        **snapshot,
        "recipient_email": recipient,
        "customer_cc_email": customer_email,
        "operator_email": operator_email,
        "cc": cc,
        "reply_to": operator_email,
        **template_state,
        "additional_note_variable": config.additional_note_variable,
        "approved_subject": approved_subject,
        "subject_override": subject is not None,
        "additional_note": additional_note,
    }
    token = approvals.create(
        action=CREDENTIAL_EMAIL_ACTION,
        site=str(frappe.local.site),
        user=user,
        payload=payload,
    )
    return {
        "status": "ready_for_approval",
        "preview": {
            **{
                key: snapshot[key]
                for key in (
                    "credential_name",
                    "customer",
                    "domain_name",
                    "credential_type",
                    "account_name",
                    "account_identity",
                    "control_panel_url",
                    "is_active",
                )
            },
            "to": recipient,
            "cc": cc,
            "reply_to": operator_email,
            "subject": approved_subject,
            "additional_note": additional_note,
            "email_template": template_name,
        },
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def prepare_customer_service_credential_email(**kwargs: Any) -> dict[str, Any]:
    try:
        return _prepare(**kwargs)
    except CredentialEmailError as error:
        return logged_public_error(
            "prepare_customer_service_credential_email",
            error.public_code,
            message=_MESSAGES.get(error.public_code),
        )


def _revalidate(payload: dict[str, Any]) -> tuple[Any, dict[str, Any], Any, str]:
    doc = _load_credential(payload["credential_name"])
    snapshot = _snapshot(doc)
    for key in (
        "credential_name",
        "credential_modified",
        "customer",
        "domain_name",
        "credential_type",
        "account_name",
        "account_identity",
        "control_panel_url",
        "is_active",
    ):
        if snapshot.get(key) != payload.get(key):
            _fail("PREPARED_STATE_CHANGED")
    recipient = _valid_email(payload.get("recipient_email"))
    if not recipient:
        _fail("PREPARED_STATE_CHANGED")
    try:
        customer = _customer_email(snapshot["customer"])
        operator = _operator_email(_current_user())
    except CredentialEmailError as error:
        raise CredentialEmailError("PREPARED_STATE_CHANGED") from error
    if (
        customer.casefold() != str(payload.get("customer_cc_email", "")).casefold()
        or operator.casefold() != str(payload.get("operator_email", "")).casefold()
        or operator.casefold() != str(payload.get("reply_to", "")).casefold()
        or _cc(recipient, customer, operator) != payload.get("cc")
    ):
        _fail("PREPARED_STATE_CHANGED")
    try:
        config = load_business_defaults(frappe_module=frappe)
        template_name = config.template_for(snapshot["credential_type"])
        template, state = _load_template(template_name, config.additional_note_variable)
    except (BusinessConfigError, CredentialEmailError) as error:
        raise CredentialEmailError("PREPARED_STATE_CHANGED") from error
    if (
        template_name != payload.get("template_name")
        or config.additional_note_variable != payload.get("additional_note_variable")
        or state != {key: payload.get(key) for key in state}
    ):
        _fail("PREPARED_STATE_CHANGED")
    approved_rendered_subject = _safe_subject(
        template,
        snapshot,
        config.additional_note_variable,
        payload.get("additional_note"),
    )
    if not payload.get("subject_override") and approved_rendered_subject != payload.get(
        "approved_subject"
    ):
        _fail("PREPARED_STATE_CHANGED")
    _outgoing_account()
    return doc, snapshot, template, operator


def _confirm(approval_token: str) -> dict[str, Any]:
    user = _current_user()
    approval, state = approvals.claim_for_confirm_write(
        approval_token,
        action=CREDENTIAL_EMAIL_ACTION,
        site=str(frappe.local.site),
        user=user,
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "credential email")
        return {
            "status": "error",
            "code": code,
            "message": message,
            "reference": new_error_reference(),
            "retryable": retryable,
        }
    payload = approval.payload
    doc, snapshot, template, operator = _revalidate(payload)
    try:
        username = _value(doc, "username")
        password = doc.get_password("password")
    except Exception as error:
        raise CredentialEmailError("CREDENTIAL_SECRET_UNAVAILABLE") from error
    if (
        not isinstance(username, str)
        or not username
        or not isinstance(password, str)
        or not password
    ):
        _fail("CREDENTIAL_SECRET_UNAVAILABLE")
    context = _context(
        snapshot, payload["additional_note_variable"], payload.get("additional_note")
    )
    context.update({"username": username, "password": password})
    try:
        rendered = template.get_formatted_email(context)
        rendered_subject, message = rendered.get("subject"), rendered.get("message")
    except Exception as error:
        raise CredentialEmailError("EMAIL_RENDER_FAILED") from error
    final_subject = (
        payload["approved_subject"] if payload["subject_override"] else rendered_subject
    )
    if (
        final_subject != payload["approved_subject"]
        or not isinstance(message, str)
        or not message
    ):
        _fail("PREPARED_STATE_CHANGED")
    try:
        queue = frappe.sendmail(
            recipients=[payload["recipient_email"]],
            cc=list(payload["cc"]),
            reply_to=operator,
            subject=final_subject,
            message=message,
            doctype=credentials.CREDENTIAL_DOCTYPE,
            name=payload["credential_name"],
            redact_message_after_send=True,
        )
        reference = _queue_reference(queue, payload)
        if reference is None:
            _fail("EMAIL_QUEUE_FAILED")
        frappe.db.commit()
    except frappe.PermissionError as error:
        frappe.db.rollback()
        raise CredentialEmailError("PERMISSION_DENIED") from error
    except CredentialEmailError:
        frappe.db.rollback()
        raise
    except Exception as error:
        frappe.db.rollback()
        raise CredentialEmailError("EMAIL_QUEUE_FAILED") from error
    return {
        "status": "queued",
        "credential_name": payload["credential_name"],
        "recipient": payload["recipient_email"],
        "queue_reference": reference,
        "message": "Credential email accepted by Frappe's Email Queue.",
    }


def confirm_customer_service_credential_email(approval_token: str) -> dict[str, Any]:
    try:
        return _confirm(approval_token)
    except CredentialEmailError as error:
        return logged_public_error(
            "confirm_customer_service_credential_email",
            error.public_code,
            message=_MESSAGES.get(error.public_code),
        )
