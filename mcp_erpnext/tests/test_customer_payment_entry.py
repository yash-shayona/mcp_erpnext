from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from mcp_erpnext.contracts.accounts.customer_payment_entry import (
    CustomerPaymentEntryConfirmInput,
    CustomerPaymentEntryPrepareInput,
)
from mcp_erpnext.services.accounts import customer_payment_entry as service


class CustomerPaymentEntryContractTests(unittest.TestCase):
    def test_payment_approval_is_independent_of_create_mode(self):
        for mode in ("disabled", "direct"):
            with self.subTest(mode=mode), patch.dict(os.environ, {"MCP_CREATE_MODE": mode}), patch.object(
                service, "_build", return_value=(object(), {"kind": "bank", "identity": "BANK-1"}, None)
            ), patch.object(service, "_preview", return_value={"amount": 100}), patch.object(
                service, "_fingerprint", return_value="fingerprint"
            ), patch.object(service, "_user", return_value="user@example.com"), patch.object(
                service.frappe, "local", SimpleNamespace(site="test.localhost")
            ), patch.object(service.approvals, "prune_expired"), patch.object(
                service.approvals, "create", return_value="opaque"
            ) as create, patch.object(
                service.approvals, "claim_for_confirm_write", return_value=(None, "unavailable")
            ) as claim:
                prepared = service.prepare_customer_payment_entry({"amount": 100})
                confirmed = service.confirm_customer_payment_entry("opaque", True)
                self.assertEqual(prepared["status"], "ready")
                self.assertEqual(prepared["approval_token"], "opaque")
                self.assertEqual(confirmed["code"], "CONFIRMATION_UNAVAILABLE")
                create.assert_called_once()
                claim.assert_called_once()

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
