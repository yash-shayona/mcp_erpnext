"""Installation hooks for site-scoped MCP business defaults."""

from __future__ import annotations

import click
import frappe
from frappe.installer import update_site_config

from mcp_erpnext.config.business_defaults import CONFIG_KEY


BUSINESS_DEFAULTS_SCAFFOLD = {"site": {}, "companies": {}, "quotation_validity_days": 0}
INITIALIZED_MESSAGE = (
	"mcp_erpnext: initialized mcp_business_defaults site configuration scaffold."
)
PRESERVED_MESSAGE = (
	"mcp_erpnext: mcp_business_defaults already exists; preserved unchanged."
)


def ensure_business_defaults_site_config() -> bool:
	"""Create the valid empty scaffold only when no effective value exists."""
	if CONFIG_KEY in frappe.conf:
		click.echo(PRESERVED_MESSAGE)
		return False

	update_site_config(CONFIG_KEY, BUSINESS_DEFAULTS_SCAFFOLD)
	click.echo(INITIALIZED_MESSAGE)
	return True


def after_install() -> None:
	"""Initialize discoverable, non-destructive site configuration on install."""
	ensure_business_defaults_site_config()
