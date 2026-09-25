# Task 66 — Sales Document Authoring Enhancements, Email Recipient Scope, Terms Handling, and MCP Instruction Modularization

## Status

**Implementation task — decisions frozen and ready for implementation.**

This task is based on inspection of the user-provided `mcp_erpnext_2026-09-25T10-36-37Z.zip` source and the architecture decisions completed before this handoff.

Repository task destination:

```text
docs/tasks/implementation/25-09-2026/66_TASK_SALES_DOCUMENT_AUTHORING_EMAIL_RECIPIENT_TERMS_AND_MCP_INSTRUCTIONS.md
```

Required implementation report destination:

```text
docs/inspect/25-09-2026/SALES_DOCUMENT_AUTHORING_EMAIL_RECIPIENT_TERMS_AND_MCP_INSTRUCTIONS_IMPLEMENTATION_REPORT.md
```

---

## Objective

Extend the existing MCP capabilities without adding unnecessary new mutation tools so that:

1. generic document email can deliberately target either the document's business party or the authenticated user's own email;
2. Item Master creation and Quotation/Sales Order/Sales Invoice item rows can accept an optional description while preserving ERPNext-native defaults when description is omitted;
3. Quotation/Sales Order/Sales Invoice can accept an explicit Terms and Conditions template, otherwise use the Company's native `default_selling_terms`, otherwise leave Terms empty, with no template-name guessing or MCP-specific terms policy/configuration;
4. the already-existing `custom_remarks` custom field on Sales Order and Sales Invoice is exposed through the MCP create inputs and review previews without creating or migrating that field;
5. the large server instruction constant is moved out of `mcp_server.py` into a maintainable, source-controlled instruction module/package with common and profile-specific composition.

All changes must preserve the current prepare -> preview/approval -> confirm safety model, permission boundaries, MCP/REST parity, and native ERPNext calculations/validation.

---

## Handoff Context

### Existing capabilities confirmed from the inspected source

- `prepare_document_email` / `confirm_document_email` already provide generic approval-bound document email with PDF attachment.
- Current email recipient resolution is deliberately restricted to document-linked business-party/contact email addresses.
- `QuotationPrepareInput` already exposes optional `tc_name` and Quotation preview already exposes `tc_name` and `terms`.
- Sales Order and standalone Sales Invoice creation contracts do not currently expose `tc_name`.
- `QuotationItemInput` and `SalesOrderItemInput` do not currently expose item-row `description`.
- `SalesInvoiceItemInput` does not currently accept description, although `SalesInvoicePreviewItem` already exposes the ERPNext-populated row description.
- Item creation does not currently accept `description`; `mcp_erpnext/config/masters/item.py` does not include `description` in `CREATION_FIELDS`.
- `custom_remarks` is a pre-existing target-site custom field on **Sales Order** and **Sales Invoice**. This task must not create it.
- `MCP_ROUTING_INSTRUCTIONS` currently lives as a large constant in `mcp_erpnext/mcp_server.py`; `test_tool_routing.py` imports and asserts against it directly.
- Remote/REST execution has dedicated handlers in `mcp_erpnext/remote_operations.py`, so every public contract change must remain transport-parity safe.
- Tool descriptions are centrally governed through `mcp_erpnext/contracts/registry.py`, and `docs/TOOLS.md` is generated from the governed contract surface.

### ERPNext native Terms behavior that must be respected

Before editing, verify the installed ERPNext version's source. The current official ERPNext source shows the intended selling-document behavior in `SellingController.onload`:

```text
if company is set and terms are empty:
    if tc_name is empty:
        tc_name = Company.default_selling_terms
    set_missing_terms()
```

`AccountsController.set_missing_terms()` renders the selected Terms and Conditions template into the transaction's `terms` field.

This matters because these MCP preparation services construct new server-side documents without normal Desk `onload` behavior. Do not assume `set_missing_values()` alone materializes both `tc_name` and rendered `terms` on every ERPNext version.

Use native controller seams such as `set_missing_terms()` where available rather than copying Terms template rendering logic into MCP.

---

## Scope

### In scope

- Existing document-email recipient scope extension: `party` vs `self`.
- Item Master optional `description` support.
- Quotation item-row optional `description` support.
- Sales Order item-row optional `description` support.
- Sales Invoice item-row optional `description` support.
- Explicit `tc_name` support for Sales Order and Sales Invoice, while preserving existing Quotation support.
- Native Company selling Terms fallback when no explicit template is supplied.
- Rendered `terms` materialization for review/persistence using ERPNext-native controller behavior.
- Existing `custom_remarks` input support on Sales Order and Sales Invoice only.
- Approval preview additions needed to make the new values human-reviewable.
- REST/MCP parity for all changed public inputs.
- MCP instruction extraction/modularization and composition by profile.
- Relevant registry descriptions, generated docs, architecture docs, and tests.
- Semantic version update as described in the Versioning section.

### Out of scope

- No new Terms policy engine.
- No `policies/` package for Terms.
- No MCP Settings DocType or child table.
- No custom Company fields for per-document Terms defaults.
- No environment variables mapping Sales Order/Sales Invoice to specific Terms templates.
- No new Terms resolver/search/query tool in this task.
- No guessing Terms from template names such as `Order Terms` or `Invoice Terms`.
- No arbitrary email recipient support.
- No CC/BCC/multi-recipient feature.
- No creation of `custom_remarks` Custom Fields.
- No custom remarks support for Quotation unless current runtime metadata/source proves it is already an explicit requirement; otherwise keep it out of scope.
- No Delivery Note/Purchase Order authoring-field expansion.
- No changes to conversion workflows unless needed only to prevent a regression in native mapped values.
- No Desk-editable MCP instruction editor.
- No unrelated tool inventory, approval, identity, lifecycle, or resolver refactor.

---

## Inputs / Source of Truth

Inspect the current worktree before editing. The following paths were confirmed in the supplied source and are authoritative starting points.

### MCP bootstrap / instructions

```text
mcp_erpnext/mcp_server.py
mcp_erpnext/settings.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py
mcp_erpnext/profiles/accounts.py
mcp_erpnext/tests/test_tool_routing.py
```

### Email

```text
mcp_erpnext/contracts/email.py
mcp_erpnext/services/common/email.py
mcp_erpnext/tools/email.py
mcp_erpnext/remote_operations.py
mcp_erpnext/tests/test_email.py
mcp_erpnext/contracts/registry.py
docs/architecture/MCP_DOCUMENT_EMAIL.md
```

### Item Master

```text
mcp_erpnext/config/masters/item.py
mcp_erpnext/contracts/masters/item.py
mcp_erpnext/services/masters/item.py
mcp_erpnext/tools/masters/item.py
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_create_contracts.py
```

### Quotation

```text
mcp_erpnext/contracts/selling/quotation.py
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/tools/selling/quotation.py
mcp_erpnext/tests/test_quotation_service.py
mcp_erpnext/remote_operations.py
```

### Sales Order

```text
mcp_erpnext/contracts/selling/sales_order.py
mcp_erpnext/services/selling/sales_order.py
mcp_erpnext/tools/selling/sales_order.py
mcp_erpnext/tests/test_create_contracts.py
mcp_erpnext/remote_operations.py
```

If no focused Sales Order creation service test module exists, create one rather than forcing all service behavior into wrapper-only tests.

### Sales Invoice

```text
mcp_erpnext/contracts/selling/sales_invoice.py
mcp_erpnext/services/selling/sales_invoice.py
mcp_erpnext/tools/selling/sales_invoice.py
mcp_erpnext/tests/test_sales_invoice.py
mcp_erpnext/remote_operations.py
```

### Contract/documentation/version governance

```text
mcp_erpnext/contracts/registry.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_rest_backend.py
scripts/generate_tool_catalog.py
docs/TOOLS.md
mcp_erpnext/__init__.py
pyproject.toml
```

### Runtime metadata checks

Before implementing the authoring fields, inspect actual runtime metadata for:

```text
Item.description
Quotation Item.description
Sales Order Item.description
Sales Invoice Item.description
Quotation.tc_name
Quotation.terms
Sales Order.tc_name
Sales Order.terms
Sales Invoice.tc_name
Sales Invoice.terms
Sales Order.custom_remarks
Sales Invoice.custom_remarks
Company.default_selling_terms
```

Use actual fieldnames and fieldtypes. Do not rely on assumptions from this task if the installed runtime differs.

---

## Current State / Confirmed Evidence

### 1. Email is party-only today

`mcp_erpnext/services/common/email.py::_resolve_recipient()` resolves only business-party-linked email candidates and rejects unrelated addresses with `INVALID_RECIPIENT`.

`DocumentEmailPrepareInput` currently exposes:

```text
doctype
name
recipient_email
subject
message
print_format
letterhead
language
```

There is no recipient intent/scope field.

### 2. Item description is not currently authorable through the create contracts

- Item Master creation filters incoming values through `item_config.CREATION_FIELDS`.
- `description` is not in that tuple.
- Quotation and Sales Order row contracts do not expose description.
- Sales Invoice preview already reads native row description, but input normalization/build does not preserve an explicitly supplied description.

### 3. Terms support is uneven

- Quotation already accepts exact `tc_name`, permission-validates it, sets `doc.tc_name`, and previews `tc_name` / `terms`.
- Sales Order and Sales Invoice standalone create inputs do not expose Terms.
- The current server-side prepare flows do not intentionally implement the native SellingController onload fallback for `Company.default_selling_terms`.

### 4. `custom_remarks` already exists outside app source

The user has confirmed that `custom_remarks` already exists on Sales Order and Sales Invoice in the target ERPNext site. Therefore it must be treated as an optional existing runtime field, not as a schema migration owned by this task.

### 5. Server instructions are embedded in bootstrap

`mcp_erpnext/mcp_server.py` currently declares one cross-profile `MCP_ROUTING_INSTRUCTIONS` string containing both generic routing policy and Sales/Quotation-specific guidance. `create_mcp()` passes the same string to every profile.

---

## Frozen Strategy / Contract

## A. Document email recipient semantics

Keep the existing `prepare_document_email` / `confirm_document_email` pair. Do **not** add a second email tool pair.

Add a typed recipient scope with a backward-compatible default:

```text
recipient_scope: "party" | "self" = "party"
```

### `party`

Preserve current behavior exactly:

- resolve document `contact_email` / selected Contact / permitted Customer or Supplier email candidates;
- `recipient_email`, when supplied, may only select one of those valid associated candidates;
- unrelated arbitrary addresses remain rejected;
- ambiguous candidates continue to return `needs_input`.

### `self`

`self` means the **currently authenticated Frappe User**, not:

- document owner;
- Customer contact;
- Employee email inferred from another record;
- an arbitrary address typed by the user;
- an address selected from other Users.

Resolve exactly one email from the authenticated `User` record using an idiomatic Frappe server-side lookup. Validate it with the same email validation boundary used by the email service.

For `recipient_scope="self"`:

- `recipient_email` must not be used to override the authenticated user's address;
- prefer rejecting a supplied `recipient_email` as a conflicting/invalid combination rather than silently ignoring it;
- do not enumerate or disclose other User records;
- if the authenticated User has no valid email, return a safe public error and do not prepare approval.

The approval payload must bind both the resolved email and `recipient_scope`.

At confirm time:

- approval already binds the same authenticated site/user;
- for `party`, keep the existing recipient revalidation;
- for `self`, re-resolve the current authenticated User's email and require it to equal the prepared recipient;
- if it changed or is no longer valid, fail closed with the existing prepared-state/stale pattern and require a new prepare.

### LLM intent guidance

Server instructions must tell the model:

```text
"send to me" / "send to my email" / "send to myself"
    -> recipient_scope="self"

"send to client" / "send to customer" / "send to supplier" / "send to party"
    -> recipient_scope="party"
```

This interpretation belongs in MCP instructions. The service itself must enforce typed scope; it must not parse natural-language phrases.

---

## B. Description semantics

There are two distinct description levels and both must be supported.

### Item Master description

Add optional `description` to the controlled sales Item creation contract.

Behavior:

```text
explicit description supplied
    -> preserve it in the prepared Item payload and final Item creation

omitted
    -> do not manufacture or require one in MCP;
       allow native ERPNext/default behavior
```

The field remains optional even if some site derives/defaults it.

Update `item_config.CREATION_FIELDS` so the metadata-driven creation path can actually carry the field.

Preview the effective prepared Item description when present so the user can review authored text before confirmation.

### Transaction item-row description

Add optional item-row `description` to:

```text
QuotationItemInput
SalesOrderItemInput
SalesInvoiceItemInput
```

Behavior for all three:

```text
explicit description supplied
    -> put that description on that transaction item row

omitted
    -> do not set a blank override;
       let ERPNext populate the normal item-row description from Item/native defaults
```

Do not update the Item Master merely because a transaction row has a custom description.

The transaction description is document-specific content.

Approval previews must expose the resulting row description for Quotation, Sales Order, and Sales Invoice.

Sales Invoice already previews description; preserve that shape and make the input path capable of setting it.

Do not replace native `set_missing_values()` item behavior with a custom Item lookup/copy implementation.

---

## C. Terms and Conditions semantics

No Terms policy layer is being implemented in this version.

The deterministic priority is:

```text
1. Explicit user-selected tc_name
2. Company.default_selling_terms
3. Nothing
```

### Explicit template

If the user explicitly supplies `tc_name`:

- treat it as an exact Terms and Conditions document name;
- validate that exact template through permission-scoped server logic;
- do not fuzzy-match or infer another template;
- do not derive template choice from words such as `Order`, `Invoice`, `Domestic`, etc.;
- explicit input wins over Company default.

Quotation already has this public field. Preserve and harden the same semantics.

Add equivalent optional `tc_name` to standalone Sales Order and Sales Invoice preparation.

### No explicit template

If `tc_name` is omitted:

- use the selected/derived Company;
- apply ERPNext's native selling default semantics from `Company.default_selling_terms`;
- if Company has no default, leave `tc_name` / `terms` empty;
- do not prompt merely because multiple Selling Terms templates exist;
- do not select one from the template list.

### Native Terms rendering

Do not stop at storing only `tc_name`.

The prepare preview and final Draft should carry the same rendered `terms` content expected from native ERPNext behavior when a valid template is selected/defaulted.

After `tc_name` is determined, use the installed ERPNext controller's native `set_missing_terms()` seam (or the exact installed-version equivalent) when `terms` is empty.

Do not copy Jinja rendering/template expansion code into MCP.

Because current official ERPNext v16 code applies Company defaults in SellingController `onload`, and API/server-created documents may not automatically run the same path, implement the smallest source-backed adapter necessary for the MCP server-side prepare flow.

A small shared helper under `services/selling/` is allowed if it removes duplicated logic across Quotation, Sales Order, and Sales Invoice. It is a native-integration helper, **not** a policy layer.

### Preview

Quotation already previews:

```text
tc_name
terms
```

Add the same human-reviewable fields to Sales Order and Sales Invoice previews.

### No new public Terms tool

This task must not add:

```text
resolve_terms_and_conditions
search_terms_and_conditions
query_terms_and_conditions
```

If a future requirement needs template discovery, treat that as a separate capability decision.

### MCP instruction guidance

Sales profile instructions must state:

- pass `tc_name` only when the user explicitly chose/specified the template;
- otherwise omit it and let the server apply Company default/no-default behavior;
- never guess a Terms template from names or document type.

---

## D. Existing `custom_remarks` semantics

The field already exists on the target site. **Do not create it.**

Add optional `custom_remarks` to:

```text
SalesOrderPrepareInput
SalesInvoicePrepareInput
```

Do not add it to Quotation in this task.

Behavior:

```text
custom_remarks omitted
    -> no effect

custom_remarks supplied and runtime field exists
    -> set it on the prepared document
    -> show it in approval preview
    -> preserve it into confirmed Draft

custom_remarks supplied but runtime field does not exist
    -> fail closed with a safe existing public-error pattern
    -> never silently drop the user's text
```

Before setting the field, inspect runtime metadata with `frappe.get_meta()` / `has_field()` or the installed equivalent.

Do not create Custom Fields, fixtures, patches, property setters, or migrations for this requirement.

Do not directly depend on field placement in the Desk form. Only the exact fieldname matters to MCP.

---

## E. MCP instruction modularization

Instructions remain **source-controlled code**, not Desk-editable business configuration.

Remove the large source-of-truth instruction body from `mcp_erpnext/mcp_server.py`.

Create a dedicated instruction package with minimal separation by responsibility. Recommended structure:

```text
mcp_erpnext/instructions/__init__.py
mcp_erpnext/instructions/base.py
mcp_erpnext/instructions/sales.py
```

Do not create empty Purchase/Accounts files solely for symmetry. Add profile modules only when they have actual profile-specific guidance.

### `base.py`

Own cross-profile guidance such as:

- get vs resolve vs search vs query vs aggregate routing;
- resolver terminal-state behavior;
- prepare -> preview/approval -> confirm;
- no duplicate semantically equivalent verification calls;
- response precision;
- document email `party` vs `self` intent guidance because email exists across current Sales/Purchase profiles.

### `sales.py`

Own Sales-specific guidance such as:

- Quotation `valid_till` server default behavior;
- Sales Terms explicit-template vs Company-default behavior;
- no Terms guessing.

### `instructions/__init__.py`

Expose one small composition API such as:

```text
get_mcp_instructions(profile)
```

It should return:

```text
base instructions
+
only the selected profile's real profile-specific instructions
```

`mcp_server.py` should become a consumer only:

```text
instructions=get_mcp_instructions(settings.profile)
```

Avoid circular imports. If the instruction composer accepts the profile enum, place dependencies so bootstrap remains simple and testable.

Do not preserve a second independently editable copy of the old instruction text in `mcp_server.py`.

If a compatibility alias is genuinely needed for internal imports, it may re-export from the new module, but the source of truth must be the dedicated instruction package.

### Profile correctness

Current Quotation-specific guidance is sent to every profile. After this refactor:

- common routing/response rules remain available to all profiles;
- Sales-only rules are present only in Sales server instructions;
- Purchase/Accounts must not receive irrelevant Quotation authoring guidance.

Update `test_tool_routing.py` accordingly. Tests should assert the composition API rather than forcing all profiles to equal one global string.

---

## Allowed Changes

The implementer may change/add the following areas when necessary for this task.

### New instruction source

```text
mcp_erpnext/instructions/
```

### Existing code

```text
mcp_erpnext/mcp_server.py
mcp_erpnext/config/masters/item.py
mcp_erpnext/contracts/email.py
mcp_erpnext/contracts/masters/item.py
mcp_erpnext/contracts/selling/quotation.py
mcp_erpnext/contracts/selling/sales_order.py
mcp_erpnext/contracts/selling/sales_invoice.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/services/common/email.py
mcp_erpnext/services/masters/item.py
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/services/selling/sales_order.py
mcp_erpnext/services/selling/sales_invoice.py
mcp_erpnext/services/selling/<small shared terms helper if source-backed and useful>
mcp_erpnext/tools/email.py
mcp_erpnext/tools/selling/quotation.py
mcp_erpnext/tools/selling/sales_order.py
mcp_erpnext/tools/selling/sales_invoice.py
mcp_erpnext/remote_operations.py
mcp_erpnext/__init__.py
```

Item tool wrapper changes are allowed only if required by the typed contract/payload change; the existing `ItemPrepareInput.to_service_payload()` path should otherwise be reused.

### Tests

Modify focused existing tests and add a narrowly scoped Sales Order creation service test file if required.

### Docs

```text
docs/TOOLS.md
docs/architecture/MCP_DOCUMENT_EMAIL.md
```

Update another existing architecture/profile doc only when the implementation changes information it currently states. Do not rewrite unrelated docs.

---

## Forbidden / Preserve

Preserve all of the following:

- Existing public tool names.
- Existing profile membership/tool count unless schema-only changes naturally regenerate docs; this task adds no tools.
- Existing approval-token store and trusted approval policy.
- Existing authenticated site/user binding.
- Existing two-phase prepare/confirm semantics.
- Existing permission-scoped Customer, Item, Contact, Company, PDF, and email behavior.
- Existing party-email security rules when `recipient_scope="party"`.
- Native ERPNext validation/calculation hooks.
- Native Item defaults when description is omitted.
- Native document conversion behavior.
- Existing REST remote-operation architecture.
- `custom_remarks` as a site-owned field, not app-owned schema.
- No `ignore_permissions=True` workaround.
- No direct SQL for any of these features.
- No arbitrary `setattr` from unbounded model input.
- No hard-coded Terms template names.
- No ENV-based Terms mapping.
- No Terms policy folder/engine.
- No new Frappe DocType for this task.

Do not edit ERPNext/Frappe core files.

---

## Implementation Steps

### Step 1 — Re-verify current worktree and installed metadata

Before editing:

1. confirm all inspected paths still match the working tree;
2. inspect runtime metadata for the fields listed in Inputs / Source of Truth;
3. inspect installed ERPNext implementations of:
   - selling document `onload` Terms behavior;
   - `set_missing_terms()`;
   - Item/transaction description fields;
4. record any difference from this task in the implementation report before changing strategy.

Do not redesign if the inspected runtime confirms the frozen contract.

### Step 2 — Modularize MCP instructions first

Extract current generic instructions and Sales-specific text into the dedicated package.

Keep wording semantically equivalent unless this task explicitly adds the new recipient/Terms guidance.

Wire `create_mcp()` to `get_mcp_instructions(settings.profile)`.

Update routing tests so:

- each profile receives common policy;
- Sales receives Quotation + Terms guidance;
- non-Sales profiles do not receive Sales-only authoring guidance;
- governed tool descriptions remain sourced from `ToolContract` registry.

### Step 3 — Add email `recipient_scope`

Update `DocumentEmailPrepareInput` with the backward-compatible typed scope.

Refactor email resolution into clearly separated internal paths, for example conceptually:

```text
_resolve_party_recipient(...)
_resolve_self_recipient(...)
```

Do not make natural-language parsing part of service code.

Update:

- MCP wrapper call;
- REST handler call;
- approval payload;
- preview;
- confirm-time recipient revalidation.

Only add a preview field for scope if it improves human review without breaking current public shape. At minimum the exact recipient remains visible. Prefer exposing `recipient_scope` in the preview if contract compatibility permits because the approval intent becomes explicit.

### Step 4 — Add Item Master description

Update:

- `ItemPrepareInput`;
- `item_config.CREATION_FIELDS`;
- Item preview contract/service;
- focused wrapper/service tests.

Do not make description mandatory.

Verify metadata-driven creation accepts the runtime Text Editor/Data field without bypassing shared field-resolution rules.

### Step 5 — Add transaction row descriptions

For Quotation, Sales Order, Sales Invoice:

- add optional input field;
- preserve it through wrapper/REST/service normalization;
- when explicitly supplied, include it in the child-row payload passed to ERPNext;
- when omitted, omit the key entirely so native defaulting can run;
- preview the resulting effective row description.

Do not write to Item Master from this path.

### Step 6 — Implement shared native selling Terms application

Implement the smallest source-backed common helper if useful.

Conceptual responsibility:

```text
apply_selling_terms(doc, explicit_tc_name)
```

It must:

1. validate an explicit exact `Terms and Conditions` name under normal permission visibility;
2. use explicit name when supplied;
3. otherwise obtain the Company's `default_selling_terms` using the same native source ERPNext uses;
4. if neither exists, leave Terms blank;
5. when `tc_name` exists and `terms` is empty, call native `doc.set_missing_terms()` or exact installed-version equivalent;
6. return a safe error instead of raising/leaking raw internals when the explicit template is invalid/not permitted;
7. never fuzzy-search or guess a template.

Apply consistently to Quotation, Sales Order, and standalone Sales Invoice before approval preview/fingerprint creation.

Preserve Quotation's current valid explicit `tc_name` behavior while consolidating only where safe.

### Step 7 — Add Sales Order/Sales Invoice Terms contract fields

Add optional `tc_name` to the prepare contracts/wrappers/REST service path.

Add `tc_name` and rendered `terms` to approval previews.

Do not require the model/user to provide Terms when omitted.

### Step 8 — Add existing `custom_remarks`

Add optional `custom_remarks` to Sales Order and Sales Invoice prepare contracts.

At prepare time:

- only inspect runtime `custom_remarks` metadata if the value was supplied;
- if field is absent, fail closed with a safe public error;
- if present, set the value before preview/fingerprint/token creation.

Add it to previews.

For Sales Order, ensure `_safe_doc_data()` includes the reviewed field naturally.

For Sales Invoice, ensure normalized request + preview + fingerprint bind the reviewed field so confirmation cannot silently change/drop it.

### Step 9 — Preserve confirm safety

For all changed create flows verify that confirmation creates exactly the approved effective values.

- Quotation/Sales Order payload replay must preserve description, terms, and custom remarks where applicable.
- Sales Invoice rebuild/fingerprint must include all newly authorable inputs/effective preview values.
- Email confirmation must revalidate scope and recipient.

Do not weaken stale-state detection to make tests pass.

### Step 10 — Update governed descriptions/docs

Update the central `ToolContract` descriptions only where the new behavior materially affects model routing, especially `prepare_document_email`.

Regenerate `docs/TOOLS.md` with the existing generator; do not hand-maintain generated sections when the project generator owns them.

Update `docs/architecture/MCP_DOCUMENT_EMAIL.md` for `party` vs `self`.

Document Terms behavior in the most relevant existing architecture/tool doc only if current docs would otherwise be misleading.

### Step 11 — Versioning

This task adds backward-compatible user-facing capabilities, so under the project's SemVer rule it is a **MINOR** change.

The inspected source currently reports:

```text
mcp_erpnext/__init__.py -> 0.0.1
```

If no newer release/version baseline has been established in the actual worktree before implementation, update the app version to:

```text
0.1.0
```

Do not invent or retroactively rewrite historical Git tags in this task.

If the worktree already has a newer version because version reconstruction/release work occurred after the supplied ZIP, apply a MINOR bump from that actual current version instead and record it in the report.

Keep source version metadata consistent with the repository's existing dynamic-version mechanism.

Do not push/create a release tag unless the established project workflow explicitly includes that action; report the intended SemVer release/tag separately.

---

## Safety / Compatibility Requirements

### Backward compatibility

Existing callers that do not send any new fields must continue to work.

Specifically:

```text
prepare_document_email(... no recipient_scope ...)
```

must behave exactly like current party-recipient behavior.

Existing Quotation requests without description/terms changes must remain valid.

Existing Sales Order / Sales Invoice requests without new fields must remain valid.

### Permissions

- Terms template validation must not bypass normal read visibility.
- `self` email lookup must reveal only the authenticated User's own email.
- `party` resolution must preserve existing Customer/Supplier/Contact permission checks.
- Create/confirm document permissions remain unchanged.

### Data exposure

Do not expose full User documents, Contact rows, Terms documents, or unrelated custom fields in tool output.

Return only the bounded values required for preview/error handling.

### Approval integrity

All new user-authored/effective values that influence the final document/email must be bound to the approval state.

### Native ownership

ERPNext remains authoritative for:

- pricing and tax calculation;
- Item defaults;
- transaction item defaults;
- Terms template rendering;
- Company default selling Terms;
- document validation and insert hooks;
- email queue behavior.

MCP controls only the bounded authoring intent and safety envelope.

---

## Acceptance Criteria

Task 66 is complete only when all of the following are demonstrably true.

### Email

1. Existing default email behavior remains party-scoped.
2. `recipient_scope="self"` sends only to the authenticated User's valid email.
3. `recipient_scope="self"` cannot be converted into arbitrary-email sending via `recipient_email`.
4. `recipient_scope="party"` still rejects unrelated addresses.
5. Confirm revalidates the same scope and recipient.
6. `send to me` vs `send to client/customer/supplier` intent is represented in server instructions, not parsed in the email service.

### Description

7. Item Master creation optionally accepts description and persists it when supplied.
8. Item Master description remains optional.
9. Quotation item row optionally accepts description.
10. Sales Order item row optionally accepts description.
11. Sales Invoice item row optionally accepts description.
12. Explicit transaction description is visible in preview and final Draft.
13. Omitted transaction description allows ERPNext's native item description/default behavior rather than writing blank text.
14. Transaction description does not mutate Item Master.

### Terms

15. Quotation continues to accept explicit exact `tc_name`.
16. Sales Order accepts explicit exact `tc_name`.
17. Sales Invoice accepts explicit exact `tc_name`.
18. Explicit `tc_name` overrides Company default.
19. With no explicit `tc_name`, Company `default_selling_terms` is applied when configured.
20. With neither explicit nor Company default, Terms remain empty and MCP does not guess.
21. The effective `tc_name` and rendered `terms` are visible in prepare preview.
22. The confirmed Draft preserves the approved effective Terms.
23. No Terms resolver/search tool, policy engine, Settings DocType, custom Company field, or ENV mapping is added.

### `custom_remarks`

24. Existing Sales Order `custom_remarks` can be supplied, previewed, and persisted.
25. Existing Sales Invoice `custom_remarks` can be supplied, previewed, and persisted.
26. No Custom Field is created/migrated by this task.
27. If the input is supplied on a runtime where the field is absent, the request fails safely instead of silently dropping it.

### Instructions / architecture

28. `mcp_server.py` no longer owns the large editable instruction body.
29. Common instructions are centralized under the new instruction package.
30. Sales-only authoring guidance is composed only into the Sales profile.
31. All profiles retain the cross-profile routing/response policy.
32. Public tool names/profile memberships remain unchanged.
33. MCP and REST expose equivalent new input semantics.
34. Generated tool documentation is current.
35. All focused and regression tests pass.
36. Version metadata follows the MINOR-bump rule from the actual current baseline.

---

## Tests / Verification

Do not claim these tests passed unless they are actually run.

### A. Instruction tests

Update/add assertions for:

- base instructions available in Sales/Purchase/Accounts;
- Sales Quotation guidance only in Sales;
- Sales Terms no-guess guidance only in Sales;
- email `self` / `party` routing guidance available wherever document email is exposed;
- `mcp_server.py` consumes the composer;
- tool registry descriptions remain governed.

Primary file:

```text
mcp_erpnext/tests/test_tool_routing.py
```

### B. Email tests

Cover at minimum:

- omitted scope -> existing party recipient;
- `party` with one native document contact;
- `party` ambiguity unchanged;
- `party` unrelated explicit address rejected;
- `self` resolves authenticated User email;
- `self` does not read another User;
- `self` + `recipient_email` conflict rejected;
- `self` with missing/invalid authenticated User email rejected;
- confirm self after unchanged User email queues successfully;
- confirm self after User email changes fails prepared-state validation;
- existing document/PDF stale checks remain intact;
- purchase-profile email self scope works for an allowed Purchase Order without weakening profile boundaries.

Primary file:

```text
mcp_erpnext/tests/test_email.py
```

### C. Item Master description tests

Cover:

- contract accepts optional description;
- `to_service_payload()` carries it;
- metadata-driven creation carries it when runtime field exists;
- preview exposes it;
- final created Item payload/doc includes it;
- omission does not create a false mandatory requirement.

Primary files:

```text
mcp_erpnext/tests/test_item_service.py
mcp_erpnext/tests/test_create_contracts.py
```

### D. Quotation tests

Cover:

- explicit row description survives prepare and preview;
- omitted row description receives native/default description in the fake/native seam without MCP forcing blank;
- explicit Terms exact template wins;
- no explicit Terms + Company default -> effective `tc_name` + rendered `terms`;
- no explicit Terms + no Company default -> blank;
- invalid/unpermitted explicit Terms fails safely;
- confirm persists approved description/Terms.

Primary file:

```text
mcp_erpnext/tests/test_quotation_service.py
```

### E. Sales Order tests

Add focused service tests if necessary for:

- description explicit/omitted behavior;
- explicit Terms;
- Company default Terms;
- no Terms fallback;
- rendered terms preview;
- custom remarks present field;
- custom remarks field missing + value supplied -> safe failure;
- preview includes description, `tc_name`, `terms`, `custom_remarks`;
- confirm persists approved values;
- existing customer/item/default calculations remain unchanged.

Also update wrapper/contract tests to verify arguments reach the service exactly once.

### F. Sales Invoice tests

Cover:

- explicit item description is normalized/build-preserved;
- omitted item description remains native-driven;
- explicit Terms and default Terms behaviors;
- rendered terms preview;
- custom remarks runtime-field behavior;
- fingerprint/stale rebuild includes the new values;
- confirmed Draft matches reviewed preview.

Primary file:

```text
mcp_erpnext/tests/test_sales_invoice.py
```

### G. MCP/REST contract parity

Update/run relevant tests for:

```text
mcp_erpnext/tests/test_create_contracts.py
mcp_erpnext/tests/test_tool_contracts.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_rest_backend.py
mcp_erpnext/tests/test_profiles.py
```

Verify the same typed fields work through remote-operation dispatch and direct MCP wrappers.

### H. Tool catalog generation

Run the existing catalog generator/check and ensure `docs/TOOLS.md` matches the current contracts.

### I. Runtime/live verification

On an authorized test site only, verify runtime metadata and perform non-destructive prepare previews for:

1. Quotation with explicit item description and explicit Terms;
2. Sales Order with description + `custom_remarks` and no explicit Terms while Company default is configured;
3. Sales Invoice with explicit Terms + `custom_remarks`;
4. email prepare with `recipient_scope="self"`;
5. email prepare with `recipient_scope="party"`.

Do not send a real external email or create a real business document in live production merely to satisfy this task unless separately authorized.

If a safe test site is available and creation is authorized, confirm Draft persistence there and report document names separately.

---

## Expected Results

After completion, conversational examples should map as follows.

### Email

```text
User: "Send SAL-ORD-2026-00014 to me"
LLM -> prepare_document_email(recipient_scope="self", ...)
Server -> authenticated User email only

User: "Send this invoice to the client"
LLM -> prepare_document_email(recipient_scope="party", ...)
Server -> existing linked Customer/Contact resolution
```

### Item description

```text
Create Item with description X
    -> Item.description = X

Create Quotation item with description Y
    -> Quotation Item.description = Y
    -> Item Master unchanged

Create Sales Order without item description
    -> MCP omits description override
    -> ERPNext native row description/default applies
```

### Terms

```text
User explicitly specifies "Special Export Terms"
    -> exact template validated and applied

No explicit template + Company.default_selling_terms exists
    -> native Company default applied and rendered

No explicit template + no Company default
    -> no Terms
```

### Custom remarks

```text
prepare_sales_order(..., custom_remarks="Internal/customer-facing note...")
    -> preview shows it
    -> confirmed Draft preserves it
```

### Instructions

```text
mcp_server.py
    -> server bootstrap only
    -> gets instructions from dedicated instruction package

Sales profile
    -> common + Sales guidance

Purchase/Accounts profiles
    -> common guidance only unless real profile-specific guidance exists
```

---

## Limitations / Risks

### Terms source/runtime differences

ERPNext Terms behavior has changed over versions and is partly tied to Desk/onload/print controller seams. Therefore the implementer must verify the installed source and tests must prove both `tc_name` and rendered `terms`, not just one field.

Do not work around an installed-version ERPNext defect by hard-coding template HTML into MCP.

### Custom field portability

`custom_remarks` is not a standard ERPNext field. The generic MCP app will expose an optional capability that only works when that runtime field exists. The safe absent-field failure is required to keep installations without that customization predictable.

### Terms per-document business defaults

Separate automatic defaults such as:

```text
Sales Order -> Order Terms
Sales Invoice -> Invoice Terms
```

are intentionally **not** implemented now. Future business-specific policy/configuration can be designed separately if needed.

### Email self semantics

`self` is intentionally only the authenticated Frappe User. This task does not support aliases, Employee personal email, arbitrary addresses, forwarding groups, CC, or BCC.

### Instruction maintenance

The new instruction package makes source maintenance cleaner but does not make instructions runtime-editable. Any future Desk-managed instruction/configuration system is a separate architecture decision.

---

## Implementation Report

Create exactly:

```text
docs/inspect/25-09-2026/SALES_DOCUMENT_AUTHORING_EMAIL_RECIPIENT_TERMS_AND_MCP_INSTRUCTIONS_IMPLEMENTATION_REPORT.md
```

The report must include:

1. **Source baseline inspected**
   - branch/commit if available;
   - `mcp_erpnext` version before/after;
   - Frappe/ERPNext versions used for runtime/native-source verification.

2. **Runtime metadata evidence**
   - exact fieldnames/types found for description, Terms, `custom_remarks`, Company default field.

3. **Files changed/added**
   - complete list with one-line purpose.

4. **Instruction architecture result**
   - final instruction files;
   - composition behavior by profile;
   - confirmation that `mcp_server.py` no longer owns the large source text.

5. **Email result**
   - `party` semantics;
   - `self` source of email;
   - confirmation revalidation;
   - arbitrary-recipient protections.

6. **Description result**
   - Item Master;
   - Quotation row;
   - Sales Order row;
   - Sales Invoice row;
   - omitted-vs-explicit behavior.

7. **Terms result**
   - explicit template path;
   - Company default path;
   - no-default path;
   - native rendering method used;
   - proof that preview/persisted Draft contains expected `tc_name` / `terms`.

8. **Custom remarks result**
   - no field creation performed;
   - runtime metadata check;
   - Sales Order/Sales Invoice preview and persistence.

9. **Transport parity**
   - MCP wrapper behavior;
   - REST/remote-operation behavior.

10. **Tests actually run**
    - exact commands;
    - pass/fail counts;
    - no generic claim such as "all tests pass" without evidence.

11. **Live/runtime checks actually run**
    - distinguish metadata-only, prepare-preview, draft creation, and email queue actions;
    - list any actions deliberately not run because they would be externally consequential.

12. **Generated docs check**
    - catalog generator result;
    - docs changed.

13. **Versioning**
    - old version;
    - new version;
    - why MINOR classification applies;
    - intended Git tag if release/tagging happens separately.

14. **Acceptance criteria matrix**
    - each criterion number -> evidence/test.

15. **Deviations / unresolved items**
    - explicitly list any task requirement not implemented and why.

16. **Resulting project state**
    - enough context for a new reviewer to continue without this chat.

---

## Handover Completeness Check

Before marking implementation complete, verify that a reviewer who has not read the conversation can determine from the task + report:

- what changed and why;
- which behavior is generic vs site-customized;
- that `custom_remarks` was not created by the app;
- how Terms fallback works;
- that no per-document Terms policy/configuration was introduced;
- where MCP instructions now live;
- how `send to me` differs from `send to client`;
- how description omission differs from an explicit row description;
- which tests and runtime checks actually proved the result;
- what version the repository is left at.

If any of those requires hidden chat context, the handoff is incomplete.

---

## Exact Next Handoff

Implement **Task 66 only** and return this exact report for review:

```text
docs/inspect/25-09-2026/SALES_DOCUMENT_AUTHORING_EMAIL_RECIPIENT_TERMS_AND_MCP_INSTRUCTIONS_IMPLEMENTATION_REPORT.md
```

Do not start a Terms policy/Settings task, new email capability, or another follow-up feature after Task 66. After the implementation report is returned, the reviewer will inspect the actual changed source and tests, decide whether correction is required or the capability is complete, and only then provide the Git commit message if accepted.
