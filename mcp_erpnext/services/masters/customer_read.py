"""Permission-aware, allowlisted Customer read and query services."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe

from ...observability import new_error_reference
from ..common.aggregate import (
    build_aggregate_field,
    build_aggregate_fields,
    execute_aggregate,
    shape_aggregate_rows,
)


_FIELDS = frozenset(
    {
        "name",
        "customer_name",
        "customer_type",
        "customer_group",
        "territory",
        "email_id",
        "mobile_no",
        "tax_id",
        "disabled",
        "is_frozen",
        "account_manager",
        "default_currency",
        "default_price_list",
        "owner",
        "creation",
        "modified",
    }
)
_SORT_FIELDS = frozenset(
    {
        "name",
        "customer_name",
        "customer_type",
        "customer_group",
        "territory",
        "disabled",
        "creation",
        "modified",
    }
)
_GROUP_FIELDS = frozenset({"customer_group", "territory", "customer_type", "disabled"})
_METRICS = {"count": build_aggregate_field("COUNT", "*", "count")}
_DIRECT_FILTER_FIELDS = (
    "name",
    "customer_name",
    "customer_type",
    "customer_group",
    "territory",
    "email_id",
    "mobile_no",
    "tax_id",
    "account_manager",
    "owner",
)


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": False,
    }


def _date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _range(filters: list[list[Any]], field: str, start: date | None, end: date | None) -> None:
    if start and end:
        filters.append([field, "between", [_date(start), _date(end)]])
    elif start:
        filters.append([field, ">=", _date(start)])
    elif end:
        # ``creation`` and ``modified`` are DateTime fields; include the whole end day.
        filters.append([field, "<", (end + timedelta(days=1)).isoformat()])


def _filters(criteria: dict[str, Any]) -> list[list[Any]]:
    filters: list[list[Any]] = []
    _range(filters, "creation", criteria.get("created_from"), criteria.get("created_to"))
    _range(filters, "modified", criteria.get("modified_from"), criteria.get("modified_to"))
    for field in _DIRECT_FILTER_FIELDS:
        if criteria.get(field) is not None:
            filters.append([field, "=", criteria[field]])
    for field in ("disabled", "is_frozen"):
        if criteria.get(field) is not None:
            filters.append([field, "=", int(criteria[field])])
    return filters


def _project(values: Any, requested: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        field: values.get(field)
        for field in requested
        if field in _FIELDS and values.get(field) is not None
    }


def _requested_fields(requested: list[str]) -> list[str]:
    if any(field not in _FIELDS for field in requested):
        raise ValueError("Customer projection contains an unsupported field.")
    return requested


def _sort_expression(sort_by: str, sort_order: str) -> str:
    if sort_by not in _SORT_FIELDS or sort_order not in {"asc", "desc"}:
        raise ValueError("Customer sort contains an unsupported field or order.")
    return f"{sort_by} {sort_order}, name {sort_order}"


def _aggregate_fields(metrics: list[str], group_by: str | None) -> tuple[list[Any], str | None]:
    if any(metric not in _METRICS for metric in metrics):
        raise ValueError("Customer aggregate contains an unsupported metric.")
    if group_by is not None and group_by not in _GROUP_FIELDS:
        raise ValueError("Customer aggregate contains an unsupported grouping field.")
    fields, _ = build_aggregate_fields(metrics, _METRICS, group_by=group_by)
    return fields, group_by


def get_customer(customer: str, fields: list[str]) -> dict[str, Any]:
    fields = _requested_fields(fields)
    try:
        doc = frappe.get_doc("Customer", customer)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "customer": customer}
    if not doc.has_permission("read"):
        return _error("PERMISSION_DENIED", "The authenticated user cannot read that Customer.")
    return {"status": "ok", "document": _project(doc, fields)}


def query_customers(criteria: dict[str, Any]) -> dict[str, Any]:
    fields = _requested_fields(criteria["fields"])
    rows = frappe.get_list(
        "Customer",
        filters=_filters(criteria),
        fields=fields,
        order_by=_sort_expression(criteria["sort_by"], criteria["sort_order"]),
        limit_start=criteria["offset"],
        limit_page_length=criteria["limit"],
        ignore_permissions=False,
    )
    return {
        "status": "ok",
        "customers": [_project(row, fields) for row in rows],
        "count": len(rows),
        "limit": criteria["limit"],
        "offset": criteria["offset"],
    }


def aggregate_customers(criteria: dict[str, Any]) -> dict[str, Any]:
    metrics = criteria["metrics"]
    group_by = criteria.get("group_by")
    fields, group_by = _aggregate_fields(metrics, group_by)
    rows = execute_aggregate(
        frappe.get_list,
        "Customer",
        filters=_filters(criteria),
        fields=fields,
        groups=[group_by] if group_by else [],
    )
    results = shape_aggregate_rows(rows, metrics, group_by=group_by)
    return {"status": "ok", "metrics": metrics, "group_by": group_by, "results": results}
