"""Buying-only Terms applicability; candidate mechanics remain shared."""
from __future__ import annotations
from typing import Any
import frappe
from ..common.terms_resolution import resolve_terms

BUYING_TERMS_FILTERS = {"buying": 1, "disabled": 0}


def resolve_buying_terms_and_conditions(query: str, *, get_list: Any = None) -> dict[str, Any]:
    return resolve_terms(query, filters=BUYING_TERMS_FILTERS, get_list=get_list or frappe.get_list)
