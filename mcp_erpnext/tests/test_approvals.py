from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from mcp_erpnext.approvals import (
	APPROVAL_TTL_SECONDS,
	ApprovalBackendError,
	ApprovalStore,
	FrappeApprovalBackend,
	approvals,
)
from mcp_erpnext.mcp_server import create_mcp
from mcp_erpnext.services.masters import customer as customer_service
from mcp_erpnext.services.masters import item as item_service
from mcp_erpnext.services.selling import quotation as quotation_service
from mcp_erpnext.services.selling import sales_order as sales_order_service
from mcp_erpnext.settings import ApprovalMode, MCPSettings
from mcp_erpnext.tests.approval_test_backend import (
	FakeSharedApprovalBackend,
	install_fake_backend,
	mutate_record,
	read_record,
)


class ApprovalStoreTests(unittest.TestCase):
	def setUp(self) -> None:
		self.backend = FakeSharedApprovalBackend()
		self.store = ApprovalStore(ApprovalMode.TRUSTED_HUMAN, backend=self.backend)
		install_fake_backend(approvals)
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
		mutate_record(self.store, self.backend, self.token, lambda approval: setattr(approval, "created_at", approval.created_at - APPROVAL_TTL_SECONDS - 1), ttl_seconds=0)
		approval, state = self.store.lookup(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "expired")

	def test_mutated_payload_is_rejected(self):
		mutate_record(self.store, self.backend, self.token, lambda approval: approval.payload.update({"doctype": "Quotation"}))
		approval, state = self.store.lookup(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "unavailable")

	def test_confirm_claim_requires_a_server_recorded_trusted_approval(self):
		approval, state = self.store.claim_for_confirm_write(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "not_trusted")

	def test_agent_delegated_claim_does_not_require_trusted_approval(self):
		store = ApprovalStore(ApprovalMode.AGENT_DELEGATED, backend=FakeSharedApprovalBackend())
		token = store.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)

		approval, state = store.claim_for_confirm_write(
			token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)

		self.assertIsNotNone(approval)
		self.assertEqual(state, "available")

	def test_store_defaults_to_agent_delegated(self):
		store = ApprovalStore(backend=FakeSharedApprovalBackend())
		token = store.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)

		self.assertEqual(
			store.claim_for_confirm_write(
				token,
				action="create_sales_order",
				site="test.localhost",
				user="sales@example.com",
			)[1],
			"available",
		)

	def test_server_settings_configure_the_shared_approval_policy(self):
		def settings(mode: ApprovalMode) -> MCPSettings:
			return MCPSettings(
				backend="direct",
				frappe_site="test.localhost",
				frappe_user="sales@example.com",
				erpnext_base_url=None,
				erpnext_api_key=None,
				erpnext_api_secret=None,
				approval_mode=mode,
			)

		create_mcp(settings(ApprovalMode.AGENT_DELEGATED))
		token = approvals.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)
		self.assertEqual(
			approvals.claim_for_confirm_write(
				token, action="create_sales_order", site="test.localhost", user="sales@example.com"
			)[1],
			"available",
		)

		create_mcp(settings(ApprovalMode.TRUSTED_HUMAN))
		token = approvals.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)
		self.assertEqual(
			approvals.claim_for_confirm_write(
				token, action="create_sales_order", site="test.localhost", user="sales@example.com"
			)[1],
			"not_trusted",
		)

	def test_agent_delegated_preserves_all_non_trust_bindings(self):
		backend = FakeSharedApprovalBackend()
		store = ApprovalStore(ApprovalMode.AGENT_DELEGATED, backend=backend)

		def create() -> str:
			return store.create(
				action="create_sales_order",
				site="test.localhost",
				user="sales@example.com",
				payload={"doctype": "Sales Order"},
			)

		for action, site, user in (
			("create_quotation", "test.localhost", "sales@example.com"),
			("create_sales_order", "other.localhost", "sales@example.com"),
			("create_sales_order", "test.localhost", "other@example.com"),
		):
			with self.subTest(action=action, site=site, user=user):
				approval, state = store.claim_for_confirm_write(create(), action=action, site=site, user=user)
				self.assertIsNone(approval)
				self.assertEqual(state, "unavailable")

		token = create()
		mutate_record(store, backend, token, lambda approval: approval.payload.update({"doctype": "Quotation"}))
		approval, state = store.claim_for_confirm_write(
			token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "unavailable")

		token = create()
		mutate_record(store, backend, token, lambda approval: setattr(approval, "created_at", approval.created_at - APPROVAL_TTL_SECONDS - 1), ttl_seconds=0)
		approval, state = store.claim_for_confirm_write(
			token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "expired")

		token = create()
		store.cancel(token, action="create_sales_order", site="test.localhost", user="sales@example.com")
		approval, state = store.claim_for_confirm_write(
			token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "consumed")

		token = create()
		self.assertEqual(
			store.claim_for_confirm_write(
				token, action="create_sales_order", site="test.localhost", user="sales@example.com"
			)[1],
			"available",
		)
		self.assertEqual(
			store.claim_for_confirm_write(
				token, action="create_sales_order", site="test.localhost", user="sales@example.com"
			)[1],
			"consumed",
		)

	def test_trusted_approval_is_user_operation_and_payload_bound_then_single_use(self):
		approval, state = self.store.record_trusted_user_approval(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertEqual(state, "available")
		self.assertIsNotNone(approval)

		for action, site, user in (
			("create_quotation", "test.localhost", "sales@example.com"),
			("create_sales_order", "other.localhost", "sales@example.com"),
			("create_sales_order", "test.localhost", "other@example.com"),
		):
			with self.subTest(action=action, site=site, user=user):
				claimed, claim_state = self.store.claim_for_confirm_write(
					self.token, action=action, site=site, user=user
				)
				self.assertIsNone(claimed)
				self.assertEqual(claim_state, "unavailable")

		claimed, claim_state = self.store.claim_for_confirm_write(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNotNone(claimed)
		self.assertEqual(claim_state, "available")
		claimed, claim_state = self.store.claim_for_confirm_write(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(claimed)
		self.assertEqual(claim_state, "consumed")

	def test_payload_tampering_after_trusted_approval_is_rejected(self):
		self.store.record_trusted_user_approval(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		mutate_record(self.store, self.backend, self.token, lambda approval: approval.payload.update({"doctype": "Quotation"}))
		approval, state = self.store.claim_for_confirm_write(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "unavailable")

	def test_declined_pending_operation_cannot_be_reused(self):
		self.store.cancel(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		approval, state = self.store.record_trusted_user_approval(
			self.token,
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
		)
		self.assertIsNone(approval)
		self.assertEqual(state, "consumed")

	def test_shared_backend_survives_a_store_restart_and_keeps_stable_digest(self):
		store_a = ApprovalStore(backend=self.backend)
		token = store_a.create(
			action="create_sales_order", site="site-a.localhost", user="alice@example.com",
			payload={"doctype": "Sales Order", "posting_date": "2026-09-12"},
		)
		created = read_record(store_a, token).created_at
		store_b = ApprovalStore(backend=self.backend)
		approval, state = store_b.lookup(
			token, action="create_sales_order", site="site-a.localhost", user="alice@example.com"
		)
		self.assertEqual(state, "available")
		self.assertEqual(approval.created_at, created)
		self.assertEqual(store_a._payload_digest(approval.payload), store_b._payload_digest(approval.payload))
		self.assertEqual(self.backend.read(token)[1] // 1000, APPROVAL_TTL_SECONDS - 1)

	def test_wrong_site_user_or_action_does_not_consume_the_shared_approval(self):
		for action, site, user in (
			("create_quotation", "site-a.localhost", "alice@example.com"),
			("create_sales_order", "site-b.localhost", "alice@example.com"),
			("create_sales_order", "site-a.localhost", "bob@example.com"),
		):
			with self.subTest(action=action, site=site, user=user):
				approval, state = self.store.claim_for_confirm_write(
					self.token, action=action, site=site, user=user
				)
				self.assertIsNone(approval)
				self.assertEqual(state, "unavailable")
		self.store.record_trusted_user_approval(
			self.token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		self.assertEqual(self.store.claim_for_confirm_write(
			self.token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)[1], "available")

	def test_only_one_concurrent_shared_claim_can_succeed(self):
		self.store.record_trusted_user_approval(
			self.token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		def claim():
			return self.store.claim_for_confirm_write(
				self.token, action="create_sales_order", site="test.localhost", user="sales@example.com"
			)[1]
		with ThreadPoolExecutor(max_workers=2) as executor:
			states = list(executor.map(lambda _unused: claim(), range(2)))
		self.assertEqual(states.count("available"), 1)
		self.assertEqual(states.count("consumed"), 1)

	def test_backend_failure_and_watch_conflict_fail_closed(self):
		failing = FakeSharedApprovalBackend()
		failing.fail_create = True
		with self.assertRaises(ApprovalBackendError):
			ApprovalStore(backend=failing).create(
				action="create_sales_order", site="test.localhost", user="sales@example.com", payload={}
			)
		self.backend.fail_read = True
		self.assertEqual(self.store.lookup(
			self.token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)[1], "unavailable")
		self.backend.fail_read = False
		self.store.record_trusted_user_approval(
			self.token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		self.backend.force_conflict = True
		self.assertEqual(self.store.claim_for_confirm_write(
			self.token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)[1], "unavailable")

	def test_private_frappe_key_fingerprints_the_public_token(self):
		key = FrappeApprovalBackend.key_name(self.token)
		self.assertNotIn(self.token, key)
		self.assertTrue(key.startswith("mcp_erpnext:approval:"))

	def test_every_current_confirm_write_rejects_model_confirm_true_without_trusted_approval(self):
		fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
		)
		for service, action, confirm in (
			(customer_service, "create_customer", customer_service.confirm_customer),
			(item_service, "create_item", item_service.confirm_item),
			(quotation_service, "create_quotation", quotation_service.confirm_quotation),
			(sales_order_service, "create_sales_order", sales_order_service.confirm_sales_order),
		):
			with self.subTest(action=action):
				token = self.store.create(
					action=action,
					site="test.localhost",
					user="sales@example.com",
					payload={"doctype": "Test"},
				)
				with patch.object(service, "approvals", self.store), patch.object(service, "frappe", fake_frappe):
					result = confirm(token, True)
				self.assertEqual(result["code"], "TRUSTED_APPROVAL_UNAVAILABLE")

	def test_delegated_sales_order_claim_reaches_the_write_path_without_trusted_approval(self):
		class FakeDoc:
			name = "SAL-ORD-TEST-0001"
			docstatus = 0

			def __init__(self):
				self.insert_calls = 0

			def insert(self, **_kwargs):
				self.insert_calls += 1

		store = ApprovalStore(ApprovalMode.AGENT_DELEGATED, backend=FakeSharedApprovalBackend())
		doc = FakeDoc()
		commits: list[bool] = []
		fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			has_permission=lambda *_: True,
			get_doc=lambda _payload: doc,
			db=SimpleNamespace(commit=lambda: commits.append(True), rollback=lambda: None),
		)
		token = store.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)

		with patch.object(sales_order_service, "approvals", store), patch.object(
			sales_order_service, "frappe", fake_frappe
		):
			result = sales_order_service.confirm_sales_order(token, True)

		self.assertEqual(result["status"], "created")
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(commits, [True])

	def test_sales_order_trusted_claim_rechecks_permission_and_is_single_use(self):
		class FakeDoc:
			name = "SAL-ORD-TEST-0001"
			docstatus = 0
			insert_calls = 0

			def insert(self, **_kwargs):
				self.insert_calls += 1

			def __init__(self):
				self.insert_calls = 0

		doc = FakeDoc()
		commits: list[bool] = []
		fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			has_permission=lambda *_: True,
			get_doc=lambda _payload: doc,
			db=SimpleNamespace(commit=lambda: commits.append(True), rollback=lambda: None),
		)
		token = self.store.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)
		self.store.record_trusted_user_approval(
			token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		with patch.object(sales_order_service, "approvals", self.store), patch.object(
			sales_order_service, "frappe", fake_frappe
		):
			result = sales_order_service.confirm_sales_order(token, True)
			self.assertEqual(result["status"], "created")
			self.assertEqual(doc.insert_calls, 1)
			self.assertEqual(commits, [True])
			self.assertEqual(sales_order_service.confirm_sales_order(token, True)["code"], "CONFIRMATION_CONSUMED")
			self.assertEqual(doc.insert_calls, 1)

		token = self.store.create(
			action="create_sales_order",
			site="test.localhost",
			user="sales@example.com",
			payload={"doctype": "Sales Order"},
		)
		self.store.record_trusted_user_approval(
			token, action="create_sales_order", site="test.localhost", user="sales@example.com"
		)
		fake_frappe.has_permission = lambda *_: False
		with patch.object(sales_order_service, "approvals", self.store), patch.object(
			sales_order_service, "frappe", fake_frappe
		):
			self.assertEqual(sales_order_service.confirm_sales_order(token, True)["code"], "PERMISSION_DENIED")
		self.assertEqual(doc.insert_calls, 1)
