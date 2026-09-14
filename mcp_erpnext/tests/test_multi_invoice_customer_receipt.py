from __future__ import annotations

import unittest

from pydantic import ValidationError

from mcp_erpnext.contracts.accounts.multi_invoice_customer_receipt import (
    CustomerReceiptAllocation,
    MultiInvoiceCustomerReceiptConfirmInput,
    MultiInvoiceCustomerReceiptPrepareInput,
)


def _row(name: str, amount: float = 10) -> dict[str, object]:
    return {"sales_invoice": name, "allocated_amount": amount}


class MultiInvoiceCustomerReceiptContractTests(unittest.TestCase):
    def test_two_to_twenty_unique_allocations_are_accepted(self):
        request = MultiInvoiceCustomerReceiptPrepareInput(
            customer="CUST-1", amount=30,
            allocations=[_row("SINV-1", 10), _row("SINV-2", 20)],
            mode_of_payment="Bank Transfer",
        )
        self.assertEqual(len(request.allocations), 2)
        twenty = MultiInvoiceCustomerReceiptPrepareInput(
            customer="CUST-1", amount=200,
            allocations=[_row(f"SINV-{index}") for index in range(20)],
            bank_account="BANK-1",
        )
        self.assertEqual(len(twenty.allocations), 20)

    def test_reference_count_is_bounded(self):
        for rows in ([_row("SINV-1")], [_row(f"SINV-{index}") for index in range(21)]):
            with self.assertRaises(ValidationError):
                MultiInvoiceCustomerReceiptPrepareInput(customer="CUST-1", amount=10, allocations=rows, bank_account="BANK-1")

    def test_duplicate_invoice_is_rejected(self):
        with self.assertRaises(ValidationError):
            MultiInvoiceCustomerReceiptPrepareInput(customer="CUST-1", amount=20, allocations=[_row("SINV-1"), _row("SINV-1")], bank_account="BANK-1")

    def test_non_positive_boolean_and_non_finite_amounts_are_rejected(self):
        for amount in (0, -1, True, float("nan"), float("inf")):
            with self.assertRaises(ValidationError):
                CustomerReceiptAllocation(sales_invoice="SINV-1", allocated_amount=amount)
        with self.assertRaises(ValidationError):
            MultiInvoiceCustomerReceiptPrepareInput(customer="CUST-1", amount=True, allocations=[_row("SINV-1"), _row("SINV-2")], bank_account="BANK-1")

    def test_destination_is_mutually_exclusive(self):
        with self.assertRaises(ValidationError):
            MultiInvoiceCustomerReceiptPrepareInput(customer="CUST-1", amount=20, allocations=[_row("SINV-1"), _row("SINV-2")], mode_of_payment="Cash", bank_account="BANK-1")

    def test_raw_accounting_inputs_are_forbidden(self):
        forbidden = ("company", "party_account", "paid_to", "source_exchange_rate", "taxes", "deductions", "reference_doctype")
        for field in forbidden:
            payload = {"customer": "CUST-1", "amount": 20, "allocations": [_row("SINV-1"), _row("SINV-2")], "bank_account": "BANK-1", field: "not-public"}
            with self.assertRaises(ValidationError, msg=field):
                MultiInvoiceCustomerReceiptPrepareInput.model_validate(payload)

    def test_remarks_and_confirm_contract_are_bounded(self):
        with self.assertRaises(ValidationError):
            MultiInvoiceCustomerReceiptPrepareInput(customer="CUST-1", amount=20, allocations=[_row("SINV-1"), _row("SINV-2")], bank_account="BANK-1", remarks="x" * 1001)
        with self.assertRaises(ValidationError):
            MultiInvoiceCustomerReceiptConfirmInput(approval_token="token", confirm=True, amount=20)


if __name__ == "__main__":
    unittest.main()
