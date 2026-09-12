# TASK 34 — Remaining Legacy Create Tools → Typed MCP Contract Migration

## Task Type

Architecture cleanup + public MCP contract migration.

This task intentionally reprioritizes the previously suggested Sales read-gap review. Task 33's historical recommendation remains valid, but the user has explicitly chosen to finish the remaining legacy contract migration first.

---

## 1. Scope

Migrate the final six legacy public MCP tools to the project's current typed MCP contract standard:

```text
prepare_customer
confirm_customer

prepare_item
confirm_item

prepare_sales_order
confirm_sales_order
```

The public tool names must remain unchanged.

This task is a **public-boundary migration**, not a rewrite of Customer, Item, Sales Order, India Compliance, approval, permission, or ERPNext business logic.

At completion, the current frozen legacy inventory should contain no remaining tools, assuming repository inspection confirms these are still the only six legacy entries.

---

## 2. Objective

After this task:

1. Customer create prepare/confirm has explicit typed input and output contracts.
2. Item create prepare/confirm has explicit typed input and output contracts.
3. Sales Order create prepare/confirm has explicit typed input and output contracts.
4. All six tools publish normal MCP `inputSchema` and `outputSchema` through the existing FastMCP/Pydantic mechanism.
5. All six are registered with `structured_output=True`.
6. `ctx` and all runtime identity/approval internals remain hidden from the public schema.
7. Successful prepare results expose the shared `APPROVAL` interaction directive.
8. Missing-input states expose the shared `INPUT` interaction directive where applicable.
9. Customer/Item creation states that require an explicit choice expose the shared `SELECTION` interaction directive where applicable.
10. Existing service functions and ERPNext/Frappe behavior remain authoritative.
11. Existing Customer GST/India Compliance behavior remains unchanged.
12. Existing Item HSN/SAC/India Compliance runtime requirement behavior remains unchanged.
13. Existing Sales Order ERPNext calculation/default/validation behavior remains unchanged.
14. Existing approval-token, permission, idempotency/replay, and confirm safety remain unchanged.
15. The six names are removed from the frozen legacy inventory.
16. The contract audit passes with **zero legacy exceptions** for the currently registered tool surface.
17. Generated `docs/TOOLS.md` reports all six as explicit typed contracts rather than legacy migration inventory.

---

## 3. Confirmed Current Repository State

Before implementation, verify this against the actual working tree. The supplied 2026-09-12 project snapshot currently shows:

### Frozen legacy inventory

`mcp_erpnext/contracts/registry.py` currently contains exactly:

```text
prepare_customer
confirm_customer
prepare_item
confirm_item
prepare_sales_order
confirm_sales_order
```

in `FROZEN_LEGACY_TOOL_NAMES`.

### Current legacy wrappers

- `mcp_erpnext/tools/masters/customer.py`
  - `prepare_customer(customer: dict[str, Any], ...) -> dict[str, Any]`
  - `confirm_customer(approval_token: str, confirm: bool, ...) -> dict[str, Any]`

- `mcp_erpnext/tools/masters/item.py`
  - `prepare_item(item: dict[str, Any], ...) -> dict[str, Any]`
  - `confirm_item(approval_token: str, confirm: bool, ...) -> dict[str, Any]`

- `mcp_erpnext/tools/selling/sales_order.py`
  - untyped item-row dictionaries
  - string Customer input
  - untyped dict outputs

### Existing typed reference implementations to reuse as patterns

Inspect and follow the current working implementations rather than inventing a new style:

```text
mcp_erpnext/contracts/selling/quotation.py
mcp_erpnext/tools/selling/quotation.py

mcp_erpnext/contracts/selling/sales_invoice.py
mcp_erpnext/tools/selling/sales_invoice.py

mcp_erpnext/contracts/buying/purchase_order.py
mcp_erpnext/tools/buying/purchase_order.py

mcp_erpnext/contracts/common.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/audit.py
```

### Contract policy already frozen

`docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md` already defines:

```text
typed public boundary
explicit input/output models
no arbitrary dict/Any at public boundary
thin wrapper -> existing service -> ERPNext/Frappe
shared interaction directives
shared approval guard
frozen legacy inventory that may only shrink
```

Do not redesign that architecture in this task.

---

## 4. Mandatory First Step — Inspect Before Editing

Before changing code, inspect the actual current repository and report:

1. current git/working-tree status;
2. exact six legacy names in `FROZEN_LEGACY_TOOL_NAMES`;
3. current FastMCP/MCP SDK and Pydantic versions available in the bench environment;
4. current Customer service input/output states;
5. current Item service input/output states;
6. current Sales Order service input/output states;
7. current Customer config creation fields;
8. current Item config creation fields;
9. Item effective runtime requirement / HSN-SAC path;
10. Customer India Compliance/GST bridge path;
11. current approval behavior and guard classification;
12. current typed Quotation/Sales Invoice/Purchase Order wrapper pattern;
13. current contract audit rules;
14. current generated tool catalog behavior;
15. current focused/full test baseline if runnable.

Do not start by writing replacement services.

---

## 5. Frozen Architecture Decision

Use this boundary:

```text
Typed public MCP model
        ↓
thin wrapper conversion
        ↓
EXISTING service function
        ↓
ERPNext / Frappe / India Compliance
```

### Allowed wrapper responsibilities

The public wrapper may:

- validate typed Pydantic input;
- convert typed nested models into the exact legacy service payload shape;
- attach shared `InteractionDirective` objects to service result states;
- validate the returned service dictionary into explicit typed result models;
- return a RootModel / typed output compatible with the installed MCP SDK;
- register with `structured_output=True`.

### Forbidden wrapper responsibilities

The wrapper must not duplicate:

- Frappe metadata inspection;
- Customer GST validation;
- Item HSN/SAC requirements;
- entity resolution logic;
- Sales Order defaults/calculation;
- Frappe permissions;
- duplicate detection;
- approval storage;
- approval policy;
- write/commit/rollback behavior;
- ERPNext validation.

---

## 6. Public Tool Names — Do Not Rename

Keep exactly:

```text
prepare_customer
confirm_customer
prepare_item
confirm_item
prepare_sales_order
confirm_sales_order
```

Do not create v2 aliases.
Do not temporarily expose both legacy and typed versions.
Do not change profile tool allowlists merely because the implementation becomes typed.

The migration is in-place at the MCP contract boundary.

---

## 7. Customer Typed Contract

Create a dedicated Customer creation contract module after inspecting the current package organization.

A likely location is conceptually:

```text
mcp_erpnext/contracts/masters/customer.py
```

but choose the exact filename only after checking collisions with the existing Customer read contracts.

### 7.1 Typed Customer prepare input

The public input must be an explicit bounded model, not `dict[str, Any]`.

It must cover only fields currently accepted by the narrow Customer creation capability, including the currently supported nested Contact/Address/GST inputs.

Current creation/config concepts include:

```text
customer_name
customer_type
customer_group
territory
tax_id
gstin
gst_category

contact:
    first_name
    last_name
    email
    mobile

address:
    address_line1
    address_line2
    city
    state
    pincode
    country
```

### Runtime-metadata requirement rule

Do **not** incorrectly hard-code every currently mandatory site field as Pydantic-required if the existing service intentionally resolves mandatory/default state from live Frappe metadata.

The public schema should be explicit and bounded, while the existing service remains responsible for runtime mandatory/default requirements.

The `customer` argument itself remains required.

### Unknown fields

The typed public boundary should reject unsupported extra keys according to the existing `PublicContractModel(extra="forbid")` standard.

This is an intentional public-contract tightening. Do not change the internal service merely to preserve arbitrary ignored keys.

### 7.2 Customer prepare output

Inspect every currently reachable service result state and model them explicitly.

At minimum account for the states actually emitted by current Customer creation and its shared field resolver, such as applicable variants of:

```text
ready
needs_input
needs_selection
not_found
invalid_value
unsupported_field
unresolved_dependency
permission_denied
duplicate_suspected
error
```

Do not blindly copy this list; verify reachable states from the current service/helpers/tests first.

Preserve the existing payload semantics and fields.

### 7.3 Customer interaction directives

At the typed wrapper boundary:

- `ready` -> shared `approval_directive()`
- `needs_input` -> shared `input_directive()`
- explicit selection-required state -> shared `selection_directive()`
- terminal errors, permission denial, duplicate suspicion, created result -> do not falsely claim an interaction kind unless the existing semantic architecture justifies one

Do not parse natural language.

### 7.4 Customer confirm input/output

Create an explicit confirm input equivalent to:

```text
approval_token
confirm
```

Use the same approval-token semantics as current Quotation/Item/Sales Invoice patterns.

Model every current confirm result state, including:

```text
created
permission_denied
duplicate_suspected
error
```

Verify exact current states before finalizing the union.

### 7.5 Customer business behavior must remain unchanged

Specifically preserve:

- runtime Frappe metadata/default resolution;
- Customer Group/Territory field resolution;
- duplicate detection;
- Contact/Address permission checks;
- Customer permission checks;
- GSTIN normalization;
- India Compliance installed/not-installed branching;
- native India Compliance GST preparation;
- transient primary-address bridge behavior;
- existing approval payload;
- existing insert/commit/rollback behavior.

---

## 8. Item Typed Contract

Create a dedicated explicit Item creation contract module.

Do not reuse `item_read.py` for write/create payloads unless the current organization clearly calls for it.

### 8.1 Typed Item prepare input

Public input must be a bounded model for the existing sales-item creation capability.

Current base creation concepts include:

```text
item_code
item_name
item_group
stock_uom
is_stock_item
is_sales_item
```

The public contract must also account for the existing conditional India Compliance runtime input used by Task 23, including:

```text
gst_hsn_code
```

if current inspection confirms that this remains the public runtime requirement input.

### Policy-owned fields

`is_sales_item` is currently an MCP policy value for this sales Item capability.

Do not accidentally let the typed public schema weaken or bypass that policy.

If the current service accepts but overrides/controls a field, preserve the service behavior and expose only what is safe and meaningful at the public boundary.

### Explicit exclusion

Do not add Item pricing/accounting/valuation/tax fields just because a new typed model is being created.

The existing narrow capability intentionally avoids leaking or accepting fields such as pricing, valuation, accounts, or unrelated stock configuration.

### 8.2 Item prepare output

Inspect and explicitly model every currently reachable state from:

```text
resolve_creation_contract
resolve_contract_values
run_effective_requirements
india_compliance_item_preflight
prepare_item
```

Likely status families include the same structured input/selection/error categories used by Customer plus:

```text
permission_denied
duplicate_suspected
ready
error
```

Do not guess; verify exact payload shapes.

### 8.3 Item interaction directives

Use the shared directives at the typed boundary:

```text
ready -> APPROVAL
needs_input -> INPUT
needs_selection -> SELECTION
```

Do not move India Compliance requirement logic into the wrapper.

### 8.4 Item confirm input/output

Add explicit confirm input and output contracts.

Preserve existing:

- approval claim/cancel behavior;
- create permission recheck;
- duplicate recheck;
- insert/commit/rollback;
- created Item result.

### 8.5 HSN/SAC protection

Task 23 behavior is frozen for this migration.

The typed migration must not:

- make India Compliance a hard dependency;
- invent an HSN/SAC requirement when India Compliance is absent;
- bypass the effective runtime requirement provider;
- perform its own HSN master validation;
- rename or silently transform the existing business requirement.

---

## 9. Sales Order Typed Contract

Create a dedicated Sales Order create contract module separate from the existing read contract unless current organization strongly supports one combined module.

### 9.1 Customer input must become an explicit resolved reference

For the public Sales Order create contract, align with the already-frozen Quotation/Sales Invoice/Purchase Order reference design.

Prefer:

```text
CustomerReference:
    doctype: "Customer"
    name: <non-empty>
```

rather than an arbitrary Customer string.

The wrapper may pass the resolved `name` into the existing Sales Order service, which remains unchanged.

This deliberately makes the public contract deterministic and removes ambiguous free-form Customer selection from this prepare tool.

Do not modify `resolve_customer` itself.

### 9.2 Item rows must become explicit typed rows

Use an Item reference plus positive quantity, conceptually:

```text
item:
    doctype: "Item"
    name: <non-empty>
qty: > 0
```

Do not expose public aliases such as arbitrary `item_code`, `item_name`, or `quantity` once the typed contract is active unless current architecture inspection proves one is intentionally required.

The thin wrapper converts the typed row to the existing internal service payload.

### 9.3 Other supported Sales Order inputs

Preserve the current narrow create capability only:

```text
company
delivery_date
selling_price_list
```

Use appropriate existing shared types / `date` types where safe.

Do not add fields merely because ERPNext Sales Order supports them.

### 9.4 Sales Order prepare output

Inspect and explicitly model every reachable current result state.

Preserve the existing preview, including currently exposed fields such as:

```text
customer
customer_name
company
order_type
transaction_date
delivery_date
currency
selling_price_list
items
grand_total
```

Preserve the current correction metadata if it remains part of the service result.

Account for current missing-input, not-found/error, and ready states as actually reachable after deterministic typed references are introduced.

### 9.5 Sales Order interaction directives

At minimum:

```text
ready -> APPROVAL
needs_input -> INPUT
```

If a verified current result state still requires an explicit candidate choice after using typed references, use the shared SELECTION directive. Do not add SELECTION merely for theoretical symmetry.

### 9.6 Sales Order confirm contract

Type:

```text
approval_token
confirm
```

Model the existing exact output states, including the current created result and the current confirmation/error semantics.

Do not normalize or redesign service states merely to look like Quotation unless a wrapper-only compatibility mapping is already established by the project standard and does not change semantics.

---

## 10. Shared Contract Reuse

Reuse existing primitives wherever semantically identical:

```text
PublicContractModel
NonEmptyString
CustomerReference
ItemReference
ToolError
InteractionDirective
approval_directive
input_directive
selection_directive
```

Create new shared create-contract output primitives only when at least two of Customer/Item/Sales Order genuinely share the exact same public shape.

Do not create a giant generic `CreateAnythingInput` or `CreateAnythingOutput`.

Public contracts remain business-capability-specific.

---

## 11. Registry Migration

Update `mcp_erpnext/contracts/registry.py`.

Replace the six `_legacy(...)` declarations with normal `ToolContract(...)` entries having explicit:

```text
input_model
output_model
operation
side_effect
approval_required
interaction_kinds
approval_confirm_tool where applicable
approval_guard for CONFIRM_WRITE
```

Expected semantic metadata:

### Prepare tools

```text
operation = PREPARE
side_effect = PREPARE
approval_required = False
```

and interaction metadata matching the actual typed result states.

### Confirm tools

```text
operation = CONFIRM
side_effect = CONFIRM_WRITE
approval_required = True
approval_guard = TRUSTED_PENDING_OPERATION_GUARD
```

### Legacy inventory

After all six pass the typed contract audit:

```python
FROZEN_LEGACY_TOOL_NAMES = frozenset()
```

or the equivalent empty immutable inventory used by the current project.

Do not delete the architecture concept that future tools may never add a new legacy exception.

If `_legacy()` becomes dead code, remove it cleanly after confirming there are no remaining callers.

---

## 12. Wrapper Registration

All six migrated tools must use the same current registration pattern as typed tools:

```text
mcp.tool(..., structured_output=True)
```

The public wrappers should be top-level named functions where that improves direct testability, following Quotation/Sales Invoice/Purchase Order conventions.

Do not expose `Context` inside `inputSchema`.

---

## 13. Interaction Audit Coverage

Inspect `mcp_erpnext/contracts/audit.py`.

The interaction implementation path audit currently includes Customer and Item wrappers and selected typed wrappers.

After Sales Order adopts the shared interaction directive, ensure the audit covers the relevant implementation path consistently.

Do not weaken the natural-language parser prohibition.

Do not add phrase matching, regex-based user-intent parsing, or client-specific interaction logic.

---

## 14. Files / Components Allowed to Change

After mandatory inspection, expected allowed areas are:

```text
mcp_erpnext/contracts/masters/...
mcp_erpnext/contracts/selling/...
mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/audit.py            # only if required for typed/interaction audit coverage

mcp_erpnext/tools/masters/customer.py
mcp_erpnext/tools/masters/item.py
mcp_erpnext/tools/selling/sales_order.py

mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_interaction_contracts.py
mcp_erpnext/tests/test_customer_service.py     # only if public-wrapper assumptions are encoded here
mcp_erpnext/tests/test_item_service.py         # only if public-wrapper assumptions are encoded here
relevant new focused contract tests

docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md   # only factual legacy-status update if needed
docs/TOOLS.md                                     # regenerate; do not hand-edit
README/docs references only if they explicitly claim legacy status

docs/inspect/LEGACY_CREATE_TOOL_TYPED_CONTRACT_MIGRATION_IMPLEMENTATION_REPORT.md
```

Add the minimum new contract files needed for clean domain organization.

---

## 15. Files / Components NOT to Change

Do not change unless a failing test proves the typed boundary cannot be implemented without a minimal compatibility correction, and document such a case explicitly:

```text
mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/masters/item.py
mcp_erpnext/services/selling/sales_order.py

mcp_erpnext/services/integrations/india_compliance_customer.py
mcp_erpnext/services/integrations/india_compliance_item.py

mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/http_transport.py
mcp_identity
Frappe / ERPNext / India Compliance source
```

No approval-store migration.
No Redis work.
No multi-worker redesign.
No lifecycle tool redesign.
No update-tool redesign in this task.

---

## 16. Explicit Non-Goals

Do not:

- rename any of the six tools;
- add Customer/Item/Sales Order v2 tools;
- rewrite service logic;
- change Frappe permissions;
- change approval mode semantics;
- change process-local approval storage;
- change approval TTL;
- add OAuth or identity changes;
- add new Customer fields beyond the current capability;
- add Item pricing/valuation/accounting fields;
- add Sales Order fields merely for completeness;
- add Sales Invoice work;
- change aggregate tools;
- change query/get/read tools;
- centralize unrelated configs;
- implement explicit Quotation/Sales Order update-tool migration;
- implement Task 33's Sales read-gap review;
- add a new legacy exception.

---

## 17. Backward Compatibility Rule

### Tool names

Must remain stable.

### Business semantics

Must remain stable.

### Public schema

A deliberate tightening is expected:

```text
arbitrary dicts -> explicit typed fields
unknown keys -> rejected
free-form Sales Order Customer/Item references -> explicit resolved references
untyped outputs -> discriminated typed output models
```

This schema tightening is the purpose of the task and should be clearly documented in the implementation report.

Do not preserve unsafe/untyped aliases merely to claim byte-for-byte schema compatibility.

---

## 18. Required Tests — Contract Layer

Add focused tests proving at least:

### 18.1 Legacy inventory is empty

```text
FROZEN_LEGACY_TOOL_NAMES == empty
```

and every registered tool still passes `audit_tool_contracts`.

### 18.2 All six tools publish explicit object schemas

For each:

```text
prepare_customer
confirm_customer
prepare_item
confirm_item
prepare_sales_order
confirm_sales_order
```

assert:

```text
inputSchema.type == object
outputSchema.type == object
```

and registry metadata reports explicit typed contracts rather than legacy.

### 18.3 No arbitrary public objects

The new input schemas must not contain unrestricted arbitrary object payloads.

Customer nested contact/address may be objects, but they must have explicit properties and forbid extras.

### 18.4 Runtime fields hidden

Assert public schemas do not expose:

```text
ctx
Context
frappe_user
authorization
approval_mode
trusted_at
record_trusted_user_approval
secrets
```

### 18.5 Approval guard preserved

All three confirm tools must still publish:

```text
side_effect = CONFIRM_WRITE
approval_guard = trusted_pending_operation
```

### 18.6 Prepare/confirm relationship

Each prepare contract requiring approval must identify the correct confirm counterpart through current registry metadata.

---

## 19. Required Tests — Customer

Add tests proving:

1. Customer prepare schema is explicit and bounded.
2. Nested contact fields are explicit.
3. Nested address fields are explicit.
4. GST-related fields currently supported by the capability remain represented.
5. unsupported extra public fields are rejected.
6. wrapper converts typed input to the existing service payload without business logic.
7. `ready` gets APPROVAL directive.
8. `needs_input` gets INPUT directive.
9. current selection-required state gets SELECTION directive.
10. permission-denied/duplicate/error states remain correctly typed.
11. confirm input requires `approval_token` + `confirm`.
12. created Customer output remains typed and preserves current public values.
13. existing Customer service test suite still passes unchanged except where a test was specifically asserting legacy public wrapper shape.
14. India Compliance Customer tests remain green.

---

## 20. Required Tests — Item

Add tests proving:

1. Item prepare schema is explicit and bounded.
2. existing narrow sales-item fields remain exposed.
3. `gst_hsn_code` remains available when required by the current public runtime requirement design.
4. pricing, valuation, accounting and unrelated tax fields are not introduced.
5. unsupported extra public keys are rejected.
6. wrapper conversion contains no India Compliance business logic.
7. `ready` -> APPROVAL.
8. runtime missing input -> INPUT.
9. selection-required link values -> SELECTION.
10. permission/duplicate/error outputs are typed.
11. confirm schema/output is typed.
12. Task 23 Item HSN/SAC/effective-requirement tests remain green.

---

## 21. Required Tests — Sales Order

Add tests proving:

1. prepare schema uses explicit `CustomerReference`.
2. each item row uses explicit `ItemReference`.
3. item quantity must be positive and rejects booleans.
4. public row does not expose legacy arbitrary `item_code`/`item_name`/`quantity` aliases unless current inspection proves one is intentionally retained.
5. `ctx` is hidden.
6. optional narrow fields remain limited to the current capability.
7. wrapper passes only converted existing-service values to `_prepare_sales_order`.
8. wrapper does not calculate totals.
9. `ready` -> APPROVAL.
10. `needs_input` -> INPUT.
11. preview output is typed.
12. confirm input/output is typed.
13. existing approval/permission/replay tests remain green.
14. Sales Order read/query/aggregate tools are unaffected.
15. Sales Order -> Sales Invoice conversion tests are unaffected.

---

## 22. Regression Tests

Run the complete current project suite, not only new tests.

From the Frappe bench/application environment, use the repository's current established commands, typically equivalent to:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover \
  -s mcp_erpnext/tests -p 'test_*.py'
```

Run focused tests first, then the full suite.

Do not claim live Frappe/ERPNext verification if the environment is unavailable.

---

## 23. Catalog / Compile / Diff Verification

Run the existing checks:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m compileall -q mcp_erpnext
```

If available, also run the repository's lint/static checks without introducing dependency upgrades.

Run:

```bash
git diff --check
```

### Generated tool catalog acceptance

`docs/TOOLS.md` must no longer say:

```text
Legacy migration inventory
```

for the six migrated tools.

It must describe their explicit contract models and interaction kinds from actual registry/schema metadata.

---

## 24. Live MCP Verification

If a runnable authenticated MCP environment is available, inspect `tools/list` / MCP Inspector for the six migrated tools.

Verify:

1. Customer prepare shows explicit nested fields rather than arbitrary `customer: object`.
2. Item prepare shows explicit fields rather than arbitrary `item: object`.
3. Sales Order prepare shows explicit Customer/Item reference schemas.
4. all prepare/confirm tools publish `outputSchema`.
5. `ctx` is absent.
6. `structuredContent` validates against the published output schema.
7. approval metadata remains present on confirm tools.

If live MCP verification is unavailable, report that exact limitation; do not fabricate a pass.

---

## 25. Acceptance Criteria

This task is complete only when all are true:

- [ ] Current repository inspected before edits.
- [ ] Customer prepare input/output are explicit typed contracts.
- [ ] Customer confirm input/output are explicit typed contracts.
- [ ] Item prepare input/output are explicit typed contracts.
- [ ] Item confirm input/output are explicit typed contracts.
- [ ] Sales Order prepare input/output are explicit typed contracts.
- [ ] Sales Order confirm input/output are explicit typed contracts.
- [ ] Existing service/business logic remains unchanged.
- [ ] Existing Customer GST/India Compliance bridge remains unchanged.
- [ ] Existing Item HSN/SAC runtime requirement remains unchanged.
- [ ] Existing Sales Order ERPNext calculation/validation remains unchanged.
- [ ] Shared interaction directives are used where semantically required.
- [ ] No natural-language parsing is added.
- [ ] All six use `structured_output=True`.
- [ ] All six registry entries have explicit input/output models.
- [ ] Confirm entries retain the trusted pending-operation approval guard.
- [ ] `FROZEN_LEGACY_TOOL_NAMES` is empty after verification.
- [ ] No new legacy exception is added.
- [ ] Contract audit passes.
- [ ] Focused tests pass.
- [ ] Full test suite passes or exact unrelated/environmental failures are documented.
- [ ] Tool catalog regenerated and `--check` passes.
- [ ] `compileall` passes.
- [ ] `git diff --check` passes.
- [ ] Implementation report created.
- [ ] Live MCP schema check performed when environment permits, otherwise limitation documented.

---

## 26. Expected Result

The public Sales-profile creation surface should become conceptually consistent:

```text
Customer
  search/resolve         typed
  get/query/aggregate    typed
  prepare/confirm        typed

Item
  search/resolve         typed
  get/query/aggregate    typed
  prepare/confirm        typed

Quotation
  get/query/aggregate    typed
  prepare/confirm        typed

Sales Order
  get/query/aggregate    typed
  prepare/confirm        typed

Sales Invoice
  get/query/aggregate    typed
  prepare/confirm        typed
```

The project should have **no remaining public legacy contract exceptions** in the currently registered inventory.

---

## 27. Implementation Report Required

Create:

```text
docs/inspect/LEGACY_CREATE_TOOL_TYPED_CONTRACT_MIGRATION_IMPLEMENTATION_REPORT.md
```

The report must include:

1. files inspected;
2. pre-existing working-tree changes;
3. MCP SDK/Pydantic versions actually used;
4. exact legacy inventory before migration;
5. exact typed inventory after migration;
6. Customer input model and why fields are required vs optional;
7. Customer result-state inventory;
8. Customer interaction-state mapping;
9. confirmation Customer GST/India Compliance service code was not rewritten;
10. Item input model and HSN/SAC handling;
11. Item result-state inventory;
12. Item interaction-state mapping;
13. confirmation Item runtime requirement/India Compliance service code was not rewritten;
14. Sales Order reference-model decision;
15. Sales Order item-row model;
16. Sales Order result-state inventory;
17. Sales Order interaction mapping;
18. confirmation Sales Order business service was not rewritten;
19. registry changes;
20. legacy inventory final state;
21. audit changes if any;
22. exact files changed;
23. focused test commands/results;
24. full suite result;
25. catalog generation/check result;
26. compile result;
27. diff check result;
28. live tools/list or MCP Inspector result, or exact limitation;
29. any backward-incompatible public schema tightening;
30. unrelated findings that were deliberately not changed;
31. exact next task recommendation.

---

## 28. Known Limitations / Boundaries

This task does not solve the current process-local approval-store limitation.

Pending prepare state still lives according to the current approval implementation. Multi-worker/shared approval storage remains a separate future scaling task.

This task also does not change the already-decided public update/lifecycle architecture.

---

## 29. Exact Next Task

After Task 34 is implemented and verified, the next architecture task should be:

# TASK 35 — Explicit Business Update Public Contract Migration — Quotation + Sales Order

Purpose:

```text
public update capabilities -> DocType/business-explicit
internal mutation mechanics -> shared generic engine
submit/cancel/delete -> remain generic lifecycle capabilities
```

Do not implement Task 35 inside Task 34.

After Task 35, return to the deferred Sales read capability gap review / next DocType selection unless the user explicitly reprioritizes again.
