# 01 MCP-Level Protocol Metadata Foundation V1 — Implementation Task

## Task Type
Implementation task following inspection of the latest `mcp_erpnext` source snapshot dated 2026-09-22.

## Scope
This is a **whole-MCP implementation**, not a Quotation-only, Customer-only, Item-only, Sales-only, or single-profile change.

The implementation must apply consistently to the complete public MCP tool surface:

- Sales profile: 66 exposed tools
- Purchase profile: 21 exposed tools
- Accounts profile: 19 exposed tools
- Unique public tools across all profiles: 85
- Declared `TOOL_CONTRACTS`: 85
- Current invariant: every exposed public tool has one corresponding `ToolContract`

This task is the first foundational task in the MCP-wide tool-behavior/approval/routing hardening program.

---

# 1. Objective

Add **standard MCP protocol annotations** to every public tool across every profile, using the existing centralized `ToolContract` / `SideEffectClass` architecture as the source of truth.

The implementation must:

1. Preserve the existing profile boundaries and public tool inventories.
2. Preserve all existing business behavior.
3. Preserve existing custom `meta=tool_meta(...)` metadata.
4. Add standards-compatible tool annotations centrally rather than hand-maintaining unrelated annotation logic in every tool module.
5. Make the annotation policy testable and auditable.
6. Prevent future public tools from being registered without governed annotations.
7. Keep `prepare_*` tools semantically truthful: they must **not** be falsely marked read-only merely because they do not create/update the final ERPNext business document.
8. Establish the server-side metadata foundation required for later host policies such as `default_tools_approval_mode = "writes"`.

This task does **not** yet redesign all tool descriptions or routing instructions. That will be the next MCP-level task.

---

# 2. Source Snapshot Inspected

Use the current source as the source of truth before changing anything.

Important existing files:

- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/audit.py`
- `mcp_erpnext/mcp_server.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/profiles/sales.py`
- `mcp_erpnext/profiles/purchase.py`
- `mcp_erpnext/profiles/accounts.py`
- all registration modules under `mcp_erpnext/tools/**`
- `mcp_erpnext/tests/test_tool_contracts.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `mcp_erpnext/tests/test_profiles.py`
- `scripts/generate_tool_catalog.py`
- `docs/TOOLS.md`
- `pyproject.toml`

Current version metadata observed:

```python
__version__ = "0.0.1"
```

Do **not** change version metadata in this task unless a separate versioning decision has already been explicitly approved.

---

# 3. Current Architecture to Preserve

The current registry already classifies every public tool using:

```python
class SideEffectClass(StrEnum):
    READ = "READ"
    RESOLVE = "RESOLVE"
    PREPARE = "PREPARE"
    CONFIRM_WRITE = "CONFIRM_WRITE"
```

and every public tool has a `ToolContract`.

The current registry also publishes custom MCP metadata through:

```python
tool_meta(name)
```

which exposes fields such as:

- domain
- operation
- side_effect
- approval_required
- approval_guard
- resolution states
- interaction kinds

This existing contract registry must remain the authoritative internal policy layer.

Do not create a second unrelated classification table.

---

# 4. Required Design Principle

## 4.1 One source of truth

Standard MCP annotations must be derived from the existing `ToolContract` model.

Do not scatter manually duplicated values such as:

```python
annotations=...
```

with independent policy decisions throughout dozens of tool files.

A public tool's:

- custom metadata
- standard MCP annotations
- approval classification

must remain traceable to the same `ToolContract`.

## 4.2 Allow explicit exceptions

Some standard annotations cannot be derived only from `SideEffectClass`.

For example:

- `confirm_document_delete` is destructive.
- `confirm_document_email` interacts outside the ERPNext data store by queuing an email.
- `prepare_*` tools may create approval/pending state even though they do not write the final business document.
- not every `CONFIRM_WRITE` should automatically receive exactly the same destructive/open-world semantics.

Therefore implement:

1. safe defaults based on existing classifications; and
2. explicit per-contract overrides where semantics genuinely differ.

Do not infer dangerous/destructive semantics from tool names alone at registration time.

---

# 5. Compatibility Gate — Must Be Done Before Coding

`pyproject.toml` currently allows:

```toml
mcp>=1.0,<2.0
```

Before implementation, inspect the **actual MCP Python package API available in the project/deployment environment**.

Verify the exact supported API for FastMCP tool annotations, including:

- the annotation model/type to import;
- exact constructor field names;
- exact `FastMCP.tool(...)` keyword parameter;
- how annotations appear in `list_tools()`;
- whether field aliases are serialized as MCP camelCase fields;
- whether the installed package version is compatible with the intended implementation.

Do not guess an annotation API from memory.

If the runtime package version is not available in the coding environment, inspect the lock/install metadata or the actual environment used by the app and document the limitation.

If a package-version constraint must be tightened for correctness, stop and report it as a compatibility finding before silently changing dependency policy.

---

# 6. Annotation Policy

The implementation must define and document a clear policy for the following standard MCP hints:

- read-only
- destructive
- idempotent
- open-world

Use the exact field names/types required by the installed MCP SDK.

## 6.1 Safe defaults

The following policy is the intended starting point and must be validated against actual tool behavior.

### `SideEffectClass.READ`

Expected default:

- read-only: true
- destructive: false
- idempotent: true
- open-world: false

Examples include:

- `get_*`
- `query_*`
- `aggregate_*`
- `search_*`
- `render_document_pdf` if inspection confirms it only creates an ephemeral/non-business artifact and does not mutate durable ERPNext business state

### `SideEffectClass.RESOLVE`

Expected default:

- read-only: true
- destructive: false
- idempotent: true
- open-world: false

Examples:

- `resolve_customer`
- `resolve_item`
- `resolve_supplier`
- `select_resolved_candidate`

The implementation must verify that no resolver persists durable business state before applying this globally.

### `SideEffectClass.PREPARE`

Expected default:

- read-only: false
- destructive: false
- idempotent: false unless actual implementation proves otherwise
- open-world: false

Important:

A `prepare_*` operation must **not** be marked read-only merely because the final ERPNext business document is not written.

Current prepare flows create/maintain prepared-operation or approval state. Standard annotation semantics must reflect actual side effects, not only ERPNext document writes.

### `SideEffectClass.CONFIRM_WRITE`

Expected default:

- read-only: false
- destructive: false by default
- idempotent: false by default
- open-world: false by default

Then use explicit contract-level overrides where needed.

---

# 7. Required Explicit Semantic Review

Do not blindly map all confirms identically.

Review every `CONFIRM_WRITE` contract and explicitly classify exceptional behavior.

At minimum inspect:

## Lifecycle tools

- `confirm_document_update`
- `confirm_document_child_add`
- `confirm_document_submit`
- `confirm_document_cancel`
- `confirm_document_delete`

`confirm_document_delete` must receive explicit destructive treatment.

Review whether cancel/submit should also be marked destructive according to actual MCP annotation semantics and the real ERPNext effects. Document the decision.

## Email

- `confirm_document_email`

Review open-world semantics because the operation queues communication to an external recipient.

Do not mark the `prepare_document_email` step open-world unless it actually communicates externally.

## Accounts writes

Review all Payment Entry creation/reconciliation confirm tools.

Do not assume payment/accounting writes are "destructive" simply because they are consequential. Apply the MCP SDK's annotation meaning precisely.

## Sales/Purchase creation and conversion

Review all create/convert confirm tools.

Creation of a draft document is a write, but not automatically destructive unless the standard semantics justify that label.

---

# 8. Required Registry Changes

Preferred architectural direction:

Extend `ToolContract` so it can produce both:

```python
contract.mcp_meta()
```

and a standard MCP annotation representation.

Possible shapes include:

```python
contract.mcp_annotations()
```

or a centralized helper:

```python
tool_annotations(name)
```

The exact implementation may differ if the installed MCP SDK requires another form.

The key requirements are:

- annotation policy lives centrally;
- every contract can deterministically expose annotations;
- exceptional hints are explicit in contract policy;
- no profile-specific duplicate policy table;
- no business service module should own MCP protocol annotation logic.

---

# 9. Registration Layer Hardening

Current registration code repeatedly uses forms such as:

```python
mcp.tool(
    meta=tool_meta("prepare_quotation"),
    structured_output=True,
)(prepare_quotation)
```

The implementation should prevent future developers from forgetting standard annotations.

Prefer a centralized registration helper or centralized kwargs builder, for example conceptually:

```python
tool_registration_kwargs("prepare_quotation")
```

returning governed registration properties such as:

- `meta`
- `annotations`
- `structured_output`

The exact helper API is up to the implementation agent after inspecting all registration patterns.

It must support existing registrations that also provide:

- explicit `name=`
- explicit `description=`
- decorator syntax
- callable-wrapper syntax

Do not force a large unrelated rewrite of tool modules.

The goal is minimal, systematic MCP registration hardening.

---

# 10. Apply to the Entire Public Surface

This implementation is complete only when **every one of the 85 unique public tool contracts** receives standard annotations through the centralized policy.

Profiles covered:

## Sales

Current expected inventory: 66 tools.

## Purchase

Current expected inventory: 21 tools.

## Accounts

Current expected inventory: 19 tools.

The union of all profile inventories must remain exactly aligned with the current 85 `TOOL_CONTRACTS`, unless an existing test proves the source snapshot differs.

No profile should be skipped because the original user-visible problem was observed in Sales.

---

# 11. No Business Logic Changes

This task must not change:

- ERPNext document validation logic
- Frappe permission behavior
- resolver matching/ranking behavior
- approval-token security
- prepared-operation payload binding
- create/update/submit/cancel/delete business workflows
- Customer/Item/Supplier resolution semantics
- Payment Entry logic
- document conversion logic
- email content logic
- PDF rendering logic
- profile membership
- public tool names
- input/output contracts

If a business behavior change appears necessary, stop and report it separately.

---

# 12. Do Not Mix the Next Routing Task Into This Task

Do not use this implementation to rewrite the complete wording of all tool descriptions.

Do not yet implement the full MCP-wide tool-routing instruction policy.

Minor description changes required only to make tests or SDK registration valid are acceptable, but the dedicated global routing/description task comes next.

This separation is intentional so we can independently verify:

1. protocol/safety metadata; then
2. model tool-selection/routing behavior.

---

# 13. Tests Required

Add or update automated tests so annotation correctness becomes a permanent invariant.

## 13.1 Every exposed tool is governed

For each profile:

- retrieve the actual `list_tools()` output where possible;
- verify every exposed tool exists in `TOOL_CONTRACTS`;
- verify every exposed tool has standard annotations;
- verify no annotation field is missing due to registration drift.

Existing profile inventory tests must continue passing.

## 13.2 Registry coverage invariant

Verify:

```text
union(all profile public tool names) == set(TOOL_CONTRACTS)
```

Current inspected baseline:

```text
Sales = 66
Purchase = 21
Accounts = 19
Union = 85
TOOL_CONTRACTS = 85
```

Use actual source/runtime results rather than hardcoding only this prose.

## 13.3 Read/resolve policy

At minimum assert representative tools:

- `get_customer`
- `query_customers`
- `aggregate_customers`
- `search_customers`
- `resolve_customer`
- `resolve_item`
- `resolve_supplier`
- `get_sales_order`
- `get_payment_entry`

are published as read-only where actual implementation confirms that classification.

## 13.4 Prepare policy

Assert representative prepare tools are **not** falsely marked read-only:

- `prepare_quotation`
- `prepare_sales_order`
- `prepare_purchase_order`
- `prepare_document_update`
- `prepare_document_email`
- `prepare_sales_invoice_payment`

## 13.5 Confirm policy

Assert representative confirms are not read-only:

- `confirm_quotation`
- `confirm_sales_order`
- `confirm_purchase_order`
- `confirm_customer`
- `confirm_sales_invoice_payment`

## 13.6 Destructive exception

Assert:

- `confirm_document_delete`

has the explicitly approved destructive annotation.

Also test any other lifecycle tools classified destructive after semantic review.

## 13.7 Open-world exception

Test the final chosen open-world policy for:

- `confirm_document_email`

and ensure ordinary ERPNext internal reads/writes do not accidentally inherit it.

## 13.8 Custom metadata remains present

Existing `mcp_erpnext` custom metadata must remain intact.

For representative tools verify both layers coexist:

- custom `meta`
- standard MCP annotations

## 13.9 Registration helper tests

If a centralized registration helper is added, test that it fails loudly for an unknown/uncontracted public tool instead of registering ungoverned metadata.

## 13.10 Existing suite

Run the relevant existing tests, including at minimum:

- `test_tool_contracts.py`
- `test_tool_registration.py`
- `test_profiles.py`
- approval tests affected by imports/registration
- any new annotation-specific tests

Then run the broader project test suite if the environment supports it.

---

# 14. Documentation Changes

Update generated/manual documentation only where needed to explain the new MCP metadata layer.

At minimum document:

1. that `ToolContract` is the source of truth;
2. that public tools expose both custom project metadata and standard MCP annotations;
3. annotation policy by side-effect class;
4. exceptional destructive/open-world overrides;
5. that host approval policy is separate from server business approval.

If `scripts/generate_tool_catalog.py` is the canonical tool-catalog generator, inspect it and extend it rather than manually maintaining contradictory metadata in `docs/TOOLS.md`.

Do not manually edit generated output without updating the generator/source.

---

# 15. Acceptance Criteria

The task is accepted only if all of the following are true:

1. All Sales, Purchase, and Accounts tools are covered.
2. All 85 unique public contracts publish standard MCP annotations.
3. Profile inventories are unchanged.
4. No public tool name or request/response contract changes.
5. Existing custom `mcp_erpnext` metadata is preserved.
6. Annotation policy is centralized.
7. New public tools cannot silently bypass annotation governance.
8. READ/RESOLVE operations are accurately identified as read-only.
9. PREPARE operations are not falsely classified as read-only.
10. CONFIRM_WRITE operations are non-read-only.
11. Destructive/open-world exceptions are explicit and tested.
12. `confirm_document_delete` receives the approved destructive classification.
13. Email external-interaction classification is explicitly reviewed and tested.
14. All relevant existing tests pass.
15. New annotation-governance tests pass.
16. The implementation does not modify ERPNext business logic.
17. No profile-specific one-off annotation workaround is introduced.
18. The implementation report clearly lists all changed files and actual test commands/results.

---

# 16. Expected Result

After this task, the MCP server itself should accurately advertise tool safety/side-effect semantics across the complete MCP surface.

This establishes the correct foundation for host/client behavior such as:

```toml
default_tools_approval_mode = "writes"
```

without lying about tool behavior.

Expected conceptual behavior:

```text
READ / RESOLVE
    -> host can recognize as read-only

PREPARE
    -> server truthfully advertises state-changing preparation semantics

CONFIRM
    -> server truthfully advertises a business write

DELETE / other exceptional actions
    -> explicit destructive hint where appropriate

EMAIL SEND
    -> explicit external/open-world treatment where appropriate
```

Host approval configuration itself is **not** part of this server-code task.

---

# 17. Limitations

This task alone will not guarantee that an LLM chooses the minimum number of tools.

For example, this task does not yet prevent/model-guide:

```text
resolve_customer
-> search_customers
-> query_customers
```

That issue will be handled in the next whole-MCP task by improving:

- server instructions;
- tool-purpose wording;
- `get` / `resolve` / `search` / `query` / `aggregate` precedence;
- prepare/confirm workflow guidance;
- terminal resolution behavior;
- cross-profile routing semantics.

This task is intentionally the protocol metadata foundation first.

---

# 18. Implementation Report Required

After implementation, create:

`MCP_LEVEL_PROTOCOL_METADATA_FOUNDATION_V1_IMPLEMENTATION_REPORT.md`

The report must contain:

- summary
- files changed
- exact annotation policy
- compatibility/API findings for the installed `mcp` package
- explicit exceptions and why
- profile coverage counts
- contract coverage counts
- before/after registration architecture
- tests added
- exact test commands run
- actual test results
- any limitations
- any deferred findings
- confirmation that no business logic changed
- confirmation that public tool inventories did not change

Do not mark the task complete without the report.

---

# 19. Exact Next Task After This One

After this implementation report is reviewed and accepted, the next task will be:

**MCP-Level Tool Routing, Description & Server Instruction Governance V1**

That task will apply to the complete MCP surface and all profiles, not only Customer/Item/Quotation.

It will define clear global semantics and routing precedence for categories such as:

```text
resolve
get
search
query
aggregate
prepare
confirm
convert
lifecycle
render
email
```

and will specifically prevent unnecessary fallback/verification chains such as:

```text
resolve -> search -> query
```

when the resolver already returned a terminal result.

Do not start that next task until this protocol-metadata implementation report has been reviewed.
