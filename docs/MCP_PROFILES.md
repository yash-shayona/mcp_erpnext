# MCP Profiles

`mcp_erpnext` is one Frappe app. `MCP_PROFILE` selects one public MCP inventory per process; it is not a tool argument. An unset value is `sales`. The only accepted values are `sales`, `purchase`, and `accounts`; any other value fails startup.

| Profile | Current scope |
| --- | --- |
| `sales` (default) | Customer, Item, and Contact masters; selling workflows/conversions; Sales document reads/query/aggregate, lifecycle, PDF, and email where registered. |
| `purchase` | Supplier/purchase Item resolution, Purchase Order workflow, lifecycle/read, PDF, and email. |
| `accounts` | Customer-payment, advance, receipt, reconciliation, Payment Entry read/query/aggregate, and lifecycle capabilities. |

The generated [tool catalog](TOOLS.md) gives the exact inventory. `tools/list` is authoritative for the process that a client actually connects to. Profiles never override Frappe or ERPNext permissions.

## Stdio

Run a separate client-launched process for each required profile. Stdio uses the configured `MCP_FRAPPE_USER` after `mcp_identity` validates it against the selected site.

```bash
cd /home/frappe/frappe-bench/sites
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost \
MCP_FRAPPE_USER=mcp-service@example.com MCP_APPROVAL_MODE=agent_delegated \
MCP_PROFILE=sales ../env/bin/python -m mcp_erpnext.mcp_server
```

Use `MCP_PROFILE=purchase` or `MCP_PROFILE=accounts` for separate client registrations. `MCP_BACKEND=rest` is supported only with `MCP_TRANSPORT=stdio` and uses the configured remote API-key principal; it does not forward a request-scoped user.

## Streamable HTTP

Streamable HTTP requires `MCP_BACKEND=direct`. Run a separate process and port for every profile that must be exposed. The examples below use the implemented `trusted_header` mode; add `MCP_HTTP_AUTH_MODE=trusted_header` explicitly when sourcing an environment where it might otherwise differ.

```bash
cd /home/frappe/frappe-bench/sites
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost MCP_TRANSPORT=streamable-http \
MCP_HTTP_AUTH_MODE=trusted_header MCP_PROFILE=sales MCP_HTTP_HOST=0.0.0.0 \
MCP_HTTP_PORT=8765 MCP_HTTP_PATH=/mcp \
MCP_HTTP_SHARED_SECRET='<minimum-32-character-secret>' \
MCP_HTTP_ALLOWED_HOSTS='host.docker.internal:8765,localhost:8765,127.0.0.1:8765' \
../env/bin/python -m mcp_erpnext.mcp_server
```

For another profile, choose a distinct port and matching explicit allowed hosts, for example `purchase` on `8766` or `accounts` on `8767`. In trusted-header mode every request must include the shared bearer secret and `X-MCP-User-Email`; the enabled non-Guest Frappe User resolved from that email is the execution user. HTTP never falls back to `MCP_FRAPPE_USER`.

OAuth is an alternative implemented HTTP mode, not an additional header. It needs the installed/migrated `mcp_identity` app, a resource-bound Frappe OAuth Client, and the OAuth environment settings documented in [`mcp_identity`'s README](../../mcp_identity/README.md). In OAuth mode the native token owner is the execution user; do not send or rely on the trusted-header identity values.

## Trusted-header LibreChat example

```yaml
mcpServers:
  erpnext-sales:
    type: streamable-http
    url: "http://host.docker.internal:8765/mcp"
    headers:
      Authorization: "Bearer ${MCP_HTTP_SHARED_SECRET}"
      X-MCP-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    timeout: 120000
```

This client configuration is for `trusted_header` only. The full LibreChat development bridge is in [LIBRECHAT_MCP_HTTP_SETUP.md](LIBRECHAT_MCP_HTTP_SETUP.md).

`MCP_APPROVAL_MODE=agent_delegated` is the default trusted-client policy. `trusted_human` requires an authenticated adapter to record approval for the exact pending operation. Pending tokens use Frappe's configured shared Redis cache; separate compatible workers can claim a still-valid operation, while expiry, eviction, flush, or Redis loss requires a fresh prepare.
