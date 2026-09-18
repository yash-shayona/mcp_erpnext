# LibreChat Streamable HTTP MCP setup

This is a controlled Docker-to-WSL development bridge. It is not a public
deployment: use firewall and network controls, do not expose its plain-HTTP
endpoint publicly, and run exactly one MCP process/worker because approvals
are process-local.

Start the MCP process manually from the bench `sites` directory. `0.0.0.0` is
explicit for this Docker-to-WSL development bridge only; it is not the default.

```bash
export MCP_BACKEND=direct
export MCP_FRAPPE_SITE=yob.localhost
export MCP_TRANSPORT=streamable-http
export MCP_HTTP_AUTH_MODE=trusted_header
export MCP_PROFILE=sales
export MCP_HTTP_HOST=0.0.0.0
export MCP_HTTP_PORT=8765
export MCP_HTTP_PATH=/mcp
export MCP_HTTP_SHARED_SECRET='<strong-development-secret-at-least-32-characters>'
export MCP_HTTP_ALLOWED_HOSTS='host.docker.internal:8765,localhost:8765,127.0.0.1:8765'

cd /home/frappe/frappe-bench/sites
../env/bin/python -m mcp_erpnext.mcp_server
```

For every HTTP request, the server verifies the Bearer secret and resolves the
generic `X-MCP-User-Email` to an existing enabled Frappe User. Missing,
unknown, or disabled users fail closed; HTTP never becomes Administrator or
uses the process service user.

Configure LibreChat's mounted YAML and its `.env` with the same secret. A
LibreChat restart is an operator action.

```yaml
mcpSettings:
  allowedAddresses:
    - "host.docker.internal:8765"

mcpServers:
  erpnext-sales:
    type: streamable-http
    url: "http://host.docker.internal:8765/mcp"
    headers:
      Authorization: "Bearer ${MCP_HTTP_SHARED_SECRET}"
      X-MCP-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    timeout: 120000
```

To connect Purchase simultaneously, start a second process with
`MCP_PROFILE=purchase`, `MCP_HTTP_PORT=8766`, and matching explicit allowed
hosts. Add this second LibreChat entry:

```yaml
  erpnext-purchase:
    type: streamable-http
    url: "http://host.docker.internal:8766/mcp"
    headers:
      Authorization: "Bearer ${MCP_HTTP_SHARED_SECRET}"
      X-MCP-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    timeout: 120000
```

The complete two-process commands are in [`MCP_PROFILES.md`](MCP_PROFILES.md).

```dotenv
MCP_HTTP_SHARED_SECRET=<same-secret-used-by-WSL-MCP-process>
```

Do not send `X-Frappe-User`, roles, `run_as`, or `Administrator`. Frappe roles
and User Permissions are evaluated only after the resolved Frappe User is set.
