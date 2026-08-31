"""Permission-aware matching primitives for trusted ERPNext master services."""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher
from collections.abc import Callable
from typing import Any

import frappe

MAX_CANDIDATES = 10
MIN_STRONG_MATCH_SCORE = 0.88
MIN_MATCH_MARGIN = 0.08


def normalize(value: Any) -> str:
    """Return a comparison-safe representation without changing stored values."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def tokens(value: Any) -> list[str]:
    return [token for token in normalize(value).split() if token]


def _search_tokens(query: str) -> list[str]:
    query_tokens = tokens(query)
    strong_tokens = [token for token in query_tokens if len(token) > 2]
    return strong_tokens or query_tokens


def _candidate_score(
    query: str, candidate: dict[str, Any], fields: tuple[str, ...]
) -> float:
    query_normalized = normalize(query)
    if not query_normalized:
        return 0.0

    values = [normalize(candidate.get(field)) for field in fields]
    values = [value for value in values if value]
    if not values:
        return 0.0

    query_tokens = set(tokens(query_normalized))
    best = 0.0
    for value in values:
        ratio = SequenceMatcher(None, query_normalized, value).ratio()
        value_tokens = set(value.split())
        if query_tokens and value_tokens:
            token_score = sum(
                max(
                    SequenceMatcher(None, query_token, value_token).ratio()
                    for value_token in value_tokens
                )
                for query_token in query_tokens
            ) / len(query_tokens)
        else:
            token_score = 0.0
        best = max(best, (ratio * 0.55) + (token_score * 0.45))
    return best


def _display_candidate(
    candidate: dict[str, Any], display_fields: tuple[str, ...]
) -> dict[str, Any]:
    return {
        "value": candidate.get("name"),
        "label": next(
            (candidate.get(field) for field in display_fields if candidate.get(field)),
            candidate.get("name"),
        ),
        **{
            field: candidate.get(field)
            for field in display_fields
            if candidate.get(field)
        },
    }


def rank_candidates(
    query: str, candidates: list[dict[str, Any]], fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Rank already-permitted candidates for a deterministic resolution decision."""
    ranked = [
        (_candidate_score(query, candidate, fields), candidate)
        for candidate in candidates
    ]
    ranked.sort(
        key=lambda pair: (
            -pair[0],
            str(pair[1].get("value") or pair[1].get("name") or ""),
        )
    )
    return [
        {**candidate, "score": round(score, 3)}
        for score, candidate in ranked[:MAX_CANDIDATES]
    ]


def resolve_ranked_candidates(
    query: str, candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Resolve only an exact or strong unambiguous candidate from a safe list."""
    if not candidates:
        return {"status": "not_found", "query": query, "candidates": []}

    normalized_query = normalize(query)
    exact = [
        candidate
        for candidate in candidates
        if normalized_query
        in {normalize(candidate.get("value")), normalize(candidate.get("label"))}
    ]
    if len(exact) == 1:
        return {
            "status": "resolved",
            "match_type": "exact",
            "candidate": exact[0],
            "candidates": candidates,
        }
    if len(exact) > 1:
        return {"status": "ambiguous", "query": query, "candidates": exact}

    top = candidates[0]
    second_score = candidates[1].get("score", 0.0) if len(candidates) > 1 else 0.0
    if (
        top.get("score", 0.0) >= MIN_STRONG_MATCH_SCORE
        and top.get("score", 0.0) - second_score >= MIN_MATCH_MARGIN
    ):
        return {
            "status": "resolved",
            "match_type": "spelling_correction",
            "candidate": top,
            "candidates": candidates,
        }
    return {"status": "ambiguous", "query": query, "candidates": candidates}


def find_candidates(
    doctype: str,
    query: str,
    base_filters: dict[str, Any],
    search_fields: tuple[str, ...],
    display_fields: tuple[str, ...],
    get_list: Callable[..., list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Find and rank only records visible through normal Frappe permissions."""
    query_tokens = _search_tokens(query)
    if not query_tokens:
        return []

    fields = tuple(dict.fromkeys(("name", *search_fields, *display_fields)))
    or_filters = [
        [doctype, field, "like", f"%{token}%"]
        for token in query_tokens
        for field in search_fields
    ]
    rows = (get_list or frappe.get_list)(
        doctype,
        filters=base_filters,
        or_filters=or_filters,
        fields=list(fields),
        limit_page_length=50,
        ignore_permissions=False,
    )
    displayed = [_display_candidate(row, display_fields) for row in rows]
    return rank_candidates(query, displayed, ("value", *display_fields))


def resolve_candidate(
    doctype: str,
    query: str,
    base_filters: dict[str, Any],
    search_fields: tuple[str, ...],
    display_fields: tuple[str, ...],
    get_list: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Resolve only an exact or strong unambiguous permitted candidate."""
    candidates = find_candidates(
        doctype, query, base_filters, search_fields, display_fields, get_list
    )
    return resolve_ranked_candidates(query, candidates)


def search_status(query: str, candidates: list[dict[str, Any]]) -> str:
    """Give public master-search endpoints the same resolution boundary."""
    if not candidates:
        return "not_found"
    normalized_query = normalize(query)
    exact = [
        candidate
        for candidate in candidates
        if normalized_query
        in {normalize(candidate.get("value")), normalize(candidate.get("label"))}
    ]
    if len(exact) == 1:
        return "resolved"
    if (
        len(candidates) == 1
        and candidates[0].get("score", 0.0) >= MIN_STRONG_MATCH_SCORE
    ):
        return "resolved"
    return "ambiguous"
