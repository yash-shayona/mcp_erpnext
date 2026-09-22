from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.services.masters import customer_contact as service
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import FakeSharedApprovalBackend


class FakeDoc:
	def __init__(self, values: dict, *, permissions: dict[str, bool] | None = None):
		self.values = dict(values)
		self.name = self.values.get("name", "CONTACT-NEW")
		self.modified = self.values.get("modified", "2026-09-22 10:00:00")
		self.customer_name = self.values.get("customer_name", "ABC Pvt Ltd")
		self.permissions = permissions or {"read": True, "write": True}
		self.insert_calls: list[dict] = []
		self.save_calls: list[dict] = []

	def get(self, fieldname: str, default=None):
		return self.values.get(fieldname, default)

	def has_permission(self, permission: str) -> bool:
		return self.permissions.get(permission, True)

	def has_link(self, doctype: str, name: str) -> bool:
		return any(
			row.get("link_doctype") == doctype and row.get("link_name") == name
			for row in self.values.get("links", [])
		)

	def run_method(self, method: str):
		if method == "validate":
			self.values["full_name"] = " ".join(
				value for value in (
					self.values.get("first_name"),
					self.values.get("middle_name"),
					self.values.get("last_name"),
					self.values.get("company_name"),
				) if value
			)
			self.values["email_id"] = next(
				(row.get("email_id") for row in self.values.get("email_ids", []) if row.get("is_primary")),
				self.values.get("email_id"),
			)
			self.values["mobile_no"] = next(
				(row.get("phone") for row in self.values.get("phone_nos", []) if row.get("is_primary_mobile_no")),
				self.values.get("mobile_no"),
			)
		return self

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self

	def append(self, fieldname: str, value: dict):
		self.values.setdefault(fieldname, []).append(value)

	def save(self, **kwargs):
		self.save_calls.append(kwargs)
		return self


class CustomerContactServiceTests(unittest.TestCase):
	def setUp(self):
		self.approval_store = ApprovalStore(
			ApprovalMode.TRUSTED_HUMAN, backend=FakeSharedApprovalBackend()
		)
		self.customer = FakeDoc({"doctype": "Customer", "name": "CUST-001", "customer_name": "ABC Pvt Ltd", "modified": "customer-v1"})
		self.contact = FakeDoc(
			{
				"doctype": "Contact",
				"name": "Amit Shah-ABC",
				"full_name": "Amit Shah",
				"email_id": "amit@example.com",
				"mobile_no": "9999999999",
				"modified": "contact-v1",
				"links": [{"link_doctype": "Customer", "link_name": "CUST-OTHER"}],
				"email_ids": [{"email_id": "amit@example.com", "is_primary": 1}],
				"phone_nos": [{"phone": "9999999999", "is_primary_mobile_no": 1}],
			},
		)
		self.docs = {"Customer:CUST-001": self.customer, "Contact:Amit Shah-ABC": self.contact}
		self.commits = 0
		self.rollbacks = 0
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			get_doc=self._get_doc,
			get_list=self._get_list,
			has_permission=lambda *_args, **_kwargs: True,
			PermissionError=frappe.PermissionError,
			DoesNotExistError=frappe.DoesNotExistError,
			db=SimpleNamespace(commit=self._commit, rollback=self._rollback),
		)
		self.patch = patch.object(service, "frappe", self.fake_frappe)
		self.patch.start()
		self.approval_patch = patch.object(service, "approvals", self.approval_store)
		self.approval_patch.start()
		self.links = []
		self.list_calls = []

	def tearDown(self):
		self.approval_patch.stop()
		self.patch.stop()

	def _get_doc(self, doctype_or_payload, name=None):
		if isinstance(doctype_or_payload, dict):
			doc = FakeDoc(doctype_or_payload)
			self.docs[f"Contact:{doc.name}"] = doc
			return doc
		return self.docs[f"{doctype_or_payload}:{name}"]

	def _get_list(self, doctype, *, filters=None, **_kwargs):
		self.list_calls.append({"doctype": doctype, "filters": filters, **_kwargs})
		if doctype == "Contact Email":
			return [
				{"parent": contact.name, "email_id": contact.get("email_id")}
				for contact in self.docs.values()
				if contact.name.startswith("Amit") and filters.get("email_id") == contact.get("email_id")
			]
		if doctype == "Contact Phone":
			return [
				{"parent": contact.name, "phone": contact.get("mobile_no")}
				for contact in self.docs.values()
				if contact.name.startswith("Amit") and "%" in str(filters.get("phone", ["", ""])[1])
			]
		if doctype == "Contact":
			name = (filters or {}).get("name")
			if name == "Amit Shah-ABC":
				return [{"name": name}]
		return []
		return []

	def test_global_child_search_uses_parent_contact_permission_context(self):
		result = service._child_parent_names("Contact Email", "email_id", "amit@example.com")

		self.assertEqual(result, {"Amit Shah-ABC"})
		self.assertEqual(self.list_calls[-1]["parent_doctype"], "Contact")

	def _commit(self):
		self.commits += 1

	def _rollback(self):
		self.rollbacks += 1

	def _target_links(self, *_args, **_kwargs):
		return [{"name": contact.name} for contact in self.links]

	def _create_request(self, **overrides):
		request = {
			"customer": {"doctype": "Customer", "name": "CUST-001"},
			"mode": "create",
			"existing_contact": None,
			"new_contact": {
				"first_name": "Neha",
				"last_name": "Shah",
				"email": "neha@example.com",
				"mobile": "8888888888",
			},
			"make_primary": False,
		}
		request.update(overrides)
		return request

	def test_create_prepare_is_non_mutating_and_native_payload_is_bounded(self):
		with patch.object(service, "get_contacts_linking_to", return_value=[]):
			result = service.prepare_customer_contact(self._create_request())
		self.assertEqual(result["status"], "ready")
		self.assertEqual(self.commits, 0)
		self.assertEqual(self.customer.get("links"), None)
		self.assertNotIn("approval_mode", result)

		service.approvals.record_trusted_user_approval(
			result["approval_token"], action="customer_contact", site="test.localhost", user="sales@example.com"
		)
		with patch.object(service, "get_contacts_linking_to", return_value=[]):
			created = service.confirm_customer_contact(result["approval_token"], True)
		self.assertEqual(created["status"], "created")
		self.assertEqual(self.commits, 1)
		new_doc = self.docs["Contact:CONTACT-NEW"]
		self.assertEqual(new_doc.insert_calls, [{"ignore_permissions": False}])
		self.assertEqual(new_doc.get("links"), [{"link_doctype": "Customer", "link_name": "CUST-001"}])
		self.assertEqual(new_doc.get("email_ids")[0]["email_id"], "neha@example.com")
		self.assertEqual(new_doc.get("phone_nos")[0]["is_primary_mobile_no"], 1)

	def test_link_prepare_and_confirm_adds_one_native_dynamic_link(self):
		with patch.object(service, "get_contacts_linking_to", return_value=[]):
			prepared = service.prepare_customer_contact(
				{
					"customer": {"doctype": "Customer", "name": "CUST-001"},
					"mode": "link",
					"existing_contact": {"doctype": "Contact", "name": "Amit Shah-ABC"},
					"new_contact": None,
					"make_primary": False,
				}
			)
		self.assertEqual(prepared["status"], "ready")
		service.approvals.record_trusted_user_approval(
			prepared["approval_token"], action="customer_contact", site="test.localhost", user="sales@example.com"
		)
		result = service.confirm_customer_contact(prepared["approval_token"], True)
		self.assertEqual(result["status"], "linked")
		self.assertFalse(result["idempotent"])
		self.assertEqual(self.contact.save_calls, [{"ignore_permissions": False}])
		self.assertEqual(self.contact.get("links")[-1], {"link_doctype": "Customer", "link_name": "CUST-001"})

	def test_existing_link_is_idempotent_without_save(self):
		self.contact.values["links"].append({"link_doctype": "Customer", "link_name": "CUST-001"})
		with patch.object(service, "get_contacts_linking_to", return_value=[]):
			prepared = service.prepare_customer_contact(
				{
					"customer": {"doctype": "Customer", "name": "CUST-001"},
					"mode": "link",
					"existing_contact": {"doctype": "Contact", "name": "Amit Shah-ABC"},
					"new_contact": None,
				}
			)
		service.approvals.record_trusted_user_approval(
			prepared["approval_token"], action="customer_contact", site="test.localhost", user="sales@example.com"
		)
		result = service.confirm_customer_contact(prepared["approval_token"], True)
		self.assertTrue(result["idempotent"])
		self.assertEqual(self.contact.save_calls, [])

	def test_duplicate_and_primary_are_bounded_errors(self):
		with patch.object(service, "get_contacts_linking_to", return_value=[{"name": self.contact.name}]), patch.object(
			service, "_load_contact", return_value=(self.contact, None)
		):
			duplicate = service.prepare_customer_contact(self._create_request(new_contact={"first_name": "Amit", "email": "amit@example.com"}))
		self.assertEqual(duplicate["code"], "CONTACT_DUPLICATE_SUSPECTED")
		primary = service.prepare_customer_contact(self._create_request(make_primary=True))
		self.assertEqual(primary["code"], "CONTACT_PRIMARY_UNSUPPORTED")

	def test_search_is_exact_globally_and_returns_no_link_names(self):
		result = service.search_contacts("amit@example.com", match="email")
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["count"], 1)
		self.assertEqual(result["contacts"][0]["name"], "Amit Shah-ABC")
		self.assertNotIn("links", result["contacts"][0])
		self.assertEqual(result["contacts"][0]["other_party_link_count"], 1)

	def test_global_name_search_does_not_fuzzy_enumerate_people(self):
		result = service.search_contacts("Amit Shah", match="name")
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["count"], 0)

	def test_link_confirmation_rejects_modified_contact(self):
		with patch.object(service, "get_contacts_linking_to", return_value=[]):
			prepared = service.prepare_customer_contact(
				{
					"customer": {"doctype": "Customer", "name": "CUST-001"},
					"mode": "link",
					"existing_contact": {"doctype": "Contact", "name": "Amit Shah-ABC"},
					"new_contact": None,
				}
			)
		self.contact.modified = "contact-v2"
		service.approvals.record_trusted_user_approval(
			prepared["approval_token"], action="customer_contact", site="test.localhost", user="sales@example.com"
		)
		result = service.confirm_customer_contact(prepared["approval_token"], True)
		self.assertEqual(result["code"], "CONTACT_LINK_STALE_STATE")
		self.assertEqual(self.contact.save_calls, [])

	def test_confirmation_true_cannot_self_authorize(self):
		with patch.object(service, "get_contacts_linking_to", return_value=[]):
			prepared = service.prepare_customer_contact(self._create_request())
			result = service.confirm_customer_contact(prepared["approval_token"], True)
		self.assertEqual(result["code"], "TRUSTED_APPROVAL_UNAVAILABLE")
		self.assertEqual(self.commits, 0)


if __name__ == "__main__":
	unittest.main()
