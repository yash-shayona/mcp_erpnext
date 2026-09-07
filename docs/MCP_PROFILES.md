# MCP Sales and Purchase Profiles

`mcp_erpnext` remains one Frappe app. `MCP_PROFILE` selects the public MCP
inventory for one process; it is not an MCP tool argument.

| Profile | Default | Public workflow tools |
| --- | --- | --- |
| `sales` | Yes | Customer, sales Item, Quotation, and Sales Order tools |
| `purchase` | No | Supplier, purchase Item, and Purchase Order tools |

An unset `MCP_PROFILE` is `sales`, preserving existing startup behavior. Any
other value fails process startup with a clear configuration error.

## Stdio

Run one process per profile. These examples use the same app installation and
site; choose distinct client registrations because stdio transports cannot
share a single process.

```bash
cd /home/frappe/frappe-bench/sites
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost \
MCP_FRAPPE_USER=mcp-service@example.com MCP_APPROVAL_MODE=agent_delegated \
MCP_PROFILE=sales ../env/bin/python -m mcp_erpnext.mcp_server
```

```bash
cd /home/frappe/frappe-bench/sites
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost \
MCP_FRAPPE_USER=mcp-service@example.com MCP_APPROVAL_MODE=agent_delegated \
MCP_PROFILE=purchase ../env/bin/python -m mcp_erpnext.mcp_server
```

## Streamable HTTP / LibreChat

Run separate processes on separate ports. The bearer secret and generic
request identity stay identical; Frappe permissions are still evaluated per
resolved user.

```bash
cd /home/frappe/frappe-bench/sites
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost MCP_TRANSPORT=streamable-http \
MCP_PROFILE=sales MCP_HTTP_HOST=0.0.0.0 MCP_HTTP_PORT=8765 MCP_HTTP_PATH=/mcp \
MCP_HTTP_SHARED_SECRET='<minimum-32-character-secret>' \
MCP_HTTP_ALLOWED_HOSTS='host.docker.internal:8765,localhost:8765,127.0.0.1:8765' \
../env/bin/python -m mcp_erpnext.mcp_server
```

```bash
cd /home/frappe/frappe-bench/sites
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost MCP_TRANSPORT=streamable-http \
MCP_PROFILE=purchase MCP_HTTP_HOST=0.0.0.0 MCP_HTTP_PORT=8766 MCP_HTTP_PATH=/mcp \
MCP_HTTP_SHARED_SECRET='<minimum-32-character-secret>' \
MCP_HTTP_ALLOWED_HOSTS='host.docker.internal:8766,localhost:8766,127.0.0.1:8766' \
../env/bin/python -m mcp_erpnext.mcp_server
```

```yaml
mcpServers:
  erpnext-sales:
    type: streamable-http
    url: "http://host.docker.internal:8765/mcp"
    headers:
      Authorization: "Bearer ${MCP_HTTP_SHARED_SECRET}"
      X-MCP-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    timeout: 120000
  erpnext-purchase:
    type: streamable-http
    url: "http://host.docker.internal:8766/mcp"
    headers:
      Authorization: "Bearer ${MCP_HTTP_SHARED_SECRET}"
      X-MCP-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    timeout: 120000
```

`agent_delegated` is shown only for the existing trusted-client development
mode. The default `trusted_human` remains fail-closed until an authenticated
human-approval adapter records approval for the exact pending operation.

Each confirmation token is process-local. Keep prepare and confirm calls on the
same profile process; do not run multiple workers for one endpoint.
