"""Permission-aware, Frappe-native PDF rendering for existing transactions."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import frappe
from frappe.translate import print_language

from ...observability import new_error_reference
from .read import _DOCUMENTS, _profile_doctypes

PDF_MIME_TYPE = "application/pdf"


def _error(code: str, message: str) -> dict[str, Any]:
	return {
		"status": "error",
		"code": code,
		"message": message,
		"reference": new_error_reference(),
		"retryable": False,
	}


def _artifact_uri(doctype: str, name: str) -> str:
	return f"artifact://mcp-erpnext/document-pdf/{quote(doctype, safe='')}/{quote(name, safe='')}"


def _filename(name: str) -> str:
	return f"{name.replace(' ', '-').replace('/', '-')}.pdf"


def _validate_explicit_print_format(doctype: str, print_format: str) -> dict[str, Any] | None:
	if print_format == "Standard":
		return None

	try:
		format_doc = frappe.get_doc("Print Format", print_format)
	except frappe.DoesNotExistError:
		return _error(
			"INVALID_PRINT_FORMAT",
			f"Print Format {print_format} does not exist.",
		)

	if (
		format_doc.get("print_format_for") != "DocType"
		or format_doc.get("doc_type") != doctype
		or bool(format_doc.get("disabled"))
	):
		return _error(
			"INVALID_PRINT_FORMAT",
			f"Print Format {print_format} is not valid for {doctype}.",
		)

	return None


def _resolve_print_format(doctype: str, requested: str | None) -> tuple[str, dict[str, Any] | None]:
	"""Resolve the name reported to the client while preserving Frappe defaults."""
	if requested:
		if error := _validate_explicit_print_format(doctype, requested):
			return requested, error
		return requested, None

	default = frappe.get_meta(doctype).default_print_format or "Standard"
	if default == "Standard":
		return default, None

	# Frappe's printview falls back to Standard when a configured default no
	# longer exists. Keep the metadata aligned with that native behavior.
	try:
		frappe.get_doc("Print Format", default)
	except frappe.DoesNotExistError:
		return "Standard", None
	return default, None


def render_document_pdf(
	doctype: str,
	name: str,
	profile: str,
	print_format: str | None = None,
	letterhead: str | None = None,
	language: str | None = None,
) -> dict[str, Any]:
	"""Render one exact supported transaction using the authenticated Frappe user."""
	if doctype not in _DOCUMENTS or doctype not in _profile_doctypes(profile):
		return _error("DOCTYPE_NOT_ALLOWED", f"{doctype} is not available in the {profile} MCP profile.")

	try:
		doc = frappe.get_doc(doctype, name)
	except frappe.DoesNotExistError:
		return {"status": "not_found", "doctype": doctype, "name": name}

	if not doc.has_permission("read") or not doc.has_permission("print"):
		return _error(
			"PERMISSION_DENIED",
			"The authenticated user cannot read and print that document.",
		)

	print_format_used, format_error = _resolve_print_format(doctype, print_format)
	if format_error:
		return format_error

	# get_print is Frappe's native printview/PDF path. It applies Print Settings,
	# the document/default Letter Head, and the selected Print Format itself.
	with print_language(language):
		pdf = frappe.get_print(
			doctype,
			name,
			print_format if print_format else None,
			doc=doc,
			as_pdf=True,
			letterhead=letterhead,
		)

	if not isinstance(pdf, bytes):
		return _error("PDF_RENDER_FAILED", "Frappe did not return a PDF artifact.")

	return {
		"status": "ok",
		"doctype": doctype,
		"name": name,
		"print_format_used": print_format_used,
		"filename": _filename(name),
		"mime_type": PDF_MIME_TYPE,
		"artifact_uri": _artifact_uri(doctype, name),
		"size_bytes": len(pdf),
		"_pdf": pdf,
	}
