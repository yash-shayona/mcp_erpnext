"""Typed MCP adapters for Shayona credential email."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from ...contracts.common import NonEmptyString
from ...contracts.shayona.credential_email import (
    CredentialEmailConfirmInput,
    CredentialEmailConfirmOutput,
    CredentialEmailPrepareInput,
    CredentialEmailPrepareOutput,
    EmailNote,
    EmailSubject,
)
from ...runtime import execute_tool_with_context
from ...services.shayona import credential_email as service


def prepare_customer_service_credential_email(
    credential_name: NonEmptyString,
    recipient_email: NonEmptyString,
    subject: EmailSubject | None = None,
    additional_note: EmailNote | None = None,
    ctx: Context = None,
) -> CredentialEmailPrepareOutput:
    request = CredentialEmailPrepareInput(
        credential_name=credential_name,
        recipient_email=recipient_email,
        subject=subject,
        additional_note=additional_note,
    )
    result = execute_tool_with_context(
        ctx,
        "prepare_customer_service_credential_email",
        lambda: service.prepare_customer_service_credential_email(
            **request.model_dump()
        ),
        rest_arguments=request.model_dump(mode="json"),
    )
    return CredentialEmailPrepareOutput.model_validate(result)


def confirm_customer_service_credential_email(
    approval_token: NonEmptyString, ctx: Context = None
) -> CredentialEmailConfirmOutput:
    request = CredentialEmailConfirmInput(approval_token=approval_token)
    result = execute_tool_with_context(
        ctx,
        "confirm_customer_service_credential_email",
        lambda: service.confirm_customer_service_credential_email(
            request.approval_token
        ),
        rest_arguments=request.model_dump(mode="json"),
    )
    return CredentialEmailConfirmOutput.model_validate(result)


def register_shayona_credential_email_tools(mcp: Any) -> None:
    mcp.tool()(prepare_customer_service_credential_email)
    mcp.tool()(confirm_customer_service_credential_email)
