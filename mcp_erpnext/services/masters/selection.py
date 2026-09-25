"""Stateless revalidation for an explicitly selected master-data candidate."""

from __future__ import annotations

from typing import Any

from ...config.masters import customer as customer_config
from ...config.masters import item as item_config
from ..common.entity_resolution import revalidate_exact_candidate
from ..selling import terms as terms_service

_SELECTABLE_ENTITIES = {
    "Customer": (customer_config.SEARCH_FILTERS, customer_config.DISPLAY_FIELDS),
    "Item": (item_config.SEARCH_FILTERS, item_config.DISPLAY_FIELDS),
    "Terms and Conditions": (
        terms_service.TERMS_SEARCH_FILTERS,
        terms_service.TERMS_DISPLAY_FIELDS,
    ),
}


def select_resolved_candidate(
    doctype: str, name: str, get_list: Any = None
) -> dict[str, Any]:
    """Return a resolved reference only after permission-aware exact revalidation.

    The public contract currently limits ``doctype`` to the map above. Future
    resolvers add their search filters/display fields here rather than creating a
    parallel selection implementation or process-local ambiguity state.
    """
    entity = _SELECTABLE_ENTITIES.get(doctype)
    if entity is None:
        return {
            "status": "not_found",
            "doctype": doctype,
            "query": name,
            "candidates": [],
        }
    filters, display_fields = entity
    resolution = revalidate_exact_candidate(
        doctype, name, filters, display_fields, get_list=get_list
    )
    if resolution["status"] != "resolved":
        return {
            "status": "not_found",
            "doctype": doctype,
            "query": resolution["query"],
            "candidates": [],
        }
    return {
        "status": "resolved",
        "doctype": doctype,
        "reference": {"doctype": doctype, "name": resolution["candidate"]["value"]},
        "match_type": "exact",
    }
