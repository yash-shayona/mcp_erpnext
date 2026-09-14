from __future__ import annotations

import unittest

from pydantic import ValidationError

from mcp_erpnext.contracts.accounts.customer_payment_entry import (
    CustomerPaymentEntryConfirmInput,
    CustomerPaymentEntryPrepareInput,
)


class CustomerPaymentEntryContractTests(unittest.TestCase):
    def test_mode_of_payment_destination(self):
        request = CustomerPaymentEntryPrepareInput(
            customer="CUST-0001", company="Acme", amount=100, mode_of_payment="Bank Transfer"
        )
        self.assertEqual(request.amount, 100)

    def test_bank_account_destination(self):
        request = CustomerPaymentEntryPrepareInput(
            customer="CUST-0001", company="Acme", amount=100, bank_account="BANK-0001"
        )
        self.assertEqual(request.bank_account, "BANK-0001")

    def test_amount_and_destination_validation(self):
        for amount in (0, -1, True, float("nan"), float("inf")):
            with self.assertRaises(ValidationError):
                CustomerPaymentEntryPrepareInput(
                    customer="CUST-0001", company="Acme", amount=amount, mode_of_payment="Cash"
                )
        for values in ({}, {"mode_of_payment": "Cash", "bank_account": "BANK-0001"}):
            with self.assertRaises(ValidationError):
                CustomerPaymentEntryPrepareInput(customer="CUST-0001", company="Acme", amount=100, **values)

    def test_raw_accounting_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            CustomerPaymentEntryPrepareInput(
                customer="CUST-0001", company="Acme", amount=100, mode_of_payment="Cash", paid_to="Debtors"
            )

    def test_confirm_has_only_approval_fields(self):
        with self.assertRaises(ValidationError):
            CustomerPaymentEntryConfirmInput(approval_token="opaque", confirm=True, amount=100)


if __name__ == "__main__":
    unittest.main()
