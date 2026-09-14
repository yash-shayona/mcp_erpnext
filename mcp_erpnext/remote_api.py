"""Authenticated Frappe endpoint for the bounded REST backend bridge."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
from pydantic import BaseModel, ConfigDict, ValidationError

from .observability import logged_public_error
from .remote_operations import RemoteOperationError, execute_remote_operation


class _RemoteEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    profile: str
    arguments: dict[str, Any]


def _safe_error(code: str, *, level: str = "warning") -> dict[str, object]:
    """Use the shared safe-error and correlation-log convention remotely."""
    return logged_public_error(
        "remote_api",
        code,
        message="The remote ERPNext request could not be completed.",
        retryable=False,
        level=level,
    )


@frappe.whitelist(methods=["POST"])
def execute_mcp_operation(payload: str) -> dict[str, object]:
    """Run one fixed MCP operation as the Frappe API-token principal.

    Frappe's normal API-token middleware authenticates this call before this
    function is reached.  ``allow_guest`` is deliberately omitted.
    """
    if frappe.session.user in {None, "Guest", "guest"}:
        raise frappe.PermissionError
    try:
        envelope = _RemoteEnvelope.model_validate_json(payload)
        result = execute_remote_operation(
            envelope.operation, envelope.profile, envelope.arguments
        )
    except (ValidationError, RemoteOperationError):
        return _safe_error("MCP_REMOTE_REQUEST_INVALID")
    except frappe.PermissionError:
        return _safe_error("ERP_PERMISSION_DENIED")
    except Exception:
        # Keep remote exception details in the configured server log only. Do
        # not log bearer credentials, approval tokens, or operation arguments.
        return _safe_error("ERP_REQUEST_FAILED", level="exception")

    if not isinstance(result, dict):
        return _safe_error("MCP_REMOTE_RESPONSE_INVALID")

    pdf = result.pop("_pdf", None)
    if pdf is not None:
        if not isinstance(pdf, bytes):
            return _safe_error("MCP_REMOTE_RESPONSE_INVALID")
        result["_pdf_base64"] = base64.b64encode(pdf).decode("ascii")
    # Frappe serializes this dict into the normal {"message": ...} API shape.
    return result
