"""MCP wrapper for Selling Terms and Conditions resolution."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import selection_directive
from ...contracts.registry import tool_meta
from ...contracts.selling.terms import TermsResolutionOutput, TermsResolutionResult
from ...runtime import execute_tool_with_context
from ...services.selling.terms import (
    resolve_terms_and_conditions as _resolve_terms_and_conditions,
)

_resolution_adapter = TypeAdapter(TermsResolutionResult)


def _with_selection_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") != "ambiguous":
        return result
    return {**result, "interaction": selection_directive().model_dump(mode="json")}


def resolve_terms_and_conditions(
    query: NonEmptyString, ctx: Context
) -> TermsResolutionOutput:
    """Resolve one enabled, permitted Selling Terms template."""
    result = execute_tool_with_context(
        ctx,
        "resolve_terms_and_conditions",
        lambda: _resolve_terms_and_conditions(query),
        rest_arguments={"query": query},
    )
    return TermsResolutionOutput(
        root=_resolution_adapter.validate_python(_with_selection_interaction(result))
    )


def register_terms_tools(mcp: Any) -> None:
    mcp.tool(meta=tool_meta("resolve_terms_and_conditions"), structured_output=True)(
        resolve_terms_and_conditions
    )
