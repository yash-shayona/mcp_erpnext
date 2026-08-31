"""Server-side, process-local approval storage for controlled MCP writes."""

from __future__ import annotations

import secrets
import time
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from json import dumps
from dataclasses import dataclass
from typing import Any, Literal


APPROVAL_TTL_SECONDS = 15 * 60
ApprovalLookup = Literal["available", "expired", "unavailable"]


@dataclass
class PendingApproval:
	"""A preview that may be confirmed only by its original site, user, and action."""

	action: str
	site: str
	user: str
	created_at: float
	payload: dict[str, Any]
	payload_digest: str
	result_document: str | None = None

	@property
	def expired(self) -> bool:
		return time.monotonic() - self.created_at > APPROVAL_TTL_SECONDS


class ApprovalStore:
	"""Keep short-lived approvals private to one local MCP process."""

	def __init__(self) -> None:
		self._approvals: dict[str, PendingApproval] = {}
		self._signing_key = secrets.token_bytes(32)

	def _payload_digest(self, payload: dict[str, Any]) -> str:
		serialized = dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
		return hmac_new(self._signing_key, serialized, sha256).hexdigest()

	def create(self, *, action: str, site: str, user: str, payload: dict[str, Any]) -> str:
		self.prune_expired()
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
		for token, approval in list(self._approvals.items()):
			if approval.expired:
				self._approvals.pop(token, None)


approvals = ApprovalStore()
