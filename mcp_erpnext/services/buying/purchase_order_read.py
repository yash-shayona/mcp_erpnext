"""Permission-aware, allowlisted Purchase Order query and analytics services."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe
from frappe.query_builder.functions import Count

from ...public_errors import defined_error
from ..common.aggregate import (
    build_aggregate_field,
    build_aggregate_fields,
    execute_aggregate,
    shape_aggregate_rows,
)

DEFAULT_ITEM_FIELDS = ("purchase_order", "item_code", "qty")
_HEADER_FIELDS = frozenset(
    {
        "name",
        "transaction_date",
        "schedule_date",
        "supplier",
        "supplier_name",
        "company",
        "status",
        "currency",
        "grand_total",
        "rounded_total",
        "total_qty",
        "per_received",
        "per_billed",
        "buying_price_list",
        "owner",
        "creation",
        "modified",
    }
)
_ITEM_FIELDS = frozenset(
    {
        "purchase_order",
        "transaction_date",
        "supplier",
        "supplier_name",
        "company",
        "currency",
        "purchase_order_status",
        "item_code",
        "item_name",
        "qty",
        "rate",
        "amount",
        "received_qty",
        "billed_amt",
        "schedule_date",
        "warehouse",
    }
)
_HEADER_METRICS = {
    "count": build_aggregate_field("COUNT", "*", "count"),
    "sum_grand_total": build_aggregate_field("SUM", "grand_total", "sum_grand_total"),
    "avg_grand_total": build_aggregate_field("AVG", "grand_total", "avg_grand_total"),
    "min_grand_total": build_aggregate_field("MIN", "grand_total", "min_grand_total"),
    "max_grand_total": build_aggregate_field("MAX", "grand_total", "max_grand_total"),
    "sum_total_qty": build_aggregate_field("SUM", "total_qty", "sum_total_qty"),
}
_ITEM_METRICS = {
    "count_rows": build_aggregate_field(
        "COUNT", "`tabPurchase Order Item`.name", "count_rows"
    ),
    "sum_qty": build_aggregate_field("SUM", "`tabPurchase Order Item`.qty", "sum_qty"),
    "sum_amount": build_aggregate_field(
        "SUM", "`tabPurchase Order Item`.amount", "sum_amount"
    ),
    "min_rate": build_aggregate_field(
        "MIN", "`tabPurchase Order Item`.rate", "min_rate"
    ),
    "max_rate": build_aggregate_field(
        "MAX", "`tabPurchase Order Item`.rate", "max_rate"
    ),
    "avg_rate": build_aggregate_field(
        "AVG", "`tabPurchase Order Item`.rate", "avg_rate"
    ),
}


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _range(
    filters: list[list[Any]], field: str, start: date | None, end: date | None
) -> None:
    if start and end:
        filters.append([field, "between", [start.isoformat(), end.isoformat()]])
    elif start:
        filters.append([field, ">=", start.isoformat()])
    elif end:
        filters.append(
            [
                field,
                "<" if field == "creation" else "<=",
                (
                    (end + timedelta(days=1)).isoformat()
                    if field == "creation"
                    else end.isoformat()
                ),
            ]
        )


def _header_filters(
    criteria: dict[str, Any], *, allow_child_filters: bool
) -> list[list[Any]]:
    filters: list[list[Any]] = []
    _range(
        filters,
        "transaction_date",
        criteria.get("transaction_date_from"),
        criteria.get("transaction_date_to"),
    )
    _range(
        filters,
        "schedule_date",
        criteria.get("schedule_date_from"),
        criteria.get("schedule_date_to"),
    )
    _range(
        filters, "creation", criteria.get("created_from"), criteria.get("created_to")
    )
    for field in (
        "supplier",
        "company",
        "status",
        "docstatus",
        "owner",
        "currency",
        "buying_price_list",
    ):
        if criteria.get(field) is not None:
            filters.append([field, "=", criteria[field]])
    if criteria.get("min_grand_total") is not None:
        filters.append(["grand_total", ">=", criteria["min_grand_total"]])
    if criteria.get("max_grand_total") is not None:
        filters.append(["grand_total", "<=", criteria["max_grand_total"]])
    if allow_child_filters and criteria.get("item_code"):
        filters.append(["Purchase Order Item", "item_code", "=", criteria["item_code"]])
    return filters


def _project(
    values: Any, requested: list[str], allowed: frozenset[str]
) -> dict[str, Any]:
    return {
        field: values.get(field)
        for field in requested
        if field in allowed and values.get(field) is not None
    }


def get_purchase_order(
    purchase_order: str, fields: list[str], include_items: bool, item_fields: list[str]
) -> dict[str, Any]:
    try:
        doc = frappe.get_doc("Purchase Order", purchase_order)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "purchase_order": purchase_order}
    if not doc.has_permission("read"):
        return _error(
            "PERMISSION_DENIED",
        )
    result: dict[str, Any] = {
        "status": "ok",
        "document": _project(doc, fields, _HEADER_FIELDS),
    }
    if include_items:
        result["items"] = [
            _project(row, item_fields, _ITEM_FIELDS) for row in (doc.get("items") or [])
        ]
    return result


def query_purchase_orders(criteria: dict[str, Any]) -> dict[str, Any]:
    fields = criteria["fields"]
    rows = frappe.get_list(
        "Purchase Order",
        filters=_header_filters(criteria, allow_child_filters=True),
        fields=fields,
        order_by=f"{criteria['sort_by']} {criteria['sort_order']}, name {criteria['sort_order']}",
        limit_start=criteria["offset"],
        limit_page_length=criteria["limit"],
        distinct=bool(criteria.get("item_code")),
        ignore_permissions=False,
    )
    return {
        "status": "ok",
        "purchase_orders": [_project(row, fields, _HEADER_FIELDS) for row in rows],
        "count": len(rows),
        "limit": criteria["limit"],
        "offset": criteria["offset"],
    }


def aggregate_purchase_orders(criteria: dict[str, Any]) -> dict[str, Any]:
    metrics, group_by = criteria["metrics"], criteria.get("group_by")
    fields, groups = build_aggregate_fields(metrics, _HEADER_METRICS, group_by=group_by)
    monetary = any(metric.endswith("grand_total") for metric in metrics)
    if monetary:
        fields.insert(0, "currency")
        groups.insert(0, "currency")
    rows = execute_aggregate(
        frappe.get_list,
        "Purchase Order",
        filters=_header_filters(criteria, allow_child_filters=False),
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


def _item_filters(criteria: dict[str, Any]) -> list[list[Any]]:
    filters: list[list[Any]] = []
    _range(
        filters,
        "transaction_date",
        criteria.get("transaction_date_from"),
        criteria.get("transaction_date_to"),
    )
    if criteria.get("supplier"):
        filters.append(["supplier", "=", criteria["supplier"]])
    if criteria.get("purchase_order"):
        filters.append(["name", "=", criteria["purchase_order"]])
    if criteria.get("purchase_order_status"):
        filters.append(["status", "=", criteria["purchase_order_status"]])
    if criteria.get("item_code"):
        filters.append(["Purchase Order Item", "item_code", "=", criteria["item_code"]])
    if criteria.get("min_qty") is not None:
        filters.append(["Purchase Order Item", "qty", ">=", criteria["min_qty"]])
    if criteria.get("max_qty") is not None:
        filters.append(["Purchase Order Item", "qty", "<=", criteria["max_qty"]])
    return filters


def _item_query_fields(fields: list[str]) -> list[str]:
    parent = {
        "purchase_order": "name as purchase_order",
        "purchase_order_status": "status as purchase_order_status",
    }
    child = {
        "item_code",
        "item_name",
        "qty",
        "rate",
        "amount",
        "received_qty",
        "billed_amt",
        "schedule_date",
        "warehouse",
    }
    return [
        parent.get(field, f"items.{field}" if field in child else field)
        for field in fields
    ]


def _item_sort(criteria: dict[str, Any]) -> str:
    field = criteria["sort_by"]
    if field in {"qty", "rate", "amount", "schedule_date"}:
        field = f"items.{field}"
    elif field == "purchase_order":
        field = "name"
    return f"{field} {criteria['sort_order']}, name {criteria['sort_order']}"


def _aggregate_items(criteria: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = criteria["metrics"]
    if not metrics:
        return []
    group_by = criteria.get("group_by")
    metric_fields = {
        metric: (
            Count(frappe.qb.DocType("Purchase Order").name)
            .distinct()
            .as_("count_distinct_orders")
            if metric == "count_distinct_orders"
            else _ITEM_METRICS[metric]
        )
        for metric in metrics
    }
    mapped_group = (
        "`tabPurchase Order Item`.item_code" if group_by == "item_code" else group_by
    )
    fields, groups = build_aggregate_fields(
        metrics,
        metric_fields,
        group_by=group_by,
        group_field=mapped_group,
        group_alias="group_value",
    )
    monetary = any(
        metric in {"sum_amount", "min_rate", "max_rate", "avg_rate"}
        for metric in metrics
    )
    if monetary:
        fields.insert(0, "currency")
        groups.insert(0, "currency")
    rows = execute_aggregate(
        frappe.get_list,
        "Purchase Order",
        filters=_item_filters(criteria),
        fields=fields,
        groups=groups,
    )
    return [
        {
            field: row.get(field)
            for field in ("group_value", "currency", *metrics)
            if row.get(field) is not None
        }
        for row in rows
    ]


def query_purchase_order_items(criteria: dict[str, Any]) -> dict[str, Any]:
    requested = criteria.get("fields")
    fields = (
        requested
        if requested is not None
        else ([] if criteria["metrics"] else list(DEFAULT_ITEM_FIELDS))
    )
    items: list[dict[str, Any]] = []
    if fields:
        rows = frappe.qb.get_query(
            "Purchase Order",
            fields=_item_query_fields(fields),
            filters=_item_filters(criteria),
            order_by=_item_sort(criteria),
            limit=criteria["limit"],
            offset=criteria["offset"],
            ignore_permissions=False,
        ).run(as_dict=True)
        items = [_project(row, fields, _ITEM_FIELDS) for row in rows]
    return {
        "status": "ok",
        "items": items,
        "count": len(items),
        "limit": criteria["limit"],
        "offset": criteria["offset"],
        "metrics": criteria["metrics"],
        "group_by": criteria.get("group_by"),
        "aggregates": _aggregate_items(criteria),
    }
