# Task 38 — Shared Approval Store / Frappe Cache Architecture Audit

## Status
**Type:** Read-only architecture and implementation audit  
**Project:** `mcp_erpnext`  
**Primary area:** Approval / confirmation state  
**Expected result:** Audit report only  
**Production code changes:** Forbidden  
**Database mutations:** Forbidden  
**Redis/cache mutations beyond safe temporary test keys:** Avoid unless absolutely necessary; prefer source inspection and isolated test/mocks

---

# 1. Objective

Inspect the current `mcp_erpnext` approval implementation and the installed Frappe v16 cache/Redis implementation to determine the safest native design for replacing the current **process-local approval store** with a **shared approval store backed by Frappe's existing cache mechanism**.

The purpose is to make prepare/confirm workflows work correctly when:

- more than one MCP process exists;
- an MCP client reconnects;
- a different MCP worker handles confirmation;
- multiple MCP containers or workers are eventually deployed;
- STDIO clients such as Codex spawn more than one MCP process.

The audit must determine whether the required behavior can be implemented using Frappe-native cache/Redis facilities without introducing unnecessary custom Redis infrastructure.

The final recommendation must preserve the current approval security semantics, especially:

- action binding;
- site binding;
- authenticated-user binding;
- payload binding/digest;
- TTL;
- trusted-human approval state where applicable;
- reject/cancel behavior;
- single-use confirmation;
- atomic claim/consumption;
- fail-closed behavior;
- safe public errors;
- normal Frappe/ERPNext write validation after approval.

---

# 2. Core Architecture Principle

Do **not** build a parallel Redis system if Frappe already provides the required foundation.

Preferred direction:

```text
MCP business services
        |
        v
ApprovalStore
        |
        v
Frappe-native cache API
        |
        v
Frappe configured Redis
        |
        +---- MCP Process A
        +---- MCP Process B
        +---- MCP Process C
```

The MCP business services must remain unaware of Redis details.

They should continue using an approval abstraction such as:

```python
approvals.create(...)
approvals.record_trusted_user_approval(...)
approvals.claim_for_confirm_write(...)
```

The task must inspect the real current implementation before assuming these exact signatures.

---

# 3. Known Problem to Validate

Current approval storage is believed to be process-local.

Example failure mode:

```text
MCP Process A
    prepare_sales_order_item_add(...)
        -> token ABC stored in process A memory

MCP Process B
    confirm_sales_order_item_add(token=ABC)
        -> process B cannot see process A memory
        -> approval unavailable
        -> confirmation fails
```

The existing approval TTL is believed to be approximately 15 minutes, so a confirmation failure only a few seconds after prepare may indicate process replacement/reconnection or another approval-state issue rather than true TTL expiry.

Do not trust this summary blindly.

Inspect the current tree and verify:

- actual storage implementation;
- actual TTL;
- actual public error mapping;
- exact claim/consume semantics;
- exact behavior after a failed confirm;
- exact trusted-approval behavior.

---

# 4. Mandatory Scope

Inspect the actual current repository first.

At minimum locate and inspect the current equivalents of:

```text
mcp_erpnext/approvals.py
mcp_erpnext/settings.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/contracts/registry.py

mcp_erpnext/services/**
mcp_erpnext/tools/**
mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py

mcp_erpnext/tests/**
docs/TOOLS.md
docs/architecture/**
docs/inspect/**
```

Do not assume these exact paths still exist.

Report the actual paths found.

Also inspect the installed Frappe v16 source used by this bench/site.

At minimum inspect the installed equivalents of:

```text
frappe/__init__.py
frappe/utils/redis_wrapper.py
frappe/utils/**
frappe/cache_manager.py
frappe/local.py / local request cache handling
frappe/config or redis connection setup
```

Search for:

```text
frappe.cache
RedisWrapper
set_value
get_value
delete_value
expires_in_sec
ttl
expire
nx
xx
setnx
getdel
pipeline
transaction
watch
lock
lua
eval
frappe.local.cache
redis_cache
make_key
site prefix
```

Do not assume every symbol exists.

---

# 5. Official Source Requirement

Ground the audit in:

1. the installed Frappe source for the actual runtime version;
2. official Frappe Framework documentation;
3. official Frappe GitHub source when useful for comparison.

Do not rely on:

- Stack Overflow;
- random blog posts;
- generic Redis tutorials;
- third-party examples;
- guesses about `redis-py`;
- assumptions based only on method names.

If installed source and current official docs differ, describe the difference and treat installed source as runtime authority.

---

# 6. Current ApprovalStore Audit

Trace the full current approval lifecycle.

## 6.1 Creation

Determine exactly:

- how tokens are generated;
- token entropy/randomness source;
- what data is stored;
- whether full payload or digest is stored;
- how site is recorded;
- how authenticated user is recorded;
- how action is recorded;
- how timestamps are stored;
- TTL calculation;
- trusted-human state;
- whether there is any profile binding;
- whether any client/session/conversation identifier is stored;
- whether the store is global, module-level, class-level, or instance-level;
- whether state is process-local.

Document the exact function/class names and file/line references.

## 6.2 Trusted approval

Trace:

```text
prepare
    -> approval created
    -> trusted-human approval recorded?
    -> confirmation allowed
```

Determine:

- how `trusted_human` mode works;
- how `agent_delegated` mode works;
- where mode is selected;
- whether client/model can control it;
- how trusted approval is recorded;
- what is mutable after prepare;
- what must remain internal.

## 6.3 Confirmation claim

Inspect `claim_for_confirm_write()` or current equivalent.

Determine exactly:

- validation order;
- token lookup behavior;
- action check;
- site check;
- user check;
- payload/digest check;
- trusted-approval check;
- TTL check;
- consume timing;
- concurrency behavior;
- replay behavior;
- what happens when persistence fails after claim;
- whether rollback restores approval state;
- whether confirmation must be prepared again.

## 6.4 Reject / cancel

Determine:

- whether reject consumes the token;
- whether conversational cancel consumes it;
- whether any ERP document cancellation is involved;
- whether current public errors distinguish expired / missing / consumed / mismatch.

## 6.5 Cleanup

Determine:

- how expired entries are removed;
- whether cleanup is lazy or active;
- whether process restart clears everything;
- whether memory can grow with unused approvals.

---

# 7. Approval Call-Site Inventory

Find every real current use of approval creation, trusted approval, claim, reject, cancel, or equivalent.

At minimum classify flows for:

```text
Customer
Item
Quotation
Sales Order
Sales Invoice
Quotation -> Sales Order
Sales Order -> Sales Invoice
document update
child/item add
submit
cancel
delete
email
PDF if approval-gated
Purchase Order
purchase mutations
any additional current write capability
```

For every approval-backed capability report:

| Capability | Prepare function | Confirm function | Approval action | Uses shared ApprovalStore? | Special stale revalidation? |
|---|---|---|---|---|

The purpose is to ensure that a future storage migration does not accidentally fix only one business flow.

---

# 8. Frappe Cache Architecture Audit

Inspect how `frappe.cache` actually works in the installed Frappe version.

Determine:

- how the Redis connection is configured;
- whether all Frappe/MCP processes for the same bench use the same configured cache Redis;
- how site namespacing is implemented;
- what happens before/after `frappe.init(site)`;
- whether `frappe.cache` requires active site context;
- serialization format;
- maximum practical payload concerns;
- TTL behavior;
- local per-request cache behavior;
- cache invalidation;
- behavior when Redis is unavailable;
- whether API calls suppress Redis exceptions;
- whether cache methods can silently fall back to local memory;
- whether any method is unsuitable for security-sensitive approval state.

Explicitly inspect `frappe.local.cache` or equivalent request-local caching.

Answer:

> Could an approval lookup accidentally be satisfied from stale process-local/request-local cache instead of Redis?

If yes, explain how to disable/bypass local cache for approval state.

If no, prove why.

---

# 9. Atomic Claim Requirement

This is the most important part of the audit.

A shared store is not sufficient unless one-shot confirmation remains atomic.

Required property:

```text
Process A ---- confirm(token) ----\
                                  +--> exactly ONE process may win
Process B ---- confirm(token) ----/
```

The audit must determine whether installed Frappe already exposes a safe native primitive that can implement this.

Inspect available Frappe/RedisWrapper facilities for possibilities such as:

- atomic get-and-delete;
- set-if-not-exists;
- delete with prior validation;
- transaction/pipeline;
- watch/multi;
- distributed locks;
- compare-and-delete;
- an existing cache API intended for one-time state;
- an official helper already used elsewhere in Frappe.

Do not select an implementation merely because Redis itself supports it.

The question is:

> What is the most Frappe-native, minimal, maintainable implementation available in the installed version?

For each viable option document:

```text
Option
Native Frappe API used
Atomicity guarantee
Race behavior
Failure behavior
Complexity
Whether custom Redis logic is required
Recommendation
```

---

# 10. Required Concurrency Scenarios

The design must handle all of these.

## Scenario A — same process

```text
Process A prepare
Process A confirm
```

Expected: works.

## Scenario B — different process

```text
Process A prepare
Process B confirm
```

Expected: works.

## Scenario C — simultaneous confirm

```text
Process A confirm(token)
Process B confirm(token)
```

Expected:

```text
one succeeds
one fails closed
```

Never two writes.

## Scenario D — expired approval

Expected:

```text
no write
fresh prepare required
```

## Scenario E — already consumed token

Expected:

```text
no replay
fresh prepare required
```

## Scenario F — wrong user

Expected:

```text
fail closed
```

## Scenario G — wrong site

Expected:

```text
fail closed
```

## Scenario H — wrong action

Expected:

```text
fail closed
```

## Scenario I — trusted-human approval missing

Expected:

```text
fail closed in trusted-human mode
```

## Scenario J — MCP process restart

```text
Process A prepare
Process A exits
Process B starts
Process B confirm
```

Expected target architecture:

```text
works if shared Frappe cache still contains valid approval
```

## Scenario K — Redis/cache unavailable

Expected:

```text
fail closed
never execute write because approval state cannot be verified
```

No silent fallback to process memory for approval authorization.

---

# 11. Security Boundary

The future design must not weaken the current approval boundary.

Verify that the recommended design preserves:

```text
cryptographically strong opaque token
action binding
site binding
authenticated user binding
payload/digest binding
TTL
trusted approval
one-shot consumption
replay protection
stale document checks
normal ERPNext/Frappe permission checks
normal native validation
commit / rollback behavior
safe public errors
```

Also determine whether raw approval tokens should be used directly as cache keys.

If the installed/native design permits a safer lookup-key derivation, discuss it.

Do not implement hashing/encryption merely because it sounds safer.

Only recommend extra token-key transformation if it has a concrete benefit and does not complicate the design unnecessarily.

---

# 12. Error Semantics Audit

Inspect current public confirmation errors.

Determine whether one public error such as:

```text
CONFIRMATION_EXPIRED
```

currently represents multiple internal conditions, for example:

```text
not found
actually expired
already consumed
wrong user
wrong site
wrong action
trusted approval unavailable
```

Do not expose sensitive internal distinctions publicly if that weakens security.

Recommend:

- stable safe public response;
- useful internal observability reason codes;
- no raw approval tokens in logs;
- no credentials/secrets;
- optional safe token fingerprint only if justified.

The audit must distinguish:

```text
public contract
vs
internal operational logging
```

---

# 13. Observability Audit

Inspect current logging/observability.

Determine whether future debugging should include:

```text
process PID
server instance ID
approval action
site
user fingerprint
safe token fingerprint
create timestamp
claim result
internal reason code
```

Do not recommend logging:

```text
raw approval token
full sensitive payload
credentials
Authorization headers
shared secrets
ERP data outside current safe logging policy
```

Determine whether PID/server-instance logging is useful for STDIO/Codex process debugging.

---

# 14. Redis / Frappe Cache Infrastructure Boundary

The recommended solution should prefer:

```text
frappe.cache
Frappe configured redis_cache
Frappe site context
Frappe RedisWrapper
existing official helper/primitives
```

Do not recommend by default:

```text
new Redis container
new redis:// environment variable
new direct redis.Redis(...) connection
new Redis credentials
parallel Redis client configuration
new cache service
new approval database/DocType
new external queue
custom cache framework
```

If any direct Redis primitive is genuinely required because Frappe does not expose the necessary atomic behavior, clearly prove this from installed source.

In that case propose the smallest possible adapter that still reuses Frappe's configured Redis connection rather than creating separate infrastructure.

---

# 15. Database / DocType Alternative

Briefly evaluate whether approval state should instead use a Frappe DocType/database table.

Compare:

```text
Frappe cache / Redis
vs
DocType / MariaDB
```

Criteria:

- multi-process sharing;
- TTL;
- atomic claim;
- temporary nature;
- database churn;
- restart behavior;
- audit requirements;
- complexity;
- cleanup;
- security;
- operational fit.

Unless evidence shows otherwise, approval state should be treated as ephemeral coordination state, not long-term ERP business data.

Do not create a DocType in this task.

---

# 16. STDIO / HTTP / Multi-Process Compatibility

Verify that the recommended store works regardless of MCP transport.

Evaluate:

```text
STDIO single process
STDIO multiple client sessions
Codex-launched STDIO child processes
HTTP one worker
HTTP multiple workers
multiple MCP containers
Sales profile process
Purchase profile process
```

The approval system must remain client-neutral.

Do not introduce:

```text
Codex-specific state
LibreChat-specific state
conversation_id
thread_id
client process ID
OpenAI run ID
UI component IDs
```

into core approval contracts.

---

# 17. Profile Boundary

Inspect whether approval tokens should be explicitly profile-bound.

Current architecture has at least:

```text
sales
purchase
```

Determine from current code whether:

- action already uniquely prevents cross-profile use;
- site/user/action/payload binding is sufficient;
- profile is already included directly or indirectly;
- explicit profile binding would improve security;
- adding it would break compatibility.

Do not introduce a profile field without evidence and justification.

---

# 18. Public MCP Contract Boundary

The desired storage migration should ideally require:

```text
ZERO public tool rename
ZERO prepare input schema change
ZERO confirm input schema change
ZERO approval token format change unless absolutely necessary
ZERO business service behavior change
ZERO profile inventory change
```

Verify whether that is achievable.

List any unavoidable contract impact separately.

---

# 19. Tests to Design for the Future Implementation

Do not implement production code in Task 37.

Define the exact tests Task 38 must add.

At minimum include:

## Unit tests

- create stores approval in shared backend;
- TTL set correctly;
- action/user/site/payload binding preserved;
- trusted-human state preserved;
- reject consumes/cancels correctly;
- wrong action fails;
- wrong user fails;
- wrong site fails;
- expired token fails;
- consumed token fails;
- malformed token fails safely;
- cache backend failure fails closed.

## Cross-instance tests

Create two independent `ApprovalStore` instances representing two MCP processes:

```text
store A create
store B claim
```

Expected: succeeds.

Then:

```text
store A create
store A claim
store B claim
```

Expected:

```text
first claim succeeds
second claim fails
```

## Concurrency test

Two threads/process-like clients attempt the same confirmation concurrently.

Expected:

```text
exactly one claim succeeds
exactly one write path can continue
```

## Regression tests

All current approval-backed workflows must remain green.

At minimum verify current project coverage for:

```text
Customer
Item
Quotation
Sales Order
Sales Invoice
Quotation -> Sales Order
Sales Order -> Sales Invoice
update/item-add
submit/cancel/delete
Purchase Order
email if approval-backed
```

## Contract tests

Verify public tool schemas and registered tool names remain unchanged.

---

# 20. Safe Runtime Verification

Prefer source inspection + tests.

If a live cache test is useful, it must:

- use a dedicated temporary key namespace;
- contain no business or approval token data;
- use a very short TTL;
- be deleted after the test;
- not modify ERP records;
- not flush Redis;
- not clear Frappe cache globally;
- not restart services;
- not change site config.

Example concept only:

```text
Task37 temporary key
Process/test context A -> set
Process/test context B -> get
cleanup
```

Do not perform this if a reliable isolated test can establish the behavior without touching live shared cache.

---

# 21. Forbidden Changes

Task 37 is audit-only.

Do not:

```text
edit mcp_erpnext production code
edit approval behavior
edit contracts
edit profiles
edit settings
change MCP_APPROVAL_MODE
change TTL
change public errors
change tool names
change schemas
create DocTypes
run migrations
change hooks
change site_config.json
change common_site_config.json
change Redis configuration
add Redis containers
install Redis packages
add Python dependencies
modify ERPNext
modify Frappe
modify India Compliance
create/update/delete ERP records
submit/cancel/delete documents
restart MCP/Frappe/Redis services
flush Redis
commit changes
```

You may create only the requested audit report in the repository documentation area if that is the established project convention.

---

# 22. Required Output

Create:

```text
docs/inspect/SHARED_APPROVAL_STORE_FRAPPE_CACHE_AUDIT.md
```

If the repository's established audit-report folder differs, use the existing convention and report the final actual path.

The report must contain:

1. Executive summary
2. Current ApprovalStore architecture
3. Current approval lifecycle
4. Approval call-site inventory
5. Current process-local limitation
6. Installed Frappe cache/Redis architecture
7. Frappe local-cache behavior
8. TTL behavior
9. Atomic primitive findings
10. Concurrency analysis
11. Security analysis
12. Failure / Redis-unavailable behavior
13. Public error semantics
14. Observability recommendation
15. Redis vs DocType comparison
16. STDIO/HTTP/multi-worker compatibility
17. Recommended target architecture
18. Exact files expected to change in Task 38
19. Exact files that must remain untouched
20. Required Task 38 tests
21. Risks / limitations
22. Final decision
23. Exact next task

---

# 23. Final Decision Format

End the audit with one of these explicit outcomes.

## Outcome A — Frappe native cache is sufficient

```text
DECISION:
Use the existing Frappe cache/Redis infrastructure.

No new Redis service.
No custom Redis connection.
No new approval DocType.

Implement shared approval persistence through the Frappe-native cache boundary.

Atomic claim will use:
<exact installed Frappe-native primitive>

Local request cache handling:
<exact decision>

TTL:
<exact decision>

Failure behavior:
fail closed

Public MCP contracts:
unchanged
```

## Outcome B — Frappe cache storage is sufficient but atomic claim needs a minimal adapter

```text
DECISION:
Use the existing Frappe configured Redis connection.

No new Redis service.
No custom Redis configuration.

Frappe's high-level cache helpers are sufficient for storage/TTL but do not expose
the atomic one-shot primitive required by ApprovalStore.

Use the smallest possible internal adapter around Frappe's existing RedisWrapper
connection for:
<exact atomic operation>

Explain why this does not create a parallel Redis architecture.
```

## Outcome C — Frappe cache is unsuitable

Only choose this if installed-source evidence proves it.

Document exactly why and propose the smallest alternative.

---

# 24. Acceptance Criteria

Task 37 is complete only when all are true:

- [ ] Actual current approval implementation inspected.
- [ ] Actual current approval TTL confirmed.
- [ ] Process-local behavior proven from source.
- [ ] All approval-backed business flows inventoried.
- [ ] Installed Frappe v16 cache implementation inspected.
- [ ] Official Frappe documentation/source referenced.
- [ ] Shared-worker behavior confirmed.
- [ ] Site namespacing behavior confirmed.
- [ ] Local request cache behavior confirmed.
- [ ] TTL behavior confirmed.
- [ ] Redis-unavailable behavior confirmed.
- [ ] Existing atomic claim semantics documented.
- [ ] At least one safe atomic shared-store strategy evaluated.
- [ ] Concurrent double-confirm scenario explicitly addressed.
- [ ] No custom Redis infrastructure proposed without proof of need.
- [ ] Redis vs DocType alternative evaluated.
- [ ] STDIO/HTTP/multi-process compatibility evaluated.
- [ ] Public contract impact documented.
- [ ] Observability improvements documented.
- [ ] Exact Task 38 file scope proposed.
- [ ] Exact Task 38 test plan proposed.
- [ ] No production behavior changed.
- [ ] Final audit report created.
- [ ] Final decision is explicit and evidence-backed.

---

# 25. Expected Result

The expected likely result is:

```text
Current:
ApprovalStore -> process-local memory

Target:
ApprovalStore -> Frappe-native shared cache -> Frappe configured Redis
```

with current prepare/confirm public APIs unchanged.

However, do not force this conclusion.

The audit must verify the installed Frappe implementation first.

The most important unresolved question is:

```text
What exact Frappe-native primitive should be used to preserve atomic
single-use claim/consume behavior across multiple MCP processes?
```

---

# 26. Limitations / Boundaries

This task does **not** redesign:

```text
Customer creation
Item creation
Quotation creation
Sales Order creation
Sales Invoice creation
Quotation -> Sales Order conversion
Sales Order -> Sales Invoice conversion
update mutation policies
item-add mutation policies
submit/cancel/delete policies
profile architecture
identity
HTTP authentication
stdio identity
LangGraph
LibreChat
Codex
Docker deployment
India Compliance
ERPNext validation
```

It audits only the approval-state persistence and claim boundary.

---

# 27. Exact Next Task

If the audit concludes that Frappe's existing cache foundation is suitable, the next task must be:

```text
Task 38 — Implement Frappe-Native Shared ApprovalStore
```

Task 38 should:

1. preserve the current `ApprovalStore` public/internal service interface where practical;
2. replace process-local approval state with the audited Frappe-native shared cache mechanism;
3. preserve the existing TTL;
4. preserve action/site/user/payload/trusted-approval binding;
5. preserve fail-closed behavior;
6. implement the audited atomic one-shot claim;
7. avoid any new Redis service/configuration;
8. avoid changes to business tool schemas;
9. add cross-instance and concurrency tests;
10. run the full MCP regression suite;
11. regenerate documentation/catalog only if required by existing project process;
12. produce an implementation report.

Do not start Task 38 during Task 37.
