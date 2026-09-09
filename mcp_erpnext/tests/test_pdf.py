from __future__ import annotations

import base64
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.services.common import pdf
from mcp_erpnext.tools import pdf as pdf_tools


class FakeDocument:
	def __init__(self, *, read=True, print_permission=True):
		self.permissions = {"read": read, "print": print_permission}

	def has_permission(self, permission):
		return self.permissions[permission]


class FakePrintFormat:
	def __init__(self, *, doctype="Sales Order", disabled=False, print_format_for="DocType"):
		self.values = {
			"print_format_for": print_format_for,
			"doc_type": doctype,
			"disabled": disabled,
		}

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)


class FakeFrappe:
	DoesNotExistError = frappe.DoesNotExistError
	PermissionError = frappe.PermissionError

	def __init__(self, *, document="__default__", default_print_format="Sales PDF", print_format="__default__"):
		self.document = FakeDocument() if document == "__default__" else document
		self.meta = SimpleNamespace(default_print_format=default_print_format)
		self.print_format = FakePrintFormat() if print_format == "__default__" else print_format
		self.print_calls = []

	def get_doc(self, doctype, name):
		if doctype == "Print Format":
			if self.print_format is None:
				raise self.DoesNotExistError
			return self.print_format
		if self.document is None:
			raise self.DoesNotExistError
		return self.document

	def get_meta(self, _doctype):
		return self.meta

	def get_print(self, *args, **kwargs):
		self.print_calls.append((args, kwargs))
		return b"%PDF-test"


class PdfServiceTests(unittest.TestCase):
	def run_service(self, fake_frappe, *, profile="sales", doctype="Sales Order", **kwargs):
		with patch.object(pdf, "frappe", fake_frappe), patch.object(pdf, "print_language", lambda _language: nullcontext()):
			return pdf.render_document_pdf(profile=profile, doctype=doctype, name="DOC-1", **kwargs)

	def test_default_format_uses_native_default_and_returns_pdf_metadata(self):
		fake = FakeFrappe()
		result = self.run_service(fake)

		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["print_format_used"], "Sales PDF")
		self.assertEqual(result["mime_type"], "application/pdf")
		self.assertEqual(result["size_bytes"], len(b"%PDF-test"))
		self.assertEqual(fake.print_calls[0][1]["as_pdf"], True)
		self.assertEqual(fake.print_calls[0][1]["letterhead"], None)
		self.assertEqual(fake.print_calls[0][0][2], None)

	def test_sales_profile_supports_quotation(self):
		result = self.run_service(FakeFrappe(), doctype="Quotation")
		self.assertEqual(result["status"], "ok")

	def test_purchase_profile_supports_purchase_order(self):
		result = self.run_service(FakeFrappe(), profile="purchase", doctype="Purchase Order")
		self.assertEqual(result["status"], "ok")

	def test_explicit_valid_format_is_used(self):
		fake = FakeFrappe()
		result = self.run_service(fake, print_format="Sales PDF", letterhead="Company Letter Head")

		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["print_format_used"], "Sales PDF")
		self.assertEqual(fake.print_calls[0][0][2], "Sales PDF")
		self.assertEqual(fake.print_calls[0][1]["letterhead"], "Company Letter Head")

	def test_missing_default_falls_back_to_standard(self):
		fake = FakeFrappe()
		fake.meta.default_print_format = "Missing Format"
		fake.print_format = None

		result = self.run_service(fake)

		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["print_format_used"], "Standard")

	def test_explicit_wrong_doctype_format_is_rejected(self):
		fake = FakeFrappe(print_format=FakePrintFormat(doctype="Purchase Order"))

		result = self.run_service(fake, print_format="Purchase PDF")

		self.assertEqual(result["code"], "INVALID_PRINT_FORMAT")
		self.assertEqual(fake.print_calls, [])

	def test_explicit_disabled_or_report_format_is_rejected(self):
		for format_doc in (
			FakePrintFormat(disabled=True),
			FakePrintFormat(print_format_for="Report"),
		):
			with self.subTest(format_doc=format_doc.values):
				result = self.run_service(FakeFrappe(print_format=format_doc), print_format="Unavailable PDF")

				self.assertEqual(result["code"], "INVALID_PRINT_FORMAT")

	def test_explicit_missing_format_is_rejected(self):
		fake = FakeFrappe(print_format=None)

		result = self.run_service(fake, print_format="Missing PDF")

		self.assertEqual(result["code"], "INVALID_PRINT_FORMAT")
		self.assertEqual(fake.print_calls, [])

	def test_cross_profile_doctype_is_rejected_before_document_lookup(self):
		fake = FakeFrappe()
		with patch.object(pdf, "frappe", fake):
			result = pdf.render_document_pdf("Purchase Order", "PO-1", "sales")

		self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")

	def test_unsupported_doctype_is_rejected(self):
		fake = FakeFrappe()
		with patch.object(pdf, "frappe", fake):
			result = pdf.render_document_pdf("Customer", "CUST-1", "sales")

		self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")

	def test_read_and_print_permissions_are_both_required(self):
		for permission in ("read", "print"):
			read = permission != "read"
			print_permission = permission != "print"
			result = self.run_service(FakeFrappe(document=FakeDocument(read=read, print_permission=print_permission)))
			self.assertEqual(result["code"], "PERMISSION_DENIED")

	def test_missing_document_is_not_found(self):
		fake = FakeFrappe(document=None)
		result = self.run_service(fake)
		self.assertEqual(result["status"], "not_found")


class PdfToolResultTests(unittest.TestCase):
	def test_success_is_an_embedded_pdf_resource_with_structured_metadata(self):
		registered = {}

		class MCP:
			def tool(self, **kwargs):
				def decorator(function):
					registered[kwargs["name"]] = function
					return function
				return decorator

		pdf_tools.register_document_pdf_tools(MCP(), "sales")
		result_payload = {
			"status": "ok",
			"doctype": "Sales Order",
			"name": "SO-1",
			"print_format_used": "Standard",
			"filename": "SO-1.pdf",
			"mime_type": "application/pdf",
			"artifact_uri": "artifact://mcp-erpnext/document-pdf/Sales%20Order/SO-1",
			"size_bytes": 9,
			"_pdf": b"%PDF-test",
		}
		with patch.object(pdf_tools, "execute_tool_with_context", return_value=result_payload):
			result = registered["render_document_pdf"]("Sales Order", "SO-1", object())

		self.assertEqual(result.structuredContent["mime_type"], "application/pdf")
		resource = result.content[0].resource
		self.assertEqual(resource.mimeType, "application/pdf")
		self.assertEqual(base64.b64decode(resource.blob), b"%PDF-test")


if __name__ == "__main__":
	unittest.main()
