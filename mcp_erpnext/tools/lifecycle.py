"""Profile-scoped MCP wrappers for shared existing-document lifecycle actions."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import TypeAdapter

from ..contracts.lifecycle import (
    LifecycleConfirmInput,
    LifecycleResult,
    PrepareActionInput,
    PrepareDeleteInput,
    PrepareUpdateInput,
    PrepareChildAddInput,
    PrepareChildRemoveInput,
)
from ..contracts.registry import tool_meta
from ..runtime import execute_tool_with_context
from ..services.common import lifecycle


def register_lifecycle_tools(mcp: Any, profile: str) -> None:
    result_adapter = TypeAdapter(LifecycleResult)

    def prepare_document_update(
        request: PrepareUpdateInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "prepare_document_update",
                lambda: lifecycle.prepare_update(
                    request.target.model_dump(),
                    [change.model_dump() for change in request.changes],
                    profile,
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def confirm_document_update(
        request: LifecycleConfirmInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "confirm_document_update",
                lambda: lifecycle.confirm(
                    "update", request.approval_token, request.confirm, profile
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def prepare_document_child_add(
        request: PrepareChildAddInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "prepare_document_child_add",
                lambda: lifecycle.prepare_child_add(
                    request.target.model_dump(),
                    request.item.model_dump(),
                    request.qty,
                    request.rate,
                    profile,
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def confirm_document_child_add(
        request: LifecycleConfirmInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "confirm_document_child_add",
                lambda: lifecycle.confirm(
                    "child_add", request.approval_token, request.confirm, profile
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def prepare_document_child_remove(
        request: PrepareChildRemoveInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "prepare_document_child_remove",
                lambda: lifecycle.prepare_child_remove(
                    request.target.model_dump(),
                    request.child_table,
                    request.row.model_dump(),
                    profile,
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def confirm_document_child_remove(
        request: LifecycleConfirmInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "confirm_document_child_remove",
                lambda: lifecycle.confirm(
                    "child_remove", request.approval_token, request.confirm, profile
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def execute_document_update(
        request: PrepareUpdateInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "execute_document_update",
                lambda: lifecycle.execute_update(
                    request.target.model_dump(),
                    [change.model_dump() for change in request.changes],
                    profile,
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def execute_document_child_add(
        request: PrepareChildAddInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "execute_document_child_add",
                lambda: lifecycle.execute_child_add(
                    request.target.model_dump(),
                    request.item.model_dump(),
                    request.qty,
                    request.rate,
                    profile,
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def execute_document_child_remove(
        request: PrepareChildRemoveInput, ctx: Context
    ) -> LifecycleResult:
        return result_adapter.validate_python(
            execute_tool_with_context(
                ctx,
                "execute_document_child_remove",
                lambda: lifecycle.execute_child_remove(
                    request.target.model_dump(),
                    request.child_table,
                    request.row.model_dump(),
                    profile,
                ),
                rest_arguments=request.model_dump(mode="json"),
            )
        )

    def prepare(name: str, action: str):
        @mcp.tool(
            name=name,
            description=f"Prepare an exact existing-document {action} action.",
            meta=tool_meta(name),
            structured_output=True,
        )
        def tool(request: PrepareActionInput, ctx: Context) -> LifecycleResult:
            return result_adapter.validate_python(
                execute_tool_with_context(
                    ctx,
                    name,
                    lambda: getattr(lifecycle, f"prepare_{action}")(
                        request.target.model_dump(), profile
                    ),
                    rest_arguments=request.model_dump(mode="json"),
                )
            )

        tool.__name__ = name
        return tool

    def confirm_tool(name: str, action: str):
        @mcp.tool(
            name=name,
            description=f"Confirm an exact existing-document {action} action.",
            meta=tool_meta(name),
            structured_output=True,
        )
        def tool(request: LifecycleConfirmInput, ctx: Context) -> LifecycleResult:
            return result_adapter.validate_python(
                execute_tool_with_context(
                    ctx,
                    name,
                    lambda: lifecycle.confirm(
                        action, request.approval_token, request.confirm, profile
                    ),
                    rest_arguments=request.model_dump(mode="json"),
                )
            )

        tool.__name__ = name
        return tool

    def execute_tool(name: str, action: str):
        @mcp.tool(
            name=name,
            description=f"Execute an exact existing-document {action} action in direct mode.",
            meta=tool_meta(name),
            structured_output=True,
        )
        def tool(request: PrepareActionInput, ctx: Context) -> LifecycleResult:
            return result_adapter.validate_python(
                execute_tool_with_context(
                    ctx,
                    name,
                    lambda: getattr(lifecycle, f"execute_{action}")(
                        request.target.model_dump(), profile
                    ),
                    rest_arguments=request.model_dump(mode="json"),
                )
            )

        tool.__name__ = name
        return tool

    if profile != "accounts":
        mcp.tool(
            name="prepare_document_update",
            description="Prepare an exact existing-document field update without writing.",
            meta=tool_meta("prepare_document_update"),
            structured_output=True,
        )(prepare_document_update)
        mcp.tool(
            name="confirm_document_update",
            description="Apply a prepared exact existing-document field update after approval.",
            meta=tool_meta("confirm_document_update"),
            structured_output=True,
        )(confirm_document_update)
        mcp.tool(
            name="execute_document_update",
            description="Execute an exact existing-document field update in direct mode.",
            meta=tool_meta("execute_document_update"),
            structured_output=True,
        )(execute_document_update)
        mcp.tool(
            name="prepare_document_child_add",
            description="Prepare adding one resolved Item as a new row to an exact existing Draft transaction.",
            meta=tool_meta("prepare_document_child_add"),
            structured_output=True,
        )(prepare_document_child_add)
        mcp.tool(
            name="confirm_document_child_add",
            description="Apply a prepared new item row after approval.",
            meta=tool_meta("confirm_document_child_add"),
            structured_output=True,
        )(confirm_document_child_add)
        mcp.tool(
            name="execute_document_child_add",
            description="Execute adding one item row in direct mode.",
            meta=tool_meta("execute_document_child_add"),
            structured_output=True,
        )(execute_document_child_add)
    if profile in {"sales", "purchase", "all"}:
        mcp.tool(
            name="prepare_document_child_remove",
            description="Prepare removal of one exact item row from an existing Draft sales or purchase transaction.",
            meta=tool_meta("prepare_document_child_remove"),
            structured_output=True,
        )(prepare_document_child_remove)
        mcp.tool(
            name="confirm_document_child_remove",
            description="Apply a prepared item-row removal after approval.",
            meta=tool_meta("confirm_document_child_remove"),
            structured_output=True,
        )(confirm_document_child_remove)
        mcp.tool(
            name="execute_document_child_remove",
            description="Execute removing one item row in direct mode.",
            meta=tool_meta("execute_document_child_remove"),
            structured_output=True,
        )(execute_document_child_remove)
    prepare("prepare_document_submit", "submit")
    confirm_tool("confirm_document_submit", "submit")
    # Cancel/Delete public MCP exposure is temporarily disabled; retain the
    # registration block so these capabilities can be re-enabled deliberately.
    # prepare("prepare_document_cancel", "cancel")
    # confirm_tool("confirm_document_cancel", "cancel")
    # execute_tool("execute_document_cancel", "cancel")
    # prepare("prepare_document_delete", "delete")
    # confirm_tool("confirm_document_delete", "delete")
    # execute_tool("execute_document_delete", "delete")
