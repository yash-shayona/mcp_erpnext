# Creation Default Ownership and Naming Series Alignment Implementation Report

## Result

Task 68 is implemented on the current `mcp_erpnext` worktree. Standalone Sales
Order preparation no longer replaces the active site's native
`frappe.new_doc("Sales Order")` naming-series value with
`SAL-ORD-.YYYY.-`. The native value is retained in the pending approval
payload and reconstructed unchanged for the normal permission-enforcing insert.

The bounded sweep found no second same-class production inconsistency. Existing
automatic values in sibling creation paths are explicit user inputs, frozen MCP
capability policy, workflow-derived values, or native mapper/factory output.
They were preserved.

No public naming-series input was added. No business record, historical Sales
Order, naming-series setting, database row, or live site was changed.

## Confirmed baseline

- Branch: `master`
- Baseline commit: `709fa6a73ace0d6d8603ab11d1ab42cba11cc577`
- Pre-task app version: `0.2.0`
- Post-task app version: `0.2.1`
- Local Frappe source: `v16.34.0`
- Local ERPNext source: `v16.35.0`
- Python: `3.14.3`
- Preserved pre-existing worktree item: untracked
  `docs/tasks/implementation/26-09-2026/`, including Task 68.

The pre-fix source at
`mcp_erpnext/services/selling/sales_order.py:217-218` initialized the native
document and immediately overwrote its naming series:

```python
doc = frappe.new_doc("Sales Order")
doc.naming_series = "SAL-ORD-.YYYY.-"
```

`SalesOrderPrepareInput`, the MCP wrapper, and the REST bridge did not accept
`naming_series`. Therefore the incorrect series came from server-side MCP
service code, not from the LLM or user.

## Implementation

The production fix is intentionally one line:

```diff
 doc = frappe.new_doc("Sales Order")
-doc.naming_series = "SAL-ORD-.YYYY.-"
 doc.customer = customer_resolution["candidate"]["value"]
```

The existing flow remains:

```text
frappe.new_doc("Sales Order")
  -> preserve runtime defaults, including naming_series
  -> apply explicit input and bounded capability policy
  -> native missing-value, totals, and validation methods
  -> store reviewed document payload in shared approval state
  -> frappe.get_doc(approved payload)
  -> normal insert(ignore_permissions=False, ...)
```

The focused regression fixture initializes a deliberately site-specific
`ST-SORD-2627-.####` series. Tests prove that preparation stores it in the
approval payload, confirmation reconstructs it, and the public contract/tool
signature still excludes `naming_series`.

## Creation-path ownership inventory

The inventory was traced from `contracts/registry.py`, profile registration,
tool wrappers, `remote_operations.py`, and the reached services. Read,
update, submit, cancel, delete, reconciliation, Contact promotion/update, and
email-send capabilities were excluded because they do not create a target
business document in this task's sense.

| Capability | Target / mechanism | Automatically set values inspected | Classification and evidence | Decision |
|---|---|---|---|---|
| Customer creation | Customer; runtime metadata contract, then normal native insert | Allowed Customer fields; optional mapped Contact/Address values | `USER_INPUT` plus `NATIVE_DEFAULT_OR_MAPPER`. `resolve_creation_contract()` calls `frappe.new_doc("Customer")`; Customer `POLICY_VALUES` is empty. | Keep |
| Item creation | Item; runtime metadata contract, then normal native insert | Allowed Item fields; `is_sales_item=1` | Runtime fields are `USER_INPUT` / `NATIVE_DEFAULT_OR_MAPPER`; `is_sales_item` is documented `MCP_CAPABILITY_POLICY` for the sales-item capability. | Keep |
| Standalone Contact creation | Contact payload and normal native insert | Identity/communication fields; child-row primary flags; no Dynamic Link | Fields are `USER_INPUT`; primary email/mobile/phone flags and the no-link boundary are `MCP_CAPABILITY_POLICY`. Native Contact validation/persistence owns projections and naming. | Keep |
| Customer-linked Contact create | Contact payload, native validate/insert | Explicit identity/communication fields; Customer Dynamic Link; `make_primary=False` | Input is `USER_INPUT`; link is `WORKFLOW_DERIVED` from the selected Customer; non-primary behavior is the frozen capability boundary. | Keep |
| Quotation creation | `frappe.new_doc("Quotation")` | Customer party, company, dates, items; `quotation_to="Customer"`; `order_type="Sales"`; optional price list/taxes/discount/Terms | Explicit fields are `USER_INPUT`; Customer/Sales values are `MCP_CAPABILITY_POLICY`; omitted `valid_till` is the documented server-only `MCP_QUOTATION_VALIDITY_DAYS` policy; commercial values and Terms rendering use native defaults/methods. No naming override exists. | Keep |
| Standalone Sales Order creation | `frappe.new_doc("Sales Order")` | Customer, company, transaction/delivery dates, items, optional price list/Terms/remarks; `order_type="Sales"`; formerly naming series | Inputs are `USER_INPUT`; Sales order type and same-day omitted delivery date are bounded `MCP_CAPABILITY_POLICY`; commercial values are `NATIVE_DEFAULT_OR_MAPPER`. The naming literal was a `SUSPICIOUS_OVERRIDE` of `frappe.new_doc` state. | Remove naming override |
| Purchase Order creation | `frappe.new_doc("Purchase Order")` | Supplier, company, transaction/schedule dates, items, optional buying price list/taxes | Explicit values are `USER_INPUT`; omitted schedule date follows the capability's effective transaction date (`MCP_CAPABILITY_POLICY`); commercial defaults remain `NATIVE_DEFAULT_OR_MAPPER`. No naming override exists. | Keep |
| Standalone Sales Invoice creation | `frappe.new_doc("Sales Invoice")` | Customer/company/items; `is_pos=0`, `is_return=0`, `is_debit_note=0`, `update_stock=0`; optional posting date/links/Terms/remarks | Inputs are `USER_INPUT`. The four mode flags are accepted Task 29 `MCP_CAPABILITY_POLICY` defining an ordinary non-POS, non-return, no-stock-update Draft. Native missing values, totals, prerequisite check, and insert remain authoritative. No naming override exists. | Keep |
| Standalone Customer Payment Entry | `frappe.new_doc("Payment Entry")` plus native setup/default/validate methods | `payment_type="Receive"`, `party_type="Customer"`, selected party/company/destination, amounts/date/reference/remarks; no allocation rows | Receive/Customer and unallocated-only shape are `MCP_CAPABILITY_POLICY`; identities and amounts are `USER_INPUT` / resolved input; accounts/currencies/differences are `NATIVE_DEFAULT_OR_MAPPER`. | Keep |
| Sales Invoice payment | ERPNext `get_payment_entry("Sales Invoice", ...)` | Native party/accounts/reference/allocation; explicit mode/bank/reference/remarks overrides | Factory state is `NATIVE_DEFAULT_OR_MAPPER`; source link is `WORKFLOW_DERIVED`; optional overrides are `USER_INPUT`. MCP does not replace naming or accounting defaults. | Keep |
| Sales Order advance payment | ERPNext `get_payment_entry("Sales Order", ...)` | Native Customer Receive advance/reference; explicit destination/reference/remarks | Factory state is `NATIVE_DEFAULT_OR_MAPPER`; Sales Order reference and Receive intent are `WORKFLOW_DERIVED` / bounded policy; optional values are `USER_INPUT`. | Keep |
| Multi-invoice Customer receipt | `frappe.new_doc("Payment Entry")` plus native Payment Entry methods | Customer Receive fields; exact Sales Invoice reference rows and allocations; destination/reference/remarks | Receive/multi-allocation boundary is `MCP_CAPABILITY_POLICY`; invoice rows are `WORKFLOW_DERIVED` from freshly loaded invoices plus explicit allocations; accounts/currency calculations are native. | Keep |
| Quotation to Sales Order | ERPNext public `make_sales_order` | Entire mapped target | `NATIVE_DEFAULT_OR_MAPPER`; source/customer eligibility is checked, and no target naming/default is overwritten after mapping. | Keep |
| Sales Order to Sales Invoice | ERPNext public `make_sales_invoice` | Entire mapped target | `NATIVE_DEFAULT_OR_MAPPER`; source rows/links are `WORKFLOW_DERIVED`. No naming/default override follows mapping. | Keep |
| Sales Order to Delivery Note | ERPNext public `make_delivery_note` | Entire mapped target | `NATIVE_DEFAULT_OR_MAPPER`; source links are `WORKFLOW_DERIVED`. No naming/default override follows mapping. | Keep |
| Delivery Note to Sales Invoice | ERPNext public `make_sales_invoice` | Entire mapped target | `NATIVE_DEFAULT_OR_MAPPER`; source links are `WORKFLOW_DERIVED`. No naming/default override follows mapping. | Keep |
| Sales Invoice to Delivery Note | ERPNext public `make_delivery_note` | Entire mapped target | `NATIVE_DEFAULT_OR_MAPPER`; eligibility checks read source `is_return` / `update_stock`, but MCP does not rewrite target naming/defaults. | Keep |

No additional `SUSPICIOUS_OVERRIDE` was confirmed, so no sibling production
service was changed.

## Files changed

Modified:

- `mcp_erpnext/services/selling/sales_order.py`
- `mcp_erpnext/__init__.py`

Added:

- `mcp_erpnext/tests/test_sales_order_service.py`
- `docs/inspect/26-09-2026/CREATION_DEFAULT_OWNERSHIP_AND_NAMING_SERIES_ALIGNMENT_IMPLEMENTATION_REPORT.md`

`docs/COMMANDS.md` was not changed because Task 68 adds or changes no reusable
project operation. `docs/TOOLS.md` was not changed because the public tool
surface and schemas remain unchanged.

## Verification actually run

### New focused regression

```bash
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python -m unittest \
  mcp_erpnext.tests.test_sales_order_service
```

Result: `Ran 3 tests in 0.004s` — `OK`.

Coverage:

- the native fixture series survives into the shared pending payload;
- confirmation reconstructs that reviewed series and uses normal insert flags;
- `naming_series` is absent from `SalesOrderPrepareInput` and the MCP wrapper
  signature.

### Required sibling regression suites

The first combined 98-test run produced 97 passes and one existing
`test_purchase_order_service` error. That test expects the first confirmation
to return `TRUSTED_APPROVAL_UNAVAILABLE`, while the process default in
`settings.py` and `ApprovalStore()` is `agent_delegated`; therefore
confirmation succeeds and the test attempts to read a missing `code`. The
same error reproduces when that module is run alone. No Task 68 code is on that
failure path.

The unaffected required suites were then run normally:

```bash
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python -m unittest \
  mcp_erpnext.tests.test_create_contracts \
  mcp_erpnext.tests.test_quotation_service \
  mcp_erpnext.tests.test_sales_order_service \
  mcp_erpnext.tests.test_sales_invoice \
  mcp_erpnext.tests.test_creation_contract \
  mcp_erpnext.tests.test_tool_contracts \
  mcp_erpnext.tests.test_rest_backend \
  mcp_erpnext.tests.test_profiles
```

Result: `Ran 96 tests in 8.099s` — `OK`.

The Purchase Order module was run after explicitly configuring the policy its
assertion expects:

```python
import mcp_erpnext.tests.test_purchase_order_service as module
from mcp_erpnext.approvals import approvals
from mcp_erpnext.settings import ApprovalMode

approvals.configure_approval_mode(ApprovalMode.TRUSTED_HUMAN)
# unittest loader then ran the module
```

Result: `Ran 2 tests in 0.002s` — `OK`.

The test processes emitted the existing Pydantic
`IncompleteFieldDefinitionWarning` for `lifespan`; it did not fail tests.

### Static and catalog checks

```bash
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py --check
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python -m compileall -q mcp_erpnext
git diff --check
```

Results: all exited successfully with no catalog diff, compile error, or
whitespace error. The catalog check emitted the same non-failing Pydantic
warning.

### Final source scans

```bash
rg -n --glob '!docs/**' 'naming_series|SAL-ORD-\.YYYY\.-' mcp_erpnext
rg -n 'naming_series|SAL-ORD-\.YYYY\.-' \
  mcp_erpnext/services mcp_erpnext/contracts mcp_erpnext/tools \
  mcp_erpnext/remote_operations.py
```

Results:

- no match in executable services, contracts, tools, or REST bridge;
- all remaining app-package matches are in
  `tests/test_sales_order_service.py`: the native-series fixture, preservation
  assertions, and the negative assertion against the old literal.

## Acceptance and safety evidence

- The executable `SAL-ORD-.YYYY.-` assignment is removed.
- Native `frappe.new_doc` naming state is preserved in approval and confirm.
- The public Sales Order prepare contract and tool do not expose
  `naming_series`.
- Approval creation/claim behavior and payload reconstruction are unchanged.
- Confirmation still uses `insert(ignore_permissions=False,
  ignore_links=False, ignore_mandatory=False)`.
- Conversion services still use installed ERPNext public mappers.
- Deliberate capability constants were retained with ownership reasons above.
- App version received only the required PATCH bump: `0.2.0 -> 0.2.1`.
- No migration, direct SQL, permission bypass, deployment, commit, tag, push,
  historical rename, or live transaction creation was performed.

## Risks, limitations, and deviations

- No live mutation was run on `yob.localhost` or another site. The result is
  established by deterministic service tests and current source inspection,
  not by creating a real Sales Order.
- Existing Sales Orders named with the old series are intentionally unchanged.
- Site defaults may change after preparation; existing approval semantics
  freeze the reviewed payload, and Task 68 does not redesign that behavior.
- The required Purchase Order test has a pre-existing implicit approval-mode
  assumption. It passes when that expected mode is configured explicitly, but
  its source was not changed because it is unrelated to default ownership.
- The mandatory `apply_patch` helper could not start because the environment's
  sandbox rejected the WSL `/mnt/wslg/distro` mount. The same exact scoped
  unified diffs were therefore applied with `git apply --recount`; no broader
  write mechanism or unrelated edit was used.

## Resulting project state

Task 68's required code, regression test, version bump, and implementation
report are complete. No further default-ownership correction was identified in
the bounded creation-path sweep. Review this report together with the current
worktree diff and the original Task 68 document.
