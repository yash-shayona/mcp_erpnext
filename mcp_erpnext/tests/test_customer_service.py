from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import APPROVAL_TTL_SECONDS, approvals
from mcp_erpnext.config.masters import customer as customer_config
from mcp_erpnext.services.masters import customer as customer_service


class FakeMeta:
	def __init__(self, fieldnames: set[str], fields: list[SimpleNamespace]):
		self._fieldnames = fieldnames
		self.fields = fields

	def has_field(self, fieldname: str) -> bool:
		return fieldname in self._fieldnames


class DefaultDocument:
	def __init__(self, values: dict):
		self.values = values

	def get(self, fieldname: str):
		return self.values.get(fieldname)


class FakeDoc:
	def __init__(self, values: dict):
		self.values = dict(values)
		self.name = self.values.get("name", "CUST-TEST-0001")
		self.customer_name = self.values.get("customer_name")
		self.insert_calls: list[dict] = []

	def get(self, key: str, default=None):
		return self.values.get(key, default)

	def run_method(self, method: str):
		if self.values.get("invalid"):
			raise frappe.ValidationError("invalid")
		return self

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self


class CustomerServiceTests(unittest.TestCase):
	def setUp(self):
		approvals._approvals.clear()
		self.docs: list[FakeDoc] = []
		self.list_rows: dict[str, list[dict]] = {}
		self.commit_count = 0
		self.rollback_count = 0
		self.defaults = {"customer_type": "Company"}
		self.meta_fields = [
			SimpleNamespace(fieldname="customer_name", label="Customer Name", fieldtype="Data", reqd=1),
			SimpleNamespace(
				fieldname="customer_type",
				label="Customer Type",
				fieldtype="Select",
				options="Company\nIndividual\nPartnership",
				reqd=1,
			),
			SimpleNamespace(fieldname="gstin", label="GSTIN", fieldtype="Data", reqd=0),
			SimpleNamespace(fieldname="customer_group", label="Customer Group", fieldtype="Link", options="Customer Group", reqd=0),
			SimpleNamespace(fieldname="territory", label="Territory", fieldtype="Link", options="Territory", reqd=0),
		]
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			get_meta=lambda _: FakeMeta({"gstin", "_address_line1"}, self.meta_fields),
			new_doc=lambda _: DefaultDocument(self.defaults),
			has_permission=lambda *_: True,
			get_list=self._get_list,
			get_doc=self._get_doc,
			db=SimpleNamespace(commit=self._commit, rollback=self._rollback),
			PermissionError=frappe.PermissionError,
			ValidationError=frappe.ValidationError,
		)
		self.patches = [
			patch.object(customer_service, "frappe", self.fake_frappe),
		]
		for active_patch in self.patches:
			active_patch.start()

	def tearDown(self):
		for active_patch in reversed(self.patches):
			active_patch.stop()

	def _get_list(self, doctype, *, filters=None, **kwargs):
		if doctype in {"Customer Group", "Territory"}:
			query = (kwargs.get("or_filters") or [[None, None, None, ""]])[0][3].strip("%").casefold()
			if query == "unknown":
				return []
			if doctype == "Customer Group" and query == "com":
				return [{"name": "Commercial"}, {"name": "Commerce"}]
			return [{"name": "Commercial"}] if doctype == "Customer Group" else [{"name": "India"}]
		if doctype != "Customer":
			return []
		for fieldname in ("name", "customer_name", "mobile_no", "email_id", "gstin"):
			if filters and fieldname in filters:
				return self.list_rows.get(f"{fieldname}:{filters[fieldname]}", [])
		return []

	def _get_doc(self, values):
		doc = FakeDoc(values)
		self.docs.append(doc)
		return doc

	def _commit(self):
		self.commit_count += 1

	def _rollback(self):
		self.rollback_count += 1

	@staticmethod
	def valid_customer(**overrides):
		customer = {
			"customer_name": "New Customer",
			"contact": {"email": "new@example.com", "mobile": "9999999999"},
			"address": {"address_line1": "1 Test Road", "city": "Pune", "state": "Maharashtra", "country": "India"},
			"gstin": "27ABCDE1234F1Z5",
		}
		customer.update(overrides)
		return customer

	def test_exact_customer_resolves_to_reusable_reference(self):
		candidate = {"value": "CUST-0001", "label": "Acme", "customer_name": "Acme"}
		with patch.object(customer_service, "resolve_customer", return_value={"status": "resolved", "candidate": candidate, "match_type": "exact"}):
			result = customer_service.resolve_customer_for_workflow("Acme")
		self.assertEqual(result["status"], "resolved")
		self.assertEqual(result["customer"], {"doctype": "Customer", "name": "CUST-0001", "customer_name": "Acme"})

	def test_multiple_customers_require_selection(self):
		with patch.object(customer_service, "resolve_customer", return_value={"status": "ambiguous", "candidates": [{"value": "CUST-1"}, {"value": "CUST-2"}]}):
			result = customer_service.resolve_customer_for_workflow("Acme")
		self.assertEqual(result["status"], "needs_selection")
		self.assertEqual(len(result["candidates"]), 2)

	def test_no_customer_requires_creation(self):
		with patch.object(customer_service, "resolve_customer", return_value={"status": "not_found", "candidates": []}):
			self.assertEqual(customer_service.resolve_customer_for_workflow("New Customer")["status"], "needs_customer_creation")

	def test_each_supported_duplicate_identifier_blocks_preparation(self):
		for fieldname, value, input_change in (
			("name", "New Customer", {}),
			("mobile_no", "9999999999", {}),
			("email_id", "new@example.com", {}),
			("gstin", "27ABCDE1234F1Z5", {}),
		):
			with self.subTest(fieldname=fieldname):
				self.list_rows = {f"{fieldname}:{value}": [{"name": "CUST-EXISTING", "customer_name": "Existing"}]}
				result = customer_service.prepare_customer(self.valid_customer(**input_change))
				self.assertEqual(result["status"], "duplicate_suspected")
				self.assertEqual(result["duplicates"][0]["identifier"], fieldname)

	def test_valid_preparation_does_not_write(self):
		result = customer_service.prepare_customer(self.valid_customer())
		self.assertEqual(result["status"], "ready")
		self.assertIn("approval_token", result)
		self.assertEqual(self.commit_count, 0)
		self.assertTrue(all(not doc.insert_calls for doc in self.docs))

	def test_invalid_customer_data_is_rejected(self):
		result = customer_service.prepare_customer(self.valid_customer(customer_type="Not a Customer Type"))
		self.assertEqual(result["status"], "invalid_value")

	def test_supplied_optional_customer_link_uses_generic_resolution(self):
		prepared = customer_service.prepare_customer(self.valid_customer(customer_group="commercial"))
		self.assertEqual(prepared["status"], "ready")
		self.assertEqual(approvals._approvals[prepared["approval_token"]].payload["customer_group"], "Commercial")

	def test_supplied_optional_customer_link_never_guesses_or_leaks(self):
		ambiguous = customer_service.prepare_customer(self.valid_customer(customer_group="com"))
		self.assertEqual(ambiguous["status"], "needs_selection")
		self.assertEqual(ambiguous["fieldname"], "customer_group")
		not_found = customer_service.prepare_customer(self.valid_customer(customer_group="Unknown"))
		self.assertEqual(not_found["status"], "not_found")
		self.assertEqual(not_found["candidates"], [])

	def test_runtime_default_satisfies_required_customer_type(self):
		prepared = customer_service.prepare_customer(self.valid_customer())
		self.assertEqual(prepared["status"], "ready")
		self.assertEqual(approvals._approvals[prepared["approval_token"]].payload["customer_type"], "Company")

	def test_custom_mandatory_exposed_field_is_reported_from_metadata(self):
		self.meta_fields.append(
			SimpleNamespace(fieldname="custom_registration_number", label="Registration Number", fieldtype="Data", reqd=1)
		)
		with patch.object(
			customer_config,
			"CREATION_FIELDS",
			customer_config.CREATION_FIELDS + ("custom_registration_number",),
		):
			result = customer_service.prepare_customer(self.valid_customer())
		self.assertEqual(result["status"], "needs_input")
		self.assertEqual(result["missing"], ["customer.custom_registration_number"])
		self.assertEqual(
			result["missing_fields"],
			[
				{
					"doctype": "Customer",
					"fieldname": "custom_registration_number",
					"path": "customer.custom_registration_number",
					"label": "Registration Number",
					"fieldtype": "Data",
					"reason": "mandatory",
					"source": "erpnext_metadata",
				}
			],
		)

	def test_user_without_customer_create_permission_is_rejected(self):
		with patch.object(self.fake_frappe, "has_permission", side_effect=lambda doctype, *_: doctype != "Customer"):
			result = customer_service.prepare_customer(self.valid_customer())
		self.assertEqual(result["status"], "permission_denied")
		self.assertEqual(result["missing_permissions"], ["Customer"])

	def test_wrong_confirmation_state_is_rejected(self):
		result = customer_service.confirm_customer("not-issued", True)
		self.assertEqual(result["code"], "CONFIRMATION_EXPIRED")

	def test_expired_confirmation_is_rejected(self):
		prepared = customer_service.prepare_customer(self.valid_customer())
		approvals._approvals[prepared["approval_token"]].created_at -= APPROVAL_TTL_SECONDS + 1
		result = customer_service.confirm_customer(prepared["approval_token"], True)
		self.assertEqual(result["code"], "CONFIRMATION_EXPIRED")

	def test_tampered_confirmation_context_is_rejected(self):
		prepared = customer_service.prepare_customer(self.valid_customer())
		self.fake_frappe.local.site = "other.localhost"
		result = customer_service.confirm_customer(prepared["approval_token"], True)
		self.assertEqual(result["code"], "CONFIRMATION_UNAVAILABLE")
		self.assertEqual(self.commit_count, 0)

	def test_valid_confirmation_creates_once_with_normal_permissions(self):
		prepared = customer_service.prepare_customer(self.valid_customer())
		result = customer_service.confirm_customer(prepared["approval_token"], True)
		self.assertEqual(result["status"], "created")
		self.assertFalse(result["idempotent"])
		self.assertEqual(self.commit_count, 1)
		inserted = self.docs[-1]
		self.assertEqual(inserted.insert_calls, [{"ignore_permissions": False, "ignore_links": False, "ignore_mandatory": False}])

	def test_confirmation_rechecks_duplicates_before_writing(self):
		prepared = customer_service.prepare_customer(self.valid_customer())
		self.list_rows = {"customer_name:New Customer": [{"name": "CUST-RACE", "customer_name": "New Customer"}]}
		result = customer_service.confirm_customer(prepared["approval_token"], True)
		self.assertEqual(result["status"], "duplicate_suspected")
		self.assertEqual(self.commit_count, 0)


if __name__ == "__main__":
	unittest.main()
