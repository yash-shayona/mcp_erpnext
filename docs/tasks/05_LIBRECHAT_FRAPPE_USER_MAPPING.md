# Task 05 — LibreChat User → Frappe User Mapping

## Objective

Add a backward-compatible identity bridge to the existing `mcp_erpnext` STDIO server:

```text
LibreChat authenticated user
        ↓
{{LIBRECHAT_USER_ID}}
        ↓
MCP environment
        ↓
LibreChat User Mapping
        ↓
Frappe User
        ↓
frappe.set_user(...)
        ↓
existing MCP tools/services
        ↓
Frappe roles + User Permissions + DocType permissions
```

The mapping layer must do only:

```text
LibreChat User ID → Frappe User
```

Do not duplicate Frappe roles/permissions inside LibreChat or this DocType.

Implement **only this task** and stop after verification.

---

## Current Source Findings — Treat as Baseline

This task was prepared against the uploaded `mcp_erpnext` source dated 2026-08-31.

Verified current behavior:

```text
mcp_erpnext/settings.py
    supports MCP_BACKEND, MCP_FRAPPE_SITE, MCP_FRAPPE_USER

mcp_erpnext/runtime.py
    ensure_context()
    → initializes/connects Frappe
    → calls frappe.set_user(MCP_FRAPPE_USER)
    → rejects Guest

all current public tool wrappers
    → call ensure_context() before services

mcp_erpnext/approvals.py
    approval token already binds:
        action + site + current Frappe user + payload digest

business services
    → use permission-aware Frappe APIs
    → writes use insert(ignore_permissions=False, ...)
```

Therefore identity mapping belongs in the **runtime boundary**, not separately inside Customer/Item/Quotation/Sales Order services.

Inspect current source again before editing in case it changed.

---

# Architecture Decision

Support two explicit modes.

## 1. Existing service-user mode — preserve

```env
MCP_IDENTITY_MODE=service
MCP_FRAPPE_USER=sales@example.com
```

Behavior:

```text
frappe.set_user(MCP_FRAPPE_USER)
```

For backward compatibility:

```text
MCP_IDENTITY_MODE absent → service
```

Existing MCP Inspector / VS Code usage must continue working.

## 2. New LibreChat mode

Conceptual LibreChat YAML:

```yaml
mcpServers:
  erpnext:
    type: stdio
    command: <frappe-bench-python>
    args: ["-m", "mcp_erpnext.mcp_server"]
    cwd: <frappe-bench-sites-directory>
    env:
      MCP_BACKEND: direct
      MCP_FRAPPE_SITE: <site>
      MCP_IDENTITY_MODE: librechat
      MCP_LIBRECHAT_USER_ID: "{{LIBRECHAT_USER_ID}}"
      MCP_LIBRECHAT_USER_EMAIL: "{{LIBRECHAT_USER_EMAIL}}"
```

LibreChat documents `{{LIBRECHAT_USER_*}}` substitution in `env` for YAML-defined STDIO MCP servers:

```text
https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers
```

Do not modify LibreChat source in this task.

---

# Security Rules — Mandatory

1. **Authoritative key = LibreChat User ID**

   ```text
   MCP_LIBRECHAT_USER_ID
   ```

   `MCP_LIBRECHAT_USER_EMAIL` is display/diagnostic only.

2. **Never authorize by email fallback.**

3. **Never let an MCP tool/LLM choose `frappe_user`, `run_as`, role, email, etc.**

4. In `librechat` mode, mapping failure must **never** fall back to `MCP_FRAPPE_USER`, even if it contains `Administrator`.

5. Do not create Frappe Users automatically. ERP-enabled LC users must map to an existing Frappe `User`.

6. Do not store LC passwords, cookies, OAuth tokens, API keys, or secrets in Frappe.

7. Do not add `ignore_permissions=True`, raw SQL permission bypasses, or `frappe.get_all()` for user-facing ERP business data.

8. Preserve current approval binding to Frappe user.

9. Do not implement Frappe `auth_hooks` for this task. Current architecture is a direct local STDIO process, not an incoming Frappe HTTP authentication flow.

10. Existing Frappe/LibreChat OAuth work must not be removed or rewritten.

---

# Phase 1 — Create Mapping DocType

Create:

```text
DocType: LibreChat User Mapping
Module: MCP ERPNext
```

Expected path:

```text
mcp_erpnext/mcp_erpnext/doctype/librechat_user_mapping/
    __init__.py
    librechat_user_mapping.json
    librechat_user_mapping.py
```

No JS file unless actual client behavior is needed.

## Fields

Use a compact Section/Column layout.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `librechat_user_id` | Data | Yes | unique, list view, authoritative key |
| `librechat_email` | Data/Email | No | list view, reference only |
| `frappe_user` | Link → User | Yes | unique, list view |
| `enabled` | Check | Yes | default `1`, list view |
| `notes` | Small Text | No | admin notes only |

Enforce one-to-one mapping:

```text
one LC User ID  → one Frappe User
one Frappe User → one LC User ID
```

## Permissions

Default management role:

```text
System Manager
    read / write / create / delete
```

Normal ERP users do not need direct access to this DocType.

## Controller validation

Validate:

```text
librechat_user_id non-empty after trim
linked Frappe User exists
linked Frappe User != Guest
duplicate LC ID rejected
duplicate Frappe User rejected
cannot enable mapping to an already disabled Frappe User
```

Do not assign/change Frappe roles from this controller.

---

# Phase 2 — Extend Settings

Modify:

```text
mcp_erpnext/settings.py
```

Add:

```text
identity_mode
librechat_user_id
librechat_user_email
```

Environment variables:

```env
MCP_IDENTITY_MODE=service|librechat
MCP_LIBRECHAT_USER_ID=
MCP_LIBRECHAT_USER_EMAIL=
```

Rules:

```text
service mode:
    existing MCP_FRAPPE_USER path remains

librechat mode:
    MCP_LIBRECHAT_USER_ID required
    email optional
    MCP_FRAPPE_USER must not determine execution identity
```

Do not implement the reserved REST backend.

---

# Phase 3 — Add Identity Resolver

Prefer a dedicated module:

```text
mcp_erpnext/identity.py
```

Suggested responsibility:

```python
resolve_frappe_user_for_runtime(settings) -> str
```

## Service mode

Return existing configured Frappe user behavior.

## LibreChat mode

Exact algorithm:

```text
1. normalize/read MCP_LIBRECHAT_USER_ID
2. reject missing/blank ID
3. lookup exact enabled LibreChat User Mapping by librechat_user_id
4. never lookup by email as fallback
5. get linked frappe_user
6. verify User exists
7. verify User enabled
8. reject Guest
9. return frappe_user
```

A narrow internal DB lookup is allowed for this mapping bootstrap because no mapped user context exists yet. It must only read mapping/User identity metadata, never ERP business records.

If runtime email differs from stored reference, it may be logged safely, but it must neither remap nor grant access.

---

# Phase 4 — Integrate With Runtime

Modify:

```text
mcp_erpnext/runtime.py
```

Preserve current site/bootstrap logic.

Required sequence:

```text
load settings
    ↓
validate backend/site/identity mode
    ↓
frappe.init(...)
frappe.connect(set_admin_as_user=False)
    ↓
resolve execution Frappe user
    ↓
frappe.set_user(resolved_user)
    ↓
verify session user is non-Guest
    ↓
continue existing tool/service execution
```

Every current tool already calls `ensure_context()`, so do not rewrite all tools.

### Important

If `ensure_context(..., user=...)` remains for internal/tests:

```text
service mode    → may preserve existing internal override if genuinely needed
librechat mode  → override must NOT bypass LC mapping
```

If that is ambiguous, narrow/remove the override and update its tests/callers.

---

# Phase 5 — Controlled Errors

Modify the current safe error layer (`mcp_erpnext/observability.py` or a cleaner equivalent).

## Unmapped/inactive identity

For:

```text
no LC mapping
mapping disabled
linked Frappe User missing
linked Frappe User disabled
Guest mapping
```

return:

```json
{
  "status": "error",
  "code": "ERP_ACCESS_NOT_CONFIGURED",
  "message": "Your LibreChat account is not linked to an active ERPNext user. Please contact your administrator.",
  "reference": "MCP-ERR-...",
  "retryable": false
}
```

## Server identity configuration problem

Example:

```text
MCP_IDENTITY_MODE=librechat
but MCP_LIBRECHAT_USER_ID missing
```

Use a safe distinct code such as:

```text
ERP_IDENTITY_CONFIGURATION_ERROR
```

Do not expose stack traces, database details, other usernames, or mapping internals.

After successful mapping, normal Frappe `PermissionError` behavior must remain unchanged.

Keep logs privacy-safe; fingerprint identity where useful instead of dumping full IDs/tokens.

---

# Phase 6 — Preserve Existing Business/Approval Behavior

Do not change current MCP tool names or schemas.

Expected tools remain:

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

All must execute under the user resolved by `ensure_context()`.

Preserve approval isolation:

```text
LC A → Frappe A → prepare → token bound to A
LC B → Frappe B → confirm A token → CONFIRMATION_UNAVAILABLE
```

Do not redesign approval storage/TTL in this task.

---

# Phase 7 — Tests

Add focused tests, preferably:

```text
mcp_erpnext/tests/test_identity.py
mcp_erpnext/tests/test_runtime.py
```

Combine if repository style makes one file cleaner.

## Required test cases

### Settings / compatibility

```text
1. missing MCP_IDENTITY_MODE defaults to service
2. explicit service mode uses MCP_FRAPPE_USER
3. librechat mode requires LC user ID
4. invalid identity mode fails deterministically
```

### Mapping

```text
5. exact LC ID maps to expected Frappe User
6. LC ID remains authoritative if email changed
7. matching email without matching LC ID does NOT grant access
8. missing mapping → ERP_ACCESS_NOT_CONFIGURED
9. disabled mapping → ERP_ACCESS_NOT_CONFIGURED
10. disabled Frappe User → ERP_ACCESS_NOT_CONFIGURED
11. Guest mapping rejected
12. librechat mode + MCP_FRAPPE_USER=Administrator still uses mapping only
```

### Isolation

```text
13. LC-A → Frappe-A and LC-B → Frappe-B remain isolated across context calls
14. mapped user is visible as current frappe.session.user to permission-sensitive services
15. approval prepared under A cannot be confirmed under B
```

### DocType

Where Frappe test environment permits:

```text
16. duplicate LC ID rejected
17. duplicate Frappe User mapping rejected
18. invalid/Guest user rejected
```

Run existing safe regression tests and keep current tool-registration expectations unchanged.

---

# Phase 8 — Documentation / Config

Update:

```text
.env.example
README.md
docs/ERPNext_MCP_ARCHITECTURE.md
docs/CODEX_MCP_SETUP.md
```

`.env.example` should show both modes without real IDs/secrets:

```dotenv
MCP_BACKEND=direct
MCP_FRAPPE_SITE=your-site.localhost

# Existing mode
MCP_IDENTITY_MODE=service
MCP_FRAPPE_USER=mcp-service@example.com

# LibreChat mode
# MCP_IDENTITY_MODE=librechat
# MCP_LIBRECHAT_USER_ID=<provided dynamically by LibreChat>
# MCP_LIBRECHAT_USER_EMAIL=<reference only>
```

Docs must state:

```text
LC login is sufficient for this flow
ERP-enabled LC user still needs an existing mapped Frappe User
Frappe Desk login is not required
Frappe roles/User Permissions remain authority
email is not an authorization key
librechat mode never falls back to MCP_FRAPPE_USER
existing OAuth work remains untouched
```

Keep documentation concise; do not create a large implementation diary.

---

# Files Allowed to Change

```text
mcp_erpnext/settings.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py
mcp_erpnext/identity.py                           # new if used

mcp_erpnext/mcp_erpnext/doctype/librechat_user_mapping/
    __init__.py
    librechat_user_mapping.json
    librechat_user_mapping.py

mcp_erpnext/tests/test_identity.py                 # new if used
mcp_erpnext/tests/test_runtime.py                  # new if used
existing tests only for relevant regression assertions

.env.example
README.md
docs/ERPNext_MCP_ARCHITECTURE.md
docs/CODEX_MCP_SETUP.md
```

If Frappe requires a minimal package/module metadata change for the DocType, make only the necessary change and explain it.

---

# Do Not Change

Unless a minimal compatibility edit is unavoidable:

```text
MCP tool catalog/tool schemas
Customer/Item/Quotation/Sales Order business rules
creation contract
field-value resolver
approval design/TTL
REST backend
LibreChat source
existing Frappe OAuth/OIDC implementation
LangGraph/coordinator-agent architecture
```

Do not remove `MCP_FRAPPE_USER`; it remains valid for service mode.

---

# Do Not Run Without Operator Permission

Do not automatically run:

```text
bench migrate
bench install-app / uninstall-app
bench update
production DB writes
real user/role/permission changes
LibreChat production config changes
Docker/service restarts
```

The new DocType will require migration before it exists in the site database. If needed, report the exact command and wait for operator approval.

Safe source/unit tests may be run when the environment supports them.

---

# Acceptance Criteria

```text
[ ] LibreChat User Mapping DocType added
[ ] LC ID unique and authoritative
[ ] Frappe User mapping unique
[ ] mapping enable/disable supported
[ ] System Manager manages mappings
[ ] no LC credentials/tokens stored

[ ] service mode preserved and default
[ ] librechat mode added
[ ] LC user ID required in librechat mode
[ ] email never used as auth fallback
[ ] no MCP_FRAPPE_USER fallback in librechat mode

[ ] runtime resolves LC ID → Frappe User
[ ] runtime calls frappe.set_user(mapped_user)
[ ] missing/disabled/Guest identity fails closed
[ ] existing tools automatically inherit mapped identity

[ ] no run-as identity tool parameter added
[ ] no permission bypass introduced
[ ] Frappe permissions remain authoritative

[ ] ERP_ACCESS_NOT_CONFIGURED implemented safely
[ ] configuration failure handled safely
[ ] no raw internal mapping details exposed

[ ] approvals remain user-bound
[ ] A cannot confirm B's approval

[ ] new tests pass
[ ] existing regression tests pass
[ ] tool catalog unchanged

[ ] .env.example updated
[ ] README/architecture/setup docs updated concisely
[ ] OAuth integration untouched
[ ] REST backend still unimplemented
```

---

# Manual Verification After Migration

Use a development site.

```text
LC-A → Frappe sales.a@example.com
LC-B → Frappe sales.b@example.com
LC-C → no mapping
```

Give A and B intentionally different Frappe permissions.

Verify:

```text
A MCP request → runs as sales.a@example.com → A permissions apply
B same request → runs as sales.b@example.com → B permissions apply
C request → ERP_ACCESS_NOT_CONFIGURED

disable A mapping → A denied on next MCP context
disable Frappe User A → A denied

service mode with MCP_FRAPPE_USER → existing Inspector/VS Code flow still works
```

---

# Known Boundaries

Not part of this task:

```text
automatic LC → Frappe user provisioning
role synchronization
remote HTTP MCP authentication
multi-site selection per LC user
persistent/multi-worker approval storage
Frappe SSO login
LibreChat Docker/WSL deployment plumbing
```

---

# Exact Next Task

After implementation and tests, stop.

Next task:

```text
Task 06 — LibreChat Multi-User ERPNext Permission End-to-End Verification
```

Task 06 will verify real LibreChat user placeholders and two different users through the actual LibreChat → STDIO MCP path.

Do not implement Task 06 now.
