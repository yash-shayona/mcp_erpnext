from __future__ import annotations

import unittest

from mcp_erpnext.approvals import APPROVAL_TTL_SECONDS, ApprovalStore


class ApprovalStoreTests(unittest.TestCase):
	def setUp(self) -> None:
		self.store = ApprovalStore()
		self.token = self.store.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)

	def test_approval_is_available_only_to_its_action_site_and_user(self):
		approval, state = self.store.lookup(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertEqual(state, "available")
		self.assertEqual(approval.payload, {"doctype": "Sales Order"})

		for action, site, user in (
			("create_quotation", "test.localhost", "sales@example.com"),
			("create_sales_order", "other.localhost", "sales@example.com"),
			("create_sales_order", "test.localhost", "other@example.com"),
		):
			with self.subTest(action=action, site=site, user=user):
				approval, state = self.store.lookup(self.token, action=action, site=site, user=user)
				self.assertIsNone(approval)
				self.assertEqual(state, "unavailable")

	def test_expired_approval_is_removed(self):
		self.store._approvals[self.token].created_at -= APPROVAL_TTL_SECONDS + 1
		approval, state = self.store.lookup(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "expired")
		self.assertNotIn(self.token, self.store._approvals)

	def test_mutated_payload_is_rejected(self):
		self.store._approvals[self.token].payload["doctype"] = "Quotation"
		approval, state = self.store.lookup(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "unavailable")
		self.assertNotIn(self.token, self.store._approvals)
