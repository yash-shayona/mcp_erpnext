# Connect `mcp_erpnext` to Codex

The current server is a local stdio MCP server. Add this entry to the Codex
configuration for the user or trusted project that will run it:

```toml
[mcp_servers.erpnext]
command = "/home/frappe/frappe-bench/env/bin/python"
args = ["-m", "mcp_erpnext.mcp_server"]
# Frappe's core file log handlers resolve paths from the bench `sites`
# directory (for example, `../logs/database.log`).
cwd = "/home/frappe/frappe-bench/sites"
env_vars = ["MCP_BACKEND", "MCP_FRAPPE_SITE", "MCP_FRAPPE_USER", "MCP_APPROVAL_MODE", "MCP_PROFILE"]
default_tools_approval_mode = "writes"
```

Before starting Codex, provide the non-secret site and service-user values in
the process environment (or in the Codex `env` table):

```bash
export MCP_BACKEND=direct
export MCP_FRAPPE_SITE=your-site.localhost
export MCP_FRAPPE_USER=mcp-service@example.com
export MCP_APPROVAL_MODE=agent_delegated
export MCP_PROFILE=sales
```

`MCP_APPROVAL_MODE` is server configuration, never an MCP tool argument.
`MCP_PROFILE` is also server configuration. It defaults to `sales`; set it to
`purchase` for a separate Purchase MCP registration. See
[`MCP_PROFILES.md`](MCP_PROFILES.md) for both profile configurations.
`trusted_human` is the default and requires an independently verified,
internally recorded human decision. `agent_delegated` is suitable for a trusted
chat Agent/client that calls `confirm_*` only after the user explicitly
approves the prepared preview; the server still validates the token, user,
site, action, payload, expiry, replay protection, and Frappe permissions.

Do not put an API secret, password, or real credential in this repository. A
private `.env` file may be used by a local wrapper, but Codex does not
automatically load arbitrary `.env` files; use its `env`/`env_vars` settings or
source the file before launching Codex.

Codex uses the local stdio setup above. HTTP clients supply a bearer secret and
the generic `X-MCP-User-Email` header for each request; `mcp_identity` resolves
the enabled Frappe User without a provider-specific mapping. Frappe roles and
User Permissions remain the permission authority.

The app must also be installed on the selected Frappe site before the server
can use its ERPNext capabilities:

```bash
./env/bin/bench --site your-site.localhost install-app mcp_erpnext
```

That command is intentionally not run by this implementation. Review the app,
choose the site, and run it only when ready.

Codex uses the local STDIO setup above. This app also provides a separately
configured Streamable HTTP bridge for LibreChat; see
[`LIBRECHAT_MCP_HTTP_SETUP.md`](LIBRECHAT_MCP_HTTP_SETUP.md). The HTTP bridge
uses request-scoped generic identity and is not configured through a Codex
tool argument. Its current controlled capabilities span Customer and Item
masters plus Quotation and Sales Order workflows. The planned REST backend
variables are documented in `.env.example` and are not active yet.

Errors are written through Frappe's logger to the bench `logs/mcp_erpnext.log`
and the selected site's `sites/<site>/logs/mcp_erpnext.log`. Do not set
`FRAPPE_STREAM_LOGGING` for this server, because that setting is intended for
stream-only diagnostics and prevents the normal file handler.

Every error response contains two different identifiers:

| Field | Purpose | Example |
| --- | --- | --- |
| `code` | Stable, machine-readable error category | `ERP_PERMISSION_DENIED` |
| `reference` | Unique log-correlation identifier for one occurrence | `MCP-ERR-97C4A07F` |

`ERP_REQUEST_FAILED` remains the safe fallback for unexpected failures. A
permission failure returns `ERP_PERMISSION_DENIED` and logs the same
`reference` with the tool, site, and a one-way fingerprint of the configured
user. Search the site log with that complete reference; the random suffix is
intentional and must not be treated as an error category.

If the MCP process cannot open a log file, it writes a minimal diagnostic to
standard error and still returns the original safe MCP error envelope. This
prevents an operating-system log-file permission issue from hiding an ERPNext
permission or validation failure.

See the [OpenAI Codex MCP configuration guide](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
for the supported configuration locations and fields.
