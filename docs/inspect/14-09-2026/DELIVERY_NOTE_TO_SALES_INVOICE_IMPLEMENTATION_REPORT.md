# Delivery Note to Sales Invoice Native Conversion Report

Task 43 adds the Sales-profile pair
`prepare_delivery_note_to_sales_invoice` and
`confirm_delivery_note_to_sales_invoice`.

## Implementation

The service calls the installed ERPNext
`erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice` mapper
with the exact source name, `target_doc=None`, and server-owned `args={}`.
It does not reproduce pending quantities, returned quantities, rates, taxes,
lineage, stock flags, or optional India Compliance mapping.

Preparation requires a readable Submitted Delivery Note and Sales Invoice
create permission. It returns a bounded native Draft preview and stores its
fingerprint in the shared site/user/action-bound ApprovalStore. Confirmation
atomically claims the approval, reloads and remaps the source, rejects a stale
fingerprint, and inserts one normal-permission Draft Sales Invoice. It never
submits the invoice or changes the Delivery Note.

## Changed files

Added:

- `mcp_erpnext/contracts/selling/delivery_note_to_sales_invoice.py`
- `mcp_erpnext/services/selling/delivery_note_to_sales_invoice.py`
- `mcp_erpnext/tools/selling/delivery_note_to_sales_invoice.py`
- `mcp_erpnext/tests/test_delivery_note_to_sales_invoice.py`

Updated:

- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/contracts/selling/__init__.py`
- `mcp_erpnext/remote_operations.py`
- `mcp_erpnext/tools/__init__.py`
- `mcp_erpnext/tests/test_tool_contracts.py`
- `mcp_erpnext/tests/test_tool_registration.py`
- `mcp_erpnext/tests/test_profiles.py`
- `mcp_erpnext/tests/test_rest_backend.py`
- generated `docs/TOOLS.md`

## Verification

Passed focused unit tests for the new service, typed contracts, Sales
registration, and fixed REST handler: 34 tests. The full suite ran 296 tests;
it retains 1 failure and 4 errors in unrelated pre-existing dirty-worktree
approval/India Compliance tests. Compile and generated-catalog checks also
passed, and `git diff --check` passed.

The rate regression test verifies that MCP preserves the native mapper result
for multiple Delivery Note rows with different rates and lineage. It does not
claim that the installed ERPNext mapper produces correct rates in a live
database. Live authenticated MCP/REST execution, target-site permissions,
native quantity/return calculations, optional-app hooks, and a real Draft
insert remain unverified.
