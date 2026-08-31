# MCP Tool Contract Standard

Every public `mcp_erpnext` tool is an API contract for LibreChat, MCP
Inspector, coordinator agents, and future MCP clients. Its public schema must
be explicit, stable, safe to inspect, and independent from an internal service
payload.

## Public boundary

Public tool arguments use typed scalar fields, nested models, enums, and
literal DocType references. Do not expose `Any`, arbitrary dictionaries,
untyped object arrays, or untyped `**kwargs` at this boundary unless a truly
dynamic field is documented and accepted by the contract audit. A reference to
a Customer, Item, Warehouse, or another document must constrain the DocType;
do not replace it with a generic `{doctype: str, name: str}` reference.

Runtime identity is never a public argument. Frappe user/session, LibreChat
identity, authorization headers, secrets, roles, `run_as`, and MCP `Context`
remain server-controlled request state.

Every public tool also declares typed output models. Errors use the safe
`status: error`, `code`, `message`, `reference`, and `retryable` envelope.
They must not reveal stack traces, credentials, headers, database details, or
other internal state. Where the installed SDK supports it, the return models
publish the standard MCP `outputSchema`; otherwise models and serialization
tests remain mandatory and the limitation is documented.

## Operation and side-effect classes

| Operation family | Side-effect class | Rule |
| --- | --- | --- |
| Search | `READ` | Locates permitted records only. |
| Resolve | `RESOLVE` | Returns deterministic resolved, ambiguous, or not-found states; never guesses an ambiguous match. |
| Prepare | `PREPARE` | Validates and previews without the final persistent write. |
| Confirm | `CONFIRM_WRITE` | Is the write boundary and requires the declared shared server-verified approval guard. |

This metadata documents a boundary; it does not replace Frappe permissions,
record-level permissions, or approval enforcement. Each `CONFIRM_WRITE`
contract must declare an approval guard. The contract audit rejects a write tool
without one and publishes the guard classification in public metadata.

`confirm=true` is never a human approval signal. A confirm tool may write only
after its shared guard validates an authenticated, server-recorded approval
bound to the original Frappe user, site, action, prepared payload digest, TTL,
and one-time consumption. If no trusted client signal exists, the guard must
fail closed. See [Explicit User Approval Safety](MCP_EXPLICIT_USER_APPROVAL_SAFETY.md).

## Resolution and explicit selection

Resolver tools must declare and publish their supported terminal states. The
normal public states are `resolved`, `ambiguous`, `not_found`, and safe
`error`. An `ambiguous` result is terminal for that turn: a client must present
its structured candidate references, wait for an explicit user/client choice,
and revalidate that reference before calling a downstream prepare tool.

Ranking is presentation only. Neither the first candidate nor the highest
score is implicit approval. A unique exact match may resolve normally. The
current `select_resolved_candidate` operation is stateless: it rechecks the
chosen document with the resolver's filters and normal Frappe permissions; it
does not retain candidate lists, use approval tokens, or create records.

Future Warehouse, Supplier, and Link-field resolvers follow the same contract:
their candidate reference must constrain its DocType, and their explicit
selection must use the shared exact-revalidation primitive.

## Layering

```text
typed public MCP contract -> thin wrapper -> domain service -> ERPNext/Frappe
```

Wrappers may convert typed request models into an existing service payload and
convert a service result into a typed public result. They must not duplicate
ERPNext business rules, permissions, identity handling, or approval storage.
Services remain the authority for business behaviour and Frappe remains the
authority for permissions.

At the public preview boundary, normalize an ERPNext `None` to numeric `0`
only when the output contract requires a number and the absent value means
business-zero after ERPNext has applied its normal defaults and calculations
(for example, no additional discount). Keep genuinely optional fields nullable,
and return `needs_input` when a required business or commercial default cannot
be resolved safely.

## Source of truth and verification

The tool signature/return model drives the MCP schema. Contract metadata in
`mcp_erpnext/contracts/registry.py` supplies domain, operation, side-effect,
approval classification, and required write approval guard for audits and
documentation. The generic audit
checks every registered tool for a description, input schema, hidden runtime
fields, classification, and (for non-legacy tools) typed input/output contracts
and an `outputSchema`.

`scripts/generate_tool_catalog.py` generates `docs/TOOLS.md` from the actual
registered tools and this metadata. Run it after a tool change; use `--check`
in tests or CI. `tools/list` is the authoritative machine-readable schema;
README stays an overview rather than a manual schema dump.

## Future-tool definition of done

A new or changed public MCP tool is complete only when it has explicit input
and output models, a declared operation/side-effect class, a thin wrapper,
contract tests (including errors), an updated/checked catalog, and relevant
domain documentation. It must preserve Frappe-controlled permissions and any
prepare/confirm write boundary. A `CONFIRM_WRITE` tool additionally needs the
shared approval guard, rechecks of Frappe permissions at write time, and tests
proving direct model calls cannot authorize it.

For a resolver change, completion additionally requires typed terminal states,
typed candidate references, an explicit selection/revalidation path where
needed, and tests proving ambiguity cannot select the first candidate.

## Legacy migration policy

The initial legacy inventory is frozen in `FROZEN_LEGACY_TOOL_NAMES`. A focused
migration may remove an entry, but new tools must never add an exception.
Existing tools are migrated domain by domain so the guard improves public
contracts without forcing unrelated business-logic rewrites.
