"""Public contract for Payment Terms Template resolution."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import (
    NonEmptyString,
    PaymentTermsTemplateReference,
    PublicContractModel,
    ToolError,
)
from ..interaction import InteractionDirective
from ..masters.resolution import MatchType


class PaymentTermsResolutionReference(PaymentTermsTemplateReference):
    template_name: NonEmptyString | None = None


class PaymentTermsResolutionCandidate(PublicContractModel):
    reference: PaymentTermsResolutionReference
    label: NonEmptyString
    score: float


class PaymentTermsResolved(PublicContractModel):
    status: Literal["resolved"]
    doctype: Literal["Payment Terms Template"]
    reference: PaymentTermsResolutionReference
    match_type: MatchType


class PaymentTermsAmbiguous(PublicContractModel):
    status: Literal["ambiguous"]
    doctype: Literal["Payment Terms Template"]
    query: NonEmptyString
    candidates: list[PaymentTermsResolutionCandidate]
    interaction: InteractionDirective


class PaymentTermsNotFound(PublicContractModel):
    status: Literal["not_found"]
    doctype: Literal["Payment Terms Template"]
    query: NonEmptyString
    candidates: list[PaymentTermsResolutionCandidate] = Field(default_factory=list)


PaymentTermsResolutionResult = Annotated[
    PaymentTermsResolved | PaymentTermsAmbiguous | PaymentTermsNotFound | ToolError,
    Field(discriminator="status"),
]


class PaymentTermsResolutionOutput(RootModel[PaymentTermsResolutionResult]):
    model_config = ConfigDict(json_schema_extra={"type": "object"})
