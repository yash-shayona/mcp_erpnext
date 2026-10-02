"""Permission-safe native Purchase Order to Draft Purchase Receipt conversion."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...public_errors import defined_error
from ..common.fingerprint import stable_fingerprint
from ..common.write_policy import approval_entry_failure, current_mode, direct_entry_failure, disabled_failure, exact_mode_failure
from ...settings import WriteMode

_ACTION = "convert_purchase_order_to_purchase_receipt"
_SOURCE = "Purchase Order"
_TARGET = "Purchase Receipt"


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw("An authenticated Frappe user is required.", frappe.PermissionError)
    return user


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _value(item) for key, item in value.items()}
    return value


def _field(doc: Any, name: str) -> Any:
    return _value(doc.get(name))


def _load_source(name: str) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        source = frappe.get_doc(_SOURCE, name)
    except frappe.DoesNotExistError:
        return None, _error("SOURCE_NOT_FOUND")
    except frappe.PermissionError:
        return None, _error("PERMISSION_DENIED")
    if not source.has_permission("read"):
        return None, _error("PERMISSION_DENIED")
    if int(source.docstatus or 0) != 1:
        return None, _error("SOURCE_NOT_READY")
    if _field(source, "status") in {"Closed", "On Hold", "Cancelled"}:
        return None, _error("SOURCE_NOT_ELIGIBLE")
    if any(bool(source.get(field)) for field in ("is_subcontracted", "is_old_subcontracting_flow", "is_internal_supplier", "is_return")):
        return None, _error("UNSUPPORTED_SOURCE")
    if not frappe.has_permission(_TARGET, "create"):
        return None, _error("PERMISSION_DENIED")
    return source, None


def _warehouse(name: str | None, company: str | None) -> tuple[str | None, dict[str, Any] | None]:
    if not name:
        return None, None
    try:
        warehouse = frappe.get_doc("Warehouse", name)
    except frappe.DoesNotExistError:
        return None, _error("WAREHOUSE_NOT_FOUND")
    except frappe.PermissionError:
        return None, _error("PERMISSION_DENIED")
    if not warehouse.has_permission("read"):
        return None, _error("PERMISSION_DENIED")
    try:
        from erpnext.stock.utils import is_group_warehouse, validate_disabled_warehouse, validate_warehouse_company
        validate_disabled_warehouse(name)
        validate_warehouse_company(name, company)
        is_group_warehouse(name)
    except frappe.PermissionError:
        return None, _error("PERMISSION_DENIED")
    except Exception:
        return None, _error("INVALID_WAREHOUSE")
    if bool(warehouse.get("disabled")) or bool(warehouse.get("is_group")) or (company and warehouse.get("company") != company):
        return None, _error("INVALID_WAREHOUSE")
    return name, None


def _native(source_name: str, selected: list[str]) -> Any:
    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    return make_purchase_receipt(source_name, target_doc=None, args={"filtered_children": selected})


def _source_rows(source: Any, selected: list[str]) -> dict[str, Any]:
    return {row.name: row for row in source.get("items") or [] if row.name in selected}


def _item_configuration(item_code: str) -> Any:
    return frappe.get_cached_value(
        "Item",
        item_code,
        ["inspection_required_before_purchase", "has_serial_no", "has_batch_no", "is_fixed_asset", "is_stock_item"],
        as_dict=True,
    ) or {}


def _apply(source: Any, target: Any, lines: list[dict[str, Any]], posting_date: str | None, delivery_note: str | None) -> dict[str, Any] | None:
    by_source = _source_rows(source, [line["purchase_order_item"] for line in lines])
    target_by_source = {row.get("purchase_order_item"): row for row in target.get("items") or []}
    if len(target_by_source) != len(lines):
        return _error("NO_MAPPABLE_ITEMS")
    for line in lines:
        source_row = by_source.get(line["purchase_order_item"])
        target_row = target_by_source.get(line["purchase_order_item"])
        if source_row is None:
            return _error("INVALID_SOURCE_ROW")
        if source_row.get("delivered_by_supplier"):
            return _error("UNSUPPORTED_SOURCE_ROW")
        if float(source_row.get("qty") or 0) <= 0:
            return _error("UNSUPPORTED_SOURCE_ROW")
        item_config = _item_configuration(source_row.get("item_code"))
        remaining = float(source_row.get("qty") or 0) - float(source_row.get("received_qty") or 0)
        proposed = float(line["accepted_qty"]) + float(line.get("rejected_qty") or 0)
        if proposed > remaining + 1e-9:
            return _error("QUANTITY_EXCEEDS_REMAINING")
        accepted, failure = _warehouse(line.get("warehouse"), target.get("company") or source.get("company"))
        if failure:
            return failure
        rejected, failure = _warehouse(line.get("rejected_warehouse"), target.get("company") or source.get("company"))
        if failure:
            return failure
        if accepted and rejected and accepted == rejected:
            return _error("INVALID_WAREHOUSE")
        target_row.qty = line["accepted_qty"]
        target_row.rejected_qty = line.get("rejected_qty") or 0
        target_row.received_qty = float(target_row.qty or 0) + float(target_row.rejected_qty or 0)
        if accepted:
            target_row.warehouse = accepted
        if rejected:
            target_row.rejected_warehouse = rejected
        if float(target_row.rejected_qty or 0) > 0 and not target_row.get("rejected_warehouse") and not target.get("rejected_warehouse"):
            return _error("REJECTED_WAREHOUSE_REQUIRED")
        if float(target_row.qty or 0) > 0 and bool(item_config and item_config.get("is_stock_item")) and not target_row.get("warehouse"):
            return _error("WAREHOUSE_REQUIRED")
    if posting_date:
        target.posting_date = posting_date
    if delivery_note is not None:
        target.supplier_delivery_note = delivery_note
    if hasattr(target, "run_method"):
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        target.run_method("set_use_serial_batch_fields")
    return None


def _preview(source: Any, target: Any, lines: list[dict[str, Any]]) -> dict[str, Any]:
    source_rows = _source_rows(source, [line["purchase_order_item"] for line in lines])
    target_rows = {row.get("purchase_order_item"): row for row in target.get("items") or []}
    items = []
    for line in lines:
        source_row = source_rows[line["purchase_order_item"]]
        row = target_rows[line["purchase_order_item"]]
        items.append({
            "purchase_order_item": line["purchase_order_item"],
            "item_code": _field(row, "item_code"),
            "item_name": _field(row, "item_name"),
            "uom": _field(row, "uom"),
            "conversion_factor": _field(row, "conversion_factor"),
            "ordered_qty": _field(source_row, "qty"),
            "already_received_qty": _field(source_row, "received_qty"),
            "native_remaining_qty": float(source_row.get("qty") or 0) - float(source_row.get("received_qty") or 0),
            "accepted_qty": _field(row, "qty"),
            "rejected_qty": _field(row, "rejected_qty"),
            "received_qty": _field(row, "received_qty"),
            "warehouse": _field(row, "warehouse"),
            "rejected_warehouse": _field(row, "rejected_warehouse") or _field(target, "rejected_warehouse"),
            "requirements": {
                "quality_inspection": bool(_item_configuration(source_row.get("item_code")).get("inspection_required_before_purchase")),
                "serial_no": bool(_item_configuration(source_row.get("item_code")).get("has_serial_no")),
                "batch_no": bool(_item_configuration(source_row.get("item_code")).get("has_batch_no")),
                "fixed_asset": bool(_item_configuration(source_row.get("item_code")).get("is_fixed_asset")),
                "rejected_warehouse": float(row.get("rejected_qty") or 0) > 0,
            },
        })
    return {
        "source": {"doctype": _SOURCE, "name": source.name, "docstatus": int(source.docstatus), "status": _field(source, "status"), "supplier": _field(source, "supplier"), "company": _field(source, "company"), "per_received": _field(source, "per_received"), "modified": _field(source, "modified")},
        "purchase_receipt": {"target_doctype": _TARGET, "supplier": _field(target, "supplier"), "company": _field(target, "company"), "posting_date": _field(target, "posting_date"), "supplier_delivery_note": _field(target, "supplier_delivery_note"), "currency": _field(target, "currency"), "items": items, "totals": {key: _field(target, key) for key in ("total_qty", "net_total", "total_taxes_and_charges", "grand_total")}, "warning": "This operation creates a Draft only. Later submission can affect stock, accounting, assets, and reservations."},
    }


def _map(source: Any, lines: list[dict[str, Any]], posting_date: str | None, delivery_note: str | None):
    selected = [line["purchase_order_item"] for line in lines]
    try:
        target = _native(source.name, selected)
    except frappe.PermissionError:
        return None, None, _error("PERMISSION_DENIED")
    except frappe.ValidationError:
        return None, None, _error("NATIVE_VALIDATION_FAILED")
    except Exception:
        return None, None, _error("CONVERSION_UNAVAILABLE")
    if int(target.docstatus or 0) != 0:
        return None, None, _error("CONVERSION_UNAVAILABLE")
    failure = _apply(source, target, lines, posting_date, delivery_note)
    if failure:
        return None, None, failure
    preview = _preview(source, target, lines)
    return target, preview, None


def _fingerprint(preview: dict[str, Any]) -> str:
    return stable_fingerprint(preview, ignored_paths={("purchase_receipt", "posting_time")})


def prepare_purchase_order_to_purchase_receipt(purchase_order: str, lines: list[dict[str, Any]], posting_date: str | None = None, supplier_delivery_note: str | None = None) -> dict[str, Any]:
    if failure := disabled_failure("create"):
        return _error(failure.code)
    user = _user()
    source, failure = _load_source(purchase_order.strip() if isinstance(purchase_order, str) else "")
    if failure:
        return failure
    target, preview, failure = _map(source, lines, posting_date, supplier_delivery_note)
    if failure:
        return failure
    if current_mode("create") is WriteMode.DIRECT:
        return {"status": "preview", "preview": preview}
    approvals.prune_expired()
    token = approvals.create(action=_ACTION, site=frappe.local.site, user=user, payload={"source_doctype": _SOURCE, "source_name": source.name, "lines": lines, "posting_date": posting_date, "supplier_delivery_note": supplier_delivery_note, "fingerprint": _fingerprint(preview), "projection": preview})
    return {"status": "ready", "approval_token": token, "expires_in_seconds": APPROVAL_TTL_SECONDS, "preview": preview, "interaction": approval_directive().model_dump(mode="json")}


def confirm_purchase_order_to_purchase_receipt(approval_token: str, confirm: bool) -> dict[str, Any]:
    if failure := approval_entry_failure("create"):
        return _error(failure.code)
    user = _user()
    if not confirm:
        approvals.cancel(approval_token, action=_ACTION, site=frappe.local.site, user=user)
        return _error("CONFIRMATION_REQUIRED")
    approval, state = approvals.claim_for_confirm_write(approval_token, action=_ACTION, site=frappe.local.site, user=user)
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Purchase Receipt conversion")
        return _error(code, retryable=retryable)
    payload = approval.payload
    if payload.get("source_doctype") != _SOURCE or not payload.get("source_name") or not payload.get("fingerprint") or not isinstance(payload.get("lines"), list):
        return _error("CONFIRMATION_UNAVAILABLE")
    source, failure = _load_source(payload["source_name"])
    if failure:
        return failure if failure.get("code") == "PERMISSION_DENIED" else _error("STALE_CONFIRMATION")
    target, preview, failure = _map(source, payload["lines"], payload.get("posting_date"), payload.get("supplier_delivery_note"))
    if failure or _fingerprint(preview) != payload["fingerprint"]:
        return failure if failure and failure.get("code") == "PERMISSION_DENIED" else _error("STALE_CONFIRMATION")
    try:
        if failure := exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED):
            return _error(failure.code)
        target.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error("PERMISSION_DENIED")
    except frappe.ValidationError:
        frappe.db.rollback()
        return _error("NATIVE_VALIDATION_FAILED")
    except Exception:
        frappe.db.rollback()
        return _error("CONVERSION_FAILED")
    return {"status": "created", "doctype": _TARGET, "purchase_receipt": target.name, "docstatus": int(target.docstatus), "source_purchase_order": source.name, "supplier": _field(target, "supplier"), "company": _field(target, "company"), "item_count": len(target.get("items") or [])}


def execute_purchase_order_to_purchase_receipt(purchase_order: str, lines: list[dict[str, Any]], posting_date: str | None = None, supplier_delivery_note: str | None = None) -> dict[str, Any]:
    if failure := direct_entry_failure("create"):
        return _error(failure.code)
    source, failure = _load_source(purchase_order.strip() if isinstance(purchase_order, str) else "")
    if failure:
        return failure
    target, preview, failure = _map(source, lines, posting_date, supplier_delivery_note)
    if failure:
        return failure
    try:
        if failure := exact_mode_failure("create", WriteMode.DIRECT):
            return _error(failure.code)
        target.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    return {"status": "created", "doctype": _TARGET, "purchase_receipt": target.name, "docstatus": int(target.docstatus), "source_purchase_order": source.name, "supplier": _field(target, "supplier"), "company": _field(target, "company"), "item_count": len(target.get("items") or [])}
