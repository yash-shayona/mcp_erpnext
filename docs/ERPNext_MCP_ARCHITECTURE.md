# ERPNext MCP Architecture

This is the current architecture reference for `mcp_erpnext`. Source code, generated tool registration, and runtime configuration are authoritative when they differ from prose.

## Boundaries

`mcp_erpnext` owns the FastMCP server, selected transport/backend, profile-specific registration, tool contracts, services, Frappe runtime scoping, and approval guard. It depends on `erpnext` and `mcp_identity`.

`mcp_identity` owns HTTP auth-mode parsing, trusted-header middleware/user resolution, configured stdio-user validation, Frappe OAuth resource binding, and opaque-token verification. It does not own MCP business tools, profile selection, Frappe lifecycle, or ERPNext permission decisions.

```text
Client -> transport -> authentication / execution identity -> selected profile tools
       -> mcp_erpnext service + scoped Frappe context -> native Frappe / ERPNext
```

Frappe roles, User Permissions, document permissions, controllers, validation, and accounting behavior remain authoritative. Callers cannot select a Frappe user, role, `run_as`, site, SQL, DocType, or method through a tool argument.

## Runtime matrix

| Backend / transport | Identity and behavior |
| --- | --- |
| `direct` + `stdio` | `MCP_FRAPPE_SITE` and `MCP_FRAPPE_USER` are required. `mcp_identity` validates the enabled non-Guest configured user after site initialization; `mcp_erpnext` applies it to Frappe. |
| `direct` + `streamable-http` + `trusted_header` | Default when `MCP_HTTP_AUTH_MODE` is absent. A 32+ character server-only bearer secret authenticates the request; then `X-MCP-User-Email` resolves to the enabled non-Guest Frappe execution user. No stdio-user fallback exists. |
| `direct` + `streamable-http` + `oauth` | Implemented resource-server mode. FastMCP verifies native opaque Frappe bearer tokens through `FrappeOAuthTokenVerifier`; the token subject is the only execution user. Trusted-header values and `MCP_FRAPPE_USER` have no authority. |
| `rest` + `stdio` | Implemented fixed typed bridge to `mcp_erpnext.remote_api.execute_mcp_operation` on a compatible remote site. The remote API-key owner is the execution principal. Streamable HTTP is rejected for this backend. |

HTTP tool execution destroys Frappe local state before and after each call. This prevents request identity/session reuse across Streamable HTTP calls.

## OAuth resource-server requirements

OAuth needs `mcp_identity` installed and migrated on the target Frappe site. Its patch adds the optional `custom_mcp_resource` field to native `OAuth Client`, `OAuth Authorization Code`, and `OAuth Bearer Token`; no parallel token store is created.

The selected pre-registered OAuth Client must permit authorization code and `code`, have a canonical HTTPS public MCP resource (including `/mcp`), and be selected by `MCP_OAUTH_FRAPPE_CLIENT_ID`. OAuth startup also requires canonical `MCP_OAUTH_ISSUER_URL`, `MCP_OAUTH_RESOURCE_SERVER_URL`, at least one `MCP_OAUTH_REQUIRED_SCOPES` value, and `MCP_FRAPPE_SITE`. Resource/client/token equality, active non-expired token status, required scopes, and an enabled non-Guest token user are checked before access is granted. See [`mcp_identity`'s README](../../mcp_identity/README.md) for the authorization-server binding flow.

## Profiles and tools

`MCP_PROFILE` accepts `sales` (default), `purchase`, or `accounts` and selects exactly one inventory for one process. Profiles limit MCP exposure but do not grant document permissions.

- Sales: Customer, Item, Contact, selling documents and conversions, reads/query/aggregate, lifecycle, PDF, and email where registered.
- Purchase: Supplier/purchase Item and Purchase Order capabilities, lifecycle/read, PDF, and email.
- Accounts: Payment Entry/payment/receipt/advance/reconciliation capabilities, Payment Entry reads/query/aggregate, and lifecycle.

The exact source-derived inventory is [TOOLS.md](TOOLS.md); MCP `tools/list` is the authority for a live connection. Do not duplicate a manually maintained list elsewhere.

## Write and approval boundary

Persistent operations use prepare -> preview -> approval -> confirm. `PREPARE` does not make the final write. A `CONFIRM_WRITE` claims a server-held operation atomically and verifies its user, site, action, payload digest, expiry, and single-use state before normal Frappe persistence.

`MCP_APPROVAL_MODE` is server-only. `agent_delegated` (default) requires the authenticated MCP client/Agent to interpret explicit user approval before confirm; `trusted_human` also requires an independently verified approval recorded through the internal seam. A public `confirm=true` flag never bypasses either guard. Frappe's configured shared Redis cache stores pending operations, so compatible workers may share still-valid state; cache loss or expiry requires a fresh prepare.

## Deployment boundaries

Code availability in the Bench does not prove installation on the target site. Both apps must be installed; OAuth resource fields additionally require the `mcp_identity` patch to be migrated. Streamable HTTP `/mcp` is protected stateful MCP JSON-RPC, not a REST health endpoint: authenticate `initialize`, send `notifications/initialized`, retain negotiated session/protocol headers, inspect `tools/list`, then use a safe read. Runtime/site/client deployment verification remains distinct from source and test evidence.
