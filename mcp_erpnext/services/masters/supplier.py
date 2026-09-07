"""Permission-aware Supplier resolution for the Purchase MCP profile."""

from __future__ import annotations

from typing import Any

from ...config.masters import supplier as supplier_config
from ..common.entity_resolution import find_candidates, resolve_candidate, search_status


def _reference(candidate: dict[str, Any]) -> dict[str, str | None]:
    return {
        "doctype": "Supplier",
        "name": candidate.get("value"),
        "supplier_name": candidate.get("supplier_name") or candidate.get("label"),
        "supplier_group": candidate.get("supplier_group"),
    }


def _candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference": _reference(candidate),
        "label": candidate.get("label") or candidate.get("value"),
        "score": candidate.get("score", 0.0),
    }


def search_suppliers(query: str) -> dict[str, Any]:
    candidates = find_candidates(
        "Supplier",
        query,
        supplier_config.SEARCH_FILTERS,
        supplier_config.SEARCH_FIELDS,
        supplier_config.DISPLAY_FIELDS,
    )
    return {
        "status": search_status(query, candidates),
        "doctype": "Supplier",
        "query": query,
        "candidates": [_candidate(candidate) for candidate in candidates],
    }


def resolve_supplier(query: str) -> dict[str, Any]:
    return resolve_candidate(
        "Supplier",
        query,
        supplier_config.SEARCH_FILTERS,
        supplier_config.SEARCH_FIELDS,
        supplier_config.DISPLAY_FIELDS,
    )


def resolve_supplier_for_workflow(query: str) -> dict[str, Any]:
    """Return a terminal Supplier state; ambiguous results require selection."""
    resolution = resolve_supplier(query)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "doctype": "Supplier",
            "reference": _reference(resolution["candidate"]),
            "match_type": resolution.get("match_type"),
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "ambiguous",
            "doctype": "Supplier",
            "query": query,
            "candidates": [_candidate(candidate) for candidate in resolution.get("candidates", [])],
        }
    return {"status": "not_found", "doctype": "Supplier", "query": query, "candidates": []}
