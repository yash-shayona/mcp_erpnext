"""Generic guard for the public MCP tool-contract standard."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .interaction import InteractionAction, InteractionKind
from .registry import FROZEN_LEGACY_TOOL_NAMES, TOOL_CONTRACTS, ToolContract

_RUNTIME_FIELD_TERMS = (
    "ctx",
    "context",
    "frappe_user",
    "frappe_session",
    "librechat_user",
    "authorization",
    "bearer",
    "run_as",
    "role",
    "credential",
    "secret",
)

_INTERACTION_CLIENT_FIELD_TERMS = (
    "librechat",
    "conversation",
    "openai",
    "gemini",
    "langgraph",
    "whatsapp",
    "message_id",
    "button",
    "component",
    "route",
)

_INTERACTION_IMPLEMENTATION_PATHS = (
    Path(__file__).with_name("interaction.py"),
    Path(__file__).parents[1] / "tools" / "masters" / "customer.py",
    Path(__file__).parents[1] / "tools" / "masters" / "item.py",
    Path(__file__).parents[1] / "tools" / "selling" / "quotation.py",
    Path(__file__).parents[1] / "tools" / "selling" / "sales_order.py",
    Path(__file__).parents[1] / "tools" / "buying" / "purchase_order.py",
)


def _has_untyped_object(schema: Any) -> bool:
    if isinstance(schema, list):
        return any(_has_untyped_object(value) for value in schema)
    if not isinstance(schema, dict):
        return False
    if (
        schema.get("type") == "object"
        and not schema.get("properties")
        and "additionalProperties" in schema
    ):
        return True
    return any(_has_untyped_object(value) for value in schema.values())


def _visible_runtime_field(schema: dict[str, Any]) -> str | None:
    for field in schema.get("properties", {}):
        if field.lower() in _RUNTIME_FIELD_TERMS:
            return field
    return None


def _declared_statuses(schema: Any) -> set[str]:
    """Collect literal status values from a generated input or output schema."""
    if isinstance(schema, list):
        return set().union(*(_declared_statuses(value) for value in schema))
    if not isinstance(schema, dict):
        return set()
    statuses = set()
    properties = schema.get("properties")
    if isinstance(properties, dict) and isinstance(properties.get("status"), dict):
        status_schema = properties["status"]
        value = status_schema.get("const")
        if isinstance(value, str):
            statuses.add(value)
        statuses.update(
            value for value in status_schema.get("enum", []) if isinstance(value, str)
        )
    for value in schema.values():
        statuses.update(_declared_statuses(value))
    return statuses


def _schema_references(schema: Any) -> set[str]:
    if isinstance(schema, list):
        return set().union(*(_schema_references(value) for value in schema))
    if not isinstance(schema, dict):
        return set()
    references = {schema["$ref"]} if isinstance(schema.get("$ref"), str) else set()
    for value in schema.values():
        references.update(_schema_references(value))
    return references


def _schema_enum_values(schema: Any) -> set[str]:
    if isinstance(schema, list):
        return set().union(*(_schema_enum_values(value) for value in schema))
    if not isinstance(schema, dict):
        return set()
    values = {value for value in schema.get("enum", []) if isinstance(value, str)}
    for value in schema.values():
        values.update(_schema_enum_values(value))
    return values


def _interaction_schema_issue(schema: Any) -> str | None:
    """Ensure a declared interaction uses the one shared client-neutral schema."""
    if not isinstance(schema, dict):
        return "typed interaction contract lacks an output schema."
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or not isinstance(
        definitions.get("InteractionDirective"), dict
    ):
        return (
            "interaction semantics do not use the shared InteractionDirective schema."
        )
    if "#/$defs/InteractionDirective" not in _schema_references(schema):
        return "interaction semantics do not reference the shared InteractionDirective schema."
    properties = definitions["InteractionDirective"].get("properties", {})
    if not {
        "required",
        "kind",
        "allowed_actions",
        "reason_code",
        "instructions",
    }.issubset(properties):
        return "shared InteractionDirective schema is incomplete."
    if any(
        term in field.lower()
        for field in properties
        for term in _INTERACTION_CLIENT_FIELD_TERMS
    ):
        return "interaction contract exposes a client-specific field."
    enum_values = _schema_enum_values(definitions)
    if not {kind.value for kind in InteractionKind}.issubset(enum_values):
        return "shared InteractionKind enum is incomplete."
    if not {action.value for action in InteractionAction}.issubset(enum_values):
        return "shared InteractionAction enum is incomplete."
    return None


def _has_natural_language_parser() -> bool:
    """Reject phrase-normalization and regex parsing in the interaction implementation."""
    for path in _INTERACTION_IMPLEMENTATION_PATHS:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "lower",
                "casefold",
            }:
                return True
            if isinstance(node.func, ast.Attribute) and isinstance(
                node.func.value, ast.Name
            ):
                if node.func.value.id == "re" and node.func.attr in {
                    "compile",
                    "match",
                    "search",
                    "fullmatch",
                }:
                    return True
    return False


def audit_tool_contracts(
    tools: Iterable[Any], contracts: dict[str, ToolContract] = TOOL_CONTRACTS
) -> list[str]:
    """Return policy violations for the registered public MCP tool inventory."""
    issues: list[str] = []
    if _has_natural_language_parser():
        issues.append(
            "Interaction implementation must not parse natural-language user intent."
        )
    registered = {tool.name: tool for tool in tools}
    undeclared = set(registered) - set(contracts)
    if undeclared:
        issues.append("Registered tools and declared contract inventory differ.")
    for name, tool in registered.items():
        contract = contracts.get(name)
        if contract is None:
            continue
        if contract.legacy != (name in FROZEN_LEGACY_TOOL_NAMES):
            issues.append(
                f"{name}: legacy status differs from the frozen legacy inventory."
            )
        if (
            contract.side_effect.value == "CONFIRM_WRITE"
            and not contract.approval_guard
        ):
            issues.append(f"{name}: CONFIRM_WRITE tool lacks a shared approval guard.")
        if not getattr(tool, "description", "").strip():
            issues.append(f"{name}: missing public description.")
        elif tool.description != contract.routing_description():
            issues.append(
                f"{name}: public description differs from its governed routing description."
            )
        input_schema = getattr(tool, "inputSchema", None)
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            issues.append(f"{name}: missing explicit input schema.")
            continue
        if runtime_field := _visible_runtime_field(input_schema):
            issues.append(
                f"{name}: runtime-only field {runtime_field!r} is model-visible."
            )
        meta = getattr(tool, "meta", None) or getattr(tool, "_meta", None) or {}
        if (
            contract.side_effect.value == "CONFIRM_WRITE"
            and meta.get("mcp_erpnext", {}).get("approval_guard")
            != contract.approval_guard
        ):
            issues.append(
                f"{name}: approval-guard classification is missing from public metadata."
            )
        if contract.legacy:
            continue
        if not contract.compliant:
            issues.append(
                f"{name}: non-legacy tool lacks explicit input or output contract models."
            )
        if _has_untyped_object(input_schema):
            issues.append(f"{name}: input schema contains an arbitrary object.")
        if not getattr(tool, "outputSchema", None):
            issues.append(
                f"{name}: typed output contract is not published as outputSchema."
            )
        if contract.interaction_kinds:
            if interaction_issue := _interaction_schema_issue(
                getattr(tool, "outputSchema", None)
            ):
                issues.append(f"{name}: {interaction_issue}")
            if meta.get("mcp_erpnext", {}).get("interaction_kinds") != [
                kind.value for kind in contract.interaction_kinds
            ]:
                issues.append(
                    f"{name}: interaction-kind metadata is missing from public metadata."
                )
        if InteractionKind.APPROVAL in contract.interaction_kinds:
            confirm_contract = contracts.get(contract.approval_confirm_tool or "")
            if (
                confirm_contract is None
                or confirm_contract.side_effect.value != "CONFIRM_WRITE"
                or not confirm_contract.approval_guard
            ):
                issues.append(
                    f"{name}: APPROVAL interaction lacks a guarded CONFIRM_WRITE counterpart."
                )
        if contract.operation.value == "RESOLVE" or contract.resolution_states:
            if not contract.resolution_states:
                issues.append(
                    f"{name}: resolver contract does not declare supported resolution states."
                )
            elif not set(contract.resolution_states).issubset(
                _declared_statuses(tool.outputSchema)
            ):
                issues.append(
                    f"{name}: output schema does not expose every declared resolution state."
                )
        meta = getattr(tool, "meta", None) or getattr(tool, "_meta", None) or {}
        annotations = getattr(tool, "annotations", None)
        if annotations is None:
            issues.append(f"{name}: missing standard MCP annotations.")
        elif annotations.model_dump() != contract.mcp_annotations().model_dump():
            issues.append(f"{name}: standard MCP annotations differ from its contract.")
        if meta.get("mcp_erpnext", {}).get("side_effect") != contract.side_effect.value:
            issues.append(
                f"{name}: side-effect classification is missing from public metadata."
            )
        if (
            meta.get("mcp_erpnext", {}).get("routing_role")
            != contract.governed_routing_role.value
        ):
            issues.append(
                f"{name}: routing-role classification is missing from public metadata."
            )
        if contract.resolution_states and meta.get("mcp_erpnext", {}).get(
            "resolution_states"
        ) != list(contract.resolution_states):
            issues.append(
                f"{name}: resolution-state metadata is missing from public metadata."
            )
    return issues
