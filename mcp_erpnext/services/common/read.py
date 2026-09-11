"""Shared, permission-aware retrieval for supported existing transactions."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe

from ...observability import new_error_reference

MAX_LIMIT = 50

_DOCUMENTS = {
    "Sales Order": {
        "party_field": "customer",
        "primary_field": "transaction_date",
        "secondary_field": "delivery_date",
        "fields": (
            "name",
            "customer",
            "transaction_date",
            "delivery_date",
            "docstatus",
            "status",
            "currency",
            "grand_total",
        ),
        "child_table": "items",
    },
    "Quotation": {
        "party_field": "party_name",
        "primary_field": "transaction_date",
        "secondary_field": "valid_till",
        "fields": (
            "name",
            "party_name",
            "quotation_to",
            "transaction_date",
            "valid_till",
            "docstatus",
            "status",
            "currency",
            "grand_total",
        ),
        "child_table": "items",
    },
    "Purchase Order": {
        "party_field": "supplier",
        "primary_field": "transaction_date",
        "secondary_field": "schedule_date",
        "fields": (
            "name",
            "supplier",
            "transaction_date",
            "schedule_date",
            "docstatus",
            "status",
            "currency",
            "grand_total",
        ),
        "child_table": "items",
    },
    "Sales Invoice": {
        "party_field": "customer",
        "primary_field": "posting_date",
        "secondary_field": "due_date",
        "fields": (
            "name",
            "customer",
            "posting_date",
            "due_date",
            "docstatus",
            "status",
            "currency",
            "grand_total",
        ),
        "child_table": "items",
    },
}

_ITEM_FIELDS = ("item_code", "item_name", "qty", "rate", "amount")


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": False,
    }


def _definition(doctype: str) -> dict[str, Any] | None:
    return _DOCUMENTS.get(doctype)


def _summary(doc: Any, doctype: str, *, include_items: bool = False) -> dict[str, Any]:
    definition = _DOCUMENTS[doctype]
    party = doc.get(definition["party_field"])
    result = {
        "doctype": doctype,
        "name": doc.name,
        "docstatus": int(doc.docstatus),
        "status": doc.get("status"),
        "party": party,
        "transaction_date": doc.get(definition["primary_field"]),
        "secondary_date": doc.get(definition["secondary_field"]),
        "currency": doc.get("currency"),
        "grand_total": doc.get("grand_total"),
    }
    if include_items:
        result["items"] = [
            {
                field: row.get(field)
                for field in _ITEM_FIELDS
                if row.get(field) is not None
            }
            for row in (doc.get(definition["child_table"]) or [])
        ]
    return result


def _normalise_dates(value: date | str | None) -> str | None:
    return value.isoformat() if isinstance(value, date) else value


def _filters(doctype: str, criteria: dict[str, Any]) -> dict[str, Any]:
    definition = _DOCUMENTS[doctype]
    filters: dict[str, Any] = {}
    if doctype == "Quotation":
        filters["quotation_to"] = "Customer"
    if criteria.get("name"):
        filters["name"] = ["like", f"%{criteria['name'].strip()}%"]
    if criteria.get("party"):
        filters[definition["party_field"]] = criteria["party"].strip()
    if criteria.get("docstatus") is not None:
        filters["docstatus"] = criteria["docstatus"]
    if criteria.get("status"):
        filters["status"] = criteria["status"].strip()
    if criteria.get("date_from"):
        filters[definition["primary_field"]] = [
            ">=", _normalise_dates(criteria["date_from"])
        ]
    if criteria.get("date_to"):
        if criteria.get("date_from"):
            filters[definition["primary_field"]] = [
                "between",
                [
                    _normalise_dates(criteria["date_from"]),
                    _normalise_dates(criteria["date_to"]),
                ],
            ]
        else:
            filters[definition["primary_field"]] = [
                "<=", _normalise_dates(criteria["date_to"])
            ]
    return filters


def get_document(target: dict[str, str], profile: str) -> dict[str, Any]:
    doctype = target.get("doctype")
    if doctype not in _DOCUMENTS or doctype not in _profile_doctypes(profile):
        return _error(
            "DOCTYPE_NOT_ALLOWED",
            f"{doctype} is not available in the {profile} MCP profile.",
        )
    name = target.get("name", "").strip()
    if not name:
        return _error("INVALID_TARGET", "An exact document name is required.")
    try:
        doc = frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "doctype": doctype, "name": name}
    if not doc.has_permission("read"):
        return _error(
            "PERMISSION_DENIED", "The authenticated user cannot read that document."
        )
    return {"status": "ok", "document": _summary(doc, doctype, include_items=True)}


def search_documents(
    doctype: str, criteria: dict[str, Any], profile: str
) -> dict[str, Any]:
    if doctype not in _DOCUMENTS or doctype not in _profile_doctypes(profile):
        return _error(
            "DOCTYPE_NOT_ALLOWED",
            f"{doctype} is not available in the {profile} MCP profile.",
        )
    limit = min(max(int(criteria.get("limit") or 20), 1), MAX_LIMIT)
    rows = frappe.get_list(
        doctype,
        filters=_filters(doctype, criteria),
        fields=list(_DOCUMENTS[doctype]["fields"]),
        order_by=f"{_DOCUMENTS[doctype]['primary_field']} desc, name desc",
        limit_page_length=limit,
        ignore_permissions=False,
    )
    return {
        "status": "ok",
        "doctype": doctype,
        "results": [_summary(_Row(row), doctype) for row in rows],
        "count": len(rows),
        "limit": limit,
    }


def _profile_doctypes(profile: str) -> frozenset[str]:
    return {
        "sales": frozenset({"Quotation", "Sales Order", "Sales Invoice"}),
        "purchase": frozenset({"Purchase Order"}),
    }.get(profile, frozenset())


class _Row:
    """Small adapter giving list rows the same ``get`` interface as Documents."""

    def __init__(self, values: dict[str, Any]):
        self._values = values
        self.name = values.get("name")
        docstatus = values.get("docstatus", 0)
        self.docstatus = docstatus

    def get(self, fieldname: str, default: Any = None) -> Any:
        return self._values.get(fieldname, default)
