# Task 39 — Implement Frappe-Native Shared ApprovalStore

## Status

**Type:** Focused implementation task  
**Project:** `mcp_erpnext`  
**Depends on:** Task 38 — Shared Approval Store / Frappe Cache Architecture Audit  
**Audit report:** `docs/inspect/SHARED_APPROVAL_STORE_FRAPPE_CACHE_AUDIT.md`  
**Primary area:** Approval / confirmation state persistence and atomic claim  
**Public MCP contract changes:** Forbidden  
**Redis infrastructure changes:** Forbidden  
**Database / DocType changes:** Forbidden

---

# 0. Task-number verification and source authority

This task is **Task 39**.

The current repository already contains:

```text
docs/tasks/implementation/37_TASK_REMOVE_CONFIRMED_SALES_BUSINESS_RULE_DUPLICATION.md
docs/tasks/audits/38_TASK_SHARED_APPROVAL_STORE_FRAPPE_CACHE_AUDIT.md
```

The Task 38 audit file has an internal heading that incorrectly says `Task 37`, and its audit report explicitly records that numbering mismatch. Do **not** renumber historical task files or rewrite completed history as part of this implementation.

For project sequence purposes:

```text
Task 37 = Remove Confirmed Sales Business-Rule Duplication
Task 38 = Shared Approval Store / Frappe Cache Architecture Audit
Task 39 = Implement Frappe-Native Shared ApprovalStore
```

The current source ZIP / working tree is the implementation authority. Before editing, re-open the actual current files and preserve unrelated in-progress changes.

---

# 1. Objective

Replace the current process-local approval state in `mcp_erpnext` with a **shared, Frappe-native Redis-backed approval store** using the already-configured `frappe.cache` / `RedisWrapper` connection.

The implementation must make prepared approvals usable across MCP processes/workers while preserving all existing approval security and business boundaries.

Target behavior:

```text
Process A
  prepare_*()
      |
      v
ApprovalStore.create()
      |
      v
Frappe configured shared Redis
      |
      v
Process B
  confirm_*()
      |
      v
ApprovalStore.claim_for_confirm_write()
      |
      v
same approval is found, validated and atomically claimed
      |
      v
existing ERPNext/Frappe business write
```

The implementation must **not** create a new Redis architecture.

Use the Frappe-managed Redis connection and site context already initialized by the MCP runtime.

---

# 2. Mandatory source verification before editing

Inspect the current equivalents of at least:

```text
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/settings.py
mcp_erpnext/mcp_server.py
mcp_erpnext/observability.py
mcp_erpnext/services/**
mcp_erpnext/tests/test_approvals.py
mcp_erpnext/tests/test_customer_service.py
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_quotation_service.py
mcp_erpnext/tests/test_sales_order_to_sales_invoice.py
mcp_erpnext/tests/test_sales_invoice.py
mcp_erpnext/tests/test_quotation_to_sales_order.py
mcp_erpnext/tests/test_purchase_order_service.py
mcp_erpnext/tests/test_lifecycle.py
mcp_erpnext/tests/test_email.py
```

Also re-open:

```text
docs/inspect/SHARED_APPROVAL_STORE_FRAPPE_CACHE_AUDIT.md
```

Use the installed Frappe source as runtime authority, especially the installed equivalents of:

```text
frappe/__init__.py
frappe/utils/redis_wrapper.py
frappe/utils/caching.py
```

Do not rely on generic Redis assumptions when installed Frappe behavior can be inspected directly.

---

# 3. Current confirmed behavior to preserve

The latest source currently has:

```text
ApprovalStore
  -> self._approvals: dict[str, PendingApproval]
  -> process-local RLock
  -> process-local random HMAC signing key
  -> time.monotonic() timestamps
  -> APPROVAL_TTL_SECONDS = 900
```

The current approval boundary explicitly binds each approval to:

```text
action
site
user
payload / payload digest
trusted approval state
expiry
consumed state
cancelled state
```

The following behavior must remain true after Task 39:

```text
wrong action   -> cannot claim
wrong site     -> cannot claim
wrong user     -> cannot claim
payload mismatch -> cannot claim
not trusted in trusted_human mode -> cannot claim
expired        -> cannot claim
cancelled      -> cannot claim
consumed       -> cannot claim again
valid matching approval -> exactly one claim may succeed
```

The storage backend is changing. The authorization semantics are not.

---

# 4. Site handling — strict no-hard-code rule

This task must **never hard-code a concrete Frappe site name**.

Do not encode any development/runtime site such as a particular `*.localhost` value in production approval logic.

The current runtime already selects the site dynamically:

```text
MCP_FRAPPE_SITE / current runtime configuration
        |
        v
runtime._ensure_context(...)
        |
        v
frappe.init(site=configured_site, ...)
        |
        v
frappe.local.site
```

Approval services already pass the active site using `frappe.local.site` (or an equivalent value derived from the active Frappe runtime context).

Task 39 must preserve this model.

## Required rule

Production approval code must use the **currently configured / initialized Frappe site**, not a literal site name.

The configured site may be different in every installation:

```text
Installation A -> configured site A
Installation B -> configured site B
Installation C -> configured site C
```

All must work without code changes.

## Site responsibility split

Frappe provides:

```text
configured site context
Redis connection
site/database Redis key namespace
```

`mcp_erpnext` ApprovalStore still owns:

```text
explicit stored approval.site
current-site equality validation
fail-closed result on site mismatch
```

Do **not** remove the explicit approval `site` field merely because Frappe namespaces Redis keys by the current site/database.

These are separate protections:

```text
Frappe Redis namespace = infrastructure isolation
ApprovalStore site check = authorization binding
```

## Tests

Tests may use synthetic values such as:

```text
site-a.localhost
site-b.localhost
test.localhost
```

but these values must exist only in tests/fixtures. No production site value may be introduced.

---

# 5. User handling — keep it our approval boundary

Frappe runtime resolves/sets the current Frappe user.

Current behavior differs by transport:

```text
STDIO
  configured service user
  -> frappe.set_user(...)

HTTP
  authenticated request identity
  -> mcp_identity resolution
  -> frappe.set_user(...)
```

Task 39 must **not** redesign identity.

ApprovalStore must continue to receive and validate the resolved current Frappe user.

Example required behavior:

```text
prepare by Alice
  approval.user = alice@example.com

confirm attempt by Bob
  current user = bob@example.com

=> unavailable / fail closed
=> Alice's valid approval is NOT consumed by Bob's failed attempt
```

Frappe cache does not decide whether a user is authorized to reuse an approval token. That remains the responsibility of `mcp_erpnext` ApprovalStore.

---

# 6. Action and payload binding — keep them in ApprovalStore

Frappe Redis is only shared storage.

It must not replace these checks:

```text
stored action == requested action
stored site == current active site
stored user == current resolved user
stored payload digest == digest(stored payload)
trusted/cancelled/consumed/expiry state valid
```

A token prepared for one action must never authorize another action.

Example:

```text
prepared action = create_sales_order
confirm action  = lifecycle_delete

=> fail closed
=> original valid approval must not be consumed merely because the caller used the wrong action
```

---

# 7. Target storage architecture

Implement the shared state behind the existing ApprovalStore abstraction.

Preferred shape:

```text
business services
      |
      v
ApprovalStore
      |
      v
private approval storage operations
      |
      v
frappe.cache (existing RedisWrapper instance)
      |
      v
Frappe-configured redis_cache
```

Do not add:

```text
new Redis service
new Redis container
new redis:// configuration
new Redis credentials
new Python Redis package
direct redis.Redis(...) construction
new Approval DocType
new MariaDB table
new external cache framework
client-specific state storage
```

The implementation may use low-level methods inherited by Frappe's already-created `RedisWrapper` **only where required for fail-closed behavior or atomic state transitions**.

That is still Frappe-managed Redis infrastructure and must remain fully encapsulated inside ApprovalStore/private approval storage code.

---

# 8. High-level Frappe cache helper restriction

The Task 38 audit found that ordinary high-level cache helpers are optimized for cache semantics, not authorization semantics.

In particular, approval authorization must not depend on a path that can:

```text
read stale frappe.local.cache
silently treat Redis connection failure as a cache miss
write only process-local cache when shared Redis write failed
fall back to request/process cache
```

Therefore:

- security-sensitive approval reads/claims must bypass stale `frappe.local.cache` behavior;
- create must not return an approval token unless shared backend persistence is known to have succeeded;
- backend uncertainty must fail closed;
- there must be no in-memory production fallback.

Do not use `frappe.client_cache` for approval authorization.

---

# 9. Redis key design

Use Frappe's current site/database namespacing through the installed `RedisWrapper`.

Do not manually hard-code the site into a global shared key and do not use `shared=True` for approval keys.

Use a private approval namespace, conceptually:

```text
mcp_erpnext:approval:<token-fingerprint>
```

Prefer a one-way SHA-256 fingerprint of the opaque public approval token for the Redis lookup suffix so normal key inspection does not reveal the raw bearer-like token.

The public token format must remain unchanged.

The key transformation is private implementation detail.

All state operations must use the same key derivation:

```text
create
lookup
record_trusted_user_approval
claim_for_confirm_write
cancel
```

---

# 10. Approval record serialization

Persist all state required to reproduce the existing `PendingApproval` semantics across processes:

```text
action
site
user
created timestamp / expiry metadata
prepared payload
payload digest
trusted timestamp/state
consumed timestamp/state
cancelled timestamp/state
```

The stored format must be process-independent.

Do not persist process-only synchronization objects or process IDs as authorization state.

If using Frappe's established pickle convention, treat Redis as a trusted server-side cache boundary and keep deserialization entirely server-side.

If another serialization format is chosen, prove it preserves the real payload types currently required by all services.

Do not change business payload shape merely to make serialization easier.

---

# 11. Cross-process timestamp migration

Do not persist `time.monotonic()` values as cross-process timestamps.

Use a process-stable wall-clock representation suitable for shared state.

Requirements:

```text
creation time stable across workers
trusted_at stable across workers
consumed_at stable across workers
cancelled_at stable across workers
Redis TTL remains authoritative for expiration
```

Redis TTL must be exactly the current policy:

```text
APPROVAL_TTL_SECONDS = 900
```

When an approval state is rewritten from available -> trusted / consumed / cancelled, preserve the **remaining original TTL**.

Never reset it to a fresh 900 seconds.

---

# 12. Payload digest migration

The current `_signing_key` is randomly generated per process and therefore cannot verify a record created by another process.

Task 39 must replace that process-local digest mechanism with a process-stable design.

For the currently audited trusted-Redis threat model, use a deterministic digest over the same canonical payload representation, unless current source inspection reveals a stronger already-approved shared signing facility.

The default implementation direction is:

```text
canonical JSON representation
        |
        v
SHA-256
        |
        v
process-stable payload digest
```

Preserve constant-time comparison where applicable.

Important security statement to document in the implementation report:

- this digest preserves payload binding/corruption detection across workers;
- it is not a keyed MAC against an attacker who can arbitrarily rewrite both Redis payload and digest;
- Frappe Redis is treated as trusted internal server infrastructure for this task.

Do **not** introduce a new signing secret as a hidden side effect.

Do **not** reuse unrelated secrets such as:

```text
MCP_HTTP_SHARED_SECRET
MCP_FRAPPE_USER
ERPNext API credentials
client-provided values
```

If current source proves a shared signing secret is already explicitly intended for this approval purpose, document it before using it. Otherwise use the audited deterministic approach.

---

# 13. Atomic one-shot claim — mandatory

A shared store is not sufficient unless confirmation remains one-shot under concurrency.

Required behavior:

```text
Process A ---- confirm(token) ----\
                                  +--> exactly ONE valid claim succeeds
Process B ---- confirm(token) ----/
```

Use the audited Frappe-configured Redis transaction approach:

```text
WATCH
  -> raw shared read
  -> deserialize
  -> validate action/site/user/payload/state/trust/TTL
  -> MULTI
  -> rewrite record as consumed with remaining TTL
  -> EXEC
```

On `WatchError` / concurrent change:

```text
do not continue to ERP business write
re-read safely only for result classification if backend state is certain
return consumed/unavailable as appropriate
```

On connection/transaction uncertainty:

```text
fail closed
never continue to business write
```

Do not implement claim as:

```text
GET -> validate -> DELETE
```

Do not use blind `GETDEL` because a wrong user/action/site or not-trusted attempt must not destroy a valid approval.

---

# 14. Trusted approval transition must also be shared and race-safe

`record_trusted_user_approval()` remains internal plumbing.

It must continue to validate:

```text
token
action
site
user
payload digest
not expired
not consumed
not cancelled
```

Then transition the shared record to trusted state without resetting the original TTL.

It must be race-safe against:

```text
claim
cancel
another trusted-state update
expiry
```

Do not expose this method as an MCP tool or public tool argument.

Do not add public `trusted_at` or `approval_mode` inputs.

---

# 15. Cancel transition must remain safe

`cancel()` must only cancel a matching valid pending approval.

Wrong action/site/user must not consume or cancel the legitimate approval.

Cancellation must be a shared state transition and preserve the remaining original TTL.

Current public behavior must remain unchanged.

---

# 16. Lookup behavior

`lookup()` must perform shared backend reads, not process-local authorization reads.

It must preserve current state semantics as closely as possible:

```text
available
expired
unavailable
consumed
```

Do not reveal security-sensitive mismatch detail publicly.

Internally, diagnostics may distinguish reasons such as:

```text
missing_or_expired
wrong_action
wrong_site
wrong_user
payload_digest_mismatch
consumed
cancelled
not_trusted
backend_unavailable
watch_conflict
serialization_failure
```

These are internal-only.

---

# 17. `prune_expired()` compatibility

Existing services currently call `approvals.prune_expired()`.

Do not force service-wide edits merely because Redis now owns expiration.

Preserve the existing method so call-sites do not need to change.

Preferred behavior after migration:

```text
prune_expired()
  -> no global Redis scan
  -> Redis TTL is authoritative
  -> compatibility no-op or minimal safe behavior
```

Do not use Redis `KEYS` scans or broad namespace cleanup during normal prepare calls.

---

# 18. Fail-closed backend behavior

Approval state is an authorization boundary, not a best-effort cache.

Required rules:

## Create failure

If the shared Redis write fails or its success is uncertain:

```text
do not return a usable approval token
```

Use the existing safe error/observability boundary. Do not leak infrastructure details.

## Lookup failure

If Redis cannot be reliably read:

```text
no approval authorization
```

## Trusted-state failure

If trust-state write is uncertain:

```text
do not treat approval as trusted
```

## Claim failure

If transaction outcome is uncertain:

```text
do not continue to ERP write
```

## Cancel failure

Do not report/assume cancellation state if the backend transition was not reliably persisted.

No production fallback to `self._approvals`, module memory, request cache, or local cache is allowed.

---

# 19. Preserve ApprovalStore service interface

Preserve these current service-level calls where practical:

```text
approvals.configure_approval_mode(...)
approvals.create(...)
approvals.lookup(...)
approvals.record_trusted_user_approval(...)
approvals.claim_for_confirm_write(...)
approvals.cancel(...)
approvals.prune_expired()
confirmation_failure(...)
```

Do not require business services to understand Redis.

Do not make Customer/Item/Quotation/Sales Order/Sales Invoice/etc. call Redis directly.

All Redis-specific behavior belongs behind ApprovalStore/private approval storage internals.

---

# 20. Public MCP contracts — zero-change requirement

Task 39 must not rename or redesign any public tool.

No changes to:

```text
prepare_* tool names
confirm_* tool names
input schemas
output schemas
approval token public format
InteractionDirective
profile inventories
Sales/Purchase profile selection
HTTP identity headers
STDIO identity configuration
MCP_APPROVAL_MODE public visibility
business capability allowlists
```

Run the current contract tests to prove this.

---

# 21. Business-service boundary — no redesign

Do not redesign or alter native ERPNext business behavior for:

```text
Customer
Item
Quotation
Sales Order
Sales Invoice
Quotation -> Sales Order
Sales Order -> Sales Invoice
Purchase Order
lifecycle update
child/item add
submit
cancel
delete
document email
PDF
```

Existing prepare/confirm services must continue to:

```text
prepare business state
create approval
confirm approval
revalidate stale/native business state
perform normal Frappe/ERPNext permissions and validation
commit / rollback according to existing behavior
```

Task 39 changes approval persistence only.

---

# 22. Post-claim write failure semantics

Preserve current behavior:

```text
approval successfully claimed
        |
        v
ERPNext/Frappe write attempted
        |
        +--> write succeeds -> approval remains consumed
        |
        +--> write fails -> ERP transaction rolls back, approval still consumed
                           caller must prepare again
```

Do not automatically restore a consumed approval after a business write failure.

This avoids duplicate/ambiguous retries after uncertain persistence.

---

# 23. Observability

Add only minimal safe internal approval diagnostics if needed to make multi-process behavior diagnosable.

Useful internal fields:

```text
PID
server instance ID if already available / safely introduced internally
approval action
active site
short user fingerprint
optional short token fingerprint
result/state
remaining TTL
backend/watch failure classification
```

Never log:

```text
raw approval token
full prepared payload
Authorization header
HTTP shared secret
ERP credentials
Redis credentials
sensitive business data not already allowed by logging policy
```

Do not add PID, instance ID, client ID, conversation ID, thread ID, Codex ID, LibreChat ID, or run ID to the public approval contract.

Observability additions are secondary to the storage migration and must remain small.

---

# 24. Allowed production changes

Primary allowed file:

```text
mcp_erpnext/approvals.py
```

A new private internal approval-storage helper module may be added **only if inspection proves it materially improves separation/testability**. If not needed, keep the implementation in `approvals.py`.

Potentially allowed, only if required for safe internal diagnostics:

```text
mcp_erpnext/observability.py
```

Do not change `runtime.py` or `settings.py` merely to support Redis storage; the current site/user runtime boundary is already correct.

If implementation reveals a genuine runtime initialization defect, stop that change from being bundled silently: document it in the report as a separate follow-up unless the defect makes Task 39 impossible.

---

# 25. Required test changes

Primary:

```text
mcp_erpnext/tests/test_approvals.py
```

Existing service tests currently access `_approvals` directly. Adapt those tests to use an explicit private test seam / fake shared backend instead of depending on the old production dictionary.

Known current tests likely requiring adaptation include:

```text
test_customer_service.py
test_item_service.py
test_quotation_service.py
test_sales_invoice.py
test_sales_order_to_sales_invoice.py
test_quotation_to_sales_order.py
test_purchase_order_service.py
test_lifecycle.py
test_email.py
```

Inspect actual current usage before changing each file.

Do not keep a fake production `_approvals` dictionary solely to satisfy old tests.

---

# 26. Test-backend seam

Default unit tests must not require a live Redis service.

Provide a private injectable/shared fake backend or equivalent controlled seam that can model:

```text
shared state between two ApprovalStore instances
TTL
conditional transaction
WatchError/conflict
backend unavailable
uncertain transaction failure
```

Production must still resolve the real backend from active Frappe `frappe.cache` after site initialization.

The fake backend is for tests only and must not become a production fallback.

---

# 27. Mandatory approval unit tests

Cover at minimum:

- create writes shared approval state;
- create does not return a token when backend write fails;
- TTL is exactly 900 seconds;
- timestamps are cross-process stable;
- raw token remains opaque and unchanged publicly;
- private cache key does not expose raw token if fingerprint design is implemented;
- action binding preserved;
- active/configured site binding preserved;
- user binding preserved;
- payload digest binding preserved;
- digest verifies across independent ApprovalStore instances;
- trusted-human state preserved;
- `agent_delegated` skips only trusted-human requirement and nothing else;
- cancel state preserved;
- consumed state preserved;
- expired state preserved;
- malformed/corrupt record fails closed;
- backend read/write failure fails closed;
- transaction uncertainty fails closed;
- stale `frappe.local.cache` is never accepted as approval authorization;
- `prune_expired()` does not perform broad Redis scans.

---

# 28. Mandatory site tests

Explicitly verify dynamic site behavior.

Example synthetic test model:

```text
configured/active site = site-a.localhost
prepare -> approval.site = site-a.localhost
confirm in site-a.localhost -> allowed if all other checks pass
```

Then:

```text
same token
active site = site-b.localhost
-> unavailable
-> token is not consumed
```

Switch back to the originally bound site while approval remains valid:

```text
site-a.localhost
-> valid caller may still claim
```

The test must prove site comes from runtime/configured context, not from a production literal.

Do not make the tests depend on the developer's real site name.

---

# 29. Mandatory user tests

Verify:

```text
Alice prepares
Bob attempts confirm -> fail closed, do not consume
Alice confirms -> succeeds if still valid
```

Also verify trusted approval recording by the wrong user does not mutate the valid approval.

---

# 30. Mandatory action tests

Verify:

```text
token prepared for action A
claim using action B -> unavailable, do not consume
action A may still validly claim afterward
```

---

# 31. Mandatory cross-instance test

Create two independent ApprovalStore instances backed by the same fake shared backend.

```text
Store A -> create
Store B -> lookup/claim
```

Expected:

```text
Store B sees the same approval
matching valid confirm succeeds
```

This is the direct regression test for the original process-local defect.

---

# 32. Mandatory concurrency test

Model two workers attempting the same valid claim concurrently.

Expected:

```text
exactly one transaction succeeds
exactly one caller receives a claim that may continue to business write
other caller cannot continue to write
```

Assert that no race can produce two successful `available` claims.

Also force a transaction/watch conflict and assert fail-closed behavior.

---

# 33. Mandatory process-restart model test

Simulate:

```text
Store A creates approval
Store A object is discarded
Store B is created using same shared backend
Store B confirms token
```

Expected:

```text
works while approval key remains valid
```

This proves approval state no longer depends on process memory or process-random signing state.

---

# 34. Redis-unavailable tests

Model failures for:

```text
create write
lookup read
trusted-state transaction
cancel transaction
claim WATCH/read
claim EXEC / uncertain result
```

Expected:

```text
no authorization success
no business-write continuation
no process-memory fallback
```

---

# 35. Service regression coverage

Run current approval-backed service tests for at least:

```text
Customer
Item
Quotation
Sales Order
Sales Invoice
Quotation -> Sales Order
Sales Order -> Sales Invoice
Purchase Order
lifecycle update
lifecycle child/item add
lifecycle submit
lifecycle cancel
lifecycle delete
document email
```

PDF remains read/render-only and must not gain an approval flow.

---

# 36. Contract/profile regression coverage

Run existing tests covering:

```text
tool registration
typed tool contracts
interaction contracts
profile registration
Sales profile
Purchase profile
runtime identity
HTTP transport
observability
```

Confirm public schemas and registered tool names are unchanged.

If the repository has a generated tool-catalog check, run it in check mode. Do not regenerate merely because internal approval storage changed unless the check requires it.

---

# 37. Optional isolated real-Frappe cache verification

After unit tests pass, an isolated temporary-key runtime verification may be run against the configured development environment if the repository/test environment already supports it safely.

Rules:

- use the site selected through normal configuration/runtime;
- never hard-code a site name in production code;
- use a unique Task 39 temporary key namespace;
- use non-business dummy data;
- use a very short TTL;
- clean up the key afterward;
- do not flush Redis;
- do not clear global Frappe cache;
- do not restart Redis/Frappe/MCP services;
- do not modify ERP records.

This verification is supplemental. Default automated tests must remain live-Redis-independent.

---

# 38. Documentation updates

Update only current-state documentation that would otherwise become false after this implementation.

Likely current docs to inspect include:

```text
docs/architecture/MCP_EXPLICIT_USER_APPROVAL_SAFETY.md
docs/architecture/MCP_TOOL_CONTRACT_ARCHITECTURE.md
docs/architecture/MCP_DOCUMENT_EMAIL.md
docs/MCP_PROFILES.md
docs/testing/POSTMAN_MCP_HTTP_TESTING.md
docs/ERPNext_MCP_ARCHITECTURE.md
docs/guides/MCP_SYSTEM_HUMAN_GUIDE_HINGLISH.md
```

Only edit files that actually contain current statements made obsolete by Task 39.

Do not rewrite historical task files or historical audit/implementation reports merely because they describe the old process-local state correctly for their time.

In particular, do not renumber Task 37 or Task 38 history in this implementation.

---

# 39. Forbidden changes

Do not:

```text
hard-code any concrete site name in production approval logic
hard-code any user identity
add a new Redis service
add a new Redis container
add a new Redis URL/env variable
add Redis credentials
construct a new redis.Redis connection
add a new approval DocType/table
change MCP_FRAPPE_SITE semantics
change MCP_FRAPPE_USER semantics
change HTTP identity resolution
change STDIO identity resolution
change MCP_APPROVAL_MODE values/default policy
change the 900-second approval policy
change public tool names
change public schemas
change profile registration
change business capability allowlists
change ERPNext/Frappe/India Compliance source
change document permissions/validation behavior
change lifecycle business policies
change conversion mapping rules
change Customer/Item/Sales business rules
flush Redis
restart services
run migrations
commit unrelated changes
```

---

# 40. Acceptance criteria

Task 39 is complete only when all are true:

- [ ] Current source re-inspected before implementation.
- [ ] Existing Task 38 audit recommendations reconciled with current code.
- [ ] Approval state no longer depends on process-local `_approvals` in production.
- [ ] No production in-memory fallback remains for approval authorization.
- [ ] Existing Frappe-configured Redis connection is reused.
- [ ] No new Redis service/configuration/credentials are introduced.
- [ ] Site is derived dynamically from configured/active Frappe runtime context.
- [ ] No concrete runtime site is hard-coded in production approval code.
- [ ] Explicit approval site binding is preserved.
- [ ] Explicit approval user binding is preserved.
- [ ] Explicit approval action binding is preserved.
- [ ] Payload binding is process-stable across workers.
- [ ] Trusted-human policy is preserved.
- [ ] `agent_delegated` changes only the trust requirement as before.
- [ ] TTL remains exactly 900 seconds.
- [ ] State rewrites preserve remaining original TTL.
- [ ] Timestamps are cross-process stable.
- [ ] Atomic one-shot claim works across independent store instances.
- [ ] Concurrent confirms cannot both continue to business write.
- [ ] Wrong user does not consume a valid approval.
- [ ] Wrong site does not consume a valid approval.
- [ ] Wrong action does not consume a valid approval.
- [ ] Backend/transaction uncertainty fails closed.
- [ ] Process restart model works while shared approval remains valid.
- [ ] `prune_expired()` no longer depends on process-local cleanup and performs no broad Redis scan.
- [ ] Existing public confirmation error contract remains safe and compatible.
- [ ] Public MCP tool names/schemas remain unchanged.
- [ ] Sales and Purchase profile inventories remain unchanged.
- [ ] Existing business service semantics remain unchanged.
- [ ] Approval-backed service regression tests pass.
- [ ] Contract/profile/runtime tests pass.
- [ ] Full MCP test suite passes.
- [ ] Current-state docs are updated only where necessary.
- [ ] Historical task/audit reports are not rewritten.
- [ ] Implementation report is created.

---

# 41. Required implementation report

Create:

```text
docs/inspect/FRAPPE_NATIVE_SHARED_APPROVAL_STORE_IMPLEMENTATION_REPORT.md
```

The report must include:

1. Task 39 scope completed
2. Source files inspected
3. Files changed
4. Final shared ApprovalStore architecture
5. Exact Frappe cache / RedisWrapper APIs used
6. Site derivation and no-hard-code verification
7. User/action/site/payload authorization boundary
8. Redis key derivation
9. Serialization format
10. Timestamp migration
11. Digest migration and threat-model statement
12. TTL behavior
13. Atomic claim implementation
14. Trusted approval transition
15. Cancel transition
16. Backend failure behavior
17. `frappe.local.cache` bypass strategy
18. Process-restart behavior
19. Concurrency behavior
20. Public contract verification
21. Tests run with exact commands and results
22. Any optional isolated cache verification performed
23. Documentation updates
24. Known limitations
25. Exact next task recommendation

---

# 42. Expected final architecture

```text
                         MCP Runtime
              configured site + resolved user
                         |
                         v
                Business prepare/confirm
                         |
                         v
                  ApprovalStore
        action/site/user/payload/trust checks
                         |
                         v
          private shared-state operations
                         |
                         v
                  frappe.cache
              existing RedisWrapper
                         |
                         v
             Frappe configured Redis
                         |
          +--------------+--------------+
          |              |              |
      MCP Proc A     MCP Proc B     MCP Proc C
```

Responsibilities remain:

```text
Frappe runtime:
  configured site
  resolved current user
  Redis configuration/connection
  site/database cache namespace

mcp_erpnext ApprovalStore:
  token generation
  explicit site binding
  explicit user binding
  action binding
  payload binding
  trust policy
  cancel/consume state
  TTL semantics
  atomic one-shot claim
  fail-closed authorization

ERPNext/Frappe document layer after successful claim:
  permissions
  native validation
  links
  hooks
  accounting/stock/compliance behavior
  persistence/rollback
```

---

# 43. Known boundaries / limitations

Task 39 does not add durable approval history.

Redis remains ephemeral coordination state. If the shared Redis key disappears because of expiry, eviction, flush, or Redis restart:

```text
approval is unavailable
no write is authorized
fresh prepare is required
```

The Redis claim and ERP database commit are separate systems. A successful claim followed by failed ERP persistence intentionally requires a new prepare.

Task 39 does not solve or redesign:

```text
human-approval UI transport
LibreChat approval UI
Codex UI
LangGraph orchestration
Docker topology
MCP identity architecture
new profiles
new business tools
business idempotency keys
long-term approval auditing
```

---

# 44. Exact next task

Do not pre-implement another feature inside Task 39.

After Task 39 is implemented and its report/tests are reviewed, choose the next project task based on the then-current roadmap.

If Task 39 uncovers a separate runtime/deployment issue, document it as a new follow-up task rather than expanding this implementation scope.
