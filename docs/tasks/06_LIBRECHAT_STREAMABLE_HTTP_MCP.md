# Task 06 — LibreChat Streamable HTTP MCP + Request-Scoped Identity

## Scope

Add a Streamable HTTP transport to the existing `mcp_erpnext` server so LibreChat running in Docker can call the MCP server running in the WSL/Frappe environment.

Preserve the existing STDIO server and all current ERPNext tools.

Implement **Task 06 only**. Do not build a LibreChat Agent yet.

---

## Objective

Target flow:

```text
LibreChat local user
        ↓
LibreChat API container
        ↓
Streamable HTTP MCP
Authorization: Bearer <shared-secret>
X-LibreChat-User-ID: <authenticated LC user id>
X-LibreChat-User-Email: <reference only>
        ↓
mcp_erpnext in WSL
        ↓
Task 05 mapping
LC User ID → Frappe User
        ↓
frappe.set_user(mapped_user)
        ↓
existing ERPNext MCP tools
        ↓
normal Frappe permissions
```

The HTTP server must safely serve different LibreChat users without user-context leakage.

---

# Starting State / Dependencies

Task 05 is already implemented.

Before editing, inspect the current post-Task-05 source and confirm the actual implementation of:

```text
mcp_erpnext/settings.py
mcp_erpnext/runtime.py
mcp_erpnext/identity.py or equivalent
mcp_erpnext/mcp_server.py
mcp_erpnext/approvals.py
LibreChat User Mapping DocType
current tests
current MCP SDK dependency/version
```

Do not duplicate Task 05 logic if its names/structure differ from this task.

Current expected tools must remain:

```text
search_customers
resolve_customer
prepare_customer
confirm_customer

search_items
resolve_item
prepare_item
confirm_item

prepare_sales_order
confirm_sales_order

prepare_quotation
confirm_quotation
```

---

# Architecture Decision

## Existing transport — preserve

```text
VS Code / MCP Inspector
        ↓
STDIO
        ↓
mcp_erpnext
```

Existing command must continue to work:

```bash
python -m mcp_erpnext.mcp_server
```

With no new transport setting, it must still use STDIO.

## New transport

```text
LibreChat Docker
        ↓
http://host.docker.internal:8765/mcp
        ↓
Streamable HTTP MCP
        ↓
mcp_erpnext
```

Reuse the same MCP server/tool registry. Do not create duplicate HTTP versions of the tools.

For Task 06:

```text
Streamable HTTP + MCP_IDENTITY_MODE=librechat   ✅
Streamable HTTP + MCP_IDENTITY_MODE=service     ❌ reject
```

Do not expose an HTTP MCP endpoint that executes every caller as one service user.

---

# Security Rules

Mandatory:

```text
1. HTTP transport requires a shared secret.
2. Use Authorization: Bearer <secret>.
3. Validate secret before ERP/Frappe tool execution.
4. Use constant-time comparison such as hmac.compare_digest.
5. Minimum project secret length: 32 characters.
6. Never log the secret or Authorization header.
7. X-LibreChat-User-ID is authoritative only after transport auth succeeds.
8. X-LibreChat-User-Email is diagnostic only.
9. Never authorize by email fallback.
10. Never let the LLM/tool argument choose Frappe user/role/run_as.
11. HTTP mode must never fall back to MCP_FRAPPE_USER.
12. HTTP mode must never fall back to process-env MCP_LIBRECHAT_USER_ID.
13. Mapping failure must fail closed.
14. No ignore_permissions=True.
15. No permission bypass through frappe.get_all() for business data.
16. No automatic Frappe User creation.
17. Existing OAuth/OpenID work remains untouched.
18. Do not use wildcard HTTP allowed-host protection.
```

---

# Phase 1 — Inspect MCP SDK Before Coding

Inspect the installed MCP Python SDK version/API from the project dependency files and imports.

Confirm how the installed version supports:

```text
Streamable HTTP server
request Context injection
request headers
ASGI/Starlette app if needed
transport-security / allowed-host configuration
```

Use the project's installed official MCP SDK API.

Do not upgrade/switch MCP libraries unless Streamable HTTP is genuinely unavailable. If an upgrade is required, stop and report the reason first.

Request Context must remain SDK-injected and invisible to the model/tool schema.

---

# Phase 2 — Transport Configuration

Extend the existing settings layer.

Recommended environment contract:

```dotenv
# default
MCP_TRANSPORT=stdio

# HTTP mode
MCP_HTTP_HOST=127.0.0.1
MCP_HTTP_PORT=8765
MCP_HTTP_PATH=/mcp
MCP_HTTP_SHARED_SECRET=
MCP_HTTP_ALLOWED_HOSTS=127.0.0.1:8765,localhost:8765
```

Rules:

```text
MCP_TRANSPORT absent
    → stdio

valid transport values
    → stdio
    → streamable-http

unknown transport
    → deterministic configuration error

HTTP shared secret
    → required
    → >= 32 characters

HTTP port
    → valid integer port

HTTP path
    → default /mcp

HTTP host
    → default 127.0.0.1
```

For the current Docker ↔ WSL development bridge, docs may explicitly use:

```text
MCP_HTTP_HOST=0.0.0.0
```

but do not make that the silent default.

---

# Phase 3 — Add Streamable HTTP Transport

Prefer the smallest structure matching the current source.

Possible layout:

```text
mcp_erpnext/mcp_server.py
mcp_erpnext/http_transport.py     # new only if useful
```

Required behavior:

```text
MCP_TRANSPORT=stdio
    → existing STDIO run path

MCP_TRANSPORT=streamable-http
    → same MCP server object
    → Streamable HTTP endpoint
    → default /mcp
```

Do not implement a custom REST API around MCP tools. The endpoint must remain MCP Streamable HTTP.

If authentication requires an ASGI/Starlette wrapper around the MCP SDK app, use a minimal wrapper. Do not duplicate tool registration.

---

# Phase 4 — Authenticate HTTP Requests

Add a narrow transport authentication layer:

```text
request
  ↓
Authorization header?
  ├─ no → HTTP 401
  ↓
Bearer format valid?
  ├─ no → HTTP 401
  ↓
constant-time compare to MCP_HTTP_SHARED_SECRET
  ├─ fail → HTTP 401
  ↓
continue MCP processing
```

Authentication failure must happen before ERP business logic.

Safe log:

```text
MCP HTTP authentication failed
```

Never log:

```text
Bearer value
configured secret
full Authorization header
```

---

# Phase 5 — Request-Scoped LibreChat Identity

Task 05 STDIO LibreChat mode may keep using process environment identity.

HTTP mode must not.

Read these headers fresh for each MCP tool request:

```text
X-LibreChat-User-ID
X-LibreChat-User-Email
```

Use MCP SDK request Context/header access available in the installed version.

Conceptually only:

```python
@mcp.tool()
def search_customers(..., ctx: Context):
    headers = ctx.headers or {}
```

The SDK Context parameter must **not** appear in `tools/list` input schema.

Do not add model-visible arguments such as:

```text
librechat_user_id
frappe_user
run_as
role
```

Prefer an internal object such as:

```text
RuntimeIdentity
    source = librechat_http
    librechat_user_id
    librechat_user_email
```

Pass this to the runtime/identity layer only.

Do not pass raw HTTP request objects into domain services.

---

# Phase 6 — Extend Task 05 Mapping Resolver

Reuse the Task 05 resolver.

Required behavior:

```text
STDIO + service
    → existing MCP_FRAPPE_USER flow

STDIO + librechat
    → Task 05 LC ID env flow

HTTP + librechat
    → request X-LibreChat-User-ID
```

HTTP identity source must be explicit so it cannot accidentally fall back to env values.

For HTTP:

```text
missing LC ID
    → ERP_IDENTITY_CONFIGURATION_ERROR or existing safe equivalent

unmapped LC ID
    → ERP_ACCESS_NOT_CONFIGURED

disabled mapping
    → ERP_ACCESS_NOT_CONFIGURED

missing/disabled/Guest linked Frappe User
    → ERP_ACCESS_NOT_CONFIGURED
```

Even if environment contains:

```text
MCP_FRAPPE_USER=Administrator
MCP_LIBRECHAT_USER_ID=some-other-user
```

HTTP execution must use only the authenticated request identity.

---

# Phase 7 — Request-Scoped Frappe Runtime

The HTTP server is persistent and may serve multiple users.

Every HTTP ERP tool invocation must get a clean Frappe runtime scope:

```text
HTTP request identity
        ↓
initialize selected Frappe site
        ↓
frappe.connect(set_admin_as_user=False)
        ↓
resolve LC ID → Frappe User
        ↓
frappe.set_user(mapped_user)
        ↓
execute existing service
        ↓
finally cleanup Frappe request context
```

Use current supported Frappe lifecycle functions already compatible with the app, including `frappe.destroy()` or equivalent scoped cleanup where appropriate.

Cleanup must occur:

```text
on success ✅
on exception ✅
```

Do not store current LC/Frappe user in an ordinary module-level mutable global.

MCP initialization and `tools/list` should not initialize the ERP DB unnecessarily. Bind Frappe runtime at ERP tool execution time.

### Isolation requirement

```text
HTTP A → LC-A → Frappe-A
HTTP B → LC-B → Frappe-B
```

B must never see `frappe.session.user == Frappe-A`.

A must never see B's user/permission caches.

---

# Phase 8 — Tool Wrapper Integration

Keep the domain services unaware of LibreChat.

Target layering:

```text
MCP tool wrapper
    ↓
SDK request Context
    ↓
transport identity extractor
    ↓
runtime scope / Task 05 mapping
    ↓
existing domain service
```

If all registered tools need an injected SDK `Context`, update their wrappers consistently.

Verify their public input schemas remain unchanged.

Do not add header parsing to:

```text
Customer service
Item service
Quotation service
Sales Order service
field resolver
approval store
```

---

# Phase 9 — Transaction / Cleanup Audit

Before using per-call `frappe.destroy()`, inspect confirmed write paths:

```text
confirm_customer
confirm_item
confirm_quotation
confirm_sales_order
```

Confirm successful writes persist with the existing direct runtime transaction design.

Do not add broad auto-commit.

Required outcome:

```text
search/read
    → no arbitrary commit

prepare
    → no final business document persistence

confirm success
    → authorized write persists

exception
    → no unintended partial write
```

If proper HTTP cleanup exposes that existing confirms relied on a long-lived uncommitted connection, add only the minimum transaction-finalization correction required and explain it.

Do not change business rules.

---

# Phase 10 — Approval Isolation

Preserve existing user-bound approval behavior:

```text
LC-A → Frappe-A → prepare → token A
LC-B → Frappe-B → confirm token A → denied
```

Approval storage is currently process-local.

Therefore Task 06 HTTP deployment must use:

```text
one process
one worker
```

Do not add multi-worker deployment yet.

Do not redesign approval persistence/TTL.

---

# Phase 11 — Tests

Add focused tests in the nearest existing test files; create new files only where cleaner.

## Transport compatibility

```text
[ ] missing MCP_TRANSPORT defaults to stdio
[ ] explicit stdio keeps old behavior
[ ] invalid transport fails deterministically
[ ] existing STDIO service-user tests pass
[ ] current tool catalog remains unchanged
```

## HTTP configuration/auth

```text
[ ] HTTP requires MCP_IDENTITY_MODE=librechat
[ ] HTTP rejects service mode
[ ] missing shared secret rejected
[ ] secret shorter than 32 chars rejected
[ ] invalid port rejected
[ ] no Authorization → 401
[ ] malformed Authorization → 401
[ ] wrong secret → 401
[ ] correct secret → request may proceed
[ ] secret not present in logs/errors
```

## Request identity

```text
[ ] HTTP LC ID read from current request
[ ] email-only request does not authorize
[ ] missing LC ID fails closed
[ ] HTTP ignores MCP_LIBRECHAT_USER_ID env fallback
[ ] HTTP ignores MCP_FRAPPE_USER fallback
[ ] LC-A maps to Frappe-A
[ ] LC-B maps to Frappe-B
[ ] LC-C unmapped → ERP_ACCESS_NOT_CONFIGURED
[ ] disabled mapping/user rejected
[ ] Guest rejected
```

## Tool schema

```text
[ ] SDK Context is not model-visible
[ ] librechat_user_id is not a tool argument
[ ] frappe_user/run_as/role are not tool arguments
[ ] existing tool schemas otherwise remain compatible
```

## Frappe isolation

```text
[ ] request A sees Frappe-A
[ ] request B sees Frappe-B
[ ] A then B has no user leak
[ ] B then A has no user leak
[ ] concurrent A/B calls do not cross identities
[ ] cleanup runs after success
[ ] cleanup runs after exception
```

Where full ERP integration is heavy, use mocks for the concurrency unit test while keeping one development-site integration verification for real permission behavior.

## Approval/write regression

```text
[ ] A token cannot be confirmed by B
[ ] A can confirm its own valid token
[ ] prepare remains non-persistent
[ ] confirmed test write persists correctly
[ ] exception path has no unintended partial write
```

Do not create production records in tests.

---

# Phase 12 — Documentation

Update existing concise docs:

```text
.env.example
README.md
docs/ERPNext_MCP_ARCHITECTURE.md
docs/CODEX_MCP_SETUP.md
```

Optionally add one focused file:

```text
docs/LIBRECHAT_MCP_HTTP_SETUP.md
```

Do not create a long implementation diary.

### `.env.example`

Document both transports with fake values only:

```dotenv
MCP_TRANSPORT=stdio
MCP_BACKEND=direct
MCP_FRAPPE_SITE=your-site.localhost

# STDIO service mode
MCP_IDENTITY_MODE=service
MCP_FRAPPE_USER=mcp-service@example.com

# HTTP LibreChat example
# MCP_TRANSPORT=streamable-http
# MCP_IDENTITY_MODE=librechat
# MCP_HTTP_HOST=127.0.0.1
# MCP_HTTP_PORT=8765
# MCP_HTTP_PATH=/mcp
# MCP_HTTP_SHARED_SECRET=<minimum-32-character-secret>
# MCP_HTTP_ALLOWED_HOSTS=127.0.0.1:8765,localhost:8765,host.docker.internal:8765
```

Do not include a real secret.

---

# Required Operator Setup Documentation

Document this WSL development startup, but do not run it automatically:

```bash
export MCP_BACKEND=direct
export MCP_FRAPPE_SITE=yob.localhost
export MCP_IDENTITY_MODE=librechat
export MCP_TRANSPORT=streamable-http
export MCP_HTTP_HOST=0.0.0.0
export MCP_HTTP_PORT=8765
export MCP_HTTP_PATH=/mcp
export MCP_HTTP_SHARED_SECRET='<strong-development-secret>'
export MCP_HTTP_ALLOWED_HOSTS='host.docker.internal:8765,localhost:8765,127.0.0.1:8765'

cd /home/frappe/frappe-bench/sites
../env/bin/python -m mcp_erpnext.mcp_server
```

Docs must state:

```text
0.0.0.0 is explicit for current Docker ↔ WSL development only.
Do not expose the plain-HTTP endpoint publicly.
Use firewall/network controls.
Run one MCP process/worker only.
Do not set MCP_LIBRECHAT_USER_ID for HTTP identity.
```

---

# Required LibreChat Config Example

Do not modify the LibreChat repository in this task.

Document this example for the operator:

```yaml
mcpSettings:
  allowedAddresses:
    - "host.docker.internal:8765"

mcpServers:
  erpnext:
    type: streamable-http
    url: "http://host.docker.internal:8765/mcp"
    headers:
      Authorization: "Bearer ${MCP_HTTP_SHARED_SECRET}"
      X-LibreChat-User-ID: "{{LIBRECHAT_USER_ID}}"
      X-LibreChat-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    timeout: 120000
```

LibreChat `.env` must contain the same secret value:

```dotenv
MCP_HTTP_SHARED_SECRET=<same-secret-used-by-WSL-MCP-process>
```

Do not add:

```text
X-Frappe-User
X-LibreChat-User-Role
run_as
Administrator
```

Frappe roles/permissions come from the mapped Frappe User.

The current LibreChat deployment already has the required `librechat.yaml` mount and `host.docker.internal:host-gateway`; do not rewrite those existing settings.

---

# Files Allowed to Change

Adapt paths to the actual post-Task-05 repo:

```text
mcp_erpnext/mcp_server.py
mcp_erpnext/settings.py
mcp_erpnext/runtime.py
mcp_erpnext/identity.py
mcp_erpnext/observability.py

mcp_erpnext/http_transport.py            # new if useful
mcp_erpnext/transport_identity.py         # new if useful

relevant existing tests
mcp_erpnext/tests/test_http_transport.py  # new if useful

.env.example
README.md
docs/ERPNext_MCP_ARCHITECTURE.md
docs/CODEX_MCP_SETUP.md
docs/LIBRECHAT_MCP_HTTP_SETUP.md          # optional
```

Minimal transaction-finalization edits to current confirm-service files are allowed only if Phase 9 proves they are needed for safe HTTP request cleanup.

---

# Do Not Change

```text
LibreChat source
LibreChat OpenID/OAuth patch
LibreChat login system
OpenAI/model configuration
Agent Builder
LangGraph/coordinator design
current MCP tool names
Customer/Item business rules
Quotation/Sales Order business rules
field resolver semantics
Task 05 mapping schema
Frappe role/User Permission configuration
REST backend placeholder
approval TTL/design
```

Do not split capabilities into multiple MCP servers.

---

# Do Not Run Without Operator Permission

Do not automatically run:

```text
bench migrate
bench install-app/uninstall-app
bench update
real ERP document creation
real user/role/permission changes
Docker restart/recreate
LibreChat restart
firewall changes
port-forwarding changes
system service creation
```

Task 06 should not require a migration if Task 05 is already migrated.

Safe unit/source tests may run.

---

# Acceptance Criteria

```text
[ ] STDIO remains default and working
[ ] Streamable HTTP added without duplicate tools
[ ] /mcp default endpoint works
[ ] HTTP settings validated

[ ] HTTP requires strong shared secret
[ ] invalid/missing Bearer rejected before tools
[ ] secret not logged
[ ] allowed-host protection is explicit
[ ] HTTP service-user mode rejected

[ ] HTTP identity is request-scoped LC User ID
[ ] email is diagnostic only
[ ] no env/service-user fallback in HTTP mode
[ ] Task 05 mapping reused
[ ] mapped user becomes frappe.session.user
[ ] missing/disabled mapping fails closed

[ ] no identity fields added to tool schemas
[ ] domain services remain unaware of HTTP/LibreChat
[ ] normal Frappe permissions remain authoritative

[ ] Frappe context cleaned after every HTTP tool call
[ ] sequential users do not leak
[ ] concurrent users do not leak

[ ] prepare/confirm behavior preserved
[ ] confirmed writes persist correctly
[ ] no broad auto-commit introduced
[ ] approval tokens remain user-bound
[ ] one-process/one-worker boundary documented

[ ] existing regression tests pass
[ ] Task 05 tests pass
[ ] new HTTP/auth/identity tests pass

[ ] .env.example updated
[ ] WSL startup documented
[ ] LibreChat YAML documented
[ ] existing OAuth/OpenID work untouched
[ ] no Agent work started
```

---

# Manual Verification After Implementation

Stop before changing the operator's running environment. Provide these steps.

## 1. Start WSL MCP HTTP server

Using the documented environment values, expected endpoint:

```text
http://host.docker.internal:8765/mcp
```

## 2. Configure LibreChat

Add the shared secret to LibreChat `.env` and the MCP entry to mounted `librechat.yaml`.

LibreChat restart is an operator action.

## 3. First test — read only

With one mapped LC user:

```text
Search customer Arkee Foods
```

Expected:

```text
LC user
  → HTTP request LC ID
  → Task 05 mapping
  → mapped Frappe User
  → search_customers
  → Frappe permission result
```

## 4. Unmapped user

Same request from an unmapped LC user:

```text
ERP_ACCESS_NOT_CONFIGURED
```

Never Administrator/service-user fallback.

## 5. Different permissions

Use two mapped LC users whose Frappe Users have intentionally different permissions.

Verify each receives only its own Frappe access.

## 6. Quotation flow

After read-only success:

```text
prepare quotation
→ preview
→ explicit approval
→ confirm
→ Draft Quotation created
```

## 7. Sales Order flow

Run the equivalent existing Sales Order prepare/confirm test on safe development data.

## 8. Approval isolation

A prepares; B attempts A's approval token.

Expected denial.

---

# Known Boundaries

Not part of Task 06:

```text
public internet deployment
HTTPS/TLS/reverse proxy
MCP OAuth 2.1 authorization
per-user MCP OAuth tokens
automatic LC → Frappe user provisioning
role synchronization
multi-site selection
multiple HTTP workers
persistent/distributed approval storage
LibreChat Agent creation
multi-agent/coordinator orchestration
removal of existing Frappe OAuth login integration
```

The shared-secret trusted-proxy bridge is for the current controlled Docker/WSL deployment. Public deployment requires a separate security task.

---

# Technical References for Codex

Inspect installed versions first.

Frappe runtime/user context:

```text
https://github.com/frappe/frappe/blob/develop/frappe/__init__.py
https://github.com/frappe/frappe/blob/develop/frappe/utils/local.py
```

Official MCP Python SDK request Context:

```text
https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/handlers/context.md
```

LibreChat MCP configuration:

```text
https://www.librechat.ai/docs/features/mcp
https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers
https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_settings
```

---

# Exact Next Task

After Task 06 implementation/tests and operator-approved connection test, stop.

Next:

```text
Task 07 — LibreChat → ERPNext MCP End-to-End Multi-User Permission Verification
```

Task 07 will validate the actual running LibreChat connection with:

```text
mapped user A
mapped restricted user B
unmapped user C
read-only tools
Quotation prepare/confirm
Sales Order prepare/confirm
permission differences
approval-token isolation
```

Do **not** create the LibreChat Agent until Task 07 passes.
