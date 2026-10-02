"""Permission-safe native Quotation to Sales Order conversion."""

from __future__ import annotations

from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals, confirmation_failure
from ...contracts.interaction import approval_directive
from ...public_errors import defined_error
from ..common.fingerprint import stable_fingerprint
from ..common.write_policy import (
    approval_entry_failure,
    current_mode,
    disabled_failure,
    direct_entry_failure,
    exact_mode_failure,
)
from ...settings import WriteMode
from .sales_order import _set_sales_order_delivery_date

_ACTION = "convert_quotation_to_sales_order"
_SOURCE_DOCTYPE = "Quotation"


def _native_make_sales_order(source_name: str) -> Any:
    """Load ERPNext's public mapper only when a conversion is actually executed."""

    from erpnext.selling.doctype.quotation.quotation import make_sales_order

    return make_sales_order(source_name)


def _error(code: str, *, retryable: bool | None = None) -> dict[str, Any]:
    return defined_error(code, retryable=retryable)


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required.", frappe.PermissionError
        )
    return user


def _load_source(name: str) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        quotation = frappe.get_doc(_SOURCE_DOCTYPE, name)
    except frappe.DoesNotExistError:
        return None, _error(
            "SOURCE_NOT_FOUND"
        )
    if not quotation.has_permission("read"):
        return None, _error(
            "PERMISSION_DENIED"
        )
    if int(quotation.docstatus) != 1:
        return None, _error(
            "SOURCE_NOT_READY",
        )
    if quotation.get("quotation_to") != "Customer":
        return None, _error(
            "UNSUPPORTED_QUOTATION_PARTY",
        )
    if not quotation.get("party_name"):
        return None, _error(
            "SOURCE_NOT_READY"
        )
    if not frappe.has_permission("Sales Order", "create"):
        return None, _error(
            "PERMISSION_DENIED",
        )
    return quotation, None


def _map_source(quotation: Any) -> Any:
    """Use ERPNext's public mapper so expiry policy and native economics remain authoritative."""

    return _native_make_sales_order(quotation.name)


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _field(doc: Any, fieldname: str) -> Any:
    value = doc.get(fieldname)
    return _json_value(value)


def _item_preview(row: Any) -> dict[str, Any]:
    return {
        "item_code": _field(row, "item_code"),
        "item_name": _field(row, "item_name"),
        "qty": _field(row, "qty"),
        "uom": _field(row, "uom"),
        "rate": _field(row, "rate"),
        "discount_percentage": _field(row, "discount_percentage"),
        "discount_amount": _field(row, "discount_amount"),
        "amount": _field(row, "amount"),
        "net_amount": _field(row, "net_amount"),
        "warehouse": _field(row, "warehouse"),
        "delivery_date": _field(row, "delivery_date"),
        "quotation_item": _field(row, "quotation_item"),
        "prevdoc_docname": _field(row, "prevdoc_docname"),
    }


def _tax_preview(row: Any) -> dict[str, Any]:
    return {
        "charge_type": _field(row, "charge_type"),
        "account_head": _field(row, "account_head"),
        "rate": _field(row, "rate"),
        "tax_amount": _field(row, "tax_amount"),
        "total": _field(row, "total"),
    }


def _stable_rows(
    doc: Any, table_field: str, fieldnames: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Serialize selected child values without depending on volatile child objects."""

    return [
        {fieldname: _field(row, fieldname) for fieldname in fieldnames}
        for row in doc.get(table_field) or []
    ]


def _preview(quotation: Any, sales_order: Any) -> dict[str, Any]:
    return {
        "source": {"doctype": _SOURCE_DOCTYPE, "quotation": quotation.name},
        "sales_order": {
            "customer": _field(sales_order, "customer"),
            "customer_name": _field(sales_order, "customer_name"),
            "company": _field(sales_order, "company"),
            "transaction_date": _field(sales_order, "transaction_date"),
            "delivery_date": _field(sales_order, "delivery_date"),
            "currency": _field(sales_order, "currency"),
            "selling_price_list": _field(sales_order, "selling_price_list"),
            "items": [_item_preview(row) for row in sales_order.get("items") or []],
            "taxes": [_tax_preview(row) for row in sales_order.get("taxes") or []],
            "totals": {
                "net_total": _field(sales_order, "net_total"),
                "total_taxes_and_charges": _field(
                    sales_order, "total_taxes_and_charges"
                ),
                "additional_discount_percentage": _field(
                    sales_order, "additional_discount_percentage"
                ),
                "discount_amount": _field(sales_order, "discount_amount"),
                "grand_total": _field(sales_order, "grand_total"),
            },
            "tc_name": _field(sales_order, "tc_name"),
            "terms": _field(sales_order, "terms"),
        },
    }


def _fingerprint(quotation: Any, preview: dict[str, Any], mapped_doc: Any) -> str:
    """Hash stable source eligibility and native target commercial state only."""

    sales_order = preview["sales_order"]
    snapshot = {
        "source": {
            "doctype": _SOURCE_DOCTYPE,
            "name": quotation.name,
            "docstatus": int(quotation.docstatus),
            "quotation_to": _field(quotation, "quotation_to"),
            "party_name": _field(quotation, "party_name"),
            "status": _field(quotation, "status"),
            "company": _field(quotation, "company"),
            "currency": _field(quotation, "currency"),
            "transaction_date": _field(quotation, "transaction_date"),
            "valid_till": _field(quotation, "valid_till"),
        },
        "sales_order": {
            **{
                key: sales_order.get(key)
                for key in (
                    "customer",
                    "customer_name",
                    "company",
                    "transaction_date",
                    "delivery_date",
                    "currency",
                    "selling_price_list",
                    "tc_name",
                    "terms",
                )
            },
            "items": sales_order.get("items", []),
            "taxes": sales_order.get("taxes", []),
            "totals": sales_order.get("totals", {}),
            "sales_team": _stable_rows(
                mapped_doc,
                "sales_team",
                ("sales_person", "allocated_percentage", "commission_rate"),
            ),
            "payment_schedule": _stable_rows(
                mapped_doc,
                "payment_schedule",
                (
                    "due_date",
                    "payment_term",
                    "invoice_portion",
                    "payment_amount",
                    "discount_type",
                    "discount_date",
                    "discount",
                ),
            ),
        },
    }
    return stable_fingerprint(snapshot)


def _map_and_preview(
    quotation: Any,
) -> tuple[Any | None, dict[str, Any] | None, dict[str, Any] | None]:
    try:
        sales_order = _map_source(quotation)
        if not _set_sales_order_delivery_date(sales_order):
            return (
                None,
                None,
                _error(
                    "CONVERSION_UNAVAILABLE",
                ),
            )
        sales_order.run_method("validate")
    except frappe.PermissionError:
        return (
            None,
            None,
            _error(
                "PERMISSION_DENIED",
            ),
        )
    except Exception:
        return (
            None,
            None,
            _error(
                "CONVERSION_UNAVAILABLE",
            ),
        )
    if int(sales_order.docstatus or 0) != 0:
        return (
            None,
            None,
            _error("CONVERSION_UNAVAILABLE"),
        )
    items = sales_order.get("items") or []
    if not items:
        return (
            None,
            None,
            _error(
                "NO_MAPPABLE_ITEMS",
            ),
        )
    for row in items:
        if not row.get("quotation_item") or not row.get("prevdoc_docname"):
            return (
                None,
                None,
                _error(
                    "CONVERSION_UNAVAILABLE",
                ),
            )
    preview = _preview(quotation, sales_order)
    return sales_order, preview, None


def prepare_quotation_to_sales_order(quotation: str) -> dict[str, Any]:
    """Prepare a native Draft Sales Order preview without persisting anything."""

    if failure := disabled_failure("create"):
        return _error(failure.code)
    user = _current_user()
    source, failure = _load_source(
        quotation.strip() if isinstance(quotation, str) else ""
    )
    if failure:
        return failure
    sales_order, preview, failure = _map_and_preview(source)
    if failure:
        return failure
    assert sales_order is not None and preview is not None
    if current_mode("create") is WriteMode.DIRECT:
        return {"status": "preview", "preview": preview}
    approvals.prune_expired()
    token = approvals.create(
        action=_ACTION,
        site=frappe.local.site,
        user=user,
        payload={
            "source_doctype": _SOURCE_DOCTYPE,
            "source_name": source.name,
            "fingerprint": _fingerprint(source, preview, sales_order),
        },
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": preview,
        "interaction": approval_directive().model_dump(mode="json"),
    }


def _stale() -> dict[str, Any]:
    return _error(
        "STALE_CONFIRMATION",
    )


def confirm_quotation_to_sales_order(
    approval_token: str, confirm: bool
) -> dict[str, Any]:
    """Create one freshly revalidated native mapped Draft Sales Order."""

    if failure := approval_entry_failure("create"):
        return _error(failure.code)
    user = _current_user()
    if not confirm:
        approvals.cancel(
            approval_token,
            action=_ACTION,
            site=frappe.local.site,
            user=user,
        )
        return _error(
            "CONFIRMATION_REQUIRED",
        )

    approval, state = approvals.claim_for_confirm_write(
        approval_token,
        action=_ACTION,
        site=frappe.local.site,
        user=user,
    )
    if state != "available" or approval is None:
        code, message, retryable = confirmation_failure(state, "Quotation conversion")
        return _error(code, retryable=retryable)
    if (
        approval.payload.get("source_doctype") != _SOURCE_DOCTYPE
        or not approval.payload.get("source_name")
        or not approval.payload.get("fingerprint")
    ):
        return _error(
            "CONFIRMATION_UNAVAILABLE"
        )

    source, failure = _load_source(approval.payload["source_name"])
    if failure:
        return _stale()
    sales_order, preview, failure = _map_and_preview(source)
    if failure or sales_order is None or preview is None:
        return _stale()
    if _fingerprint(source, preview, sales_order) != approval.payload["fingerprint"]:
        return _stale()

    try:
        if failure := exact_mode_failure("create", WriteMode.APPROVAL_REQUIRED):
            return _error(failure.code)
        sales_order.insert(
            ignore_permissions=False, ignore_links=False, ignore_mandatory=False
        )
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED",
        )
    except Exception:
        frappe.db.rollback()
        return _error(
            "CONVERSION_FAILED",
        )
    return {
        "status": "created",
        "sales_order": sales_order.name,
        "docstatus": int(sales_order.docstatus),
        "source_quotation": source.name,
        "idempotent": False,
    }


def execute_quotation_to_sales_order(quotation: str) -> dict[str, Any]:
    """Create a fresh native mapped Sales Order only in direct mode."""
    if failure := direct_entry_failure("create"):
        return _error(failure.code)
    _current_user()
    source, failure = _load_source(
        quotation.strip() if isinstance(quotation, str) else ""
    )
    if failure:
        return failure
    sales_order, _preview_data, failure = _map_and_preview(source)
    if failure or sales_order is None:
        return failure or _error("CONVERSION_UNAVAILABLE")
    try:
        if failure := exact_mode_failure("create", WriteMode.DIRECT):
            return _error(failure.code)
        sales_order.insert(
            ignore_permissions=False, ignore_links=False, ignore_mandatory=False
        )
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _error(
            "PERMISSION_DENIED",
        )
    except Exception:
        frappe.db.rollback()
        return _error(
            "CONVERSION_FAILED",
        )
    return {
        "status": "created",
        "sales_order": sales_order.name,
        "docstatus": int(sales_order.docstatus),
        "source_quotation": source.name,
        "idempotent": False,
    }
