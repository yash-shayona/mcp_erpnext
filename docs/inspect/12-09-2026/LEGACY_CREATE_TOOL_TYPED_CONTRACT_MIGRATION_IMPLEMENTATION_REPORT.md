# Legacy Create Tool Typed Contract Migration Report

## Scope

Task 34 migrated the existing public tools in place. Tool names, service calls,
ERPNext behavior, India Compliance behavior, approval storage, and permission
checks remain unchanged.

## Inspection baseline

- Checkout: `apps/mcp_erpnext`, branch `master`.
- Pre-existing working-tree changes were preserved in
  `mcp_erpnext/services/selling/quotation_read.py` and
  `mcp_erpnext/tools/selling/quotation_read.py`.
- The six frozen legacy names were exactly `prepare_customer`,
  `confirm_customer`, `prepare_item`, `confirm_item`,
  `prepare_sales_order`, and `confirm_sales_order`.
- The bench interpreter is `../../env/bin/python` from the app checkout. The
  installed SDK is `mcp 1.29.0`, whose `mcp.server.fastmcp.FastMCP` supplied the
  registration mechanism; no separate `fastmcp` distribution is installed.
  Pydantic is `2.12.5`.
- Customer and Item services use live Frappe metadata/defaults through
  `resolve_creation_contract`, field resolution through
  `resolve_contract_values`, and the existing permission, duplicate, and
  approval paths.
- Item HSN/SAC remains supplied to the unchanged service input and evaluated by
  `run_effective_requirements` and `india_compliance_item_preflight`.
- Customer GST behavior remains inside the unchanged
  `india_compliance_customer` bridge, including the transient address property.
- Sales Order continues to resolve and validate through the unchanged service;
  the wrapper converts typed Customer/Item references to the service's existing
  name-based payload shape.
- The existing Quotation, Sales Invoice, and Purchase Order wrappers provided
  the RootModel, TypeAdapter, shared-directive, and `structured_output=True`
  patterns.

## Implementation

Added explicit public contracts for Customer, Item, and Sales Order creation.
The models reject unknown fields, hide `Context`, use resolved references for
Sales Order inputs, reject boolean quantities, and preserve the narrow existing
capabilities. Item `is_sales_item` is represented as `Literal[True]` and is
removed from the downstream payload so the existing service policy remains the
authority. `gst_hsn_code` remains available for the existing conditional
runtime requirement.

Each wrapper is now a top-level typed function. It converts only public model
shapes, calls the existing service, adds shared `INPUT`, `SELECTION`, or
`APPROVAL` directives for the states that need them, and validates the service
result through an explicit discriminated output union.

The registry now declares all six contracts with explicit models. Confirm tools
retain `CONFIRM_WRITE` and `trusted_pending_operation`; prepare tools point to
their confirm counterparts. The frozen legacy inventory is empty. The generic
interaction audit also includes the Sales Order wrapper.

## Verification

Passed:

- Focused contract, interaction, registration, and wrapper tests: 27 tests.
- Full app suite: 264 tests, `OK`.
- `scripts/generate_tool_catalog.py` completed successfully.
- Generated `docs/TOOLS.md` reports all six as explicit typed contracts and no
  longer reports them as legacy migration inventory.
- FastMCP `list_tools()` inspection: all six publish object `inputSchema` and
  object `outputSchema`; `ctx` is absent; contract audit returns no issues.
- `compileall` passed for the changed contract and wrapper modules.

Live authenticated MCP execution and `structuredContent` validation against a
running external client were not performed in this implementation run. The
schemas were inspected from the local FastMCP registration instead.
