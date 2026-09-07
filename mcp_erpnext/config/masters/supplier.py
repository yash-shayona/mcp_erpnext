"""Supplier lookup policy for the Purchase MCP profile."""

from __future__ import annotations

SEARCH_FILTERS = {"disabled": ["!=", 1]}
SEARCH_FIELDS = ("name", "supplier_name")
DISPLAY_FIELDS = ("supplier_name", "supplier_group")
