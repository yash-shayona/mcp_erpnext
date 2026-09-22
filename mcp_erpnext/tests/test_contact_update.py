from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import ApprovalMode, ApprovalStore
from mcp_erpnext.services.masters import contact_update as service
from mcp_erpnext.tests.approval_test_backend import FakeSharedApprovalBackend


class FakeDoc:
	def __init__(self, values):
		self.values = dict(values)
		self.save_calls = []
		self.modified = self.values.get("modified", "v1")
		self.name = self.values.get("name")

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return self.values.get(f"can_{permission}", True)

	def append(self, fieldname, value):
		self.values.setdefault(fieldname, []).append(value)

	def save(self, **kwargs):
		self.save_calls.append(kwargs)
		return self


class ContactUpdateTests(unittest.TestCase):
	def setUp(self):
		self.store = ApprovalStore(ApprovalMode.TRUSTED_HUMAN, backend=FakeSharedApprovalBackend())
		self.customer = FakeDoc({
			"doctype": "Customer", "name": "CUST-001", "modified": "customer-v1",
			"customer_primary_contact": "CONTACT-001",
		})
		self.contact = FakeDoc({
			"doctype": "Contact", "name": "CONTACT-001", "modified": "contact-v1",
			"first_name": "Amit", "last_name": "Shah", "full_name": "Amit Shah",
			"links": [{"link_doctype": "Customer", "link_name": "CUST-001"}],
			"email_ids": [
				{"name": "EMAIL-1", "email_id": "amit@example.com", "is_primary": 1},
				{"name": "EMAIL-2", "email_id": "amit.secondary@example.com", "is_primary": 0},
			],
			"phone_nos": [
				{"name": "PHONE-1", "phone": "9999999999", "is_primary_phone": 1, "is_primary_mobile_no": 1},
			],
		})
		self.docs = {"Customer:CUST-001": self.customer, "Contact:CONTACT-001": self.contact}
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			get_doc=lambda doctype, name: self.docs[f"{doctype}:{name}"],
			has_permission=lambda *_args, **_kwargs: True,
			PermissionError=frappe.PermissionError,
			DoesNotExistError=frappe.DoesNotExistError,
			db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
		)
		self.frappe_patch = patch.object(service, "frappe", self.fake_frappe)
		self.frappe_patch.start()
		self.approval_patch = patch.object(service, "approvals", self.store)
		self.approval_patch.start()
		self.search_patch = patch.object(service, "_search_contacts", return_value=[])
		self.search_patch.start()
		self.customer_patch = patch.object(service, "_load_customer", return_value=(self.customer, None))
		self.contact_patch = patch.object(service, "_load_contact", return_value=(self.contact, None))
		self.customer_patch.start()
		self.contact_patch.start()

	def tearDown(self):
		self.contact_patch.stop()
		self.customer_patch.stop()
		self.search_patch.stop()
		self.approval_patch.stop()
		self.frappe_patch.stop()

	def request(self, operation):
		return {
			"customer": {"doctype": "Customer", "name": "CUST-001"},
			"contact": {"doctype": "Contact", "name": "CONTACT-001"},
			"operation": operation,
		}

	def approve(self, prepared):
		self.store.record_trusted_user_approval(
			prepared["approval_token"], action="customer_contact_update",
			site="test.localhost", user="sales@example.com",
		)

	def test_contract_prepare_is_non_mutating_and_binds_child_state(self):
		prepared = service.prepare_contact_update(self.request({
			"action": "replace_primary_email",
			"current_email": "amit@example.com",
			"email": "amit.new@example.com",
		}))
		self.assertEqual(prepared["status"], "ready")
		self.assertEqual(prepared["preview"]["selected_current_value"], "amit@example.com")
		self.assertEqual(self.contact.save_calls, [])
		self.assertEqual(self.customer.save_calls, [])

	def test_confirm_replaces_email_row_in_place_and_refreshes_customer(self):
		prepared = service.prepare_contact_update(self.request({
			"action": "replace_primary_email",
			"current_email": "amit@example.com",
			"email": "amit.new@example.com",
		}))
		self.approve(prepared)
		result = service.confirm_contact_update(prepared["approval_token"], True)
		self.assertEqual(result["status"], "updated")
		self.assertEqual(self.contact.get("email_ids")[0]["name"], "EMAIL-1")
		self.assertEqual(self.contact.get("email_ids")[0]["email_id"], "amit.new@example.com")
		self.assertEqual(self.contact.save_calls, [{"ignore_permissions": False}])
		self.assertEqual(self.customer.save_calls, [{"ignore_permissions": False}])

	def test_set_primary_email_preserves_rows(self):
		prepared = service.prepare_contact_update(self.request({
			"action": "set_primary_email", "email": "amit.secondary@example.com",
		}))
		self.approve(prepared)
		result = service.confirm_contact_update(prepared["approval_token"], True)
		self.assertEqual(result["status"], "updated")
		self.assertEqual([row["is_primary"] for row in self.contact.get("email_ids")], [0, 1])

	def test_shared_contact_is_rejected_without_disclosing_other_link(self):
		self.contact.values["links"].append({"link_doctype": "Supplier", "link_name": "SUP-SECRET"})
		result = service.prepare_contact_update(self.request({"action": "set_primary_email", "email": "amit@example.com"}))
		self.assertEqual(result["code"], "CONTACT_SHARED_WITH_OTHER_PARTIES")
		self.assertNotIn("SUP-SECRET", str(result))

	def test_link_removed_after_prepare_is_stale(self):
		prepared = service.prepare_contact_update(self.request({"action": "set_primary_email", "email": "amit@example.com"}))
		self.approve(prepared)
		self.contact.values["links"] = []
		result = service.confirm_contact_update(prepared["approval_token"], True)
		self.assertEqual(result["code"], "CONTACT_STALE_STATE")
		self.assertEqual(self.contact.save_calls, [])

	def test_customer_write_permission_blocks_primary_update_before_save(self):
		self.customer.values["can_write"] = False
		result = service.prepare_contact_update(self.request({"action": "set_primary_email", "email": "amit@example.com"}))
		self.assertEqual(result["code"], "CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED")


if __name__ == "__main__":
	unittest.main()
