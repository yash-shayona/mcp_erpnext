# MCP ERPNext Commands

These commands start one MCP process for each public profile. Run them from
`/home/frappe/frappe-bench/sites`.

## Stdio

### Sales Profile

```bash
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost \
MCP_FRAPPE_USER=mcp-service@example.com MCP_APPROVAL_MODE=agent_delegated \
MCP_PROFILE=sales ../env/bin/python -m mcp_erpnext.mcp_server
```

### Purchase Profile

```bash
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost \
MCP_FRAPPE_USER=mcp-service@example.com MCP_APPROVAL_MODE=agent_delegated \
MCP_PROFILE=purchase ../env/bin/python -m mcp_erpnext.mcp_server
```

## Streamable HTTP

### Sales Profile

```bash
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost \
MCP_TRANSPORT=streamable-http MCP_PROFILE=sales \
MCP_HTTP_HOST=0.0.0.0 MCP_HTTP_PORT=8765 MCP_HTTP_PATH=/mcp \
MCP_HTTP_SHARED_SECRET='<minimum-32-character-secret>' \
MCP_HTTP_ALLOWED_HOSTS='host.docker.internal:8765,localhost:8765,127.0.0.1:8765' \
../env/bin/python -m mcp_erpnext.mcp_server
```

### Purchase Profile

```bash
MCP_BACKEND=direct MCP_FRAPPE_SITE=your-site.localhost \
MCP_TRANSPORT=streamable-http MCP_PROFILE=purchase \
MCP_HTTP_HOST=0.0.0.0 MCP_HTTP_PORT=8766 MCP_HTTP_PATH=/mcp \
MCP_HTTP_SHARED_SECRET='<minimum-32-character-secret>' \
MCP_HTTP_ALLOWED_HOSTS='host.docker.internal:8766,localhost:8766,127.0.0.1:8766' \
../env/bin/python -m mcp_erpnext.mcp_server
```

Replace placeholders with local environment values. Never put real passwords,
API keys, tokens, or shared secrets in this file.