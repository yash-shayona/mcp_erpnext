"""Typed public contracts for approval-bound credential email."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, RootModel, StringConstraints

from ..common import NonEmptyString, PublicContractModel, ToolError
from ..interaction import InteractionDirective

EmailSubject = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
EmailNote = Annotated[str, StringConstraints(max_length=10_000)]


class CredentialEmailPrepareInput(PublicContractModel):
    credential_name: NonEmptyString
    recipient_email: NonEmptyString
    subject: EmailSubject | None = None
    additional_note: EmailNote | None = None


class CredentialEmailConfirmInput(PublicContractModel):
    approval_token: NonEmptyString


class CredentialEmailPreview(PublicContractModel):
    credential_name: NonEmptyString
    customer: NonEmptyString
    domain_name: NonEmptyString
    credential_type: NonEmptyString
    account_name: NonEmptyString
    account_identity: str | None = None
    control_panel_url: str | None = None
    is_active: Literal[True]
    to: NonEmptyString
    cc: list[NonEmptyString]
    reply_to: NonEmptyString
    subject: NonEmptyString
    additional_note: str | None = None
    email_template: NonEmptyString


class CredentialEmailReady(PublicContractModel):
    status: Literal["ready_for_approval"]
    preview: CredentialEmailPreview
    approval_token: NonEmptyString
    expires_in_seconds: Annotated[int, Field(gt=0)]
    interaction: InteractionDirective


class CredentialEmailPrepareOutput(
    RootModel[
        Annotated[CredentialEmailReady | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}


class CredentialEmailQueued(PublicContractModel):
    status: Literal["queued"]
    credential_name: NonEmptyString
    recipient: NonEmptyString
    queue_reference: NonEmptyString | None = None
    message: NonEmptyString


class CredentialEmailConfirmOutput(
    RootModel[
        Annotated[CredentialEmailQueued | ToolError, Field(discriminator="status")]
    ]
):
    model_config = {"json_schema_extra": {"type": "object"}}
