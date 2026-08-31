"""Permission-aware, two-phase Customer operations for approved workflows."""

from __future__ import annotations

from typing import Any

import frappe

from ...approvals import APPROVAL_TTL_SECONDS, approvals
from ...config.masters import customer as customer_config
from ...observability import new_error_reference
from ..common.creation_contract import missing_input_response, resolve_creation_contract
from ..common.entity_resolution import find_candidates, resolve_candidate, search_status
from ..common.field_value_resolver import resolve_contract_values

_ACTION = "create_customer"


def _current_user() -> str:
    user = getattr(frappe.session, "user", None)
    if not user or user in {"Guest", "guest"}:
        frappe.throw(
            "An authenticated Frappe user is required for Customer creation.",
            frappe.PermissionError,
        )
    return user


def _reference(candidate: dict[str, Any]) -> dict[str, str | None]:
    """Return only the stable Customer reference a parent workflow needs."""
    return {
        "doctype": "Customer",
        "name": candidate.get("value"),
        "customer_name": candidate.get("customer_name") or candidate.get("label"),
    }


def _customer_has_field(fieldname: str) -> bool:
    return bool(frappe.get_meta("Customer").has_field(fieldname))


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _confirmation_error(code: str, message: str, *, retryable: bool) -> dict[str, Any]:
    return {
        "status": "error",
        "code": code,
        "message": message,
        "reference": new_error_reference(),
        "retryable": retryable,
    }


def search_customers(query: str) -> dict[str, Any]:
    candidates = find_candidates(
        "Customer",
        query,
        customer_config.SEARCH_FILTERS,
        customer_config.SEARCH_FIELDS,
        customer_config.DISPLAY_FIELDS,
    )
    return {
        "status": search_status(query, candidates),
        "doctype": "Customer",
        "query": query,
        "candidates": candidates,
    }


def resolve_customer(query: str) -> dict[str, Any]:
    return resolve_candidate(
        "Customer",
        query,
        customer_config.SEARCH_FILTERS,
        customer_config.SEARCH_FIELDS,
        customer_config.DISPLAY_FIELDS,
    )


def resolve_customer_for_workflow(query: str) -> dict[str, Any]:
    """Translate Customer lookup into the reusable parent-workflow contract."""
    resolution = resolve_customer(query)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "customer": _reference(resolution["candidate"]),
            "match_type": resolution.get("match_type"),
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "needs_selection",
            "query": query,
            "candidates": resolution.get("candidates", []),
        }
    return {"status": "needs_customer_creation", "query": query, "candidates": []}


def _normalise_identifier(fieldname: str, value: str) -> str:
    if fieldname == "gstin":
        return value.upper()
    if fieldname == "email_id":
        return value.casefold()
    return value


def _duplicate_matches(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Find visible exact duplicates before either preview or persistent creation."""
    identifiers = [
        ("name", data["customer_name"]),
        ("customer_name", data["customer_name"]),
    ]
    if data.get("mobile_no"):
        identifiers.append(("mobile_no", data["mobile_no"]))
    if data.get("email_id"):
        identifiers.append(("email_id", data["email_id"]))
    if data.get("gstin") and _customer_has_field("gstin"):
        identifiers.append(("gstin", data["gstin"]))

    matches: list[dict[str, Any]] = []
    for fieldname, value in identifiers:
        value = _normalise_identifier(fieldname, value)
        rows = frappe.get_list(
            "Customer",
            filters={fieldname: value, **customer_config.SEARCH_FILTERS},
            fields=["name", "customer_name", "customer_group", "territory"],
            limit_page_length=10,
            ignore_permissions=False,
        )
        if rows:
            matches.append(
                {
                    "identifier": fieldname,
                    "candidates": [
                        {
                            "value": row.get("name"),
                            "label": row.get("customer_name") or row.get("name"),
                            "customer_name": row.get("customer_name"),
                            "customer_group": row.get("customer_group"),
                            "territory": row.get("territory"),
                        }
                        for row in rows
                    ],
                }
            )
    return matches


def _customer_data(
    customer: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate and map the narrow Customer input contract without writing."""
    if not isinstance(customer, dict):
        return None, _confirmation_error(
            "INVALID_CUSTOMER_DETAILS",
            "Customer details must be an object.",
            retryable=False,
        )

    provided = {
        fieldname: value
        for fieldname in customer_config.CREATION_FIELDS
        if (value := _clean_text(customer.get(fieldname))) is not None
    }
    contract = resolve_creation_contract(
        doctype="Customer",
        input_values=provided,
        creation_fields=customer_config.CREATION_FIELDS,
        policy_values=customer_config.POLICY_VALUES,
        path_prefix="customer",
        get_meta=frappe.get_meta,
        new_document=frappe.new_doc,
    )
    if contract["missing"]:
        return None, missing_input_response(contract)

    resolved_fields = resolve_contract_values(
        contract=contract,
        creation_fields=customer_config.CREATION_FIELDS,
        path_prefix="customer",
        reference_filters=customer_config.REFERENCE_FILTERS,
        get_list=frappe.get_list,
    )
    if resolved_fields["status"] != "resolved":
        return None, resolved_fields
    data: dict[str, Any] = {"doctype": "Customer", **resolved_fields["values"]}

    contact = customer.get("contact") or {}
    address = customer.get("address") or {}
    if not isinstance(contact, dict) or not isinstance(address, dict):
        return None, _confirmation_error(
            "INVALID_CUSTOMER_DETAILS",
            "Contact and address details must be objects.",
            retryable=False,
        )

    for source, target in customer_config.CONTACT_FIELD_MAP.items():
        if value := _clean_text(contact.get(source)):
            data[target] = _normalise_identifier(target, value)

    gstin = _clean_text(customer.get("gstin"))
    if gstin:
        if not _customer_has_field("gstin"):
            return None, _confirmation_error(
                "GSTIN_UNSUPPORTED",
                "GSTIN is not configured for Customer on this site.",
                retryable=False,
            )
        data["gstin"] = _normalise_identifier("gstin", gstin)

    if address:
        required_address_fields = ("address_line1", "city", "country")
        missing = [
            f"customer.address.{fieldname}"
            for fieldname in required_address_fields
            if not _clean_text(address.get(fieldname))
        ]
        if missing:
            return None, {"status": "needs_input", "missing": missing}
        address_data = {
            fieldname: _clean_text(address.get(fieldname))
            for fieldname in customer_config.ADDRESS_FIELDS
        }
        address_data["doctype"] = "Address"
        address_data["address_title"] = data["customer_name"]
        address_data["address_type"] = "Billing"
        address_data["links"] = [
            {"link_doctype": "Customer", "link_name": data["customer_name"]}
        ]
        if gstin:
            address_data["gstin"] = data["gstin"]
        frappe.get_doc(address_data).run_method("validate")
        # India Compliance deliberately maps its quick-entry address through this
        # field; core ERPNext uses address_line1 directly.
        data[
            (
                "_address_line1"
                if _customer_has_field("_address_line1")
                else "address_line1"
            )
        ] = address_data["address_line1"]
        for fieldname in ("address_line2", "city", "state", "pincode", "country"):
            if address_data.get(fieldname):
                data[fieldname] = address_data[fieldname]

    return data, None


def _create_permissions(data: dict[str, Any]) -> list[str]:
    missing = []
    if not frappe.has_permission("Customer", "create"):
        missing.append("Customer")
    if any(
        data.get(fieldname)
        for fieldname in ("first_name", "last_name", "email_id", "mobile_no")
    ) and not frappe.has_permission("Contact", "create"):
        missing.append("Contact")
    if data.get("address_line1") or data.get("_address_line1"):
        if not frappe.has_permission("Address", "create"):
            missing.append("Address")
    return missing


def _permission_denied(missing: list[str]) -> dict[str, Any]:
    return {
        "status": "permission_denied",
        "missing_permissions": missing,
        "message": "The authenticated user cannot create the required Customer records.",
    }


def _preview(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "customer_name": data["customer_name"],
        "customer_type": data["customer_type"],
        "customer_group": data.get("customer_group"),
        "territory": data.get("territory"),
        "contact": {
            fieldname: data.get(fieldname)
            for fieldname in ("first_name", "last_name", "email_id", "mobile_no")
            if data.get(fieldname)
        },
        "address": {
            fieldname: data.get(fieldname)
            for fieldname in ("address_line2", "city", "state", "pincode", "country")
            if data.get(fieldname)
        }
        | (
            {"address_line1": data.get("_address_line1") or data.get("address_line1")}
            if data.get("_address_line1") or data.get("address_line1")
            else {}
        ),
        "gstin": data.get("gstin"),
    }


def prepare_customer(customer: dict[str, Any]) -> dict[str, Any]:
    """Validate a proposed Customer and issue a private confirmation token without a write."""
    approvals.prune_expired()
    _current_user()
    data, failure = _customer_data(customer)
    if failure:
        return failure
    assert data is not None
    if missing := _create_permissions(data):
        return _permission_denied(missing)
    if duplicates := _duplicate_matches(data):
        return {"status": "duplicate_suspected", "duplicates": duplicates}

    # Run Customer hooks/validation now; only a later explicit confirmation may insert it.
    frappe.get_doc(data).run_method("validate")
    token = approvals.create(
        action=_ACTION, site=frappe.local.site, user=_current_user(), payload=data
    )
    return {
        "status": "ready",
        "approval_token": token,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "preview": _preview(data),
    }


def confirm_customer(approval_token: str, confirm: bool) -> dict[str, Any]:
    """Create the reviewed Customer only for its original site and authenticated user."""
    approvals.prune_expired()
    if not confirm:
        return _confirmation_error(
            "CONFIRMATION_REQUIRED",
            "Review the Customer preview before confirming it.",
            retryable=False,
        )
    approval, state = approvals.lookup(
        approval_token, action=_ACTION, site=frappe.local.site, user=_current_user()
    )
    if state == "expired":
        return _confirmation_error(
            "CONFIRMATION_EXPIRED",
            "This Customer confirmation has expired. Please prepare it again.",
            retryable=True,
        )
    if state == "unavailable" or approval is None:
        return _confirmation_error(
            "CONFIRMATION_UNAVAILABLE",
            "This Customer confirmation is not available in the current session.",
            retryable=False,
        )
    if approval.result_document:
        return {
            "status": "created",
            "customer": {
                "doctype": "Customer",
                "name": approval.result_document,
                "customer_name": approval.payload["customer_name"],
            },
            "idempotent": True,
        }
    if missing := _create_permissions(approval.payload):
        return _permission_denied(missing)
    if duplicates := _duplicate_matches(approval.payload):
        return {"status": "duplicate_suspected", "duplicates": duplicates}

    try:
        doc = frappe.get_doc(approval.payload)
        doc.insert(ignore_permissions=False, ignore_links=False, ignore_mandatory=False)
        frappe.db.commit()
    except frappe.PermissionError:
        frappe.db.rollback()
        return _permission_denied(["Customer"])
    except Exception:
        frappe.db.rollback()
        raise
    approval.result_document = doc.name
    return {
        "status": "created",
        "customer": {
            "doctype": "Customer",
            "name": doc.name,
            "customer_name": doc.customer_name,
        },
        "idempotent": False,
    }
