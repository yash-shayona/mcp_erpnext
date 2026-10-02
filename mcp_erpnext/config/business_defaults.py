"""Typed, site-scoped business defaults for standalone document authoring."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping

import frappe

CONFIG_KEY = "mcp_business_defaults"
QUOTATION_VALIDITY_DAYS_KEY = "quotation_validity_days"


class BusinessDefaultKey(StrEnum):
    TERMS_AND_CONDITIONS_TEMPLATE = "terms_and_conditions_template"
    PAYMENT_TERMS_TEMPLATE = "payment_terms_template"


SUPPORTED_DOCUMENT_TYPES = frozenset({"Quotation", "Sales Order", "Sales Invoice", "Purchase Order"})
_SUPPORTED_TOP_LEVEL_KEYS = frozenset(
    {"site", "companies", QUOTATION_VALIDITY_DAYS_KEY}
)


class BusinessDefaultsConfigurationError(RuntimeError):
    """The active site's business-default configuration is malformed."""


def _mapping(value: Any, *, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BusinessDefaultsConfigurationError(f"{location} must be an object.")
    return value


def _validate_document_scope(value: Any, *, location: str) -> Mapping[str, Any]:
    scope = _mapping(value, location=location)
    for doctype, configured_defaults in scope.items():
        if doctype not in SUPPORTED_DOCUMENT_TYPES:
            raise BusinessDefaultsConfigurationError(
                f"{location} contains an unsupported document type."
            )
        defaults = _mapping(configured_defaults, location=f"{location}.{doctype}")
        for key, configured_value in defaults.items():
            try:
                BusinessDefaultKey(key)
            except (TypeError, ValueError) as error:
                raise BusinessDefaultsConfigurationError(
                    f"{location}.{doctype} contains an unsupported business-default key."
                ) from error
            if not isinstance(configured_value, str) or not configured_value.strip():
                raise BusinessDefaultsConfigurationError(
                    f"{location}.{doctype}.{key} must be a non-empty record name."
                )
    return scope


def _validate_quotation_validity_days(config: Mapping[str, Any]) -> int:
    value = config.get(QUOTATION_VALIDITY_DAYS_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BusinessDefaultsConfigurationError(
            f"{CONFIG_KEY}.{QUOTATION_VALIDITY_DAYS_KEY} must be a whole number zero or greater."
        )
    return value


def _validated_config(
    raw_config: Any,
) -> tuple[Mapping[str, Any], Mapping[str, Any], int]:
    if raw_config is None:
        return {}, {}, 0
    config = _mapping(raw_config, location=CONFIG_KEY)
    unsupported = set(config) - _SUPPORTED_TOP_LEVEL_KEYS
    if unsupported:
        raise BusinessDefaultsConfigurationError(
            f"{CONFIG_KEY} contains an unsupported top-level key."
        )

    site = _validate_document_scope(
        config.get("site", {}), location=f"{CONFIG_KEY}.site"
    )
    companies = _mapping(
        config.get("companies", {}), location=f"{CONFIG_KEY}.companies"
    )
    validated_companies: dict[str, Mapping[str, Any]] = {}
    for company, company_scope in companies.items():
        if not isinstance(company, str) or not company.strip():
            raise BusinessDefaultsConfigurationError(
                f"{CONFIG_KEY}.companies keys must be non-empty Company names."
            )
        validated_companies[company] = _validate_document_scope(
            company_scope, location=f"{CONFIG_KEY}.companies.{company}"
        )
    return site, validated_companies, _validate_quotation_validity_days(config)


def get_document_business_default(
    doctype: str,
    key: BusinessDefaultKey | str,
    company: str | None,
    *,
    frappe_module: Any = frappe,
) -> str | None:
    """Resolve a company override, then a site-wide DocType default."""
    if doctype not in SUPPORTED_DOCUMENT_TYPES:
        raise BusinessDefaultsConfigurationError(
            "An unsupported document type was requested from business defaults."
        )
    try:
        typed_key = BusinessDefaultKey(key)
    except (TypeError, ValueError) as error:
        raise BusinessDefaultsConfigurationError(
            "An unsupported business-default key was requested."
        ) from error

    site, companies, _quotation_validity_days = _validated_config(
        getattr(frappe_module, "conf", {}).get(CONFIG_KEY)
    )
    if company is not None:
        if not isinstance(company, str) or not company.strip():
            raise BusinessDefaultsConfigurationError(
                "The Company used for business-default resolution must be non-empty."
            )
        configured = companies.get(company, {}).get(doctype, {}).get(typed_key.value)
        if configured is not None:
            return configured.strip()

    configured = site.get(doctype, {}).get(typed_key.value)
    return configured.strip() if configured is not None else None


def get_quotation_validity_days(*, frappe_module: Any = frappe) -> int:
    """Return the active site's non-negative Quotation validity period."""
    _site, _companies, quotation_validity_days = _validated_config(
        getattr(frappe_module, "conf", {}).get(CONFIG_KEY)
    )
    return quotation_validity_days
