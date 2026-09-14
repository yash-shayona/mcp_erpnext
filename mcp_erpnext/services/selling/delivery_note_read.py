"""Permission-aware, allowlisted Delivery Note read/query/aggregate services."""

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
    "name customer customer_name posting_date posting_time docstatus status company currency conversion_rate selling_price_list price_list_currency total_qty base_total base_net_total total net_total base_grand_total grand_total total_taxes_and_charges base_total_taxes_and_charges is_return return_against per_billed per_installed owner creation modified".split()
)
_SORT = frozenset(
    "name customer customer_name posting_date status company currency grand_total total_qty creation modified".split()
)
_GROUP = frozenset(
    "customer customer_name status company currency is_return posting_date docstatus".split()
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


def _error(code, message):
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": False,
    }


def _fields(fields):
    if any(f not in _FIELDS for f in fields):
        raise ValueError("Delivery Note projection contains an unsupported field.")
    return fields


def _filters(c):
    result = []
    for f in (
        "name",
        "customer",
        "customer_name",
        "company",
        "docstatus",
        "status",
        "currency",
        "selling_price_list",
        "price_list_currency",
        "return_against",
        "owner",
    ):
        if c.get(f) is not None:
            result.append([f, "=", c[f]])
    if c.get("is_return") is not None:
        result.append(["is_return", "=", int(c["is_return"])])
    for f, start, end in (
        ("posting_date", c.get("posting_date_from"), c.get("posting_date_to")),
        ("creation", c.get("created_from"), c.get("created_to")),
        ("modified", c.get("modified_from"), c.get("modified_to")),
    ):
        if start and end:
            result.append([f, "between", [start.isoformat(), end.isoformat()]])
        elif start:
            result.append([f, ">=", start.isoformat()])
        elif end:
            result.append(
                [
                    f,
                    "<",
                    (
                        (end + timedelta(days=1)).isoformat()
                        if f != "posting_date"
                        else end.isoformat()
                    ),
                ]
            )
    for f, lo, hi in (
        ("grand_total", c.get("min_grand_total"), c.get("max_grand_total")),
        ("net_total", c.get("min_net_total"), c.get("max_net_total")),
    ):
        if lo is not None:
            result.append([f, ">=", lo])
        if hi is not None:
            result.append([f, "<=", hi])
    return result


def _project(v, fields):
    return {f: v.get(f) for f in fields if v.get(f) is not None}


def get_delivery_note(delivery_note, fields):
    fields = _fields(fields)
    try:
        doc = frappe.get_doc("Delivery Note", delivery_note)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "delivery_note": delivery_note}
    if not doc.has_permission("read"):
        return _error(
            "PERMISSION_DENIED",
            "The authenticated user cannot read that Delivery Note.",
        )
    return {"status": "ok", "document": _project(doc, fields)}


def query_delivery_notes(c):
    fields = _fields(c["fields"])
    sort = c["sort_by"]
    if sort not in _SORT or c["sort_order"] not in {"asc", "desc"}:
        raise ValueError("Delivery Note sort contains an unsupported field or order.")
    rows = frappe.get_list(
        "Delivery Note",
        filters=_filters(c),
        fields=fields,
        order_by=f"{sort} {c['sort_order']}, name {c['sort_order']}",
        limit_start=c["offset"],
        limit_page_length=c["limit"],
        ignore_permissions=False,
    )
    return {
        "status": "ok",
        "delivery_notes": [_project(r, fields) for r in rows],
        "count": len(rows),
        "limit": c["limit"],
        "offset": c["offset"],
    }


def aggregate_delivery_notes(c):
    metrics = c["metrics"]
    group = c.get("group_by")
    if any(m not in _METRICS for m in metrics):
        raise ValueError("Delivery Note aggregate contains an unsupported metric.")
    if group and group not in _GROUP:
        raise ValueError(
            "Delivery Note aggregate contains an unsupported grouping field."
        )
    fields, groups = build_aggregate_fields(metrics, _METRICS, group_by=group)
    rows = execute_aggregate(
        frappe.get_list,
        "Delivery Note",
        filters=_filters(c),
        fields=fields,
        groups=groups,
    )
    return {
        "status": "ok",
        "metrics": metrics,
        "group_by": group,
        "results": shape_aggregate_rows(rows, metrics, group_by=group),
    }
