from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import ApprovalMode, ApprovalStore
from mcp_erpnext.services.masters import customer_primary_contact as service
from mcp_erpnext.services.masters import customer_contact as customer_contact_service
from mcp_erpnext.tests.approval_test_backend import FakeSharedApprovalBackend


class PrimaryFakeDoc:
	def __init__(self, values: dict, events: list[str]):
		object.__setattr__(self, "values", dict(values))
		object.__setattr__(self, "events", events)
		object.__setattr__(self, "permissions", {"read": True, "write": True})

	def __getattr__(self, fieldname):
		if fieldname in self.values:
			return self.values[fieldname]
		raise AttributeError(fieldname)

	def __setattr__(self, fieldname, value):
		if fieldname in {"values", "events", "permissions"}:
			object.__setattr__(self, fieldname, value)
		else:
			self.values[fieldname] = value

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def has_permission(self, permission):
		return self.permissions.get(permission, True)

	def has_link(self, doctype, name):
		return any(row.get("link_doctype") == doctype and row.get("link_name") == name for row in self.values.get("links", []))

	def save(self, **kwargs):
		self.events.append(f"save:{self.values['doctype']}:{self.name}")
		if self.values["doctype"] == "Contact" and self.values.get("is_primary_contact"):
			for document in getattr(self, "demote_on_primary", []):
				document.values["is_primary_contact"] = 0
		return self


class CustomerPrimaryContactServiceTests(unittest.TestCase):
	def setUp(self):
		self.events: list[str] = []
		links = lambda: [{"link_doctype": "Customer", "link_name": "CUST-001"}]
		self.customer = PrimaryFakeDoc({"doctype": "Customer", "name": "CUST-001", "modified": "customer-v1", "customer_primary_contact": "RAVI", "customer_name": "ABC"}, self.events)
		self.ravi = PrimaryFakeDoc({"doctype": "Contact", "name": "RAVI", "modified": "ravi-v1", "is_primary_contact": 1, "links": links(), "full_name": "Ravi", "email_id": "ravi@example.com"}, self.events)
		self.amit = PrimaryFakeDoc({"doctype": "Contact", "name": "AMIT", "modified": "amit-v1", "is_primary_contact": 0, "links": links(), "full_name": "Amit", "email_id": "amit@example.com"}, self.events)
		self.docs = {("Customer", "CUST-001"): self.customer, ("Contact", "RAVI"): self.ravi, ("Contact", "AMIT"): self.amit}
		self.amit.demote_on_primary = [self.ravi]
		self.commits = 0
		self.rollbacks = 0
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			get_doc=lambda doctype, name: self.docs[(doctype, name)],
			PermissionError=frappe.PermissionError,
			DoesNotExistError=frappe.DoesNotExistError,
			db=SimpleNamespace(commit=lambda: setattr(self, "commits", self.commits + 1), rollback=lambda: setattr(self, "rollbacks", self.rollbacks + 1)),
		)
		self.approvals = ApprovalStore(ApprovalMode.TRUSTED_HUMAN, backend=FakeSharedApprovalBackend())
		self.frappe_patch = patch.object(service, "frappe", self.fake_frappe)
		self.customer_contact_frappe_patch = patch.object(customer_contact_service, "frappe", self.fake_frappe)
		self.approval_patch = patch.object(service, "approvals", self.approvals)
		self.frappe_patch.start()
		self.customer_contact_frappe_patch.start()
		self.approval_patch.start()

	def tearDown(self):
		self.approval_patch.stop()
		self.customer_contact_frappe_patch.stop()
		self.frappe_patch.stop()

	def _request(self):
		return {"customer": {"doctype": "Customer", "name": "CUST-001"}, "contact": {"doctype": "Contact", "name": "AMIT"}}

	def _prepare(self):
		with patch.object(service, "get_contacts_linking_to", return_value=[{"name": "RAVI"}, {"name": "AMIT"}]):
			return service.prepare_customer_primary_contact(self._request())

	def _approve(self, prepared):
		self.approvals.record_trusted_user_approval(prepared["approval_token"], action="customer_primary_contact", site="test.localhost", user="sales@example.com")

	def test_replaces_current_primary_with_native_save_order(self):
		prepared = self._prepare()
		self.assertEqual(prepared["status"], "ready")
		self._approve(prepared)
		with patch.object(service, "get_contacts_linking_to", return_value=[{"name": "RAVI"}, {"name": "AMIT"}]):
			result = service.confirm_customer_primary_contact(prepared["approval_token"], True)
		self.assertEqual(result["status"], "promoted")
		self.assertEqual(self.events, ["save:Contact:AMIT", "save:Customer:CUST-001"])
		self.assertEqual(self.commits, 1)

	def test_already_primary_is_idempotent_without_save(self):
		self.customer.values["customer_primary_contact"] = "AMIT"
		self.amit.values["is_primary_contact"] = 1
		self.ravi.values["is_primary_contact"] = 0
		prepared = self._prepare()
		self._approve(prepared)
		with patch.object(service, "get_contacts_linking_to", return_value=[{"name": "RAVI"}, {"name": "AMIT"}]):
			result = service.confirm_customer_primary_contact(prepared["approval_token"], True)
		self.assertEqual(result["status"], "already_primary")
		self.assertEqual(self.events, [])
		self.assertEqual(self.commits, 0)

	def test_selected_shared_contact_is_rejected_without_mutation(self):
		self.amit.values["links"].append({"link_doctype": "Supplier", "link_name": "SUP-001"})
		result = self._prepare()
		self.assertEqual(result["code"], "CONTACT_SHARED_WITH_OTHER_PARTIES")
		self.assertEqual(self.events, [])

	def test_multiple_customer_primaries_are_inconsistent(self):
		self.amit.values["is_primary_contact"] = 1
		result = self._prepare()
		self.assertEqual(result["code"], "CONTACT_PRIMARY_STATE_INCONSISTENT")

	def test_changed_customer_state_is_stale(self):
		prepared = self._prepare()
		self.customer.values["modified"] = "customer-v2"
		self._approve(prepared)
		with patch.object(service, "get_contacts_linking_to", return_value=[{"name": "RAVI"}, {"name": "AMIT"}]):
			result = service.confirm_customer_primary_contact(prepared["approval_token"], True)
		self.assertEqual(result["code"], "CUSTOMER_PRIMARY_CONTACT_STALE")
		self.assertEqual(self.events, [])


if __name__ == "__main__":
	unittest.main()
