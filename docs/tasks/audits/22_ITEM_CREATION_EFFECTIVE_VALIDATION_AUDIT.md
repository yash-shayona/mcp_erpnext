# Task 22 — Item Creation Effective Validation Audit

## Status
Planned / Audit Only

## Task Type
Architecture + Source Inspection + Root-Cause Audit

## Scope
This task audits the current `mcp_erpnext` Item creation flow and determines how MCP should discover and surface **effective runtime creation requirements** that are not represented only by normal Frappe DocType mandatory metadata.

The immediate real-world case is the HSN/SAC requirement introduced by India Compliance for eligible Items, but this task must not turn into an India-Compliance-only patch design unless the source inspection proves that a narrowly scoped adapter is the correct boundary.

This task is strictly **inspection and design recommendation only**.

No production code, schema, tool contract, service logic, hooks, settings, tests, migrations, fixtures, or app behavior may be changed in this task.

---

## Objective
Determine exactly why Item creation can reach `confirm_item` and then fail with an HSN/SAC validation error, and define the smallest architecture that lets `prepare_item` detect applicable runtime/app-specific requirements early enough to ask the user for missing input before approval.

The audit must answer all of the following:

1. How does the current Item creation path work end-to-end?
2. Which required Item fields are currently discovered from runtime DocType metadata?
3. At what exact point does Frappe perform the final `Item` validation/insert lifecycle?
4. Where does India Compliance attach Item validation?
5. Under exactly which conditions does India Compliance require `gst_hsn_code`?
6. Why is that requirement not currently surfaced by `prepare_item`?
7. Should MCP solve this through:
   - existing metadata only,
   - a generic effective-requirements/preflight layer,
   - an app-specific integration adapter,
   - or a combination of generic preflight infrastructure plus isolated adapters?
8. How should the solution behave when India Compliance is not installed?
9. How should the solution behave when India Compliance is installed but HSN validation is disabled?
10. How should the solution behave for non-sales / purchase-only Items?
11. How can the solution preserve the current public MCP tool-contract philosophy without adding arbitrary untyped dictionaries or making India-specific fields globally mandatory?
12. What is the smallest implementation task that should follow this audit?

---

## Known Starting Evidence
Treat the following as starting evidence only. Re-inspect the actual project and installed app source before finalizing conclusions.

### Current MCP Item creation design
The project already has an Item creation flow based around existing Item resolution and explicit approval:

```text
resolve_item
  -> not_found
  -> prepare_item
  -> explicit approval
  -> confirm_item
  -> created/resolved Item
```

The current design intentionally uses runtime Item metadata and should not be replaced by a hardcoded ERPNext mandatory-field list.

### India Compliance behavior to verify
Upstream India Compliance v16 currently attaches an Item `validate` hook and invokes HSN/SAC validation for sales Items.

The effective condition is expected to be more specific than:

```text
India Compliance installed = HSN mandatory
```

The audit must verify the actual condition from source and current site configuration.

Expected behavior to verify:

```text
India Compliance absent
-> no India Compliance HSN requirement

India Compliance present
+ GST Settings HSN validation disabled
-> no HSN requirement from this rule

India Compliance present
+ GST Settings HSN validation enabled
+ Item is a sales item
-> HSN/SAC required

India Compliance present
+ Item is not a sales item
-> this specific validation should not require HSN/SAC
```

Do not assume this matrix is final until source inspection confirms it for the actual installed version.

---

## Inputs / Dependencies
Inspect the actual current repository and active Frappe environment as the source of truth.

Required inputs include:

- Current `mcp_erpnext` source tree.
- Current Item tool layer.
- Current Item service layer.
- Current Item creation contracts/models.
- Current Item configuration files.
- Current resolver logic.
- Current approval/confirm logic.
- Current error mapping / MCP error translation logic.
- Current runtime metadata helpers.
- Current installed-app detection helpers, if any.
- Current Frappe/ERPNext Item metadata.
- Current installed India Compliance source, if installed.
- Current `GST Settings` fields relevant to HSN validation.
- Existing project architecture/contract docs related to public tool schemas and generic internal engines.

If the repository contains newer or renamed files compared with older documentation, use the live repository as authoritative and record the difference in the audit report.

---

## Source-Grounding Rules
For Frappe/ERPNext/India Compliance behavior:

1. Prefer the actual installed source in the current bench/app environment.
2. Otherwise verify against the matching official upstream branch/version.
3. Do not rely on forum posts, blogs, Stack Overflow, guesses, or old task descriptions for behavioral claims.
4. Separate:
   - confirmed current-project behavior,
   - confirmed upstream framework/app behavior,
   - inference/recommendation.

Every architecture recommendation must point back to inspected code paths or settings.

---

## Files / Components Allowed to Inspect
At minimum inspect all relevant files under the current equivalents of:

```text
mcp_erpnext/
  tools/
    masters/
      item.py
  services/
    masters/
      item.py
  contracts/
    masters/
  config/
    masters/
  resolvers/
  approvals/
  errors/
  common/
  settings.py
  mcp_server.py

tests/
  ...item-related tests...
```

Also inspect any shared helpers actually used by Item creation, including metadata, validation, approval, capability/profile, identity, or error helpers.

Inspect Frappe/ERPNext/India Compliance source relevant to:

```text
Item
Item.validate lifecycle
DocType metadata loading
installed app discovery
India Compliance hooks
India Compliance Item override/validation
GST HSN Code validation
GST Settings
```

Do not assume these paths are exact if the live repository differs.

---

## Allowed Changes
Only one deliverable may be created:

```text
docs/inspect/ITEM_CREATION_EFFECTIVE_VALIDATION_AUDIT.md
```

If `docs/inspect/` does not exist, create that directory only if this matches the existing documentation organization. If the project already has a different established inspection/audit folder, reuse the existing project convention instead and clearly state the chosen path.

No other project file may be modified.

---

## Explicitly Disallowed Changes
Do not:

- modify `prepare_item`;
- modify `confirm_item`;
- modify public MCP tool schemas;
- add `gst_hsn_code` to any contract;
- make HSN/SAC globally mandatory;
- add an `india_compliance` hardcoded branch to production code;
- create a new validation framework;
- create a plugin/adapter registry;
- bypass Frappe validation;
- use `ignore_validate`;
- use `ignore_mandatory`;
- suppress India Compliance validation errors;
- change approval behavior;
- change Item eligibility defaults;
- change sales/purchase profile behavior;
- change app installation state;
- change GST Settings;
- add migrations or fixtures;
- add or modify tests;
- refactor unrelated code.

This audit decides what should be implemented later; it must not implement the answer itself.

---

# Required Inspection Steps

## Step 1 — Trace the current Item creation flow end-to-end
Start from the public MCP tools and trace the actual code path through every layer for:

```text
search_items
resolve_item
prepare_item
confirm_item
```

Document:

- public tool function;
- request/response contract;
- service call;
- metadata lookup;
- missing-field detection;
- preview creation;
- approval token/state handling;
- confirmation path;
- Frappe document creation;
- `insert()` / `save()` call;
- error translation path.

Produce a call-flow diagram using project file/function names.

Do not stop at the public tool layer.

---

## Step 2 — Inspect the current runtime metadata mechanism
Find exactly how `prepare_item` determines which fields are required.

Answer:

- Does it call `frappe.get_meta("Item")` directly or through a helper?
- Which metadata flags are considered?
- Are `reqd`, fieldtype, default, hidden, read-only, depends-on, mandatory-depends-on, or custom fields considered?
- Does it inspect runtime Custom Fields?
- Does it inspect property setters?
- Does it distinguish fields required for creation from fields required only by later controller validation?
- Does it know the final value of `is_sales_item` before deciding readiness?
- Does it apply Item defaults before evaluating requirements?

Record the exact current behavior, not the desired behavior.

---

## Step 3 — Reproduce or trace the HSN/SAC failure location
Find where the current failure actually occurs.

If a safe existing automated test or existing reproducible development path exists, use it without mutating business data unnecessarily.

Otherwise trace statically from source.

Determine whether the error occurs during:

```text
prepare_item
approval
confirm_item
frappe.get_doc(...)
insert()
before_validate
validate
before_insert
other lifecycle hook
```

Capture:

- exception type;
- message;
- originating function;
- calling stack/path;
- current MCP error returned to the client.

The report must clearly distinguish the immediate failing function from the architectural reason the input was not requested earlier.

---

## Step 4 — Inspect India Compliance Item integration
If India Compliance is installed, inspect the installed source.

If it is not installed in the current environment, inspect the matching official upstream source for the project version and clearly label this as upstream verification rather than active-site behavior.

Locate:

- Item-related hooks;
- Item override/validation function;
- HSN/SAC validation function;
- GST Settings lookup;
- any Item client-side behavior related to HSN/SAC;
- any custom field / property setter / install setup that provides `gst_hsn_code` on Item.

Answer exactly:

```text
When is gst_hsn_code required?
```

Do not reduce the answer to installed-app presence.

---

## Step 5 — Inspect GST Settings dependency
Identify the exact settings involved in HSN validation.

At minimum verify:

- validation enable/disable flag;
- minimum/valid HSN length configuration;
- whether these values are cached;
- whether any company-specific or global behavior applies;
- behavior when the setting is missing/unconfigured;
- behavior for blank `gst_hsn_code`;
- behavior for invalid length;
- whether a referenced GST HSN Code record must exist.

Document which checks must remain authoritative in India Compliance versus which checks MCP may safely use for proactive input collection.

---

## Step 6 — Verify the sales-item gate
Inspect both core ERPNext Item defaults and the current MCP Item creation contract.

Determine:

- default value of `is_sales_item`;
- whether current `prepare_item` explicitly sets it;
- whether sales and purchase profiles produce different Item eligibility values;
- whether a new Item created from a sales flow is effectively a sales Item by default;
- whether a purchase-only Item can avoid the specific HSN validation;
- whether MCP currently has enough information at prepare time to know this.

This is important because the effective HSN requirement depends on the resulting Item state, not only installed apps/settings.

---

## Step 7 — Inspect installed-app/capability detection already present in the project
Search before inventing anything new.

Look for existing project helpers for:

- `frappe.get_installed_apps()`;
- app availability checks;
- optional integration handling;
- feature/capability detection;
- profile capability configuration;
- runtime metadata adapters;
- validation/preflight registries;
- optional field handling.

If an existing pattern is sound, prefer reusing it.

If no such pattern exists, record that clearly.

Do not design a new abstraction until this search is complete.

---

## Step 8 — Inspect public MCP schema constraints
Review the existing MCP tool-contract standard and current Item create contract.

Determine what options are compatible with the project's schema philosophy.

Specifically evaluate whether each of these would be appropriate or inappropriate:

```text
A. Add gst_hsn_code as a normal optional Item creation field.
B. Add arbitrary extra_fields: dict.
C. Add generic dynamic key/value fields.
D. Add typed integration-specific optional structures.
E. Keep public input unchanged and return structured needs_input requirements.
F. Introduce a generic internal requirement/preflight layer while keeping public tools explicit.
```

Do not choose based only on convenience.

Evaluate:

- discoverability for LLM clients;
- typed schema quality;
- MCP tools/list stability;
- client independence;
- portability without India Compliance;
- future optional apps;
- security;
- validation authority;
- backward compatibility;
- implementation complexity.

---

## Step 9 — Determine the correct architecture boundary
Compare at least these architecture options.

### Option A — Metadata-only
Continue relying only on runtime DocType metadata.

Explain whether this can detect the real HSN/SAC rule and why/why not.

### Option B — Hardcoded India Compliance condition in Item service
Example concept only:

```text
if india_compliance installed and HSN validation enabled:
    require gst_hsn_code
```

Explain why this is or is not acceptable.

### Option C — Generic effective-requirements/preflight service
A shared internal layer resolves creation requirements from:

```text
core runtime metadata
+ effective document state/defaults
+ optional installed-app/business validation requirements
```

Explain what should be generic and what should not.

### Option D — Generic preflight framework + isolated integration adapter
Core Item creation remains generic, while India Compliance-specific knowledge lives behind a small isolated adapter/provider that is invoked only when applicable.

Explain whether this is the cleanest boundary for a standalone MCP server.

### Option E — Other existing project-native pattern
If the repository already contains a better established pattern, document it and compare it with A-D.

---

## Step 10 — Define behavior matrix
The report must include a verified matrix covering at least:

| Environment / State | Expected `prepare_item` behavior | Expected `confirm_item` behavior |
|---|---|---|
| ERPNext only | Normal existing metadata-driven flow | Normal Frappe validation |
| India Compliance installed, HSN validation OFF | Do not ask for HSN because of this rule | Normal validation |
| India Compliance installed, HSN validation ON, sales Item, HSN missing | Return `needs_input` before approval | Confirmation must not be reached until required input is supplied |
| India Compliance installed, HSN validation ON, sales Item, HSN invalid length | Surface actionable validation before approval if safely derivable | Upstream validation remains final authority |
| India Compliance installed, HSN validation ON, non-sales Item | Do not require HSN because of this specific rule | Normal validation |
| Optional app absent | No import/runtime dependency on that app | Existing Item creation remains functional |

Add any additional cases discovered during inspection.

---

## Step 11 — Define error/UX behavior
Recommend the user-facing behavior for a missing conditional requirement.

The audit should determine whether `prepare_item` can return a structured result such as:

```text
status: needs_input
missing requirement: HSN/SAC Code
reason: required by active GST/India Compliance validation for this sales Item
```

Do not finalize exact field names unless they fit the current response contract.

The final UX should avoid exposing internal stack traces or implementation details to ordinary users.

For environment/configuration problems that the current user cannot resolve, wording should direct the user to an authorized person, administrator, or support as appropriate.

---

## Step 12 — Preserve Frappe as final authority
The recommendation must preserve this rule:

```text
MCP preflight = proactive conversational guidance
Frappe / ERPNext / installed app validation = final write authority
```

Even if MCP validates HSN presence or length early, `confirm_item` must still perform a normal Frappe insert and allow upstream validation to run.

The audit must explicitly reject designs that duplicate and replace the authoritative application validation.

---

## Step 13 — Recommend the smallest next implementation
After inspection, recommend one concrete next task only.

The recommendation must identify:

- exact architecture choice;
- exact files/components that would change;
- exact files/components that should remain untouched;
- whether a new internal helper/module is justified;
- whether any public tool schema change is required;
- whether an integration-specific adapter is required;
- tests needed;
- backward-compatibility impact;
- behavior when India Compliance is absent.

Do not implement it in this task.

---

# Required Deliverable
Create exactly one audit report:

```text
docs/inspect/ITEM_CREATION_EFFECTIVE_VALIDATION_AUDIT.md
```

If another existing project inspection-report folder is clearly the established convention, use that convention and state the final path in the task completion summary.

---

# Required Audit Report Structure
The report must contain these sections in this order.

## 1. Executive Summary
Short conclusion explaining the actual root cause and recommended architecture direction.

## 2. Current Item Creation Flow
End-to-end call path with exact files/functions.

## 3. Current Metadata-Driven Requirement Logic
What `prepare_item` currently considers and does not consider.

## 4. Exact HSN/SAC Failure Path
Where the error originates and why it reaches that point.

## 5. India Compliance Source Findings
Hooks, validators, settings, Item gates, and HSN/SAC rules.

## 6. GST Settings Findings
Exact runtime conditions and configuration behavior.

## 7. Sales vs Purchase Item Behavior
How `is_sales_item` and current profiles affect the requirement.

## 8. Existing Project Capability / Integration Patterns
Reusable helpers or confirmation that none exist.

## 9. Public MCP Contract Constraints
What schema designs fit or conflict with the current standard.

## 10. Architecture Options Comparison
A table comparing all inspected options.

## 11. Recommended Architecture
One preferred design with justification.

## 12. Verified Behavior Matrix
Environment/settings/item-state combinations.

## 13. Error and User-Experience Recommendation
How missing conditional requirements should surface.

## 14. Security and Validation Boundaries
What MCP may preflight versus what Frappe must remain authoritative for.

## 15. Backward Compatibility
ERPNext-only and India-Compliance-absent behavior.

## 16. Exact Files for Next Task
Allowed and forbidden modifications for implementation.

## 17. Test Plan for Next Task
Unit/integration scenarios required.

## 18. Known Limitations / Open Questions
Anything not proven by current source.

## 19. Final Decision Proposal
A concise proposed architecture decision ready for review/freeze.

## 20. Exact Next Task
One implementation task title and objective only.

---

# Acceptance Criteria
This task is complete only when all of the following are true:

- The current Item creation path has been traced end-to-end.
- The exact current metadata requirement logic has been identified.
- The exact HSN/SAC exception origin has been identified.
- The India Compliance Item hook has been verified from actual installed source or matching official source.
- The exact HSN/SAC requirement condition has been verified.
- `GST Settings` dependency has been verified.
- `is_sales_item` gating has been verified.
- The reason `prepare_item` currently misses the requirement has been proven or clearly labeled as unresolved.
- Existing project-native optional-app/capability patterns have been searched before proposing a new one.
- Public MCP schema constraints have been evaluated.
- At least four architecture options have been compared.
- A single smallest recommended architecture has been proposed.
- The design keeps ERPNext-only installations working unchanged.
- The design does not make HSN/SAC globally mandatory.
- The design does not bypass or replace Frappe/India Compliance validation.
- No production code has been changed.
- Exactly one audit report has been created.
- The report includes an exact next implementation task.

---

# Verification / Tests for This Audit Task
Because this is an audit-only task, testing is verification-oriented.

## Verification 1 — Repository cleanliness
Confirm only the audit report file was added/changed.

Expected result:

```text
No application source, test source, config, hook, schema, migration, or fixture changed.
```

## Verification 2 — Source trace completeness
Every major conclusion in the report should include the exact project or framework/app file and function from which it was derived.

Expected result:

```text
A reviewer can independently follow the same code path.
```

## Verification 3 — Conditional matrix correctness
Verify the HSN behavior matrix against the actual source/settings logic.

Expected result:

```text
The report does not claim that India Compliance installation alone makes HSN/SAC mandatory.
```

## Verification 4 — Portability
Confirm the recommended architecture has no mandatory runtime import/dependency on India Compliance when that app is absent.

Expected result:

```text
ERPNext-only Item creation remains supported.
```

## Verification 5 — Validation authority
Confirm the recommended approach still performs normal Frappe document insertion and allows upstream validators to execute.

Expected result:

```text
MCP improves preflight UX without weakening application validation.
```

---

# Expected Result
At the end of this task, we should be able to answer this question with source-backed certainty:

> How should `mcp_erpnext` determine the effective required inputs for Item creation when optional installed Frappe apps add runtime validation requirements that are not represented by ordinary DocType `reqd` metadata?

For the immediate HSN/SAC case, the audit should establish whether the final intended flow should conceptually become:

```text
prepare_item
  -> resolve core Item runtime metadata/defaults
  -> determine effective Item state
  -> evaluate applicable conditional runtime requirements
  -> if required input is missing:
       return needs_input
  -> build preview
  -> explicit approval
  -> confirm_item
  -> normal Frappe insert
  -> authoritative ERPNext / installed-app validation
```

This flow is only a hypothesis until the audit confirms the correct architecture boundary.

---

# Limitations / Boundaries
This task does not attempt to create a universal interpreter for arbitrary Frappe controller code or validation hooks.

It also does not assume every validation error can or should be predicted before insert.

The goal is to identify a maintainable boundary for requirements that are:

- knowable before write;
- relevant for conversational input collection;
- stable enough to model safely;
- and worth surfacing before approval.

Unexpected or deeply dynamic validations may still legitimately be returned by Frappe during confirmation.

---

# Exact Next Task
Do not start automatically.

After this audit report is reviewed and the architecture decision is frozen, create:

```text
Task 23 — Item Creation Conditional Runtime Requirements Implementation
```

Its exact scope must be derived from the audit findings rather than assumed in advance.
