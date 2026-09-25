# Task 67 - Terms and Conditions Natural-Language Resolver

## Objective

Add one read-only Sales-profile MCP capability that resolves a user's natural-language reference to an existing ERPNext `Terms and Conditions` document and returns the canonical `tc_name` reference required by the existing Quotation, Sales Order, and Sales Invoice prepare flows.

The target user experience is conversational. A user should not need to remember or type the exact ERPNext Terms document name. Examples such as `sales order terms`, `order terms`, or a reasonable typo such as `sles oder terms` must enter the resolver flow rather than forcing the LLM to invent a template name.

This task must preserve Task 66's existing defaulting rule:

1. if the user explicitly refers to a Terms template, resolve that reference first and pass the resolved canonical name as `tc_name`;
2. if the user does not mention Terms, keep the existing Company `default_selling_terms` behavior;
3. if there is no Company default, keep Terms empty;
4. never guess a Terms template merely from the transaction DocType.

## Handoff Context

Task 66 is already accepted as the baseline capability. Its implementation report states that:

- `mcp_erpnext/services/selling/terms.py` now owns the shared native selling-Terms adapter;
- Quotation, Sales Order, and standalone Sales Invoice accept explicit `tc_name` and use the frozen priority `explicit tc_name -> Company.default_selling_terms -> no Terms`;
- the Terms helper never searches or guesses template names;
- no Terms resolver, policy DocType, environment mapping, or custom Company field was added;
- MCP instructions were moved out of `mcp_server.py` into the dedicated instructions package;
- the accepted version moved from `0.0.1` to `0.1.0`.

The current worktree after Task 66 is the authoritative implementation baseline. Inspect it before editing and do not assume the pre-Task-66 archive is identical to the current source.

The previously inspected resolver architecture establishes these existing patterns:

- `mcp_erpnext/services/common/entity_resolution.py` owns permission-aware normalization, candidate ranking, exact/strong resolution, spelling-correction classification, and exact revalidation;
- Customer and Item resolvers reuse those shared primitives rather than implementing separate fuzzy logic;
- ambiguous resolution uses the shared semantic `SELECTION` interaction contract;
- `select_resolved_candidate` is the stateless exact-revalidation path for an explicit candidate selection;
- public tools are governed through `mcp_erpnext/contracts/registry.py`;
- MCP and REST must route through the same typed service behavior.

Official ERPNext `Terms and Conditions` metadata confirms that the document is named from its unique `title`, contains `disabled`, `selling`, and `buying` flags, and stores the actual Terms body separately. For this Sales capability, only enabled Selling templates are eligible resolver candidates.

## Scope

### In scope

- Add a Sales-profile read-only tool named `resolve_terms_and_conditions`.
- Resolve natural-language Terms references to the canonical ERPNext `Terms and Conditions.name` used as `tc_name`.
- Reuse the existing shared entity-resolution scoring and ambiguity semantics.
- Support bounded typo fallback when normal token/LIKE candidate retrieval finds nothing, without weakening global Customer/Item resolver behavior.
- Restrict candidates to permission-visible, enabled Selling Terms templates.
- Return only minimal reference/display metadata; do not expose the Terms body through the resolver.
- Reuse/extend the existing generic candidate-selection flow for ambiguous Terms candidates rather than creating a second selection mechanism.
- Update Sales MCP instructions so the model knows when to call the resolver and when not to call it.
- Add MCP/REST contract, registration, generated documentation, and focused tests.
- Apply the project's semantic-versioning rule for a new backward-compatible public capability.

### Out of scope

- No new Terms settings DocType.
- No `policies/` framework or Terms policy layer.
- No environment-variable Terms mapping.
- No custom fields on Company.
- No automatic Sales Order vs Sales Invoice template mapping.
- No `search_terms_and_conditions` tool unless inspection proves the existing resolver contract cannot safely provide ambiguity candidates. The intended public addition is one resolver tool.
- No Terms creation, update, rename, disable, delete, or bulk operations.
- No direct editing of the Terms body.
- No Purchase-profile Terms resolver in this task.
- No change to Task 66's Company-default behavior when the user did not mention Terms.
- No weakening of shared resolver confidence thresholds merely to force a match.
- No live business-document mutation unless separately authorized.

## Inputs / Source of Truth

Inspect these current-worktree areas before implementation:

```text
mcp_erpnext/services/common/entity_resolution.py
mcp_erpnext/services/masters/selection.py
mcp_erpnext/contracts/masters/resolution.py
mcp_erpnext/contracts/common.py
mcp_erpnext/tools/masters/selection.py
mcp_erpnext/services/selling/terms.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/remote_operations.py
mcp_erpnext/instructions/base.py
mcp_erpnext/instructions/sales.py
mcp_erpnext/tests/test_entity_selection.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_rest_backend.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_routing.py
scripts/generate_tool_catalog.py
docs/TOOLS.md
```

Also inspect the current Task 66 Terms and prepare-flow tests before editing so the new resolver is integrated without changing the accepted explicit/default behavior.

Likely new/changed focused files, subject to current-worktree verification, are:

```text
mcp_erpnext/contracts/selling/terms.py
mcp_erpnext/services/selling/terms.py
mcp_erpnext/tools/selling/terms.py
mcp_erpnext/contracts/common.py
mcp_erpnext/contracts/masters/resolution.py
mcp_erpnext/services/masters/selection.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
mcp_erpnext/instructions/sales.py
mcp_erpnext/tests/test_terms_resolution.py
mcp_erpnext/tests/test_entity_selection.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_rest_backend.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_routing.py
mcp_erpnext/__init__.py
docs/TOOLS.md
```

Do not create any listed file merely because it appears above. First verify the current post-Task-66 layout and reuse the established structure.

## Current State / Confirmed Evidence

### Existing resolver behavior

The existing shared resolver normalizes input, ranks candidates, and auto-resolves only exact or strong unambiguous matches. Low-confidence or close matches must remain ambiguous rather than being silently selected.

Normal candidate discovery is token/LIKE based before fuzzy ranking. That means a query where every meaningful token is misspelled can produce zero database candidates before the in-memory scorer gets a chance to rank anything. This task must address that Terms-specific gap without changing the generic Customer/Item resolver semantics globally.

### Existing Terms behavior

Task 66 implemented the following accepted prepare behavior:

```text
explicit valid tc_name
    -> use it and render native Terms

no explicit tc_name
    -> Company.default_selling_terms when available

no explicit tc_name and no Company default
    -> no Terms
```

That behavior is not a resolver. It assumes the canonical `tc_name` is already known when an explicit template is requested.

### ERPNext Terms metadata

For Sales resolution, an eligible candidate must be:

```text
doctype = "Terms and Conditions"
selling = 1
disabled = 0
visible to the authenticated Frappe user under normal permissions
```

The resolver must not return buying-only or disabled templates.

The resolver does not need the `terms` body to identify a candidate and must not expose that body to the model.

## Frozen Strategy / Contract

### 1. Public tool

Add exactly one new public Sales-profile tool:

```text
resolve_terms_and_conditions
```

Input:

```text
query: non-empty human-entered string
```

The input should reuse the existing generic resolution input contract where sound rather than inventing a duplicate `query` model.

### 2. Resolution states

Use the same public mental model as Customer/Item resolution:

```text
resolved
ambiguous
not_found
error
```

A resolved result must provide the canonical reference:

```text
doctype = "Terms and Conditions"
name = <canonical ERPNext document name / tc_name>
title = <safe display title, if retained by the typed contract>
```

A candidate must contain only the minimal safe reference/display values needed for selection plus the existing score field. Do not include `terms`, Jinja content, attachments, ownership metadata, or unrelated fields.

### 3. Match behavior

Use the existing shared normalization, ranking, and `match_type` semantics. Do not create a separate arbitrary fuzzy algorithm if the shared resolver primitives can be composed.

Expected behavior examples:

```text
Master: "Sales Order Terms"
Query:  "Sales Order Terms"
-> resolved / exact

Master: "Sales Order Terms"
Query:  "sales order terms"
-> resolved / exact after normalization

Master: "Sales Order Terms"
Query:  "sales order"
-> may resolve only when the existing shared strong-match and margin rules make it unambiguous

Master: "Sales Order Terms"
Query:  "sles oder terms"
-> must enter fuzzy ranking even if normal token LIKE discovery found nothing;
   resolve only if existing confidence rules permit, otherwise return candidate(s) as ambiguous

Masters:
- "Sales Order Terms"
- "Sales Order Export Terms"
Query: "sales order"
-> ambiguous when the shared confidence/margin rules do not justify one candidate
```

The resolver must never pick a low-confidence candidate simply because it is the only record scanned.

### 4. Terms-specific bounded typo fallback

Do not globally modify Customer/Item candidate discovery solely for this feature.

For Terms resolution, when normal permission-aware token/LIKE discovery returns no candidates, perform a bounded permission-aware fallback scan of eligible Selling Terms names/titles and feed those safe rows through the existing shared ranking and resolution functions.

Requirements:

- use normal Frappe permission enforcement (`ignore_permissions=False` or equivalent native default behavior);
- filter `selling=1` and `disabled=0` before ranking;
- fetch only fields required for resolution (`name` and title/display field as applicable);
- bound the scan with an explicit constant and document the boundary;
- return only the shared top candidate limit to the public contract;
- do not fetch or expose `terms` content;
- do not lower or bypass the existing shared strong-match score/margin rules;
- if the bounded fallback cannot establish a safe match, return `ambiguous` with safe candidate(s) or `not_found`, never an invented name.

If current ERPNext/Frappe source provides a more native permission-aware search API that cleanly handles this typo case, the implementer may use it instead, but the implementation report must cite the inspected source and explain why it is safer/better than the bounded fallback. Do not switch approaches based on assumption alone.

### 5. Ambiguous selection

Reuse the existing stateless `select_resolved_candidate` architecture.

Extend it only as needed so that an explicitly selected `Terms and Conditions` candidate can be revalidated with the same Sales eligibility filters:

```text
selling = 1
disabled = 0
```

The selection path must re-check current permissions and current eligibility. It must not trust a previous candidate list or process-local state.

Do not add a second Terms-specific `select_*` tool.

### 6. Interaction with prepare flows

The resolver does not modify Quotation, Sales Order, or Sales Invoice itself.

The intended orchestration is:

```text
user explicitly mentions a Terms template in natural language
    -> resolve_terms_and_conditions(query)
    -> if resolved, take reference.name
    -> call existing prepare_* with tc_name=reference.name

resolver ambiguous
    -> ask/select exactly one candidate
    -> revalidate through existing selection flow
    -> pass selected canonical name as tc_name

user does not mention Terms
    -> do not call resolver merely because the transaction is a Sales Order/Invoice
    -> existing Task 66 Company-default behavior remains authoritative
```

The existing prepare service must continue to validate the final exact `tc_name` independently. The resolver is a convenience/read capability, not an authorization bypass.

### 7. MCP instructions

Update the Sales instructions so an agent can route correctly without guessing.

The instruction must communicate, in concise operational wording:

- when the user explicitly names/describes a Terms template but the canonical ERPNext name is not already known, call `resolve_terms_and_conditions`;
- use the resolved canonical `reference.name` as `tc_name` in Quotation/Sales Order/Sales Invoice preparation;
- if ambiguous, obtain one user selection and use the existing candidate-selection flow;
- do not infer a Terms template from document type alone;
- do not call the resolver when the user did not request a Terms template; allow Task 66's Company default to operate.

Keep Sales-specific guidance in the Sales instruction module. Do not move this behavior back into `mcp_server.py`.

### 8. Profile boundary

Expose `resolve_terms_and_conditions` in the Sales profile only for this task.

Do not add it to Purchase or Accounts merely because ERPNext Terms can also be buying-enabled. Buying Terms support is a separate future capability decision.

## Allowed Changes

Allowed changes are limited to the smallest set required for:

- the typed Terms resolver contract;
- Terms resolver service behavior;
- Sales tool wrapper/registration;
- generic selected-candidate support for this one additional resolvable DocType;
- REST parity;
- Sales routing instructions;
- tests and generated tool documentation;
- the required semantic version bump.

A small shared contract extension is allowed when required to reuse `select_resolved_candidate` safely.

## Forbidden / Preserve

Preserve all of the following:

- Task 66 Terms priority and native `set_missing_terms()` behavior;
- current Quotation/Sales Order/Sales Invoice prepare/approval behavior;
- Customer, Item, and Supplier resolver behavior and thresholds;
- no `ignore_permissions=True`;
- no direct SQL for candidate discovery;
- no process-local ambiguity cache;
- no LLM-generated canonical template names;
- no exposure of the Terms body in resolver outputs;
- no Company custom fields, policy framework, or settings DocType;
- no new mutation approval path because this tool is read-only;
- no unrelated refactor of the resolver framework.

If inspection reveals that a listed preserve condition cannot be maintained, stop and document the conflict rather than silently redesigning the architecture.

## Implementation Steps

1. Inspect the post-Task-66 worktree and confirm the current Terms helper, Sales instructions, contract registry, tool registration, REST dispatch, and tests.
2. Inspect the existing Customer/Item entity-resolution and candidate-selection paths end to end.
3. Verify current runtime metadata for `Terms and Conditions` on the target development site, specifically `title`, `disabled`, `selling`, `buying`, and the document naming behavior. This check must be read-only.
4. Define the minimal typed Terms resolution reference/candidate/resolved/ambiguous/not-found/output contracts in the established contract location.
5. Implement the Terms resolver by composing shared `entity_resolution` primitives with Sales eligibility filters.
6. Add the bounded Terms-specific fallback candidate scan for the all-token-typo/no-LIKE-hit case, unless an inspected official Frappe/ERPNext native API provides a clearly better equivalent.
7. Extend the existing stateless candidate-selection contract/service so `Terms and Conditions` can be revalidated without a new selection tool.
8. Add the `resolve_terms_and_conditions` MCP wrapper and register it only in the Sales profile.
9. Add the same typed operation to REST dispatch so MCP and REST use the same service logic.
10. Add the governed `ToolContract` metadata, resolution states, and `SELECTION` interaction declaration.
11. Update Sales instructions with the frozen natural-language Terms routing rule.
12. Add focused tests and regression tests listed below.
13. Regenerate `docs/TOOLS.md` using the repository's generator and run its `--check` mode.
14. Bump the app's MINOR version according to the established project SemVer process. Based on the accepted Task 66 report, the expected transition is `0.1.0 -> 0.2.0`; if the current worktree version differs, calculate the correct MINOR bump from the actual current version and report it.
15. Produce the required implementation report with exact evidence. Do not create a Git tag or push unless separately authorized.

## Safety / Compatibility Requirements

- This is a read-only resolver; it must never write a Terms document or transaction.
- Frappe permissions must be applied to every candidate discovery and exact-selection revalidation.
- Disabled templates are ineligible.
- Buying-only templates are ineligible for this Sales-profile resolver.
- Candidate metadata returned to the model must remain minimal.
- Fuzzy resolution must fail safely: low confidence means selection/not-found, not forced selection.
- Existing exact `tc_name` prepare validation remains the final authority before a business document is prepared.
- MCP and REST must expose equivalent typed behavior.
- Tool registration must continue to be contract-governed.
- Existing Customer/Item resolver outcomes must remain regression-compatible.

## Acceptance Criteria

Task 67 is complete only when all of the following are true:

1. Sales profile exposes exactly one new resolver tool named `resolve_terms_and_conditions`.
2. Purchase and Accounts profiles do not expose that tool.
3. The tool accepts one non-empty natural-language query through the existing typed query convention.
4. Only permission-visible `Terms and Conditions` records with `selling=1` and `disabled=0` can appear as candidates or resolved references.
5. Resolver output never contains the Terms body.
6. Exact canonical input resolves to the canonical Terms reference.
7. Case/format normalization does not require an exact user spelling/casing match.
8. A normal partial phrase such as `sales order` is handled through the shared scoring rules rather than requiring the complete exact title.
9. An all-token typo case that would miss normal SQL LIKE candidate discovery still reaches bounded fuzzy ranking.
10. A typo is auto-resolved only when the existing shared confidence/margin rules justify it.
11. A low-confidence or close multi-candidate result returns `ambiguous` plus safe selectable candidates.
12. Zero eligible candidates returns `not_found`.
13. The resolver never guesses a template based solely on Quotation, Sales Order, or Sales Invoice document type.
14. `select_resolved_candidate` can statelessly revalidate a selected `Terms and Conditions` candidate with the same permission and Sales eligibility filters.
15. A selected candidate that became disabled, buying-only, deleted, or permission-invisible fails revalidation.
16. Resolved `reference.name` can be passed unchanged as the existing `tc_name` input to Quotation, Sales Order, and standalone Sales Invoice prepare flows.
17. Task 66 behavior remains unchanged when the user does not mention Terms: Company default first, otherwise no Terms.
18. Existing Customer/Item resolver tests remain green with no threshold or behavioral regression introduced for this task.
19. MCP and REST expose the same resolver semantics.
20. Tool contract metadata, registration, routing description, and generated `docs/TOOLS.md` are current.
21. Sales server instructions describe the resolver flow and explicitly forbid document-type guessing.
22. `mcp_server.py` remains instruction-body free.
23. No Terms settings DocType, policy layer, Company field, or ENV mapping is added.
24. App version is bumped by one MINOR release from the actual accepted pre-Task-67 version.

## Tests / Verification

Add focused automated tests for at least:

- exact Terms title/name resolution;
- case-insensitive/normalized exact resolution;
- safe partial natural-language resolution;
- typo query where at least one normal token still discovers candidates;
- all-token typo requiring the bounded fallback scan;
- weak single candidate returning selection rather than forced resolution when below shared confidence;
- ambiguous close candidates;
- not found;
- disabled template exclusion;
- buying-only template exclusion;
- permission-invisible template exclusion;
- candidate payload does not contain `terms`;
- Terms candidate exact revalidation through `select_resolved_candidate`;
- selected candidate becoming invalid before revalidation;
- existing Customer and Item selection regression coverage;
- Sales-only tool registration/profile exposure;
- governed tool contract/routing metadata;
- REST backend parity;
- Sales instruction routing assertions;
- existing Task 66 Terms/default tests remaining green;
- generated tool catalog current.

Run the focused suite plus the relevant existing contract/registration/profile/REST/routing tests. At minimum include the current equivalents of:

```text
mcp_erpnext.tests.test_terms_resolution
mcp_erpnext.tests.test_entity_selection
mcp_erpnext.tests.test_tool_contracts
mcp_erpnext.tests.test_tool_registration
mcp_erpnext.tests.test_rest_backend
mcp_erpnext.tests.test_profiles
mcp_erpnext.tests.test_tool_routing
mcp_erpnext.tests.test_quotation_service
mcp_erpnext.tests.test_sales_invoice
```

Also run:

```text
python scripts/generate_tool_catalog.py
python scripts/generate_tool_catalog.py --check
```

Use the repository's actual Python/bench invocation convention rather than blindly copying the command prefix above.

Do not claim live mutation coverage. Runtime verification for this task should be read-only unless separately authorized.

## Expected Results

After Task 67, a conversational client can safely execute a flow such as:

```text
User: Create the Sales Order and use sales order terms.

Agent:
1. resolves customer/item references as usual;
2. calls resolve_terms_and_conditions("sales order terms");
3. receives canonical Terms reference, for example:
   Terms and Conditions / Sales Order Terms;
4. calls prepare_sales_order(..., tc_name="Sales Order Terms");
5. existing Task 66 Terms rendering/default/approval behavior continues unchanged.
```

For ambiguity:

```text
User: use sales order terms

Candidates:
- Sales Order Terms
- Sales Order Export Terms

-> require one selection
-> revalidate selected candidate
-> pass selected canonical name as tc_name
```

For no explicit Terms request:

```text
User: Create a Sales Order for ABC.

-> do not call the Terms resolver merely because this is a Sales Order
-> Company.default_selling_terms remains the existing fallback
-> otherwise no Terms
```

## Limitations / Risks

- Natural-language resolution is intentionally conservative. Some weak typos may require user selection instead of auto-resolution.
- The bounded typo fallback cannot safely guarantee scanning an unbounded number of Terms templates. The chosen bound must be explicit, tested, and reported.
- This task resolves Selling Terms only. Purchase-profile Buying Terms are not included.
- The resolver returns the template identity, not the Terms body. The existing prepare flow remains responsible for native rendering.
- This task does not solve per-DocType default Terms policy; that remains intentionally deferred.

## Implementation Report

Create the implementation report at this exact path:

```text
docs/inspect/25-09-2026/TERMS_AND_CONDITIONS_NATURAL_LANGUAGE_RESOLVER_IMPLEMENTATION_REPORT.md
```

The report must include:

- baseline commit/worktree and pre/post app version;
- exact files changed/added;
- current runtime `Terms and Conditions` metadata evidence;
- inspected existing resolver/selection architecture and what was reused;
- exact Sales eligibility filters;
- the normal candidate-discovery path;
- the typo fallback strategy and explicit scan bound;
- public contract examples for `resolved`, `ambiguous`, and `not_found`;
- evidence that candidate payloads do not expose Terms body content;
- evidence that selected Terms candidates are statelessly revalidated;
- MCP/REST/profile/instruction changes;
- tests/commands actually run and their actual results;
- generated catalog check result;
- acceptance-criteria evidence;
- deviations from this task, if any;
- unresolved blockers/limitations;
- resulting project state;
- whether any live runtime checks were read-only or mutating;
- anything the next reviewer needs that is not obvious from the source.

Do not state `done` without this evidence.

## Handover Completeness Check

Before considering implementation complete, verify that another developer can reconstruct the resulting behavior from the source plus the Task 67 report without relying on this conversation:

- Task 66 Terms default behavior is explicitly preserved;
- the new resolver's responsibility is clear and separate from default selection;
- exact eligibility and permission boundaries are recorded;
- ambiguity/selection behavior is documented;
- the typo fallback and its bound are documented;
- MCP/REST/profile exposure is recorded;
- tests and current version are recorded;
- deferred policy/default customization remains clearly out of scope.

## Exact Next Handoff

Return only the completed Task 67 implementation report at:

```text
docs/inspect/25-09-2026/TERMS_AND_CONDITIONS_NATURAL_LANGUAGE_RESOLVER_IMPLEMENTATION_REPORT.md
```

for review against this task and the actual changed source. Do not start a Terms policy/settings task after this one unless it is separately requested.
