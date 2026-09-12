# Task 36 — Frappe / ERPNext Authority Duplication Audit

## Status

**Type:** Architecture / inspection audit only  
**Implementation changes:** NOT allowed in this task  
**Project:** `mcp_erpnext`  
**Primary question:** Is the MCP server acting as a thin bridge to Frappe/ERPNext, or are we duplicating framework/ERP business authority in custom MCP logic?

> This task supersedes the previously drafted implementation-oriented Task 36.
> Do not implement Sales mutation hardening until this audit is reviewed.

---

# 1. Objective

Inspect the **entire current `mcp_erpnext` project** and identify every place where the MCP server may be duplicating, re-implementing, hard-coding, or second-guessing logic that Frappe/ERPNext already owns.

The desired architectural principle is:

```text
LLM / MCP Client
      ↓
MCP Server
      ↓
resolve intent / entity / missing input
preview / approval / response shaping
      ↓
Frappe / ERPNext
      ↓
metadata
permissions
document state
validation
business rules
controller hooks
link rules
transactions
persistence
      ↓
result / error
      ↓
MCP converts result into a bounded client-neutral response
```

The audit must determine whether the current code follows this principle consistently.

Do not assume that existing custom logic is wrong.

Do not assume that all custom logic should be removed.

Classify each piece of logic based on **who should be authoritative**.

---

# 2. Core Architectural Principle to Evaluate

Use this question repeatedly:

> **Does Frappe/ERPNext already know how to decide this correctly at runtime?**

If **yes**, then the MCP should normally:

- call/use the authoritative Frappe/ERPNext API or metadata,
- preserve native validation and permission behavior,
- avoid maintaining a second independent copy of the same rule.

If **no**, because it is an MCP/client/orchestration concern, then custom MCP logic may be valid.

Examples of valid MCP concerns:

- profile/tool exposure,
- Sales vs Purchase MCP surface,
- identity hand-off into Frappe user context,
- entity resolution/disambiguation,
- asking for missing information,
- preview generation,
- human/agent approval flow,
- approval token handling,
- MCP contract typing,
- response shaping,
- error normalization/sanitization,
- data minimization,
- model-facing schemas,
- tool naming,
- observability,
- client-neutral interaction directives.

These are **not** considered duplication merely because they are custom.

---

# 3. Important Boundary — MCP Profile Scope Is Our Rule

Do not remove the concept of MCP profiles.

For example:

```text
MCP_PROFILE=sales
MCP_PROFILE=purchase
```

is an intentional MCP product boundary.

Frappe does not decide:

> which tools a particular MCP endpoint should expose to an LLM.

Therefore profile-specific public exposure may remain custom.

The audit must distinguish:

```text
VALID MCP SCOPE RULE
Sales MCP exposes selected Sales-domain capabilities
```

from:

```text
POSSIBLE DUPLICATION
MCP separately hard-codes that a DocType is submittable
when Frappe metadata already knows that
```

---

# 4. Scope

Inspect the entire current project, not only Sales Order or Quotation.

At minimum inspect:

## Profiles

- Sales
- Purchase

Purchase must be inspected only to understand shared architecture and duplication patterns.

This audit does **not** authorize a Purchase redesign.

## Main business DocTypes currently exposed

At minimum:

- Customer
- Item
- Quotation
- Sales Order
- Sales Invoice
- Supplier
- Purchase Order

Also include any additional DocType discovered in public tools, policies, shared services, conversions, or configuration.

## Operation families

Inspect:

- create
- read/get
- query
- aggregate
- update
- child-row mutation
- submit
- cancel
- delete
- convert/map
- PDF
- email
- resolve/search
- metadata-driven required fields
- India Compliance bridges
- permissions
- approval
- identity/runtime context
- error handling

---

# 5. What Counts as Possible Duplication

Search specifically for code/config that independently reproduces framework or ERP knowledge.

Examples include, but are not limited to:

## 5.1 Static DocType lifecycle knowledge

Look for custom lists/maps such as:

```text
SUBMITTABLE_DOCTYPES
CANCELLABLE_DOCTYPES
DELETABLE_DOCTYPES
```

or equivalent action allowlists.

Determine whether they represent:

### A. valid MCP exposure boundary

Example:

```text
Sales profile is allowed to address these DocTypes
```

or:

### B. duplicated Frappe capability truth

Example:

```text
Quotation is submittable
Customer is not submittable
```

when runtime metadata already provides `is_submittable`.

Do not collapse these two concepts.

---

## 5.2 Static field knowledge

Look for:

- manually duplicated field existence checks,
- manually copied ERPNext field lists,
- hard-coded mandatory fields that runtime metadata already provides,
- hard-coded field types,
- hard-coded `read_only`,
- hard-coded `allow_on_submit`,
- static Link/Select definitions that metadata already exposes.

Classify whether each list is:

- intentional narrow MCP product policy,
- necessary typed public contract,
- performance/cache optimization,
- or duplicated framework metadata.

---

## 5.3 Permission logic

Inspect every custom permission check.

Determine whether code:

### Correctly delegates to Frappe

Examples:

```text
doc.check_permission(...)
frappe.has_permission(...)
normal doc.insert/save/submit/cancel/delete
```

or:

### Reimplements permission rules

Examples:

- custom role-name checks,
- custom user-role matrices,
- custom ownership logic,
- custom write/submit/cancel/delete authorization independent of Frappe.

MCP may perform early permission checks for better UX, but the authority should remain Frappe.

Document both:

- early delegated check,
- final native enforcement.

---

## 5.4 Lifecycle state rules

Inspect custom checks for:

- Draft,
- Submitted,
- Cancelled,
- `docstatus`,
- `is_submittable`,
- allow-on-submit,
- cancel eligibility,
- delete eligibility.

Determine whether each is:

- required MCP preflight,
- direct delegation to Frappe metadata/state,
- or duplicated lifecycle business logic.

---

## 5.5 Validation rules

Inspect custom validation for:

- mandatory fields,
- numeric ranges,
- Link existence,
- Select membership,
- duplicate rows,
- UOM,
- warehouse,
- delivery date,
- tax,
- totals,
- stock/accounting behavior,
- GST,
- HSN/SAC.

Determine whether the MCP:

1. validates only model-facing contract shape,
2. delegates business validation to Frappe/ERPNext,
3. or duplicates ERPNext controller/service logic.

---

## 5.6 Calculations and defaults

Search for custom calculations/defaults that Frappe/ERPNext can already provide.

Examples:

- amount = qty × rate,
- taxes,
- net totals,
- grand totals,
- UOM conversion,
- pricing,
- warehouse defaults,
- delivery defaults,
- account defaults,
- tax templates,
- stock implications.

The desired rule is generally:

> prefer normal ERPNext document/controller/defaulting/calculation paths.

Any custom duplicate must be justified.

---

## 5.7 Link/dependency rules

Inspect whether the MCP manually determines:

- whether a linked document blocks deletion,
- whether cancel is allowed,
- whether source/target references are valid.

Determine whether the code uses native Frappe/ERPNext mechanisms or duplicates them.

---

## 5.8 Create requirements

Inspect `resolve_creation_contract`, metadata/default resolution, effective requirements, and master configs.

For Customer, Item, Quotation, Sales Order, Sales Invoice, Supplier, Purchase Order:

- what comes from runtime metadata?
- what comes from MCP config?
- what comes from ERP business services?
- what is intentionally narrowed for MCP?
- what is duplicated?

Do not assume static config is wrong; identify its purpose.

---

## 5.9 Update logic

Inspect generic and explicit update mechanics.

Determine:

- what metadata already validates,
- what normal `doc.save()` validates,
- what field restrictions are MCP product policy,
- what restrictions duplicate Frappe capability,
- whether arbitrary field/value exposure is a model-interface issue rather than an ERP validation issue.

Do not design the replacement implementation in this audit.

---

## 5.10 Delete logic

Inspect delete handling carefully.

Separate:

```text
Can this DocType technically be deleted in Frappe?
```

from:

```text
Should this MCP profile expose delete for this DocType?
```

Do not infer delete eligibility from `is_submittable`.

Verify whether native:

- delete permission,
- linked-document rules,
- cancel-before-delete behavior,
- hooks,
- dependency checks

are already authoritative.

---

# 6. Native Persistence Boundary Audit

Inspect every business write path.

Classify persistence calls.

Preferred normal business mutation path should generally be through normal Document APIs such as:

```text
doc.insert()
doc.save()
doc.submit()
doc.cancel()
doc.delete()
```

or official ERPNext mapping/service APIs where appropriate.

Identify any use of:

```text
frappe.db.set_value()
doc.db_update()
direct SQL
frappe.db.sql(...)
ignore_permissions=True
```

in business mutation paths.

For each occurrence determine:

- why it exists,
- whether it bypasses controller validation/hooks,
- whether it is safe/intentional,
- whether it should be replaced by normal authoritative Frappe execution.

Do not change code in this task.

---

# 7. Metadata Authority Audit

Inspect use of:

```text
frappe.get_meta(...)
doc.meta
DocField metadata
runtime custom fields
property setters
is_submittable
mandatory
fieldtype
options
read_only
allow_on_submit
```

Determine where runtime metadata is already authoritative.

Identify any custom duplicated copy that can drift from:

- custom fields,
- property setters,
- installed apps,
- India Compliance,
- site configuration,
- future ERPNext upgrades.

Explicitly document site/runtime sensitivity.

---

# 8. ERPNext Controller / Business-Service Authority Audit

For each major transaction:

- Quotation
- Sales Order
- Sales Invoice
- Purchase Order

inspect whether the MCP reuses native ERPNext:

- controllers,
- mapper functions,
- defaulting,
- calculation,
- validation,
- transaction methods.

Identify any custom business-rule reproduction.

For conversion tools inspect specifically:

- Quotation → Sales Order
- Sales Order → Sales Invoice
- any Purchase conversion if present.

Preferred pattern:

```text
MCP resolves/approves
→ official ERPNext mapper/business path
→ native validation
→ native persistence
```

---

# 9. India Compliance / Official App Integration Audit

Inspect:

- Customer GST integration
- Item HSN/SAC integration
- any other India Compliance hooks/bridges

Determine whether the MCP:

- delegates to India Compliance/Frappe behavior,
- conditionally detects installed app behavior,
- or duplicates India Compliance validation/business logic.

The preferred architecture is:

```text
official app installed
→ use/allow its native behavior

official app absent
→ normal ERPNext/Frappe behavior
```

Do not create a hard dependency unless already required.

---

# 10. MCP-Specific Logic That Should Probably Remain

The report must explicitly identify valid custom logic so the audit does not become “remove all custom code.”

At minimum evaluate and likely preserve where correct:

## 10.1 Profile exposure

- Sales vs Purchase tool exposure
- intentional feature scope

## 10.2 Identity bridge

- shared secret / trusted user email
- mapping request to real Frappe user
- fail-closed identity behavior

## 10.3 Entity resolution

- search
- ambiguity handling
- resolved references
- permission-aware resolution

## 10.4 Conversational interaction

- missing input
- selection
- approval
- `InteractionDirective`

## 10.5 Approval layer

- prepare/confirm
- opaque token
- action/site/user/payload binding
- trusted-human / agent-delegated server mode
- single-use/replay protection

Approval is an MCP/LLM safety concern, not Frappe business-rule duplication.

## 10.6 Public typed contracts

Typed MCP schemas may intentionally be narrower than the full DocType.

This is a valid model-facing/data-minimization boundary.

The audit must distinguish:

```text
narrow public MCP schema
```

from:

```text
reimplementation of ERPNext business validation
```

## 10.7 Response shaping

- bounded previews
- structured errors
- sanitization
- no traceback/internal secrets
- no unnecessary business-data leakage

---

# 11. Error-Handling Audit

Inspect how Frappe/ERPNext exceptions are handled.

For errors such as:

- PermissionError
- ValidationError
- MandatoryError
- LinkValidationError
- DuplicateEntryError
- DoesNotExistError
- submitted/cancelled state errors

determine whether MCP:

### Good pattern

```text
Frappe decides
→ MCP catches/classifies
→ safe structured response
```

or:

### Bad pattern

```text
Frappe rejects
→ MCP applies alternate custom business logic
→ bypass/force behavior
```

Identify any place where MCP changes business meaning rather than only adapting the response.

---

# 12. Mandatory Code Search

Search the full project for patterns that may indicate duplicated authority.

At minimum search for:

```text
is_submittable
docstatus
allow_on_submit
mandatory
reqd
read_only
fieldtype
has_permission
check_permission
get_permissions
roles
frappe.session.user
ignore_permissions
frappe.db.set_value
db_update
frappe.db.sql
delete_doc
doc.delete
doc.save
doc.insert
doc.submit
doc.cancel
get_meta
meta.get_field
ValidationError
PermissionError
LinkValidationError
MandatoryError
DuplicateEntryError
```

Also search for project-specific constants/maps containing:

```text
ALLOWED
DENIED
TARGETS
DOCTYPES
FIELDS
LIFECYCLE
UPDATE
SUBMIT
CANCEL
DELETE
CHILD
REQUIRED
```

Do not label a constant as duplication only because it is static.

Inspect its purpose and authority.

---

# 13. Mandatory Authority Classification

For every meaningful rule discovered, classify it into exactly one of these categories:

## A. Frappe/ERPNext Authority — delegated correctly

Example:

```text
doc.check_permission("write")
doc.save()
doc.meta.is_submittable
```

## B. Valid MCP Product Boundary

Example:

```text
Sales profile does not expose Purchase Order tools
```

## C. Valid MCP Interaction/Safety Logic

Example:

```text
prepare → approval → confirm
```

## D. Valid MCP Data-Minimization / Contract Policy

Example:

```text
model only sees the fields required by this MCP capability
```

## E. Possible Duplication — review needed

Custom logic appears to reproduce framework/ERP truth.

## F. Confirmed Duplication — should be removed/simplified

Same rule is independently maintained while Frappe/ERPNext already provides authoritative runtime behavior.

## G. Intentional Business Restriction

A narrower MCP rule exists by deliberate product decision even though Frappe permits more.

This category requires a documented reason.

---

# 14. Required Duplication Inventory Table

Produce a table like:

| Area | File / Symbol | Current custom rule | Existing Frappe/ERP authority | Classification | Risk | Recommendation |
|---|---|---|---|---|---|---|

Examples of risk:

- drift after ERPNext upgrade
- custom field incompatibility
- property setter incompatibility
- India Compliance divergence
- duplicate permission logic
- duplicate state machine
- unnecessary code
- no meaningful risk / valid MCP boundary

Every recommendation must cite exact code evidence.

---

# 15. Required Operation-by-Operation Review

For each operation family, state **who should decide what**.

## Create

Separate:

- MCP input collection
- Frappe metadata requirements
- ERPNext defaults/calculation
- permissions
- persistence

## Update

Separate:

- MCP target/field/value input
- model-facing field exposure
- metadata field existence/type
- permission
- controller validation
- final save

## Submit

Separate:

- profile exposure
- `is_submittable`
- submit permission
- docstatus/state
- native submit

## Cancel

Separate:

- profile exposure
- submittable metadata
- submitted state
- cancel permission
- linked dependencies
- native cancel

## Delete

Separate:

- profile exposure
- delete permission
- dependency/link checks
- submitted document handling
- native delete

## Child-row mutation

Separate:

- MCP business input
- child metadata
- Item resolution
- defaults
- calculations
- validation
- save

## Convert

Separate:

- MCP source/target resolution
- approval
- official ERPNext mapper
- final insert

---

# 16. Required Profile-Boundary Review

For Sales and Purchase separately document:

```text
Which rules exist because of MCP profile scope?
Which rules duplicate Frappe capability?
```

Do not recommend eliminating profile allowlists merely to become more dynamic.

Profile boundaries are security/product exposure controls.

The audit should instead identify whether a single rule is currently doing two jobs:

```text
MCP exposure boundary
+
ERP capability truth
```

If so, recommend separating those concerns.

---

# 17. Required Thin-Bridge Target Architecture

The report must propose a final conceptual architecture based on evidence.

Target principle should resemble:

```text
Public MCP tool
    ↓
typed/minimized request
    ↓
identity context
    ↓
entity resolution
    ↓
optional early Frappe permission/meta preflight
    ↓
preview / approval
    ↓
normal Frappe/ERPNext operation
    ↓
native result/error
    ↓
safe structured MCP result
```

For each layer specify:

- what MCP owns,
- what Frappe owns,
- what ERPNext owns,
- what official app owns.

---

# 18. No Implementation Changes Allowed

This audit must not:

- add tools,
- remove tools,
- rename tools,
- change profile registrations,
- change allowlists,
- change contracts,
- change services,
- change permissions,
- change lifecycle behavior,
- change Customer/Item/Sales transaction behavior,
- change Purchase behavior,
- change approval storage,
- modify ERPNext/Frappe core,
- mutate business data.

Only an audit report/document may be added.

---

# 19. Allowed Output

Create one review report following the current repository convention.

Suggested filename:

```text
docs/reviews/FRAPPE_ERP_AUTHORITY_DUPLICATION_AUDIT_REPORT.md
```

If an existing reports/reviews directory convention exists, follow it.

Do not create unnecessary folder structures.

---

# 20. Required Report Structure

The final report must include:

1. Executive summary
2. Architecture principle evaluated
3. Repository areas inspected
4. Complete MCP-specific responsibility inventory
5. Complete Frappe/ERPNext authority inventory
6. Duplication search methodology
7. Duplication inventory table
8. Profile-boundary analysis
9. Metadata duplication findings
10. Permission duplication findings
11. Lifecycle duplication findings
12. Validation duplication findings
13. Calculation/default duplication findings
14. Link/dependency duplication findings
15. Persistence/API bypass findings
16. India Compliance / official-app findings
17. Error-handling findings
18. Per-operation authority matrix
19. Valid custom MCP logic that should remain
20. Confirmed duplication that should be removed/simplified
21. Possible duplication needing a business decision
22. Thin-bridge target architecture
23. Migration risks
24. What should NOT change
25. Exact next implementation/refactor task
26. Acceptance checklist

Every important conclusion must point to:

- project file,
- symbol/function/class,
- and official Frappe/ERPNext/official-app evidence where material.

---

# 21. Required Authority Matrix

Produce a matrix similar to:

| Concern | MCP | Frappe Framework | ERPNext / Official App |
|---|---|---|---|
| Profile exposure | Authoritative | — | — |
| Identity handoff | Bridge | User/permission authority | — |
| Entity disambiguation | Authoritative interaction concern | Permission-aware data source | — |
| Field metadata | Consumer | Authoritative | ERPNext defines fields/controllers |
| Required fields | Interaction helper only | Authoritative metadata | ERPNext/official app requirements |
| Permissions | Must not duplicate | Authoritative | controller permission hooks may contribute |
| Validation | Public input shape only | Document validation lifecycle | Business validation authoritative |
| Submitability | Must not duplicate | `is_submittable`/lifecycle authority | DocType definition |
| Calculations/defaults | Must not duplicate | execution framework | ERP business authority |
| Approval | Authoritative MCP safety layer | — | — |
| Persistence | Calls native API | Authoritative transaction/document layer | controller behavior |
| Error presentation | Authoritative adaptation | Source error | Source business error |

Adjust based on actual evidence.

---

# 22. Verification

Run safe non-mutating checks only.

Examples:

- full existing test suite,
- contract audit,
- tool catalog check,
- static code search,
- list-tools inspection,
- runtime `frappe.get_meta()` reads,
- permission/metadata inspection using read-only calls,
- installed app/version inspection.

Do not perform destructive writes for this audit.

Document any existing failing baseline.

---

# 23. Acceptance Criteria

Task is complete only when:

- [ ] Entire current MCP project was inspected, not just Quotation/Sales Order.
- [ ] Sales and Purchase profile boundaries were understood.
- [ ] Valid profile scope rules were not mislabeled as duplication.
- [ ] All major mutation/read/create paths were reviewed.
- [ ] Runtime metadata usage was traced.
- [ ] Static metadata/field/state duplicates were identified.
- [ ] Permission logic was classified as delegated vs duplicated.
- [ ] Submit/cancel/delete logic was classified correctly.
- [ ] Delete was not incorrectly tied to `is_submittable`.
- [ ] Normal Frappe persistence paths were distinguished from bypass APIs.
- [ ] ERPNext calculations/defaults/controller logic were checked for duplication.
- [ ] India Compliance integration was inspected.
- [ ] Approval was preserved as an MCP-specific safety concern.
- [ ] Identity/profile/data-minimization boundaries were preserved as MCP concerns.
- [ ] Error handling was reviewed for adaptation vs business override.
- [ ] A complete duplication inventory was produced.
- [ ] A per-operation authority matrix was produced.
- [ ] A thin-bridge target architecture was proposed.
- [ ] Exact code areas that can be simplified were identified.
- [ ] One exact next implementation/refactor task was defined.
- [ ] No production/business code was changed.

---

# 24. Expected Result

At the end of this audit we should know:

```text
WHAT MCP SHOULD OWN
- profile exposure
- identity bridge
- model-facing contracts
- resolution/disambiguation
- missing-input interaction
- approval
- response shaping
- data minimization

WHAT FRAPPE / ERPNEXT SHOULD OWN
- runtime metadata
- permissions
- lifecycle capability/state
- business validation
- controller hooks
- defaults
- calculations
- link rules
- transactions
- persistence

WHAT CURRENT MCP CODE DUPLICATES
- exact files/symbols
- why it is duplication
- whether it can be removed
- what authoritative Frappe/ERPNext path should replace it
```

The audit must give us evidence before we simplify anything.

---

# 25. Exact Next Task

The audit report must define **one focused next implementation/refactor task**.

Do not pre-decide that the next task is:

- explicit Quotation/Sales Order update wrappers,
- Customer/Item restriction,
- lifecycle allowlist removal,
- or any other previously discussed change.

The next task must be derived from the duplication audit.

It must specify:

- exact duplicated rules to remove/simplify,
- exact authoritative Frappe/ERPNext APIs/metadata to rely on,
- MCP boundaries that remain,
- profile behavior that remains,
- backward compatibility requirements,
- tests,
- expected behavior,
- limitations.

Only after this audit is reviewed should the next implementation begin.
