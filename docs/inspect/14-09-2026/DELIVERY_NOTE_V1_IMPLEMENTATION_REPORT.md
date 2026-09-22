# Delivery Note V1 Implementation Report

Task 42 is implemented for the Sales profile. The implementation adds the
native Submitted Sales Order to Draft Delivery Note flow and bounded existing
Delivery Note intelligence. It does not submit, invoice, allocate stock, or
create standalone Delivery Notes.

## Changed files

Added: `mcp_erpnext/contracts/selling/delivery_note.py`,
`mcp_erpnext/contracts/selling/delivery_note_read.py`,
`mcp_erpnext/services/selling/sales_order_to_delivery_note.py`,
`mcp_erpnext/services/selling/delivery_note_read.py`,
`mcp_erpnext/tools/selling/delivery_note.py`, and
`mcp_erpnext/tools/selling/delivery_note_read.py`.

Updated: `mcp_erpnext/contracts/registry.py`, `mcp_erpnext/contracts/read.py`,
`mcp_erpnext/contracts/pdf.py`, `mcp_erpnext/contracts/email.py`,
`mcp_erpnext/profiles/sales.py`, `mcp_erpnext/tools/__init__.py`,
`mcp_erpnext/services/common/read.py`,
`mcp_erpnext/services/common/lifecycle.py`,
`mcp_erpnext/services/common/email.py`, `mcp_erpnext/remote_operations.py`,
and generated `docs/TOOLS.md`.

## Public tools and contracts

The public tools are `prepare_sales_order_to_delivery_note` with only
`sales_order`, `confirm_sales_order_to_delivery_note` with only
`approval_token` and `confirm`, `get_delivery_note` with an allowlisted exact
name and projection, `query_delivery_notes` with typed filters/projection/
sorting/pagination, and `aggregate_delivery_notes` with allowlisted metrics
and grouping. All public models forbid extra fields.

## Native flow and approval

Preparation calls
`erpnext.selling.doctype.sales_order.sales_order.make_delivery_note` with the
exact source name, `target_doc=None`, and server-owned empty `kwargs`. It
returns a bounded preview and stores a SHA-256 fingerprint in the shared
site/user/action-bound `ApprovalStore`. Confirmation atomically claims the
one-shot approval, reloads the source, remaps natively, compares the fresh
fingerprint, and inserts with normal permissions. The target remains Draft;
no `submit()` or Sales Invoice operation is called.

## Permissions and policies

Source read and Delivery Note create permission are checked before mapping.
The mapper and insert use normal Frappe permission behavior; no MCP-owned
permission bypass or identity override was added. Delivery Note is allowed in
the Sales lifecycle policy only for submit, cancel, and delete. Generic PDF and
email use the existing exact-target, permission-aware services. Generic update
and child-row mutation remain unavailable.

## Read, query, aggregate, and REST

Delivery Note has a local header field policy and bounded projection. Query and
aggregate use `frappe.get_list(..., ignore_permissions=False)` and the shared
Frappe v16 dictionary aggregate builder. No SQL or raw filter expression is
accepted. Each new operation has a fixed typed entry in the REST remote
registry and calls the same authoritative service as direct execution.

## Verification

Passed:

- `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py`
- `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check`
- Python `compileall` for the app.
- Static registration assertions for all five tools, Sales-only read policy,
  fixed REST handlers, and lifecycle submit/cancel/delete-only behavior.
- `PYTHONPATH=apps/mcp_erpnext ./env/bin/python -m unittest -q` targeted
  registration/profile/REST tests: **15 passed**.

The full unittest suite ran 291 tests and currently has 1 failure and 4 errors
in pre-existing shared-approval/India Compliance tests from unrelated dirty
worktree changes. No dependency was installed. Authenticated MCP execution,
REST round trips, target-site metadata, permissions, native
stock/warehouse/serial/batch validation, and live create/read/lifecycle/PDF/
email scenarios are **not verified**.

## Runtime and optional-app notes

The implementation uses the configured runtime site and current Frappe user.
No site name is hard-coded. India Compliance remains runtime-controlled: its
hooks, if installed, are allowed to run normally, and no GST, e-Waybill,
transporter, or India Compliance logic was copied into MCP.

## Deliberate limitations

Standalone Delivery Note creation, Delivery Note to Sales Invoice conversion,
returns, child-row selection, quantity/rate/tax overrides, allocation,
Pick List/Packing Slip/Shipment/Delivery Trip, e-Waybill, and Accounts or
Purchase changes remain out of scope. Purchase remains unchanged and no
Accounts profile was introduced.
