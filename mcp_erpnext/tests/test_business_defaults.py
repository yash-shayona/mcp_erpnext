from __future__ import annotations

import unittest
from types import SimpleNamespace

from mcp_erpnext.config.business_defaults import (
    BusinessDefaultKey,
    BusinessDefaultsConfigurationError,
    get_document_business_default,
    get_quotation_validity_days,
)


class BusinessDefaultsTests(unittest.TestCase):
    def resolve(self, config, doctype="Quotation", key=BusinessDefaultKey.PAYMENT_TERMS_TEMPLATE, company="Acme"):
        return get_document_business_default(
            doctype, key, company, frappe_module=SimpleNamespace(conf={"mcp_business_defaults": config})
        )

    def test_no_configuration_preserves_native_defaulting(self):
        self.assertIsNone(
            get_document_business_default(
                "Quotation",
                BusinessDefaultKey.PAYMENT_TERMS_TEMPLATE,
                "Acme",
                frappe_module=SimpleNamespace(conf={}),
            )
        )

    def test_company_value_overrides_site_value_without_cross_doctype_leakage(self):
        config = {
            "site": {
                "Quotation": {"payment_terms_template": "Site Quotation"},
                "Sales Order": {"payment_terms_template": "Site Order"},
            },
            "companies": {
                "Acme": {
                    "Quotation": {"payment_terms_template": "Acme Quotation"}
                }
            },
        }
        self.assertEqual(self.resolve(config), "Acme Quotation")
        self.assertEqual(self.resolve(config, company="Other"), "Site Quotation")
        self.assertEqual(
            self.resolve(config, doctype="Sales Order", company="Acme"), "Site Order"
        )

    def test_malformed_or_arbitrary_configuration_is_rejected(self):
        invalid_values = (
            [],
            {"unknown": {}},
            {"site": {"Delivery Note": {}}},
            {"site": {"Quotation": {"warehouse": "Stores - A"}}},
            {"site": {"Quotation": {"payment_terms_template": "  "}}},
            {"companies": {"": {}}},
        )
        for config in invalid_values:
            with self.subTest(config=config), self.assertRaises(
                BusinessDefaultsConfigurationError
            ):
                self.resolve(config)

    def test_unsupported_requested_key_is_rejected(self):
        with self.assertRaises(BusinessDefaultsConfigurationError):
            self.resolve({}, key="warehouse")


    def test_quotation_validity_days(self):
        self.assertEqual(get_quotation_validity_days(frappe_module=SimpleNamespace(conf={})), 0)
        self.assertEqual(get_quotation_validity_days(frappe_module=SimpleNamespace(conf={"mcp_business_defaults":{"quotation_validity_days":30}})),30)


if __name__ == "__main__":
    unittest.main()
