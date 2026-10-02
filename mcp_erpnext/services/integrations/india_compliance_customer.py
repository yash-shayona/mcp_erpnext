"""Optional, prepare-safe bridge to the installed India Compliance Customer flow."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Any

import frappe


_APP_NAME = "india_compliance"
_TRANSIENT_ADDRESS_FIELD = "_address_line1"


@dataclass(frozen=True)
class CustomerCapabilities:
	"""Runtime capabilities discovered without importing India Compliance eagerly."""

	installed: bool
	native_gst_prepare: bool = False
	transient_primary_address: bool = False
	prepare_safe_enrichment: bool = False


def _installed() -> bool:
	get_installed_apps = getattr(frappe, "get_installed_apps", None)
	if not callable(get_installed_apps):
		return False
	try:
		return _APP_NAME in (get_installed_apps() or ())
	except Exception:
		# Optional capability discovery must not make generic Customer creation fail.
		return False


def get_capabilities() -> CustomerCapabilities:
	"""Discover only the installed native seams this bridge is allowed to use."""
	if not _installed():
		return CustomerCapabilities(installed=False)

	try:
		gst_utils = importlib.import_module("india_compliance.gst_india.utils")
		native_gst_prepare = all(
			callable(getattr(gst_utils, name, None))
			for name in ("validate_gstin", "guess_gst_category", "validate_gst_category")
		)
		expected_primary_address = getattr(
			importlib.import_module("india_compliance.gst_india.overrides.party"),
			"create_primary_address",
			None,
		)
		transient_primary_address = bool(
			callable(expected_primary_address)
			and _TRANSIENT_ADDRESS_FIELD in inspect.getsource(expected_primary_address)
		)
	except (ImportError, OSError, TypeError):
		return CustomerCapabilities(installed=True)

	return CustomerCapabilities(
		installed=True,
		native_gst_prepare=native_gst_prepare,
		transient_primary_address=transient_primary_address,
		# The only observed lookup path can perform external I/O and queued writes.
		prepare_safe_enrichment=False,
	)


def prepare_customer_gst(
	data: dict[str, Any],
	*,
	country: str | None = None,
	capabilities: CustomerCapabilities | None = None,
) -> CustomerCapabilities:
	"""Apply only native pure GST normalization/category validation during prepare.

	The full India Compliance Customer validation hook is intentionally not called
	here because its category setter may invoke GSTIN autofill and queued
	persistence. Confirmation remains responsible for the normal document
	lifecycle and its authoritative hooks.
	"""
	capabilities = capabilities or get_capabilities()
	if not capabilities.installed or not capabilities.native_gst_prepare:
		return capabilities

	utils = importlib.import_module("india_compliance.gst_india.utils")
	validate_gstin = utils.validate_gstin
	guess_gst_category = utils.guess_gst_category
	validate_gst_category = utils.validate_gst_category

	gstin = validate_gstin(data.get("gstin"))
	if gstin:
		data["gstin"] = gstin

	if "gst_category" in data:
		category = guess_gst_category(gstin, country, data.get("gst_category"))
		data["gst_category"] = category
		validate_gst_category(category, gstin)

	return capabilities
