"""Central registration guard for public MCP tools."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..contracts.registry import get_tool_contract


def tool_registration_kwargs(name: str, kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Add contract-governed metadata and annotations to one public tool.

    Registration modules may continue to own a tool's name and description, but
    cannot choose independent project metadata or standard safety hints.
    """
    try:
        contract = get_tool_contract(name)
    except KeyError as error:
        raise RuntimeError(
            f"{name}: public tools must declare a ToolContract before registration."
        ) from error

    registered_meta = kwargs.get("meta")
    if registered_meta is not None and not isinstance(registered_meta, Mapping):
        raise RuntimeError(f"{name}: MCP metadata must be a mapping.")
    if (
        isinstance(registered_meta, Mapping)
        and registered_meta.get("mcp_erpnext") != contract.mcp_meta()["mcp_erpnext"]
    ):
        raise RuntimeError(
            f"{name}: custom MCP metadata must be derived from its ToolContract."
        )

    registered_annotations = kwargs.get("annotations")
    if (
        registered_annotations is not None
        and registered_annotations.model_dump() != contract.mcp_annotations().model_dump()
    ):
        raise RuntimeError(
            f"{name}: standard MCP annotations must be derived from its ToolContract."
        )

    merged_meta = {**(registered_meta or {}), **contract.mcp_meta()}
    return {
        **kwargs,
        "meta": merged_meta,
        "annotations": contract.mcp_annotations(),
        "structured_output": kwargs.get("structured_output", True),
    }


class GovernedMCP:
    """Delegate FastMCP registration while enforcing the public contract registry."""

    def __init__(self, mcp: Any):
        self._mcp = mcp

    def tool(self, *args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        declared_name = kwargs.get("name")
        if declared_name is None and args:
            declared_name = args[0]

        def register(function: Any) -> Any:
            name = declared_name or function.__name__
            return self._mcp.tool(*args, **tool_registration_kwargs(name, kwargs))(function)

        return register

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)
