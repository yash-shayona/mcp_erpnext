# Task 26 - Sales Invoice Native Flow Inspection and Architecture Freeze

## Status

Inspection / R&D only. No Sales Invoice implementation is authorized by this task.

## Purpose

Inspect the current `mcp_erpnext` implementation and the exact installed Frappe / ERPNext / India Compliance behavior required to add Sales Invoice capabilities safely.

This task must produce evidence for two distinct future creation paths:

1. Sales Order -> Sales Invoice native conversion.
2. Direct / standalone Sales Invoice creation without a Sales Order when ERPNext policy permits it.

Do not collapse these into one generic create-invoice implementation. They have different source-of-truth, validation, eligibility, stale-state, and business-control requirements.

The inspection must also determine how an existing Sales Invoice should later participate in shared read, PDF, email, update, submit, cancel, and delete capabilities without accidentally exposing unsafe accounting mutations.

---

# 1. Frozen Project Context

The project currently uses one `mcp_erpnext` Frappe app with profile-specific MCP servers. Sales Invoice belongs to the existing `sales` profile. Do not create a new Frappe app, a separate invoice MCP server, or an accounts profile merely for Sales Invoice.

Current architectural principles that must remain intact:

- Public business creation / conversion tools are explicit per business capability.
- Genericity belongs mainly in shared internal mechanics.
- Existing shared lifecycle tools remain generic, but capability exposure must be controlled by strict profile / DocType / action policy.
- Normal Frappe permissions and document lifecycle remain authoritative.
- Do not use `ignore_permissions=True`, Administrator fallback, or hidden privileged writes.
- Prepare and confirm remain separate for writes that need explicit approval.
- Approval state remains bound to the current site, user, action, and prepared payload according to the existing approval service.
- Runtime DocType metadata is authoritative for installed Custom Fields and Property Setters.
- Optional apps such as India Compliance must be detected at runtime and must not become hard dependencies of an ERPNext-only site.
- Prefer ERPNext / Frappe native helpers, mappers, defaults, and validation over copied business logic.
- Do not duplicate ERPNext tax, accounting, stock, GST, pricing, credit-limit, or status-update logic in MCP.
- Keep MCP standalone and client-neutral. Do not make the server depend on LibreChat, LangGraph, a coordinator agent, or any other particular MCP client.

The most recent implemented conversion pattern to inspect is Quotation -> Sales Order. The previous implementation intentionally did not include Sales Order -> Sales Invoice and identified that conversion as a future capability candidate.

---

# 2. Objective

By the end of this task, produce one evidence-based audit report that answers all of the following questions before any Sales Invoice code is added:

1. What Sales Invoice capability is already indirectly supported by existing generic MCP services, and what is not supported at all?
2. What exact current `mcp_erpnext` files, contracts, policies, registries, profile registrations, tests, and generated docs would be affected by Sales Invoice support?
3. What is ERPNext's exact native Sales Order -> Sales Invoice path in the installed version?
4. What source eligibility rules does the native mapper enforce or depend on?
5. How does native mapping handle partially billed Sales Orders, previously billed quantities, returns, Delivery Notes, stock items, service items, source row references, taxes, pricing, payment schedule, addresses, accounts, and totals?
6. Which mapped target values are safe and stable enough to include in MCP preview and stale-confirmation fingerprints?
7. Can prepare safely call the native mapper only, or mapper + Sales Invoice validation, without causing writes, external API calls, queued jobs, or other side effects?
8. What does `Sales Invoice.validate()` do in the installed ERPNext version, including inherited controller behavior and installed-app hooks?
9. What does `Sales Invoice.on_submit()` do, especially GL, outstanding, stock ledger, Sales Order billing state, Delivery Note state, project, loyalty, credit checks, and other downstream changes?
10. What does cancellation reverse or update?
11. What linked-document behavior can block cancel or delete?
12. What is the correct native path for direct / standalone Sales Invoice creation with no Sales Order?
13. Which direct-invoice fields should MCP request from the user, which can be resolved from metadata/defaults/native helpers, and which must never be arbitrarily exposed?
14. How do Selling Settings and Customer-level exceptions control whether a direct Sales Invoice is allowed without Sales Order and/or Delivery Note?
15. Should standalone V1 support stock-updating invoices, POS, returns / credit notes, debit notes, timesheet billing, project billing, advances, subscriptions, or consolidated invoices? Give evidence-based decisions for each.
16. What India Compliance behavior attaches to Sales Invoice and Sales Invoice Item when the app is installed?
17. Which GST-related custom fields, validation hooks, tax behavior, e-invoice/e-waybill hooks, place-of-supply rules, GSTIN rules, HSN/SAC rules, reverse-charge/export rules, or other India-specific behavior matters during prepare, insert, submit, cancel, and print?
18. What must happen when India Compliance is not installed?
19. Can the current generic lifecycle allowlist safely add `Sales Invoice`, or would that also unintentionally enable generic update / child-row mutation?
20. Does lifecycle policy need to become action-scoped before Sales Invoice is added?
21. What safe subset of Sales Invoice fields, if any, may later be editable through MCP on Draft invoices?
22. Should submitted Sales Invoice updates be supported at all through the existing generic update tool? If not, identify the correct boundary.
23. How should Sales Invoice be added to generic read/search, PDF, and email services?
24. What exact public tools should Task 27, Task 28, and Task 29 implement?
25. What unit, static, and live verification matrix is required for those implementation tasks?

Do not answer these from memory. Trace the current local source and runtime behavior.

---

# 3. Inputs and Evidence Sources

## 3.1 Current `mcp_erpnext` working tree

Inspect the actual working tree present when this task is executed. Do not assume the attached/archive snapshot is newer than the live repository.

At minimum inspect:

```text
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/tools/selling/**
mcp_erpnext/services/selling/**
mcp_erpnext/contracts/selling/**
mcp_erpnext/contracts/registry.py
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/tools/lifecycle.py
mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/contracts/lifecycle.py
mcp_erpnext/tools/read.py
mcp_erpnext/services/common/read.py
mcp_erpnext/contracts/read.py
mcp_erpnext/tools/pdf.py
mcp_erpnext/services/common/pdf.py
mcp_erpnext/contracts/pdf.py
mcp_erpnext/tools/email.py
mcp_erpnext/services/common/email.py
mcp_erpnext/contracts/email.py
mcp_erpnext/tests/**
docs/TOOLS.md
docs/MCP_PROFILES.md
docs/architecture/**
docs/inspect/QUOTATION_TO_SALES_ORDER_NATIVE_CONVERSION_IMPLEMENTATION_REPORT.md
```

Also inspect any Task 22-25 changes already present in the real working tree. Preserve them. Do not infer the current state only from older ZIP files.

## 3.2 Existing MCP patterns that must be compared

Trace and document the current call flow of:

```text
prepare_quotation -> confirm_quotation
prepare_sales_order -> confirm_sales_order
prepare_quotation_to_sales_order -> confirm_quotation_to_sales_order
prepare_document_update -> confirm_document_update
prepare_document_submit -> confirm_document_submit
prepare_document_cancel -> confirm_document_cancel
prepare_document_delete -> confirm_document_delete
get_document / search_documents
prepare_document_pdf
prepare_document_email -> confirm_document_email
```

The point is not to copy these blindly. The point is to identify which existing mechanism is correct for Sales Invoice and where invoice accounting risk requires a narrower policy.

## 3.3 Exact installed Frappe / ERPNext source

Inspect the exact installed code, not only online documentation. At minimum trace relevant code under paths such as:

```text
apps/erpnext/erpnext/selling/doctype/sales_order/**
apps/erpnext/erpnext/accounts/doctype/sales_invoice/**
apps/erpnext/erpnext/controllers/**
apps/erpnext/erpnext/selling/doctype/customer/**
apps/erpnext/erpnext/stock/doctype/delivery_note/**
apps/erpnext/erpnext/stock/**
apps/erpnext/erpnext/accounts/**
apps/frappe/frappe/model/document.py
apps/frappe/frappe/model/mapper.py
```

Do not assume the native mapper lives in a particular file because ERPNext code layout can differ by version. Find the exact callable used by the installed version.

Official version-16 source and official ERPNext docs may be used as secondary evidence, but the installed source is authoritative for implementation design.

## 3.4 India Compliance

If `india_compliance` is installed on the inspected site, inspect its exact installed source and runtime metadata.

At minimum inspect:

```text
apps/india_compliance/india_compliance/hooks.py
apps/india_compliance/india_compliance/gst_india/**
```

Search for every Sales Invoice / Sales Invoice Item integration, including:

```text
Sales Invoice
Sales Invoice Item
doc_events
override_doctype_class
override_whitelisted_methods
custom_fields
validate
before_validate
before_save
on_submit
on_cancel
GST Settings
gstin
place_of_supply
gst_category
gst_hsn_code
reverse_charge
export
e_invoice
e_waybill
IRN
```

Do not assume every India Compliance feature runs during ordinary invoice creation. Trace exact hooks and conditions.

If India Compliance is absent from another available ERPNext-only site, compare runtime metadata and installed-app behavior between the two sites without writing data.

---

# 4. Allowed Changes

This is an inspection-only task.

The only repository file that may be created or modified is:

```text
docs/inspect/SALES_INVOICE_NATIVE_FLOW_AUDIT.md
```

If the repository already uses a different exact naming convention under `docs/inspect`, follow that convention but create only one inspection report.

No production Python code, contracts, tests, profile registration, generated tool catalog, hooks, fixtures, migrations, or site data may be changed.

---

# 5. Explicitly Forbidden Changes

Do not modify:

```text
mcp_erpnext/**.py
mcp_erpnext/contracts/**
mcp_erpnext/services/**
mcp_erpnext/tools/**
mcp_erpnext/profiles/**
mcp_erpnext/tests/**
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py
docs/TOOLS.md
apps/erpnext/**
apps/frappe/**
apps/india_compliance/**
```

Do not:

- create a Sales Invoice;
- submit, cancel, amend, return, or delete an invoice;
- create GL Entries or Stock Ledger Entries;
- call a production GST/e-invoice/e-waybill API;
- consume India Compliance API credits;
- enqueue side-effecting compliance jobs merely to inspect behavior;
- change Selling Settings, Accounts Settings, GST Settings, Customer settings, Company defaults, permissions, roles, or Custom Fields;
- run migrations;
- run fixtures;
- run build/yarn commands;
- change approval mode;
- add temporary permission bypasses;
- use Administrator as an execution fallback;
- implement Sales Invoice tools in this task.

---

# 6. Inspection Method

## Step 1 - Establish actual repository state

Record:

- current git branch / revision if available;
- relevant changed/untracked files;
- installed `mcp_erpnext` code structure;
- current sales profile tool registration;
- current generated tool inventory;
- whether any Sales Invoice-specific code already exists.

Do not clean/reset/stash the worktree.

## Step 2 - Establish exact app/runtime versions

Record the exact installed versions of:

- Frappe;
- ERPNext;
- India Compliance, if installed;
- `mcp_erpnext`;
- `mcp_identity` where relevant to request context.

Also record the inspected site's installed-app list using a read-only method.

Do not treat `apps.txt` or the presence of an app directory alone as proof that the app is installed on a site.

## Step 3 - Trace current Sales profile architecture

Produce a call/registration map showing how the Sales profile currently exposes:

- Customer / Item tools;
- Quotation tools;
- Sales Order tools;
- Quotation -> Sales Order conversion;
- generic lifecycle;
- generic read/search;
- PDF;
- email.

Identify all separate allowlists / DocType registries currently used by these services.

Important: inspect whether a single `Sales Invoice` addition to any shared allowlist would expose more actions than intended.

## Step 4 - Audit generic lifecycle policy before adding Sales Invoice

Inspect the current lifecycle service in detail.

Build a matrix like:

| Action | Quotation | Sales Order | Customer | Item | Potential Sales Invoice consequence |
|---|---|---|---|---|---|
| update | current behavior | current behavior | current behavior | current behavior | inspect |
| child_add | current behavior | current behavior | N/A | N/A | inspect |
| submit | current behavior | current behavior | N/A/blocked | N/A/blocked | inspect |
| cancel | current behavior | current behavior | N/A/blocked | N/A/blocked | inspect |
| delete | current behavior | current behavior | current behavior | current behavior | inspect |

Determine whether current policy is:

- profile/DocType-scoped only;
- action-scoped;
- field-scoped;
- DocType+action+field scoped.

If adding Sales Invoice to one profile DocType set would automatically allow generic updates or child-row additions, flag that as an architecture blocker. Do not fix it in this task.

The report must recommend the smallest policy change needed before Sales Invoice is added to shared lifecycle.

## Step 5 - Locate and trace the native Sales Order -> Sales Invoice mapper

Find the exact installed public/native ERPNext callable used to create a Sales Invoice from a Sales Order.

Document:

- function path and signature;
- whether it is whitelisted;
- source permission behavior;
- source docstatus requirement;
- target creation permission behavior, if any;
- target draft state;
- treatment of Sales Order status / hold / close;
- treatment of zero quantities;
- calculation of remaining billable quantity;
- existing Sales Invoice quantities / amounts considered;
- returns and re-delivery behavior;
- Delivery Note interaction;
- mapping of `sales_order` and `so_detail` references;
- address/contact data;
- company/currency/price-list fields;
- item quantities, UOM, rates, discounts, warehouses, accounts;
- taxes and charges;
- payment terms / payment schedule;
- projects / cost centers / accounting dimensions if relevant;
- packed items / product bundles if relevant;
- advances if relevant;
- calls made by mapper post-processing / `set_missing_values` / taxes-and-totals helpers.

Trace all helper functions it invokes that materially change eligibility or target content.

## Step 6 - Define conversion eligibility and no-op states

The report must distinguish at least:

- Sales Order not found;
- no read permission;
- Draft Sales Order;
- Cancelled Sales Order;
- Closed / On Hold source;
- Submitted source with billable rows;
- fully billed source;
- partially billed source;
- rows with zero remaining billable qty;
- source changed after preview;
- target create permission missing;
- mapper returns no eligible items;
- native mapping/validation failure.

Recommend safe public error / interaction states. Reuse existing project error vocabulary where it fits; do not invent a second approval model.

## Step 7 - Determine prepare boundary for conversion

This is a critical part of the audit.

The existing Quotation -> Sales Order implementation may call native target validation during prepare. Do not assume the same is safe for Sales Invoice.

Trace exactly what happens when a mapped unsaved Sales Invoice receives:

```text
set_missing_values
calculate_taxes_and_totals
validate
run_method("validate")
```

For each candidate operation, classify:

- pure/local calculation;
- permission-aware read;
- database write;
- enqueue/background job;
- external network/API call;
- cache/global mutation;
- other observable side effect.

If behavior depends on `update_stock`, POS, return, India Compliance, or settings, record the conditions separately.

The report must explicitly recommend one prepare strategy:

A. mapper only;
B. mapper + bounded safe helper calls;
C. mapper + native validate;
D. another native path.

The decision must be evidence-based and must preserve the project's prepare-side-effect boundary.

## Step 8 - Design stale-confirmation evidence for conversion

Inspect the existing Quotation -> Sales Order fingerprint/re-map approach.

For Sales Order -> Sales Invoice, determine which source and mapped target fields must be compared at confirm time to catch changes such as:

- source cancellation / status change;
- source hold / close change;
- quantity already billed by another invoice after preview;
- Delivery Note / billing state change;
- source item quantity / rate / discount changes allowed by ERPNext;
- taxes / totals changes;
- currency / company / party changes;
- payment schedule changes;
- accounting-relevant mapped values;
- stock / warehouse fields when relevant.

Do not rely only on `Sales Order.modified` if downstream documents can alter remaining billable state without changing the relevant source revision in a way that guarantees safety.

Recommend whether confirm should:

1. claim approval;
2. reload source;
3. recheck eligibility and permissions;
4. run the same native mapper again;
5. recompute a stable commercial fingerprint;
6. compare it to approval-bound state;
7. insert only on exact match.

Document any exception to this pattern with source evidence.

## Step 9 - Trace Sales Invoice validation

Inspect `Sales Invoice.validate()` and inherited controller methods.

At minimum identify behavior related to:

- Customer and company;
- posting date/time;
- due date and payment terms;
- currency and conversion rate;
- receivable account (`debit_to`);
- income accounts;
- taxes and charges;
- discount / pricing rule behavior;
- Sales Order / Delivery Note requirement checks;
- previous-document validation;
- project/customer consistency;
- UOM/quantity validation;
- warehouse validation;
- stock-update validation;
- serialized/batched item validation;
- POS behavior;
- return / credit note behavior;
- debit note behavior if present;
- advances / allocations;
- loyalty;
- deferred revenue;
- tax withholding;
- credit limits;
- accounting dimensions;
- item tax and HSN/SAC-related behavior;
- hooks from installed apps.

Separate validation that only reads/calculates from validation that may cause observable side effects.

## Step 10 - Trace submit behavior and accounting impact

Document the exact `on_submit` call flow and material effects.

At minimum inspect:

- GL entry creation;
- Payment Ledger / outstanding behavior;
- receivable account posting;
- income and tax postings;
- Sales Order billing status update;
- Delivery Note billing status update;
- stock ledger update when `update_stock=1`;
- serial/batch bundle effects;
- stock reservation effects;
- asset effects if relevant;
- project updates;
- loyalty updates;
- sales analytics/company sales updates;
- credit-limit checks;
- overdue billing checks;
- coupon/promotional state if relevant;
- hooks from India Compliance or other installed apps.

Clearly state why Sales Invoice submit requires explicit confirmation and why draft creation and submission must not be one implicit MCP write in V1.

## Step 11 - Trace cancellation and delete behavior

Document:

- `on_cancel` behavior;
- GL reversal/cancellation behavior;
- stock ledger reversal when relevant;
- Sales Order / Delivery Note billing status rollback;
- Payment Entry / Journal Entry / Credit Note / e-invoice / e-waybill or other linked-document blockers;
- immutable ledger implications if applicable to the installed version;
- standard Frappe linked-document delete rules;
- India Compliance restrictions on cancelling an e-invoiced/e-waybilled document, if present in installed source.

Do not propose bypassing linked documents.

## Step 12 - Audit direct / standalone Sales Invoice creation

Treat this as a separate future public capability from Sales Order conversion.

The report must determine the correct native ERPNext approach for a Sales Invoice created without a Sales Order.

Do not assume a single public `make_sales_invoice()` exists for this use case. Inspect how ERPNext itself creates/defaults a fresh Sales Invoice and how standard server-side helpers populate party and item values.

Trace at minimum:

- `frappe.new_doc("Sales Invoice")` defaults;
- Customer/company defaults;
- party details/address/contact/tax category;
- posting date;
- due date / payment terms;
- currency / selling price list;
- receivable account;
- item details;
- UOM / conversion factor;
- rate / price list rate / pricing rules;
- warehouse when relevant;
- income account;
- cost center/accounting dimensions;
- taxes and charges templates / tax calculation;
- project/campaign/sales team if applicable;
- payment schedule;
- `update_stock`;
- Sales Order and Delivery Note requirement validation.

The report must identify the smallest safe V1 user-input contract for standalone invoice creation.

The preferred initial scope to evaluate is:

```text
Customer invoice
Draft only on confirm
non-POS
not a return / credit note
not a debit note
update_stock = 0
normal sales Items / service Items
no automatic payment creation
```

This is a hypothesis, not a conclusion. Confirm or change it based on native source evidence.

## Step 13 - Inspect Selling Settings and Customer exceptions

Read the installed fields and code that enforce:

- Sales Order required for Sales Invoice;
- Delivery Note required for Sales Invoice;
- Customer-level exceptions allowing direct invoice without Sales Order;
- Customer-level exceptions allowing invoice without Delivery Note.

Document the exact fieldnames and controller logic from the installed version.

The standalone MCP tool must never bypass these rules. If the site/customer configuration disallows direct invoice, the future tool should return an actionable safe result instead of inventing a source document or using privileged flags.

## Step 14 - Evaluate standalone scope variants

For each variant below, mark `V1`, `later explicit capability`, or `out of scope`, and justify using source behavior:

| Variant | Decision required |
|---|---|
| normal non-stock/service invoice | V1 candidate |
| stock item invoice with `update_stock=0` | inspect |
| direct stock sale with `update_stock=1` | inspect, probably later |
| POS invoice behavior through Sales Invoice | inspect, probably separate |
| return / credit note | inspect, separate capability candidate |
| debit note / rate adjustment | inspect, separate capability candidate |
| timesheet billing | inspect |
| project/milestone billing | inspect |
| subscription/auto-repeat generated invoice | inspect |
| consolidated invoice | inspect |
| inter-company invoice | inspect |
| invoice with advances allocated | inspect |
| multi-currency invoice | inspect |

Do not widen standalone V1 merely because ERPNext technically supports a feature.

## Step 15 - India Compliance Sales Invoice audit

If India Compliance is installed, build a precise lifecycle matrix:

| Stage | India Compliance code/hook | Condition | Reads | Writes | External I/O | User input/field impact |
|---|---|---|---|---|---|---|
| new/default | | | | | | |
| validate | | | | | | |
| insert/save | | | | | | |
| submit | | | | | | |
| cancel | | | | | | |
| print/PDF | | | | | | |

Inspect runtime merged metadata for `Sales Invoice` and `Sales Invoice Item` and list only relevant India Compliance-added fields, including their:

- fieldname;
- fieldtype;
- options;
- reqd;
- mandatory_depends_on;
- depends_on;
- fetch_from;
- fetch_if_empty;
- default;
- read_only/hidden state when meaningful.

Do not implement a generic evaluator for arbitrary `depends_on` expressions in this task.

Determine whether India Compliance requires conversational preflight for any invoice field that ordinary MCP preparation would otherwise discover only at confirm/insert/submit time.

If such requirements exist, recommend a small optional integration provider/adapter only if native runtime metadata and native app helpers are insufficient. Do not create that provider here.

## Step 16 - ERPNext-only portability check

On an ERPNext-only site if one is safely available, verify read-only:

- Sales Invoice metadata loads normally;
- India Compliance custom fields are absent as expected;
- `mcp_erpnext` can import/start without India Compliance;
- proposed future invoice core code would not need module-level imports from India Compliance.

If no ERPNext-only site is available, state that the portability check is source-based only.

## Step 17 - Audit generic read/search/PDF/email integration

Inspect exactly how current shared services determine supported DocTypes.

For Sales Invoice, recommend:

- read summary fields;
- search filter fields;
- party field;
- transaction/posting date field;
- secondary date (for example due date) if appropriate;
- status/docstatus handling;
- item summary fields;
- whether outstanding amount should be included;
- PDF compatibility with native print formats;
- email recipient inference from Sales Invoice / Customer / Contact;
- profile boundary.

Do not implement these changes.

Important: note any coupling where adding Sales Invoice to the shared read `_DOCUMENTS` or profile set automatically enables PDF/email. State whether that coupling is acceptable or should be separated.

## Step 18 - Define future public tool architecture

The report must recommend exact tool families for future tasks.

Expected direction to evaluate:

### Task 27 - Sales Order -> Sales Invoice native conversion

Candidate public tools:

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

Expected result: Draft Sales Invoice only.

No implicit submit.

### Task 28 - Existing Sales Invoice capability integration

Reuse shared mechanisms where safe:

```text
get_document / search_documents
prepare_document_pdf
prepare_document_email / confirm_document_email
prepare_document_submit / confirm_document_submit
prepare_document_cancel / confirm_document_cancel
prepare_document_delete / confirm_document_delete
```

Generic update and child-add must be enabled only if the audit proves a safe action/field policy. Merely adding Sales Invoice to a broad DocType allowlist is not acceptable if that exposes unsafe fields or actions.

### Task 29 - Direct / standalone Sales Invoice creation

Candidate public tools:

```text
prepare_sales_invoice
confirm_sales_invoice
```

Expected result: Draft Sales Invoice only.

This tool must create an invoice without a Sales Order only when native ERPNext configuration permits it. It must not set flags to bypass Sales Order / Delivery Note requirements.

No implicit submit or payment creation.

Do not implement any of these tools in Task 26.

## Step 19 - Interaction and approval contract review

Determine how each future write should use the existing typed interaction model:

- `needs_input` for genuinely missing required user input;
- `needs_selection` if entity resolution is ambiguous;
- `needs_confirmation` for a prepared write;
- `ready` only according to existing project semantics;
- safe errors for permission/configuration/native validation failures.

Do not create Sales Invoice-specific approval semantics unless the current generic approval store cannot safely represent the operation. Any proposed exception must be justified.

## Step 20 - Observability and error mapping

Inspect how current errors are made safe for MCP clients.

Recommend mappings for invoice-specific failure families without leaking:

- SQL;
- server filesystem paths;
- role internals;
- secrets;
- full tracebacks;
- GST API credentials;
- accounting internals that the user is not permitted to read.

The report should preserve useful business guidance, for example configuration blocking direct invoicing, while keeping sensitive implementation details in server logs only.

---

# 7. Required Audit Report Structure

Create:

```text
docs/inspect/SALES_INVOICE_NATIVE_FLOW_AUDIT.md
```

The report must contain these sections in this order.

## 1. Executive conclusion

Answer in plain language:

- whether Sales Invoice is currently implemented;
- whether SO -> SI native conversion is feasible;
- whether standalone SI creation is feasible;
- whether both should be separate public tool families;
- whether current shared lifecycle policy is safe as-is for Sales Invoice;
- recommended V1 boundaries.

## 2. Exact versions and site/app state

Include current source/runtime evidence.

## 3. Current `mcp_erpnext` Sales architecture

Include tool/profile/service/contract call map and current Sales Invoice gaps.

## 4. Current lifecycle/read/PDF/email policy findings

Include all relevant allowlists and coupling.

## 5. Native Sales Order -> Sales Invoice source path

Include exact function paths and helper call flow.

## 6. Native conversion eligibility matrix

Include partial/fully billed cases and source state.

## 7. Native mapped Sales Invoice field analysis

Separate source-derived, defaulted, calculated, accounting, stock, and compliance fields.

## 8. Conversion prepare-side-effect audit

State exactly what may safely execute before approval.

## 9. Conversion stale-confirmation design

Recommend fingerprint fields and re-map/recheck behavior.

## 10. Sales Invoice validation flow

Trace base and inherited validation plus hooks.

## 11. Sales Invoice submit effects

Accounting, stock, source status, credit, and other effects.

## 12. Cancel/delete and linked-document behavior

Include accounting/stock/compliance consequences.

## 13. Standalone Sales Invoice native creation path

Trace native defaults and helper APIs.

## 14. Standalone minimum input contract

Propose exact V1 inputs and defaults with reasoning.

## 15. Selling Settings / Customer policy matrix

Show when direct invoice is allowed or blocked.

## 16. Standalone feature-scope matrix

V1 vs later for stock update, POS, return, etc.

## 17. India Compliance Sales Invoice integration

Hooks, custom fields, GST requirements, lifecycle side effects, portability.

## 18. ERPNext-only behavior

Show no optional-app hard dependency.

## 19. Shared existing-document capability design

Read/search/PDF/email/lifecycle integration proposal.

## 20. Lifecycle action-policy decision

Explicitly answer whether action-scoped / field-scoped policy is required before adding Sales Invoice.

## 21. Recommended public MCP contracts

Exact proposed tool names and bounded responsibilities for Tasks 27-29.

## 22. Security and permission model

Show normal Frappe permission flow and forbidden bypasses.

## 23. Test plan for implementation tasks

Unit/static/live test matrix.

## 24. Known limitations and open questions

Only unresolved evidence-based items.

## 25. Final architecture decision

Provide one final recommended sequence and explain why.

## 26. Exact next task

This must be Task 27 only, not all implementation work at once.

---

# 8. Required Decision Matrix

The report must include a concise final matrix similar to:

| Capability | Public tool strategy | V1? | Native authority | Approval | Notes |
|---|---|---:|---|---|---|
| SO -> SI conversion | explicit pair | yes | ERPNext native mapper | yes | Draft target only |
| standalone SI creation | explicit pair | yes/later based on audit | ERPNext defaults/helpers | yes | no SO bypass |
| SI read/search | shared generic | yes | permission-aware Frappe reads | no write approval | action allowlist |
| SI PDF | shared generic | yes | native print/PDF | no write approval | read permission |
| SI email | shared generic | yes | Frappe sendmail + native PDF | yes for send | existing pattern |
| SI submit | shared lifecycle | yes after policy check | `doc.submit()` | yes | GL impact |
| SI cancel | shared lifecycle | yes after policy check | `doc.cancel()` | yes | reversal impact |
| SI delete | shared lifecycle | bounded | `doc.delete()` | yes | linked docs |
| generic SI update | inspect | not automatically | `doc.save()` | yes | field policy required |
| SI child add | inspect | not automatically | native doc model | yes | likely restricted |
| POS | separate | later | ERPNext POS | yes | not standalone V1 |
| Update Stock direct sale | separate/bounded | later unless audit proves simple | ERPNext stock/accounting | yes | stock + GL |
| return / credit note | explicit separate | later | ERPNext return flow | yes | do not overload create |
| Payment Entry | separate future capability | later | ERPNext Accounts | yes | not this task |

The final values must come from inspection, not from this example.

---

# 9. Minimum Test Plan to Design for Task 27

The audit must define tests for at least:

1. Submitted Sales Order with one unbilled item -> ready conversion preview.
2. Draft Sales Order -> source not ready.
3. Cancelled Sales Order -> source not ready.
4. Closed/on-hold source -> correct native/safe result.
5. Fully billed Sales Order -> no mappable items.
6. Partially billed Sales Order -> remaining quantity/amount only.
7. Multiple items with mixed billed state -> only native eligible quantities.
8. Source read denied -> permission denied.
9. Sales Invoice create denied -> permission denied.
10. Prepare performs no Sales Invoice insert.
11. Prepare performs no GL/stock ledger writes.
12. Prepare performs no external compliance API I/O unless explicitly proven safe and intended.
13. Approval bound to site/user/action/payload.
14. Confirm without approval -> denied.
15. Approval replay -> no duplicate invoice.
16. Source billing state changes after preview -> stale confirmation.
17. Source document relevant commercial state changes -> stale confirmation.
18. Confirm reuses same native mapper logic.
19. Confirm inserts Draft Sales Invoice with normal permissions.
20. Confirm does not submit automatically.
21. `sales_order` and `so_detail` links preserved.
22. Native totals/taxes/payment schedule remain consistent.
23. ERPNext-only site works without India Compliance import.
24. India Compliance site preserves native GST behavior.

---

# 10. Minimum Test Plan to Design for Task 28

The audit must define tests for at least:

1. Sales Invoice get/read allowed under Sales profile.
2. Sales Invoice search returns permission-scoped results.
3. Sales Invoice unavailable under Purchase profile.
4. PDF uses normal read/print permission.
5. Email recipient resolution works for Sales Invoice.
6. Email remains approval-gated for send.
7. Draft invoice submit requires approval.
8. Submit permission denied is safe.
9. Submit invokes normal ERPNext `doc.submit()` with no bypass.
10. Submitted invoice cancellation requires approval.
11. Cancellation respects linked/compliance rules.
12. Delete respects linked docs and cancel-then-delete policy where applicable.
13. Generic update is unavailable unless explicitly action/field enabled.
14. Child-add is unavailable unless explicitly enabled.
15. Adding Sales Invoice does not accidentally broaden Customer/Item/Quotation/Sales Order capabilities.
16. Cross-profile allowlists remain intact.

---

# 11. Minimum Test Plan to Design for Task 29

The audit must define tests for at least:

1. Direct normal customer invoice allowed by Selling Settings -> ready preview.
2. Sales Order required globally and no Customer exception -> structured blocked/needs prerequisite result.
3. Sales Order required but Customer exception permits direct invoice -> proceeds through native path.
4. Delivery Note required and no exception -> blocked.
5. Delivery Note requirement exception -> native path continues.
6. Missing Customer -> resolver/needs input behavior.
7. Ambiguous Customer -> needs selection.
8. Missing/ambiguous Item -> existing resolver behavior.
9. Missing mandatory effective field -> needs input before approval when safely knowable.
10. Native defaults for company/currency/price list/account are used rather than hardcoded.
11. Pricing/taxes use ERPNext native calculations.
12. Prepare does not insert.
13. Confirm inserts Draft only.
14. Confirm does not submit.
15. Confirm does not create Payment Entry.
16. `update_stock` cannot be silently enabled in V1 if V1 freezes it off.
17. POS cannot be silently entered through the standalone V1 contract.
18. Return/credit-note flags cannot be silently entered through standalone V1.
19. India Compliance absent -> core path works.
20. India Compliance present -> applicable GST requirements are collected/preflighted without copied GST logic.
21. Final insert still runs native ERPNext/India Compliance validation.
22. Permission denial remains safe.
23. Approval replay cannot duplicate an invoice.
24. Prepared payload includes every effective value that can materially affect the confirmed invoice.

---

# 12. Expected Results

A successful Task 26 does not add any MCP tool.

It produces a report that lets the next implementation task be written without guessing.

Expected conclusions should be precise enough to answer:

```text
Can we convert a submitted Sales Order to a Draft Sales Invoice using ERPNext's native mapper?
What exact native function should be called in this installed version?
What state must be bound into approval?
What must be rechecked/remapped at confirm?
Can target validation safely run during prepare?
How do partial billing and previously billed quantities work?
What India Compliance behavior is triggered and when?
Can a standalone Sales Invoice be created without a Sales Order?
Under which Selling Settings / Customer conditions?
What is the smallest safe standalone V1 contract?
Should standalone V1 force update_stock=0?
How should Sales Invoice enter generic read/PDF/email/lifecycle tools?
Does the current lifecycle allowlist need action-scoped policy first?
Which invoice updates must remain unsupported?
What is Task 27 exactly?
```

---

# 13. Acceptance Criteria

Task 26 is complete only when all of the following are true:

- [ ] Current `mcp_erpnext` implementation was inspected before design recommendations.
- [ ] Current Sales profile registration and every relevant shared allowlist were traced.
- [ ] No Sales Invoice implementation was added.
- [ ] Exact installed ERPNext native SO -> SI mapper was located and traced.
- [ ] Source eligibility and partial-billing behavior were documented.
- [ ] Mapper and target validation side effects were explicitly audited.
- [ ] Sales Invoice validation was traced through inherited/native logic.
- [ ] Submit accounting and optional stock effects were documented.
- [ ] Cancel/delete consequences and linked-document rules were documented.
- [ ] Direct/standalone Sales Invoice path was independently inspected.
- [ ] Selling Settings and Customer exceptions were traced by exact installed field/code behavior.
- [ ] A minimum standalone V1 input contract was proposed.
- [ ] POS, update-stock, returns, debit notes, timesheet/project billing and other variants were individually scoped.
- [ ] India Compliance Sales Invoice integration was inspected when installed.
- [ ] ERPNext-only portability was addressed.
- [ ] Existing read/PDF/email integration points were identified.
- [ ] Lifecycle action/field policy risk was explicitly decided.
- [ ] Proposed public tools for Tasks 27-29 were named.
- [ ] Required tests for each future implementation task were listed.
- [ ] Report distinguishes confirmed source behavior from recommendations/inference.
- [ ] Only the inspection report file changed.
- [ ] Exact next task is one focused implementation task, not a multi-feature bundle.

---

# 14. Verification for This Inspection Task

Because this task must not write business data, verification is primarily read-only and static.

At minimum:

1. Confirm `git diff --check` passes for the report.
2. Confirm git diff contains only the intended inspection report.
3. Search the repository to confirm no new Sales Invoice implementation files/tools were added.
4. If existing mocked/unit tests are run, do not modify them and record the exact command/result.
5. If live site inspection is used, record only read-only app/version/metadata/settings evidence.
6. Do not create disposable transactions in Task 26 unless the user separately authorizes live write verification.

Expected result:

```text
One evidence-based inspection report exists.
No application behavior changed.
No database business record was written by the task.
No approval/security/profile policy was changed.
```

---

# 15. Known Boundaries

This task does not implement:

- Sales Order -> Sales Invoice conversion;
- standalone Sales Invoice creation;
- Sales Invoice read/search registration;
- Sales Invoice PDF registration;
- Sales Invoice email registration;
- Sales Invoice update;
- Sales Invoice child row add;
- Sales Invoice submit/cancel/delete registration;
- Delivery Note tools;
- POS tools;
- Credit Note / Sales Return tools;
- Debit Note tools;
- Payment Entry tools;
- e-invoice generation tools;
- e-waybill generation tools;
- GST API calls;
- Accounts MCP profile.

The audit may recommend later explicit capabilities for these, but must not implement them.

---

# 16. Frozen Direction Unless Inspection Disproves It

The intended architecture to test, not blindly implement, is:

```text
Sales Agent / any MCP client
        |
        v
mcp_erpnext sales profile
        |
        +-- Quotation creation
        |
        +-- Quotation -> Sales Order native conversion
        |
        +-- Sales Order creation
        |
        +-- Sales Order -> Sales Invoice native conversion       [Task 27]
        |       prepare -> approval -> confirm -> Draft SI
        |
        +-- Existing Sales Invoice capabilities                  [Task 28]
        |       read / search / PDF / email
        |       submit / cancel / delete under narrow policy
        |       update only if separately safe/allowed
        |
        +-- Standalone Sales Invoice creation                    [Task 29]
                prepare -> native defaults/rules
                -> approval -> confirm -> Draft SI
                -> no Sales Order bypass
                -> no implicit submit
                -> no implicit payment
```

The two Sales Invoice creation paths are deliberately separate:

```text
A. Source-backed invoice
   Submitted Sales Order
      -> ERPNext native mapper
      -> remaining billable state
      -> Draft Sales Invoice

B. Standalone/direct invoice
   Customer + Items + bounded user inputs
      -> ERPNext native new-document/default/item/tax logic
      -> Selling Settings / Customer policy checks
      -> Draft Sales Invoice
```

Do not fake path B by creating a hidden Sales Order, and do not fake path A by copying Sales Order fields manually into a generic standalone creator.

---

# 17. Exact Next Task

After the user reviews and accepts `SALES_INVOICE_NATIVE_FLOW_AUDIT.md`, the next task is:

```text
Task 27 - Sales Order -> Sales Invoice Native Conversion Foundation
```

Task 27 should implement only the source-backed conversion pair, based on the audit's exact installed native mapper and safety findings.

Planned later sequence, subject to Task 26 evidence:

```text
Task 27 - Sales Order -> Sales Invoice Native Conversion Foundation
Task 28 - Existing Sales Invoice Read/PDF/Email/Lifecycle Integration
Task 29 - Direct / Standalone Sales Invoice Creation Foundation
```

Do not combine Tasks 27-29 into one implementation change.
