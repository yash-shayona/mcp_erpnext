"""Server-side, process-local approval storage for controlled MCP writes."""

from __future__ import annotations

import secrets
import time
from threading import RLock
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from json import dumps
from dataclasses import dataclass
from typing import Any, Literal

from .settings import ApprovalMode


APPROVAL_TTL_SECONDS = 15 * 60
ApprovalLookup = Literal["available", "expired", "unavailable", "consumed"]
ApprovalClaim = Literal["available", "expired", "unavailable", "consumed", "not_trusted"]


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

	@property
	def expired(self) -> bool:
		return time.monotonic() - self.created_at > APPROVAL_TTL_SECONDS


class ApprovalStore:
	"""Keep short-lived prepared operations private to one local MCP process.

	The store deliberately has no MCP-callable method that grants trust. A
	transport-specific adapter may call :meth:`record_trusted_user_approval` only
	after it has independently verified a human-originated approval event. The
	adapter remains required when the server is configured for
	``trusted_human`` approval mode.
	"""

	def __init__(self, approval_mode: ApprovalMode = ApprovalMode.TRUSTED_HUMAN) -> None:
		self._approvals: dict[str, PendingApproval] = {}
		self._signing_key = secrets.token_bytes(32)
		self._lock = RLock()
		self._approval_mode = ApprovalMode(approval_mode)

	def configure_approval_mode(self, approval_mode: ApprovalMode) -> None:
		"""Set the process policy during MCP server startup, not from a tool call."""
		with self._lock:
			self._approval_mode = ApprovalMode(approval_mode)

	def _payload_digest(self, payload: dict[str, Any]) -> str:
		serialized = dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
		return hmac_new(self._signing_key, serialized, sha256).hexdigest()

	def create(self, *, action: str, site: str, user: str, payload: dict[str, Any]) -> str:
		with self._lock:
			self._prune_expired_locked()
			token = secrets.token_urlsafe(32)
			self._approvals[token] = PendingApproval(
				action=action,
				site=site,
				user=user,
				created_at=time.monotonic(),
				payload=payload,
				payload_digest=self._payload_digest(payload),
			)
			return token

	def lookup(self, token: str, *, action: str, site: str, user: str) -> tuple[PendingApproval | None, ApprovalLookup]:
		"""Validate a pending operation without granting or consuming it."""
		with self._lock:
			approval, state = self._lookup_locked(token, action=action, site=site, user=user)
			if state != "available" or approval is None:
				return approval, state
			if approval.consumed_at is not None or approval.cancelled_at is not None:
				return None, "consumed"
			return approval, "available"

	def record_trusted_user_approval(
		self, token: str, *, action: str, site: str, user: str
	) -> tuple[PendingApproval | None, ApprovalLookup]:
		"""Record an externally verified human approval for one pending operation.

		This is intentionally internal server-side plumbing, not a tool argument or
		MCP tool. Calling code must be an authenticated transport/client adapter
		which has verified the human decision and its request binding.
		"""
		with self._lock:
			approval, state = self._lookup_locked(token, action=action, site=site, user=user)
			if state != "available" or approval is None:
				return approval, state
			if approval.consumed_at is not None or approval.cancelled_at is not None:
				return None, "consumed"
			approval.trusted_at = time.monotonic()
			return approval, "available"

	def claim_for_confirm_write(
		self, token: str, *, action: str, site: str, user: str
	) -> tuple[PendingApproval | None, ApprovalClaim]:
		"""Atomically claim a policy-compliant pending operation before a final write."""
		with self._lock:
			approval, state = self._lookup_locked(token, action=action, site=site, user=user)
			if state != "available" or approval is None:
				return approval, state
			if approval.consumed_at is not None or approval.cancelled_at is not None:
				return None, "consumed"
			if self._approval_mode == ApprovalMode.TRUSTED_HUMAN and approval.trusted_at is None:
				return None, "not_trusted"
			# Consume before persistence so concurrent confirms cannot both write.
			approval.consumed_at = time.monotonic()
			return approval, "available"

	def cancel(self, token: str, *, action: str, site: str, user: str) -> None:
		"""Consume a matching pending operation after an explicit declined confirm."""
		with self._lock:
			approval, state = self._lookup_locked(token, action=action, site=site, user=user)
			if state == "available" and approval is not None and approval.consumed_at is None:
				approval.cancelled_at = time.monotonic()

	def _lookup_locked(
		self, token: str, *, action: str, site: str, user: str
	) -> tuple[PendingApproval | None, Literal["available", "expired", "unavailable"]]:
		approval = self._approvals.get(token)
		if approval is None:
			return None, "expired"
		if approval.expired:
			self._approvals.pop(token, None)
			return None, "expired"
		if approval.action != action or approval.site != site or approval.user != user:
			return None, "unavailable"
		if not compare_digest(approval.payload_digest, self._payload_digest(approval.payload)):
			self._approvals.pop(token, None)
			return None, "unavailable"
		return approval, "available"

	def prune_expired(self) -> None:
		with self._lock:
			self._prune_expired_locked()

	def _prune_expired_locked(self) -> None:
		for token, approval in list(self._approvals.items()):
			if approval.expired:
				self._approvals.pop(token, None)


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
