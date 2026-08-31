# ERPNext MCP Server

`mcp_erpnext` is one local ERPNext MCP server. It exposes a small, controlled
set of reusable ERPNext capabilities; it is not a generic ERPNext, Frappe, SQL,
or arbitrary-DocType CRUD interface.

The server supports local STDIO and an explicitly configured Streamable HTTP
bridge. Both transports use the same registered tool catalog:

```text
MCP Client / Agent
        |
        v
MCP transport
        |
        v
Domain MCP tools
        |
        v
ERPNext services
        |
        v
Frappe runtime and permissions
        |
        v
ERPNext
```

## Current capabilities

One server contains multiple domain capabilities:

```text
ERPNext MCP Server
|
|-- Masters
|   |-- Customer
|   `-- Item
|
`-- Selling
    |-- Quotation
    `-- Sales Order
```

Customer and Item are reusable master capabilities. Quotation and Sales Order
are Selling capabilities in this same server, not separate MCP servers. For
example, a client can resolve or create a Customer through the Customer master
capability before preparing either a Quotation or a Sales Order.

The source-registered MCP tools are:

```text
search_customers
resolve_customer
prepare_customer
confirm_customer

search_items
resolve_item
prepare_item
confirm_item

prepare_sales_order
confirm_sales_order

prepare_quotation
confirm_quotation
```

The current architecture and the complete tool catalog are documented in
[`docs/ERPNext_MCP_ARCHITECTURE.md`](docs/ERPNext_MCP_ARCHITECTURE.md). The
original, narrower Sales Order baseline is preserved in
[`docs/MCP_SALES_ORDER_V1_FROZEN.md`](docs/MCP_SALES_ORDER_V1_FROZEN.md).

## Safe persistent writes

Search and resolution tools locate records that the configured Frappe user may
read and do not persist data. Creation follows a shared two-phase boundary:

```text
resolve / validate
        |
        v
prepare
        |
        v
preview
        |
        v
explicit approval
        |
        v
confirm
        |
        v
ERPNext write
```

`prepare_customer`, `prepare_item`, `prepare_sales_order`, and
`prepare_quotation` validate the requested data, apply ERPNext defaults and
document behavior where their services implement them, and return a structured
preview plus an approval token. They do not perform the final persistent
write. Their matching `confirm_*` tools require `confirm=true` and write only
the server-side prepared payload through normal Frappe document APIs.

For Customer and Item, the prepare services build an unsaved Frappe document
and inspect the installed site's runtime DocField metadata. Explicit input,
intentional MCP policy, and ERPNext/Frappe defaults are resolved before the
server asks for a still-missing mandatory capability field. Missing responses
retain the compatible `missing` paths and add structured field metadata.

Supplied exposed master values are then resolved from their live DocField type:
Links use permission-aware candidates for the DocField's target DocType,
Selects use runtime options, and Check/scalar values are normalized or rejected
deterministically. This remains capability-scoped; the server does not expose
arbitrary DocType resolution.

Approval state is local to the MCP process, expires after 15 minutes, and is
bound to the capability action, Frappe site, authenticated Frappe user, and a
digest of the prepared payload. This design is for one local process; a remote
or multi-worker deployment needs persistent approval storage and per-user
authentication before it is enabled.

## Runtime and permission boundary

The default transport is local `stdio` with `MCP_BACKEND=direct` and a
configured `MCP_FRAPPE_SITE`. The default `MCP_IDENTITY_MODE=service` preserves
the existing `MCP_FRAPPE_USER` service-user flow. `MCP_IDENTITY_MODE=librechat`
resolves the authoritative `MCP_LIBRECHAT_USER_ID` through an enabled
**LibreChat User Mapping** to an existing enabled Frappe User. It never
authorizes by email and never falls back to `MCP_FRAPPE_USER` in LibreChat mode.

LibreChat login is sufficient to start this local MCP flow; an ERP-enabled
LibreChat user still needs an administrator-created mapping, but does not need
to log in to Frappe Desk. Frappe roles, User Permissions, and DocType
permissions remain the authority after the runtime sets the resolved user. A
caller cannot pick the user through a tool argument. All record lookup and
persistence remains subject to normal Frappe permissions. Existing OAuth work
is unchanged.

For the controlled Docker-to-WSL bridge, set `MCP_TRANSPORT=streamable-http`
with `MCP_IDENTITY_MODE=librechat`. HTTP requires a minimum 32-character
`MCP_HTTP_SHARED_SECRET` in `Authorization: Bearer ...`; it rejects service
identity mode. Each authenticated request supplies its authoritative
`X-LibreChat-User-ID`, which is resolved through the same mapping DocType. The
optional email header is diagnostic only. HTTP never uses
`MCP_LIBRECHAT_USER_ID` or `MCP_FRAPPE_USER` as a fallback and clears the
Frappe request context after every tool call.

The REST backend settings remain a future boundary and are not implemented by
this server. Do not put credentials in this repository or expose them as tool
arguments.

Start the local server from the bench `sites` directory after configuring the
required environment:

```bash
export MCP_BACKEND=direct
export MCP_FRAPPE_SITE=your-site.localhost
export MCP_IDENTITY_MODE=service
export MCP_FRAPPE_USER=mcp-service@example.com
cd /home/frappe/frappe-bench/sites
../env/bin/python -m mcp_erpnext.mcp_server
```

For LibreChat mode, configure its YAML-defined STDIO server to pass
`MCP_IDENTITY_MODE=librechat` and its `MCP_LIBRECHAT_USER_ID` placeholder. The
optional `MCP_LIBRECHAT_USER_EMAIL` is reference-only and is never an
authorization key.

See [`docs/CODEX_MCP_SETUP.md`](docs/CODEX_MCP_SETUP.md) for the Codex stdio
registration and [`docs/LIBRECHAT_MCP_HTTP_SETUP.md`](docs/LIBRECHAT_MCP_HTTP_SETUP.md)
for the HTTP operator setup. The app must be installed on the selected site before its code
can be used; installation is an operator action and is not performed by this
server.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app mcp_erpnext
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/mcp_erpnext
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
