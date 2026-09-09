# Task 07B — Generic Ambiguous Entity Selection Enforcement

## Status

Ready for implementation after Task 07A is complete and passing.

This task must use the MCP Tool Contract Standard introduced in Task 07A.

---

## 1. Scope

Implement a reusable, deterministic ambiguity-handling architecture for ERPNext entity resolution.

The immediate production case is the LibreChat quotation flow where:

```text
search_items("Development Item")
    -> ambiguous
    -> multiple candidates returned
```

and the model incorrectly selected the first candidate itself.

This task must solve that class of problem generically for:

```text
Customer
Item
Warehouse
and future resolvable ERPNext entities
```

Do not make this a Quotation-only fix.

---

## 2. Objective

After this task:

1. An ambiguous entity result must never be silently converted into an arbitrary resolved entity by MCP orchestration rules.
2. The MCP server must expose a clear contract for:
   - resolved
   - ambiguous
   - not_found
   - error
3. Ambiguous results must contain structured candidate IDs/references suitable for UI/client selection.
4. A client/model must use an explicit candidate selection/reference to continue.
5. The architecture must work for future entity resolvers without custom one-off logic.
6. Existing Frappe permissions and ERPNext search behavior remain authoritative.
7. No write/confirmation behavior is changed in this task.

---

## 3. Inputs / Dependencies

Required completed work:

```text
Task 07A — MCP Tool Contract Foundation + Quotation First Migration
MCP Tool Contract Standard
current Customer resolver
current Item resolver
current generic link/field resolver infrastructure
existing HTTP/LibreChat request-scoped identity
existing tests
```

Before editing, inspect the actual repository and confirm:

```text
current search_* tools
current resolve_* tools
resolver service interfaces
candidate structures
existing generic Link resolver
how exact/fuzzy matching scores are produced
current tool contracts from Task 07A
existing tests for ambiguous/not_found/resolved states
```

Do not assume filenames from this task if the repository differs.

---

## 4. Core Architecture

Target flow:

```text
User says vague entity text
        |
        v
search/resolve entity
        |
        +---- resolved ----> continue
        |
        +---- not_found ---> ask/recover
        |
        +---- ambiguous ---> STOP automatic continuation
                              |
                              v
                        return candidates
                              |
                              v
                    explicit user/client selection
                              |
                              v
                    validate selected candidate
                              |
                              v
                         resolved reference
```

The critical rule is:

> `ambiguous` is a terminal resolution state for that turn until a specific candidate is explicitly selected.

The model must not infer "first candidate", "highest score", or "probably this one" as approval to continue.

---

## 5. Generic Resolution Result Contract

Use the Task 07A public contract architecture.

Create or refine reusable typed result models for entity resolution.

Conceptual states:

```text
ResolvedResult
AmbiguousResult
NotFoundResult
ResolutionError
```

### Resolved

Conceptual shape:

```json
{
  "status": "resolved",
  "doctype": "Item",
  "reference": {
    "doctype": "Item",
    "name": "SV-FRAPPE-DEVELOPMENT"
  },
  "match_type": "exact"
}
```

Existing payload field names may be preserved where compatibility requires it.

Do not unnecessarily break current clients.

### Ambiguous

Conceptual shape:

```json
{
  "status": "ambiguous",
  "doctype": "Item",
  "query": "Development Item",
  "candidates": [
    {
      "selection_id": "...",
      "reference": {
        "doctype": "Item",
        "name": "SV-FRAPPE-DEVELOPMENT"
      },
      "label": "Frappe Custom App Development",
      "score": 0.597
    }
  ]
}
```

The exact shape must follow current repository conventions.

The important requirement is that every candidate has an unambiguous value/reference that can be returned back for selection.

---

## 6. Selection Contract

Introduce a generic explicit-selection mechanism.

Choose the smallest architecture that fits the current MCP server.

Preferred conceptual approach:

```text
select_resolved_candidate
```

or an equivalent domain-neutral resolver operation.

Input concept:

```json
{
  "doctype": "Item",
  "selection_id": "...",
  "name": "SV-FRAPPE-DEVELOPMENT"
}
```

Do not require both fields if one secure, deterministic identifier is sufficient.

The implementation must inspect existing architecture before choosing the final contract.

### Important

The selection mechanism must:

```text
validate that the selected candidate actually came from the current/valid ambiguity set,
or otherwise revalidate the exact ERPNext document safely
```

It must not blindly trust arbitrary model-provided names if doing so bypasses the intended resolution step.

If the current architecture does not retain ambiguity state, use deterministic revalidation rather than introducing unnecessary server-side state.

---

## 7. Stateless vs Stateful Selection

Prefer a stateless design if possible.

Example stateless pattern:

```text
ambiguous result gives candidate reference
        ↓
client/user chooses candidate
        ↓
exact resolve call with that candidate reference/name
        ↓
server verifies exact document exists and is permitted
        ↓
resolved
```

If a stateful `selection_id` is introduced, document:

```text
storage
TTL
user binding
multi-worker implications
```

Do not add process-local state casually.

A simple deterministic exact-reference revalidation is preferred when it gives the same safety.

---

## 8. Model / Client Behavior Contract

Update the relevant agent/project documentation so future clients/agents follow:

```text
If status == "ambiguous":
    do not call downstream prepare/create tools
    do not choose a candidate automatically
    present candidates to the user/client
    wait for explicit selection
    then resolve/revalidate exact selected candidate
```

This is a client/orchestration behavior rule, but the MCP responses must make it easy to follow.

Do not implement LibreChat UI customization in this task unless the existing client already supports structured choices without source changes.

---

## 9. Downstream Prepare Tool Safety

Generic prepare tools should only accept resolved reference contracts.

Examples:

```text
prepare_quotation
prepare_sales_order
future prepare_sales_invoice
future prepare_payment_entry
```

They should not accept:

```text
raw fuzzy query
ambiguous candidate collection
search result object
unresolved label
```

Task 07A already establishes typed reference contracts.

For this task, verify the affected current prepare tools do not accidentally accept ambiguous/raw result structures.

Do not refactor unrelated domains unnecessarily.

---

## 10. Entity Coverage

### Mandatory in this task

Implement/audit:

```text
Customer
Item
```

because both are already used in current business flows.

### Generic architecture coverage

The shared mechanism must support future:

```text
Warehouse
Supplier
Address
Contact
Price List
Cost Center
Account
Project
Sales Person
and other ERPNext Link fields
```

Do not implement all these tools now.

### Existing generic Link resolver

If the project already has a generic Link resolver from earlier tasks:

```text
reuse it
do not duplicate its matching logic
```

This task should standardize its external ambiguity contract and selection behavior rather than creating another parallel resolver stack.

---

## 11. Candidate Ordering

Preserve current search/ranking behavior unless a bug is proven.

The server may rank candidates.

But:

```text
highest score != user selection
first candidate != user selection
```

Candidate ordering is presentation only.

Do not automatically resolve ambiguity merely because one candidate has the highest fuzzy score unless the existing exact-match rules legitimately classify it as `resolved`.

---

## 12. Exact Match Rules

Preserve existing exact-match semantics.

Examples:

```text
exact document name
exact item_code
exact customer name
```

may legitimately return:

```text
status = resolved
```

when the existing resolver determines that uniquely.

Do not force user confirmation for an actual unique exact match.

This task only blocks unsafe continuation from genuinely ambiguous results.

---

## 13. Error Contract

Use the Task 07A standard error envelope.

Relevant stable codes may include existing equivalents of:

```text
AMBIGUOUS_REFERENCE
INVALID_SELECTION
REFERENCE_NOT_FOUND
REFERENCE_NOT_PERMITTED
SELECTION_EXPIRED
```

Do not invent new codes if the project already has appropriate ones.

Messages should remain concise and safe.

Do not expose:

```text
stack traces
SQL
credentials
authorization headers
Frappe session IDs
internal filesystem paths
```

---

## 14. Files / Components Allowed to Change

After repository inspection, changes may include equivalents of:

```text
mcp_erpnext/contracts/**
mcp_erpnext/resolvers/**
mcp_erpnext/services/resolution/**
mcp_erpnext/mcp_server.py
current Customer resolver
current Item resolver
generic Link resolver
tests for resolution contracts
docs/architecture/**
docs/TOOLS.md generator/catalog metadata
AGENTS.md / project agent instructions
```

Change only what is necessary.

---

## 15. Files / Components Not to Change

Do not change:

```text
LibreChat source code
LibreChat authentication
OpenID/OAuth
HTTP transport
shared bearer-secret policy
request-scoped LibreChat -> Frappe identity
Frappe permission behavior
Quotation business rules
Sales Order business rules
approval token TTL
approval storage architecture
confirm_* semantics
explicit write approval policy
coordinator/sub-agent architecture
```

---

## 16. Implementation Steps

### Step 1 — Inspect

Document current:

```text
Customer resolution path
Item resolution path
generic Link resolver path
candidate structures
exact/fuzzy decision rules
public schemas
tests
```

### Step 2 — Define shared result contracts

Create/refine typed contracts for:

```text
resolved
ambiguous
not_found
error
candidate
```

Keep domain-specific references constrained.

### Step 3 — Standardize Customer

Ensure:

```text
unique exact -> resolved
multiple plausible -> ambiguous
none -> not_found
```

Ambiguous must expose explicit candidate references.

### Step 4 — Standardize Item

Apply the same contract.

Reproduce the known case:

```text
query = "Development Item"
```

It must return ambiguous candidates without silently selecting the first result.

### Step 5 — Add explicit selection/revalidation path

Implement the chosen generic mechanism.

Selected candidate must be verified before becoming a resolved reference.

### Step 6 — Verify downstream boundary

Check current prepare tools use resolved reference types and cannot directly consume ambiguous/raw search results.

### Step 7 — Update contract audit

Extend Task 07A contract audit so resolver tools must declare supported resolution states and candidate contracts.

### Step 8 — Update docs

Update:

```text
MCP Tool Contract Standard
docs/TOOLS.md generation/metadata
agent/project rule
```

Do not copy a giant manual tool list into README.

### Step 9 — Run tests

Run focused and regression tests.

Stop after successful verification.

---

## 17. Tests to Run

### A. Customer exact resolve

Input:

```text
known exact Customer
```

Expected:

```text
resolved
one exact Customer reference
no ambiguity prompt required
```

### B. Customer ambiguous

Use or create safe test fixtures producing multiple plausible customers.

Expected:

```text
status = ambiguous
multiple structured candidates
no automatic first-candidate selection
```

### C. Item exact resolve

Input:

```text
SV-FRAPPE-DEVELOPMENT
```

Expected:

```text
resolved
Item reference
```

### D. Known Item ambiguity

Input:

```text
Development Item
```

Expected:

```text
ambiguous
candidate list includes relevant development items
no downstream prepare call is made by server logic
```

### E. Explicit candidate selection

Choose one returned candidate.

Expected:

```text
candidate is revalidated
exact resolved Item reference returned
```

### F. Invalid selection

Provide an unknown/non-candidate reference.

Expected:

```text
deterministic safe error/not_found
no arbitrary fallback
```

### G. Permission isolation

If User A cannot access a record that User B can:

```text
User A must not receive/select it through resolver behavior
```

Use existing safe test infrastructure.

### H. Contract schema

Verify public MCP schemas clearly expose:

```text
resolved result fields
ambiguous candidate fields
selection/revalidation input
domain-specific reference types
```

### I. Regression

Run existing tests for:

```text
Customer
Item
Quotation
Sales Order
HTTP transport
Task 05/06 request identity
Task 07A contract audit
```

No real ERPNext business document should be created.

---

## 18. Expected Test Results

Expected:

```text
exact matches still resolve normally
ambiguous matches remain ambiguous
first candidate is never treated as implicit user selection
selected candidate is revalidated
permission filtering remains unchanged
Quotation prepare still requires resolved Customer/Item references
all Task 07A contract tests remain passing
no writes occur during resolver tests
```

---

## 19. Acceptance Criteria

```text
[ ] generic ambiguity architecture exists
[ ] architecture is not Quotation-specific
[ ] Customer follows shared resolution states
[ ] Item follows shared resolution states
[ ] `Development Item` remains ambiguous until explicit selection
[ ] candidate references are structured and reusable
[ ] explicit selected candidate is revalidated
[ ] highest-score/first candidate is not implicit approval
[ ] exact unique matches still resolve automatically
[ ] Frappe permissions remain authoritative
[ ] downstream prepare tools require resolved references
[ ] Task 07A contract audit is extended appropriately
[ ] docs/TOOLS.md/check remains current
[ ] agent/project instructions contain ambiguity rule
[ ] relevant tests pass
[ ] no real ERPNext business document is created
```

---

## 20. Known Limitations / Boundaries

This task does **not** solve:

```text
explicit user approval before ERPNext writes
confirm_* safety
approval token lifecycle redesign
LibreChat custom selection UI
coordinator/sub-agent routing
dynamic tool exposure
multi-worker approval storage
```

Structured candidate output may still be rendered as plain text by some MCP clients.

That is acceptable for this task as long as the contract is deterministic and the client can submit an explicit candidate selection.

---

## 21. Required Completion Report

After implementation, report:

1. Exact files changed.
2. Existing resolver architecture discovered.
3. Shared resolution contracts created/changed.
4. Final Customer resolved/ambiguous/not_found response shapes.
5. Final Item resolved/ambiguous/not_found response shapes.
6. Exact selection/revalidation mechanism.
7. Whether any server-side selection state was introduced.
8. How permission filtering is preserved.
9. Actual MCP schemas for affected tools.
10. Contract audit changes.
11. Documentation updates.
12. Tests run and exact results.
13. Reproduction result for `Development Item`.
14. Confirmation that no automatic first-candidate selection remains.
15. Confirmation that no write/approval behavior was changed.
16. Confirmation that no real ERPNext business document was created.

Do not continue into Task 07C automatically.

---

## 22. Exact Next Task

After Task 07B passes:

```text
Task 07C — Generic Explicit User Approval / Confirm Tool Safety
```

Task 07C must protect all current and future `confirm_*` / write-capable MCP tools, not only Quotation.
