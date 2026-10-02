from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mcp_erpnext.services.buying import purchase_order, purchase_order_to_purchase_receipt
from mcp_erpnext.services.masters import contact, customer, customer_contact, item
from mcp_erpnext.services.selling import (
	delivery_note_to_sales_invoice,
	quotation,
	quotation_to_sales_order,
	sales_invoice,
	sales_invoice_to_delivery_note,
	sales_order,
	sales_order_to_delivery_note,
	sales_order_to_sales_invoice,
)


class CreatePolicyEntryGuardTests(unittest.TestCase):
	def setUp(self):
		self.prepares = (
			lambda: customer.prepare_customer({}),
			lambda: item.prepare_item({}),
			lambda: contact.prepare_contact({}),
			lambda: customer_contact.prepare_customer_contact({"mode": "create", "customer": {"doctype": "Customer", "name": "C-1"}, "new_contact": {"first_name": "A"}}),
			lambda: quotation.prepare_quotation({}, []),
			lambda: sales_order.prepare_sales_order("C-1", []),
			lambda: sales_invoice.prepare_sales_invoice({}, []),
			lambda: quotation_to_sales_order.prepare_quotation_to_sales_order("Q-1"),
			lambda: sales_order_to_sales_invoice.prepare_sales_order_to_sales_invoice("SO-1"),
			lambda: sales_order_to_delivery_note.prepare_sales_order_to_delivery_note("SO-1"),
			lambda: sales_invoice_to_delivery_note.prepare_sales_invoice_to_delivery_note("SI-1"),
			lambda: delivery_note_to_sales_invoice.prepare_delivery_note_to_sales_invoice("DN-1"),
			lambda: purchase_order.prepare_purchase_order({}, []),
			lambda: purchase_order_to_purchase_receipt.prepare_purchase_order_to_purchase_receipt("PO-1", []),
		)
		self.executes = (
			lambda: customer.execute_customer({}),
			lambda: item.execute_item({}),
			lambda: contact.execute_contact({}),
			lambda: customer_contact.execute_customer_contact({"mode": "create"}),
			lambda: quotation.execute_quotation({}, []),
			lambda: sales_order.execute_sales_order(customer="C-1", items=[]),
			lambda: sales_invoice.execute_sales_invoice({}, []),
			lambda: quotation_to_sales_order.execute_quotation_to_sales_order("Q-1"),
			lambda: sales_order_to_sales_invoice.execute_sales_order_to_sales_invoice("SO-1"),
			lambda: sales_order_to_delivery_note.execute_sales_order_to_delivery_note("SO-1"),
			lambda: sales_invoice_to_delivery_note.execute_sales_invoice_to_delivery_note("SI-1"),
			lambda: delivery_note_to_sales_invoice.execute_delivery_note_to_sales_invoice("DN-1"),
			lambda: purchase_order.execute_purchase_order({}, []),
			lambda: purchase_order_to_purchase_receipt.execute_purchase_order_to_purchase_receipt("PO-1", []),
		)
		self.confirms = (
			lambda: customer.confirm_customer("opaque", True),
			lambda: item.confirm_item("opaque", True),
			lambda: contact.confirm_contact("opaque", True),
			lambda: quotation.confirm_quotation("opaque", True),
			lambda: sales_order.confirm_sales_order("opaque", True),
			lambda: sales_invoice.confirm_sales_invoice("opaque", True),
			lambda: quotation_to_sales_order.confirm_quotation_to_sales_order("opaque", True),
			lambda: sales_order_to_sales_invoice.confirm_sales_order_to_sales_invoice("opaque", True),
			lambda: sales_order_to_delivery_note.confirm_sales_order_to_delivery_note("opaque", True),
			lambda: sales_invoice_to_delivery_note.confirm_sales_invoice_to_delivery_note("opaque", True),
			lambda: delivery_note_to_sales_invoice.confirm_delivery_note_to_sales_invoice("opaque", True),
			lambda: purchase_order.confirm_purchase_order("opaque", True),
			lambda: purchase_order_to_purchase_receipt.confirm_purchase_order_to_purchase_receipt("opaque", True),
		)

	def test_disabled_prepare_and_execute_fail_closed_for_every_create_family(self):
		with patch.dict(os.environ, {}, clear=True):
			for index, operation in enumerate((*self.prepares, *self.executes)):
				with self.subTest(operation=index):
					self.assertEqual(operation()["code"], "CREATE_DISABLED")

	def test_prepare_and_execute_entry_modes_do_not_touch_approval_store(self):
		for mode, operations, expected in (
			("approval_required", self.executes, "APPROVAL_REQUIRED"),
			("direct", self.confirms, "DIRECT_EXECUTION_REQUIRED"),
		):
			with patch.dict(os.environ, {"MCP_CREATE_MODE": mode}, clear=True):
				for index, operation in enumerate(operations):
					with self.subTest(mode=mode, operation=index):
						self.assertEqual(operation()["code"], expected)


if __name__ == "__main__":
	unittest.main()
