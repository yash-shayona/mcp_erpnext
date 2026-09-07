"""Shared, public-safe MCP contract primitives."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PublicContractModel(BaseModel):
    """Base model for public tool inputs and JSON-compatible outputs."""

    model_config = ConfigDict(extra="forbid")


class CustomerReference(PublicContractModel):
    """A previously resolved ERPNext Customer document."""

    doctype: Literal["Customer"]
    name: NonEmptyString


class ItemReference(PublicContractModel):
    """A previously resolved ERPNext Item document."""

    doctype: Literal["Item"]
    name: NonEmptyString


class SupplierReference(PublicContractModel):
    """A previously resolved ERPNext Supplier document."""

    doctype: Literal["Supplier"]
    name: NonEmptyString


ResolvableDoctype = Literal["Customer", "Item"]


class ToolError(PublicContractModel):
    """Safe, stable error envelope shared by public tool contracts."""

    status: Literal["error"]
    code: NonEmptyString
    message: NonEmptyString
    reference: NonEmptyString
    retryable: bool = False
