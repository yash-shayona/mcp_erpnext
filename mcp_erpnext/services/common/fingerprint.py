"""Canonical hashing for approval-bound, business-state projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

_MISSING = object()


def _canonicalize(
    value: Any, path: tuple[str, ...], ignored_paths: set[tuple[str, ...]]
) -> Any:
    if path in ignored_paths:
        return _MISSING
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value, key=str):
            child = _canonicalize(value[key], (*path, str(key)), ignored_paths)
            if child is not _MISSING:
                result[str(key)] = child
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for index, item in enumerate(value):
            child = _canonicalize(item, (*path, str(index)), ignored_paths)
            if child is not _MISSING:
                result.append(child)
        return result
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def stable_fingerprint(
    value: Any, *, ignored_paths: set[tuple[str, ...]] | None = None
) -> str:
    """Hash a canonical projection while excluding only declared paths.

    Mapping keys are ordered and date/decimal values are normalized. Collection
    order is preserved because row order can be material to native documents.
    Callers must explicitly declare any proven non-business runtime paths.
    """

    canonical = _canonicalize(value, (), ignored_paths or set())
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
