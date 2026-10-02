from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from pydantic import ValidationError

from mcp_erpnext.contracts.shayona.credentials import (
    CredentialAggregateInput,
    CredentialQueryInput,
)
from mcp_erpnext.services.shayona import credentials
from mcp_erpnext.tools.shayona import credentials as credential_tools

SAFE_ROW = {
    "name": "ST-CSC-00001",
    "customer": "Example Customer",
    "domain_name": "example.com",
    "credential_type": "cPanel",
    "account_name": "Main Hosting",
    "account_identity": "main.example.com",
    "control_panel_url": "https://panel.example.com",
    "is_active": 1,
    "username": "SECRET-USERNAME-SENTINEL",
    "password": "SECRET-PASSWORD-SENTINEL",
}


def _meta(*fields: str, valid_columns: tuple[str, ...] | None = None):
    valid_columns = valid_columns or fields
    return SimpleNamespace(
        get_valid_columns=lambda: list(valid_columns),
        get_field=lambda fieldname: (
            SimpleNamespace(fieldtype="Data", options="URL")
            if fieldname == "control_panel_url"
            else None
        ),
    )


def _meta_with_control_panel(fieldtype="Data", options="URL"):
    meta = _meta(valid_columns=("doctype", *credentials.REQUIRED_FIELDS))
    meta.get_field = lambda fieldname: (
        SimpleNamespace(fieldtype=fieldtype, options=options)
        if fieldname == "control_panel_url"
        else None
    )
    return meta


class ShayonaCredentialServiceTests(unittest.TestCase):
    def _complete_meta(self):
        return _meta(
            valid_columns=("doctype", *credentials.REQUIRED_FIELDS),
        )

    @patch.object(frappe, "get_meta")
    @patch.object(frappe, "get_list", return_value=[SAFE_ROW])
    def test_search_uses_public_projection_and_excludes_secret_search_fields(
        self, get_list, get_meta
    ):
        get_meta.return_value = self._complete_meta()

        result = credentials.search_customer_service_credentials(
            {"query": "example.com", "limit": 10, "include_inactive": False}
        )

        self.assertNotIn("username", result["credentials"][0])
        self.assertNotIn("password", result["credentials"][0])
        self.assertEqual(
            result["credentials"][0]["control_panel_url"],
            SAFE_ROW["control_panel_url"],
        )
        kwargs = get_list.call_args.kwargs
        self.assertEqual(kwargs["fields"], list(credentials.PUBLIC_FIELDS))
        self.assertEqual(kwargs["ignore_permissions"], False)
        self.assertTrue(
            all(row[0] in credentials.SEARCH_FIELDS for row in kwargs["or_filters"])
        )

    @patch.object(frappe, "get_meta")
    @patch.object(frappe, "get_doc")
    def test_get_is_fixed_projection_and_does_not_decrypt_password(
        self, get_doc, get_meta
    ):
        get_meta.return_value = self._complete_meta()
        get_password = Mock()
        get_doc.return_value = SimpleNamespace(
            **SAFE_ROW,
            has_permission=lambda permission: permission == "read",
            get_password=get_password,
        )

        result = credentials.get_customer_service_credential("ST-CSC-00001")

        self.assertNotIn("username", result["credential"])
        self.assertNotIn("password", result["credential"])
        self.assertIn("control_panel_url", result["credential"])
        get_password.assert_not_called()

    @patch.object(frappe, "get_meta")
    @patch.object(frappe, "get_list", return_value=[])
    def test_query_cannot_filter_or_sort_secrets_and_keeps_active_default(
        self, get_list, get_meta
    ):
        get_meta.return_value = self._complete_meta()
        credentials.query_customer_service_credentials(
            {"limit": 10, "offset": 0, "sort_by": "name", "sort_order": "asc"}
        )
        kwargs = get_list.call_args.kwargs
        self.assertEqual(kwargs["filters"], {"is_active": 1})
        self.assertNotIn("username", kwargs["filters"])
        self.assertNotIn("password", kwargs["filters"])
        self.assertNotIn("control_panel_url", kwargs["order_by"])

        credentials.query_customer_service_credentials(
            {
                "limit": 10,
                "offset": 0,
                "sort_by": "name",
                "sort_order": "asc",
                "include_inactive": True,
            }
        )
        self.assertEqual(get_list.call_args.kwargs["filters"], {})

        credentials.query_customer_service_credentials(
            {
                "limit": 10,
                "offset": 0,
                "sort_by": "name",
                "sort_order": "asc",
                "is_active": False,
            }
        )
        self.assertEqual(get_list.call_args.kwargs["filters"], {"is_active": 0})

    def test_public_contracts_reject_secret_fields_and_url_grouping(self):
        with self.assertRaises(ValidationError):
            CredentialQueryInput(username="secret")
        with self.assertRaises(ValidationError):
            CredentialQueryInput(sort_by="username")
        with self.assertRaises(ValidationError):
            CredentialAggregateInput(metrics=["count"], group_by="control_panel_url")
        with self.assertRaises(ValidationError):
            CredentialAggregateInput(metrics=["count"], password="secret")

    @patch.object(credential_tools, "execute_tool_with_context")
    def test_typed_tool_adapter_uses_shared_runtime_and_rest_payload(self, execute):
        execute.return_value = {
            "status": "ok",
            "credentials": [],
            "count": 0,
            "limit": 20,
            "offset": 0,
        }
        credential_tools.query_customer_service_credentials(ctx=object())
        self.assertEqual(
            execute.call_args.args[1], "query_customer_service_credentials"
        )
        self.assertEqual(
            execute.call_args.kwargs["rest_arguments"],
            {
                "name": None,
                "customer": None,
                "domain_name": None,
                "credential_type": None,
                "account_name": None,
                "account_identity": None,
                "is_active": None,
                "include_inactive": False,
                "limit": 20,
                "offset": 0,
                "sort_by": "name",
                "sort_order": "asc",
            },
        )

    @patch.object(frappe, "get_meta")
    def test_incomplete_live_schema_fails_closed_with_bounded_error(self, get_meta):
        get_meta.return_value = _meta("name", "customer")
        result = credentials.query_customer_service_credentials(
            {"limit": 1, "offset": 0, "sort_by": "name", "sort_order": "asc"}
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "CREDENTIAL_SCHEMA_UNAVAILABLE")

    @patch.object(frappe, "get_meta")
    @patch.object(frappe, "get_list")
    def test_missing_control_panel_url_fails_before_query(self, get_list, get_meta):
        get_meta.return_value = _meta(
            valid_columns=("doctype", *credentials.REQUIRED_FIELDS)
        )
        get_meta.return_value.get_field = lambda _fieldname: None
        result = credentials.query_customer_service_credentials(
            {"limit": 1, "offset": 0, "sort_by": "name", "sort_order": "asc"}
        )
        self.assertEqual(result["code"], "CREDENTIAL_SCHEMA_UNAVAILABLE")
        get_list.assert_not_called()

    @patch.object(frappe, "get_meta")
    def test_wrong_control_panel_url_fieldtype_fails_closed(self, get_meta):
        get_meta.return_value = _meta_with_control_panel(fieldtype="Link")
        result = credentials.query_customer_service_credentials(
            {"limit": 1, "offset": 0, "sort_by": "name", "sort_order": "asc"}
        )
        self.assertEqual(result["code"], "CREDENTIAL_SCHEMA_UNAVAILABLE")

    @patch.object(frappe, "get_meta")
    def test_wrong_control_panel_url_options_fails_closed(self, get_meta):
        get_meta.return_value = _meta_with_control_panel(options="Text")
        result = credentials.query_customer_service_credentials(
            {"limit": 1, "offset": 0, "sort_by": "name", "sort_order": "asc"}
        )
        self.assertEqual(result["code"], "CREDENTIAL_SCHEMA_UNAVAILABLE")

    @patch.object(frappe, "get_meta")
    @patch.object(frappe, "get_doc")
    def test_get_permission_denial_is_not_converted_to_success(self, get_doc, get_meta):
        get_meta.return_value = self._complete_meta()
        get_doc.return_value = SimpleNamespace(
            **SAFE_ROW, has_permission=lambda _permission: False
        )
        with self.assertRaises(frappe.PermissionError):
            credentials.get_customer_service_credential("ST-CSC-00001")

    @patch.object(frappe, "get_meta")
    @patch.object(
        frappe, "get_list", return_value=[{"customer": "Example", "count": 2}]
    )
    def test_aggregate_is_count_only_and_permission_aware(self, get_list, get_meta):
        get_meta.return_value = self._complete_meta()
        result = credentials.aggregate_customer_service_credentials(
            {"metrics": ["count"], "group_by": "customer", "include_inactive": True}
        )
        self.assertEqual(result["results"], [{"count": 2, "group_value": "Example"}])
        kwargs = get_list.call_args.kwargs
        self.assertEqual(kwargs["ignore_permissions"], False)
        self.assertEqual(kwargs["fields"], ["customer", credentials.COUNT_FIELD])


if __name__ == "__main__":
    unittest.main()
