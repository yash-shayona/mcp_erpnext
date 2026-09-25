"""Public contract for Selling Terms and Conditions resolution."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from ..common import (
    NonEmptyString,
    PublicContractModel,
    TermsAndConditionsReference,
    ToolError,
)
from ..interaction import InteractionDirective
from ..masters.resolution import MatchType


class TermsResolutionReference(TermsAndConditionsReference):
    """A canonical Selling Terms reference plus its safe display title."""

    title: NonEmptyString | None = None


class TermsResolutionCandidate(PublicContractModel):
    reference: TermsResolutionReference
    label: NonEmptyString
    score: float


class TermsResolved(PublicContractModel):
    status: Literal["resolved"]
    doctype: Literal["Terms and Conditions"]
    reference: TermsResolutionReference
    match_type: MatchType


class TermsAmbiguous(PublicContractModel):
    status: Literal["ambiguous"]
    doctype: Literal["Terms and Conditions"]
    query: NonEmptyString
    candidates: list[TermsResolutionCandidate]
    interaction: InteractionDirective


class TermsNotFound(PublicContractModel):
    status: Literal["not_found"]
    doctype: Literal["Terms and Conditions"]
    query: NonEmptyString
    candidates: list[TermsResolutionCandidate] = Field(default_factory=list)


TermsResolutionResult = Annotated[
    TermsResolved | TermsAmbiguous | TermsNotFound | ToolError,
    Field(discriminator="status"),
]


class TermsResolutionOutput(RootModel[TermsResolutionResult]):
    """Root-shaped Selling Terms resolution result."""

    model_config = ConfigDict(json_schema_extra={"type": "object"})
