"""MCP wrapper for Payment Terms Template resolution."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString
from ...contracts.interaction import selection_directive
from ...contracts.registry import tool_meta
from ...contracts.selling.payment_terms import (
    PaymentTermsResolutionOutput,
    PaymentTermsResolutionResult,
)
from ...runtime import execute_tool_with_context
from ...services.selling.payment_terms import (
    resolve_payment_terms_template as _resolve_payment_terms_template,
)

_resolution_adapter = TypeAdapter(PaymentTermsResolutionResult)


def _with_selection_interaction(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") != "ambiguous":
        return result
    return {**result, "interaction": selection_directive().model_dump(mode="json")}


def resolve_payment_terms_template(
    query: NonEmptyString, ctx: Context
) -> PaymentTermsResolutionOutput:
    """Resolve one permitted Payment Terms Template."""
    result = execute_tool_with_context(
        ctx,
        "resolve_payment_terms_template",
        lambda: _resolve_payment_terms_template(query),
        rest_arguments={"query": query},
    )
    return PaymentTermsResolutionOutput(
        root=_resolution_adapter.validate_python(_with_selection_interaction(result))
    )


def register_payment_terms_tools(mcp: Any) -> None:
    mcp.tool(meta=tool_meta("resolve_payment_terms_template"), structured_output=True)(
        resolve_payment_terms_template
    )
