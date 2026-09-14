from __future__ import annotations

import unittest

from pydantic import ValidationError

from mcp_erpnext.contracts.accounts.sales_invoice_payment import (
    SalesInvoicePaymentConfirmInput,
    SalesInvoicePaymentPrepareInput,
)


class SalesInvoicePaymentContractTests(unittest.TestCase):
    def test_only_bounded_business_intent_is_accepted(self):
        request = SalesInvoicePaymentPrepareInput(
            sales_invoice="SINV-0001",
            amount=25.0,
            mode_of_payment="Bank Transfer",
            reference_no="UTR-1",
            remarks="Customer receipt",
        )
        self.assertEqual(request.sales_invoice, "SINV-0001")
        self.assertEqual(request.amount, 25.0)

    def test_raw_accounting_fields_and_extra_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            SalesInvoicePaymentPrepareInput(
                sales_invoice="SINV-0001",
                paid_to="Debtors - TC",
            )

    def test_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            SalesInvoicePaymentPrepareInput(sales_invoice="SINV-0001", amount=0)

    def test_confirm_has_no_business_fields(self):
        with self.assertRaises(ValidationError):
            SalesInvoicePaymentConfirmInput(
                approval_token="opaque-token", confirm=True, amount=10
            )


if __name__ == "__main__":
    unittest.main()
