# Task 23 — Item Creation Conditional Runtime Requirements Implementation

Date: 2026-09-10

## 1. Task Type

Implementation task.

This task implements the architecture approved by the read-only audit:
`ITEM_CREATION_EFFECTIVE_VALIDATION_AUDIT.md`.

Do not redesign the Item creation workflow from scratch. Inspect the current repository first and extend the existing patterns only where required.

---

## 2. Objective

Implement a small, client-independent, runtime preflight mechanism for Item creation so that known conditional requirements contributed by optional installed apps can be surfaced during `prepare_item`, before approval and before `confirm_item` attempts the real write.

The first and only optional-app rule in scope is the source-confirmed India Compliance Item HSN/SAC rule.

The implementation must ensure that:

1. ERPNext-only sites continue to work exactly as before.
2. India Compliance is not a hard dependency of `mcp_erpnext`.
3. HSN/SAC is not made globally mandatory.
4. HSN/SAC is requested only when the active runtime rule actually applies.
5. The final write still goes through the existing normal Frappe `insert()` lifecycle with permissions, links, mandatory checks, ERPNext validation, and installed-app hooks enabled.
6. Approval security and approval ownership are unchanged.
7. No generic arbitrary-field or `extra_fields` input surface is introduced.
8. The MCP server remains standalone and client-independent.

---

## 3. Source of Truth

Use the completed audit as the governing design input.

Confirmed audit findings that must drive this implementation:

- `prepare_item` currently uses the shared metadata/default creation flow but only treats static `reqd` as missing.
- `mandatory_depends_on` is recorded but not evaluated.
- current Item creation input is narrowed by `item_config.CREATION_FIELDS`.
- current MCP Item policy fixes `is_sales_item=1` for the sales Item creation capability.
- India Compliance adds `Item.gst_hsn_code` as a runtime Custom Field.
- that field has `mandatory_depends_on` tied to active GST validation and `doc.is_sales_item`.
- India Compliance also registers a server-side Item `validate` hook.
- the actual HSN/SAC server validator requires a code only when:
  - India Compliance is active for the site,
  - `GST Settings.validate_hsn_code` is enabled,
  - effective `Item.is_sales_item` is truthy,
  - and `gst_hsn_code` is blank.
- `min_hsn_digits` affects accepted code length, not whether the rule is active.
- confirmation currently calls normal Frappe insert with:
  - `ignore_permissions=False`
  - `ignore_links=False`
  - `ignore_mandatory=False`
- the approval token is consumed before persistence, so a preventable late HSN failure currently forces the user to prepare again.

Do not replace these findings with assumptions.

---

## 4. Existing Architecture to Preserve

The implementation must preserve the current flow:

```text
resolve_item
    -> resolved / ambiguous / not_found

not_found
    -> prepare_item
        -> needs_input OR ready
        -> ready creates guarded approval
    -> explicit trusted approval
    -> confirm_item
        -> normal Frappe insert
```

Preserve these existing boundaries:

```text
MCP tool wrapper
    -> request/runtime context
    -> Item service
    -> shared metadata/default resolution
    -> permission-aware field/link resolution
    -> approval store
    -> confirmation write
    -> Frappe / ERPNext / installed-app validation
```

The new logic belongs in preparation/preflight. It must not move business-write authority out of Frappe.

---

## 5. Mandatory First Step — Inspect Before Editing

Before changing code, inspect the actual current implementation and nearby patterns.

At minimum inspect:

```text
mcp_erpnext/services/masters/item.py
mcp_erpnext/services/common/creation_contract.py
mcp_erpnext/services/common/field_value_resolver.py
mcp_erpnext/config/masters/item.py
mcp_erpnext/tools/masters/item.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/approvals.py
mcp_erpnext/settings.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_creation_contract.py
```

Also inspect repository conventions for:

- small service helper modules,
- optional integration boundaries,
- dataclass / typed internal result patterns,
- error-envelope construction,
- `needs_input` result shape,
- test factories and monkeypatch patterns,
- installed-app checks,
- safe settings reads.

Do not create a new folder or abstraction only because this task suggests a possible location. Reuse an existing repository convention when one is clearly suitable.

If the current source differs materially from the audit, document the difference before implementing and adapt conservatively.

---

## 6. Frozen Architecture Decision

Implement this architecture:

```text
prepare_item
    -> resolve core configured Item fields
       from merged runtime metadata + defaults + MCP policy
    -> build effective unsaved Item state
    -> run bounded effective-requirements preflight
       -> generic core requirement handling
       -> optional-app providers
          -> India Compliance Item HSN provider
    -> if known required input is missing
         return needs_input
         DO NOT create approval
    -> otherwise continue existing field resolution / preview
    -> create approval bound to complete prepared payload

confirm_item
    -> unchanged guarded approval claim
    -> unchanged permission / duplicate rechecks
    -> frappe.get_doc(approved payload)
    -> unchanged normal insert
    -> installed-app validation remains authoritative
```

The preflight is advisory/proactive. It is not a replacement validation engine.

---

## 7. Core Design Requirements

### 7.1 Bounded effective-requirements seam

Add the smallest internal seam that allows preparation to ask:

> Given this doctype, effective prepared state, runtime metadata, and current site, are there any known additional inputs that should be collected before approval?

The seam may be implemented by extending `creation_contract.py` or by adding one small common module if that produces a cleaner boundary.

Do not create a universal validation framework.

The internal contract should be typed or structurally explicit.

A provider result should be able to represent at least:

```text
- applies / does not apply
- satisfied / missing / invalid / unavailable
- exact canonical fieldname
- safe human label
- reason
- optional safe constraints/guidance
- optional normalized/resolved value to include in prepared payload
```

Names may follow existing repository conventions.

Do not expose provider internals directly as arbitrary public dictionaries.

### 7.2 Provider execution order

Run provider preflight only after the effective core Item state is known, because applicability depends on effective `is_sales_item`.

Do not decide applicability only from raw user input.

### 7.3 No arbitrary expression evaluator

Do not generically evaluate `mandatory_depends_on`, `depends_on`, or arbitrary `eval:` expressions.

Reason:

- Frappe form expressions are not a complete server-side validation model.
- installed apps can enforce rules in controller hooks.
- executing arbitrary expressions would be unsafe and incomplete.

The India Compliance provider must model only the confirmed rule it owns.

---

## 8. India Compliance Provider

Implement one isolated provider for the Item HSN/SAC requirement.

The provider must not create a hard import dependency on India Compliance.

### 8.1 Applicability checks

The provider should apply only when all required runtime conditions are safely established.

Required checks:

```text
1. current site has india_compliance installed
2. effective Item metadata exposes gst_hsn_code as a usable Item field
3. effective Item.is_sales_item is truthy
4. GST Settings.validate_hsn_code is truthy
```

Installation alone must never imply that HSN is mandatory.

### 8.2 Settings read

Read the same effective site-level settings used by India Compliance:

```text
GST Settings.validate_hsn_code
GST Settings.min_hsn_digits
```

Prefer normal Frappe APIs and existing repository helpers.

Do not maintain a separate MCP settings cache.

Do not accept these values from the client.

### 8.3 HSN value sources

The provider must consider the effective HSN value from safe preparation inputs.

It must also inspect whether a value can be safely inherited from the configured Item Group HSN field, because India Compliance defines:

```text
gst_hsn_code.fetch_from = item_group.gst_hsn_code
fetch_if_empty = 1
```

Do not execute the entire document lifecycle just to obtain that value.

If the Item Group value can be read safely and permission-consistently using normal Frappe APIs, it may satisfy preflight.

If inheritance is uncertain or cannot be safely resolved, do not pretend the requirement is satisfied.

Final native Frappe link fetching and validation remain authoritative.

### 8.4 Missing HSN

When:

```text
india_compliance installed
AND validation enabled
AND effective is_sales_item = true
AND no supplied/inherited HSN is safely available
```

`prepare_item` must return `needs_input` before `approvals.create(...)`.

The response must clearly identify the missing HSN/SAC requirement and explain that it is required by the active GST/India Compliance rule for this sales Item.

No approval token should be created for an incomplete payload.

### 8.5 HSN length

When validation is enabled and `min_hsn_digits` is safely available, the provider may perform the same bounded length guidance used by India Compliance:

```text
min 4 -> accepted 4, 6, 8
min 6 -> accepted 6, 8
min 8 -> accepted 8
```

This is proactive guidance only.

Do not claim that preflight proves the HSN Link record exists.

Do not copy tax behavior into MCP.

Frappe/India Compliance remain responsible for:

- actual Link validity,
- final code validation,
- taxes populated from GST HSN Code,
- other hooks/controller logic,
- future rule changes not modeled here.

---

## 9. Critical Input-Continuation Design

The audit found an important constraint:

- current Item creation only projects configured core `CREATION_FIELDS`;
- `gst_hsn_code` is not part of that tuple;
- public arbitrary `extra_fields` input is forbidden;
- however the current legacy `prepare_item` wrapper receives a raw Item dictionary.

This implementation must support the actual continuation flow:

```text
prepare_item(...)
    -> needs_input: gst_hsn_code

caller supplies gst_hsn_code

prepare_item(..., gst_hsn_code=<value>)
    -> provider consumes that exact known field
    -> complete prepared payload
    -> ready
```

### 9.1 Required solution

Do NOT add `gst_hsn_code` to the global/core `item_config.CREATION_FIELDS` tuple.

Instead, introduce a narrow provider-owned accepted-input path.

The preferred shape is conceptually:

```text
raw Item request
    -> core creation-field projection
    -> provider-owned exact input extraction
         allowed only for a provider-declared canonical field
         allowed only when that field exists in current merged Item metadata
         allowed only when the provider is applicable/available
    -> effective prepared payload
```

The implementation may use a slightly different internal mechanism if it better fits current source conventions, but it must preserve these properties:

1. no arbitrary field passthrough;
2. no mass assignment;
3. no `extra_fields: dict`;
4. no global HSN requirement;
5. no direct app-specific branch scattered through generic Item field projection;
6. supplied provider value must become part of the final approval-bound payload;
7. provider-supplied field must still go through appropriate metadata/type/link handling where applicable.

### 9.2 Static public contract rule

Do not migrate the Item tools to a new typed public contract in this task.

The legacy wrapper remains the existing boundary.

This task is allowed to recognize the exact known provider-owned key `gst_hsn_code` inside the existing legacy Item request because that is required for the `needs_input -> provide input -> prepare again` continuation to function.

This exception is narrow and must be covered by tests.

A future contract-migration task can expose the same behavior with a typed schema and `InteractionDirective`.

---

## 10. Prepared Payload Requirements

When HSN is supplied or safely inherited and the provider accepts it:

- include canonical `gst_hsn_code` in the prepared document payload;
- ensure it is included in the data hashed/bound by the existing approval mechanism;
- include it in the preview only if current preview conventions safely expose normal business fields;
- do not expose internal provider names or implementation details;
- do not mutate the database during prepare.

The approved payload must be exactly what confirmation later uses to construct the Item document, subject to normal Frappe defaults/hooks.

---

## 11. Error / UX Behavior

### 11.1 Missing known requirement

For a known missing HSN/SAC requirement, return the existing `needs_input` style.

The user-facing guidance should be equivalent to:

```text
Provide the HSN/SAC code for this sales Item.
```

It may include accepted lengths when safely known from active settings.

Do not expose:

- Python paths,
- hook function names,
- stack traces,
- SQL/database details,
- approval internals,
- server secrets.

### 11.2 Settings unavailable / inconsistent

If India Compliance appears applicable but required settings cannot be read safely or the environment is inconsistent, do not silently treat HSN as optional.

Return the repository's appropriate safe configuration/unavailable error shape.

Guidance should tell the user that authorized administrator/support assistance is required.

Do not fabricate a default.

### 11.3 Native confirmation error

Do not suppress or bypass native validation errors during `confirm_item`.

Existing safe error mapping may remain responsible for unexpected native failures.

The purpose of this task is to prevent the known HSN missing-input case from reaching confirmation when it can be safely determined earlier.

---

## 12. Allowed Changes

After the mandatory source inspection, the implementation may change only the smallest relevant set of files.

Likely allowed scope:

```text
mcp_erpnext/services/common/creation_contract.py
mcp_erpnext/services/masters/item.py
mcp_erpnext/services/common/<small-effective-requirements-module>.py
mcp_erpnext/services/integrations/<india-compliance-item-provider>.py
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_creation_contract.py
```

If the repository has an established alternative location for integrations/providers, use that instead and document why.

Small test helper/factory changes are allowed when strictly necessary.

Do not broaden this into Customer, Quotation, Sales Order, Supplier, Purchase Order, or unrelated creation flows.

---

## 13. Files / Areas That Must Remain Untouched

Do not change these unless a source-level blocker is proven and documented before modification:

```text
mcp_erpnext/approvals.py
mcp_erpnext/tools/masters/item.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py
mcp_erpnext/settings.py
apps/erpnext/**
apps/india_compliance/**
apps/frappe/**
```

Also do not change:

- GST Settings records,
- Custom Field records,
- Property Setters,
- hooks,
- fixtures,
- migrations,
- profile tool allowlists,
- approval modes,
- identity/authentication behavior.

---

## 14. Explicitly Forbidden Changes

Do not implement any of the following:

```text
if "india_compliance" in installed_apps:
    require_hsn_for_every_item = True
```

Do not:

- make `gst_hsn_code` globally mandatory;
- add arbitrary `extra_fields` input;
- allow generic dynamic key/value assignment;
- evaluate arbitrary Frappe `eval:` strings;
- run `doc.validate()` as a generic prepare-time preflight;
- perform a temporary insert/save/rollback during prepare;
- use `ignore_validate`;
- use `ignore_mandatory`;
- use `ignore_permissions`;
- use `ignore_links`;
- auto-approve after collecting HSN;
- alter approval TTL/ownership/digest policy;
- import India Compliance modules eagerly at MCP module import time;
- duplicate India Compliance tax propagation logic;
- assume a HSN code exists merely because its length is valid;
- trust client-provided app installation state or GST settings.

---

## 15. Implementation Steps

### Step 1 — Reconfirm current source

Trace current:

```text
prepare_item
_item_data
resolve_creation_contract
resolve_contract_values
approvals.create
confirm_item
approval payload construction
```

Record any difference from the audit.

### Step 2 — Freeze internal result shape

Define the smallest explicit internal representation for provider preflight.

It must support:

```text
not applicable
satisfied
missing input
invalid known input
configuration unavailable
resolved provider payload additions
```

Reuse repository conventions rather than inventing a framework.

### Step 3 — Implement generic preflight seam

Add a bounded hook/seam to Item preparation.

Core creation metadata/default behavior must remain unchanged.

Do not make `creation_contract.py` aware of India Compliance by name unless repository architecture makes an isolated provider registry impossible. Prefer separation.

### Step 4 — Implement isolated India Compliance provider

Implement site-installation, metadata, effective sales-state, GST Settings, HSN presence, optional Item Group inheritance, and length guidance checks.

Keep imports lazy/optional.

### Step 5 — Implement provider-owned exact input extraction

Allow only provider-declared exact canonical fields, starting with `gst_hsn_code`.

Do not add generic pass-through fields.

Ensure supplied HSN is resolved/validated through normal metadata-aware behavior where appropriate and included in the final prepared payload.

### Step 6 — Integrate before approval creation

Call preflight only after effective state is known and before `approvals.create`.

If HSN is missing/invalid/config-unavailable:

```text
return without approval
```

If satisfied:

```text
continue existing ready + approval flow
```

### Step 7 — Keep confirmation unchanged

Verify by source diff and tests that `confirm_item` still uses the existing normal insert path and no validation bypass was introduced.

### Step 8 — Add tests

Add focused unit/service tests for every required behavior matrix row.

### Step 9 — Run full relevant regression tests

Run the Item tests plus all tests touching shared creation-contract logic.

If shared creation helper code changes, also run Customer creation tests because Customer currently uses that common helper.

### Step 10 — Produce implementation report

Create a report under the repository's existing docs/results/report convention.

Suggested filename:

```text
ITEM_CREATION_CONDITIONAL_RUNTIME_REQUIREMENTS_IMPLEMENTATION_REPORT.md
```

Use the actual existing documentation folder convention after inspection.

---

## 16. Required Test Matrix

At minimum implement and run these tests.

### T1 — ERPNext-only / provider absent

Given India Compliance is not installed:

Expected:

```text
prepare_item uses existing metadata/default flow
no HSN requirement
no India Compliance import failure
ready/needs_input behavior otherwise unchanged
```

### T2 — India Compliance installed, HSN validation disabled

Expected:

```text
no HSN requirement from this provider
existing Item preparation continues
```

### T3 — Installed + validation enabled + sales Item + missing HSN

Expected:

```text
prepare_item -> needs_input
missing field is gst_hsn_code / HSN-SAC
approvals.create is NOT called
```

### T4 — Continuation with supplied HSN

First call:

```text
prepare_item -> needs_input(gst_hsn_code)
```

Second call with exact HSN input:

```text
prepare_item -> ready
prepared payload contains gst_hsn_code
approval digest/payload contains gst_hsn_code
```

### T5 — Accepted HSN length

For active minimum 6:

```text
6-digit and 8-digit values pass preflight length guidance
```

Final native Link validation is not mocked away.

### T6 — Invalid HSN length

For active minimum 6:

```text
4-digit input -> actionable invalid-input / needs_input style result
no approval created
```

Use the existing error/result convention.

### T7 — Non-sales effective Item

When provider is tested against `is_sales_item=0`:

Expected:

```text
HSN not required by this rule
```

Even though current sales Item creation policy normally fixes it to 1, unit-test the provider boundary independently.

### T8 — Safe Item Group inheritance

When Item Group provides a valid `gst_hsn_code` and it can be safely read:

Expected:

```text
preflight considers the HSN satisfied
prepared payload carries the effective HSN if needed by the implementation
final confirmation still performs native validation
```

### T9 — Item Group HSN unavailable/uncertain

Expected:

```text
preflight does not falsely treat HSN as satisfied
```

### T10 — Settings unavailable

Expected:

```text
no silent disablement
safe configuration/unavailable result
no approval created
no internal traceback leaked in public result
```

### T11 — Existing core required fields

Existing static metadata-required field behavior must remain unchanged.

### T12 — Duplicate Item behavior

Existing permission-aware duplicate check must remain unchanged.

### T13 — Permission behavior

Existing Item create permission checks must remain unchanged.

### T14 — Confirmation flags

Assert confirmation still uses:

```text
ignore_permissions=False
ignore_links=False
ignore_mandatory=False
```

### T15 — Approval ownership/security

Provider logic must not allow:

- direct `confirm=true` self-authorization,
- approval reuse,
- approval from another site/user,
- payload mutation after approval.

Existing tests should continue to pass.

### T16 — Unknown extra input rejected/ignored safely

A random unknown field supplied inside the legacy Item request must not become document payload merely because provider support was added.

### T17 — Provider-owned field unavailable in metadata

If `gst_hsn_code` is not present in current merged Item metadata:

Expected:

```text
no mass assignment
no document payload injection
provider does not assume the field exists
```

### T18 — Shared creation regression

If `creation_contract.py` changes, existing Customer creation tests must pass unchanged.

---

## 17. Acceptance Criteria

Task is complete only when all of the following are true:

1. Existing `prepare_item -> ready -> approval -> confirm_item` flow remains intact.
2. ERPNext-only site behavior is unchanged.
3. No eager India Compliance import exists on ERPNext-only startup.
4. Installation alone does not make HSN required.
5. HSN validation disabled means `prepare_item` does not ask for HSN because of this provider.
6. Validation enabled + effective sales Item + missing HSN returns pre-approval `needs_input`.
7. Missing HSN path does not call `approvals.create`.
8. Caller can provide the exact HSN field on a subsequent `prepare_item` call.
9. That HSN becomes part of the exact prepared/approved payload.
10. No arbitrary field pass-through was introduced.
11. Invalid HSN length is proactively actionable only when active settings are safely known.
12. Item Group inheritance is handled conservatively and safely.
13. Final HSN Link validity is still enforced by Frappe.
14. India Compliance tax propagation remains only in India Compliance.
15. `confirm_item` still uses native Frappe insert with no bypass flags.
16. Approval logic is unchanged.
17. Existing Item regression tests pass.
18. Shared creation/Customer tests pass if common creation code changed.
19. No ERPNext, Frappe, India Compliance, GST Settings, hooks, migration, fixture, profile, identity, or approval-policy change was made.
20. Implementation report documents exact files changed, behavior, tests, results, and remaining boundaries.

---

## 18. Expected Runtime Behavior

### Case A — ERPNext only

```text
User: create sales Item X
MCP: normal existing required inputs / preview
MCP: ready
approval
confirm
Frappe insert
```

No HSN-specific behavior.

### Case B — India Compliance installed but HSN validation off

```text
User: create sales Item X
MCP: normal existing flow
```

No HSN question from this rule.

### Case C — India Compliance active, validation on, HSN missing

```text
User: create sales Item X
MCP prepare_item:
    needs_input -> HSN/SAC Code
    no approval created

User provides HSN
MCP prepare_item:
    preflight satisfied
    ready preview
    approval created over complete payload

User explicitly approves
MCP confirm_item:
    normal Frappe insert
    India Compliance validator runs normally
```

### Case D — India Compliance active, invalid HSN length

```text
prepare_item
    -> actionable input correction
    -> no approval
```

Native validation still remains authoritative later.

---

## 19. Known Boundaries

This task intentionally does NOT solve all dynamic validation in Frappe.

Out of scope:

- generic interpretation of all `mandatory_depends_on` fields;
- arbitrary app hook introspection;
- executing controller validation during prepare;
- dynamically generating MCP schemas from installed apps;
- purchase Item creation;
- HSN creation/master management;
- GST tax-table management;
- typed migration of legacy `prepare_item` / `confirm_item`;
- Quotation or Sales Order conditional-requirement changes;
- generic rule-provider plugin marketplace;
- auto-retry after confirm failure;
- redesigning approval consumption semantics.

Future optional-app rules must be added only when individually source-confirmed and worth collecting before approval.

---

## 20. Implementation Report Requirements

The agent must produce a Markdown implementation report containing:

1. inspected source files and relevant existing patterns;
2. any source differences from the audit;
3. final architecture actually implemented;
4. exact files added/modified;
5. why each file changed;
6. exact provider applicability logic;
7. exact handling of `gst_hsn_code` input continuation;
8. confirmation that arbitrary fields are still blocked;
9. confirmation that approval logic was not changed;
10. confirmation that `confirm_item` native insert path remains unchanged;
11. tests added;
12. commands/tests run;
13. pass/fail results;
14. any test not run and why;
15. limitations / remaining risks;
16. exact recommended next task.

Do not report the task as complete if required tests fail.

---

## 21. Expected Result

After this task, the known HSN/SAC failure should move from a late confirmation-time surprise to an earlier conversational preparation requirement when the rule is actually active.

Before:

```text
prepare_item -> ready -> approval -> confirm_item -> HSN MandatoryError
```

After:

```text
prepare_item
    -> effective requirement detects missing HSN
    -> needs_input
    -> user supplies HSN
    -> prepare_item ready
    -> approval
    -> confirm_item
    -> normal native validation/write
```

On an ERPNext-only site or an India Compliance site with HSN validation disabled:

```text
existing behavior remains unchanged
```

---

## 22. Exact Next Task After Completion

Do not automatically implement the next task.

After this implementation is complete and the report is reviewed, the next decision should be:

```text
Task 24 — Item Creation Contract Migration Review
```

Purpose:

Review whether the frozen legacy `prepare_item` / `confirm_item` raw-dictionary contracts should now be migrated to the project's typed MCP tool contract standard, using the shared `InteractionDirective` for `needs_input` / approval continuation without changing the business behavior implemented in Task 23.

Task 24 is a review/design task first, not an automatic implementation.

