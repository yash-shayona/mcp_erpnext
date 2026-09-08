# Postman MCP HTTP testing

This guide tests the current mcp_erpnext Streamable HTTP server directly.
Postman is a low-level MCP client: it sends JSON-RPC messages and manually
follows the workflow. It does not interpret natural language, choose tools,
display candidate-selection UI, or act as an MCP orchestrator.

## What is being tested

~~~text
Postman
   |
   | HTTP + MCP JSON-RPC messages
   v
mcp_erpnext Streamable HTTP endpoint (/mcp by default)
   |
   v
Bearer authentication middleware
   |
   v
mcp_identity -> enabled Frappe User
   |
   v
MCP tool registry -> ERPNext services -> Frappe permissions
~~~

initialize, notifications/initialized, tools/list, and tools/call are MCP
protocol messages sent to one endpoint. They are not REST routes such as
/api/tools/list.

The current HTTP app uses stateful Streamable HTTP. The normal sequence is:

~~~text
POST initialize
  -> capture response mcp-session-id
POST notifications/initialized
POST tools/list
POST tools/call
~~~

The server uses SSE responses (text/event-stream) because json_response is not
enabled in mcp_erpnext.mcp_server. Each response contains an SSE data: line
whose value is a JSON-RPC response.

## Current environment facts

These facts were inspected in the local bench environment on 2026-09-08. They
can change when the bench environment changes.

| Fact | Current value |
| --- | --- |
| Python | 3.14.3 |
| Frappe | 16.25.0 |
| ERPNext | 16.15.0 |
| MCP Python SDK | 1.29.0 |
| Pydantic | 2.12.5 |
| mcp_identity | 0.0.1 |
| mcp_erpnext | 0.0.1 |
| Transports | stdio, streamable-http |
| HTTP host default | 127.0.0.1 |
| HTTP port default | 8765 |
| HTTP path default | /mcp |
| HTTP session mode | Stateful; stateless_http=False in FastMCP defaults |
| SDK-supported protocol versions | 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25 |
| SDK default when a version is omitted | 2025-03-26 |

The installed SDK advertises 2025-11-25 as its latest version and supports the
four versions listed above. The examples use 2025-11-25; the initialize
response is the negotiated authority for the session.

The current app constructs FastMCP with json_response=False, no event store,
and explicit Host validation. It does not configure allowed Origins. An absent
Origin is accepted; a supplied Origin is rejected by the SDK's current empty
allowlist.

## Start the server

The selected site must already have mcp_identity, mcp_erpnext, ERPNext, and
their dependencies installed. Start one process from the bench sites directory:

~~~bash
export MCP_BACKEND=direct
export MCP_FRAPPE_SITE=your-site.localhost
export MCP_TRANSPORT=streamable-http
export MCP_PROFILE=sales
export MCP_HTTP_HOST=127.0.0.1
export MCP_HTTP_PORT=8765
export MCP_HTTP_PATH=/mcp
export MCP_HTTP_SHARED_SECRET='<minimum-32-character-development-secret>'
export MCP_HTTP_ALLOWED_HOSTS='127.0.0.1:8765,localhost:8765'

cd /home/frappe/frappe-bench/sites
../env/bin/python -m mcp_erpnext.mcp_server
~~~

MCP_HTTP_SHARED_SECRET is server-only configuration. It must be at least 32
characters. Do not commit it, put it in a Postman collection, or paste it into
chat. Put the same value only in a local, uncommitted Postman environment.

For a Docker-to-WSL bridge, host and allowlist must be changed together, for
example MCP_HTTP_HOST=0.0.0.0 and an explicit
MCP_HTTP_ALLOWED_HOSTS=host.docker.internal:8765,... . This is a local
development bridge, not a public deployment.

MCP_PROFILE is sales by default and may be purchase. A separate process and
port are needed if both inventories must be available. The REST backend is not
implemented in this server; use MCP_BACKEND=direct.

For HTTP, MCP_FRAPPE_USER is not a fallback. Every tool call resolves its
execution user from the authenticated request's X-MCP-User-Email header.

## Import the supplied Postman files

Import these files:

- [Postman collection](../postman/mcp_erpnext.postman_collection.json)
- [Example local environment](../postman/mcp_erpnext.local.postman_environment.example.json)

Select the imported environment and replace these values locally:

| Variable | Meaning |
| --- | --- |
| base_url | Server origin, for example http://127.0.0.1:8765 |
| mcp_path | Current path, normally /mcp |
| mcp_url | {{base_url}}{{mcp_path}} |
| shared_secret | Local server secret; never commit the real value |
| verified_user_email | Existing, enabled Frappe User email |
| protocol_version | Start with 2025-11-25; initialize may negotiate it |
| mcp_session_id | Filled by the Initialize test script |
| test_customer | Exact permitted Customer name for prepare tests |
| test_item | Exact permitted sales Item name for prepare tests |
| test_supplier | Exact permitted Supplier name for purchase tests |
| approval_token | Filled manually only for an explicitly authorized write test |

Run 01 - MCP Protocol / Discovery in order. Initialize stores
mcp-session-id from the response header. The collection does not invent a
session ID for a stateless server.

## Headers

| Header | Status | Use |
| --- | --- | --- |
| Authorization: Bearer <secret> | Required on endpoint requests | App middleware checks it. Missing, malformed, or wrong values return HTTP 401 before the SDK receives the request. |
| Content-Type: application/json | Required on POST | SDK checks it; invalid or missing content type returns HTTP 400. |
| Accept: application/json, text/event-stream | Required by current SSE mode | Both media types must be accepted; otherwise SDK returns HTTP 406. |
| X-MCP-User-Email: person@example.com | Required for tool execution | Generic caller identity. mcp_identity resolves it to an existing enabled Frappe User after bearer authentication. |
| mcp-session-id: <server value> | Required after initialize | Copy the exact response header to later session requests. It is server-generated. |
| mcp-protocol-version: <negotiated value> | Required by examples after initialize; omission currently falls back to 2025-03-26 | Must be one of the SDK-supported versions. |
| Host: host:port | Automatically sent, but must be allowed | SDK validates it against MCP_HTTP_ALLOWED_HOSTS. |
| Origin | Optional | Do not send it from Postman. Current app does not configure allowed Origins, so a supplied Origin is rejected. |

There is no current requirement for Mcp-Method, Mcp-Name, X-Frappe-User, roles,
run_as, or Administrator. Do not send those as identity or authorization
substitutes. The identity header is deliberately generic and is not a
LibreChat-specific mapping.

## 1. Initialize

Create a POST request to {{mcp_url}} with Authorization, Content-Type, Accept,
and X-MCP-User-Email. Do not send mcp-session-id or mcp-protocol-version on this
first request.

~~~json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "{{protocol_version}}",
    "capabilities": {},
    "clientInfo": {
      "name": "postman",
      "version": "1.0"
    }
  }
}
~~~

Expected successful behavior:

- HTTP status 200.
- Content-Type text/event-stream.
- A response mcp-session-id header.
- An SSE data event containing a JSON-RPC result with protocolVersion,
  capabilities, and serverInfo.

Use returned protocolVersion for subsequent requests. If the server negotiates
another supported value, use that value rather than assuming the request value
was accepted.

## 2. Mark the session initialized

Send a second POST using the captured session ID and negotiated protocol version:

~~~json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
~~~

This is a JSON-RPC notification, so the current SDK responds with HTTP 202
Accepted and no JSON-RPC result body. Keep session and protocol headers on this
request.

## 3. Discover tools with tools/list

Send:

~~~json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
~~~

The JSON-RPC result contains tools. Each tool can expose name, description,
inputSchema, outputSchema, and annotations or metadata when provided.

tools/list is the machine-readable contract. The generated [TOOLS.md](../TOOLS.md)
is a useful static catalog, but it is not a replacement for the live response.

The sales profile currently registers Customer, sales Item, Quotation, Sales
Order, lifecycle, and existing-document read/search tools. The purchase profile
registers Supplier, purchase Item, Purchase Order, lifecycle, and existing
Purchase Order read/search tools. The profile is process configuration, not a
tool argument.

## 4. Call a safe read/resolution tool

Call search_customers with:

~~~json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search_customers",
    "arguments": {
      "query": "Acme"
    }
  }
}
~~~

For typed tools, inspect structuredContent inside the JSON-RPC result. Clients
may also receive a textual content representation. A normal successful result
has this shape:

~~~json
{
  "status": "resolved",
  "doctype": "Customer",
  "query": "Acme",
  "candidates": [
    {
      "reference": {
        "doctype": "Customer",
        "name": "CUSTOMER-NAME",
        "customer_name": "Customer display name"
      },
      "label": "Customer display name",
      "score": 1.0
    }
  ]
}
~~~

Use an exact permitted record from the response. Never infer a document name
from a score or select the first fuzzy match automatically.

Other safe calls include resolve_customer, search_items, resolve_item,
select_resolved_candidate, and profile-appropriate existing-document
read/search tools. select_resolved_candidate accepts:

~~~json
{
  "doctype": "Customer",
  "name": "CUSTOMER-NAME"
}
~~~

or an Item reference. It is stateless and revalidates the exact reference with
normal Frappe permissions; it does not trust a client-supplied candidate list.

## 5. Ambiguity and terminal resolution states

Current Customer, Item, and Supplier resolvers use these terminal states:

| State | Meaning | Postman action |
| --- | --- | --- |
| resolved | One permitted reference was selected deterministically | Use typed reference in the next call. |
| ambiguous | Multiple candidates remain possible | Inspect candidate reference values, choose one manually, then call select_resolved_candidate where supported. |
| not_found | No permitted match was found | Correct the query or ask for an exact identifier. Do not create a guessed record. |
| error | Safe operational error envelope | Record code and reference; inspect server logs using the reference. |

An ambiguous result includes the shared client-neutral interaction directive,
for example kind SELECTION and allowed_actions SELECT, CANCEL. This is semantic
guidance, not a Postman UI command.

## 6. Prepare without a final write

After obtaining exact permitted Customer and Item references, call typed Sales
prepare_quotation:

~~~json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "prepare_quotation",
    "arguments": {
      "customer": {
        "doctype": "Customer",
        "name": "{{test_customer}}"
      },
      "items": [
        {
          "item": {
            "doctype": "Item",
            "name": "{{test_item}}"
          },
          "qty": 1
        }
      ],
      "valid_till": "2027-01-01"
    }
  }
}
~~~

prepare_quotation validates references, applies implemented ERPNext/Frappe
defaults and calculations, and returns needs_input, permission_denied, error, or
ready. A ready result contains a preview, approval_token, expiry, and an
APPROVAL directive.

The preview contains calculated customer, items, taxes, totals, dates, currency,
and commercial values. Preparation builds an unsaved document and does not
perform the final persistent insert. Verify this on the selected site with
read-only checks; do not assume a preview is saved.

Purchase uses analogous prepare_purchase_order with a resolved Supplier,
resolved Item rows, and quantity. Existing-document lifecycle prepare tools
also return a preview without the final operation.

## 7. Confirm/write boundary — manual and test site only

These are CONFIRM_WRITE tools:

~~~text
confirm_customer
confirm_item
confirm_sales_order
confirm_quotation
confirm_purchase_order
confirm_document_update
confirm_document_child_add
confirm_document_submit
confirm_document_cancel
confirm_document_delete
~~~

Every such request is WRITE / TEST SITE ONLY. The public confirmation input
contains an opaque approval_token and confirm: true. confirm: true is a request
to execute the confirmation step; it is not proof that a human approved anything.

The default MCP_APPROVAL_MODE=trusted_human requires an independently
authenticated adapter to record approval for the exact pending operation. No
such approval adapter is exposed as an MCP tool or Postman argument. Therefore
raw Postman confirmation normally fails safely with TRUSTED_APPROVAL_UNAVAILABLE.

In local development only, MCP_APPROVAL_MODE=agent_delegated permits the
authenticated Agent/client to perform the final call after the user approved the
exact preview. It still enforces the same process-local token, action, site,
authenticated user, payload digest, 15-minute TTL, single-use claim, and final
Frappe permission check. Prepare and confirm must use the same MCP process;
restart or a second worker loses or cannot see the pending operation.

The supplied collection marks its confirm request disabled. Do not enable it in
a collection runner. Any authorized manual test must use a development/test
site, followed by exact read-back and a cleanup plan. Never run a write against
production.

Expected guard codes include TRUSTED_APPROVAL_UNAVAILABLE,
CONFIRMATION_EXPIRED, CONFIRMATION_CONSUMED, CONFIRMATION_UNAVAILABLE, and
CONFIRMATION_REQUIRED, depending on operation and token state.

## Negative authentication and protocol tests

Run these separately from the successful flow. Requests requiring an existing
session must first complete Initialize and store its session ID.

| Test | Change | Current expected result |
| --- | --- | --- |
| Missing bearer | Remove Authorization | HTTP 401, Unauthorized; no MCP message reaches SDK. |
| Wrong bearer | Use a different Bearer value | HTTP 401, Unauthorized. |
| Missing user identity | Remove X-MCP-User-Email from valid tools/call | Safe tool error MCP_USER_IDENTITY_MISSING; no operation runs. Handshake/discovery does not currently resolve a Frappe user. |
| Invalid email | Use not-an-email | Safe tool error MCP_USER_IDENTITY_MISSING. |
| Unknown user | Use an email not present as an enabled Frappe User | Safe tool error MCP_USER_NOT_FOUND. |
| Disabled user | Use an authorized known-disabled Frappe User | Safe tool error MCP_USER_DISABLED; an absent account returns MCP_USER_NOT_FOUND. |
| Wrong Host | Override Host with a value absent from allowlist | HTTP 421, Invalid Host header. A proxy may prevent this. |
| Bad Origin | Add any Origin while current allowed-origin list is empty | HTTP 403, Invalid Origin header. Omit Origin normally. |
| Unsupported protocol | Send mcp-protocol-version 2099-01-01 after initialize | HTTP 400 with an MCP error describing supported versions. |
| Missing session | Remove mcp-session-id from a post-init request | HTTP 400 for the session-bound request. |
| Invalid/expired session | Use not-a-real-session | HTTP 404 with Session not found or invalid/expired wording. |
| Invalid JSON | Send malformed JSON | HTTP 400 parse/validation error from SDK. |
| Bad Accept | Send only application/json while SSE mode is active | HTTP 406. |
| Bad Content-Type | Send text/plain | HTTP 400. |

Identity errors are safe MCP tool results because identity is resolved in
runtime.execute_tool_with_context after protocol dispatch. They are not the
same layer as the HTTP middleware's 401 response.

## Permission test

Use two already-authorized test accounts only:

~~~text
User A -> can read the selected record
User B -> lacks the relevant Frappe permission
~~~

Repeat the same safe search, resolve, or existing-document read with the two
X-MCP-User-Email values. Do not change Roles, User Permissions, or database
records as part of this documentation task. If suitable accounts and records
are not already available, the comparison is NOT VERIFIED.

Frappe remains the permission authority. A valid bearer secret authenticates the
client; it does not grant ERPNext access, make the caller Administrator, or
override record-level permissions.

## Troubleshooting by layer

| Layer | Example symptom | Meaning | Where to check |
| --- | --- | --- | --- |
| Network | Connection refused | No process is listening at configured origin/port | Server process, host, port, container/WSL routing |
| HTTP authentication | 401 | Bearer header or shared secret problem | http_transport.py, mcp_identity.identity |
| Host/Origin security | 421 or 403 | SDK DNS-rebinding protection rejected headers | MCP_HTTP_ALLOWED_HOSTS; omit Postman Origin |
| Identity | MCP_USER_IDENTITY_MISSING, MCP_USER_NOT_FOUND, or MCP_USER_DISABLED | Caller could not become an enabled Frappe User | mcp_identity, User record, header |
| MCP protocol | 400/404 | JSON-RPC, negotiated version, or stateful session mismatch | SDK transport and Postman headers |
| Tool contract | Invalid parameters or schema validation | JSON does not match tools/list inputSchema | Live tools/list, contracts, tool name |
| Frappe permission | ERP_PERMISSION_DENIED or PERMISSION_DENIED | Authenticated user lacks required DocType/record permission | Roles/User Permissions and server logs |
| Domain validation | INVALID_CUSTOMER, INVALID_ITEM, INVALID_QUOTATION_DETAILS, INVALID_PURCHASE_ORDER_DETAILS, or similar | ERPNext/MCP business validation failed | Relevant service and returned reference |
| Approval | TRUSTED_APPROVAL_UNAVAILABLE, CONFIRMATION_EXPIRED, or CONFIRMATION_UNAVAILABLE | Final write guard blocked request | Approval mode, same process, token/action/site/user/payload |

Safe error envelopes contain status error, stable code, safe message, an
MCP-ERR-... reference, and retryable. Search server logs with the reference;
the public response excludes stack traces, credentials, headers, and database
details.

## Postman, MCP Inspector, VS Code, and LibreChat

| Client | Role |
| --- | --- |
| Postman | Manual, low-level HTTP protocol testing. The tester sends each JSON-RPC message and follows results manually. |
| MCP Inspector | MCP-aware development/debug client that manages handshake and displays tools. |
| VS Code | MCP client integrated into coding-agent workflow; it may launch stdio or connect to HTTP. |
| LibreChat | Chat/Agent client using MCP tools; the Agent interprets language and conversation. |

All can consume the same profile-specific business server, but transport startup
and identity configuration differ. Streamable HTTP must already be running for
HTTP clients. A compatible MCP client can launch stdio; Postman does not
directly test stdio.

## Verification boundary for this documentation pass

Static source, generated catalog, package metadata, and unit-test contracts were
inspected. A no-write in-process HTTP probe using the installed environment
emitted this SDK warning and did not complete initialize within 30 seconds:

~~~text
IncompleteFieldDefinitionWarning: Field 'lifespan' has an incomplete definition
~~~

That is a current runtime/dependency verification blocker, not evidence that a
tool was called or an ERPNext record changed. No database write was made and no
claim of a live Postman handshake is made here. Re-run the ordered collection
after the installed SDK/runtime handshake is healthy.

## Source map

- [mcp_server.py](../../mcp_erpnext/mcp_server.py): FastMCP construction, profile registration, and transport startup.
- [settings.py](../../mcp_erpnext/settings.py): environment names, defaults, validation, profiles, and approval mode.
- [http_transport.py](../../mcp_erpnext/http_transport.py): Bearer middleware and HTTP path.
- [runtime.py](../../mcp_erpnext/runtime.py): request identity extraction, Frappe context, and per-call cleanup.
- mcp_identity/identity.py in the sibling app: shared-secret and enabled Frappe User resolution.
- [TOOLS.md](../TOOLS.md): generated static inventory and contract summary.
- [MCP_EXPLICIT_USER_APPROVAL_SAFETY.md](../architecture/MCP_EXPLICIT_USER_APPROVAL_SAFETY.md): write guard details.
- [MCP_CONVERSATIONAL_INTERACTION_CONTRACT.md](../architecture/MCP_CONVERSATIONAL_INTERACTION_CONTRACT.md): client/server interaction boundary.

