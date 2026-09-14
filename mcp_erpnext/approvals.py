"""Shared Frappe-cache approval storage for controlled MCP writes."""

from __future__ import annotations

import pickle
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from json import dumps
from typing import TYPE_CHECKING, Any, Literal, Protocol

import frappe
from redis.exceptions import WatchError

from .settings import ApprovalMode

if TYPE_CHECKING:
    from collections.abc import Callable

APPROVAL_TTL_SECONDS = 15 * 60
ApprovalLookup = Literal["available", "expired", "unavailable", "consumed"]
ApprovalClaim = Literal[
    "available", "expired", "unavailable", "consumed", "not_trusted"
]


class ApprovalBackendError(RuntimeError):
    """The shared authorization backend could not provide a certain result."""


class ApprovalBackend(Protocol):
    """Private raw-record operations; production has no in-memory fallback."""

    def create(self, token: str, value: bytes, ttl_seconds: int) -> bool: ...

    def read(self, token: str) -> tuple[bytes | None, int | None]: ...

    def compare_and_set(
        self, token: str, expected: bytes, value: bytes, ttl_milliseconds: int
    ) -> bool: ...


class FrappeApprovalBackend:
    """Use the initialized Frappe RedisWrapper without local-cache helpers."""

    _KEY_PREFIX = "mcp_erpnext:approval:"

    @classmethod
    def key_name(cls, token: str) -> str:
        # Redis key inspection must not reveal the bearer-like public token.
        return f"{cls._KEY_PREFIX}{sha256(token.encode('utf-8')).hexdigest()}"

    def _key(self, token: str):
        # ``make_key`` keeps Frappe's configured database/site namespace.
        if not getattr(frappe.local, "site", None):
            raise ApprovalBackendError("Approval storage is unavailable.")
        try:
            return frappe.cache.make_key(self.key_name(token), shared=False)
        except Exception as error:
            raise ApprovalBackendError("Approval storage is unavailable.") from error

    def create(self, token: str, value: bytes, ttl_seconds: int) -> bool:
        try:
            return bool(
                frappe.cache.set(self._key(token), value, ex=ttl_seconds, nx=True)
            )
        except Exception as error:
            raise ApprovalBackendError("Approval storage is unavailable.") from error

    def read(self, token: str) -> tuple[bytes | None, int | None]:
        try:
            key = self._key(token)
            value = frappe.cache.get(key)
            if value is None:
                return None, None
            remaining = frappe.cache.pttl(key)
            if remaining <= 0:
                return None, None
            return value, remaining
        except Exception as error:
            raise ApprovalBackendError("Approval storage is unavailable.") from error

    def compare_and_set(
        self, token: str, expected: bytes, value: bytes, ttl_milliseconds: int
    ) -> bool:
        key = self._key(token)
        try:
            with frappe.cache.pipeline() as pipeline:
                pipeline.watch(key)
                if pipeline.get(key) != expected:
                    pipeline.unwatch()
                    return False
                # Preserve the original key lifetime rather than refreshing it.
                pipeline.multi()
                pipeline.set(key, value, px=ttl_milliseconds)
                pipeline.execute()
                return True
        except WatchError:
            return False
        except Exception as error:
            raise ApprovalBackendError("Approval storage is unavailable.") from error


@dataclass
class PendingApproval:
    """One private prepared operation and its server-controlled approval state."""

    action: str
    site: str
    user: str
    created_at: float
    payload: dict[str, Any]
    payload_digest: str
    trusted_at: float | None = None
    consumed_at: float | None = None
    cancelled_at: float | None = None


class ApprovalStore:
    """Authorize one-shot writes through Frappe's shared Redis cache.

    The store deliberately has no MCP-callable method that grants trust. A
    transport-specific adapter may call :meth:`record_trusted_user_approval` only
    after it has independently verified a human-originated approval event.
    """

    def __init__(
        self,
        approval_mode: ApprovalMode = ApprovalMode.AGENT_DELEGATED,
        *,
        backend: ApprovalBackend | None = None,
    ) -> None:
        self._approval_mode = ApprovalMode(approval_mode)
        self._backend: ApprovalBackend = backend or FrappeApprovalBackend()

    def configure_approval_mode(self, approval_mode: ApprovalMode) -> None:
        """Set the process policy during MCP server startup, not from a tool call."""
        self._approval_mode = ApprovalMode(approval_mode)

    @staticmethod
    def _payload_digest(payload: dict[str, Any]) -> str:
        """Return a process-stable digest for trusted internal Redis records.

        This detects payload corruption and preserves cross-worker binding. It is
        intentionally not a MAC: Frappe Redis is the trusted server-side cache
        boundary for this ephemeral authorization state.
        """
        serialized = dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return sha256(serialized).hexdigest()

    @staticmethod
    def _serialize(approval: PendingApproval) -> bytes:
        return pickle.dumps(approval, protocol=5)

    @staticmethod
    def _deserialize(value: bytes) -> PendingApproval:
        try:
            approval = pickle.loads(value)
        except Exception as error:
            raise ApprovalBackendError("Approval storage is unavailable.") from error
        if not isinstance(approval, PendingApproval):
            raise ApprovalBackendError("Approval storage is unavailable.")
        return approval

    def create(
        self, *, action: str, site: str, user: str, payload: dict[str, Any]
    ) -> str:
        """Persist a new approval before returning its opaque public token."""
        for _attempt in range(3):
            token = secrets.token_urlsafe(32)
            approval = PendingApproval(
                action=action,
                site=site,
                user=user,
                created_at=time.time(),
                payload=payload,
                payload_digest=self._payload_digest(payload),
            )
            if self._backend.create(
                token, self._serialize(approval), APPROVAL_TTL_SECONDS
            ):
                return token
        raise ApprovalBackendError("Approval storage is unavailable.")

    def lookup(
        self, token: str, *, action: str, site: str, user: str
    ) -> tuple[PendingApproval | None, ApprovalLookup]:
        """Validate shared state without granting or consuming it."""
        approval, _raw, state = self._read_and_validate(
            token, action=action, site=site, user=user
        )
        if state != "available" or approval is None:
            return None, state
        if approval.consumed_at is not None or approval.cancelled_at is not None:
            return None, "consumed"
        return approval, "available"

    def record_trusted_user_approval(
        self, token: str, *, action: str, site: str, user: str
    ) -> tuple[PendingApproval | None, ApprovalLookup]:
        """Atomically record a separately verified human decision."""
        return self._transition(
            token,
            action=action,
            site=site,
            user=user,
            transition=lambda approval: setattr(approval, "trusted_at", time.time()),
            require_trusted=False,
        )

    def claim_for_confirm_write(
        self, token: str, *, action: str, site: str, user: str
    ) -> tuple[PendingApproval | None, ApprovalClaim]:
        """Atomically claim a policy-compliant shared operation before a write."""
        return self._transition(
            token,
            action=action,
            site=site,
            user=user,
            transition=lambda approval: setattr(approval, "consumed_at", time.time()),
            require_trusted=True,
        )

    def cancel(self, token: str, *, action: str, site: str, user: str) -> None:
        """Atomically mark a matching pending operation as declined."""
        self._transition(
            token,
            action=action,
            site=site,
            user=user,
            transition=lambda approval: setattr(approval, "cancelled_at", time.time()),
            require_trusted=False,
        )

    def _transition(
        self,
        token: str,
        *,
        action: str,
        site: str,
        user: str,
        transition: Callable[[PendingApproval], None],
        require_trusted: bool,
    ) -> tuple[PendingApproval | None, ApprovalClaim]:
        approval, raw, state = self._read_and_validate(
            token, action=action, site=site, user=user
        )
        if state != "available" or approval is None or raw is None:
            return None, state
        if approval.consumed_at is not None or approval.cancelled_at is not None:
            return None, "consumed"
        if (
            require_trusted
            and self._approval_mode == ApprovalMode.TRUSTED_HUMAN
            and approval.trusted_at is None
        ):
            return None, "not_trusted"
        try:
            _value, remaining_ms = self._backend.read(token)
        except ApprovalBackendError:
            return None, "unavailable"
        if remaining_ms is None or remaining_ms <= 0:
            return None, "expired"
        transition(approval)
        try:
            if not self._backend.compare_and_set(
                token, raw, self._serialize(approval), remaining_ms
            ):
                # A concurrent success is observed as consumed on a safe reread;
                # other conflicts fail closed without consuming the original.
                current, _current_raw, current_state = self._read_and_validate(
                    token, action=action, site=site, user=user
                )
                if (
                    current_state == "available"
                    and current is not None
                    and (
                        current.consumed_at is not None
                        or current.cancelled_at is not None
                    )
                ):
                    return None, "consumed"
                if current_state == "available":
                    return None, "unavailable"
                return None, current_state
        except ApprovalBackendError:
            return None, "unavailable"
        return approval, "available"

    def _read_and_validate(
        self, token: str, *, action: str, site: str, user: str
    ) -> tuple[PendingApproval | None, bytes | None, ApprovalLookup]:
        try:
            raw, remaining_ms = self._backend.read(token)
            if raw is None or remaining_ms is None or remaining_ms <= 0:
                return None, None, "expired"
            approval = self._deserialize(raw)
        except ApprovalBackendError:
            return None, None, "unavailable"
        if approval.action != action or approval.site != site or approval.user != user:
            return None, raw, "unavailable"
        if not compare_digest(
            approval.payload_digest, self._payload_digest(approval.payload)
        ):
            return None, raw, "unavailable"
        return approval, raw, "available"

    def prune_expired(self) -> None:
        """Compatibility no-op: Redis key expiry owns shared approval cleanup."""


approvals = ApprovalStore()


def confirmation_failure(state: ApprovalClaim, subject: str) -> tuple[str, str, bool]:
    """Map shared approval-guard states to the safe public error envelope."""
    if state == "expired":
        return (
            "CONFIRMATION_EXPIRED",
            f"This {subject} confirmation has expired. Please prepare it again.",
            True,
        )
    if state == "consumed":
        return (
            "CONFIRMATION_CONSUMED",
            f"This {subject} confirmation has already been used or declined. Please prepare it again.",
            False,
        )
    if state == "not_trusted":
        return (
            "TRUSTED_APPROVAL_UNAVAILABLE",
            f"A server-verified human approval is required before this {subject} can be created.",
            False,
        )
    return (
        "CONFIRMATION_UNAVAILABLE",
        f"This {subject} confirmation is not available in the current session.",
        False,
    )
