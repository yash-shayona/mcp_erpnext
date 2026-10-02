"""Permission-aware, allowlisted Supplier read and aggregate services."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe

from ...public_errors import defined_error
from ..common.aggregate import (
    build_aggregate_field,
    build_aggregate_fields,
    execute_aggregate,
    shape_aggregate_rows,
)

_FIELDS = frozenset(
    {
        "name",
        "supplier_name",
        "supplier_group",
        "supplier_type",
        "country",
        "default_currency",
        "disabled",
        "owner",
        "creation",
        "modified",
    }
)
_SORT_FIELDS = frozenset(
    {
        "name",
        "supplier_name",
        "supplier_group",
        "supplier_type",
        "country",
        "disabled",
        "creation",
        "modified",
    }
)
_GROUP_FIELDS = frozenset({"supplier_group", "supplier_type", "country", "disabled"})
_DIRECT_FILTER_FIELDS = (
    "name",
    "supplier_name",
    "supplier_group",
    "supplier_type",
    "country",
    "default_currency",
    "owner",
)
_METRICS = {"count": build_aggregate_field("COUNT", "*", "count")}


def _error(code: str, *, retryable: bool = False) -> dict[str, Any]:
	return defined_error(code, retryable=retryable)


def _range(
    filters: list[list[Any]], field: str, start: date | None, end: date | None
) -> None:
    if start and end:
        filters.append([field, "between", [start.isoformat(), end.isoformat()]])
    elif start:
        filters.append([field, ">=", start.isoformat()])
    elif end:
        filters.append([field, "<", (end + timedelta(days=1)).isoformat()])


def _filters(criteria: dict[str, Any]) -> list[list[Any]]:
    filters: list[list[Any]] = []
    _range(
        filters, "creation", criteria.get("created_from"), criteria.get("created_to")
    )
    _range(
        filters, "modified", criteria.get("modified_from"), criteria.get("modified_to")
    )
    for field in _DIRECT_FILTER_FIELDS:
        if criteria.get(field) is not None:
            filters.append([field, "=", criteria[field]])
    if criteria.get("disabled") is not None:
        filters.append(["disabled", "=", int(criteria["disabled"])])
    return filters


def _project(values: Any, fields: list[str]) -> dict[str, Any]:
    return {
        field: values.get(field)
        for field in fields
        if field in _FIELDS and values.get(field) is not None
    }


def get_supplier(supplier: str, fields: list[str]) -> dict[str, Any]:
    try:
        doc = frappe.get_doc("Supplier", supplier)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "supplier": supplier}
    if not doc.has_permission("read"):
        return _error("PERMISSION_DENIED")
    return {"status": "ok", "document": _project(doc, fields)}


def query_suppliers(criteria: dict[str, Any]) -> dict[str, Any]:
    fields = criteria["fields"]
    rows = frappe.get_list(
        "Supplier",
        filters=_filters(criteria),
        fields=fields,
        order_by=f"{criteria['sort_by']} {criteria['sort_order']}, name {criteria['sort_order']}",
        limit_start=criteria["offset"],
        limit_page_length=criteria["limit"],
        ignore_permissions=False,
    )
    return {
        "status": "ok",
        "suppliers": [_project(row, fields) for row in rows],
        "count": len(rows),
        "limit": criteria["limit"],
        "offset": criteria["offset"],
    }


def aggregate_suppliers(criteria: dict[str, Any]) -> dict[str, Any]:
    metrics, group_by = criteria["metrics"], criteria.get("group_by")
    fields, groups = build_aggregate_fields(metrics, _METRICS, group_by=group_by)
    rows = execute_aggregate(
        frappe.get_list,
        "Supplier",
        filters=_filters(criteria),
        fields=fields,
        groups=groups,
    )
    return {
        "status": "ok",
        "metrics": metrics,
        "group_by": group_by,
        "results": shape_aggregate_rows(rows, metrics, group_by=group_by),
    }
