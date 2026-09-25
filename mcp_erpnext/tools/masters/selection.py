"""MCP wrapper for stateless explicit master-data candidate selection."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ...contracts.common import NonEmptyString, ResolvableDoctype
from ...contracts.masters.resolution import SelectResolvedCandidateOutput, SelectResolvedCandidateResult
from ...contracts.registry import tool_meta
from ...runtime import execute_tool_with_context
from ...services.masters.selection import select_resolved_candidate as _select_resolved_candidate


_selection_adapter = TypeAdapter(SelectResolvedCandidateResult)


def select_resolved_candidate(
	doctype: ResolvableDoctype, name: NonEmptyString, ctx: Context
) -> SelectResolvedCandidateOutput:
	"""Revalidate a selected Customer, Item, or Selling Terms reference."""
	result = execute_tool_with_context(
		ctx, "select_resolved_candidate", lambda: _select_resolved_candidate(doctype, name), rest_arguments={"doctype": doctype, "name": name}
	)
	return SelectResolvedCandidateOutput(root=_selection_adapter.validate_python(result))


def register_selection_tools(mcp: Any) -> None:
	"""Register generic, explicit selection for current resolvable entities."""
	mcp.tool(meta=tool_meta("select_resolved_candidate"), structured_output=True)(
		select_resolved_candidate
	)
