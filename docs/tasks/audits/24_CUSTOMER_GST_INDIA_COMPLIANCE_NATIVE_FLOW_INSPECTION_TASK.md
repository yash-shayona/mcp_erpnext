# Task 24 - Customer GST / India Compliance Native Flow Inspection

## 1. Task Type

Inspection and architecture decision only.

Do not implement production code in this task.
Do not modify ERPNext, Frappe, India Compliance, mcp_erpnext runtime code, schemas, contracts, tests, hooks, settings, database records, or fixtures.

The only allowed repository output from this task is the inspection report described below.

---

## 2. Objective

Inspect the currently installed Frappe, ERPNext, India Compliance, and current mcp_erpnext source to determine the exact native Customer GST creation flow that mcp_erpnext should bridge.

The goal is NOT to recreate GST behavior inside mcp_erpnext.

The goal is to identify and document the existing India Compliance server-side capabilities used by the normal Customer / Quick Entry GSTIN flow, including:

- GSTIN handling
- GST category handling
- GSTIN verification / lookup / autofill
- Customer field population
- Address field population
- Customer and Address validation
- Customer insert hooks
- Address creation hooks
- configuration / account / API feature gates
- local development behavior
- sandbox behavior, if present in the installed source
- failure behavior when the API feature is disabled, unavailable, or not configured

Then define the smallest bridge architecture for the existing `prepare_customer -> confirm_customer` MCP flow.

---

## 3. Frozen Architecture Principle

This principle is mandatory for this task:

> mcp_erpnext is a bridge to ERPNext / India Compliance behavior. It must not reimplement GST business logic that the installed apps already own.

Therefore, do NOT propose or implement:

- custom GSTIN regex validation in mcp_erpnext
- custom GST state-code logic
- custom GST category derivation
- custom HTTP calls to GST / GSP / India Compliance endpoints
- direct storage of India Compliance API credentials in mcp_erpnext
- copied India Compliance API client code
- copied Quick Entry JavaScript logic
- duplicated Customer / Address GST validation
- direct database writes that bypass normal Frappe document lifecycle
- edits to India Compliance or ERPNext source
- a separate `create_gst_customer` tool merely because India Compliance is installed

The preferred direction, unless installed-source evidence proves it impossible, is:

```text
existing prepare_customer
        -> detect installed capability
        -> invoke/reuse the native India Compliance server-side capability where appropriate
        -> build exact preview from effective native result
        -> existing approval boundary
        -> existing confirm_customer
        -> normal Frappe Customer insert
        -> ERPNext + India Compliance hooks/validation remain authoritative
```

If the installed source shows that a different boundary is required, document the evidence and proposal in the report. Do not implement it in this task.

---

## 4. Version Policy - Critical

Do NOT hardcode any Frappe, ERPNext, India Compliance, or mcp_erpnext version number into the architecture assumptions or task logic.

The agent must inspect the versions actually installed in the current bench/worktree/site at execution time and record them in the report as observed evidence.

The implementation recommendation must be based on the installed source, not on an assumed release number, online example, old report, or memory.

Required distinction:

```text
observed installed version
        !=
architecture requirement
```

Record observed versions for traceability, but do not design logic that requires one fixed version string.

---

## 5. Inputs / Dependencies

Inspect the current repository/worktree and installed applications available in the active development bench.

At minimum inspect the current equivalents of these mcp_erpnext areas, if present:

```text
mcp_erpnext/services/masters/customer.py
mcp_erpnext/config/masters/customer.py
mcp_erpnext/tools/masters/customer.py
mcp_erpnext/services/common/creation_contract.py
mcp_erpnext/services/common/field_value_resolver.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/approvals.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tests/*customer*
mcp_erpnext/tests/test_creation_contract.py
mcp_erpnext/tests/test_approvals.py
```

Also inspect the currently installed source for:

```text
Frappe Customer/Address lifecycle support
ERPNext Customer creation / address helpers
India Compliance hooks
India Compliance Customer / Supplier / party overrides
India Compliance Address overrides
India Compliance GST custom-field definitions
India Compliance Customer/Address client scripts or Quick Entry integration
India Compliance GST Settings
India Compliance account/API configuration
India Compliance GSTIN lookup / verification / autofill server functions
India Compliance API client/service classes used by that lookup
India Compliance sandbox/developer-related gates, if any
```

Do not assume exact file names. Discover the real installed paths and functions first.

---

## 6. Existing mcp_erpnext Flow - Inspect Before Designing

Trace the current Customer creation implementation from public MCP tool to persistence.

Document the exact call flow for:

```text
prepare_customer
confirm_customer
```

Answer all of the following from source evidence:

1. What public Customer fields are currently accepted?
2. Is `gstin` currently accepted? Where?
3. Is `gst_category` currently accepted? Where or why not?
4. How are `customer_type`, `customer_group`, `territory`, and other defaults resolved?
5. How are Contact values handled?
6. How are Address values handled?
7. Is a temporary/unsaved Customer document created during prepare?
8. Is Customer validation called during prepare?
9. If validation mutates GST-related values, are those effective values copied back into the prepared payload and preview?
10. What exact payload is approval-bound?
11. What does `confirm_customer` insert?
12. Does confirmation use normal permissions, mandatory checks, link checks, hooks, and controller validation?
13. Are Customer/Address records written during prepare? They must not be unless existing architecture explicitly and safely requires it.
14. Does current code inspect special India Compliance helper fields such as `_address_line1` through Customer metadata? If yes, verify whether that detection is actually valid in the installed source.
15. Does the current test suite fake fields or behavior that do not exist in merged runtime metadata?

Do not propose changes until this current flow is fully traced.

---

## 7. Runtime Metadata Inspection

Use read-only runtime inspection on the relevant development site(s) where possible.

Determine:

- whether `india_compliance` is installed on the active site
- merged Customer metadata for GST-related fields
- merged Address metadata for GST-related fields
- fieldname, fieldtype, options, reqd, default, depends_on, mandatory_depends_on, read_only, hidden, fetch_from, fetch_if_empty where relevant
- whether fields such as `gstin` and `gst_category` are Custom Fields or core fields in the effective runtime metadata
- whether any underscore-prefixed Quick Entry/helper attributes are real DocFields or transient runtime attributes

Important:

- `apps.txt` / bench inventory alone is not proof that an app is installed on a specific site.
- Prefer the current site's installed-app state.
- Do not change metadata or settings.

---

## 8. India Compliance Customer GST Flow - Full Native Trace

Trace the native flow from the normal ERPNext/India Compliance UI down to the server implementation.

The report must include an evidence-backed call chain similar to this shape, but with the actual installed functions/files:

```text
Customer Quick Entry / GSTIN field event
        -> client-side trigger
        -> whitelisted/native server method
        -> GSTIN lookup/verification service
        -> India Compliance API/account/settings gate
        -> returned party/address data
        -> mapping/population into Customer/Address form state
        -> Customer insert
        -> Customer validate hooks
        -> after_insert hooks
        -> linked Address creation/update hooks
```

Do not assume every step exists exactly in this form. Record the actual installed flow.

For each step document:

- file path
- function/class name
- whether it is client-side or server-side
- whether it performs external I/O
- whether it performs database writes
- required permissions
- required settings/account state
- inputs
- returned values
- exceptions / failure states

---

## 9. Quick Entry vs MCP Boundary - Mandatory Finding

Explicitly determine which parts of GST autofill exist only to provide browser UI/UX and which parts are reusable server-side business capabilities.

Answer:

1. What exact JavaScript/client event triggers GSTIN autofill in Quick Entry?
2. What exact server-side method/function does it call?
3. Is that server-side method whitelisted only as an HTTP endpoint, or is its underlying Python service/helper directly reusable?
4. Which server-side function is the correct bridge candidate for mcp_erpnext?
5. Can mcp_erpnext call the Python function directly under the current Frappe request/user context instead of making an HTTP call back into the same site?
6. Does invoking that native server function preserve India Compliance permission checks and configuration gates?
7. Does that native server function only read/fetch data, or can it persist anything?
8. Is it safe for `prepare_customer` to invoke it without violating the existing prepare/confirm write boundary?

Preferred principle:

```text
Do not emulate Quick Entry UI.
Bridge the native server capability that Quick Entry already uses.
```

But prove the exact bridge from installed source before recommending it.

---

## 10. GSTIN Autofill Configuration / Availability Inspection

Determine exactly when India Compliance attempts or permits GSTIN lookup/autofill.

Inspect all relevant gates, including whatever exists in the installed source for:

- India Compliance installed status
- GST Settings
- API Features enablement
- party/GSTIN autofill setting
- India Compliance Account / API account presence
- authentication/configuration state
- API credits/subscription checks, if present
- sandbox mode, if present
- local development behavior
- developer mode, if referenced anywhere
- permission checks
- company or site scope, if any

Do NOT assume that `developer_mode = 1` enables India Compliance API functionality.

Do NOT assume that a local site has API access merely because India Compliance is installed.

Produce an observed behavior/configuration matrix such as:

| India Compliance installed | Autofill feature enabled | API/account usable | Expected native behavior |
|---|---|---|---|
| No | N/A | N/A | ERPNext-only Customer flow |
| Yes | No | Any | Native non-autofill GST behavior |
| Yes | Yes | No | Record exact native unavailable/error/fallback behavior |
| Yes | Yes | Yes | Native GSTIN lookup/autofill flow |

Fill this from source/runtime evidence, not assumptions.

---

## 11. Real External API Call Safety

This inspection task must NOT make a real GST/GSP/India Compliance external lookup merely to discover behavior unless the user has separately authorized such a call.

Reasons include:

- network dependency
- credentials/account dependency
- possible API credits
- rate limits
- sandbox restrictions
- audit/privacy concerns

Use:

- installed source inspection
- existing tests/mocks
- read-only settings inspection
- already-existing logs only when safe and relevant

If a real call is required to verify one remaining question, mark it as `NOT LIVE VERIFIED` and state the exact optional verification step instead of calling it.

Never expose or print secrets, tokens, passwords, API keys, authorization headers, or private account credentials in the report.

---

## 12. GST Category Inspection

Determine the exact installed-source behavior of `gst_category` for Customer and Address.

Answer:

- Where is the field defined?
- What values/options are allowed?
- Is it required by metadata, conditional metadata, or controller/hook logic?
- Is it defaulted?
- Is it derived or changed when a GSTIN is supplied?
- Does native GSTIN lookup return it?
- Does Customer validation normalize/change it?
- Is it copied to Address?
- Can Customer and Address legally end up with different categories in the native flow?
- What happens for unregistered, overseas, SEZ, composition, or other categories supported by the installed source?

Do not copy those rules into MCP. The purpose is only to know what native values must be accepted, previewed, and preserved.

---

## 13. Address Flow Inspection

Trace how Customer address creation works in both cases:

### A. ERPNext-only site

Determine the normal ERPNext Customer/Address helper path.

### B. India Compliance site

Determine whether India Compliance:

- injects temporary Customer attributes for Quick Entry
- uses `_address_line1` or an equivalent transient helper
- creates a primary Address in `after_insert`
- copies Customer GSTIN/category into Address
- validates Address GST data
- overrides or augments ERPNext address creation

Explicitly verify whether any current mcp_erpnext logic incorrectly uses `frappe.get_meta("Customer").has_field(...)` to detect a transient helper attribute.

If that logic exists and is invalid, report it as a confirmed defect with file/line evidence. Do not fix it in this inspection task.

---

## 14. Native Validation Authority

Identify which validations should remain exclusively authoritative in installed ERPNext / India Compliance.

Examples to inspect, not assume:

- GSTIN format/checksum validation
- GST category compatibility
- state/GSTIN relationship
- Address GSTIN handling
- overseas/SEZ/category rules
- duplicate GSTIN rules
- API-return normalization
- account/API authorization

The report must explicitly state that mcp_erpnext should not duplicate a rule when a native function/controller/hook already owns it.

If MCP needs preflight behavior for better conversational UX, recommend calling the native source function or reading native metadata/settings rather than copying the business rule.

---

## 15. Prepare-Time Native Lookup Semantics

Determine whether native GSTIN lookup/autofill belongs in `prepare_customer` when a GSTIN is supplied.

Evaluate:

- Does lookup perform only external/read operations?
- Does it mutate database state?
- Does it consume an API credit?
- Is it deterministic enough to bind into an approval preview?
- What fields can it enrich?
- What happens when the user also supplied a conflicting name/address/category?
- Does native India Compliance define precedence between user-entered and fetched data?
- Would calling it twice during prepare/confirm create inconsistent or costly behavior?
- Should confirm reuse approval-bound fetched data or re-fetch/revalidate?
- What native validation must still rerun at insert time?

Do not invent the answer. Give an evidence-backed recommendation.

The architecture must preserve the existing rule that prepare does not persist ERPNext business documents.

---

## 16. Candidate Bridge Designs to Compare

Compare at least these approaches using installed-source evidence:

### Option A - Rely only on Customer.insert hooks

Question: Does this reproduce the normal GSTIN autofill flow, or only validation/after-insert behavior?

### Option B - Copy Quick Entry/client logic into mcp_erpnext

Expected default: reject, because UI logic should not be duplicated.

### Option C - Call India Compliance public/whitelisted method through HTTP

Evaluate whether this creates unnecessary loopback HTTP/auth complexity when both apps run inside the same Frappe process.

### Option D - Directly reuse the same installed India Compliance Python service/helper used by its whitelisted method

Evaluate permissions, configuration gates, compatibility, and side effects.

### Option E - Reimplement the GST/GSP API call in mcp_erpnext

Expected default: reject.

### Option F - Optional integration adapter around the native India Compliance function

Evaluate whether a thin lazy adapter is the cleanest way to keep ERPNext-only sites independent while reusing native behavior when the app is installed.

The report must recommend one boundary and explain why.

---

## 17. Optional-App Dependency Rules

Any future implementation recommendation must preserve these rules:

1. mcp_erpnext must still import/start on ERPNext sites without India Compliance.
2. Do not import India Compliance unconditionally at mcp_erpnext module import time if that can break ERPNext-only sites.
3. Detect actual site installation/capability using normal Frappe runtime mechanisms.
4. Lazy-load/call the integration only when applicable.
5. Missing India Compliance must not turn normal Customer creation into an error.
6. India Compliance installed but API autofill disabled must follow native behavior; MCP must not silently bypass the app and call an external API itself.
7. India Compliance installed but misconfigured must expose a safe actionable result based on native behavior, without leaking credentials/internal secrets.
8. Final Customer persistence must continue through normal Frappe/ERPNext document lifecycle.

---

## 18. Public MCP Contract Inspection

Inspect the current public contract status of `prepare_customer` and `confirm_customer`.

Determine:

- whether they are typed or frozen legacy contracts
- where their schemas are registered
- whether `gstin` is already publicly exposed
- whether `gst_category` is exposed
- how optional Contact/Address structures are represented
- whether adding fields would require a contract migration or can fit the existing approved boundary
- whether an arbitrary `extra_fields` dictionary exists or has been rejected by architecture standards

Do NOT add a generic `extra_fields: dict` solution.

Do NOT change the public contract in this inspection task.

If a contract extension is needed, document the exact smallest extension for the next implementation task.

---

## 19. Permissions and Identity

Verify that any recommended native India Compliance call can run under the existing authenticated Frappe user context.

Do not add:

- Administrator fallback
- service-user bypass
- ignore_permissions behavior
- hardcoded roles
- client-supplied Frappe user identity

Document the permissions checked by:

- Customer creation
- Customer read if needed
- Address creation
- native GSTIN lookup/autofill method
- any linked DocType reads used by that method

If the native API method has its own permission checks, preserve them.

---

## 20. Error / Interaction Behavior

Inspect how the existing MCP Customer flow represents:

- missing input
- ambiguity
- invalid values
- permission denial
- approval requirement
- native validation errors
- unexpected ERP errors

Then recommend how these native India Compliance outcomes should map without inventing new app-specific error machinery unless required:

- India Compliance absent
- GSTIN omitted
- GSTIN supplied, API autofill feature disabled
- GSTIN supplied, API/account unavailable
- GSTIN supplied, native lookup succeeds
- GSTIN supplied, native lookup says invalid/not found
- returned data conflicts with user input
- GST category missing but native flow can derive it
- GST category missing and native flow requires user input

Reuse the existing shared interaction/error contract where possible.

---

## 21. Tests / Verification During Inspection

This is primarily a source and read-only runtime audit.

Allowed verification:

- inspect installed source
- inspect current mcp_erpnext source
- inspect merged metadata
- inspect installed-app list
- inspect non-secret boolean/select settings needed to understand feature gates
- run existing unit tests if they are read-only and already configured
- inspect existing India Compliance tests/mocks for GSTIN autofill behavior
- inspect existing mcp_erpnext Customer tests

Do not:

- create a real Customer
- create a real Address
- change GST Settings
- enable/disable India Compliance API features
- create/update India Compliance Account records
- consume external API credits
- modify test fixtures
- change production code

If live write verification is desirable, specify it separately in the report as a later explicitly-authorized verification step.

---

## 22. Required Behavior Matrix

The report must include a matrix covering at least:

| Scenario | Native app state | Expected MCP bridge behavior | Source evidence | Live verified? |
|---|---|---|---|---|
| ERPNext-only site | India Compliance absent | Existing Customer flow unchanged | | |
| India Compliance installed, no GSTIN | GST extension present | Native normal Customer behavior | | |
| GSTIN supplied, autofill disabled | Feature disabled | Follow native non-autofill behavior | | |
| GSTIN supplied, autofill enabled but API unavailable | Config/account unavailable | Follow native safe error/fallback behavior | | |
| GSTIN supplied, autofill available | Native lookup usable | Reuse native lookup result in prepare preview | | |
| Native GSTIN invalid/not found | Native lookup/validation rejects | Safe actionable response, no approval/write | | |
| User supplies address without GSTIN lookup | Normal manual path | Preserve native Customer/Address validation | | |
| India Compliance creates primary Address after Customer insert | Hook applicable | Do not duplicate address creation | | |
| ERPNext-only manual address creation | No India Compliance hook | Preserve existing ERPNext behavior | | |

Fill this from observed evidence.

---

## 23. Required Findings / Decisions

The final report must answer these questions explicitly with `YES`, `NO`, or `CONDITIONAL`, followed by evidence:

1. Is current `prepare_customer` already partially GST-aware?
2. Is `gstin` already accepted publicly?
3. Is `gst_category` currently missing from the MCP creation contract?
4. Is Quick Entry autofill triggered client-side?
5. Is the actual GST lookup implemented server-side in India Compliance?
6. Can that native server-side capability be reused directly from mcp_erpnext without custom external HTTP/GST logic?
7. Does normal `Customer.insert()` alone trigger the external GSTIN autofill lookup?
8. Do normal Customer insert hooks still perform India Compliance validation/after-insert behavior?
9. Does India Compliance create/copy GST data into a primary Address during its native flow?
10. Is `_address_line1` or equivalent a real Customer DocField or a transient helper in the installed source?
11. Is current mcp_erpnext detection of that helper correct?
12. Does `developer_mode` control India Compliance API availability?
13. What settings/account state actually controls GSTIN autofill?
14. What happens on the current local development site when those features are not configured?
15. Can prepare safely use the native lookup without persistent DB writes?
16. Should confirm re-fetch the GSTIN data, revalidate only, or use approval-bound prepared data? Give installed-source evidence.
17. Can ERPNext-only sites remain completely unchanged?
18. Is a new public MCP tool required? Default expectation is NO unless evidence proves otherwise.

---

## 24. Recommended Implementation Boundary

At the end of the report, provide one concrete implementation recommendation.

It should be expressed as a call flow, for example:

```text
prepare_customer
  -> current generic Customer contract/default resolution
  -> determine whether India Compliance Customer GST capability is installed
  -> if applicable and GSTIN supplied:
       call the same native India Compliance server capability used by Quick Entry
       under the current Frappe user context
       obey native feature/account/settings gates
       consume returned Customer/Address values
  -> run appropriate native unsaved-document validation/preflight without persistence
  -> build preview from effective values
  -> approval binds complete effective Customer/Contact/Address/GST state

confirm_customer
  -> existing approval claim
  -> current permission/duplicate rechecks
  -> normal Customer insert
  -> installed ERPNext/India Compliance hooks remain authoritative
  -> do not duplicate native Address creation when India Compliance already owns it
```

That is only an example shape. Adjust it to the installed source evidence.

Also identify the exact internal seam where an optional India Compliance adapter/provider should live, if one is justified by the repository's existing architecture.

Do not create a generic plugin framework unless the current codebase already has one or the source evidence clearly requires it.

---

## 25. Allowed Changes

Only create/update this inspection report:

```text
docs/inspect/CUSTOMER_GST_INDIA_COMPLIANCE_NATIVE_FLOW_AUDIT.md
```

If the repository has an established naming convention that differs, place the report in the existing `docs/inspect/` convention with an equivalent descriptive filename and state the final path.

Do not modify any other file.

---

## 26. Files / Components That Must Not Change

Do not modify:

```text
mcp_erpnext/**
apps/frappe/**
apps/erpnext/**
apps/india_compliance/**
site_config.json
common_site_config.json
GST Settings
India Compliance Account
Custom Field
Property Setter
Customer
Address
Contact
database records
fixtures
patches
hooks
migrations
profile allowlists
tool registration
contracts
approval behavior
```

The report file is the only write allowed by this task.

---

## 27. Report Structure

The report must contain these sections in this order:

1. Executive Summary
2. Scope and Non-Changes
3. Current Installed Versions Observed
4. Sites / Installed-App State Inspected
5. Current mcp_erpnext Customer Creation Call Flow
6. Current Public Customer Creation Contract
7. Effective Customer and Address GST Metadata
8. India Compliance Hooks Relevant to Customer/Address
9. Quick Entry GSTIN Autofill Client Trigger
10. Native GSTIN Autofill Server Call Chain
11. India Compliance API / Account / Settings Gates
12. Local Development and Developer Mode Findings
13. Sandbox Findings, If Applicable
14. GST Category Native Behavior
15. Customer Address Native Behavior
16. `_address_line1` / Transient Helper Finding
17. Prepare-Time Side Effects and Safety
18. Permission and Identity Behavior
19. Error / Failure Behavior
20. ERPNext-Only Compatibility
21. Architecture Options Comparison
22. Recommended Bridge Architecture
23. Required MCP Contract Change, If Any
24. Test Plan for Next Implementation Task
25. Known Limitations / Not Live Verified
26. Final Frozen Decision Proposal
27. Exact Next Task

Every significant implementation claim must cite installed file/function/line evidence where practical.

---

## 28. Acceptance Criteria

This task is complete only when all of the following are true:

- Current mcp_erpnext Customer create flow is fully traced before proposing changes.
- Installed versions are discovered dynamically and recorded; no fixed version is assumed.
- Actual site installation state for India Compliance is distinguished from bench inventory.
- Customer and Address GST fields are verified from merged metadata and source.
- Quick Entry GSTIN autofill is traced from UI trigger to the native server function.
- The exact native server bridge candidate is identified.
- It is proven whether `Customer.insert()` alone does or does not perform external GSTIN autofill.
- India Compliance feature/account/settings gates are identified from installed source.
- Developer mode is checked explicitly and not assumed to enable API access.
- Local/sandbox behavior is documented from source/config evidence without making unauthorized real API calls.
- GST category behavior is traced natively.
- Customer-to-Address GST behavior is traced natively.
- `_address_line1` or equivalent is classified correctly as metadata field vs transient helper.
- Existing mcp_erpnext address detection logic is evaluated against that fact.
- No GST/GSP/API business logic is proposed for duplication inside mcp_erpnext.
- ERPNext-only behavior is preserved in the recommendation.
- The recommended design keeps `prepare_customer -> confirm_customer` unless source evidence requires otherwise.
- A clear implementation task can be written from the report without another architecture discovery pass.
- No production/runtime/source files were changed except the report.

---

## 29. Expected Result

Expected architectural result, subject to installed-source confirmation:

```text
mcp_erpnext does not become a GST engine.

Quick Entry remains only a UI trigger.
The reusable India Compliance server-side GSTIN capability is the bridge target.

If India Compliance is absent:
    existing ERPNext Customer creation remains unchanged.

If India Compliance is installed but autofill is disabled/unavailable:
    MCP follows the installed app's native behavior and does not bypass it.

If native GSTIN autofill is available:
    prepare_customer can reuse the native server-side result for preview,
    subject to the prepare/confirm safety analysis.

Final Customer creation still uses normal Frappe lifecycle,
so ERPNext and India Compliance validation/hooks remain authoritative.
```

Do not force this conclusion if installed source proves otherwise; document evidence and adjust only the minimum necessary boundary.

---

## 30. Known Boundaries / Limitations

- This task does not implement GST support.
- This task does not modify the public MCP schema.
- This task does not create a new MCP tool.
- This task does not make a real external GSTIN lookup without separate authorization.
- This task does not create test Customer/Address records.
- This task does not change India Compliance settings/account state.
- This task does not guarantee API availability on the current local site.
- Source behavior may differ between installed versions; therefore all conclusions must be tied to the currently installed source rather than a hardcoded release assumption.

---

## 31. Exact Next Task

After this inspection report is reviewed and approved:

### Task 25 - Customer GST / India Compliance Native Bridge Implementation

Implement only the bridge architecture proven by the Task 24 report.

The next task must:

- reuse the existing Customer creation flow
- reuse native India Compliance server functions where applicable
- preserve ERPNext-only sites
- avoid custom GST API/business logic
- preserve the current prepare/approval/confirm write boundary
- add only the smallest required explicit Customer GST contract fields
- preserve native Customer/Address validation and hooks
- add regression coverage for both India Compliance-present and India Compliance-absent behavior
- include local behavior when native GST autofill is unavailable/configuration-gated

Do not write Task 25 implementation details until the Task 24 inspection report has established the exact installed-source call chain and integration seam.
