# Task 68 - Creation Default Ownership and Naming Series Alignment

## Objective

Fix the confirmed standalone Sales Order naming-series bug and perform one bounded cross-capability consistency sweep of MCP document-creation paths so that ERPNext/Frappe remains the source of truth for naming series, runtime defaults, controller behavior, and other native document state unless a field is intentionally owned by an explicit MCP capability policy or by user input.

The immediate bug is that standalone Sales Order preparation currently overwrites the site's configured Sales Order naming series with `SAL-ORD-.YYYY.-`. After this task, MCP-created Sales Orders must preserve the naming series/default resolved by the active ERPNext/Frappe site, such as the observed site value `ST-SORD-2627-.####`, instead of forcing an MCP-specific series.

This task also requires the implementer to inspect sibling creation flows for the same class of architectural inconsistency. If no additional inconsistency is found, report that with evidence and stop. Do not manufacture extra refactors.

## Handoff Context

The current `mcp_erpnext` codebase already follows a thin-bridge/native-authority architecture:

```text
LLM / MCP client
  -> bounded typed MCP input
  -> MCP resolution / preview / approval policy
  -> Frappe / ERPNext native defaults, metadata, controller logic, permissions
  -> normal document insert / save / mapper behavior
```

Relevant previously frozen project principles include:

- inspect the installed/current implementation before changing behavior;
- prefer Frappe/ERPNext native behavior over copied or hard-coded ERP business truth;
- keep the LLM-facing contract narrow;
- do not add fields to public contracts merely because ERPNext has those fields;
- let normal Frappe permissions, metadata, validation, defaults, hooks, naming, and persistence remain authoritative;
- only retain MCP-owned values when they are deliberate capability policy, explicit user input, or workflow-derived state;
- avoid unrelated refactors.

Task 36's authority audit already established the thin-bridge target: MCP owns bounded contracts, orchestration, preview/approval, and response shaping; Frappe/ERPNext owns runtime metadata, defaults, validation, document lifecycle, and native business semantics.

The current app version in the supplied 26-Sep-2026 snapshot is:

```text
mcp_erpnext/__init__.py
__version__ = "0.2.0"
```

This task is a backward-compatible correctness fix/hardening task, not a new public capability. Under the project's semantic-versioning rule, successful completion should bump PATCH from `0.2.0` to `0.2.1`, unless the current worktree has already advanced beyond `0.2.0`; in that case bump the current PATCH version appropriately and record the actual before/after values.

## Scope

### In scope

1. Remove the confirmed standalone Sales Order naming-series override.
2. Preserve the naming series/runtime default produced by the active site/Frappe document initialization rather than inventing a series in MCP code.
3. Keep `naming_series` out of the current public Sales Order prepare input. This task does not make naming-series selection an LLM-controlled feature.
4. Inspect all currently exposed persisted document-creation capabilities and conversion creation paths for the same ownership problem:
   - hard-coded naming series;
   - hard-coded document defaults that silently replace a Frappe/ERPNext runtime default;
   - duplicated native defaults/settings that MCP does not need to own;
   - service-level constants that are actually deliberate MCP capability policy and therefore should remain;
   - workflow-derived values that should remain because they come from the source transaction or explicit workflow contract.
5. For every inspected field that MCP sets automatically, classify its ownership before changing it.
6. Fix any additional *confirmed* inconsistency of the same class when the correction is local, backward-compatible, and clearly supported by the existing architecture/native behavior.
7. Add regression tests that prove the Sales Order naming series is preserved and that the public contract still does not expose an arbitrary naming-series input.
8. Add focused tests for any additional inconsistency fixed by this task.
9. Record the cross-capability inspection inventory and evidence in the implementation report.
10. Apply the PATCH version bump after tests pass.

### Out of scope

- No new MCP tool.
- No new public `naming_series` input for Sales Order, Quotation, Sales Invoice, Purchase Order, or other creation tools.
- No environment variable, site setting, MCP setting, custom DocType, or custom config for naming-series selection.
- No automatic guessing of a naming series from company, fiscal year, transaction type, document type, or prior documents.
- No migration or rename of existing documents such as previously created `SAL-ORD-2026-...` records.
- No database rewrite of historical names.
- No redesign of the approval store or two-phase prepare/confirm contract.
- No broad refactor of all creation services merely to make them look identical.
- No removal of deliberate capability policy solely because it is a constant. Constants must first be classified against the frozen contract and native behavior.
- No change to conversion mapper behavior unless inspection proves MCP is overriding mapper/native output after the mapper returns.
- No change to customer/item/contact creation policy unrelated to native-default ownership.
- No new feature for user-selectable naming series. If that becomes a requirement later, it must be a separate explicit design decision.
- No deployment, production data mutation, commit, tag, push, or historical document rename as part of this implementation task unless separately authorized.

## Inputs / Source of Truth

The implementer must inspect the current worktree first. The supplied ZIP snapshot is evidence, but the current worktree at implementation time is authoritative.

### Confirmed relevant current files

```text
mcp_erpnext/services/selling/sales_order.py
mcp_erpnext/contracts/selling/sales_order.py
mcp_erpnext/tools/selling/sales_order.py
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/services/selling/sales_invoice.py
mcp_erpnext/services/buying/purchase_order.py
mcp_erpnext/services/common/creation_contract.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py
mcp_erpnext/profiles/accounts.py
mcp_erpnext/tests/test_create_contracts.py
mcp_erpnext/tests/test_quotation_service.py
mcp_erpnext/tests/test_sales_invoice.py
mcp_erpnext/tests/test_purchase_order_service.py
mcp_erpnext/__init__.py
```

Also inspect all current service/tool/contract files reached by public prepare/confirm creation operations in `contracts/registry.py`, profile registration, and `remote_operations.py`. Do not rely only on a grep for `frappe.new_doc`, because some creation flows are native mapper based or construct payloads/documents through other helpers.

### Existing architecture references

```text
docs/tasks/audits/36_TASK_FRAPPE_ERP_AUTHORITY_DUPLICATION_AUDIT.md
docs/inspect/12-09-2026/FRAPPE_ERP_AUTHORITY_DUPLICATION_AUDIT_REPORT.md
docs/tasks/implementation/11-09-2026/27_TASK_SALES_ORDER_TO_SALES_INVOICE_NATIVE_CONVERSION_FOUNDATION.md
```

Task 27 explicitly preserves native target naming and states that conversion code must not hard-code a naming series. Use that principle consistently for standalone creation too.

## Current State / Confirmed Evidence

The 26-Sep-2026 source snapshot was inspected before this task was written.

### 1. Confirmed Sales Order bug

Current standalone Sales Order preparation contains:

```python
doc = frappe.new_doc("Sales Order")
doc.naming_series = "SAL-ORD-.YYYY.-"
```

This is in:

```text
mcp_erpnext/services/selling/sales_order.py
```

The assignment overrides the value/default that the active ERPNext/Frappe site would otherwise provide.

### 2. This is not coming from the LLM contract

Current `SalesOrderPrepareInput` contains customer, items, company, delivery date, selling price list, Terms reference, and custom remarks. It does **not** expose `naming_series`.

The Sales Order MCP tool wrapper and REST bridge likewise do not accept/pass a naming-series parameter.

Therefore the observed `SAL-ORD-...` creation behavior is server-side MCP service behavior, not an LLM-selected naming series.

### 3. No second executable naming-series hardcode was found in the inspected snapshot

A source sweep of executable `mcp_erpnext` code found `naming_series` only in the standalone Sales Order assignment above. Quotation, Purchase Order, and standalone Sales Invoice initialize native documents without forcing a naming series.

This is evidence for the current snapshot only. The implementation agent must repeat the check against the actual current worktree.

### 4. Existing native-default pattern already exists in the codebase

`mcp_erpnext/services/common/creation_contract.py` intentionally creates an unsaved document through `frappe.new_doc` so installed site metadata and user/runtime defaults can be applied before MCP decides what input is still missing.

That establishes an existing project pattern: runtime Frappe defaults are data to preserve, not values for the MCP service to overwrite without an explicit policy reason.

### 5. Other constants exist but are not automatically bugs

The current snapshot also contains deliberate-looking fixed values such as:

```text
Quotation:
- quotation_to = "Customer"
- order_type = "Sales"

Sales Order:
- order_type = "Sales"

Standalone Sales Invoice:
- is_pos = 0
- is_return = 0
- is_debit_note = 0
- update_stock = 0
```

These may define the bounded capability itself rather than duplicate a site default. Do not remove them mechanically. The task requires each such field to be classified against its existing contract, task history, and native behavior first.

## Frozen Strategy / Contract

### 1. Native-default ownership rule

For a new document field, use this priority model:

```text
explicit user input allowed by the public contract
  -> use the validated user value

explicit MCP capability policy already frozen by design
  -> use the policy value

workflow-derived/native mapper value
  -> preserve the derived/native value

Frappe/ERPNext runtime default or controller-owned value
  -> preserve native value; MCP must not replace it arbitrarily

otherwise
  -> do not invent a value merely to make creation pass
```

### 2. Naming-series contract

For the current MCP version:

```text
MCP does not own naming_series.
LLM does not choose naming_series.
The active Frappe/ERPNext site owns naming_series/default naming behavior.
```

For standalone Sales Order creation, the prepare path must initialize the document natively and must not overwrite `doc.naming_series` with `SAL-ORD-.YYYY.-` or any other MCP literal.

If `frappe.new_doc("Sales Order")` resolves the site value to:

```text
ST-SORD-2627-.####
```

then the prepared/approved document must preserve that value through confirmation, subject to normal Frappe behavior.

Do not replace the hardcode with another way of computing the same value.

### 3. Public contract remains narrow

`naming_series` must remain absent from `SalesOrderPrepareInput` and from the public tool schema in this task.

Do not solve the bug by asking the model/user for a naming series.

### 4. Consistency sweep rule

For each currently exposed persisted creation capability, build an internal audit table with at least:

```text
capability/tool
created target DocType
creation mechanism
field/value automatically set by MCP
ownership classification
native/runtime source available?
keep/change decision
evidence
```

Ownership classification must be one of:

```text
USER_INPUT
MCP_CAPABILITY_POLICY
WORKFLOW_DERIVED
NATIVE_DEFAULT_OR_MAPPER
SUSPICIOUS_OVERRIDE
```

Only `SUSPICIOUS_OVERRIDE` findings with sufficient evidence may be changed in this task.

### 5. No false uniformity

Alignment means consistent ownership rules, not identical code.

For example:

- Quotation may legitimately force `quotation_to = "Customer"` because the exposed capability is specifically a Customer quotation.
- Standalone Sales Invoice may legitimately force non-POS/non-return behavior if that is the accepted capability boundary.
- A conversion should preserve the ERPNext mapper's target values rather than reconstructing them manually.

The implementation report must explain these decisions rather than removing valid policy constants just to reduce differences between files.

## Allowed Changes

The confirmed required source change is:

```text
mcp_erpnext/services/selling/sales_order.py
```

Expected test/version areas include:

```text
mcp_erpnext/tests/test_create_contracts.py
mcp_erpnext/__init__.py
```

A dedicated standalone Sales Order service regression test file may be created if the current worktree still has no appropriate focused service-test file, for example:

```text
mcp_erpnext/tests/test_sales_order_service.py
```

Additional service/test files may be changed only when the required cross-capability inspection identifies another confirmed ownership inconsistency and the report records the evidence.

Documentation may be updated only when an existing document incorrectly states MCP ownership of a native default or when the task's durable architecture rule needs to be recorded in an already appropriate architecture document. Do not create broad documentation churn.

The implementation report itself must be created at the exact path specified below.

## Forbidden / Preserve

Preserve all of the following unless current-worktree evidence proves one is already superseded:

- current tool names;
- Sales/Purchase/Accounts profile boundaries;
- typed input/output contracts except for tests proving unchanged shape;
- two-phase prepare/confirm approval flow;
- explicit user confirmation requirements;
- Frappe permission checks;
- normal `insert(ignore_permissions=False, ...)` behavior;
- native validation/hooks/controller lifecycle;
- Terms behavior from Tasks 66/67;
- existing Customer/Item runtime-metadata creation contract;
- conversion mappers and source links;
- data-minimization boundaries;
- REST/MCP parity.

Do not:

- use `ignore_permissions=True`;
- write directly to the database to solve naming;
- call `rename_doc` on historical transactions;
- add a fallback hard-coded naming series;
- derive naming series by inspecting existing record names;
- query "latest Sales Order name" and increment it manually;
- add naming-series values to MCP instructions so the LLM starts guessing them;
- weaken approval or validation behavior;
- change valid capability-policy fields without evidence.

## Implementation Steps

### Step 1 - Re-inspect the actual current worktree

Before editing, confirm:

1. current app version;
2. current standalone Sales Order prepare/confirm flow;
3. whether `doc.naming_series = "SAL-ORD-.YYYY.-"` is still present;
4. current `SalesOrderPrepareInput` schema;
5. current Sales Order MCP wrapper and REST bridge inputs;
6. current task/report conventions;
7. current test coverage for standalone Sales Order preparation.

Record this baseline in the implementation report.

### Step 2 - Build the bounded creation-path inventory

Use `contracts/registry.py`, profile registration, tool wrappers, and `remote_operations.py` to identify currently exposed persisted create/convert operations.

Trace each operation to its service/native mapper and inspect automatic document-field assignments. At minimum cover the currently present families where applicable:

```text
Customer creation
Item creation
Standalone Contact creation
Customer-linked Contact creation
Quotation creation
Sales Order creation
Purchase Order creation
Standalone Sales Invoice creation
Payment Entry creation flows
Quotation -> Sales Order
Sales Order -> Sales Invoice
Sales Order -> Delivery Note
Delivery Note -> Sales Invoice
Sales Invoice -> Delivery Note
```

If the current worktree exposes another persisted create capability, include it too.

Do not treat read/update/submit/cancel/delete tools as creation paths for this specific inventory.

### Step 3 - Classify automatic values

For every meaningful constant/default assigned by MCP before insert, classify it using the frozen ownership categories.

Examples to inspect, not predetermined outcomes:

```text
Sales Order naming_series
Sales Order order_type
Quotation quotation_to
Quotation order_type
Sales Invoice is_pos
Sales Invoice is_return
Sales Invoice is_debit_note
Sales Invoice update_stock
transaction/posting/schedule date defaults
company defaults
price-list/taxes defaults
payment-entry mode/reference fields
conversion target fields modified after native mapper calls
```

For each item, answer:

- Is the field explicit user input?
- Is it an intentional bounded capability policy?
- Is it source/workflow-derived?
- Does `frappe.new_doc`, runtime metadata, user defaults, Selling/Buying Settings, a controller method, or a native mapper already own it?
- Would the MCP assignment override a site's valid configuration?
- Is the current assignment documented by an accepted task/contract?

### Step 4 - Fix the confirmed Sales Order naming-series override

Remove the explicit MCP assignment of `SAL-ORD-.YYYY.-`.

Do not replace it with:

- the observed `ST-SORD-2627-.####` value;
- another literal;
- a regex/guess;
- a setting in MCP env/config;
- a model-facing input.

Preserve the native `frappe.new_doc("Sales Order")` initialized value and existing normal confirm/insert flow.

### Step 5 - Fix only other confirmed same-class mismatches

If the inventory finds another automatic assignment that clearly overrides native configuration/mapper output without a frozen MCP-policy reason:

1. document the evidence;
2. make the smallest local correction;
3. preserve the current public contract unless a contract correction is strictly necessary;
4. add a focused regression test.

If no other mismatch is found, make no additional production-code changes merely for stylistic consistency.

### Step 6 - Add Sales Order regression coverage

Add a focused service-level test that makes the native document start with a site-specific naming series distinct from the old literal, for example:

```text
ST-SORD-2627-.####
```

The test must prove that preparation does not replace it with:

```text
SAL-ORD-.YYYY.-
```

Where practical, assert the value that is stored in the pending approved document payload or otherwise carried to confirmation, not only a temporary local variable.

Also assert through the typed contract/tool schema that `naming_series` is not a public prepare input.

Do not make the test depend on one production site's exact series beyond using a deliberately different fixture value to prove preservation.

### Step 7 - Regression-test sibling creation flows

Run the focused creation tests for Quotation, Sales Order, Sales Invoice, Purchase Order, and the common creation contract, plus tests for every additional file changed by this task.

The goal is to prove that removing the Sales Order override does not disturb:

- native defaults;
- preview construction;
- approval payload handling;
- confirmation insert;
- typed contracts;
- REST/MCP parity;
- profile exposure.

### Step 8 - Versioning

Because the required work is a backward-compatible bug fix/hardening change with no new public capability, bump PATCH only after successful verification.

Expected from the inspected snapshot:

```text
0.2.0 -> 0.2.1
```

If the actual worktree version differs, apply PATCH to the actual current version and document why.

Do not create a release tag or push unless separately requested.

### Step 9 - Produce the implementation report

The report must contain both:

1. implementation evidence for the Sales Order fix; and
2. the complete creation-path ownership inventory showing what else was checked and why it was kept or changed.

This prevents the result from being "we fixed one line" without verifying sibling architectural consistency.

## Safety / Compatibility Requirements

- No live historical Sales Order rename.
- No destructive data migration.
- No direct SQL/direct database field writes.
- No permission bypass.
- No model-controlled naming-series selection.
- No source-of-truth duplication for native naming/default behavior.
- Approval preview/confirm semantics must remain stable.
- If native runtime metadata or current ERPNext source contradicts an assumption in this task, stop that specific change, record the evidence, and preserve native behavior rather than forcing this document's assumption.
- Any runtime/live test that creates a business transaction must be explicitly identified and should use a safe test site/test data. Do not mutate production merely to prove the fix.

## Acceptance Criteria

The task is complete only when all applicable criteria pass.

1. `mcp_erpnext/services/selling/sales_order.py` no longer hard-codes `SAL-ORD-.YYYY.-` or another Sales Order naming-series literal.
2. A Sales Order document initialized with a site-specific/native naming series retains that series through preparation/pending creation data instead of being replaced by MCP.
3. `naming_series` is not added to `SalesOrderPrepareInput` or the public MCP tool schema.
4. MCP instructions do not tell the LLM to guess or provide naming series.
5. Current Quotation, Sales Invoice, Purchase Order, and other inspected creation paths have been reviewed for the same native-default ownership problem.
6. The implementation report contains the creation-path ownership table and evidence for every inspected capability.
7. Any additional code change beyond Sales Order has a documented `SUSPICIOUS_OVERRIDE` finding and a focused regression test.
8. Deliberate capability-policy constants are preserved when supported by existing contracts/native scope; they are not removed for cosmetic uniformity.
9. Conversion flows continue using native ERPNext mapper output and do not gain naming-series overrides.
10. Existing prepare/confirm approval behavior remains intact.
11. Existing Frappe permission and normal insert behavior remains intact.
12. Focused tests pass.
13. Static/catalog checks applicable to the unchanged public tool surface pass.
14. No unrelated feature/refactor is introduced.
15. App version receives a PATCH bump only, based on the current actual version.
16. The implementation report is written to the exact required path below.

## Tests / Verification

Use current-worktree commands/paths where they differ, but the minimum verification should include the focused suites corresponding to:

```text
mcp_erpnext.tests.test_create_contracts
mcp_erpnext.tests.test_quotation_service
mcp_erpnext.tests.test_sales_invoice
mcp_erpnext.tests.test_purchase_order_service
mcp_erpnext.tests.test_creation_contract
mcp_erpnext.tests.test_tool_contracts
mcp_erpnext.tests.test_rest_backend
mcp_erpnext.tests.test_profiles
```

Also run the dedicated Sales Order service regression test file added/used by this task and tests for every additional creation service modified.

Use the project's established environment invocation, for example when running inside the Frappe bench app context:

```bash
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python -m unittest <focused test modules>
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python scripts/generate_tool_catalog.py --check
PYTHONPATH=. /home/frappe/frappe-bench/env/bin/python -m compileall -q mcp_erpnext
git diff --check
```

Because this task should not change public tool inventory/schema, `docs/TOOLS.md` should normally remain unchanged. If catalog generation changes it, inspect why before accepting the diff.

### Required source scans

Repeat these or equivalent scans against the final worktree and include the results in the report:

```bash
grep -RIn --exclude-dir='.git' 'naming_series' mcp_erpnext
grep -RIn --exclude-dir='.git' 'SAL-ORD-.YYYY.-' mcp_erpnext
```

The expected result is:

- no executable hard-coded `SAL-ORD-.YYYY.-` assignment;
- any remaining `naming_series` references are intentional/test/documentation references and are explained.

### Optional live verification

If a safe non-production ERPNext site is available, perform one read/create validation using that site's configured Sales Order naming series:

1. record the current Sales Order default naming series from runtime/UI metadata;
2. prepare and confirm a test Draft Sales Order through MCP;
3. verify the created name follows the site's configured series;
4. verify no naming-series parameter was sent by the client/LLM.

If no safe site is available, do not block code completion solely on live mutation. Report live verification as not run and rely on deterministic service regression tests plus runtime metadata inspection.

## Expected Results

After implementation:

```text
ERPNext/Frappe site naming configuration
        |
        v
frappe.new_doc("Sales Order")
        |
        | preserve native/runtime naming_series
        v
MCP fills only explicit/policy/workflow fields
        |
        v
preview + approval payload
        |
        v
normal frappe.get_doc(payload) / insert
        |
        v
created Sales Order follows site naming convention
```

For the user's current observed site configuration, a new MCP-created Sales Order should follow the configured `ST-SORD-2627-...` pattern rather than being forced into `SAL-ORD-2026-...`, assuming that is still the active site default at runtime.

Sibling creation capabilities should either:

- remain unchanged with an explicit ownership justification; or
- receive a small evidence-backed correction if the audit proves the same class of native-default override.

## Limitations / Risks

- Existing Sales Orders already created with `SAL-ORD-...` are not renamed by this task.
- Site naming settings can change after preparation; the existing approval design may intentionally freeze prepared document values. Do not redesign approval semantics here.
- Some constants are product/capability policy, not duplicated ERP defaults. Misclassifying them could widen or change business behavior, which is why the ownership inventory is mandatory before editing.
- `frappe.new_doc` runtime defaults can vary by site, user, Property Setter, installed app, and version. Tests should prove preservation without hard-coding production assumptions.
- Conversion naming is ultimately governed by the native mapped target and Frappe naming lifecycle; this task should not reimplement it.
- A full codebase-wide architecture refactor is explicitly not required. The sweep is bounded to currently exposed persisted create/convert capabilities and this specific ownership class.

## Implementation Report

Create the implementation report at exactly:

```text
docs/inspect/26-09-2026/CREATION_DEFAULT_OWNERSHIP_AND_NAMING_SERIES_ALIGNMENT_IMPLEMENTATION_REPORT.md
```

The report must include:

- baseline commit/branch if available;
- actual pre-task and post-task app version;
- exact files changed;
- the confirmed pre-fix Sales Order hardcode evidence;
- the final Sales Order behavior;
- the full creation-path ownership inventory table;
- every additional inconsistency found, or an explicit statement that none was found;
- for each retained constant, a short reason why it is deliberate MCP policy/workflow state rather than an accidental native-default override;
- tests/commands actually run and exact results;
- source-scan results for `naming_series` and the old literal;
- whether a safe runtime/live test was run;
- acceptance-criteria evidence;
- deviations from this task;
- unresolved limitations/blockers;
- resulting project state;
- confirmation that historical documents were not renamed;
- confirmation that no public naming-series input/tool was added.

Do not claim tests, runtime metadata inspection, or live mutation that was not actually performed.

## Handover Completeness Check

Before marking the task complete, verify that a reviewer who has not read prior chat can determine from the task, code diff, and implementation report:

- why the existing `SAL-ORD` behavior occurred;
- whether it came from the LLM or server code;
- who now owns naming-series selection;
- which other creation paths were inspected;
- why each automatic field was kept or changed;
- what tests prove the behavior;
- what version changed;
- whether any live data was touched;
- whether any further required work remains.

## Exact Next Handoff

After implementation, return:

```text
docs/inspect/26-09-2026/CREATION_DEFAULT_OWNERSHIP_AND_NAMING_SERIES_ALIGNMENT_IMPLEMENTATION_REPORT.md
```

for review together with the resulting code/worktree.

The reviewer must compare the report against this Task 68 and inspect the actual changed code before acceptance. If the report proves the naming-series fix and the bounded creation-ownership sweep is clean, this capability is complete. Do not create another follow-up task unless the evidence identifies a concrete unresolved required issue.
