"""Permission-aware bounded Purchase Receipt reads."""

from __future__ import annotations

from typing import Any
from datetime import date, timedelta

from frappe.query_builder.functions import Count

from ..common.aggregate import build_aggregate_field, build_aggregate_fields, execute_aggregate, shape_aggregate_rows

import frappe

from ...public_errors import defined_error

_HEADER_FIELDS = {"name", "supplier", "supplier_name", "company", "posting_date", "posting_time", "docstatus", "status", "currency", "total_qty", "grand_total", "per_billed", "is_return", "return_against", "supplier_delivery_note", "owner", "creation", "modified"}
_ITEM_FIELDS = {"name", "item_code", "item_name", "purchase_order", "purchase_order_item", "qty", "rejected_qty", "received_qty", "uom", "stock_uom", "conversion_factor", "warehouse", "rejected_warehouse", "rate", "amount", "quality_inspection"}


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _project(value: Any, fields: list[str]) -> dict[str, Any]:
    return {field: value.get(field) for field in fields if value.get(field) is not None}


def get_purchase_receipt(purchase_receipt: str, fields: list[str], include_items: bool = False, item_fields: list[str] | None = None) -> dict[str, Any]:
    if any(field not in _HEADER_FIELDS for field in fields):
        return _error("INVALID_FIELDS")
    if item_fields and any(field not in _ITEM_FIELDS for field in item_fields):
        return _error("INVALID_FIELDS")
    try:
        doc = frappe.get_doc("Purchase Receipt", purchase_receipt)
    except frappe.DoesNotExistError:
        return {"status": "not_found", "purchase_receipt": purchase_receipt}
    except frappe.PermissionError:
        return _error("PERMISSION_DENIED")
    if not doc.has_permission("read"):
        return _error("PERMISSION_DENIED")
    document = _project(doc, fields)
    if include_items:
        document["items"] = [_project(row, item_fields or ["name", "item_code", "purchase_order", "purchase_order_item", "qty", "rejected_qty"]) for row in doc.get("items") or []]
    return {"status": "ok", "document": document}


# The following structured reads keep their allowlists independent of exact read.
_QUERY_FIELDS = frozenset({"name", "supplier", "supplier_name", "posting_date", "posting_time", "docstatus", "status", "company", "currency", "conversion_rate", "buying_price_list", "price_list_currency", "total_qty", "grand_total", "per_billed", "per_returned", "is_return", "return_against", "supplier_delivery_note", "owner", "creation", "modified"})
_HISTORY_FIELDS = frozenset({"name", "purchase_receipt", "posting_date", "supplier", "supplier_name", "company", "currency", "purchase_receipt_status", "docstatus", "is_return", "return_against", "item_code", "item_name", "purchase_order", "purchase_order_item", "qty", "rejected_qty", "received_qty", "stock_qty", "uom", "stock_uom", "conversion_factor", "rate", "amount", "net_rate", "net_amount", "billed_amt", "warehouse", "rejected_warehouse", "schedule_date", "quality_inspection", "is_fixed_asset"})
_CHILD_FIELDS = _HISTORY_FIELDS - {"purchase_receipt", "posting_date", "supplier", "supplier_name", "company", "currency", "purchase_receipt_status", "docstatus", "is_return", "return_against"}
_HEADER_METRICS = {
    "count": build_aggregate_field("COUNT", "*", "count"),
    **{f"{op.lower()}_grand_total": build_aggregate_field(op, "grand_total", f"{op.lower()}_grand_total") for op in ("SUM", "AVG", "MIN", "MAX")},
    "sum_total_qty": build_aggregate_field("SUM", "total_qty", "sum_total_qty"),
}
_ITEM_METRICS = {
    "count_rows": build_aggregate_field("COUNT", "`tabPurchase Receipt Item`.name", "count_rows"),
    **{f"sum_{field}": build_aggregate_field("SUM", f"`tabPurchase Receipt Item`.{field}", f"sum_{field}") for field in ("qty", "received_qty", "rejected_qty", "amount")},
    **{f"{op.lower()}_rate": build_aggregate_field(op, "`tabPurchase Receipt Item`.rate", f"{op.lower()}_rate") for op in ("MIN", "MAX", "AVG")},
}


def _range(filters: list[list[Any]], field: str, start: date | None, end: date | None) -> None:
    if start:
        filters.append([field, ">=", start.isoformat()])
    if end:
        if field in {"creation", "modified"}:
            filters.append([field, "<", (end + timedelta(days=1)).isoformat()])
        else:
            filters.append([field, "<=", end.isoformat()])


def _structured_header_filters(criteria: dict[str, Any], *, child: bool) -> list[list[Any]]:
    filters: list[list[Any]] = []
    for field, prefix in (("posting_date", "posting_date"), ("creation", "created"), ("modified", "modified")):
        _range(filters, field, criteria.get(f"{prefix}_from"), criteria.get(f"{prefix}_to"))
    for field in ("name", "supplier", "company", "docstatus", "status", "currency", "owner", "is_return", "return_against"):
        if criteria.get(field) is not None:
            filters.append([field, "=", criteria[field]])
    for bound, op in (("min_grand_total", ">="), ("max_grand_total", "<=")):
        if criteria.get(bound) is not None:
            filters.append(["grand_total", op, criteria[bound]])
    if child:
        for field in ("item_code", "purchase_order"):
            if criteria.get(field):
                filters.append(["Purchase Receipt Item", field, "=", criteria[field]])
    return filters


def query_purchase_receipts(criteria: dict[str, Any]) -> dict[str, Any]:
    fields = criteria["fields"]
    rows = frappe.get_list(
        "Purchase Receipt", filters=_structured_header_filters(criteria, child=True), fields=fields,
        order_by=f"{criteria['sort_by']} {criteria['sort_order']}, name {criteria['sort_order']}",
        limit_start=criteria["offset"], limit_page_length=criteria["limit"],
        distinct=bool(criteria.get("item_code") or criteria.get("purchase_order")), ignore_permissions=False,
    )
    return {"status": "ok", "purchase_receipts": [{field: row.get(field) for field in fields if field in _QUERY_FIELDS and row.get(field) is not None} for row in rows], "count": len(rows), "limit": criteria["limit"], "offset": criteria["offset"]}


def aggregate_purchase_receipts(criteria: dict[str, Any]) -> dict[str, Any]:
    metrics, group_by = criteria["metrics"], criteria.get("group_by")
    fields, groups = build_aggregate_fields(metrics, _HEADER_METRICS, group_by=group_by)
    monetary = any(metric.endswith("grand_total") for metric in metrics)
    if monetary and group_by != "currency":
        fields.insert(0, "currency")
        groups.insert(0, "currency")
    rows = execute_aggregate(frappe.get_list, "Purchase Receipt", filters=_structured_header_filters(criteria, child=False), fields=fields, groups=groups)
    results = shape_aggregate_rows(rows, metrics, group_by=group_by)
    if monetary:
        for result, row in zip(results, rows):
            result["currency"] = row.get("currency")
    return {"status": "ok", "metrics": metrics, "group_by": group_by, "results": results}


def _item_filters(criteria: dict[str, Any]) -> list[list[Any]]:
    filters: list[list[Any]] = []
    _range(filters, "posting_date", criteria.get("posting_date_from"), criteria.get("posting_date_to"))
    for field in ("purchase_receipt", "supplier", "company", "purchase_receipt_status", "docstatus", "is_return"):
        value = criteria.get(field)
        if value is not None:
            parent_field = {"purchase_receipt": "name", "purchase_receipt_status": "status"}.get(field, field)
            filters.append([parent_field, "=", value])
    for field in ("purchase_order", "item_code", "warehouse", "rejected_warehouse"):
        if criteria.get(field):
            filters.append(["Purchase Receipt Item", field, "=", criteria[field]])
    for field in ("qty", "received_qty", "rejected_qty"):
        for bound, operator in (("min", ">="), ("max", "<=")):
            value = criteria.get(f"{bound}_{field}")
            if value is not None:
                filters.append(["Purchase Receipt Item", field, operator, value])
    return filters


def _item_query_fields(fields: list[str]) -> list[str]:
    aliases = {"name": "items.name as name", "purchase_receipt": "name as purchase_receipt", "purchase_receipt_status": "status as purchase_receipt_status"}
    return [aliases.get(field, f"items.{field}" if field in _CHILD_FIELDS else field) for field in fields]


def _item_sort(criteria: dict[str, Any]) -> str:
    field = criteria["sort_by"]
    if field in {"qty", "received_qty", "rejected_qty", "rate", "amount"}:
        field = f"items.{field}"
    elif field == "purchase_receipt":
        field = "name"
    order = criteria["sort_order"]
    return f"{field} {order}, name {order}, items.name {order}"


def _aggregate_items(criteria: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = criteria["metrics"]
    if not metrics:
        return []
    group_by = criteria.get("group_by")
    metric_fields = {metric: Count(frappe.qb.DocType("Purchase Receipt").name).distinct().as_("count_distinct_receipts") if metric == "count_distinct_receipts" else _ITEM_METRICS[metric] for metric in metrics}
    mapped_group = f"`tabPurchase Receipt Item`.{group_by}" if group_by in {"item_code", "warehouse", "purchase_order"} else group_by
    fields, groups = build_aggregate_fields(metrics, metric_fields, group_by=group_by, group_field=mapped_group, group_alias="group_value")
    monetary = any(metric in {"sum_amount", "min_rate", "max_rate", "avg_rate"} for metric in metrics)
    if monetary:
        fields.insert(0, "currency")
        groups.insert(0, "currency")
    rows = execute_aggregate(frappe.get_list, "Purchase Receipt", filters=_item_filters(criteria), fields=fields, groups=groups)
    return [{field: row.get(field) for field in ("group_value", "currency", *metrics) if row.get(field) is not None} for row in rows]


def query_purchase_receipt_items(criteria: dict[str, Any]) -> dict[str, Any]:
    requested = criteria.get("fields")
    fields = requested if requested is not None else ([] if criteria["metrics"] else ["name", "purchase_receipt", "item_code", "purchase_order", "purchase_order_item", "qty", "rejected_qty", "received_qty"])
    items: list[dict[str, Any]] = []
    if fields:
        rows = frappe.qb.get_query("Purchase Receipt", fields=_item_query_fields(fields), filters=_item_filters(criteria), order_by=_item_sort(criteria), limit=criteria["limit"], offset=criteria["offset"], ignore_permissions=False).run(as_dict=True)
        items = [{field: row.get(field) for field in fields if field in _HISTORY_FIELDS and row.get(field) is not None} for row in rows]
    return {"status": "ok", "items": items, "count": len(items), "limit": criteria["limit"], "offset": criteria["offset"], "metrics": criteria["metrics"], "group_by": criteria.get("group_by"), "aggregates": _aggregate_items(criteria)}
