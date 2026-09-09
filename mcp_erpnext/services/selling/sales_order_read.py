"""Permission-aware, allowlisted Sales Order query and analytics services."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe

from ...observability import new_error_reference


DEFAULT_ITEM_FIELDS = ("sales_order", "item_code", "qty")

_HEADER_FIELDS = frozenset({
	"name", "transaction_date", "customer", "customer_name", "status", "delivery_status", "billing_status",
	"delivery_date", "currency", "grand_total", "total_qty", "per_delivered", "per_billed", "customer_group",
	"territory", "owner", "creation", "modified",
})
_ITEM_FIELDS = frozenset({
	"sales_order", "transaction_date", "customer", "customer_name", "currency", "sales_order_status", "item_code",
	"item_name", "qty", "rate", "amount", "discount_percentage", "discount_amount", "delivered_qty", "delivery_date",
})
_HEADER_METRICS = {
	"count": "count(name) as count",
	"sum_grand_total": "sum(grand_total) as sum_grand_total",
	"avg_grand_total": "avg(grand_total) as avg_grand_total",
	"min_grand_total": "min(grand_total) as min_grand_total",
	"max_grand_total": "max(grand_total) as max_grand_total",
	"sum_total_qty": "sum(total_qty) as sum_total_qty",
}
_ITEM_METRICS = {
	"count_rows": "count(`tabSales Order Item`.name) as count_rows",
	"count_distinct_orders": "count(distinct `tabSales Order`.name) as count_distinct_orders",
	"sum_qty": "sum(`tabSales Order Item`.qty) as sum_qty",
	"sum_amount": "sum(`tabSales Order Item`.amount) as sum_amount",
	"min_rate": "min(`tabSales Order Item`.rate) as min_rate",
	"max_rate": "max(`tabSales Order Item`.rate) as max_rate",
	"avg_rate": "avg(`tabSales Order Item`.rate) as avg_rate",
}


def _error(code: str, message: str) -> dict[str, Any]:
	return {"status": "error", "code": code, "message": message, "reference": new_error_reference(), "retryable": False}


def _date(value: date | None) -> str | None:
	return value.isoformat() if value else None


def _range(filters: list[list[Any]], field: str, start: date | None, end: date | None) -> None:
	if start and end:
		filters.append([field, "between", [_date(start), _date(end)]])
	elif start:
		filters.append([field, ">=", _date(start)])
	elif end:
		# Frappe expands a DateTime ``between`` endpoint to the end of day, but
		# a bare ``creation <= YYYY-MM-DD`` would otherwise stop at midnight.
		if field == "creation":
			filters.append([field, "<", (end + timedelta(days=1)).isoformat()])
		else:
			filters.append([field, "<=", _date(end)])


def _header_filters(criteria: dict[str, Any], *, allow_child_filters: bool) -> list[list[Any]]:
	filters: list[list[Any]] = []
	_range(filters, "transaction_date", criteria.get("transaction_date_from"), criteria.get("transaction_date_to"))
	_range(filters, "creation", criteria.get("created_from"), criteria.get("created_to"))
	_range(filters, "delivery_date", criteria.get("delivery_date_from"), criteria.get("delivery_date_to"))
	for field in ("customer", "customer_group", "territory", "status", "delivery_status", "billing_status", "docstatus", "owner", "currency"):
		if criteria.get(field) is not None:
			filters.append([field, "=", criteria[field]])
	if criteria.get("min_grand_total") is not None:
		filters.append(["grand_total", ">=", criteria["min_grand_total"]])
	if criteria.get("max_grand_total") is not None:
		filters.append(["grand_total", "<=", criteria["max_grand_total"]])
	if allow_child_filters and criteria.get("item_code"):
		filters.append(["Sales Order Item", "item_code", "=", criteria["item_code"]])
	if allow_child_filters and criteria.get("sales_person"):
		filters.append(["Sales Team", "sales_person", "=", criteria["sales_person"]])
	return filters


def _project(values: dict[str, Any], requested: list[str] | tuple[str, ...], allowed: frozenset[str]) -> dict[str, Any]:
	return {field: values.get(field) for field in requested if field in allowed and values.get(field) is not None}


def get_sales_order(sales_order: str, fields: list[str], include_items: bool, item_fields: list[str]) -> dict[str, Any]:
	try:
		doc = frappe.get_doc("Sales Order", sales_order)
	except frappe.DoesNotExistError:
		return {"status": "not_found", "sales_order": sales_order}
	if not doc.has_permission("read"):
		return _error("PERMISSION_DENIED", "The authenticated user cannot read that Sales Order.")
	result: dict[str, Any] = {"status": "ok", "document": _project(doc, fields, _HEADER_FIELDS)}
	if include_items:
		result["items"] = [_project(row, item_fields, _ITEM_FIELDS) for row in (doc.get("items") or [])]
	return result


def search_sales_orders(criteria: dict[str, Any]) -> dict[str, Any]:
	fields = criteria["fields"]
	rows = frappe.get_list(
		"Sales Order",
		filters=_header_filters(criteria, allow_child_filters=True),
		fields=fields,
		order_by=f"{criteria['sort_by']} {criteria['sort_order']}, name {criteria['sort_order']}",
		limit_start=criteria["offset"],
		limit_page_length=criteria["limit"],
		distinct=bool(criteria.get("item_code") or criteria.get("sales_person")),
		ignore_permissions=False,
	)
	return {
		"status": "ok", "sales_orders": [_project(row, fields, _HEADER_FIELDS) for row in rows],
		"count": len(rows), "limit": criteria["limit"], "offset": criteria["offset"],
	}


def aggregate_sales_orders(criteria: dict[str, Any]) -> dict[str, Any]:
	metrics = criteria["metrics"]
	group_by = criteria.get("group_by")
	monetary = any(metric.endswith("grand_total") for metric in metrics)
	fields = [_HEADER_METRICS[metric] for metric in metrics]
	groups: list[str] = []
	if group_by:
		fields.insert(0, group_by)
		groups.append(group_by)
	if monetary:
		fields.insert(0, "currency")
		groups.insert(0, "currency")
	rows = frappe.get_list(
		"Sales Order",
		filters=_header_filters(criteria, allow_child_filters=False),
		fields=fields,
		group_by=", ".join(groups) or None,
		order_by=", ".join(groups) or None,
		ignore_permissions=False,
	)
	results = []
	for row in rows:
		result = {metric: row.get(metric) for metric in metrics if row.get(metric) is not None}
		if group_by:
			result["group_value"] = row.get(group_by)
		if monetary:
			result["currency"] = row.get("currency")
		results.append(result)
	return {"status": "ok", "metrics": metrics, "group_by": group_by, "results": results}


def _item_filters(criteria: dict[str, Any]) -> list[list[Any]]:
	filters: list[list[Any]] = []
	_range(filters, "transaction_date", criteria.get("transaction_date_from"), criteria.get("transaction_date_to"))
	for field in ("customer",):
		if criteria.get(field):
			filters.append([field, "=", criteria[field]])
	if criteria.get("sales_order"):
		filters.append(["name", "=", criteria["sales_order"]])
	if criteria.get("sales_order_status"):
		filters.append(["status", "=", criteria["sales_order_status"]])
	if criteria.get("item_code"):
		filters.append(["Sales Order Item", "item_code", "=", criteria["item_code"]])
	if criteria.get("min_qty") is not None:
		filters.append(["Sales Order Item", "qty", ">=", criteria["min_qty"]])
	if criteria.get("max_qty") is not None:
		filters.append(["Sales Order Item", "qty", "<=", criteria["max_qty"]])
	return filters


def _item_query_fields(fields: list[str]) -> list[str]:
	return [
		{"sales_order": "name as sales_order", "sales_order_status": "status as sales_order_status"}.get(field, f"items.{field}" if field in {"item_code", "item_name", "qty", "rate", "amount", "discount_percentage", "discount_amount", "delivered_qty", "delivery_date"} else field)
		for field in fields
	]


def _item_sort(criteria: dict[str, Any]) -> str:
	field = criteria["sort_by"]
	if field in {"qty", "rate", "amount", "delivery_date"}:
		field = f"items.{field}"
	elif field == "sales_order":
		field = "name"
	return f"{field} {criteria['sort_order']}, name {criteria['sort_order']}"


def _aggregate_sales_order_items(criteria: dict[str, Any]) -> list[dict[str, Any]]:
	metrics = criteria["metrics"]
	if not metrics:
		return []
	group_by = criteria.get("group_by")
	monetary = any(metric in {"sum_amount", "min_rate", "max_rate", "avg_rate"} for metric in metrics)
	fields = [_ITEM_METRICS[metric] for metric in metrics]
	groups: list[str] = []
	if group_by:
		mapped_group = "`tabSales Order Item`.item_code" if group_by == "item_code" else group_by
		fields.insert(0, f"{mapped_group} as group_value")
		groups.append(mapped_group)
	if monetary:
		fields.insert(0, "currency")
		groups.insert(0, "currency")
	rows = frappe.get_list(
		"Sales Order", filters=_item_filters(criteria), fields=fields,
		group_by=", ".join(groups) or None, order_by=", ".join(groups) or None,
		ignore_permissions=False,
	)
	return [{field: row.get(field) for field in ("group_value", "currency", *metrics) if row.get(field) is not None} for row in rows]


def query_sales_order_items(criteria: dict[str, Any]) -> dict[str, Any]:
	requested = criteria.get("fields")
	# A metrics-only request does not fetch source rows. Otherwise expose only the compact default or requested projection.
	fields = requested if requested is not None else ([] if criteria["metrics"] else list(DEFAULT_ITEM_FIELDS))
	items: list[dict[str, Any]] = []
	if fields:
		query = frappe.qb.get_query(
			"Sales Order", fields=_item_query_fields(fields), filters=_item_filters(criteria),
			order_by=_item_sort(criteria), limit=criteria["limit"], offset=criteria["offset"],
			ignore_permissions=False,
		)
		rows = query.run(as_dict=True)
		items = [_project(row, fields, _ITEM_FIELDS) for row in rows]
	return {
		"status": "ok", "items": items, "count": len(items), "limit": criteria["limit"], "offset": criteria["offset"],
		"metrics": criteria["metrics"], "group_by": criteria.get("group_by"), "aggregates": _aggregate_sales_order_items(criteria),
	}
