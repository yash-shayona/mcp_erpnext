# MCP ERPNext Commands

These commands start one MCP HTTP process for each public profile as the
Bench-owning Linux user. Run each process in its own terminal from the bench
`sites` directory. The MCP server does not load `.env` automatically, so each
command sources `apps/mcp_erpnext/.env` explicitly.

## Prepare

Copy the example configuration and edit the site, user, and secret values:

```bash
BENCH_ROOT="/path/to/your/frappe-bench"
cd "$BENCH_ROOT"
cp apps/mcp_erpnext/.env.example apps/mcp_erpnext/.env
chmod 600 apps/mcp_erpnext/.env
```

The HTTP auth mode defaults to `trusted_header`; the example sets it explicitly.
In that mode the shared secret must be at least 32 characters. Keep `.env`
private and never commit it. OAuth mode instead uses the native Frappe OAuth
Client/token settings documented by `mcp_identity` and does not use the shared
secret or `X-MCP-User-Email`.

## Streamable HTTP

Open a separate terminal for each profile and run the profile-specific block
below as the Linux user that owns the Bench directory and can read
`apps/mcp_erpnext/.env`. If necessary, switch to that OS user using the normal
user-switching method for the host. Do not use an ERPNext login email as the
Linux username.

### Sales Profile

```bash
BENCH_ROOT="/path/to/your/frappe-bench"
cd "$BENCH_ROOT/sites"
source ../env/bin/activate
set -a
source ../apps/mcp_erpnext/.env
set +a
export MCP_PROFILE=sales
export MCP_HTTP_PORT=8765
export MCP_HTTP_ALLOWED_HOSTS='127.0.0.1:8765,localhost:8765,host.docker.internal:8765'
exec python -m mcp_erpnext.mcp_server
```

### Purchase Profile

```bash
BENCH_ROOT="/path/to/your/frappe-bench"
cd "$BENCH_ROOT/sites"
source ../env/bin/activate
set -a
source ../apps/mcp_erpnext/.env
set +a
export MCP_PROFILE=purchase
export MCP_HTTP_PORT=8766
export MCP_HTTP_ALLOWED_HOSTS='127.0.0.1:8766,localhost:8766,host.docker.internal:8766'
exec python -m mcp_erpnext.mcp_server
```

The endpoints are:

```text
Sales:    http://127.0.0.1:8765/mcp
Purchase: http://127.0.0.1:8766/mcp
```

After both processes are running, configure VS Code to connect to these HTTP
endpoints. VS Code must not start these servers as `stdio` processes.

Use the same shared secret for both entries and send the ERPNext identity in
the `X-MCP-User-Email` header.

## Stdio

Stdio is for a client that starts its own MCP process. It runs as the current
Linux user and should not be used together with the manually managed HTTP
processes above.

```bash
BENCH_ROOT="/path/to/your/frappe-bench"
cd "$BENCH_ROOT/sites"
source ../env/bin/activate
set -a
source ../apps/mcp_erpnext/.env
set +a
export MCP_TRANSPORT=stdio
export MCP_PROFILE=sales
exec python -m mcp_erpnext.mcp_server
```

Replace placeholders with local environment values. Never put real passwords,
API keys, tokens, or shared secrets in this file.

## Codex Host PREPARE Overrides

Generate the non-secret Policy-B override tables from the current public-tool
contracts. Replace the placeholder with the exact existing Codex MCP server ID;
this prints child tables only and never reads or changes `config.toml`.

```bash
cd /path/to/your/frappe-bench/apps/mcp_erpnext
PYTHONDONTWRITEBYTECODE=1 /path/to/your/frappe-bench/env/bin/python \
  scripts/generate_tool_catalog.py --prepare-approval-overrides \
  --server-id '<existing-server-id>'
```

Follow [MCP Host Approval Policy](operations/MCP_HOST_APPROVAL_POLICY.md) for
the required `writes` baseline, validation, and rollback procedure.
