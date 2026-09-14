# Task 40 — Implement the Remote ERPNext REST Backend

## Status

**Type:** Focused architecture-preserving implementation task  
**Project:** `mcp_erpnext`  
**Depends on:** Task 39 — Implement Frappe-Native Shared ApprovalStore  
**Primary area:** Backend selection, authenticated remote execution, and native ERPNext workflows  
**Public MCP contract changes:** Forbidden  
**Generic Frappe REST CRUD:** Forbidden  
**Remote-site schema / DocType changes:** Forbidden  

---

# 0. Task-number verification and source authority

This task is **Task 40**.

The current sequence is:

```text
Task 38 = Shared Approval Store / Frappe Cache Architecture Audit
Task 39 = Implement Frappe-Native Shared ApprovalStore
Task 40 = Implement the Remote ERPNext REST Backend
```

Task 39 is a hard prerequisite. A REST confirmation must be claimed, consumed,
and recorded by the remote ERPNext site. A local MCP process must not become a
second approval-token store.

The current working tree is authoritative. Before editing, re-open the actual
source and preserve all unrelated in-progress work. In particular, do not
assume that historical documentation still represents the latest approval
storage implementation.

---

# 1. Objective

Make this configuration operational:

```bash
MCP_BACKEND=rest
ERPNEXT_BASE_URL=https://erp.example.com
ERPNEXT_API_KEY=<configured-api-key>
ERPNEXT_API_SECRET=<configured-api-secret>
```

The local MCP process must keep its current public tool names, typed schemas,
profiles, interaction directives, and safe error envelopes. Instead of
initializing a local Frappe site and calling the ORM itself, it must send a
bounded authenticated request to the configured remote ERPNext site. The
remote `mcp_erpnext` application must execute the matching existing native
workflow inside that site's normal Frappe request context.

Target flow:

```text
MCP client
    |
    v
local mcp_erpnext MCP tool wrapper
    |
    +-- MCP_BACKEND=direct --> existing local Frappe/ORM service
    |
    +-- MCP_BACKEND=rest ----> authenticated HTTPS request
                                      |
                                      v
                              remote mcp_erpnext API bridge
                                      |
                                      v
                              existing native service / Frappe ORM
                                      |
                                      v
                              normal permissions, defaults, validation,
                              approval claim, transaction, and response
```

The REST backend is a **remote execution transport**, not a new business-rule
implementation. It must not duplicate ERPNext defaults, validation, document
lifecycle behavior, India Compliance behavior, or approval policy in the
local client.

---

# 2. Confirmed current gap

Current source has only the configuration vocabulary for REST:

```text
mcp_erpnext/settings.py
  MCP_BACKEND accepts direct or rest
  ERPNEXT_BASE_URL, ERPNEXT_API_KEY, ERPNEXT_API_SECRET are read from env
  validate() requires those three values when backend=rest

mcp_erpnext/runtime.py
  _ensure_context() rejects every backend other than direct
  error: REST backend is reserved for a future phase

mcp_erpnext/tools/**
  public wrappers use execute_tool_with_context(..., lambda: local service)

mcp_erpnext/services/**
  services use the local frappe module, frappe.local, permissions,
  metadata/defaults, document methods, and database transactions directly
```

No current REST client, endpoint/handler registry, remote authentication
implementation, or REST integration test exists. The references to REST in
`.env.example`, `README.md`, and `docs/MCP_SETUP.md` are future-boundary
documentation, not a working backend.

---

# 3. Non-goals and security boundary

This task must not:

- call Frappe's generic `/api/resource/<DocType>` endpoint for MCP workflows;
- reconstruct document payloads, pricing, defaults, or lifecycle behavior in
  the local REST client;
- add arbitrary method invocation, arbitrary DocType access, arbitrary SQL, or
  an unrestricted proxy endpoint;
- add `ignore_permissions=True`, bypass normal document hooks, or expose a
  client-selected Frappe user;
- expose API credentials, authorization headers, approval tokens, or request
  business payloads in logs, errors, tool output, documentation examples, or
  generated catalog output;
- change public MCP tool names, input/output schemas, profile inventories, or
  `InteractionDirective` semantics;
- add a per-tool approval-policy branch or a public approval-policy argument;
- enable REST merely by deleting the existing `backend != "direct"` guard.

`MCP_TRANSPORT=streamable-http` and `MCP_BACKEND=rest` are different choices:

```text
MCP_TRANSPORT = how an MCP client connects to this MCP process
MCP_BACKEND   = how this MCP process reaches ERPNext
```

Do not treat the existing local Streamable HTTP shared secret as authorization
to operate a remote ERPNext site.

---

# 4. Frozen architecture decision

Use one narrow, application-owned remote API bridge. The bridge is part of
`mcp_erpnext`, is installed on the remote ERPNext site, and dispatches only a
static registry of already-public MCP operations.

```text
Local client                         Remote ERPNext site
------------                         -------------------
typed MCP wrapper                    Frappe API method
  -> backend dispatcher                 -> fixed handler registry
       -> REST client                     -> existing service function
          POST /api/method/...              -> normal Frappe ORM behavior
```

The remote bridge is required because existing services are intentionally
Frappe-native. It gives the remote site—not the local client—the authority for:

```text
Frappe request user and permissions
site metadata and defaults
document/controller methods and hooks
India Compliance integration
approval creation, trusted transition, cancellation, and atomic claim
database commit / rollback
final response shape
```

## Required remote method properties

The exact import path may be chosen after inspecting the current package, but
the remote method must:

- be a Frappe whitelisted method that requires normal Frappe API-token
  authentication; it must not be guest-accessible;
- accept exactly a bounded request envelope, such as an explicit operation
  identifier and JSON object arguments;
- resolve the operation through a static allowlist/registry—never import or
  call a name supplied by the request;
- validate the operation payload using the same internal typed models or
  explicit adapters used by the public MCP wrappers;
- invoke the existing service/native implementation, not reimplement it;
- return only JSON-compatible values validated against the same response
  contract used at the MCP boundary;
- reject unknown operations, extra top-level envelope fields, non-object
  arguments, malformed JSON, missing authentication, and unauthorized Frappe
  users without falling back to another identity;
- leave approval tokens in the remote site's shared ApprovalStore; and
- avoid logging request arguments, tokens, authorization data, or secret
  values.

The endpoint is an internal transport boundary, not a second public business
API. It must not be listed as an MCP tool.

---

# 5. REST principal and identity policy

Initial REST support is limited to the Frappe user who owns
`ERPNEXT_API_KEY`/`ERPNEXT_API_SECRET` on the remote site.

```text
ERPNext API token authentication
    -> remote Frappe session user
    -> existing Frappe permission checks
    -> ApprovalStore token user binding
```

This preserves normal Frappe authorization for a configured service/API user.
It does **not** safely preserve a distinct browser/HTTP caller identity across
the new network boundary; the present REST configuration has no authenticated,
replay-resistant delegation protocol for that purpose.

Therefore, until a separately approved identity-delegation design exists:

- REST must not trust `X-MCP-User-Email`, `MCP_FRAPPE_USER`, a tool argument,
  or any client-provided user value as the remote execution user;
- REST + local Streamable HTTP must either be rejected during startup or be
  explicitly documented and tested as operating solely as the configured
  remote API principal; choose the safer behavior after inspecting all current
  identity paths;
- the approval token's `user` must be the remote authenticated Frappe API user;
- documentation must state this distinction plainly.

Do not silently weaken the existing request-scoped HTTP identity guarantee.
A future task may introduce a narrowly designed, signed delegation mechanism
only after an architecture audit and explicit approval.

---

# 6. Mandatory source and deployment verification before editing

Before implementation, inspect and report the current equivalents of:

```text
mcp_erpnext/settings.py
mcp_erpnext/runtime.py
mcp_erpnext/mcp_server.py
mcp_erpnext/http_transport.py
mcp_erpnext/observability.py
mcp_erpnext/approvals.py
mcp_erpnext/tools/**
mcp_erpnext/profiles/**
mcp_erpnext/contracts/**
mcp_erpnext/services/**
mcp_erpnext/tests/test_runtime.py
mcp_erpnext/tests/test_http_transport.py
mcp_erpnext/tests/test_identity.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_profiles.py
docs/TOOLS.md
docs/COMMANDS.md
docs/MCP_SETUP.md
README.md
```

Also inspect, as installed runtime authority, the remote Frappe version's API
token authentication and whitelisted-method dispatch path. Confirm with source
or a safe authenticated test that:

```text
Authorization: token <api-key>:<api-secret>
    -> authenticated Frappe session user
    -> normal permissions
    -> whitelisted method invocation
```

Do not assume the deployed remote site has the same app version, enabled app,
or endpoint route as the local checkout. Record the exact deployment/version
compatibility requirement before enabling REST.

---

# 7. Operation inventory and registry — mandatory first implementation step

Generate the operation inventory from the current profile registrations and
MCP `tools/list`; do not copy a stale historical tool count into source.

For every currently public tool in each profile, record:

```text
public tool name
profile
typed input contract
typed output contract
current wrapper
canonical service/operation entrypoint
read / prepare / confirm-write / lifecycle / PDF / email classification
required remote permission behavior
approval action, when applicable
```

Create one reviewed static registry shared by the direct/REST dispatch layer
and remote API bridge. The registry must bind a stable operation identifier to
an explicit handler; it must never derive a Python import path, DocType, or
method name from caller input.

Illustrative shape only:

```text
"prepare_sales_order"
  -> profile: sales
  -> request adapter: explicit typed model
  -> direct handler: existing prepare Sales Order service
  -> remote handler: same existing prepare Sales Order service
  -> response adapter: existing typed result model
```

The final implementation may use a different internal module layout, but all
public wrappers must retain their current typed contract behavior.

## Required classification

The implementation report must classify handlers at least as:

```text
read-only
prepare-without-write
confirm-write
existing-document lifecycle write
PDF generation
email queueing write
```

This prevents a read-only proxy shortcut from accidentally changing a write
operation's confirmation or transaction semantics.

---

# 8. Client transport requirements

Create a dedicated internal REST client. Do not place HTTP code inside every
tool wrapper or service.

The client must:

- use `ERPNEXT_BASE_URL` only after strict validation: absolute `https` URL by
  default, no embedded credentials, no query/fragment, and no path traversal;
- build the configured remote API-method path without allowing caller-controlled
  paths or redirects to alter the target;
- send Frappe API-token authentication only in the request Authorization
  header, never the URL or payload;
- use explicit finite connect/read/total timeouts and no infinite retry loop;
- disable redirects or validate every redirect against the original approved
  HTTPS origin before sending credentials;
- apply bounded retries only to demonstrably safe transport failures on
  read-only and prepare operations;
- never automatically retry a confirm-write, lifecycle write, or email queue
  request after an ambiguous network failure;
- map connection, timeout, malformed-response, remote 5xx, authentication,
  and permission failures into existing safe response/error conventions without
  leaking remote internals;
- preserve a remote response's stable domain result/status/code when the
  response validates; and
- require a JSON object response and reject unexpected response shapes
  fail-closed.

Do not assume a particular HTTP dependency. Inspect the project/runtime first;
add a dependency only when the user separately approves it. The implementation
may use a suitable already-installed standard/runtime-supported client if it
can meet the timeout, TLS, and testability requirements.

---

# 9. Direct and REST dispatch boundary

Refactor only enough to make backend selection explicit at the shared internal
boundary. The intended shape is:

```text
public typed MCP wrapper
    -> validate public input
    -> build bounded canonical operation payload
    -> backend dispatcher
         direct: initialize local Frappe context and call existing handler
         rest:   call remote bridge with same operation/payload
    -> validate existing typed output
```

Rules:

- Direct mode must continue to call the current local workflow and retain its
  current behavior.
- REST mode must never call `frappe.init()`, `frappe.connect()`, local
  `frappe.db`, or direct ERPNext services in the local client process.
- The remote bridge must be the only REST caller of the direct services.
- Do not serialize a Python callable, Frappe document, exception object, or
  request context across the network.
- The generic dispatcher must carry the explicit tool/operation identifier and
  canonical JSON-safe payload. It must not rely on closure introspection.
- `execute_tool_with_context()` and observability behavior may be refactored,
  but all errors must retain the existing safe public boundary.

Do not change the direct backend merely to make it resemble REST.

---

# 10. Approval, transaction, and idempotency requirements

For every prepare/confirm pair and lifecycle/email write:

```text
prepare request -> remote native service -> remote ApprovalStore token
confirm request -> same remote site -> atomic remote approval claim -> native write
```

Required rules:

- A REST approval token is site-bound, action-bound, payload-bound, user-bound,
  expiring, cancellable, and single-use under Task 39 semantics.
- The local MCP process must not deserialize, mutate, trust, or store approval
  records.
- The remote service owns commit/rollback and the existing post-claim failure
  behavior. The REST client must not issue a compensating document write.
- An ambiguous connection failure after a write must return a safe uncertain
  failure; it must not retry automatically or claim that a document was not
  created.
- Repeating a delivered confirm request must preserve the current remote
  idempotency/replay semantics.
- No endpoint may treat an LLM/UI `confirm=true` as a trusted-human approval
  token or bypass `ApprovalStore.claim_for_confirm_write()`.

Task 40 relies on Task 39's shared remote storage; it must not resurrect a
process-local fallback or use local memory in tests as a production fallback.

---

# 11. Remote error and response contract

The remote bridge must return a stable, JSON-safe application envelope for
transport failures. It must not return Python tracebacks, Frappe exception
messages, raw SQL, headers, credentials, or implementation paths.

Required handling:

```text
unknown/disallowed operation      -> bounded remote request error
invalid envelope/payload          -> bounded validation error
remote API authentication failure -> local safe authentication/configuration error
remote Frappe PermissionError     -> existing stable permission result
remote validation/business result -> existing domain result/output model
timeout/network failure           -> safe retryability only where operation is safe to retry
malformed remote response         -> safe remote protocol error
```

Use a correlation reference that is safe to expose. Correlate local and remote
logs without putting approval tokens, business payloads, or credentials into
either log. Reuse the project's existing observability conventions where they
fit; do not create a separate error format for one REST tool.

---

# 12. Required production changes

The exact filenames must follow the current source layout, but a complete
implementation is expected to include narrowly scoped equivalents of:

```text
mcp_erpnext/settings.py
  - REST URL validation and selected-backend validation
  - explicit REST identity/transport compatibility policy

mcp_erpnext/runtime.py or a dedicated backend dispatcher
  - direct vs REST execution selection
  - no local Frappe initialization in REST mode

mcp_erpnext/rest_client.py (or current-layout equivalent)
  - bounded authenticated remote request client

mcp_erpnext/remote_api.py (or current-layout equivalent)
  - whitelisted fixed remote method and static handler registry

mcp_erpnext/tools/** and/or shared wrapper helpers
  - minimal canonical-operation payload handoff, retaining public schemas

mcp_erpnext/observability.py
  - only if needed to map safe REST transport/protocol failures consistently

mcp_erpnext/tests/**
  - focused unit, contract, and integration-style transport coverage

.env.example
README.md
docs/MCP_SETUP.md
docs/COMMANDS.md (only if a reusable project-specific REST command is added)
docs/TOOLS.md (only if generated catalog behavior changes)
```

Do not add a DocType, migration, site hard-code, custom permission bypass, or
generic REST router.

---

# 13. Required tests

Tests must be hermetic unless the user separately authorizes a real remote
site. Mock at the HTTP boundary and use the existing Frappe/service seams.

## Settings and startup tests

Cover at least:

```text
direct remains the default
unknown backend is rejected
rest without each required setting is rejected without echoing a secret
invalid/non-HTTPS/credential-bearing REST base URL is rejected
selected REST identity/Streamable-HTTP policy is enforced
direct startup behavior remains unchanged
```

## Client tests

Cover at least:

```text
fixed API-method URL construction
Authorization header construction without output/log leakage
finite timeout configuration
redirect refusal/origin protection
request JSON envelope shape
network timeout / connection failure mapping
401/403/5xx response mapping
malformed/non-object JSON response rejection
read/prepare safe retry boundary, if retries are implemented
no retry for confirm, lifecycle write, or email write
```

## Remote bridge tests

Cover at least:

```text
method is not guest-accessible
API-token authenticated user is the Frappe execution user
unknown operation is rejected
extra envelope field is rejected
non-object or malformed arguments are rejected
operation registry is profile-aware and static
handler calls the existing canonical service path
result is JSON-safe and contract-valid
Frappe PermissionError retains the stable safe permission result
no token/payload/secret appears in logs or returned failure
```

## Workflow regression tests

For every operation category represented by the inventory, test direct and
REST dispatch using the same canonical request/response fixture. At minimum:

```text
one read operation
one prepare-without-write operation
one confirm-write operation
one existing-document lifecycle action
one PDF operation
one email-queue operation
Sales and Purchase profile allowlist behavior
```

For a confirm-write regression, assert:

```text
prepare remotely -> token originates remotely
confirm remotely -> exactly one native write
wrong remote user/action/site -> fail closed
repeat/parallel confirm -> no duplicate write
ambiguous client timeout -> no automatic second write
```

Run focused tests first, then the full app suite only with explicit execution
permission. Report static/unit results separately from any authenticated remote
site verification.

---

# 14. Documentation and operational requirements

Update documentation only after the implementation is verified against current
source. It must state:

- REST is available only when the remote ERPNext site has the compatible
  `mcp_erpnext` app/version installed and enabled;
- the API key/secret identify the remote Frappe principal; they are not an
  end-user impersonation mechanism;
- deployment configuration uses neutral placeholders such as `BENCH_ROOT`,
  remote origin, and a configured API user—never personal paths or real
  credentials;
- REST requires HTTPS in normal deployment;
- direct and REST backend selection is distinct from stdio/Streamable HTTP
  MCP transport;
- no generic ERPNext resource endpoint is supported;
- remote approval state and writes occur on the remote ERPNext site;
- a confirm-write network uncertainty must be investigated through the remote
  site/record before retrying; and
- exact tests performed versus unverified remote deployment boundaries.

If the task creates a reusable local/remote start, inspection, or test command,
add only that project-specific command to `docs/COMMANDS.md` after verifying it.
Never document a real secret, token, or site name.

---

# 15. Forbidden changes

The following are specifically forbidden:

```text
generic /api/resource DocType CRUD for MCP workflows
arbitrary api/method forwarding
caller-chosen Python function/module/DocType names
client-side ERPNext defaults, pricing, validation, or document construction
ignore_permissions=True
frappe.set_user() from caller-provided REST data
MCP_FRAPPE_USER as a REST authorization fallback
unbounded retries or confirm-write retry
logging Authorization headers, keys, secrets, approval tokens, or full payloads
REST endpoint guest access
new public MCP tools, aliases, or tool-specific approval modes
database schema / DocType changes
unrelated direct-service refactors
```

---

# 16. Acceptance criteria

Task 40 is complete only when all of the following are true:

1. `MCP_BACKEND=direct` remains behaviorally compatible with the current
   direct backend.
2. `MCP_BACKEND=rest` with valid non-secret configuration reaches a fixed,
   authenticated remote `mcp_erpnext` API bridge.
3. The remote bridge executes the existing native workflow as its authenticated
   Frappe API user, with normal permissions and no bypass.
4. Every current public tool/profile operation is either supported through the
   static inventory or REST is fail-closed before registration; no tool is
   silently redirected to unsupported generic CRUD.
5. Direct and REST paths expose the same public MCP names, typed schemas,
   interaction directives, and validated result shapes.
6. REST prepare/confirm, lifecycle, PDF, and email behavior preserves current
   native service boundaries.
7. Approval records and writes remain remote-site owned; Task 39 atomic claim
   semantics are verified for remote confirms.
8. The REST client cannot follow an untrusted redirect, use a caller-controlled
   target, retry an ambiguous write, or expose a secret.
9. The REST identity policy is enforced and documented; no header or tool
   argument silently impersonates a remote Frappe user.
10. Focused static/unit tests pass, and authenticated remote verification is
    reported separately with exact environment-safe evidence.
11. Documentation accurately changes REST from “future boundary” to its actual
    supported scope only after the preceding criteria are met.

---

# 17. Required implementation report

Create a report under `docs/inspect/` after implementation. It must include:

```text
current branch and worktree status before edits
Task 39 prerequisite evidence
remote app/version deployment requirement
operation inventory and handler mapping
chosen REST identity policy and its limitation
exact source files changed
direct versus REST dispatch trace
remote authentication and permission trace
approval/transaction/idempotency trace
timeout/retry/redirect decisions
focused and full test commands/results
authenticated remote-site verification, if performed
what was not live-verified
security review of credentials, payloads, redirects, and impersonation
```

Do not claim a remote site was contacted, authenticated, or wrote a document
unless that occurred and the evidence is recorded without sensitive data.

---

# 18. Known limitation and explicit follow-up

This task deliberately supports a configured remote Frappe API principal, not
end-user delegation through a local Streamable HTTP client. That is the only
model supported by the current REST settings.

If a future product requirement needs a remote action to execute as the
individual authenticated browser user, create a separate architecture audit
before implementation. It must define credential issuance, signed assertions,
audience/site binding, expiry/replay handling, revocation, request identity
verification, audit logging, and the approval-token user binding. Do not fold
that design into Task 40.
