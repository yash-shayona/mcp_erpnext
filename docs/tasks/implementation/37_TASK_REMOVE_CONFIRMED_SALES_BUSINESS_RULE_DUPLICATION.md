# Task 37 — Remove Confirmed Sales Business-Rule Duplication

## Status

**Type:** Focused implementation/refactor task  
**Project:** `mcp_erpnext`  
**Depends on:** Task 36 — Frappe / ERPNext Authority Duplication Audit  
**Scope:** Only the two confirmed duplications identified by the audit  
**Purchase profile:** Must remain unchanged  
**Other possible-duplication findings:** Explicitly out of scope

---

# 1. Objective

Remove or simplify the two confirmed MCP-side copies of ERPNext business rules so that Frappe/ERPNext remains authoritative.

The two confirmed duplications are:

1. Sales Invoice direct prerequisite logic in:

```text
mcp_erpnext/services/selling/sales_invoice.py
_direct_invoice_policy()
```

2. Quotation `valid_till` ordering logic in:

```text
mcp_erpnext/services/selling/quotation.py
prepare_quotation()
```

The implementation must preserve the useful MCP interaction behavior:

- missing-input handling,
- bounded preview,
- approval,
- typed public results,
- safe errors,
- final native persistence,

while removing independent copies of ERPNext business truth.

---

# 2. Architectural Rule

Use this rule throughout the task:

```text
MCP may prepare, explain, preview, and adapt.
Frappe / ERPNext decides business validity.
```

Do not move a duplicated rule into another MCP helper under a new name.

Do not replace a duplicate with another static mirror.

If native validation can safely provide the answer during prepare, use it.

If full native validation is not safe during prepare because of hooks or side effects:

1. inspect for a stable side-effect-free native helper/seam;
2. use that helper if appropriate;
3. otherwise retain only a clearly documented MCP readiness boundary that does not claim to be the final ERP business authority.

---

# 3. Exact Scope

## 3.1 Sales Invoice

Inspect and refactor:

```text
mcp_erpnext/services/selling/sales_invoice.py
_direct_invoice_policy()
```

The audit found that it duplicates ERPNext Sales Invoice prerequisite logic including:

- Selling Settings `so_required`,
- Selling Settings `dn_required`,
- Customer-level exceptions,
- prerequisite decisions already enforced by native Sales Invoice validation.

ERPNext's native Sales Invoice validation must remain authoritative.

## 3.2 Quotation

Inspect and refactor the prepare-time rule that independently rejects:

```text
valid_till < transaction_date
```

ERPNext Quotation controller already owns this validation through its native validation path.

The MCP should no longer maintain the same comparison independently as business truth.

---

# 4. Inputs / Dependencies

Before changing code, inspect:

## Project code

- `mcp_erpnext/services/selling/sales_invoice.py`
- `mcp_erpnext/services/selling/quotation.py`
- related contracts/wrappers only as needed
- related tests
- Task 36 audit report

## Installed ERPNext source

Verify current installed/native behavior for:

- Sales Invoice `validate()`
- `so_dn_required()`
- Customer exception handling
- Sales Order / Delivery Note prerequisite behavior
- return/POS exclusions
- Quotation `validate()`
- Quotation `validate_valid_till()`

## Runtime / official-app interaction

Check whether invoking the chosen native validation path during prepare:

- persists anything,
- queues jobs,
- sends notifications,
- mutates linked documents,
- triggers unsafe India Compliance behavior,
- or otherwise creates side effects.

Use read-only/source-level inspection first.

---

# 5. Allowed Changes

Prefer the smallest possible change set.

Allowed files include:

- `mcp_erpnext/services/selling/sales_invoice.py`
- `mcp_erpnext/services/selling/quotation.py`
- focused Sales Invoice tests
- focused Quotation tests
- shared test fixtures only if needed
- implementation report

Only touch contracts/wrappers if the existing bounded result model cannot represent the native-validation-derived outcome cleanly.

Do not broaden the task merely to clean up nearby code.

---

# 6. Files / Areas Not to Change

Do not change:

- Sales/Purchase profile registration
- lifecycle allowlists
- generic update/child-add architecture
- approval storage
- approval modes
- identity
- Customer creation
- Item creation
- GST bridge
- HSN/SAC bridge
- Sales Order creation behavior
- Purchase Order behavior
- conversion tools
- PDF
- email
- reads
- queries
- aggregates
- database schema
- Frappe core
- ERPNext core
- India Compliance core

---

# 7. Sales Invoice Refactor Requirements

## 7.1 Remove independent business-rule authority

The MCP must no longer independently decide the Sales Invoice prerequisite rule by reconstructing ERPNext logic from:

- Selling Settings,
- Customer exception values,
- copied prerequisite conditions.

If `_direct_invoice_policy()` becomes unnecessary, remove it.

If part of it remains useful for MCP response shaping, it must not independently decide ERP validity.

## 7.2 Native-validation-backed behavior

Prefer a flow conceptually like:

```text
build unsaved Sales Invoice using existing MCP inputs
    ↓
apply normal native defaults / preparation
    ↓
run a safe native ERPNext validation seam
    ↓
ERPNext decides prerequisite validity
    ↓
MCP maps result into bounded blocked/ready response
```

Do not persist during prepare.

## 7.3 Preserve useful MCP interaction

When ERPNext rejects a direct Sales Invoice because a Sales Order or Delivery Note is required:

- return a stable MCP error/status,
- do not leak traceback/internal details,
- keep the response useful to the agent,
- do not expose raw ERPNext internals unnecessarily.

If a stable code already exists, preserve it where reasonable.

If wording changes because the native source becomes authoritative, tests should assert stable MCP semantics rather than fragile exact native text.

## 7.4 Required Sales Invoice cases

Cover at least:

- no SO/DN requirement
- SO required
- DN required
- Customer exception disables the general prerequisite
- item-level prerequisite behavior where ERPNext applies it
- return behavior
- POS behavior
- valid standalone Sales Invoice path
- permission failure
- native validation failure
- final insert still uses native Frappe persistence

Do not guess these cases from memory; derive them from installed ERPNext source.

---

# 8. Quotation Refactor Requirements

## 8.1 Remove duplicate comparison

Remove the MCP-owned final business decision equivalent to:

```text
valid_till < transaction_date
```

The native Quotation controller validation must own that rule.

## 8.2 Preserve prepare-time usefulness

The MCP still needs a clean prepare result.

Preferred flow:

```text
build unsaved Quotation
    ↓
apply current defaults/resolution
    ↓
run safe native validation / native validation seam
    ↓
native invalid-valid_till result
    ↓
map to bounded MCP error
```

Do not persist during prepare.

## 8.3 Required Quotation cases

Cover:

- `valid_till` after transaction date
- same date
- before transaction date
- omitted `valid_till` if supported by current contract/default behavior
- other native Quotation validation errors remain correctly surfaced
- permission behavior unchanged
- final insert still uses native validation and persistence

---

# 9. Prepare-Time Safety Requirement

This is the most important implementation constraint.

Do not simply call a broad controller validation method without checking side effects.

Before selecting the native path, inspect:

- Frappe controller lifecycle behavior,
- ERPNext controller methods invoked,
- official-app hooks,
- any database writes,
- queue/enqueue behavior,
- external calls,
- mutations outside the unsaved document.

The selected preparation path must be safe and non-persisting.

If the full native method is not safe:

- find a narrower authoritative native helper, or
- document why a narrow MCP readiness preflight must temporarily remain.

But do not re-copy the complete ERPNext rule.

---

# 10. Error Contract

Native validation remains authoritative, but the MCP owns public response shaping.

The final MCP behavior should follow:

```text
native validation/result
    ↓
classify safely
    ↓
stable MCP code/status
    ↓
bounded client-neutral message
```

Do not:

- expose traceback,
- expose SQL/database internals,
- expose internal Frappe stack details,
- silently override ERPNext's rejection,
- force persistence after a native failure.

---

# 11. Tests

Run focused tests first, then the full suite.

## 11.1 Quotation focused tests

Verify:

- valid date accepted
- same date accepted where native ERPNext allows it
- invalid date rejected by native-backed path
- MCP no longer independently owns the comparison
- stable bounded error returned
- final insert remains native

## 11.2 Sales Invoice focused tests

Verify:

- SO requirement
- DN requirement
- Customer exception behavior
- item-level prerequisite behavior
- return/POS exclusions
- valid standalone invoice
- native permission failure
- native validation error mapping
- no duplicate custom business-rule decision remains

## 11.3 Regression

Run:

- existing Quotation tests
- existing Sales Invoice tests
- conversion tests
- Customer/Item tests
- Purchase tests
- lifecycle tests
- contract tests
- full app test suite
- tool catalog check if project workflow requires it
- compile/static checks used by the project

Purchase behavior must remain unchanged.

---

# 12. Acceptance Criteria

Task is complete only when:

- [ ] `_direct_invoice_policy()` no longer independently mirrors ERPNext Sales Invoice prerequisite business truth.
- [ ] Quotation prepare no longer independently owns the `valid_till` ordering business rule.
- [ ] Native ERPNext/Frappe validation is authoritative for both cases.
- [ ] Prepare remains non-persisting.
- [ ] Chosen native validation path has been checked for prepare-time side effects.
- [ ] MCP still returns bounded, stable, client-neutral responses.
- [ ] Existing approval flow is unchanged.
- [ ] Existing entity resolution is unchanged.
- [ ] Existing runtime defaults are unchanged except where directly required by this refactor.
- [ ] Final persistence still uses normal Frappe Document APIs with permissions enabled.
- [ ] No Purchase behavior changed.
- [ ] No profile/registry/lifecycle redesign was introduced.
- [ ] Focused tests pass.
- [ ] Full app suite passes.
- [ ] Implementation report is created.

---

# 13. Expected Result

Before:

```text
MCP copies ERPNext business rule
    ↓
MCP decides
    ↓
ERPNext later decides again
```

After:

```text
MCP prepares safe unsaved document
    ↓
ERPNext/native validation decides
    ↓
MCP adapts result
    ↓
approval
    ↓
native final persistence
```

The MCP should become thinner without losing its conversational/safety value.

---

# 14. Known Limitations / Boundaries

This task does not decide:

- Item HSN preflight redesign
- commercial-default list simplification
- Sales Order delivery-date default/refactor
- field-type strategy catalog cleanup
- generic update architecture
- lifecycle policy redesign
- shared approval persistence
- Customer/Item update design
- Purchase redesign

Those remain separate follow-up topics.

---

# 15. Required Implementation Report

Create:

```text
CONFIRMED_SALES_BUSINESS_RULE_DUPLICATION_REMOVAL_IMPLEMENTATION_REPORT.md
```

The report must include:

1. Exact code inspected
2. Exact duplicate rules removed/simplified
3. Native ERPNext/Frappe authority used instead
4. Prepare-time side-effect analysis
5. Final Sales Invoice flow
6. Final Quotation flow
7. Error-response mapping
8. Files changed
9. Tests run and exact results
10. Purchase regression result
11. Any behavior difference discovered
12. Remaining possible-duplication items
13. Exact recommended next task

---

# 16. Exact Next Task After Completion

Do not implement the possible-duplication items inside this task.

After this task is complete and reviewed, choose the next focused audit/refactor from the remaining Task 36 findings, such as:

- Item HSN preflight compatibility
- commercial/default readiness lists
- Sales Order delivery-date default/rejection
- field-type strategy catalog

The next task must be selected from implementation evidence, not pre-frozen in advance.
