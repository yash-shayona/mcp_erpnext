# Task 25 - Customer GST / India Compliance Native Bridge Implementation

## Status
Implementation task, based on completed Task 24 audit.

## Primary Evidence
Before changing code, read and treat this audit as the primary design evidence:

`docs/inspect/CUSTOMER_GST_INDIA_COMPLIANCE_NATIVE_FLOW_AUDIT.md`

Do not assume the version numbers recorded in that audit are still current. At task execution time, inspect the currently installed Frappe, ERPNext, India Compliance, and `mcp_erpnext` source on the active target site and use the installed implementation as the runtime authority.

---

# 1. Objective

Upgrade the existing `prepare_customer -> confirm_customer` capability so Customer creation correctly bridges the installed India Compliance GST behavior without reimplementing India Compliance business logic, GST/GSP APIs, GSTIN algorithms, category rules, or Quick Entry browser behavior.

The implementation must:

- keep the existing Customer creation tool pair;
- preserve the existing approval boundary;
- preserve Frappe permissions and normal `Customer.insert()` lifecycle;
- support the India Compliance GST fields that are actually present at runtime;
- correctly carry GSTIN and effective GST Category through preview and approval;
- correctly use India Compliance's native transient primary-address convention when its installed hook requires that convention;
- keep ERPNext-only sites working unchanged;
- isolate India Compliance-specific knowledge in a lazy optional integration adapter;
- use installed India Compliance server functions/helpers where suitable instead of copying their logic;
- never create an MCP-owned GST API client;
- never copy Quick Entry JavaScript business logic into Python;
- never silently perform an external GSTIN lookup during `prepare_customer` when that native path can consume credits, enqueue jobs, or persist auxiliary integration records.

This is a bridge task, not a GST implementation task.

---

# 2. Frozen Architecture Decision

The following decisions are frozen for this task unless the currently installed source directly proves that a referenced native seam no longer exists or behaves materially differently.

```text
User / MCP client
      |
      v
prepare_customer
      |
      +--> existing generic Customer defaults / link resolution / duplicate checks
      |
      +--> lazy India Compliance adapter, only when capability exists on current site
      |       |
      |       +--> native metadata/defaults
      |       +--> native prepare-safe GST validation/normalization helpers
      |       +--> native prepare-safe enrichment only if a reusable native seam exists
      |       +--> native transient address convention when applicable
      |
      +--> effective approval-bound payload
      +--> effective preview
      |
      v
trusted approval
      |
      v
confirm_customer
      |
      +--> existing approval claim/site/user binding
      +--> existing permissions + duplicate recheck
      +--> frappe.get_doc(approved_payload)
      +--> normal Customer.insert(...)
      |       |
      |       +--> ERPNext lifecycle
      |       +--> installed India Compliance validate hooks
      |       +--> installed India Compliance after_insert address hook
      |
      v
commit
```

## Important boundary

Quick Entry is a browser/UI trigger. MCP must not imitate its dialog code.

If Quick Entry calls an India Compliance server capability, MCP may bridge the same installed Python capability only when doing so respects the MCP prepare/approval contract.

The audit-observed public GSTIN lookup can perform external I/O, enqueue status work, and enqueue Integration Request persistence. Therefore it must **not** be called unconditionally from `prepare_customer`.

If the installed app exposes a genuinely reusable, side-effect-free/read-only native seam for an archived or otherwise safe result, that seam may be used.

If no such seam exists, do **not** create one by copying archive queries, endpoint logic, response mapping rules, GST category rules, or API behavior into `mcp_erpnext`. Complete the rest of this task without proactive remote enrichment during prepare.

Normal `Customer.insert()` during confirmation remains allowed to execute whatever India Compliance lifecycle behavior is native for the installed configuration. MCP must not add a second GST lookup during confirmation.

---

# 3. Mandatory Inspect-Before-Change Gate

Before editing production code, inspect the current repository and installed source. Record the findings in the implementation report.

At minimum inspect:

1. Current `mcp_erpnext` Customer creation service.
2. Current Customer configuration/creation fields.
3. Current public Customer tool wrappers and contract registry.
4. Existing shared creation-contract and field-value resolver helpers.
5. Existing integration/provider patterns already implemented in `mcp_erpnext`, especially any India Compliance Item/HSN provider from earlier tasks.
6. Current approval store and interaction result conventions.
7. Current Customer tests and fake metadata.
8. Installed ERPNext Customer controller and primary-address helper.
9. Installed India Compliance:
   - Customer hooks;
   - Address hooks;
   - party validation;
   - GSTIN validation/normalization helpers;
   - GST category helpers;
   - GST API/autofill settings gates;
   - GSTIN info server function;
   - Quick Entry mapping only to understand the native boundary;
   - primary-address helper;
   - any safe archived/read-only GSTIN accessor if one exists.
10. Effective runtime Customer and Address metadata on the target site.
11. Installed-app state for the actual target site using runtime installed-app discovery, not only bench directory presence.

### Version rule

Do not hardcode or branch on a specific version string merely because Task 24 observed one version.

Record current versions for traceability only.

### Native-helper rule

Function names mentioned in Task 24 are audit evidence, not permanent APIs. Verify their current signatures/behavior against the installed source before importing/calling them.

---

# 4. Scope

## In scope

### A. Customer GST contract

Support the existing `gstin` field and add the smallest explicit `gst_category` extension required by the installed Customer metadata and native India Compliance behavior.

`gst_category` must:

- be explicit;
- be accepted only through the defined Customer creation contract;
- use runtime metadata/native validation;
- never be implemented through `extra_fields` or arbitrary field passthrough;
- appear in the effective preview when applicable;
- be approval-bound.

### B. Optional India Compliance adapter

Add or extend a narrowly-scoped integration module under the existing integrations/service structure.

Suggested conceptual responsibility:

```text
IndiaComplianceCustomerAdapter
    - capability detection
    - installed-app/source-compatible lazy imports
    - GST field availability
    - prepare-safe native normalization/validation
    - safe optional enrichment capability detection
    - transient Customer primary-address payload convention
```

Do not create a generic plugin framework just for this task.

### C. Effective prepared state

The preview and approval payload must represent the effective prepared Customer state, not an obsolete pre-validation input dictionary.

At minimum this applies to:

- `gstin`;
- `gst_category`;
- Customer name only if a native prepare-safe enrichment path actually changed it;
- address fields only if a native prepare-safe enrichment path actually changed them;
- the transient address carrier required by the installed India Compliance Customer hook.

Do not serialize the entire validated `Document` blindly into the approval payload. Project back only explicitly supported/required fields.

### D. Native primary Address bridge

When India Compliance is installed and its current Customer after-insert helper uses a transient input convention equivalent to the audited `_address_line1` path, construct that transient payload deliberately.

Do not detect that transient helper through `frappe.get_meta("Customer").has_field(...)` unless the current installed source actually defines it as a DocField.

The final Customer lifecycle must create the primary Address exactly once.

When India Compliance is absent, preserve ERPNext's normal `address_line1` path.

### E. Prepare safety

`prepare_customer` must not unexpectedly:

- insert Customer/Address/Contact records;
- call a custom MCP GST endpoint;
- perform a loopback HTTP call to Frappe;
- consume India Compliance API credits merely to build a preview;
- enqueue India Compliance API/integration persistence merely to build a preview;
- insert Integration Request records through an MCP-created path;
- bypass native access checks.

If the installed full Customer/Address validation hooks can themselves trigger external autofill under current settings, the adapter must avoid blindly invoking that side-effecting path during prepare.

Use installed native **prepare-safe** helpers where available for GSTIN format/normalization/category validation rather than reimplementing rules.

If current installed source provides no safe way to obtain remote enrichment during prepare, remote enrichment is unavailable in prepare for this task. That is an acceptable result and must be reported explicitly; do not solve it by duplicating India Compliance internals.

### F. Confirmation

Keep the existing confirm flow:

- claim trusted approval;
- bind to site/user/context;
- recheck permissions;
- recheck duplicate state;
- build Customer from the approval payload;
- call normal `insert()` with all bypass flags false;
- allow ERPNext and India Compliance lifecycle hooks/validation to remain authoritative;
- commit only after successful insert;
- rollback through existing error path on failure.

Do not perform an MCP GSTIN refetch in `confirm_customer`.

---

# 5. Explicitly Out of Scope

Do not implement any of the following:

- new `create_gst_customer` public tool;
- new generic GST lookup public tool unless separately approved in a later task;
- MCP-owned GST/GSP HTTP client;
- copied India Compliance Public API endpoint logic;
- copied API credential/secret management;
- copied GSTIN checksum/regex/category algorithm;
- copied Quick Entry JavaScript/dialog behavior;
- custom pincode/GST state derivation when India Compliance already owns it;
- custom archive query that reproduces India Compliance GSTIN archive semantics;
- external API call tests using real credits;
- sandbox account setup;
- GST Settings mutation;
- India Compliance credential creation;
- Customer contract redesign beyond the smallest required GST Category extension;
- migration of unrelated legacy Customer tools to a new broad typed schema;
- changes to Quotation, Sales Order, Item, Supplier, Purchase Order, or Accounts capabilities;
- changes to shared approval semantics;
- Administrator/service-user fallback;
- `ignore_permissions=True` for Customer or Address creation;
- arbitrary custom-field passthrough;
- bench/app version pinning.

---

# 6. Inputs and Dependencies

Primary inputs:

1. Task 24 audit document.
2. Current `mcp_erpnext` repository.
3. Current target site runtime metadata and installed-app state.
4. Installed Frappe/ERPNext/India Compliance source.
5. Existing Customer service tests.
6. Existing shared interaction/approval infrastructure.
7. Existing integration/provider pattern, if already present.

The implementation must remain loadable on a site where India Compliance is not installed.

---

# 7. Allowed Changes

After inspection confirms exact current paths, changes may be made only where necessary in these areas:

- Customer creation configuration/contract field list;
- Customer master service;
- narrowly-scoped India Compliance Customer integration adapter/provider;
- Customer service unit/regression tests;
- integration/provider tests;
- public tool/contract documentation only if the explicit `gst_category` addition requires it;
- implementation report for this task.

Potential paths may include, depending on the current repository:

```text
mcp_erpnext/config/masters/customer.py
mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/integrations/india_compliance_customer.py
mcp_erpnext/tests/test_customer_service.py
mcp_erpnext/tests/...integration/provider-specific test...
mcp_erpnext/contracts/registry.py          # only if contract metadata must change
mcp_erpnext/docs/TOOLS.md                  # only if public contract docs must change
mcp_erpnext/docs/implement/...report.md
```

Do not create paths mechanically if the current repository has since established a better existing integration location. Reuse the established pattern.

---

# 8. Disallowed Changes

Do not modify:

- Frappe source;
- ERPNext source;
- India Compliance source;
- GST Settings values;
- site config secrets;
- database schema manually;
- Custom Field records manually;
- Property Setters manually;
- approval token semantics;
- identity model;
- MCP transport/authentication;
- unrelated tool contracts;
- unrelated master or transaction services;
- external integration credentials.

Do not add dependencies unless the currently installed app already provides the required module and the import is lazy/optional.

---

# 9. Implementation Requirements

## 9.1 Capability detection

Use runtime installed-app/capability detection.

Requirements:

- bench directory presence alone is insufficient;
- no unconditional India Compliance import at `mcp_erpnext` module import time;
- ordinary Customer creation must work when India Compliance is absent;
- adapter must fail closed only for the specific optional GST capability it is trying to use, not for generic ERPNext Customer creation.

## 9.2 `gst_category` contract

Add `gst_category` as a deliberate supported Customer creation field only where runtime metadata/app capability supports it.

Expected behavior:

- existing clients without `gst_category` keep working;
- explicit category values are checked through existing runtime field resolver/native metadata where applicable;
- native defaults remain native defaults;
- native GST/category validators remain authoritative;
- arbitrary unknown Customer fields remain rejected/ignored according to the existing narrow contract behavior;
- do not add `extra_fields`.

## 9.3 GSTIN normalization and validation

Do not create a new GSTIN validation implementation.

On an India Compliance site, use the installed native prepare-safe helper(s) for GSTIN normalization/validation if current source confirms they are side-effect-free.

On a non-India-Compliance site, preserve existing metadata-driven behavior.

Do not make India Compliance imports mandatory for generic Customer startup.

## 9.4 GST Category derivation

Do not hardcode category derivation rules.

If an effective category is needed during prepare:

- prefer native runtime default;
- use installed native pure/prepare-safe category helper(s) if applicable;
- preserve an explicit user category where native rules permit it;
- let native validation reject incompatible combinations;
- do not duplicate the category/GSTIN mapping tables in MCP.

If the installed native category setter can trigger remote lookup, do not blindly call that setter during prepare. Select the installed prepare-safe native seam instead, if one exists.

## 9.5 Remote/native GSTIN enrichment

Treat enrichment separately from basic GST correctness.

Algorithmic rule:

```text
if India Compliance absent:
    no enrichment integration
elif GSTIN absent:
    no enrichment call
elif native prepare-safe enrichment seam exists:
    call that native seam under current Frappe user/context
    map only native returned supported fields
else:
    do not call external GST service during prepare
    continue supported manual/local GST prepare behavior
    do not pretend autofill occurred
```

### Critical prohibition

Do not inspect Integration Request tables yourself and reproduce India Compliance archive-age/filter/normalization behavior unless the installed India Compliance source exposes that exact operation as a reusable native helper intended for such use.

Do not copy private implementation into `mcp_erpnext` just to manufacture a prepare-safe archive path.

If the only existing native function can fall through to external API I/O and queued persistence, it is **not prepare-safe** for this task.

## 9.6 Current-user behavior

Any native callable reused by the adapter must run under the already established Frappe user context.

Do not:

- switch to Administrator;
- use service-user fallback;
- bypass Desk-access checks in the public India Compliance wrapper;
- call private helpers merely to avoid a public permission check.

If using a native pure helper that has no access check because it is only a validator/normalizer, normal MCP Customer create permission checks still remain required before approval and confirmation.

## 9.7 Effective payload projection

Fix the current validation-mutation loss.

Do not do this conceptually:

```text
validate temporary Document
throw Document away
approve old pre-validation dict
```

Instead:

- construct the prepared Document/state;
- run only allowed prepare-safe native operations;
- explicitly project supported effective values back into a narrow payload;
- build preview from that effective payload;
- approval must bind the same payload that the user previewed.

Do not approve fields that were not shown when they materially change Customer identity/GST/address behavior.

## 9.8 Address behavior

### India Compliance site

When current installed source confirms the transient primary-address convention:

- pass the address through that native convention;
- include effective GSTIN/category as required by the native hook;
- do not also populate the ERPNext core address carrier in a way that causes a second Address;
- do not insert Address manually from MCP if the native Customer lifecycle owns creation;
- approval-bind all address inputs used by the final native hook.

### ERPNext-only site

Keep the current core address behavior unchanged.

### Test-model correction

Remove the false assumption that the transient helper must appear in Customer metadata. Fake metadata should model actual metadata semantics.

## 9.9 Address validation

Use native Frappe/India Compliance validation where it can be done within the prepare-safety boundary.

If a full Address validation hook can trigger remote autofill under production settings, do not invoke it blindly during prepare. Reuse installed safe native validators/helpers where available and leave full lifecycle validation to confirmation.

Do not copy state/GSTIN/pincode business rules into MCP.

## 9.10 Error/result behavior

Reuse the existing MCP interaction and observability conventions.

Return safe actionable outcomes for cases such as:

- GST capability unavailable;
- unsupported GST field on current site;
- invalid GSTIN;
- invalid GST category/GSTIN combination;
- permission denial;
- duplicate Customer/GSTIN;
- required address input missing;
- native enrichment not available during prepare;
- native API/configuration unavailable.

Do not expose:

- API secrets;
- credentials;
- internal stack traces;
- raw Integration Request payloads;
- low-level GSP response secrets.

Do not create a new client-specific error schema.

---

# 10. Required Scenario Behavior

## Scenario A - ERPNext-only site, basic Customer

Expected:

- no India Compliance import failure;
- existing Customer prepare/confirm behavior unchanged;
- core address path remains unchanged.

## Scenario B - India Compliance installed, no GSTIN

Expected:

- no remote lookup;
- native/default GST Category behavior respected;
- normal manual Customer/address creation supported;
- preview shows effective category if the contract/runtime field applies.

## Scenario C - GSTIN supplied, API/autofill disabled

Expected:

- no external lookup;
- use native local/prepare-safe validation and category behavior;
- prepared GSTIN/category visible in preview;
- approval binds them;
- final insert runs native lifecycle.

## Scenario D - GSTIN supplied, sandbox mode

Expected:

- no Public API autofill attempt from MCP prepare;
- native local behavior used;
- no custom fallback API.

## Scenario E - GSTIN supplied, production autofill configured

Expected:

- `prepare_customer` must not blindly call a side-effecting lookup merely because configuration enables it;
- use a native prepare-safe enrichment seam only if current installed source exposes/proves one;
- otherwise prepare using supported local/manual data and state clearly in code/result semantics that remote enrichment was not performed during prepare;
- `confirm_customer` does not add an MCP refetch;
- normal Customer insert may execute native India Compliance production lifecycle behavior.

## Scenario F - Native safe cached/archived result is available

Conditional scenario.

Only if the installed app exposes a reusable prepare-safe native seam:

- use it;
- preserve current user context;
- map native result into supported Customer/address fields;
- show effective values in preview;
- bind exact effective values to approval;
- prove no external request, queue, or persistence was triggered by the prepare call.

If no reusable seam exists, mark this scenario as not applicable and do not implement a copied archive reader.

## Scenario G - Invalid GSTIN

Expected:

- native validator result/error used;
- no approval token;
- no Customer/Address write.

## Scenario H - GST Category conflict

Expected:

- native rule decides validity;
- no duplicated MCP category algorithm;
- no approval when invalid.

## Scenario I - India Compliance primary Address

Expected:

- final Customer insert creates exactly one primary Address through native lifecycle;
- Address receives GSTIN/category according to native app behavior;
- no MCP direct duplicate Address insert.

## Scenario J - User without permission

Expected:

- normal Customer/Address/Contact permission checks deny as appropriate;
- no bypass user;
- no ignored permissions.

---

# 11. Required Tests

Use the current project test conventions. Do not require real GST API credits.

At minimum add/adjust tests for:

1. India Compliance absent startup/import safety.
2. Existing ERPNext-only Customer regression.
3. Explicit `gst_category` accepted when supported.
4. `gst_category` not silently accepted through arbitrary extra fields.
5. GSTIN omitted.
6. GSTIN with API/autofill disabled.
7. Sandbox behavior.
8. Native pure GSTIN validation helper delegation.
9. Native category helper/default delegation.
10. Invalid GSTIN -> no approval.
11. Invalid category/GSTIN -> no approval.
12. Prepared effective GSTIN/category copied into preview and approval payload.
13. Validation/effective-state mutation is not discarded.
14. `_address_line1` or current installed equivalent is treated as transient, not fake metadata.
15. India Compliance address path does not also trigger ERPNext duplicate address creation through MCP payload construction.
16. ERPNext-only address path remains unchanged.
17. Permission denial for Customer.
18. Permission denial for Address when address creation is requested.
19. Guest/current-user safety.
20. Duplicate Customer/GSTIN behavior remains permission-aware.
21. Confirm uses approved payload and does not perform an MCP GSTIN refetch.
22. Confirm still uses normal `Customer.insert()` bypass flags false.
23. No MCP path inserts Integration Request during prepare.
24. No MCP path makes external HTTP during unit tests.
25. Conditional native safe-enrichment test only if installed source exposes a reusable prepare-safe seam.

### Mocking rule

Mocks may prove that a native callable was or was not invoked, but do not mock a behavior and then claim that behavior was live-verified.

Separate:

- unit/static proof;
- Frappe database integration proof;
- native hook proof;
- external API proof;
- browser Quick Entry proof.

No real external API call is required for task completion.

---

# 12. Test Execution Safety

Run only the project's normal authorized test commands.

Do not:

- call a real GST/GSP endpoint;
- consume API credits;
- modify GST Settings to force a branch;
- write real production Customer records merely to prove the task;
- change credentials;
- enable/disable sandbox on the user's behalf.

If a database-backed test creates records in a dedicated test context, use the project's existing test isolation/cleanup conventions.

---

# 13. Acceptance Criteria

Task 25 is complete only when all applicable criteria are satisfied.

### Architecture

- [ ] No new GST Customer public tool was added.
- [ ] India Compliance code is isolated behind a lazy optional adapter/provider.
- [ ] ERPNext-only startup remains independent of India Compliance.
- [ ] No GST/GSP/API business logic is reimplemented in MCP.
- [ ] No Quick Entry browser code is copied.

### Contract

- [ ] Existing `gstin` support remains.
- [ ] `gst_category` is the only deliberate GST contract extension unless current installed source proves another field is strictly necessary.
- [ ] No `extra_fields` passthrough was added.
- [ ] Effective GST values are visible in preview and approval-bound.

### Prepare safety

- [ ] No Customer/Address/Contact business record is inserted by prepare.
- [ ] No custom MCP external GST API call exists.
- [ ] No side-effecting native GSTIN lookup is called unconditionally by prepare.
- [ ] No MCP-created Integration Request/status queue side effect occurs during prepare.
- [ ] If no native prepare-safe enrichment seam exists, implementation explicitly leaves remote enrichment unavailable during prepare rather than duplicating it.

### Native behavior

- [ ] Native GSTIN/category helpers are used where appropriate and safe.
- [ ] Final insert still runs normal ERPNext/India Compliance hooks.
- [ ] Current-user/permission behavior is preserved.
- [ ] No Administrator or ignored-permission fallback exists.

### Address

- [ ] Transient India Compliance address convention is selected by installed capability/hook knowledge, not incorrect DocField detection.
- [ ] Exactly one primary Address is produced by the native lifecycle in the India Compliance path.
- [ ] GSTIN/category reach that Address through native behavior.
- [ ] ERPNext-only address behavior is unchanged.

### Tests

- [ ] Required unit/regression tests pass.
- [ ] No test requires a live GST API.
- [ ] Conditional tests are clearly marked when the installed source has no prepare-safe enrichment seam.
- [ ] Fake metadata no longer claims the transient address helper is a DocField.

---

# 14. Expected Results

After Task 25, the MCP Customer creation behavior should conceptually be:

```text
"Create ABC Industries with GSTIN ..."
        |
        v
prepare_customer
        |
        +--> use current ERPNext Customer defaults/resolvers
        +--> detect India Compliance only if installed on current site
        +--> use native safe GST validation/category behavior
        +--> optionally use only proven native prepare-safe enrichment
        +--> prepare correct native address carrier
        |
        v
Preview
  Customer name
  Customer type/group/territory
  GSTIN
  Effective GST Category
  Contact
  Effective Address
        |
        v
Trusted approval
        |
        v
confirm_customer
        |
        v
normal Customer.insert()
        |
        +--> ERPNext lifecycle
        +--> India Compliance validation if installed
        +--> India Compliance primary Address hook if installed/applicable
        |
        v
Customer created
```

On a site without India Compliance:

```text
prepare_customer -> existing ERPNext Customer flow -> confirm_customer
```

No optional-app import error should occur.

---

# 15. Known Boundary Around Autofill

Do not misreport the implementation as reproducing browser Quick Entry autofill unless a native prepare-safe server seam was actually found and reused.

Task 24 proved that the audited public native GSTIN lookup can fall through to:

```text
external India Compliance Public API
    + queued GSTIN status work
    + queued Integration Request persistence
```

Therefore:

- browser Quick Entry capability and MCP prepare capability are not automatically equivalent;
- final `Customer.insert()` still runs installed native validation behavior;
- full party-name/address remote enrichment before approval is only supported when the installed app exposes a native path compatible with prepare safety;
- absence of such a path is a native boundary, not a reason to build duplicate MCP logic.

---

# 16. Implementation Report Required

Create a report under the project's established implementation-report folder.

The report must include:

1. Current versions observed at execution time.
2. Target site and installed-app evidence.
3. Existing files inspected before change.
4. Exact India Compliance native functions/helpers reused.
5. For each reused helper, why it is safe in prepare or why it is confirm-only.
6. Whether a reusable prepare-safe GSTIN enrichment seam exists.
7. If none exists, explicitly state that no MCP archive/API implementation was added.
8. Exact files changed.
9. Public contract delta.
10. Before/after Customer prepare flow.
11. Before/after primary Address flow.
12. Tests added/changed.
13. Commands/tests run.
14. Test results.
15. What was mocked versus live verified.
16. Confirmation that no real GST API call/credit was used during implementation testing unless the user separately authorized it.
17. Remaining limitations.
18. Exact next task recommendation.

---

# 17. Stop / Escalation Conditions

Stop implementation of the affected sub-part and document evidence if:

- installed India Compliance source materially differs from the audit in a way that changes the bridge boundary;
- the only possible approach requires copying GST/GSP/API logic;
- the only possible prepare enrichment path requires external I/O or persistence and there is no native safe seam;
- correct address behavior would require modifying India Compliance/ERPNext source;
- a requested field requires widening the public contract beyond the approved explicit GST fields;
- implementation would require changing approval semantics;
- implementation would require secret inspection/output;
- a test would require consuming real API credits without explicit user authorization.

Do **not** invent a workaround. Complete all unaffected in-scope implementation and report the blocked sub-part clearly.

---

# 18. Exact Next Task

After Task 25 implementation and verification, the next task is **not automatically another GST feature**.

First review the Task 25 implementation report and actual tests.

If Task 25 proves Customer GST creation, effective preview, approval binding, and native primary Address behavior are correct, the next task should be a focused runtime verification task for the Customer creation capability across:

- India Compliance installed with current local/sandbox settings; and
- an ERPNext-only site if one is safely available.

A separate native remote-GSTIN-enrichment task should be created only if the implementation report proves a remaining business requirement and identifies a native callable boundary that can be used without duplicating India Compliance logic or violating approval/prepare safety.

---

# Final Rule for the Coding Agent

**Evidence first, bridge second, custom logic last.**

Do not solve this task by making `mcp_erpnext` smarter than India Compliance.

Make `mcp_erpnext` correctly hand data to, and safely reuse, the installed native India Compliance/Frappe lifecycle.
