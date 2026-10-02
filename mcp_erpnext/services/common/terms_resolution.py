"""Domain-neutral Terms discovery using shared bounded candidate ranking."""

from __future__ import annotations

from typing import Any

from .entity_resolution import find_candidates, rank_candidates, resolve_ranked_candidates

TERMS_TYPO_FALLBACK_SCAN_LIMIT = 100


def _reference(candidate: dict[str, Any]) -> dict[str, str | None]:
    return {
        "doctype": "Terms and Conditions",
        "name": candidate.get("value"),
        "title": candidate.get("title") or candidate.get("label"),
    }


def _candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference": _reference(candidate),
        "label": candidate.get("label") or candidate.get("value"),
        "score": candidate.get("score", 0.0),
    }


def _fallback_candidates(query: str, get_list: Any, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Rank a bounded safe scan after all normal search tokens miss."""
    rows = get_list(
        "Terms and Conditions",
        filters=filters,
        fields=["name", "title"],
        order_by="name asc",
        limit_page_length=TERMS_TYPO_FALLBACK_SCAN_LIMIT,
        ignore_permissions=False,
    )
    displayed = [
        {
            "value": row.get("name"),
            "label": row.get("title") or row.get("name"),
            **({"title": row.get("title")} if row.get("title") else {}),
        }
        for row in rows
    ]
    return rank_candidates(query, displayed, ("value", "title"))


def resolve_terms(query: str, *, filters: dict[str, Any], get_list: Any) -> dict[str, Any]:
    """Resolve permitted Terms using the caller-owned applicability policy."""
    permitted_get_list = get_list
    candidates = find_candidates(
        "Terms and Conditions",
        query,
        filters,
        ("name", "title"),
        ("title",),
        get_list=permitted_get_list,
    )
    if not candidates:
        candidates = _fallback_candidates(query, permitted_get_list, filters)

    resolution = resolve_ranked_candidates(query, candidates)
    if resolution["status"] == "resolved":
        return {
            "status": "resolved",
            "doctype": "Terms and Conditions",
            "reference": _reference(resolution["candidate"]),
            "match_type": resolution["match_type"],
        }
    if resolution["status"] == "ambiguous":
        return {
            "status": "ambiguous",
            "doctype": "Terms and Conditions",
            "query": query,
            "candidates": [
                _candidate(candidate) for candidate in resolution.get("candidates", [])
            ],
        }
    return {
        "status": "not_found",
        "doctype": "Terms and Conditions",
        "query": query,
        "candidates": [],
    }

