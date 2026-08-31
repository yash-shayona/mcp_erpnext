from __future__ import annotations

import unittest
from types import SimpleNamespace

from mcp_erpnext.services.common.field_value_resolver import (
    FIELD_TYPE_CATEGORIES,
    classify_fieldtype,
    resolve_contract_values,
    resolve_field_value,
)


class FieldValueResolverTests(unittest.TestCase):
    def field(self, fieldname: str, fieldtype: str, **values):
        return SimpleNamespace(
            fieldname=fieldname,
            label=fieldname.replace("_", " ").title(),
            fieldtype=fieldtype,
            **values,
        )

    def test_installed_frappe_fieldtype_catalog_is_classified(self):
        expected = {
            "Autocomplete",
            "Attach",
            "Attach Image",
            "Barcode",
            "Button",
            "Check",
            "Code",
            "Color",
            "Column Break",
            "Currency",
            "Data",
            "Date",
            "Datetime",
            "Duration",
            "Dynamic Link",
            "Float",
            "Fold",
            "Geolocation",
            "Heading",
            "HTML",
            "HTML Editor",
            "Icon",
            "Image",
            "Int",
            "JSON",
            "Link",
            "Long Text",
            "Markdown Editor",
            "Password",
            "Percent",
            "Phone",
            "Read Only",
            "Rating",
            "Section Break",
            "Select",
            "Signature",
            "Small Text",
            "Tab Break",
            "Table",
            "Table MultiSelect",
            "Text",
            "Text Editor",
            "Time",
        }
        self.assertEqual(set(FIELD_TYPE_CATEGORIES), expected)
        self.assertEqual(classify_fieldtype("Link"), "reference")
        self.assertEqual(classify_fieldtype("Future Field"), "unsupported")

    def test_select_uses_metadata_options_for_exact_and_normalized_values(self):
        field = self.field("customer_type", "Select", options="Company\nIndividual")
        for supplied in ("Company", "company"):
            with self.subTest(supplied=supplied):
                result = resolve_field_value(
                    fieldname="customer_type",
                    field=field,
                    path_prefix="customer",
                    value=supplied,
                    source="user_input",
                    resolved_values={},
                    link_filters={},
                    get_list=lambda **_: [],
                )
                self.assertEqual(result["status"], "resolved")
                self.assertEqual(result["value"], "Company")

    def test_select_reports_invalid_and_ambiguous_values(self):
        field = self.field("customer_type", "Select", options="Company\nCompanion")
        invalid = resolve_field_value(
            fieldname="customer_type",
            field=field,
            path_prefix="customer",
            value="Other",
            source="user_input",
            resolved_values={},
            link_filters={},
            get_list=lambda **_: [],
        )
        self.assertEqual(invalid["status"], "invalid_value")
        self.assertEqual(invalid["allowed_values"], ["Company", "Companion"])
        ambiguous = resolve_field_value(
            fieldname="customer_type",
            field=field,
            path_prefix="customer",
            value="comp",
            source="user_input",
            resolved_values={},
            link_filters={},
            get_list=lambda **_: [],
        )
        self.assertEqual(ambiguous["status"], "needs_selection")

    def test_link_target_and_candidates_are_metadata_and_permission_scoped(self):
        field = self.field("item_group", "Link", options="Item Group")
        calls = []

        def get_list(doctype, **kwargs):
            calls.append((doctype, kwargs))
            return [{"name": "Products"}]

        result = resolve_field_value(
            fieldname="item_group",
            field=field,
            path_prefix="item",
            value="products",
            source="user_input",
            resolved_values={},
            link_filters={"is_group": 0},
            get_list=get_list,
        )
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["value"], "Products")
        self.assertEqual(result["target_doctype"], "Item Group")
        self.assertEqual(calls[0][0], "Item Group")
        self.assertFalse(calls[0][1]["ignore_permissions"])
        self.assertEqual(calls[0][1]["filters"]["is_group"], 0)

    def test_link_ambiguous_and_not_found_do_not_guess_or_leak(self):
        field = self.field("stock_uom", "Link", options="UOM")
        ambiguous = resolve_field_value(
            fieldname="stock_uom",
            field=field,
            path_prefix="item",
            value="pc",
            source="user_input",
            resolved_values={},
            link_filters={},
            get_list=lambda *_args, **_kwargs: [{"name": "Piece"}, {"name": "Pcs"}],
        )
        self.assertEqual(ambiguous["status"], "needs_selection")
        not_found = resolve_field_value(
            fieldname="stock_uom",
            field=field,
            path_prefix="item",
            value="Private UOM",
            source="user_input",
            resolved_values={},
            link_filters={},
            get_list=lambda *_args, **_kwargs: [],
        )
        self.assertEqual(not_found["status"], "not_found")
        self.assertEqual(not_found["candidates"], [])

    def test_boolean_and_scalar_values_are_normalized_or_rejected(self):
        check = self.field("is_sales_item", "Check")
        self.assertEqual(
            resolve_field_value(
                fieldname="is_sales_item",
                field=check,
                path_prefix="item",
                value="true",
                source="mcp_policy",
                resolved_values={},
                link_filters={},
                get_list=lambda **_: [],
            )["value"],
            1,
        )
        invalid_boolean = resolve_field_value(
            fieldname="is_sales_item",
            field=check,
            path_prefix="item",
            value="yes",
            source="user_input",
            resolved_values={},
            link_filters={},
            get_list=lambda **_: [],
        )
        self.assertEqual(invalid_boolean["status"], "invalid_value")
        integer = self.field("lead_time_days", "Int")
        self.assertEqual(
            resolve_field_value(
                fieldname="lead_time_days",
                field=integer,
                path_prefix="item",
                value="4",
                source="user_input",
                resolved_values={},
                link_filters={},
                get_list=lambda **_: [],
            )["value"],
            4,
        )
        self.assertEqual(
            resolve_field_value(
                fieldname="lead_time_days",
                field=integer,
                path_prefix="item",
                value="four",
                source="user_input",
                resolved_values={},
                link_filters={},
                get_list=lambda **_: [],
            )["status"],
            "invalid_value",
        )

    def test_optional_absent_field_is_skipped_but_unsupported_supplied_field_fails(
        self,
    ):
        contract = {
            "values": {},
            "sources": {},
            "fields": {"notes": self.field("notes", "Table")},
        }
        self.assertEqual(
            resolve_contract_values(
                contract=contract,
                creation_fields=("notes",),
                path_prefix="customer",
                reference_filters={},
                get_list=lambda **_: [],
            )["status"],
            "resolved",
        )
        unsupported = resolve_field_value(
            fieldname="notes",
            field=self.field("notes", "Table"),
            path_prefix="customer",
            value=[],
            source="user_input",
            resolved_values={},
            link_filters={},
            get_list=lambda **_: [],
        )
        self.assertEqual(unsupported["status"], "unsupported_field")

    def test_dynamic_link_requires_its_metadata_controller(self):
        field = self.field(
            "reference_name", "Dynamic Link", options="reference_doctype"
        )
        result = resolve_field_value(
            fieldname="reference_name",
            field=field,
            path_prefix="example",
            value="ABC",
            source="user_input",
            resolved_values={},
            link_filters={},
            get_list=lambda **_: [],
        )
        self.assertEqual(result["status"], "unresolved_dependency")


if __name__ == "__main__":
    unittest.main()
