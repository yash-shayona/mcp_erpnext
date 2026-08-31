"""Safe, two-phase Sales Order service for the controlled MCP capability."""

from __future__ import annotations

import math
from typing import Any

import frappe
from frappe.utils import getdate, nowdate

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...observability import new_error_reference, public_error
from ..masters.customer import resolve_customer
from ..masters.item import resolve_sales_item


_ACTION = "create_sales_order"


def _current_user() -> str:
	user = getattr(frappe.session, "user", None)
	if not user or user in {"Guest", "guest"}:
		frappe.throw("An authenticated Frappe user is required for Sales Order creation.", frappe.PermissionError)
	return user


def _resolve_company(company: str | None) -> str | None:
	"""Use only an explicit or permission-visible default Company."""
	resolved = company or frappe.defaults.get_user_default("Company")
	if not resolved:
		return None
	if not frappe.get_list(
		"Company",
		filters={"name": resolved},
		fields=["name"],
		limit_page_length=1,
		ignore_permissions=False,
	):
		frappe.throw(f"Company {resolved} was not found or is not permitted.", frappe.PermissionError)
	return resolved


def _coerce_quantity(value: Any) -> float | None:
	if value in (None, ""):
		return None
	if isinstance(value, bool):
		frappe.throw("Item quantity must be a positive number.", frappe.ValidationError)
	try:
		quantity = float(value)
	except (TypeError, ValueError) as exc:
		raise frappe.ValidationError("Item quantity must be a positive number.") from exc
	if not math.isfinite(quantity) or quantity <= 0:
		frappe.throw("Item quantity must be a positive number.", frappe.ValidationError)
	return quantity


def _prepare_items(items: Any) -> dict[str, Any]:
	if not isinstance(items, list) or not items:
		return {"status": "needs_input", "missing": ["items"], "items": []}

	resolved_items: list[dict[str, Any]] = []
	missing_quantities: list[dict[str, Any]] = []
	for index, raw_item in enumerate(items, start=1):
		if not isinstance(raw_item, dict):
			return public_error("INVALID_ORDER_DETAILS", message=f"Item row {index} must be a valid item entry.")
		query = raw_item.get("item") or raw_item.get("item_code") or raw_item.get("item_name")
		if not query:
			return {"status": "needs_input", "missing": [f"items[{index}].item"], "items": []}

		resolution = resolve_sales_item(str(query))
		if resolution["status"] != "resolved":
			return {
				"status": resolution["status"],
				"field": f"items[{index}].item",
				"query": query,
				"candidates": resolution.get("candidates", []),
			}
		quantity = _coerce_quantity(raw_item.get("qty", raw_item.get("quantity")))
		if quantity is None:
			missing_quantities.append(
				{
					"index": index,
					"item_code": resolution["candidate"]["value"],
					"item_name": resolution["candidate"].get("item_name"),
				}
			)
		resolved_items.append(
			{
				"item_code": resolution["candidate"]["value"],
				"item_name": resolution["candidate"].get("item_name"),
				"qty": quantity,
				"match_type": resolution.get("match_type"),
			}
		)

	if missing_quantities:
		return {"status": "needs_input", "missing_quantities": missing_quantities, "items": resolved_items}
	return {"status": "resolved", "items": resolved_items}


def _safe_doc_data(doc: Any) -> dict[str, Any]:
	"""Keep only JSON-safe data required to create the reviewed Draft later."""
	data = doc.as_dict()
	for field in ("__islocal", "owner", "creation", "modified", "modified_by"):
		data.pop(field, None)
	return data


def _preview(doc: Any) -> dict[str, Any]:
	return {
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"company": doc.company,
		"order_type": doc.order_type,
		"transaction_date": str(doc.transaction_date),
		"delivery_date": str(doc.delivery_date),
		"currency": doc.currency,
		"selling_price_list": doc.selling_price_list,
		"items": [
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": row.qty,
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
				"warehouse": row.warehouse,
				"delivery_date": str(row.delivery_date) if row.delivery_date else None,
			}
			for row in doc.items
		],
		"grand_total": doc.grand_total,
	}


def prepare_sales_order(
	customer: str,
	items: list[dict[str, Any]],
	company: str | None = None,
	delivery_date: str | None = None,
	selling_price_list: str | None = None,
) -> dict[str, Any]:
	"""Resolve inputs and return a preview without writing a Sales Order."""
	approvals.prune_expired()
	user = _current_user()
	if not customer or not str(customer).strip():
		return {"status": "needs_input", "missing": ["customer"]}

	customer_resolution = resolve_customer(customer)
	if customer_resolution["status"] != "resolved":
		return {
			"status": customer_resolution["status"],
			"field": "customer",
			"query": customer,
			"candidates": customer_resolution.get("candidates", []),
		}
	item_result = _prepare_items(items)
	if item_result["status"] != "resolved":
		return item_result

	resolved_company = _resolve_company(company)
	if not resolved_company:
		return {
			"status": "needs_input",
			"missing": ["company"],
			"message": "No default Company is configured for the authenticated service user.",
		}
	transaction_date = getdate(nowdate())
	resolved_delivery_date = getdate(delivery_date or transaction_date)
	if resolved_delivery_date < transaction_date:
		return public_error("INVALID_ORDER_DETAILS", message="Delivery date cannot be before the transaction date.")

	doc = frappe.new_doc("Sales Order")
	doc.naming_series = "SAL-ORD-.YYYY.-"
	doc.customer = customer_resolution["candidate"]["value"]
	doc.company = resolved_company
	doc.order_type = "Sales"
	doc.transaction_date = transaction_date
	doc.delivery_date = resolved_delivery_date
	if selling_price_list:
		doc.selling_price_list = selling_price_list
	for item in item_result["items"]:
		doc.append("items", {"item_code": item["item_code"], "qty": item["qty"]})

	doc.set_missing_values()
	missing_defaults = [
		field
		for field in ("selling_price_list", "price_list_currency", "currency", "conversion_rate", "plc_conversion_rate")
		if not doc.get(field)
	]
	if missing_defaults:
		return {
			"status": "needs_input",
			"missing": missing_defaults,
			"message": "ERPNext could not determine all commercial defaults for this order.",
		}
	doc.calculate_taxes_and_totals()
	doc.run_method("validate")
	if not doc.selling_price_list:
		return {
			"status": "needs_input",
			"missing": ["selling_price_list"],
			"message": "ERPNext could not determine a selling price list for this customer.",
		}

	token = approvals.create(
		action=_ACTION,
		site=frappe.local.site,
		user=user,
		payload=_safe_doc_data(doc),
	)
	return {
		"status": "ready",
		"approval_token": token,
		"expires_in_seconds": APPROVAL_TTL_SECONDS,
		"corrections": {
			"customer": customer_resolution.get("match_type") == "spelling_correction",
			"items": [item["match_type"] for item in item_result["items"] if item.get("match_type")],
		},
		"preview": _preview(doc),
	}


def _confirmation_error(code: str, message: str, *, retryable: bool) -> dict[str, Any]:
	return {
		"status": "error",
		"code": code,
		"message": message,
		"reference": new_error_reference(),
		"retryable": retryable,
	}


def confirm_sales_order(approval_token: str, confirm: bool) -> dict[str, Any]:
	"""Create the reviewed Draft only for the original site, user, and action."""
	user = _current_user()
	if not confirm:
		approvals.cancel(approval_token, action=_ACTION, site=frappe.local.site, user=user)
		return {
			"status": "confirmation_required",
			"code": "CONFIRMATION_REQUIRED",
			"message": "Review the Sales Order preview before confirming it.",
			"reference": new_error_reference(),
			"retryable": False,
		}
	approval, state = approvals.claim_for_confirm_write(
		approval_token,
		action=_ACTION,
		site=frappe.local.site,
		user=user,
	)
	if state != "available" or approval is None:
		code, message, retryable = confirmation_failure(state, "Sales Order")
		return _confirmation_error(code, message, retryable=retryable)
	if not frappe.has_permission("Sales Order", "create"):
		return _confirmation_error(
			"PERMISSION_DENIED",
			"The authenticated user cannot create Sales Orders.",
			retryable=False,
		)

	try:
		doc = frappe.get_doc(approval.payload)
		doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
		frappe.db.commit()
	except frappe.PermissionError:
		frappe.db.rollback()
		raise
	except Exception:
		frappe.db.rollback()
		raise
	return {"status": "created", "sales_order": doc.name, "docstatus": doc.docstatus}
