# MCP Quotation Inspector Verification

Date: 2026-08-26

## Scope and safety

This report records verification of the single local ERPNext MCP server's
Customer, Item, and Quotation capability path. It does not cover the custom
chatbot, LangGraph, OAuth, or custom application browser workflow.

No ERPNext records were created, changed, submitted, or deleted while preparing
this report. In particular, `confirm_customer`, `confirm_item`, and
`confirm_quotation` were not called.

## Environment result

| Check | Result | Evidence |
| --- | --- | --- |
| Python MCP dependency | PASS | The bench environment reports `mcp 1.29.0`. |
| Node runtime | PASS | Node `v24.13.0` is installed under Frappe's NVM directory, but is not on the default shell `PATH`. |
| MCP Inspector availability | PASS | The official Inspector `2.3.0` was downloaded and launched using that Node runtime. |
| Inspector web and sandbox listeners | PASS | The Inspector started on alternate local ports after `6274` was already in use. Its browser UI and MCP Apps sandbox listeners started without an Inspector traceback. |
| Inspector CLI STDIO handshake | FAIL | `tools/list` started the server, emitted only the `IncompleteFieldDefinitionWarning`, and timed out after 20 seconds without an MCP initialize response. |
| Independent MCP client handshake | FAIL | The installed `mcp 1.29.0` client reproduced the same 20-second initialization timeout. |
| Minimal FastMCP STDIO handshake | FAIL | An in-memory one-tool FastMCP server, using the same installed MCP package and Python runtime, produced the same warning and timed out after 10 seconds. |

The Inspector browser process is available, but its UI starting is not a
successful MCP connection. The independently reproduced initialization timeout
is the Phase 1 blocker. A local configuration or a passing unit test is not
treated as a successful STDIO handshake.

## Live runtime observations

The normal Inspector port `6274` was already occupied. Launching the official
Inspector on alternate local ports successfully started both the web UI and
its MCP Apps sandbox listener. This verifies the Inspector/browser side, not
the ERPNext MCP transport.

The equivalent non-interactive Inspector command attempted only this safe MCP
operation:

```text
tools/list
```

It started the configured STDIO command but did not receive an `initialize`
response within 20 seconds. The server emitted this warning to stderr before
the timeout:

```text
IncompleteFieldDefinitionWarning: Field 'lifespan' has an incomplete definition
```

An independent client from the installed `mcp 1.29.0` package used the same
server command and environment, then timed out at `session.initialize()` after
the same warning. No Customer, Item, Sales Order, or Quotation tool was invoked.

The same client was then used against an isolated one-tool FastMCP process
created entirely in memory. It also timed out during initialization after the
same warning. Therefore the first known divergence is below the
`mcp_erpnext` tool registration and ERPNext runtime layers: the installed
FastMCP/MCP dependency stack does not complete a STDIO initialize exchange in
this Python runtime. This is a supported diagnosis boundary, not a confirmed
version-compatibility root cause.

## Current source and static evidence

The current server entrypoint is `mcp_erpnext.mcp_server`; it creates FastMCP
and runs the `stdio` transport. `tools/__init__.py` registers the following
current controlled tool catalog, which is also asserted by the registration
unit test:

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

`prepare_quotation` accepts a resolved Customer reference, resolved Item
references with quantities, `valid_till`, and optional company/commercial
fields. Source inspection confirms that prepare builds and validates an
unsaved Quotation preview and issues an approval token; only
`confirm_quotation(..., confirm=True)` inserts a Draft. This is static source
evidence, not live ERPNext verification.

The following non-network suite passed:

```text
/home/frappe/frappe-bench/env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'

Ran 60 tests — OK
```

## Verification matrix

| Test | Result | Notes |
| --- | --- | --- |
| MCP Inspector web/sandbox startup | PASS | Official Inspector `2.3.0` launched locally on alternate ports. |
| MCP STDIO handshake | FAIL | Both the Inspector CLI and the installed MCP client timed out after 20 seconds waiting for initialize. |
| Minimal FastMCP STDIO handshake | FAIL | The same failure occurs without `mcp_erpnext` or Frappe code, so tool logic is not yet the first failing point. |
| Tool catalog through Inspector | NOT RUN | `tools/list` cannot proceed before initialize; static registration test passes. |
| Customer resolution | NOT RUN | No live MCP tool call. |
| Item resolution | NOT RUN | No live MCP tool call. |
| Metadata-driven Customer/Item missing fields | NOT RUN | Unit-tested only. |
| Select, Link, scalar, and Check resolution | NOT RUN | Unit-tested only. |
| Customer prepare performs no write | NOT RUN | Unit-tested only; no live prepare call. |
| Item prepare performs no write | NOT RUN | Unit-tested only; no live prepare call. |
| Quotation prepare returns preview without insert | NOT RUN | Source/unit evidence only; no live prepare call. |
| Quotation confirmation | NOT RUN | Requires Inspector and separate explicit test-write permission. |
| Quotation idempotency | NOT RUN | Requires a confirmed live test write. |
| Runtime permission behavior | NOT RUN | Requires a controlled authenticated Inspector session and suitable data. |

## Required continuation

1. Resolve the installed FastMCP/MCP runtime's STDIO initialization failure
   before changing `mcp_erpnext` code. The warning comes from the
   FastMCP/Pydantic dependency path, and the minimal FastMCP reproduction
   establishes that this is below application tool logic; no causal exception
   was emitted, so the exact dependency/version defect remains unconfirmed.
2. Repeat Inspector `tools/list` only after the handshake succeeds.
3. Complete resolution, metadata, field-resolution, and prepare-only checks
   before considering any write.
4. Obtain separate explicit approval for a safe development-site Draft
   Quotation before calling `confirm_quotation`.

Until those steps are completed, this report does not establish live MCP,
Frappe, permission, Quotation-preview, or persistent-write behavior.
