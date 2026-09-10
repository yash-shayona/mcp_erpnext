# Task 07C — Generic Explicit User Approval / Confirm Tool Safety

## Status

Ready for implementation after:

```text
Task 07A — MCP Tool Contract Foundation + Quotation First Migration
Task 07B — Generic Ambiguous Entity Selection Enforcement
```

Both must already be complete and passing.

---

## 1. Scope

Design and implement a reusable explicit-user-approval safety boundary for all current and future ERPNext MCP write operations.

The immediate production failure observed in LibreChat was:

```text
prepare_quotation failed / old approval token existed
        ↓
LLM itself called confirm_quotation(confirm=true)
        ↓
user had NOT explicitly approved that prepared preview
```

The expired token prevented the write in that specific run, but the architecture must not depend on token expiry for safety.

This task must solve the problem generically for:

```text
confirm_customer
confirm_item
confirm_quotation
confirm_sales_order
future confirm_sales_invoice
future confirm_payment_entry
future write-capable tools
```

Do not make this Quotation-only.

---

## 2. Core Safety Principle

The following is NOT sufficient proof of user approval:

```json
{
  "confirm": true
}
```

because that argument is model-generated.

The following is also NOT sufficient by itself:

```text
LLM says "the user approved"
LLM repeats "yes"
LLM chooses an approval token
LLM calls a second approval tool
```

A model-callable tool cannot create its own trusted approval.

Required rule:

> A write-capable `confirm_*` operation may execute only when the server can verify a trusted, user-originated approval signal bound to the exact prepared operation, exact authenticated Frappe user, and valid approval lifetime.

If the currently deployed LibreChat/MCP path cannot provide such a trusted human-originated signal, the system must fail closed rather than pretending `confirm=true` is secure approval.

---

## 3. Objective

After this task:

1. `confirm=true` alone cannot authorize an ERPNext write.
2. Approval is bound to the exact prepared payload/preview.
3. Approval is bound to the authenticated Frappe user.
4. Approval cannot be reused for a different operation.
5. Approval cannot be reused after successful consumption.
6. Expired approval cannot be used.
7. A model cannot manufacture a valid approval merely by calling another model-visible MCP tool.
8. Current and future write tools share the same generic approval boundary.
9. Frappe permissions remain authoritative at execution time.
10. Existing prepare/confirm business behavior is preserved except where required to harden authorization.
11. No real ERPNext document is created by automated tests.

---

## 4. Mandatory First Step — Inspect Current Capabilities

Before changing code, inspect the actual current repository and deployed client path.

At minimum inspect:

```text
current approval token implementation
approval token storage
approval TTL
approval user binding
prepare_* result structure
confirm_* wrappers/services
current confirm=true behavior
Task 07A contract metadata
Task 07B resolver/selection behavior
request-scoped LibreChat -> Frappe identity
MCP SDK version/capabilities
current Streamable HTTP transport
current LibreChat version/config used in this project
whether the current LibreChat version has a native human/tool confirmation mechanism
whether the MCP client can provide a trustworthy user-confirmation signal or metadata
whether MCP elicitation/user-interaction features are supported end-to-end
```

For LibreChat-specific capability verification, inspect the actual installed/local LibreChat source/config or official documentation/source appropriate to the installed version.

Do not assume a feature exists from memory.

Report the discovered approval capabilities before implementing the final mechanism.

---

## 5. Trust Boundary

Current architecture:

```text
Human User
   |
   v
LibreChat
   |
   v
LLM
   |
   v
MCP tool call
   |
   v
mcp_erpnext
   |
   v
Frappe / ERPNext
```

The LLM is NOT an approval authority.

Therefore:

```text
model-generated arguments
        !=
trusted human approval
```

The approval proof must originate from a layer where the model cannot fabricate it.

---

## 6. Preferred Approval Architecture

Use this target concept:

```text
prepare_*()
    |
    v
server validates request
    |
    v
returns preview + pending approval handle
    |
    v
Human sees exact preview
    |
    v
Trusted client/user confirmation
    |
    v
server records/grants approval
    |
    v
confirm_*()
    |
    v
server verifies:
    - approval exists
    - exact operation matches
    - exact payload/preview matches
    - exact authenticated Frappe user matches
    - approval is unexpired
    - approval is unused
    |
    v
re-check Frappe permission
    |
    v
consume approval atomically
    |
    v
perform ERPNext write
```

The exact implementation depends on what the current LibreChat + MCP SDK path actually supports.

---

## 7. Approval Strategy Selection

Choose the safest strategy actually supported by the deployed stack.

### Strategy A — Native trusted client confirmation

Prefer this if the installed LibreChat/MCP client provides a real human-confirmation gate for tool execution and the server can reliably distinguish/verify it.

Requirements:

```text
confirm/write tool requires human approval in client
model cannot bypass the gate
approval is tied to the exact pending action
server receives or can validate a trustworthy approval condition
```

Do not merely enable a visual confirmation dialog if the server still accepts direct unauthenticated/model-generated confirmation through another path.

---

### Strategy B — Trusted non-model approval endpoint/action

Use this when necessary if the client has no suitable native MCP approval proof but can invoke a separate trusted user action.

Concept:

```text
MCP prepare_* -> pending operation
Human presses Approve in trusted UI/client action
Trusted non-model path -> grant approval
MCP confirm_* -> consumes grant
```

Critical rule:

> The approval-grant action must NOT be exposed as a normal model-callable MCP tool.

Otherwise the model can approve its own write.

If this strategy requires a small client-side integration, keep it narrowly scoped to approval only.

Do not redesign LibreChat generally.

---

### Strategy C — Fail closed

If neither A nor B can be implemented safely with the current stack:

```text
do NOT weaken the rule
do NOT treat confirm=true as approval
do NOT create a fake second approval MCP tool
```

Instead:

```text
confirm_* returns APPROVAL_REQUIRED / TRUSTED_APPROVAL_UNAVAILABLE
writes remain blocked
report the exact missing client capability
```

This is an acceptable safe outcome for Task 07C.

A follow-up client-integration task can then implement the required human approval channel.

---

## 8. Forbidden Approval Designs

Do NOT implement any of these as the final security boundary:

### Forbidden A

```text
confirm_quotation(confirm=true)
```

with no trusted approval proof.

### Forbidden B

A model-visible tool:

```text
approve_quotation(...)
```

followed by:

```text
confirm_quotation(...)
```

If the LLM can call both, no human gate exists.

### Forbidden C

Trusting natural-language strings from the model such as:

```text
"yes"
"approved"
"user approved"
"please create"
```

inside tool arguments.

### Forbidden D

Trusting candidate order, model reasoning, conversation summaries, or assistant messages as approval.

### Forbidden E

An approval token that is:

```text
not user-bound
not operation-bound
reusable
not expiring
not consumed atomically
```

---

## 9. Generic Pending Operation Model

Create/refine one shared approval model for write-capable operations.

Conceptually a pending operation must be bound to:

```text
operation_id / approval_token
operation type
target tool/domain
authenticated Frappe user
prepared payload fingerprint
preview fingerprint or canonical prepared data
created_at
expires_at
approval state
consumed state
```

Do not expose sensitive internal fields unnecessarily to the model/client.

### Payload binding

A valid approval for:

```text
Customer A
Item X
Qty 2
```

must NOT authorize:

```text
Customer A
Item X
Qty 20
```

or:

```text
Customer B
Item X
Qty 2
```

or another DocType operation.

Use deterministic canonicalization/fingerprinting appropriate to the existing codebase.

Do not use Python's process-randomized `hash()` for persistent/security-sensitive fingerprints.

---

## 10. User Binding

Approval must remain bound to the same authenticated Frappe user established by the existing request-scoped identity architecture.

Example:

```text
prepare as alice@example.com
        ↓
approval belongs to alice@example.com
        ↓
confirm as bob@example.com
        ↓
reject
```

Preserve the current fail-closed identity mapping.

Never accept model-provided:

```text
frappe_user
role
run_as
user_email
```

as authority.

---

## 11. Operation Binding

Approval must include enough server-side information to distinguish:

```text
confirm_customer
confirm_item
confirm_quotation
confirm_sales_order
future confirm_sales_invoice
future confirm_payment_entry
```

A token/grant issued for one operation must not authorize another.

Test cross-tool replay explicitly.

---

## 12. One-Time Consumption

Successful approval must be one-time-use.

Required behavior:

```text
valid pending approval
    ↓
confirm starts
    ↓
approval validated
    ↓
approval consumed atomically / safely
    ↓
write happens once
```

A second confirm attempt must not repeat the write.

Inspect current transaction/concurrency behavior before choosing the consumption mechanism.

Avoid a check-then-write race where two requests can consume the same approval simultaneously.

---

## 13. Permission Re-Check

Approval does NOT replace Frappe permissions.

At actual write time:

```text
resolve authenticated Frappe user
        ↓
validate trusted approval
        ↓
re-check normal Frappe/ERPNext permission/business validation
        ↓
write
```

If permissions changed between prepare and confirm:

```text
confirm must fail according to current Frappe permissions
```

Do not cache authorization from prepare as permanent permission.

---

## 14. Preview Integrity

The human-approved preview must represent the exact operation later executed.

If data affecting the action changes between prepare and confirm, choose the safest existing-compatible behavior.

At minimum:

```text
server must not silently execute a materially different payload than the one approved
```

If the current service recalculates ERPNext values at confirm time, inspect and document which values are:

```text
user-approved inputs
server-derived values
ERPNext-calculated values
```

Do not freeze ERPNext internals incorrectly just to make a hash.

Bind the approval to the intended user-controlled operation fields and prepared server contract.

---

## 15. Tool Contract Changes

Using the Task 07A contract system, update generic confirm/write contracts.

Public confirm tools may retain compatibility fields where necessary, but:

```text
confirm=true
```

must no longer be sufficient authorization.

The public contract/documentation must clearly state:

```text
side effect = CONFIRM_WRITE
trusted explicit approval required
approval token/operation handle must be valid
```

Do not expose trusted internal approval markers that the model can simply invent.

---

## 16. Current Tool Coverage

Audit all currently registered tools.

Mandatory current write/confirm tools include the equivalents of:

```text
confirm_customer
confirm_item
confirm_quotation
confirm_sales_order
```

Use actual registry names from the repository.

Every current `CONFIRM_WRITE` tool must either:

```text
use the shared trusted approval guard
```

or:

```text
be explicitly blocked/fail-closed until migrated
```

No existing write tool may remain silently outside the approval policy.

---

## 17. Future Tool Guard

Extend the generic contract audit from Task 07A.

Required policy:

```text
Any tool classified CONFIRM_WRITE
        ↓
must declare/use the shared approval guard
        ↓
otherwise contract/architecture test fails
```

Future tools such as:

```text
confirm_sales_invoice
confirm_payment_entry
confirm_purchase_order
confirm_stock_entry
```

must inherit the same requirement automatically.

Do not rely only on naming convention if explicit side-effect metadata already exists.

---

## 18. Approval Storage

Inspect existing approval storage first.

Do not redesign storage unless required for correctness.

If current approval state is process-local/in-memory, preserve it for this task only if:

```text
existing architecture already accepts that limitation
single-process/dev behavior remains correct
tests document it
```

But clearly retain/document limitations for:

```text
multiple workers
container restart
horizontal scaling
```

Do not silently claim production durability.

A later focused task may move pending approvals to Redis/Frappe/database if needed.

---

## 19. Cancellation

If current prepare/confirm design already supports:

```text
confirm=false
cancel
decline
```

preserve it.

Cancellation must never write.

A cancelled/declined approval must not later become reusable.

Do not add elaborate workflow states unless required.

---

## 20. Expiry

Preserve current configured approval TTL unless a proven bug requires a focused fix.

Expected:

```text
prepare
    ↓
approval expires
    ↓
confirm
    ↓
CONFIRMATION_EXPIRED
```

Do not extend TTL merely to make tests easier.

---

## 21. Error Contract

Use the Task 07A safe error envelope.

Prefer existing stable codes where available.

Possible concepts:

```text
APPROVAL_REQUIRED
APPROVAL_NOT_TRUSTED
CONFIRMATION_EXPIRED
CONFIRMATION_CONSUMED
CONFIRMATION_USER_MISMATCH
CONFIRMATION_OPERATION_MISMATCH
CONFIRMATION_PAYLOAD_MISMATCH
PERMISSION_DENIED
TRUSTED_APPROVAL_UNAVAILABLE
```

Do not create duplicate codes if equivalents already exist.

Do not expose:

```text
approval storage internals
raw signatures/secrets
authorization headers
Frappe session IDs
stack traces
database details
filesystem paths
```

---

## 22. LibreChat Boundary

This task is allowed to INSPECT the installed/current LibreChat capability because that is necessary to determine whether a real human approval signal exists.

Do not make broad LibreChat changes.

If a tiny configuration/client change is absolutely required for trusted approval:

1. document it first,
2. isolate it,
3. explain why server-only enforcement is impossible,
4. do not proceed into unrelated LibreChat customization.

If the task would require a significant LibreChat patch:

```text
STOP
keep server fail-closed
report the required follow-up integration task
```

Do not hide a large client modification inside this MCP task.

---

## 23. Files / Components Allowed to Change

After inspection, changes may include equivalents of:

```text
mcp_erpnext/contracts/**
mcp_erpnext/approval/**
mcp_erpnext/services/**
mcp_erpnext/mcp_server.py
current confirm tool wrappers
current pending approval helpers
contract audit tests
approval tests
docs/architecture/**
docs/TOOLS.md generator/metadata
AGENTS.md / relevant project-agent docs
minimal LibreChat config only if a native trusted confirmation feature is verified and configuration alone is sufficient
```

Use actual repository paths.

---

## 24. Files / Components Not to Change

Do not change unrelated:

```text
Customer search semantics
Item search semantics
Task 07B ambiguity rules
Quotation pricing/business rules
Sales Order business rules
ERPNext controllers
Frappe role/permission model
OAuth/OpenID architecture
shared HTTP bearer-secret policy
request-scoped identity mapping
coordinator/sub-agent architecture
dynamic tool routing
Sales Invoice business workflow
Payment Entry business workflow
```

---

## 25. Implementation Steps

### Step 1 — Audit all write tools

Produce:

```text
tool
domain
side-effect classification
current approval mechanism
current vulnerability/bypass status
```

### Step 2 — Inspect trusted human-confirmation capability

Determine exactly what the deployed LibreChat + MCP path supports.

Classify result:

```text
A = native trusted confirmation available
B = separate trusted non-model action feasible
C = no trusted channel currently available
```

Do not continue from an assumption.

### Step 3 — Define generic approval guard

Create/refine one reusable server-side validation mechanism for all `CONFIRM_WRITE` tools.

### Step 4 — Bind pending operation

Bind approval to:

```text
Frappe user
operation type
prepared operation/payload
TTL
single-use state
```

### Step 5 — Integrate current confirm tools

Apply the same guard to all current `CONFIRM_WRITE` tools.

Do not duplicate approval logic in each domain.

### Step 6 — Fail closed where necessary

Any write path without trusted approval must reject execution.

### Step 7 — Extend contract audit

A `CONFIRM_WRITE` tool without the shared approval guard must fail architecture tests.

### Step 8 — Update docs

Update:

```text
MCP Tool Contract Standard
approval/security architecture doc
docs/TOOLS.md metadata/catalog
agent/project instructions
```

README only needs a concise security statement/link if appropriate.

### Step 9 — Run automated tests

All tests must use mocked/fake write services or transactions that cannot create real business documents.

### Step 10 — Manual dev verification

Only after automated tests pass, provide a separate manual verification plan.

Do NOT create a real ERPNext document automatically during this task.

Stop and report.

---

## 26. Tests — Approval Cannot Be Self-Granted

### A. Direct model-style confirm

Call:

```json
{
  "approval_token": "<prepared token>",
  "confirm": true
}
```

without trusted human approval.

Expected:

```text
REJECT
no ERPNext write
```

This is the most important regression test.

---

## 27. Tests — User Binding

```text
User A prepares
User B attempts confirm
```

Expected:

```text
REJECT
no write
```

Then:

```text
User A with valid trusted approval confirms
```

Expected in mocked service:

```text
allowed exactly once
```

---

## 28. Tests — Payload Binding

Prepare:

```text
Customer A
Item X
Qty 2
```

Approve it.

Attempt confirm for modified payload/operation:

```text
Qty 20
```

or equivalent tampering.

Expected:

```text
REJECT
```

---

## 29. Tests — Cross-Tool Replay

Use approval prepared for:

```text
Quotation
```

against:

```text
Customer
Item
Sales Order
```

Expected:

```text
REJECT
```

---

## 30. Tests — Replay / Double Confirm

First valid confirm:

```text
mocked write executes once
```

Second confirm with same approval:

```text
REJECT
mocked write count remains one
```

---

## 31. Tests — Expiry

Expired approval:

```text
REJECT
no write
```

Preserve current expiry code/semantics where possible.

---

## 32. Tests — Permission Change

Prepare under a permitted user.

Before mocked confirm, simulate permission revocation/denial.

Expected:

```text
trusted approval alone does not bypass Frappe permission
confirm fails
```

---

## 33. Tests — All Current Write Tools

For every current `CONFIRM_WRITE` tool:

```text
without trusted approval -> reject
wrong user -> reject
expired -> reject
cross-operation token -> reject
valid trusted approval -> reaches mocked service once
```

No real ERPNext documents.

---

## 34. Tests — Contract Guard

Create a temporary test-only `CONFIRM_WRITE` tool without the approval guard.

Expected:

```text
contract/architecture audit FAILS
```

The temporary tool must not remain in production registration.

---

## 35. Tests — 07A/07B Regressions

Run relevant existing tests for:

```text
public tool contracts
output contracts
Customer resolution
Item resolution
ambiguous selection
Quotation prepare
Sales Order prepare
HTTP transport
request-scoped identity
Frappe user mapping
```

Expected:

```text
all remain passing
```

---

## 36. Expected Test Results

```text
model-generated confirm=true alone cannot write
trusted approval is required
approval is user-bound
approval is operation-bound
approval is payload-bound
approval is expiring
approval is one-time
Frappe permissions are re-checked
all current CONFIRM_WRITE tools use the shared guard or fail closed
future unguarded write tools fail contract tests
no real ERPNext document is created in automated tests
07A/07B behavior remains intact
```

---

## 37. Acceptance Criteria

```text
[ ] trusted explicit-user-approval architecture is documented
[ ] model-generated confirm=true is not approval
[ ] current client capability was verified, not assumed
[ ] approval strategy A/B/C is explicitly reported
[ ] generic shared approval guard exists
[ ] approval is bound to authenticated Frappe user
[ ] approval is bound to operation
[ ] approval is bound to prepared payload/intention
[ ] approval expires
[ ] approval is single-use
[ ] replay is blocked
[ ] cross-tool replay is blocked
[ ] payload tampering is blocked
[ ] Frappe permissions are re-checked at write time
[ ] all current CONFIRM_WRITE tools are covered or fail closed
[ ] future unguarded CONFIRM_WRITE tools fail architecture tests
[ ] Task 07A contract rules remain passing
[ ] Task 07B ambiguity rules remain passing
[ ] no real ERPNext document was created by automated tests
```

---

## 38. Known Limitations / Boundaries

This task does not implement:

```text
coordinator agent
specialized agents
dynamic tool exposure
Sales Invoice workflow
Payment Entry workflow
Redis/distributed approval storage unless strictly required
custom general-purpose LibreChat UI
```

If the current LibreChat client cannot provide a trustworthy human-originated approval signal, the correct result is:

```text
writes safely blocked
+
exact follow-up client integration requirement documented
```

not a weaker server-side imitation of human approval.

---

## 39. Required Completion Report

After implementation, stop and report:

1. Exact files changed/created.
2. All current `CONFIRM_WRITE` tools discovered.
3. Previous approval mechanism and exact weakness.
4. Installed MCP SDK/client approval capabilities discovered.
5. Current LibreChat approval capability discovered and evidence/source used.
6. Selected strategy: A, B, or C.
7. Why that strategy is trustworthy.
8. Shared approval guard implementation.
9. Exact user-binding mechanism.
10. Exact operation-binding mechanism.
11. Exact payload/preview-binding mechanism.
12. Expiry behavior.
13. One-time-consumption behavior.
14. Concurrency/replay behavior.
15. Permission re-check behavior.
16. Actual public schema changes.
17. Contract audit changes.
18. Documentation changes.
19. Tests run and exact results.
20. Proof that direct `confirm=true` without trusted approval is rejected.
21. Proof that cross-user/cross-tool/replay attempts are rejected.
22. Confirmation that no real ERPNext business document was created by automated tests.
23. Any remaining limitation, especially multi-worker/process-local storage.
24. Whether a separate LibreChat approval integration task is still required.

Do not proceed automatically into the next task.

---

## 40. Exact Next Task

If Task 07C establishes a working trusted human approval channel:

```text
Task 07D — Quotation End-to-End LibreChat Verification
```

07D will validate the complete real flow:

```text
user prompt
-> Customer resolve
-> Item ambiguity/select if needed
-> prepare quotation
-> preview
-> explicit trusted user approval
-> confirm
-> Draft Quotation created as the mapped Frappe user
-> permission verification
```

If Task 07C ends in Strategy C because LibreChat has no trusted approval channel:

```text
Task 07C.1 — LibreChat Trusted Approval Integration
```

must come before 07D.
