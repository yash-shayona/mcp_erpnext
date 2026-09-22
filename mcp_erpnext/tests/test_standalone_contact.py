from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.contracts.masters.contact import ContactCreateInput
from mcp_erpnext.services.masters import contact as service
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import FakeSharedApprovalBackend


class FakeContact:
	def __init__(self, values: dict):
		self.values = dict(values)
		self.name = self.values.get("name", "CONTACT-NEW")
		self.insert_calls: list[dict] = []

	def get(self, fieldname: str, default=None):
		return self.values.get(fieldname, default)

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self


class StandaloneContactServiceTests(unittest.TestCase):
	def setUp(self):
		self.approval_store = ApprovalStore(
			ApprovalMode.TRUSTED_HUMAN, backend=FakeSharedApprovalBackend()
		)
		self.created: list[FakeContact] = []
		self.commits = 0
		self.rollbacks = 0
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			has_permission=lambda *_args, **_kwargs: True,
			PermissionError=frappe.PermissionError,
			db=SimpleNamespace(commit=self._commit, rollback=self._rollback),
			get_doc=self._get_doc,
		)
		self.frappe_patch = patch.object(service, "frappe", self.fake_frappe)
		self.frappe_patch.start()
		self.approval_patch = patch.object(service, "approvals", self.approval_store)
		self.approval_patch.start()
		self.duplicates_patch = patch.object(service, "_duplicate_contacts", return_value=[])
		self.duplicates_patch.start()
		self.email_patch = patch.object(service, "validate_email_address", side_effect=lambda value, throw=False: value)
		self.phone_patch = patch.object(service, "validate_phone_number", return_value=True)
		self.email_patch.start()
		self.phone_patch.start()

	def tearDown(self):
		self.phone_patch.stop()
		self.email_patch.stop()
		self.duplicates_patch.stop()
		self.approval_patch.stop()
		self.frappe_patch.stop()

	def _commit(self):
		self.commits += 1

	def _rollback(self):
		self.rollbacks += 1

	def _get_doc(self, payload):
		doc = FakeContact(payload)
		self.created.append(doc)
		return doc

	def _request(self):
		return {
			"contact": {
				"first_name": " Amit ",
				"middle_name": "K",
				"last_name": "Shah",
				"designation": "Sales",
				"department": "West",
				"email": "amit@example.com",
				"mobile": "9999999999",
				"phone": "011-44444444",
			}
		}

	def test_contract_rejects_relationship_and_system_fields(self):
		with self.assertRaises(ValueError):
			ContactCreateInput(first_name="Amit", links=[])

	def test_prepare_is_non_mutating_and_bounded(self):
		with patch.object(service.frappe, "get_doc", side_effect=AssertionError("prepare inserted")):
			result = service.prepare_contact(self._request())
		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["preview"]["full_name"], "Amit K Shah")
		self.assertEqual(self.commits, 0)
		approval, state = self.approval_store.lookup(
			result["approval_token"], action="contact_create", site="test.localhost", user="sales@example.com"
		)
		self.assertEqual(state, "available")
		self.assertNotIn("links", approval.payload["values"])

	def test_confirm_constructs_separate_primary_phone_rows_and_commits_once(self):
		prepared = service.prepare_contact(self._request())
		self.approval_store.record_trusted_user_approval(
			prepared["approval_token"], action="contact_create", site="test.localhost", user="sales@example.com"
		)
		result = service.confirm_contact(prepared["approval_token"], True)
		self.assertEqual(result["status"], "created")
		self.assertEqual(self.commits, 1)
		self.assertEqual(self.created[0].insert_calls, [{"ignore_permissions": False}])
		payload = self.created[0].values
		self.assertNotIn("links", payload)
		self.assertEqual(payload["email_ids"], [{"email_id": "amit@example.com", "is_primary": 1}])
		self.assertEqual(
			payload["phone_nos"],
			[
				{"phone": "9999999999", "is_primary_mobile_no": 1, "is_primary_phone": 0},
				{"phone": "011-44444444", "is_primary_phone": 1, "is_primary_mobile_no": 0},
			],
		)

	def test_approval_replay_cannot_write_twice(self):
		prepared = service.prepare_contact(self._request())
		self.approval_store.record_trusted_user_approval(
			prepared["approval_token"], action="contact_create", site="test.localhost", user="sales@example.com"
		)
		self.assertEqual(service.confirm_contact(prepared["approval_token"], True)["status"], "created")
		second = service.confirm_contact(prepared["approval_token"], True)
		self.assertEqual(second["code"], "CONFIRMATION_CONSUMED")
		self.assertEqual(len(self.created), 1)


if __name__ == "__main__":
	unittest.main()
