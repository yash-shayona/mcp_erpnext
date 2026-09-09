# ERPNext MCP Architecture

This is the primary current architecture reference for `mcp_erpnext`.

`mcp_erpnext` is **one ERPNext MCP server** with multiple controlled domain
capabilities. It does not provide separate Customer, Item, Quotation, or Sales
Order MCP servers, and it does not expose unrestricted ERPNext administration,
SQL, or arbitrary DocType CRUD.

```text
ERPNext MCP Server
|
|-- Master Capabilities
|   |-- Customer
|   `-- Item
|
`-- Selling Capabilities
    |-- Quotation
    `-- Sales Order
```

## Request path

```text
MCP Client / Agent
        |
        v
MCP transport (STDIO by default, Streamable HTTP when explicitly configured)
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

The FastMCP server in `mcp_server.py` defaults to STDIO and can serve the same
registry over Streamable HTTP. It calls the central registration function in
`tools/__init__.py`; only tools registered there are part of the public MCP
surface, so HTTP does not add duplicate tool implementations.

## Source-verified tool catalog

The current registration order in `tools/__init__.py` and the static
registration test both define this catalog:

| Domain | Capability | Tools |
| --- | --- | --- |
| Masters | Customer | `search_customers`, `resolve_customer`, `prepare_customer`, `confirm_customer` |
| Masters | Item | `search_items`, `resolve_item`, `prepare_item`, `confirm_item` |
| Selling | Sales Order | `prepare_sales_order`, `confirm_sales_order` |
| Selling | Quotation | `prepare_quotation`, `confirm_quotation` |

There are no generic search, SQL, arbitrary document-read, or arbitrary
document-write MCP tools in this catalog.

## Tool categories

### Search and resolution

`search_customers`, `resolve_customer`, `search_items`, and `resolve_item`
locate permitted active records. The shared resolution code uses
permission-aware `frappe.get_list` queries and returns structured result,
candidate, selection, or creation-needed states. Search and resolution tools
do not create persistent records.

Customer and Item master capabilities are reusable. A Selling workflow may
use a resolved Customer or Item reference, but the master capability is not
owned by Quotation or Sales Order.

### Prepare

`prepare_customer`, `prepare_item`, `prepare_sales_order`, and
`prepare_quotation` form the non-persistent half of the write workflow. They
validate their narrow inputs, check applicable permission or record access,
and prepare a structured preview. Transaction services also invoke the
ERPNext defaulting, calculation, and validation behavior implemented in their
respective services before issuing an approval token.

Preparing does not insert the final Customer, Item, Draft Sales Order, or Draft
Quotation.

For Customer and Item, `services/common/creation_contract.py` resolves the
master creation contract from an unsaved `frappe.new_doc()` and the installed
runtime metadata. Its precedence is explicit input, intentional MCP policy,
then ERPNext/Frappe defaults. Only an exposed field that runtime metadata still
marks mandatory and leaves unresolved is returned in `needs_input`. The
existing `missing` path list is retained alongside structured field metadata;
this keeps site-specific metadata changes traceable without hard-coding a
second mandatory-field list in a service.

`services/common/field_value_resolver.py` validates every populated exposed
master field after the creation contract. It dispatches by the runtime
DocField's type: Link targets and Select options come from metadata, while
Check and supported scalar values are normalized deterministically. Link
candidates use normal Frappe permissions and unresolved multiple candidates
return `needs_selection`; no generic arbitrary-DocType resolver is exposed.

### Confirm

`confirm_customer`, `confirm_item`, `confirm_sales_order`, and
`confirm_quotation` require the approval token returned by their corresponding
prepare operation and an explicit `confirm=true`. They persist only the
trusted, server-side prepared state through Frappe document APIs with normal
permission enforcement. The current write capabilities are therefore:

- Customer creation
- Item creation
- Draft Sales Order creation
- Draft Quotation creation

## Conversational interaction contract

The MCP server returns client-neutral semantic interaction guidance when an
existing typed workflow needs a user continuation. It does not interpret chat
language or own conversation state. `SELECTION` covers ambiguous candidates,
`INPUT` covers structured missing business fields, and `APPROVAL` covers a
prepared preview that must be reviewed. The Agent interprets the user's message
or UI action and calls the existing structured selection, prepare, or confirm
tool as appropriate.

An `APPROVE` action is only semantic intent. The existing approval token and
trusted server-side approval guard remain mandatory before a `CONFIRM_WRITE`
tool can persist data. See
[MCP Conversational Interaction Contract](architecture/MCP_CONVERSATIONAL_INTERACTION_CONTRACT.md).

## Shared approval boundary

Every persistent creation path follows this boundary:

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

`approvals.py` keeps the pending approval server-side in the local MCP
process. A token expires after 15 minutes. Lookup verifies the intended action,
site, and authenticated Frappe user, and checks a keyed digest of the prepared
payload before a confirm service can use it. Confirmation can return the
already-created document for the same still-available approval rather than
create a second document.

This is a controlled local-process safety boundary, not a remote or
multi-worker approval system. A future remote or multi-worker design must use
appropriate persistent approval storage and per-user authentication.

## Code organization

```text
mcp_erpnext/
|-- mcp_server.py
|   MCP server entrypoint and stdio transport startup
|
|-- tools/
|   MCP-facing tool contracts and wrappers
|   |-- masters/
|   |   |-- customer.py
|   |   `-- item.py
|   `-- selling/
|       |-- quotation.py
|       `-- sales_order.py
|
|-- services/
|   ERPNext capability implementation
|   |-- common/
|   |   Reusable permission-aware entity resolution
|   |-- masters/
|   |   Reusable Customer and Item capabilities
|   `-- selling/
|       Quotation and Sales Order capabilities
|
|-- approvals.py
|   Controlled persistent-write approval state
|
`-- runtime.py
    Frappe site and resolved-user runtime context
```

The tool wrappers call `runtime.ensure_context()` before invoking services.
`runtime.py` supports only `MCP_BACKEND=direct` and initializes the configured
Frappe site. Stdio uses `MCP_FRAPPE_USER` for local development/testing. HTTP
uses `mcp_identity` to resolve the authenticated request's generic email to an
enabled Frappe User, with no `MCP_FRAPPE_USER` fallback. A tool caller cannot
supply another user. The resolved identity remains subject to normal Frappe
permission checks for reads and writes.

## Security and runtime limits

- `MCP_TRANSPORT=stdio` is the default. `MCP_TRANSPORT=streamable-http` is a
  controlled Docker-to-WSL bridge, not a public endpoint.
- HTTP requires an explicit non-wildcard allowed Host list, a minimum
  32-character shared Bearer secret, and `X-MCP-User-Email`. The SDK's
  transport security validates the Host header before MCP processing.
- HTTP reads the generic email afresh from the authenticated request context.
  It never falls back to `MCP_FRAPPE_USER` or a tool argument.
- Each HTTP tool call initializes and destroys a separate Frappe context. Run
  exactly one MCP process/worker because approval storage remains process-local.
- `MCP_BACKEND=direct` is required; the REST backend is not implemented.
- `MCP_FRAPPE_SITE` configures the Frappe context. The resolved Frappe User's
  roles and User Permissions remain authoritative.
- Persistent writes are protected by the prepare/preview/explicit-confirm
  boundary.
- Services use Frappe ORM and document APIs with normal permission checks;
  they do not provide an arbitrary SQL MCP tool.
- Approval state is process-local, short-lived, and unsuitable by itself for
  remote or multi-worker deployment.

The original Sales Order-only V1 scope is historical documentation. See
[`MCP_SALES_ORDER_V1_FROZEN.md`](MCP_SALES_ORDER_V1_FROZEN.md) for that frozen
baseline, not for the current complete tool catalog.
