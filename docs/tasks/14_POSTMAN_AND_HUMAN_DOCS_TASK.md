# Task — Postman MCP Testing + Human-Readable Hinglish System Documentation

## Task Type

Documentation-first implementation task with safe runtime verification.

This task must inspect the **actual current source** of both Frappe apps before writing documentation:

- `mcp_identity`
- `mcp_erpnext`

Do not derive the final documentation only from old task files, old LibreChat docs, prior chat notes, or assumptions about the MCP protocol.

---

# 1. Objective

Create two authoritative documentation tracks for the current MCP ERPNext system:

1. **Postman / raw HTTP testing documentation**
   - A developer must be able to test the running MCP server without LibreChat, VS Code, MCP Inspector, or another AI UI.
   - The guide must explain the exact HTTP request sequence, headers, authentication/identity contract, MCP protocol messages, tool discovery, tool calling, error behavior, and safe write boundaries.
   - Where practical, provide an importable Postman collection and safe example environment.

2. **Human-readable Hinglish system guide**
   - Explain the whole system from scratch in normal human language.
   - A developer/admin who did not build this project should be able to understand what `mcp_identity` and `mcp_erpnext` do, how a request travels, how permissions work, how tools work, why the server may need to be running, and how clients such as LibreChat / VS Code / MCP Inspector / Postman fit around the same server.
   - This guide is for humans, not primarily for an AI coding agent.

The docs must reflect the **current implementation**, not the historical LibreChat-specific design.

---

# 2. Why This Task Exists

The project already has architecture/task documentation, but much of it is optimized for an AI agent or implementation work.

We now need:

```text
A. MACHINE / TEST OPERATOR GUIDE
   Postman -> MCP HTTP endpoint -> tools/list -> tools/call

B. HUMAN UNDERSTANDING GUIDE
   "Ye pura system actually karta kya hai aur request andar kaise travel karti hai?"
```

A UI is not required to verify an MCP server if its Streamable HTTP transport is enabled and reachable.

However, Postman is not an MCP orchestrator. It will not automatically interpret natural language, select tools, handle ambiguity, or continue workflows. The tester manually sends the MCP protocol requests.

---

# 3. Mandatory Source Inspection First

Before creating or editing docs, inspect the real current repositories.

At minimum inspect the actual equivalents of:

## `mcp_identity`

- `README.md`
- `hooks.py`
- package/version metadata
- identity/authentication modules
- HTTP identity extraction/verification code
- Frappe user resolution code
- shared-secret validation
- verified-user-email/header handling
- tests
- architecture/security docs
- any site/env configuration documentation

## `mcp_erpnext`

- `README.md`
- `pyproject.toml` / package metadata
- `mcp_server.py`
- `settings.py`
- `runtime.py`
- `http_transport.py`
- transport identity adapter code
- MCP server/tool registry
- contracts
- resolvers
- services
- approvals
- profile/domain registration
- tests
- `docs/TOOLS.md`
- architecture docs
- current HTTP setup docs

Do not assume these exact paths exist. Discover and report the real paths.

---

# 4. Mandatory Runtime / Dependency Facts

Record the actual installed/runtime facts where available:

```text
Python version
Frappe version
ERPNext version
MCP Python SDK package + version
Pydantic version
mcp_identity version
mcp_erpnext version
configured MCP transports
configured HTTP path/host/port behavior
supported MCP protocol revision(s)
```

This is especially important because MCP Streamable HTTP behavior has changed across protocol revisions.

Do not assume whether the current server uses:

```text
initialize -> notifications/initialized -> tools/list
```

or a newer stateless MCP flow.

Determine it from the installed SDK and actual server behavior.

---

# 5. Source of Truth Rule

Use this priority:

```text
1. Actual current runtime/source
2. Current tests
3. Generated tools/list schema
4. Current repo docs
5. Old task docs only as historical context
```

If old documentation conflicts with the current source, update or clearly deprecate the old documentation.

Do not preserve outdated LibreChat-specific identity wording if the current `mcp_identity` architecture is generic.

---

# 6. Allowed Changes

Documentation-only by default.

Allowed:

```text
mcp_erpnext/docs/**
mcp_erpnext/README.md          # links/index only where useful
mcp_identity/README.md         # links/clarification only if genuinely needed
```

Also allowed, if useful and accurate:

```text
mcp_erpnext/docs/postman/mcp_erpnext.postman_collection.json
mcp_erpnext/docs/postman/mcp_erpnext.local.postman_environment.example.json
```

Do not place real secrets, real passwords, real API tokens, real session IDs, or private user data in any committed file.

---

# 7. Forbidden Changes

Do not change runtime behavior in this task.

Do not modify:

```text
MCP tool business logic
ERPNext services
resolvers
approval semantics
identity semantics
permission semantics
HTTP authentication behavior
Frappe user mapping/resolution behavior
LibreChat configuration
VS Code MCP configuration
database data
DocTypes
site_config secrets
production process configuration
```

If documentation testing reveals a runtime bug, report it separately.

Do not silently fix the runtime bug in the documentation task.

---

# 8. Required Output Files

Create these files, adapting paths only if the current repository has a clearly established docs convention.

## Output 1

```text
mcp_erpnext/docs/testing/POSTMAN_MCP_HTTP_TESTING.md
```

Purpose:

> Exact, copyable, human-operable guide for testing the current Streamable HTTP MCP server through Postman.

## Output 2

```text
mcp_erpnext/docs/guides/MCP_SYSTEM_HUMAN_GUIDE_HINGLISH.md
```

Purpose:

> Top-to-bottom human-readable explanation of the complete current system in natural Hinglish.

## Output 3 — Recommended

```text
mcp_erpnext/docs/postman/mcp_erpnext.postman_collection.json
```

Purpose:

> Importable Postman collection containing safe protocol and read/prepare examples.

## Output 4 — Recommended

```text
mcp_erpnext/docs/postman/mcp_erpnext.local.postman_environment.example.json
```

Purpose:

> Example variables only. Never contain real secrets.

## README navigation

Add small links from the main `mcp_erpnext/README.md` if appropriate.

Do not duplicate full docs inside README.

---

# 9. POSTMAN_MCP_HTTP_TESTING.md — Mandatory Contents

Write this as a practical operator guide.

## 9.1 What Postman is testing

Explain clearly:

```text
Postman
   |
   | HTTP + MCP protocol messages
   v
mcp_erpnext Streamable HTTP endpoint
   |
   v
mcp_identity / request identity verification
   |
   v
Frappe user context
   |
   v
MCP tool registry
   |
   v
ERPNext/Frappe services
```

Clarify:

- `tools/list` and `tools/call` are MCP protocol methods.
- They are not ordinary custom REST endpoints such as `/api/tools/list`.
- The same MCP business tools should remain client-neutral.
- Postman is simply acting as a low-level MCP HTTP client.

## 9.2 When the server must be running

Explain the exact current behavior for both transports:

### Streamable HTTP

The MCP server is an independent HTTP service and must already be running/listening before Postman can call it.

### stdio

A compatible MCP client may launch the MCP process itself and communicate over stdin/stdout.

Postman does not directly test stdio.

State the actual current startup command and working directory from source/docs, using placeholders for secrets.

## 9.3 Safe local configuration

Document:

```text
host
port
MCP HTTP path
allowed hosts / Origin behavior if implemented
transport setting
Frappe site
backend mode
shared-secret variable
identity mode/settings
```

Use the actual names from current source.

Never print a real configured secret.

## 9.4 Postman environment variables

Define example variables such as:

```text
base_url
mcp_path
mcp_url
shared_secret
verified_user_email
protocol_version
mcp_session_id        # only if current protocol/server uses one
test_customer
test_item
```

Use the exact current identity header name from source.

Do not invent a header name.

## 9.5 Required HTTP headers

Document the exact current headers.

Potential categories to inspect:

```text
Authorization: Bearer ...
Content-Type
Accept
MCP-Protocol-Version
Mcp-Session-Id
current generic verified-user identity header
Host
Origin, if relevant
Mcp-Method / Mcp-Name, if required by the negotiated/current protocol revision
```

Only include headers that are actually required or supported by the current server/SDK.

Clearly mark:

```text
required
conditional
optional
server-generated
must never be user/model supplied
```

## 9.6 Protocol initialization / discovery

Derive the correct flow from the current server.

If the current implementation is session-based, document the exact sequence such as:

```text
initialize
-> capture Mcp-Session-Id if returned
-> notifications/initialized
-> tools/list
```

If the current implementation uses the newer stateless MCP revision, document that actual sequence instead.

Do not mix protocol revisions in one "working request" example.

A separate compatibility note may explain older/newer differences.

## 9.7 List tools

Provide an exact Postman request for the current protocol.

Expected result explanation must include:

```text
tool name
description
inputSchema
outputSchema if exposed
tool metadata / annotations if exposed
```

Explain that `tools/list` is the authoritative machine-readable contract where that remains true in the current implementation.

## 9.8 Call a safe read tool

Use an actual current registered read-only tool, for example only if present:

```text
search_customers
resolve_customer
search_items
resolve_item
```

Provide exact request body and expected response shape.

## 9.9 Ambiguity test

Show how a raw MCP client handles:

```text
resolved
ambiguous
not_found
error
```

Explain that Postman does not render a selection UI.

The human tester manually chooses a candidate and sends the appropriate selection/revalidation call.

Use actual current tool names/contracts.

## 9.10 Prepare test

Use an actual current PREPARE operation if available.

Example domains may include:

```text
Quotation
Sales Order
Purchase workflow
```

Use only the currently implemented profiles/tools.

Explain:

- prepare performs validation/preview according to actual current semantics;
- whether it persists anything must be verified from source/tests;
- how missing inputs are represented;
- how approval/interaction metadata is represented.

## 9.11 Confirm/write safety

This section is mandatory.

Inspect the actual current approval implementation.

Explain exactly whether Postman can successfully execute a `CONFIRM_WRITE`.

Do not equate:

```text
"confirm": true
```

with trusted human approval unless the current server explicitly verifies such a channel.

If the current approval design intentionally rejects raw Postman confirmation, document the expected safe failure code.

If a trusted manual/API approval adapter now exists, document the correct non-model flow and safety requirements.

Any request that can create ERPNext data must be clearly labeled:

```text
WRITE / TEST SITE ONLY
```

Do not make write requests run automatically in the Postman collection.

## 9.12 Negative authentication tests

Add separate examples for:

```text
missing bearer/shared secret
wrong bearer/shared secret
missing verified-user identity
invalid email format if validated
nonexistent Frappe user
disabled Frappe user if applicable
disallowed Host
bad Origin if applicable
wrong/unsupported MCP protocol version
missing session id if current protocol requires one
expired/invalid session id if current protocol uses one
```

Document the observed status/error, not guessed behavior.

## 9.13 Permission test

Use two safe test users only if already available and authorized for testing:

```text
User A -> permitted
User B -> lacks permission
```

Verify that the same tool behaves according to the authenticated Frappe user's permissions.

Do not alter role or User Permission data during this task.

If suitable test users are not available, mark runtime permission comparison as `NOT VERIFIED`.

## 9.14 Error-layer troubleshooting table

Create a table like:

| Layer | Example symptom | Meaning | Where to check |
|---|---|---|---|
| Network | connection refused | MCP HTTP server not listening | process/host/port |
| HTTP auth | 401/403 | secret/header problem | identity/HTTP adapter |
| Identity | user not resolved | verified caller cannot map to Frappe user | mcp_identity |
| MCP protocol | invalid request/version/session | protocol mismatch | SDK/transport |
| Tool contract | invalid params | JSON does not match input schema | tools/list/contracts |
| Frappe permission | permission denied | authenticated Frappe user lacks permission | Frappe roles/User Permissions |
| Domain validation | business error | ERPNext/MCP business validation failed | service/ERPNext |
| Approval | trusted approval unavailable/expired | write guard blocked request | approval layer |

Use actual current error codes where they exist.

## 9.15 Postman vs MCP Inspector vs VS Code vs LibreChat

Explain:

```text
Postman       = manual low-level HTTP protocol testing
MCP Inspector = MCP-aware development/debug client
VS Code       = MCP client integrated into coding-agent workflow
LibreChat     = chat/agent client using MCP tools
```

They may consume the same MCP business server, but transport startup and identity configuration can differ.

---

# 10. Postman Collection Requirements

If creating the collection, organize folders like:

```text
00 - Health / Connectivity (only if an actual health route exists)
01 - MCP Protocol / Discovery
02 - Tools - Read
03 - Resolver / Ambiguity
04 - Prepare - No Final Write
90 - Negative Auth / Identity
99 - Confirm Write - MANUAL / TEST SITE ONLY
```

Do not invent a health route if none exists.

## Environment behavior

If the current MCP protocol returns `Mcp-Session-Id`, add a safe Postman test script to save it into an environment variable.

If the current protocol is stateless, do not create fake session handling.

## Safety

The collection must not automatically run any final write request.

The confirm/write folder should be disabled from normal collection-run flow where practical, or documented as manual-only.

---

# 11. MCP_SYSTEM_HUMAN_GUIDE_HINGLISH.md — Mandatory Contents

Write this in natural, professional Hinglish.

Use English for technical identifiers and Hindi/Hinglish for explanation.

Example tone:

> "`mcp_identity` ko security gate samjho. Request pehle yahan verify hoti hai ki caller trusted MCP client se aaya hai aur kis Frappe user ke naam par kaam karna hai."

Avoid slang that makes the document difficult for another developer to maintain.

## 11.1 Start from zero

Explain:

- ERPNext kya hai in this architecture
- Frappe kya control karta hai
- MCP kya solve karta hai
- MCP server kya hota hai
- MCP client kya hota hai
- AI/LLM optional client-side intelligence hai; MCP server khud LLM nahi hai unless source says otherwise

## 11.2 Our two apps

Explain the actual current responsibilities of:

```text
mcp_identity
mcp_erpnext
```

Use real source evidence.

Clearly explain what each app does **not** own.

## 11.3 Full architecture picture

Include an ASCII diagram similar to:

```text
User
  |
  v
LibreChat / VS Code / MCP Inspector / Postman / future client
  |
  v
Transport: stdio OR Streamable HTTP
  |
  v
HTTP authentication + mcp_identity
  |
  v
Authenticated Frappe user context
  |
  v
mcp_erpnext MCP tool registry/profile
  |
  v
typed tool contract
  |
  v
resolver / domain service
  |
  v
ERPNext/Frappe
  |
  v
structured MCP response
```

Adjust based on actual source.

## 11.4 Server "ON" concept

Explain in simple terms:

- Why Streamable HTTP server has to be running.
- Why a stdio-capable client may start the process automatically.
- Why "server is installed" and "server process is listening" are different things.
- What happens if nothing is listening on the configured HTTP host/port.

## 11.5 Request journey

Give a numbered real example.

Example only if current tool names support it:

```text
User: "Sunrise Auto Components ke liye Development item qty 2 quotation banao"

1. Client intent samajhta hai.
2. MCP tool call bhejta hai.
3. HTTP/shared-secret verification hoti hai.
4. Verified caller email se Frappe user resolve hota hai.
5. Frappe request context us user ke naam par set hota hai.
6. Customer resolve hota hai.
7. Item resolve hota hai.
8. Ambiguous ho to candidates return hote hain.
9. Prepare tool ERPNext defaults/validation se preview banata hai.
10. Client preview user ko dikhata hai.
11. Approval/write guard ke bina final create nahi hota.
12. Successful write me ERPNext permission dubara authoritative rehti hai.
```

Use actual current behavior.

## 11.6 Tool categories

Explain current tool operation classes:

```text
READ
RESOLVE
PREPARE
CONFIRM_WRITE
```

Only if these are still current in source.

Explain why `prepare` and `confirm` are separate.

## 11.7 Tool schemas

Explain:

- `tools/list`
- typed input contract
- typed output contract
- why the client/model should not guess payload shape
- why identity/auth fields must not appear as public tool arguments

## 11.8 Resolution / ambiguity

Explain with a simple Customer example.

Show:

```text
unique match -> resolved
multiple matches -> ambiguous
zero matches -> not_found
user selects -> exact revalidation
```

Explain that the UI is client responsibility; MCP returns structured state.

## 11.9 Identity flow

Explain current generic identity contract from actual `mcp_identity` source.

Include:

```text
what the shared secret proves
what the verified-user identity proves
how the Frappe user is located
what happens for missing/invalid/nonexistent user
why caller cannot simply pass run_as/Administrator
```

Do not document old `LibreChat User Mapping` as current if it no longer exists.

## 11.10 Permissions

Explain:

```text
identity tells us WHO
Frappe permissions decide WHAT that user may do
MCP tool contract decides HOW the operation is exposed
approval guard decides WHETHER a guarded final write is allowed now
```

Make this distinction very clear.

## 11.11 Profiles / domain separation

Inspect the current profile architecture.

Document only profiles actually implemented, for example:

```text
sales
purchase
future profiles
```

Do not list deferred profiles as active.

Explain why one Frappe app can expose multiple MCP server profiles if that is still the current design.

## 11.12 Client comparison

Explain each client in simple language:

### LibreChat
Chat UI + agent/tool consumer.

### VS Code/Codex MCP client
Developer/agent client.

### MCP Inspector
Protocol-aware test/debug client.

### Postman
Raw HTTP/manual protocol tester.

### Future custom UI/LangGraph
Own orchestration, same MCP business contracts where compatible.

## 11.13 What MCP server does NOT do

Based on source, clarify likely boundaries such as:

```text
does not own natural-language conversation history
does not decide UI layout
does not store LibreChat message IDs
does not make client-specific radio buttons
does not bypass Frappe permissions
does not accept arbitrary model-supplied identity
```

Only state what source confirms.

## 11.14 Approval explained for humans

Explain:

```text
prepare = "ye hone wala hai"
user approval = "haan, ye exact action acceptable hai"
confirm/write = "ab ERPNext me actual persistent change karo"
```

Then explain how the current trusted approval mechanism actually works and its limitations.

## 11.15 Error ownership

Explain how to identify which layer failed:

```text
client
network
HTTP auth
identity
MCP protocol
tool schema
resolver
Frappe permission
ERPNext validation
approval
```

## 11.16 Local vs production

Document source-confirmed limitations:

```text
HTTP vs HTTPS expectations
localhost binding
shared secret handling
multi-worker limitations if any
process-local state if any
restart effects if any
session behavior
reverse proxy considerations if implemented
```

Do not copy stale limitations if they have already been fixed.

## 11.17 Glossary

Include a compact glossary:

```text
MCP
MCP client
MCP server
stdio
Streamable HTTP
JSON-RPC
tool
tools/list
tools/call
contract/schema
resolver
Frappe context
permission
shared secret
verified user identity
prepare
approval
confirm/write
profile
```

---

# 12. Documentation Style Rules

## Human guide

Use:

- Hinglish
- short paragraphs
- concrete examples
- diagrams
- tables only when they improve understanding
- "why" along with "what"

Do not write it like an AI-agent task prompt.

Do not assume the reader already knows MCP.

## Postman guide

Use:

- exact request bodies
- exact headers
- copyable examples
- expected response examples
- troubleshooting
- safety warnings around writes

Use placeholders like:

```text
{{shared_secret}}
{{verified_user_email}}
```

Never use real credentials.

---

# 13. Runtime Verification

Where safe, run actual local checks.

Preferred safe verification:

```text
start/inspect Streamable HTTP server using existing configuration
protocol discovery/initialize as applicable
tools/list
read-only search/resolve
prepare that is confirmed source-safe and non-persistent
negative auth/identity requests
```

Do not create ERPNext business records during verification unless the user has separately authorized a specific test write.

Do not run migrations/build/restart production services.

If the server is already running, use it.

If starting it requires environment secrets you are not permitted to inspect, report the exact manual command template and mark runtime parts `NOT VERIFIED`.

---

# 14. Test Matrix

The completion report must include a matrix:

| Test | Expected | Observed | Result |
|---|---|---|---|
| HTTP endpoint reachable | current server responds | ... | PASS/FAIL/NOT VERIFIED |
| missing secret | fail closed | ... | ... |
| wrong secret | fail closed | ... | ... |
| missing user identity | fail closed | ... | ... |
| valid identity | Frappe user context established | ... | ... |
| tools/list | registered tools returned | ... | ... |
| read tool | safe result | ... | ... |
| ambiguity | structured candidates/state | ... | ... |
| prepare | preview / needs_input | ... | ... |
| final confirm without trusted approval | actual expected current behavior | ... | ... |
| Frappe permission denial | fail according to user permission | ... | ... |

Do not fabricate Observed values.

---

# 15. Acceptance Criteria

Task is complete only when all applicable items pass:

```text
[ ] actual current mcp_identity source inspected
[ ] actual current mcp_erpnext source inspected
[ ] installed MCP SDK/protocol behavior identified
[ ] current HTTP auth + identity headers identified from source
[ ] no old LibreChat-specific identity contract is documented as current unless still truly implemented
[ ] POSTMAN_MCP_HTTP_TESTING.md created
[ ] human Hinglish system guide created
[ ] exact current tools/list flow documented
[ ] at least one safe read tool example documented
[ ] ambiguity flow documented
[ ] prepare flow documented
[ ] confirm/write safety documented
[ ] negative auth/identity cases documented
[ ] Postman vs MCP Inspector vs VS Code vs LibreChat explained
[ ] server-running behavior for stdio vs HTTP explained
[ ] no real secret committed
[ ] no ERPNext business record created during safe verification
[ ] importable Postman collection created if current protocol can be represented safely
[ ] README links added without schema duplication
[ ] old conflicting docs either updated, clearly marked historical, or referenced as superseded
```

---

# 16. Expected Result

After this task, a new developer should be able to do both:

## A. Test without a UI

```text
Start current MCP HTTP server
-> open Postman
-> authenticate using the documented generic identity contract
-> perform the correct MCP protocol flow
-> list tools
-> call a read tool
-> test ambiguity
-> test prepare
-> understand why a final write is or is not allowed
```

## B. Understand the system without asking an AI agent

They should be able to read one Hinglish guide and answer:

```text
mcp_identity kya karta hai?
mcp_erpnext kya karta hai?
MCP client aur server me difference kya hai?
server kab manually ON karna padta hai?
Postman ka role kya hai?
MCP Inspector kya extra karta hai?
tools/list aur tools/call kya hai?
Frappe permission kaha apply hoti hai?
identity kaha verify hoti hai?
ambiguity kaise handle hoti hai?
prepare aur confirm alag kyon hai?
final ERPNext write kis boundary par hota hai?
```

---

# 17. Limitations / Safety

- Do not assume today's latest MCP specification is the protocol revision implemented by this project.
- Do not invent an identity header.
- Do not expose real shared secrets.
- Do not treat a raw Postman button click as trusted approval unless current code explicitly implements a server-verifiable trusted approval path for it.
- Do not use `Administrator` as a shortcut for testing.
- Do not bypass Frappe permissions.
- Do not change production/deployment behavior in a documentation task.
- Do not silently rewrite architecture to make the docs easier.

---

# 18. Completion Report Format

Return:

## 1. Source inspected

Real paths and versions.

## 2. Protocol verdict

```text
Transport:
Protocol revision:
Sessionful/stateless:
Required MCP headers:
```

## 3. Current identity contract

```text
shared-secret setting:
user identity header:
Frappe resolution behavior:
fail-closed cases:
```

Mask secrets.

## 4. Files created/updated

List exact paths.

## 5. Runtime checks

Provide the test matrix.

## 6. Important findings

Especially stale documentation or protocol/version mismatch.

## 7. Safety confirmation

Explicitly confirm:

```text
No real secrets were added to docs.
No ERPNext business records were created.
No runtime identity/permission/approval behavior was changed.
```

## 8. Exact next task

If all documentation is accurate and runtime-safe tests pass:

```text
Next task: independent manual Postman verification using a designated non-production Frappe test user.
```

If runtime verification was blocked:

```text
Next task: perform the documented manual runtime verification on the configured development site and update only the Observed/Verified notes.
```
