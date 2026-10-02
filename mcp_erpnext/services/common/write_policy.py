"""Shared fail-closed policy mechanics for bounded write families."""

from __future__ import annotations

from dataclasses import dataclass

from ...public_errors import definition_for
from ...settings import MCPSettings, WriteMode

_DISABLED_CODES = {
    "create": "CREATE_DISABLED",
    "update": "UPDATE_DISABLED",
    "cancel": "CANCEL_DISABLED",
    "delete": "DELETE_DISABLED",
    "email": "EMAIL_DISABLED",
}


def _family(action: str) -> str:
    return "update" if action in {"child_add", "child_remove"} else action


@dataclass(frozen=True)
class PolicyFailure:
    code: str
    message: str


def current_mode(action: str) -> WriteMode:
    """Read the current process policy each time, including at write boundaries."""
    settings = MCPSettings.from_environment()
    modes = {
        "create": settings.create_mode,
        "update": settings.update_mode,
        "cancel": settings.cancel_mode,
        "delete": settings.delete_mode,
        "email": settings.email_mode,
    }
    action = _family(action)
    try:
        return modes[action]
    except KeyError as error:
        raise ValueError(f"Unsupported write policy action: {action}") from error


def policy_failure(action: str, expected: WriteMode) -> PolicyFailure | None:
    """Return a stable denial unless the current mode exactly authorizes a path."""
    action = _family(action)
    mode = current_mode(action)
    if mode is expected:
        return None
    if mode is WriteMode.DISABLED:
        code = _DISABLED_CODES[action]
        return PolicyFailure(code, definition_for(code).message)
    if expected is WriteMode.DIRECT:
        code = "APPROVAL_REQUIRED"
        return PolicyFailure(code, definition_for(code).message)
    code = "DIRECT_EXECUTION_REQUIRED"
    return PolicyFailure(code, definition_for(code).message)


def disabled_failure(action: str) -> PolicyFailure | None:
    """Block prepare entry only when its governed write family is disabled."""
    action = _family(action)
    if current_mode(action) is not WriteMode.DISABLED:
        return None
    code = _DISABLED_CODES[action]
    return PolicyFailure(code, definition_for(code).message)


def direct_entry_failure(action: str) -> PolicyFailure | None:
    return policy_failure(action, WriteMode.DIRECT)


def approval_entry_failure(action: str) -> PolicyFailure | None:
    return policy_failure(action, WriteMode.APPROVAL_REQUIRED)


def exact_mode_failure(action: str, expected: WriteMode) -> PolicyFailure | None:
    return policy_failure(action, expected)
