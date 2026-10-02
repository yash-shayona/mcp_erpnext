"""Small internal seam for bounded, prepare-time runtime requirements."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RequirementStatus(StrEnum):
	"""The only outcomes a bounded runtime requirement provider may return."""

	NOT_APPLICABLE = "not_applicable"
	SATISFIED = "satisfied"
	MISSING = "missing"
	INVALID = "invalid"
	UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EffectiveRequirementContext:
	"""Prepared state and safe runtime accessors supplied to providers."""

	doctype: str
	site: str
	values: Mapping[str, Any]
	input_values: Mapping[str, Any]
	fields: Mapping[str, Any]
	get_installed_apps: Callable[[], Sequence[str]]
	get_cached_value: Callable[..., Any] | None
	get_meta: Callable[[str], Any]
	get_list: Callable[..., list[dict[str, Any]]]


@dataclass(frozen=True)
class EffectiveRequirement:
	"""One safe, user-facing description of a known runtime requirement."""

	doctype: str
	fieldname: str
	label: str
	reason: str
	guidance: str


@dataclass(frozen=True)
class RequirementResult:
	"""A provider result; values are the only payload additions it may contribute."""

	status: RequirementStatus
	requirement: EffectiveRequirement | None = None
	values: Mapping[str, Any] = field(default_factory=dict)
	reason: str | None = None


RequirementProvider = Callable[[EffectiveRequirementContext], RequirementResult]


def run_effective_requirements(
	context: EffectiveRequirementContext,
	providers: Sequence[RequirementProvider],
) -> RequirementResult:
	"""Run bounded providers and merge only their declared payload additions."""
	values: dict[str, Any] = {}
	for provider in providers:
		result = provider(context)
		if result.status in {
			RequirementStatus.MISSING,
			RequirementStatus.INVALID,
			RequirementStatus.UNAVAILABLE,
		}:
			return result
		values.update(result.values)
	return RequirementResult(status=RequirementStatus.SATISFIED, values=values)
