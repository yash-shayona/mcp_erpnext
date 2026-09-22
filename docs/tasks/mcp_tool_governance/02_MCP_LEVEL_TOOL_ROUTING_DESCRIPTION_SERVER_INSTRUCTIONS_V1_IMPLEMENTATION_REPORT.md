# MCP-Level Tool Routing, Description & Server Instructions V1 — Implementation Report

Date: 2026-09-22

## Summary

Implemented MCP-wide, contract-governed routing descriptions and server
instructions for the complete public `mcp_erpnext` surface. `ToolContract`
remains the single source of truth: it now derives a routing role, the public
description, and published `mcp_erpnext.routing_role` metadata. The governed
registrar injects that description for every public tool, and the contract audit
rejects description or role-metadata drift.

No ERPNext business service, resolver ranking, permission rule, public tool
name, typed schema, profile membership, approval-token mechanic, or Task-01
MCP annotation policy was changed.

## Post-Task-01 source inspected

- `mcp_erpnext/contracts/registry.py`, `audit.py`, and `__init__.py`
- `mcp_erpnext/tools/registration.py`, `tools/__init__.py`, all profile modules,
  and public registration wrappers
- `mcp_erpnext/mcp_server.py`
- `scripts/generate_tool_catalog.py` and generated `docs/TOOLS.md`
- existing tool-contract, registration, profile, approval, annotation, resolver,
  and transport tests
- the Task-01 implementation report in this task folder

The actual post-Task-01 inventory is unchanged: 85 unique `TOOL_CONTRACTS` and
public tools, with Sales 66, Purchase 21, and Accounts 19.

## Files changed

- `mcp_erpnext/contracts/registry.py` — central role taxonomy, deterministic
  name/operation role derivation, routing guidance, contract-derived public
  descriptions, and routing metadata.
- `mcp_erpnext/tools/registration.py` — publishes the contract-derived
  description rather than a wrapper docstring/decorator description.
- `mcp_erpnext/contracts/audit.py` — rejects missing/drifted descriptions and
  missing routing-role metadata.
- `mcp_erpnext/mcp_server.py` — publishes one client-neutral routing policy for
  every profile while retaining response-precision guidance.
- `mcp_erpnext/contracts/__init__.py` — exports routing governance API.
- `scripts/generate_tool_catalog.py` and generated `docs/TOOLS.md` — add the
  routing policy, role column, and generated governed descriptions.
- `docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md` — documents precedence,
  resolver states, and the Supplier selection boundary.
- `mcp_erpnext/tests/test_tool_routing.py` — server, inventory, taxonomy,
  description, terminal-state, specialized workflow, and audit-drift coverage.

## Tool-role taxonomy and routing precedence

The centralized taxonomy covers `RESOLVE`, `SELECT_RESOLVED_CANDIDATE`, `GET`,
`SEARCH`, `QUERY`, `AGGREGATE`, generic `PREPARE`/`CONFIRM`, lifecycle
prepare/confirm, conversion prepare/confirm, render, and email prepare/confirm.
Generic prepares cover create preparation; conversion has its own role because
it requires an eligible exact source document.

```text
exact known reference                    -> get_*
natural-language workflow reference      -> resolve_*
  resolved                               -> reuse returned reference
  ambiguous                              -> returned candidates / applicable selection flow
  not_found                              -> ask; search only for requested alternatives
explicit browse or candidate discovery   -> search_*
structured filtering/listing             -> query_*
supported server-side metric             -> aggregate_*
consequential operation                  -> prepare -> preview/approval -> confirm
```

`select_resolved_candidate` intentionally remains limited to Customer and Item
candidates, as confirmed by its typed `ResolvableDoctype` schema. Supplier
ambiguity retains the returned candidate context; this task does not invent a
Supplier selection capability.

## Server instructions

All selected profiles now expose the same `MCP_ROUTING_INSTRUCTIONS` through
the initialized `FastMCP.instructions` property. It covers exact vs
natural-language vs discovery vs structured vs aggregate routing; resolver
terminal behavior; prepare/preview/approval/confirm sequencing; reuse of
previous results; duplicate-call avoidance; and profile/domain boundaries. The
previous response-precision policy remains appended verbatim.

## Description governance architecture

`routing_role_for_tool_name()` classifies the stable public names, with an
operation fallback only for synthetic contract-audit fixtures. `ToolContract`
combines its existing domain-specific `purpose` with role-specific operational
guidance through `routing_description()`. `GovernedMCP` always injects that
description. The audit compares the actual registered description and metadata
with the same contract-derived value, so a future local decorator/docstring
cannot silently drift.

Representative change:

| Tool | Previous public wording | Governed routing addition |
| --- | --- | --- |
| `resolve_customer` | Resolve one permitted Customer or return a terminal selection state. | Natural-language workflow lookup; `resolved` terminal; `ambiguous` candidates; `not_found` clarification/explicit alternatives. |
| `get_customer` | Retrieve selected fields from one permitted Customer by exact reference. | Exact-known-reference preference; no fuzzy discovery or query refetch. |
| `prepare_quotation_to_sales_order` | Prepare a Draft Sales Order preview from an eligible Submitted Customer Quotation. | Exact eligible source requirement and prepare -> approval -> confirm conversion sequencing. |
| `confirm_document_email` | Queue one exact prepared document email through Frappe's native Email Queue. | Only valid prepared email state after approval; not a lookup/preview tool. |

## Resolver state semantics actually found

- `resolve_customer`, `resolve_item`, and `resolve_supplier` publish
  `resolved`, `ambiguous`, `not_found`, and `error`.
- Their governed descriptions make `resolved` terminal for lookup, direct
  `ambiguous` to returned candidates/selection, and require clarification or
  explicitly requested alternative discovery after `not_found`.
- `select_resolved_candidate` publishes `resolved`, `not_found`, and `error`
  for explicit Customer/Item candidate revalidation.
- Exact-reference read/render tools retain their distinct `ok`, `not_found`,
  and `error` output states where their existing contracts declare them; this
  task did not relabel their results as resolver states.

## Validation matrix

| User intent | Expected first routing choice |
| --- | --- |
| Create a quotation for client Vertex | `resolve_customer`; reuse `resolved`, or use returned candidates after `ambiguous` |
| Create a quotation for item `domain` after resolver `not_found` | report/clarify; offer `search_items` only if alternatives are requested |
| Get Sales Order `SAL-ORD-2026-00014` | `get_sales_order` |
| Find Customers matching Vertex | `search_customers` |
| List Customers in territory X sorted by creation | `query_customers` |
| Count supported Sales Order metric | matching `aggregate_sales_orders` metric, not client-side query aggregation |
| Convert a submitted Quotation to Sales Order | `prepare_quotation_to_sales_order` -> preview/approval -> `confirm_quotation_to_sales_order` |
| Email an exact existing document | `prepare_document_email` -> preview/approval -> `confirm_document_email` |

## Tests and exact results

Passed:

```text
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest \
  mcp_erpnext.tests.test_tool_routing \
  mcp_erpnext.tests.test_tool_annotations \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_approvals
# Ran 57 tests — OK

PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python \
  scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python \
  scripts/generate_tool_catalog.py --check
# both completed successfully

git -C apps/mcp_erpnext diff --check
# passed
```

## Broader discovery result

```text
PYTHONDONTWRITEBYTECODE=1 /home/frappe/frappe-bench/env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
# Ran 426 tests — FAILED (4 errors, 1 failure)
```

The failures are the same pre-existing Task-01 baseline, with the total test
count increasing from 419 to 426 because this task adds seven routing tests:

- `test_customer_service`, `test_item_service`, `test_purchase_order_service`,
  and `test_quotation_service`: `KeyError: 'code'` while asserting
  `TRUSTED_APPROVAL_UNAVAILABLE`.
- `test_email`: received `PROFILE_MISMATCH` instead of
  `TRUSTED_APPROVAL_UNAVAILABLE`.

No new failure category was introduced, and no unrelated approval or business
logic was changed to mask this baseline.

## Task-01 and business-boundary confirmation

`test_tool_annotations`, `test_tool_contracts`, and `test_profiles` confirm
the Task-01 annotation values and existing custom metadata remain contract
derived. The complete 85-tool set and the profile counts/names remain unchanged.
Only the new additive `routing_role` metadata field is published. No business
service, resolver algorithm, permission rule, schema, or approval-token
mechanic changed.

## Limitations and deferred findings

Server instructions and descriptions guide MCP-capable models; they cannot
stop an independently acting client from calling another valid tool. No live
ERPNext write, external email delivery, or external LLM routing evaluation was
performed. The pre-existing full-discovery approval failures remain outside
this task's scope. Do not begin Task 03 until this report is reviewed and
accepted.
