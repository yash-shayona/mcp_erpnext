"""Validated legacy-compatible Shayona business defaults."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CONFIG_VERSION = 1
SUPPORTED_CREDENTIAL_TYPES = frozenset({"cPanel", "Domain"})
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BusinessConfigError(RuntimeError):
    public_code = "EMAIL_TEMPLATE_INVALID"


class BusinessConfigNotConfiguredError(BusinessConfigError):
    public_code = "EMAIL_TEMPLATE_NOT_CONFIGURED"


@dataclass(frozen=True)
class CredentialEmailConfig:
    email_templates: dict[str, str]
    additional_note_variable: str

    def template_for(self, credential_type: str) -> str:
        try:
            return self.email_templates[credential_type]
        except (KeyError, TypeError) as error:
            raise BusinessConfigError("Credential type is not configured.") from error


def load_business_defaults(*, frappe_module: Any) -> CredentialEmailConfig:
    """Read the deployed ``mcp_shayona.business_defaults`` namespace."""
    try:
        data = frappe_module.conf.get("mcp_shayona")
        defaults = data["business_defaults"]
        credential_email = defaults["credential_email"]
        templates = credential_email["email_templates"]
        note_variable = credential_email["additional_note_variable"]
    except (AttributeError, TypeError, KeyError) as error:
        raise BusinessConfigNotConfiguredError(
            "Business defaults are unavailable."
        ) from error
    if (
        not isinstance(data, dict)
        or not isinstance(defaults, dict)
        or defaults.get("version") != CONFIG_VERSION
        or not isinstance(credential_email, dict)
        or not isinstance(templates, dict)
        or set(templates) != SUPPORTED_CREDENTIAL_TYPES
        or not all(
            isinstance(value, str) and value.strip() for value in templates.values()
        )
        or not isinstance(note_variable, str)
        or not _IDENTIFIER.fullmatch(note_variable)
    ):
        raise BusinessConfigError("Business defaults are invalid.")
    return CredentialEmailConfig(
        email_templates={key: value.strip() for key, value in templates.items()},
        additional_note_variable=note_variable,
    )
