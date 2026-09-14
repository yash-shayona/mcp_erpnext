# REST Backend Implementation Report

## Scope

Task 40 adds a bounded remote-execution path for `MCP_BACKEND=rest`. The local
MCP public tool names, typed contracts, profiles, interaction directives, and
direct Frappe/ORM path remain unchanged.

The implementation adds:

```text
mcp_erpnext/rest_client.py
  HTTPS API-token client with a fixed endpoint, 15 second timeout, and no redirects

mcp_erpnext/remote_api.py
  non-guest Frappe whitelisted bridge endpoint

mcp_erpnext/remote_operations.py
  static Sales, Purchase, and shared-operation handler registry
```

All 52 current public wrapper call sites pass their typed JSON-safe request
payload to the shared backend boundary. Direct mode ignores that payload and
continues to execute its existing local callable. REST mode sends it to the
remote bridge and does not initialize a local Frappe site.

## Execution and authority trace

```text
MCP wrapper
  -> execute_tool_with_context(..., rest_arguments=typed JSON payload)
  -> ERPNextRestClient
  -> POST /api/method/mcp_erpnext.remote_api.execute_mcp_operation
  -> Frappe API-token authentication
  -> static remote operation registry
  -> existing native service
  -> remote Frappe permissions, approvals, transaction, and result
```

The remote bridge does not expose generic DocType CRUD, arbitrary method
dispatch, caller-selected user identity, or arbitrary operation imports.

## Identity and approval boundary

REST executes as the remote Frappe user who owns the configured API key and
secret. To avoid silently replacing the existing request-scoped HTTP identity
model, `MCP_BACKEND=rest` rejects `MCP_TRANSPORT=streamable-http`; it currently
supports local MCP stdio only.

Prepare/confirm tokens remain created and claimed on the remote site through
the installed shared `ApprovalStore` implementation. The local client does not
read or mutate approval records. Confirm-write requests are not automatically
retried after a network failure.

## Transport safeguards

- `ERPNEXT_BASE_URL` must be an HTTPS origin without a path, credentials,
  query, or fragment. The only exception is explicit local development with
  `MCP_REST_ALLOW_INSECURE_HTTP=1` and a loopback-only origin such as
  `http://yob.localhost:8000`; LAN and live origins still require HTTPS.
- The request target is fixed; API credentials occur only in the Authorization
  header.
- Redirects are disabled.
- The client requires a JSON object in Frappe's normal `message` envelope.
- Remote validation, permission, and unexpected failures return safe bounded
  envelopes. The remote server log records unexpected errors without request
  arguments, approval tokens, or credentials.
- PDF bytes cross this single bridge as validated base64 and are restored only
  for the existing MCP artifact wrapper.

## Verification

Static syntax parsing and `git diff --check` completed without errors.

Focused command:

```bash
cd BENCH_ROOT/apps/mcp_erpnext
../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_rest_backend \
  mcp_erpnext.tests.test_runtime \
  mcp_erpnext.tests.test_http_transport \
  mcp_erpnext.tests.test_identity \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_create_contracts
```

Result: **53 tests passed**. The interpreter emitted the existing FastMCP
`IncompleteFieldDefinitionWarning` and environment-prefix warnings; neither
failed the suite.

Full command:

```bash
cd BENCH_ROOT/apps/mcp_erpnext
../../env/bin/python -m unittest discover -s mcp_erpnext/tests
```

Result: **288 tests run; 1 failure and 4 errors**. They are existing
approval-policy expectation failures caused by the current in-progress change
that makes `agent_delegated` the default while those tests still expect
`trusted_human`. They occur in Customer, Item, Purchase Order, Quotation, and
Email approval tests, not in the REST transport path.

No real remote ERPNext site, API credentials, network connection, remote
Frappe authentication, or remote document write was used in this verification.
