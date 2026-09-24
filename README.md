# ERPNext MCP Server

`mcp_erpnext` exposes bounded, profile-specific ERPNext capabilities through MCP. It is not a generic ERPNext, Frappe, SQL, or arbitrary-DocType CRUD interface. Native Frappe and ERPNext remain authoritative for document validation, permissions, defaults, ledgers, and transactional side effects.

## Ownership and architecture

`mcp_erpnext` owns FastMCP construction, transport and backend selection, profile-specific tool registration, request-scoped Frappe lifecycle, typed tool contracts, approvals, and business-service orchestration. Its required apps are `erpnext` and `mcp_identity`.

`mcp_identity` owns HTTP authentication-mode configuration, trusted-header authentication, configured stdio-user validation, and Frappe OAuth resource-binding/token-verification support. It does not own MCP business tools or ERPNext permissions. See [the current architecture reference](docs/ERPNext_MCP_ARCHITECTURE.md) and [`mcp_identity`'s README](../mcp_identity/README.md).

```text
MCP client -> stdio or Streamable HTTP -> authenticated execution identity (when HTTP)
           -> selected profile's MCP tools -> mcp_erpnext services and scoped Frappe context
           -> native Frappe / ERPNext permissions and business rules
```

## Profiles and public tools

`MCP_PROFILE` selects one public inventory per process. It is server configuration, never a tool argument. Omitted means `sales`; accepted values are `sales`, `purchase`, and `accounts`.

| Profile | Current scope |
| --- | --- |
| `sales` (default) | Customer, Item, and Contact masters; Quotation, Sales Order, Sales Invoice, and Delivery Note workflows/conversions; exact reads, queries/aggregates, lifecycle, PDF, and document email where registered. |
| `purchase` | Supplier and purchase Item resolution; Purchase Order workflow, lifecycle/read, PDF, and document email. |
| `accounts` | Sales Invoice payments, multi-invoice receipts, standalone Payment Entries, Sales Order advances, payment reconciliation, Payment Entry reads/queries/aggregates, and applicable lifecycle actions. |

Profiles isolate exposed MCP capabilities; they do not grant ERPNext access. Every call remains subject to the resolved user's normal Frappe and ERPNext permissions. The generated [tool catalog](docs/TOOLS.md) is the human-readable inventory; MCP `tools/list` is the machine-readable authority.

## Write safety

Consequential operations use a prepare -> preview -> approval -> confirm boundary. Prepare returns a server-held pending operation and does not make the final write. Confirm reclaims that operation atomically and rechecks its site, user, action, payload digest, expiry, single-use state, and normal Frappe permissions before native persistence.

`MCP_APPROVAL_MODE` is server-only and defaults to `agent_delegated`: the authenticated MCP client/Agent must obtain explicit user approval before it calls a confirm tool. `trusted_human` instead requires an independently verified, internally recorded approval; without it confirmation fails closed with `TRUSTED_APPROVAL_UNAVAILABLE`. A tool argument such as `confirm=true` never provides that approval. Pending operations live in Frappe's configured shared Redis cache, so compatible workers can claim a still-valid operation; expiry, eviction, flush, or Redis loss requires a fresh prepare. See [approval safety](docs/architecture/MCP_EXPLICIT_USER_APPROVAL_SAFETY.md).

## Runtime, transport, and identity

The default local path is `MCP_BACKEND=direct` with `MCP_TRANSPORT=stdio`. It requires `MCP_FRAPPE_SITE` and `MCP_FRAPPE_USER`; after the app opens the site context, `mcp_identity` validates the configured enabled non-Guest Frappe User and `mcp_erpnext` applies it with `frappe.set_user()`.

For `MCP_TRANSPORT=streamable-http`, `MCP_BACKEND` must be `direct`. HTTP has two exact, case-sensitive `MCP_HTTP_AUTH_MODE` values, owned by `mcp_identity`:

- `trusted_header` is the backward-compatible default. It requires a server-only `MCP_HTTP_SHARED_SECRET` of at least 32 characters in `Authorization: Bearer ...` plus `X-MCP-User-Email` on every request. The email is resolved only after bearer authentication to an enabled non-Guest Frappe User.
- `oauth` is implemented for Streamable HTTP. FastMCP uses `mcp_identity`'s Frappe-native opaque-token verifier and protected-resource settings. The token's Frappe User is the only execution identity; `X-MCP-User-Email`, `MCP_FRAPPE_USER`, and the shared secret have no authority in this mode.

HTTP never falls back to the process-level stdio user and clears Frappe context before and after each tool call. OAuth startup requires `mcp_identity` to be installed and migrated on the target site, a resource-bound native Frappe OAuth Client, and `MCP_OAUTH_ISSUER_URL`, `MCP_OAUTH_RESOURCE_SERVER_URL`, `MCP_OAUTH_REQUIRED_SCOPES`, and `MCP_OAUTH_FRAPPE_CLIENT_ID`. The OAuth client must support authorization code + `code`, have the canonical public `/mcp` resource configured, and issue a token with every required scope. The detailed resource-binding setup is in [`mcp_identity`'s README](../mcp_identity/README.md).

`MCP_BACKEND=rest` is also implemented, but supports only `stdio`. It calls the fixed `mcp_erpnext.remote_api.execute_mcp_operation` bridge on a compatible remote site as the remote API key/secret owner, never as a caller-selected identity and never through generic CRUD. REST requires `ERPNEXT_BASE_URL`, `ERPNEXT_API_KEY`, and `ERPNEXT_API_SECRET`; HTTPS is required except for an explicit loopback development origin with `MCP_REST_ALLOW_INSECURE_HTTP=1`.

## Setup and operation

Copy [`.env.example`](.env.example) only as a private starting point; the server does not load `.env` itself. The selected site must have both apps installed and migrations applied before their code or OAuth Custom Fields are available. Installation/migration, service start/restart, and deployment are operator actions.

- [Commands](docs/COMMANDS.md): reusable stdio and Streamable HTTP launch patterns.
- [Profile guide](docs/MCP_PROFILES.md): per-profile launch and client examples.
- [Codex stdio setup](docs/MCP_SETUP.md) and [LibreChat trusted-header setup](docs/LIBRECHAT_MCP_HTTP_SETUP.md).
- [Postman Streamable HTTP guide](docs/testing/POSTMAN_MCP_HTTP_TESTING.md): manual trusted-header protocol testing.

Never put real credentials, bearer secrets, or OAuth tokens in this repository or MCP tool arguments.

## Contributing

New or changed public MCP tools must follow the [MCP Tool Contract Standard](docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md): typed input/output contracts, side-effect classification, contract tests, and a checked generated catalog. Resolver changes must preserve `ambiguous` until an explicit candidate is selected and revalidated.

## License

mit
