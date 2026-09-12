"""Permission-aware, allowlisted Quotation read, query, and aggregate services."""

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
        "quotation_to",
        "party_name",
        "customer_name",
        "transaction_date",
        "valid_till",
        "order_type",
        "company",
        "docstatus",
        "status",
        "currency",
        "conversion_rate",
        "selling_price_list",
        "price_list_currency",
        "total_qty",
        "base_total",
        "base_net_total",
        "total",
        "net_total",
        "base_grand_total",
        "grand_total",
        "base_total_taxes_and_charges",
        "total_taxes_and_charges",
        "additional_discount_percentage",
        "discount_amount",
        "referral_sales_partner",
        "customer_group",
        "territory",
        "owner",
        "creation",
        "modified",
    }
)
_SORT_FIELDS = frozenset(
    {
        "name",
        "party_name",
        "customer_name",
        "transaction_date",
        "valid_till",
        "order_type",
        "status",
        "company",
        "grand_total",
        "net_total",
        "total_qty",
        "creation",
        "modified",
    }
)
_GROUP_FIELDS = frozenset(
    {
        "quotation_to",
        "party_name",
        "customer_name",
        "status",
        "company",
        "currency",
        "order_type",
        "customer_group",
        "territory",
        "transaction_date",
    }
)
_METRICS = {
    "count": build_aggregate_field("COUNT", "*", "count"),
    "sum_grand_total": build_aggregate_field("SUM", "grand_total", "sum_grand_total"),
    "avg_grand_total": build_aggregate_field("AVG", "grand_total", "avg_grand_total"),
    "min_grand_total": build_aggregate_field("MIN", "grand_total", "min_grand_total"),
    "max_grand_total": build_aggregate_field("MAX", "grand_total", "max_grand_total"),
    "sum_net_total": build_aggregate_field("SUM", "net_total", "sum_net_total"),
    "sum_total_qty": build_aggregate_field("SUM", "total_qty", "sum_total_qty"),
}
_MONETARY_METRICS = frozenset(
    {
        "sum_grand_total",
        "avg_grand_total",
        "min_grand_total",
        "max_grand_total",
        "sum_net_total",
    }
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


def _range(
    filters: list[list[Any]], field: str, start: date | None, end: date | None
) -> None:
    if start and end:
        filters.append([field, "between", [_date(start), _date(end)]])
    elif start:
        filters.append([field, ">=", _date(start)])
    elif end:
        # DateTime fields need an exclusive next-day endpoint to include the full day.
        if field in {"creation", "modified"}:
            filters.append([field, "<", (end + timedelta(days=1)).isoformat()])
        else:
            filters.append([field, "<=", _date(end)])


def _filters(criteria: dict[str, Any]) -> list[list[Any]]:
    filters: list[list[Any]] = []
    for field in (
        "name",
        "quotation_to",
        "party_name",
        "customer_name",
        "order_type",
        "company",
        "docstatus",
        "status",
        "currency",
        "selling_price_list",
        "price_list_currency",
        "referral_sales_partner",
        "customer_group",
        "territory",
        "owner",
    ):
        if criteria.get(field) is not None:
            filters.append([field, "=", criteria[field]])
    _range(
        filters,
        "transaction_date",
        criteria.get("transaction_date_from"),
        criteria.get("transaction_date_to"),
    )
    _range(
        filters,
        "valid_till",
        criteria.get("valid_till_from"),
        criteria.get("valid_till_to"),
    )
    _range(
        filters, "creation", criteria.get("created_from"), criteria.get("created_to")
    )
    _range(
        filters, "modified", criteria.get("modified_from"), criteria.get("modified_to")
    )
    for field, minimum, maximum in (
        (
            "grand_total",
            criteria.get("min_grand_total"),
            criteria.get("max_grand_total"),
        ),
        ("net_total", criteria.get("min_net_total"), criteria.get("max_net_total")),
        ("total_qty", criteria.get("min_total_qty"), criteria.get("max_total_qty")),
    ):
        if minimum is not None:
            filters.append([field, ">=", minimum])
        if maximum is not None:
            filters.append([field, "<=", maximum])
    return filters


def _project(values: Any, requested: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        field: values.get(field)
        for field in requested
        if field in _FIELDS and values.get(field) is not None
    }


def _requested_fields(requested: list[str]) -> list[str]:
    if any(field not in _FIELDS for field in requested):
        raise ValueError("Quotation projection contains an unsupported field.")
    return requested


def _sort_expression(sort_by: str, sort_order: str) -> str:
    if sort_by not in _SORT_FIELDS or sort_order not in {"asc", "desc"}:
        raise ValueError("Quotation sort contains an unsupported field or order.")
    return f"{sort_by} {sort_order}, name {sort_order}"


def _aggregate_fields(
    metrics: list[str], group_by: str | None
) -> tuple[list[Any], list[str]]:
    if any(metric not in _METRICS for metric in metrics):
        raise ValueError("Quotation aggregate contains an unsupported metric.")
    if group_by is not None and group_by not in _GROUP_FIELDS:
        raise ValueError("Quotation aggregate contains an unsupported grouping field.")
    return build_aggregate_fields(metrics, _METRICS, group_by=group_by)


def get_quotation(quotation: str, fields: list[str]) -> dict[str, Any]:
    fields = _requested_fields(fields)
    try:
        doc = frappe.get_doc("Quotation", quotation)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "quotation": quotation}
    if not doc.has_permission("read"):
        return _error(
            "PERMISSION_DENIED", "The authenticated user cannot read that Quotation."
        )
    return {"status": "ok", "document": _project(doc, fields)}


def query_quotations(criteria: dict[str, Any]) -> dict[str, Any]:
    fields = _requested_fields(criteria["fields"])
    rows = frappe.get_list(
        "Quotation",
        filters=_filters(criteria),
        fields=fields,
        order_by=_sort_expression(criteria["sort_by"], criteria["sort_order"]),
        limit_start=criteria["offset"],
        limit_page_length=criteria["limit"],
        ignore_permissions=False,
    )
    return {
        "status": "ok",
        "quotations": [_project(row, fields) for row in rows],
        "count": len(rows),
        "limit": criteria["limit"],
        "offset": criteria["offset"],
    }


def aggregate_quotations(criteria: dict[str, Any]) -> dict[str, Any]:
    metrics = criteria["metrics"]
    group_by = criteria.get("group_by")
    fields, groups = _aggregate_fields(metrics, group_by)
    monetary = bool(_MONETARY_METRICS.intersection(metrics))
    if monetary and group_by != "currency":
        fields.insert(0, "currency")
        groups.insert(0, "currency")
    rows = execute_aggregate(
        frappe.get_list,
        "Quotation",
        filters=_filters(criteria),
        fields=fields,
        groups=groups,
    )
    results = shape_aggregate_rows(rows, metrics, group_by=group_by)
    if monetary:
        for result, row in zip(results, rows):
            result["currency"] = row.get("currency")
    return {
        "status": "ok",
        "metrics": metrics,
        "group_by": group_by,
        "results": results,
    }
