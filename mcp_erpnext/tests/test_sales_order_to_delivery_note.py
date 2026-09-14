from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from mcp_erpnext.approvals import approvals
from mcp_erpnext.services.selling import sales_order_to_delivery_note as service
from mcp_erpnext.tests.approval_test_backend import install_fake_backend


class Row:
	def __init__(self, **values):
		self.values = values

	def get(self, key, default=None):
		return self.values.get(key, default)


class Document:
	def __init__(self, doctype, name, *, docstatus=0, items=None, **values):
		self.doctype = doctype
		self.name = name
		self.docstatus = docstatus
		self.items = items or []
		self.values = values
		self.packed_items = values.pop("packed_items", [])
		self.insert_calls = []

	def get(self, key, default=None):
		if key == "items":
			return self.items
		if key == "packed_items":
			return self.packed_items
		return self.values.get(key, default)

	def has_permission(self, permission):
		return self.values.get(f"can_{permission}", True)

	def insert(self, **kwargs):
		self.insert_calls.append(kwargs)
		return self


def source_sales_order():
	return Document(
		"Sales Order",
		"SAL-ORD-0001",
		docstatus=1,
		status="To Deliver and Bill",
		customer="CUST-001",
		customer_name="Acme Customer",
		company="Test Company",
		currency="INR",
		per_delivered=0,
		items=[Row(item_code="ITEM-001", qty=1, rate=500, delivered_qty=0)],
	)


def mapped_delivery_note(posting_time):
	return Document(
		"Delivery Note",
		"MAT-DN-0001",
		docstatus=0,
		customer="CUST-001",
		customer_name="Acme Customer",
		company="Test Company",
		currency="INR",
		posting_date="2026-09-14",
		posting_time=posting_time,
		total_qty=1,
		net_total=500,
		total_taxes_and_charges=0,
		grand_total=500,
		items=[
			Row(
				item_code="ITEM-001",
				item_name="Known Item",
				qty=1,
				uom="Nos",
				rate=500,
				amount=500,
				warehouse="Stores - TC",
				against_sales_order="SAL-ORD-0001",
				so_detail="SO-ITEM-0001",
			)
		],
	)


class SalesOrderToDeliveryNoteTests(unittest.TestCase):
	def setUp(self):
		self.backend = install_fake_backend(approvals)
		self.source = source_sales_order()
		self.first_target = mapped_delivery_note("10:00:00")
		self.second_target = mapped_delivery_note("10:00:01")
		self.targets = [self.first_target, self.second_target]
		self.fake_frappe = SimpleNamespace(
			session=SimpleNamespace(user="sales@example.com"),
			local=SimpleNamespace(site="test.localhost"),
			get_doc=lambda doctype, name: self.source,
			has_permission=lambda *_: True,
			DoesNotExistError=frappe.DoesNotExistError,
			PermissionError=frappe.PermissionError,
			ValidationError=frappe.ValidationError,
			db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
			throw=lambda message, error: (_ for _ in ()).throw(error(message)),
		)
		self.frappe_patch = patch.object(service, "frappe", self.fake_frappe)
		self.frappe_patch.start()

	def tearDown(self):
		self.frappe_patch.stop()
		self.backend.clear()

	def native(self, source_name):
		self.assertEqual(source_name, self.source.name)
		return self.targets.pop(0)

	def test_confirm_allows_native_posting_time_to_change(self):
		with patch.object(service, "_native", side_effect=self.native):
			prepared = service.prepare_sales_order_to_delivery_note(self.source.name)
		self.assertEqual(prepared["status"], "ready")
		approvals.record_trusted_user_approval(
			prepared["approval_token"],
			action=service._ACTION,
			site="test.localhost",
			user="sales@example.com",
		)
		with patch.object(service, "_native", side_effect=self.native):
			result = service.confirm_sales_order_to_delivery_note(
				prepared["approval_token"], True
			)
		self.assertEqual(result["status"], "created")
		self.assertEqual(self.first_target.insert_calls, [])
		self.assertEqual(len(self.second_target.insert_calls), 1)


if __name__ == "__main__":
	unittest.main()
