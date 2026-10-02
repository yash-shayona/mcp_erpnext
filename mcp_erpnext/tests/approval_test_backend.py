"""Test-only shared backend for ApprovalStore unit and service tests."""

from __future__ import annotations

import time
from threading import Lock

from mcp_erpnext.approvals import ApprovalBackendError, ApprovalStore, PendingApproval


class FakeSharedApprovalBackend:
    """Small raw-value model of Redis TTL and compare-and-set semantics."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[bytes, float]] = {}
        self._lock = Lock()
        self.fail_create = False
        self.fail_read = False
        self.fail_compare_and_set = False
        self.force_conflict = False

    def create(self, token: str, value: bytes, ttl_seconds: int) -> bool:
        if self.fail_create:
            raise ApprovalBackendError("backend unavailable")
        with self._lock:
            if token in self._values:
                return False
            self._values[token] = (value, time.monotonic() + ttl_seconds)
            return True

    def read(self, token: str) -> tuple[bytes | None, int | None]:
        if self.fail_read:
            raise ApprovalBackendError("backend unavailable")
        with self._lock:
            value = self._values.get(token)
            if value is None:
                return None, None
            raw, expires_at = value
            remaining_ms = int((expires_at - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                self._values.pop(token, None)
                return None, None
            return raw, remaining_ms

    def compare_and_set(
        self, token: str, expected: bytes, value: bytes, ttl_milliseconds: int
    ) -> bool:
        if self.fail_compare_and_set:
            raise ApprovalBackendError("backend unavailable")
        with self._lock:
            current = self._values.get(token)
            if self.force_conflict or current is None or current[0] != expected:
                return False
            self._values[token] = (
                value,
                time.monotonic() + ttl_milliseconds / 1000,
            )
            return True

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def is_empty(self) -> bool:
        with self._lock:
            return not self._values

    def replace(self, token: str, value: bytes, ttl_seconds: int) -> None:
        """Test-only corruption/expiry setup without a production memory store."""
        with self._lock:
            self._values[token] = (value, time.monotonic() + ttl_seconds)


def install_fake_backend(store: ApprovalStore) -> FakeSharedApprovalBackend:
    backend = FakeSharedApprovalBackend()
    store._backend = backend
    return backend


def read_record(store: ApprovalStore, token: str) -> PendingApproval:
    raw, _remaining_ms = store._backend.read(token)
    assert raw is not None
    return store._deserialize(raw)


def replace_record(
    store: ApprovalStore,
    backend: FakeSharedApprovalBackend,
    token: str,
    record: PendingApproval,
    *,
    ttl_seconds: int = 900,
) -> None:
    backend.replace(token, store._serialize(record), ttl_seconds)


def mutate_record(
    store: ApprovalStore,
    backend: FakeSharedApprovalBackend,
    token: str,
    mutation,
    *,
    ttl_seconds: int = 900,
) -> None:
    record = read_record(store, token)
    mutation(record)
    replace_record(store, backend, token, record, ttl_seconds=ttl_seconds)
