# Task 28 - Sales Invoice Existing-Document Capabilities and Action-Scoped Lifecycle Policy

Date: 2026-09-11
Project: `mcp_erpnext`
Profile: `sales`
Task type: implementation + tests + implementation report
Predecessor: Task 27 - Sales Order -> Sales Invoice Native Conversion Foundation
Successor: Task 29 - Standalone Sales Invoice Creation Foundation

---

## 0. Task status and non-negotiable boundary

Task 27 is complete according to the supplied implementation report. It added exactly:

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

Task 28 must NOT redesign, broaden, or fold that conversion into a generic transaction engine.

Task 28 is only about an **already-existing Sales Invoice** and the shared document capabilities around it:

```text
read/search
PDF
email
submit
cancel
delete
```

The central architecture change required by this task is a **minimal action-scoped lifecycle authorization policy**. The current lifecycle service uses a broad profile-level doctype set. Simply adding `Sales Invoice` to that set would also expose generic update for Sales Invoice, which is explicitly forbidden for V1.

The required Sales Invoice policy is:

```text
Sales profile
  Sales Invoice: READ      = ALLOW
  Sales Invoice: PRINT     = ALLOW
  Sales Invoice: EMAIL     = ALLOW
  Sales Invoice: SUBMIT    = ALLOW
  Sales Invoice: CANCEL    = ALLOW
  Sales Invoice: DELETE    = ALLOW
  Sales Invoice: UPDATE    = DENY
  Sales Invoice: CHILD_ADD = DENY
```

Do not implement standalone Sales Invoice creation in this task. That remains Task 29.

---

# 1. Objective

Extend the existing shared `mcp_erpnext` document capabilities so that the Sales profile can safely work with an existing `Sales Invoice`, while preserving normal Frappe/ERPNext permissions, document lifecycle, India Compliance hooks, approval semantics, profile isolation, and all existing document behavior.

After this task, an authenticated Sales-profile client should be able to:

1. retrieve one exact Sales Invoice;
2. search Sales Invoices using bounded, permission-aware criteria;
3. render a Sales Invoice through the existing generic PDF capability;
4. prepare and confirm a Sales Invoice email through the existing generic email capability;
5. prepare and confirm submit for a Draft Sales Invoice;
6. prepare and confirm cancel for a Submitted Sales Invoice;
7. prepare and confirm delete using the existing linked-document and cancel-then-delete behavior;
8. receive an explicit denial if generic update or child-row add is attempted against Sales Invoice.

The implementation must not create a second Sales Invoice-specific lifecycle engine when the existing generic services are sound.

---

# 2. Required inputs and source of truth

Before modifying code, inspect all of the following in the CURRENT worktree. Do not rely only on this task file or an older ZIP.

## 2.1 Project evidence

Read first:

```text
docs/inspect/SALES_INVOICE_NATIVE_FLOW_AUDIT.md
```

and the Task 27 implementation/report if present:

```text
docs/inspect/SALES_ORDER_TO_SALES_INVOICE_NATIVE_CONVERSION_IMPLEMENTATION_REPORT.md
```

Inspect the actual Task 27 implementation too so this task preserves its registration/contracts/tests.

## 2.2 Existing shared MCP implementation

At minimum inspect:

```text
mcp_erpnext/services/common/read.py
mcp_erpnext/contracts/read.py
mcp_erpnext/tools/read.py

mcp_erpnext/services/common/pdf.py
mcp_erpnext/contracts/pdf.py
mcp_erpnext/tools/pdf.py

mcp_erpnext/services/common/email.py
mcp_erpnext/contracts/email.py
mcp_erpnext/tools/email.py

mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/contracts/lifecycle.py
mcp_erpnext/tools/lifecycle.py

mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py
```

Inspect current tests before choosing file changes:

```text
mcp_erpnext/tests/test_read.py
mcp_erpnext/tests/test_pdf.py
mcp_erpnext/tests/test_email.py
mcp_erpnext/tests/test_lifecycle.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_contracts.py
```

Also inspect any newer focused read tests or policy helpers added after the previously audited ZIP.

## 2.3 Installed ERPNext/Frappe/India Compliance authority

Use the installed source, not copied business logic.

At minimum inspect the current installed version of:

```text
apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py
apps/erpnext/erpnext/controllers/accounts_controller.py
apps/erpnext/erpnext/controllers/selling_controller.py
apps/frappe/frappe/model/document.py
apps/frappe/frappe/model/delete_doc.py
```

If India Compliance is installed on the site/worktree, inspect its Sales Invoice hooks and relevant transaction handlers. Imports from optional apps must remain optional/lazy in `mcp_erpnext`; do not make `mcp_erpnext` startup depend on India Compliance.

Runtime metadata is authoritative for actual fields. Do not hard-code fields merely from browser UI labels.

---

# 3. Frozen architecture decisions

These are requirements, not suggestions.

## 3.1 Existing shared engines stay shared

Reuse the existing shared implementations for:

```text
existing-document read/search
PDF rendering
email preparation/confirmation
submit/cancel/delete
approval storage
interaction directives
safe errors
profile registration
```

Do not create:

```text
sales_invoice_read_service.py
sales_invoice_pdf_service.py
sales_invoice_email_service.py
sales_invoice_lifecycle_service.py
```

unless the current code proves a genuinely isolated adapter is necessary. The expected design is to extend the existing shared services with bounded Sales Invoice definitions/policies.

## 3.2 Read/PDF/email eligibility is not lifecycle authorization

Do not introduce one giant doctype set that governs every capability.

A document being readable/printable/emailable does not imply it is generically updatable.

Sales Invoice is the concrete reason this separation is now required.

## 3.3 Lifecycle authorization must become action-scoped

The current broad `PROFILE_DOCTYPES` behavior must no longer be the sole authorization decision for lifecycle actions.

The implementation must be able to answer at least:

```text
is doctype X allowed for profile P and lifecycle action A?
```

where the relevant actions are the existing lifecycle actions, including:

```text
update
child_add
submit
cancel
delete
```

For Sales Invoice in Sales profile:

```text
update    -> deny
child_add -> deny
submit    -> allow
cancel    -> allow
delete    -> allow
```

Existing behavior for all already-supported doctypes must remain unchanged unless an existing test or explicit frozen policy says otherwise.

## 3.4 Prefer the smallest policy abstraction that fits current architecture

First inspect whether the cleanest implementation belongs inside `services/common/lifecycle.py` or in an existing config/policy module.

A small new shared policy module is allowed only if it materially avoids policy duplication across the current implementation.

Do NOT build:

```text
a generic RBAC engine
a policy DSL
a rule expression evaluator
a plugin registry
a universal document capability framework
```

This task needs only a clear, deterministic profile + doctype + action allowlist.

## 3.5 Generic Sales Invoice update is out of scope

Do not expose Sales Invoice through the existing generic `prepare_update` / confirm update path.

Do not try to make update safe by excluding only a few fields.

The audit found no sufficiently reviewed generic field set for Sales Invoice. Accounting/tax/source-lineage/update-after-submit behavior is too high-impact for broad runtime-writable-field logic.

Required behavior:

```text
prepare_document_update(target={doctype: "Sales Invoice", ...})
    -> safe DOCTYPE/ACTION not allowed result
    -> no approval created
    -> no document mutation
```

Use the existing public error style and naming conventions. Do not invent a special UI-only error shape.

## 3.6 Sales Invoice child add is out of scope

Do not add `Sales Invoice -> Sales Invoice Item` to `CHILD_ADD_TARGETS` or any equivalent child-add policy.

Attempted generic child add against Sales Invoice must fail before mutation/approval.

## 3.7 Submit/cancel/delete stay native

Reuse existing lifecycle prepare/confirm behavior and native Frappe document methods:

```text
doc.submit()
doc.cancel()
doc.delete() / existing deletion path
```

with normal permissions and existing linked-document checks.

Do not reimplement GL reversal, Sales Order billing updates, stock effects, India Compliance behavior, e-Invoice/e-Waybill behavior, or linked-document handling.

## 3.8 Draft creation and lifecycle remain separate

Task 27 creates a Draft only.
Task 28 may later submit that Draft only through the generic approval-gated submit lifecycle.

Never make Task 27 confirmation implicitly submit.

## 3.9 Task 29 remains separate

Do not add:

```text
prepare_sales_invoice
confirm_sales_invoice
```

in this task.

Do not add direct Customer + items Sales Invoice construction.

---

# 4. Scope

## 4.1 In scope

### A. Shared read/search support for Sales Invoice

Add Sales Invoice to the shared existing-document read capability for `sales` only.

The public typed contract must accept Sales Invoice where appropriate.

Use a bounded Sales Invoice definition. At minimum the summary/detail should support the existing common projection concepts and Sales Invoice-relevant dates.

Recommended effective summary mapping:

```text
doctype        = Sales Invoice
party          = customer
primary date   = posting_date
secondary date = due_date
status         = status
docstatus      = docstatus
currency       = currency
grand_total    = grand_total
items          = bounded existing item projection
```

If the existing generic model uses the property name `transaction_date`, preserve the public model unless a contract migration is necessary. It is acceptable to populate that normalized public field from `posting_date` for Sales Invoice. Do not create a breaking rename solely for Sales Invoice.

Search date filters for Sales Invoice must target its real runtime field (`posting_date`), not assume `transaction_date` exists.

Search must remain permission-aware with normal Frappe list permissions.

Do not expose arbitrary accounting or GST internals in search results.

### B. PDF support

Extend the existing PDF typed contract and doctype/profile definition so:

```text
render_document_pdf(
    doctype="Sales Invoice",
    name="..."
)
```

works under the Sales profile.

Keep:

```text
exact target
read permission
print permission
native frappe.get_print(..., as_pdf=True)
existing artifact behavior
existing print-format/letterhead/language handling
```

Do not build a separate Sales Invoice HTML/PDF renderer.

Installed hooks such as India Compliance `before_print` must remain naturally reachable through the native print path.

### C. Email support

Extend the existing generic document email capability for Sales Invoice.

Required party mapping:

```text
Sales Invoice -> Customer -> invoice.customer
```

Preserve the current recipient resolution order/semantics, including the transaction's selected contact/contact email and permission-aware Customer/Contact resolution.

Keep:

```text
prepare_document_email
confirm_document_email
native PDF attachment
outgoing Email Account check
approval-bound exact recipient/content/PDF
stale document/PDF/recipient detection
frappe.sendmail queue path
queued != delivered
```

No custom SMTP implementation.

### D. Submit support

Sales Invoice must be targetable by the existing generic submit pair only after action-scoped lifecycle policy is in place.

Prepare must:

```text
load exact Sales Invoice
check profile/action allowlist
check required Frappe permission through existing lifecycle behavior
verify native document state
produce bounded preview
create normal shared approval
```

Confirm must:

```text
claim the existing one-shot approval
re-check exact document/profile/action/state as current lifecycle does
call native doc.submit()
commit only on success
rollback/error safely on failure
```

Do not call GL APIs directly.
Do not call stock ledger APIs directly.
Do not call India Compliance APIs directly.

Native hooks are final authority.

### E. Cancel support

Sales Invoice must be targetable by the existing generic cancel pair through the action policy.

Do not pre-bypass or duplicate native e-Invoice/E-Waybill cancellation logic.

If India Compliance or ERPNext blocks cancellation, surface the existing safe MCP error envelope. Do not convert a native failure into success.

### F. Delete support

Sales Invoice must be targetable through the existing delete pair under the action policy.

Preserve:

```text
linked-document preflight
native linked-document enforcement
cancel-then-delete plan for submitted docs when supported by current service
approval binding
no cascade deletion
normal permission checks
```

Do not automatically delete Payment Entries, Sales Orders, Delivery Notes, GL entries, e-Invoice records, or any other linked records to make deletion succeed.

---

# 5. Explicitly out of scope

Do not implement any of the following in Task 28:

```text
standalone Sales Invoice creation
Sales Order -> Sales Invoice conversion changes
Delivery Note -> Sales Invoice conversion
generic Sales Invoice update
Sales Invoice child-row add
submitted Sales Invoice field edits
update-after-submit accounting edits
POS invoice workflow
update_stock=1 direct-sale workflow
return / Credit Note
Debit Note
Timesheet billing
Project billing workflow
advance allocation
Payment Entry creation
write-off workflow
loyalty operations
inter-company invoice
subscription / Auto Repeat
consolidated POS invoice
e-Invoice generation tool
e-Waybill generation tool
custom GST calculation
custom HSN validation
custom GL or stock ledger logic
```

Also do not add Accounts profile in this task.

---

# 6. Allowed changes

Agent must inspect the current worktree and change only what is actually required.

Expected/allowed areas include:

```text
mcp_erpnext/services/common/read.py
mcp_erpnext/contracts/read.py

mcp_erpnext/services/common/pdf.py
mcp_erpnext/contracts/pdf.py

mcp_erpnext/services/common/email.py
mcp_erpnext/contracts/email.py

mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/contracts/lifecycle.py   # only if contract change is actually needed

mcp_erpnext/profiles/sales.py        # only if registration needs adjustment
mcp_erpnext/contracts/registry.py    # only if typed catalog metadata requires it
mcp_erpnext/tools/__init__.py        # only if current registration architecture requires it

mcp_erpnext/tests/test_read.py
mcp_erpnext/tests/test_pdf.py
mcp_erpnext/tests/test_email.py
mcp_erpnext/tests/test_lifecycle.py
mcp_erpnext/tests/test_tool_registration.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_contracts.py
```

A focused new test file is allowed if that is cleaner than overloading existing tests, for example:

```text
mcp_erpnext/tests/test_sales_invoice_existing_document.py
```

A tiny new internal action-policy module is allowed only after inspecting existing conventions and only if it is cleaner than keeping the mapping in `lifecycle.py`.

Generated documentation may change through the repository's existing catalog generator:

```text
docs/TOOLS.md
```

Create the implementation report at:

```text
docs/inspect/SALES_INVOICE_EXISTING_DOCUMENT_CAPABILITIES_IMPLEMENTATION_REPORT.md
```

If repository conventions clearly use a different exact report name, use the closest established convention and state it in the report.

---

# 7. Files/components that must not be changed

Unless a failing test proves a direct Task 28 dependency, do not change:

```text
mcp_erpnext/services/selling/sales_order_to_sales_invoice.py
mcp_erpnext/contracts/selling/sales_order_to_sales_invoice.py
mcp_erpnext/tools/selling/sales_order_to_sales_invoice.py

mcp_erpnext/services/selling/quotation_to_sales_order.py
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/services/selling/sales_order.py

mcp_erpnext/services/masters/customer.py
mcp_erpnext/services/masters/item.py
mcp_erpnext/approvals.py
mcp_erpnext/runtime.py
mcp_erpnext/observability.py
mcp_identity/**
```

Do not edit official app code:

```text
apps/frappe/**
apps/erpnext/**
apps/india_compliance/**
```

Do not create or modify:

```text
DocTypes
hooks
fixtures
patches
migrations
site_config.json
common_site_config.json
GST Settings
Selling Settings
Accounts Settings
Customer records
Sales Invoice records
Sales Order records
Email Account records
```

unless live verification is separately and explicitly authorized.

No secrets/tokens/passwords may be added.

---

# 8. Implementation sequence

Complete these steps in order. Do not jump directly to code changes before Step 1.

## Step 1 - Inspect current implementation and record the exact coupling

Confirm in the current worktree:

1. where read doctype definitions live;
2. how each doctype chooses party/date/search fields;
3. how PDF reuses read/profile authorization;
4. how email reuses PDF/read policy and resolves a party;
5. how lifecycle `_target`/`_load` currently authorizes profile doctypes;
6. whether update, child-add, submit, cancel, and delete all currently pass through the same broad doctype gate;
7. how profile registration exposes generic wrappers;
8. whether Task 27 changed any shared behavior since Task 26.

Do not proceed until the implementation preserves established patterns.

## Step 2 - Design the minimal action policy

Implement the smallest deterministic action-aware policy needed to preserve current behavior and add Sales Invoice safely.

The policy must clearly distinguish at least:

```text
update
child_add
submit
cancel
delete
```

One acceptable conceptual shape is:

```text
LIFECYCLE_ACTION_DOCTYPES = {
    "sales": {
        "update": {...existing updateable doctypes, but NOT Sales Invoice...},
        "child_add": {...existing child-add doctypes, but NOT Sales Invoice...},
        "submit": {...existing submit targets..., "Sales Invoice"},
        "cancel": {...existing cancel targets..., "Sales Invoice"},
        "delete": {...existing delete targets..., "Sales Invoice"},
    },
    "purchase": {...preserve existing behavior...},
}
```

This is conceptual, not a required variable name.

If Customer/Item lifecycle applicability differs by action in the current service, preserve actual current behavior and tests. Do not accidentally make previously allowed actions unavailable unless the current architecture already rejects them by native state/permission.

The authorization check must happen before an approval token is created.

For an unallowed action, return a safe deterministic MCP error using existing style.

## Step 3 - Wire lifecycle action checks through every public lifecycle path

Ensure the correct action is supplied at target authorization time.

Conceptually:

```text
prepare_update      -> action=update
prepare_child_add   -> action=child_add
prepare_submit      -> action=submit
prepare_cancel      -> action=cancel
prepare_delete      -> action=delete
```

Confirm paths remain approval-bound to the already-prepared action and must not widen authorization.

Do not let an approval prepared for one lifecycle action authorize another.

## Step 4 - Add Sales Invoice read definition

Extend the generic read definition with Sales Invoice using actual fieldnames.

At minimum:

```text
party field     = customer
primary date    = posting_date
secondary date  = due_date
child table     = items
```

Update the generic search/filter code only as much as needed so the normalized public date criteria operate on `posting_date` for Sales Invoice and preserve `transaction_date` behavior for existing doctypes.

Do not write a Sales Invoice-only search implementation.

The item projection must remain bounded. Reuse existing item summary fields unless a minimal Sales Invoice source-lineage field is needed by the current public contract; do not expose full child rows.

## Step 5 - Extend typed read contract

Add `Sales Invoice` to the relevant typed `Literal`/model contract.

Do not change public result shapes unnecessarily.

Update tests proving schema acceptance and that Purchase profile still cannot target Sales Invoice.

## Step 6 - Extend PDF support

Add Sales Invoice to the explicit PDF typed doctype and corresponding service/profile definition.

Prove:

```text
Sales profile + permitted SI -> native PDF path
Purchase profile + SI -> DOCTYPE_NOT_ALLOWED
read denied -> denied
print denied -> denied
```

Do not bypass native print hooks.

## Step 7 - Extend email support

Add Sales Invoice to the typed email doctype and the existing party resolver:

```text
Sales Invoice -> ("Customer", doc.customer)
```

Preserve native document `contact_email` behavior and the existing associated-recipient restrictions.

Prove that prepare sends nothing and confirm queues exactly one email under the same approval/stale rules as the other supported documents.

## Step 8 - Allow only submit/cancel/delete for Sales Invoice

Add Sales Invoice to the lifecycle action policy for exactly:

```text
submit
cancel
delete
```

Do not add it for:

```text
update
child_add
```

The generic lifecycle engine must continue to call native Frappe methods and existing linked-document preflight.

## Step 9 - Regression-check Task 27

Run Task 27 focused tests after lifecycle/read/PDF/email changes.

Task 28 must not alter:

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

registration, schema, approval behavior, native mapper behavior, or Draft-only result.

## Step 10 - Generate/check tool documentation

Use the repository's existing generator.

Do not manually maintain generated sections if the project generator owns them.

Confirm Sales Invoice appears only where Task 28 authorizes it.

Especially verify the catalog/schema does NOT imply generic Sales Invoice update or child-add is supported.

## Step 11 - Produce implementation report

Create:

```text
docs/inspect/SALES_INVOICE_EXISTING_DOCUMENT_CAPABILITIES_IMPLEMENTATION_REPORT.md
```

The report must contain the sections defined later in this task.

---

# 9. Required behavior details

## 9.1 Read behavior

### Exact get

Expected conceptual request:

```json
{
  "target": {
    "doctype": "Sales Invoice",
    "name": "SINV-..."
  }
}
```

Expected successful result stays in the existing generic read shape.

No write approval is needed for reading.

### Search

Must support the existing criteria model:

```text
name
party
docstatus
status
date_from
date_to
limit
```

For Sales Invoice, the date criteria must filter `posting_date`.

`party` maps to Customer through `customer`.

Do not make result ordering reference a nonexistent Sales Invoice `transaction_date` field. Use the definition's actual primary date field or another minimal generic mechanism.

## 9.2 PDF behavior

Expected conceptual call:

```text
render_document_pdf(
  doctype="Sales Invoice",
  name="SINV-..."
)
```

Must return the existing PDF result type/artifact behavior.

No duplicate report renderer.

## 9.3 Email behavior

Expected conceptual flow:

```text
prepare_document_email(doctype="Sales Invoice", name="SINV-...")
  -> ready_for_approval OR needs_input OR safe error

confirm_document_email(approval_token)
  -> queued
```

`queued` must never be described as delivered.

## 9.4 Submit behavior

Expected conceptual flow:

```text
prepare_document_submit(
  target={doctype="Sales Invoice", name="SINV-..."}
)
  -> ready_for_approval OR native/safe blocker

confirm_document_submit(...)
  -> native doc.submit()
```

A successful submit may cause ERPNext and installed-app side effects including GL entries, Sales Order/Delivery Note billing updates, credit checks, and India Compliance behavior. MCP must not duplicate those effects.

## 9.5 Cancel behavior

Expected conceptual flow:

```text
prepare_document_cancel(...)
confirm_document_cancel(...)
```

Native ERPNext/India Compliance blockers remain authoritative.

Do not auto-create a Credit Note when cancellation is blocked.

## 9.6 Delete behavior

Expected conceptual flow:

```text
prepare_document_delete(...)
  -> preview/blockers/cancel-then-delete plan through existing service
confirm_document_delete(...)
```

No cascade delete.

## 9.7 Forbidden update behavior

Both parent and child updates must remain denied for Sales Invoice.

Examples that must NOT be allowed through generic lifecycle:

```text
customer
company
posting_date
due_date
debit_to
currency
selling_price_list
update_stock
taxes
account heads
payment/advance fields
GST fields
IRN/e-Waybill fields
sales_order
so_detail
item qty
item rate
```

The reason is not that only these fields are unsafe. The entire generic SI update capability is out of scope.

## 9.8 Forbidden child-add behavior

This must remain denied:

```text
prepare_child_add(
  target={doctype="Sales Invoice", ...},
  item=...,
  qty=...
)
```

Task 29 will define bounded item construction for a NEW Draft Sales Invoice. That is not permission to mutate arbitrary existing SI rows through the generic child-add engine.

---

# 10. Permission and identity requirements

Preserve the current authenticated Frappe identity as the only business identity.

Every capability must keep its existing normal permission boundary.

Required principles:

```text
no Administrator fallback
no client-selected Frappe user
no ignore_permissions=True write
no direct SQL write
no direct ledger write
no bypass of Link validation
no profile fallback
no shared-secret identity reinterpretation inside business services
```

Sales Invoice must be unavailable from the Purchase profile.

Read/search must not expose rows the current Frappe user cannot read.

PDF must retain read + print permission.

Email must retain read/print/email-related existing checks and approval.

Lifecycle actions must retain action-appropriate permission checks/native enforcement.

---

# 11. India Compliance requirements

India Compliance is optional.

Task 28 must work on:

```text
ERPNext-only site
ERPNext + India Compliance site
```

Do not import India Compliance at shared module import time just to support Sales Invoice.

For Sales Invoice:

```text
PDF -> native before_print hooks may run
submit -> native validate/on_submit hooks may run
cancel -> native before_cancel hooks may run
```

MCP must not copy or replace:

```text
GST calculations
HSN validation
IRN rules
e-Invoice generation/cancellation
e-Waybill generation/cancellation
backdated GST rules
GST account validation
```

If a native hook blocks the operation, the MCP result must be failure, not synthetic success.

If a native submit/cancel schedules external compliance work, report only the document lifecycle result that the MCP can actually know. Do not claim remote e-Invoice/e-Waybill completion synchronously.

---

# 12. Error behavior

Reuse current safe public error envelopes and error-reference mechanism.

Do not expose:

```text
stack traces
SQL
filesystem paths
credentials
shared secrets
internal approval digests
IRN API credentials/responses
unreadable accounting data
```

Use established codes where they already fit.

If action-scoped policy needs a distinct deterministic error, prefer an existing style such as `DOCTYPE_NOT_ALLOWED` or a clearly named `ACTION_NOT_ALLOWED` only if that improves accuracy without breaking current contracts/tests.

Whichever code is chosen, tests must lock it.

A Sales Invoice update/child-add denial must occur before approval creation or mutation.

---

# 13. Required tests

Tests must cover the real architecture change, not only happy-path mocks.

## 13.1 Action-policy regression matrix

At minimum test:

```text
Sales / Quotation   -> existing lifecycle behavior unchanged
Sales / Sales Order -> existing lifecycle behavior unchanged
Sales / Customer    -> existing lifecycle behavior unchanged where currently supported
Sales / Item        -> existing lifecycle behavior unchanged where currently supported
Purchase / Purchase Order -> unchanged
Purchase / Supplier -> unchanged where currently supported
Purchase / Item     -> unchanged where currently supported
```

Then Sales Invoice:

```text
submit    -> policy permits target
cancel    -> policy permits target
delete    -> policy permits target
update    -> denied before approval
child_add -> denied before approval
```

And:

```text
Purchase profile + Sales Invoice -> denied
```

## 13.2 Read tests

Test:

1. exact Sales Invoice get success;
2. not-found result;
3. read-permission denial;
4. bounded item projection;
5. `party == customer`;
6. primary public date is sourced correctly from `posting_date`;
7. secondary date is sourced from `due_date`;
8. search by customer;
9. search by docstatus/status;
10. date range uses `posting_date` for Sales Invoice;
11. search ordering does not use a nonexistent field;
12. Sales Invoice unavailable in Purchase profile;
13. existing Quotation/Sales Order/Purchase Order behavior unchanged.

## 13.3 PDF tests

Test:

1. Sales Invoice accepted by typed contract;
2. Sales profile permits SI PDF;
3. Purchase profile rejects SI PDF;
4. read denied;
5. print denied;
6. native `frappe.get_print` path called exactly as existing behavior requires;
7. no custom SI PDF renderer;
8. existing Q/SO/PO PDF tests remain green.

Where installed-hook behavior is mocked, verify Task 28 does not bypass the native print seam. Do not claim live India Compliance print verification unless actually run.

## 13.4 Email tests

Test:

1. SI party mapping resolves Customer;
2. native `contact_email` preferred according to current logic;
3. Customer/Contact fallback stays permission-safe;
4. ambiguous recipients -> existing `needs_input` result;
5. invalid unrelated requested recipient -> denied;
6. prepare sends nothing;
7. confirm queues exactly once;
8. replay does not duplicate queueing;
9. stale modified/docstatus state fails;
10. stale recipient fails;
11. stale PDF digest fails;
12. Purchase profile rejects Sales Invoice email;
13. existing email doctypes remain green.

## 13.5 Submit tests

Test at minimum:

1. Sales Invoice target reaches existing submit flow;
2. Draft state produces prepared approval when other mocked checks permit;
3. confirm without valid approval is denied;
4. wrong user/site/action token denied;
5. replay denied;
6. native `doc.submit()` invoked exactly once on successful confirm;
7. no direct GL/stock/compliance API called by MCP service;
8. native submit error rolls back/surfaces safely;
9. document state change after prepare triggers existing stale behavior;
10. Purchase profile denied.

## 13.6 Cancel tests

Test:

1. submitted SI can prepare cancellation under policy;
2. native `doc.cancel()` is the mutation seam;
3. invalid state/native blocker returns safe failure;
4. approval replay/wrong context denied;
5. no MCP-level GST/e-Invoice reversal implementation is called;
6. Purchase profile denied.

## 13.7 Delete tests

Test:

1. Draft SI delete through existing native deletion path;
2. Submitted SI uses current cancel-then-delete planning semantics where applicable;
3. linked blocker is surfaced;
4. no cascade delete;
5. approval required;
6. replay denied;
7. Purchase profile denied.

## 13.8 Explicit deny tests

These are mandatory:

```text
prepare_update(Sales Invoice) -> denied, approvals.create NOT called
prepare_child_add(Sales Invoice) -> denied, approvals.create NOT called
```

If confirm tools can only be reached with a valid server-held approval, prove there is no way to fabricate a Sales Invoice update/child-add confirmation through a token for another action.

## 13.9 Task 27 regression

Run the current focused Task 27 tests and prove both tools remain present and unchanged in public behavior.

## 13.10 Full regression

Run the repository's full unit test suite after focused tests.

---

# 14. Commands / verification

Use the repository's existing Python environment and test conventions. Do not invent a new test runner.

Expected command family, adjusted only to actual repository paths:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_read \
  mcp_erpnext.tests.test_pdf \
  mcp_erpnext.tests.test_email \
  mcp_erpnext.tests.test_lifecycle \
  mcp_erpnext.tests.test_tool_registration \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_tool_contracts
```

Include a focused Sales Invoice test module if created.

Also run Task 27 regression, for example:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_sales_order_to_sales_invoice
```

Then:

```text
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m compileall -q mcp_erpnext
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
git diff --check
```

If exact environment-relative paths differ, use the current repository's established equivalent and document the exact commands/results.

Do not run live destructive bench/site writes unless separately authorized.

Read-only source/runtime inspection is acceptable if needed.

---

# 15. Optional live verification gate

Unit/static implementation is required.

Live Sales Invoice lifecycle operations are NOT automatically authorized by this task because submit/cancel/delete can produce or reverse accounting/stock/compliance effects.

If no disposable live fixture and explicit authorization exist, report:

```text
NOT VERIFIED LIVE
```

for actual submit/cancel/delete.

Do not turn that into a blocker for completing the unit-tested implementation.

If live verification is separately authorized, use isolated disposable test data and explicitly record:

```text
site
user/role category (no secrets)
Sales Invoice name
action performed
before state
after state
whether India Compliance is installed
whether stock update is involved
whether external e-Invoice/e-Waybill work was triggered
cleanup result
```

Never test destructive lifecycle behavior against production/customer invoices merely to satisfy this task.

---

# 16. Acceptance criteria

Task 28 is complete only when ALL applicable criteria are satisfied.

## Architecture

- [ ] Existing shared read/PDF/email/lifecycle engines were reused.
- [ ] Action-scoped lifecycle policy exists before Sales Invoice lifecycle access is enabled.
- [ ] `PROFILE_DOCTYPES` or equivalent broad set is no longer the sole authorization decision for every lifecycle action.
- [ ] Existing doctypes preserve their previous behavior.
- [ ] No universal policy framework/DSL/plugin system was introduced.

## Sales Invoice read/search

- [ ] Sales Invoice is accepted by typed read contracts.
- [ ] Sales profile can get/search SI with normal permissions.
- [ ] Customer is the party field.
- [ ] `posting_date` drives the normalized transaction/search date behavior.
- [ ] `due_date` is the secondary date.
- [ ] item output remains bounded.
- [ ] Purchase profile cannot read/search SI through these MCP wrappers.

## PDF

- [ ] Sales Invoice is allowed by typed PDF contract for Sales profile.
- [ ] Existing native `frappe.get_print` path is reused.
- [ ] Read + print permissions remain enforced.
- [ ] No custom Sales Invoice renderer exists.

## Email

- [ ] Sales Invoice is allowed by typed email contract for Sales profile.
- [ ] SI maps to Customer through `customer`.
- [ ] existing contact/recipient rules are reused.
- [ ] prepare queues/sends nothing.
- [ ] confirm is approval-bound and queues through Frappe.
- [ ] queued is not represented as delivered.
- [ ] native PDF attachment path is reused.

## Lifecycle

- [ ] Sales Invoice submit is allowed only through existing approval-gated lifecycle.
- [ ] Sales Invoice cancel is allowed only through existing approval-gated lifecycle.
- [ ] Sales Invoice delete is allowed only through existing approval-gated lifecycle.
- [ ] Generic Sales Invoice update is denied before approval/mutation.
- [ ] Sales Invoice child-add is denied before approval/mutation.
- [ ] no approval token/action cross-use is possible.
- [ ] native `doc.submit`, `doc.cancel`, and existing delete path remain final mutation seams.
- [ ] no direct GL/stock/GST mutation was added.

## Security

- [ ] no `ignore_permissions=True` write path was introduced.
- [ ] no Administrator fallback.
- [ ] no client-selected user override.
- [ ] no direct SQL write.
- [ ] no secrets added.
- [ ] no cross-profile SI exposure.

## Optional apps

- [ ] ERPNext-only import remains valid.
- [ ] no India Compliance module import is required at core module load time.
- [ ] installed native hooks are not bypassed.

## Regression

- [ ] Task 27 focused tests pass.
- [ ] lifecycle/read/PDF/email focused tests pass.
- [ ] tool registration/profile/contract tests pass.
- [ ] full test suite passes.
- [ ] compileall passes.
- [ ] generated tool catalog check passes.
- [ ] `git diff --check` passes.

## Reporting

- [ ] implementation report created.
- [ ] changed files and exact tests/results documented.
- [ ] live/non-live verification clearly distinguished.

---

# 17. Expected results

After successful Task 28 implementation, the Sales profile capability model should be conceptually:

```text
Sales profile

Creation / conversion
  Quotation creation                     existing
  Sales Order creation                   existing
  Quotation -> Sales Order              existing
  Sales Order -> Sales Invoice          Task 27 existing

Existing Sales Invoice
  get/search                            Task 28 enabled
  PDF                                   Task 28 enabled
  email                                 Task 28 enabled
  submit                                Task 28 enabled + approval
  cancel                                Task 28 enabled + approval
  delete                                Task 28 enabled + approval
  generic update                        DENIED
  generic child add                     DENIED

Standalone Sales Invoice creation
  prepare_sales_invoice                 NOT YET - Task 29
  confirm_sales_invoice                 NOT YET - Task 29
```

A Sales Invoice becoming readable/printable/emailable must not automatically become generically editable.

---

# 18. Known limitations / boundaries after Task 28

Even after Task 28, the following remain intentionally unsupported:

1. standalone/direct Sales Invoice creation;
2. generic SI field update;
3. generic SI item add/remove/edit;
4. Delivery Note -> Sales Invoice conversion;
5. POS;
6. `update_stock=1` direct-sales workflow;
7. return/Credit Note;
8. Debit Note;
9. Payment Entry creation;
10. advance allocation;
11. Timesheet/Project billing workflows;
12. inter-company/consolidated/recurring variants;
13. explicit MCP e-Invoice/e-Waybill generation/cancellation tools.

Task 28 should not solve these opportunistically.

Live submit/cancel/delete verification may remain pending when no explicitly authorized disposable fixture is available.

---

# 19. Required implementation report

Create:

```text
docs/inspect/SALES_INVOICE_EXISTING_DOCUMENT_CAPABILITIES_IMPLEMENTATION_REPORT.md
```

The report must include:

## A. Result

State exactly which capabilities are now available for Sales Invoice.

## B. Existing architecture inspected

List relevant read/PDF/email/lifecycle/profile/contract files inspected before changes.

## C. Action-policy design

Document:

```text
previous authorization coupling
new action-scoped policy shape
existing behavior preserved
Sales Invoice allow/deny matrix
```

Explicitly state how generic SI update and child-add are prevented.

## D. Files changed

Exact paths only.

## E. Read/search implementation

Document Sales Invoice field mapping and date filtering/ordering behavior.

## F. PDF implementation

Confirm native print path and permission behavior.

## G. Email implementation

Confirm Customer party mapping, recipient behavior, PDF reuse, approval, and queued semantics.

## H. Lifecycle implementation

Document submit/cancel/delete authorization and native mutation seams.

## I. Permission/security behavior

Confirm no bypasses or Administrator fallback.

## J. India Compliance / ERPNext-only behavior

State exactly what was verified and whether optional-app imports remain safe.

## K. Tests run

Exact commands and exact pass/fail counts.

## L. Task 27 regression

State whether `prepare_sales_order_to_sales_invoice` and `confirm_sales_order_to_sales_invoice` remained unchanged and tests passed.

## M. Live verification

Clearly distinguish:

```text
VERIFIED LIVE
NOT VERIFIED LIVE
```

per operation.

Do not imply real accounting/e-Invoice behavior was tested when it was mocked/static only.

## N. Known limitations

Carry forward the intentionally unsupported capabilities.

## O. Exact next task

Must be:

```text
Task 29 - Standalone Sales Invoice Creation Foundation
```

Do not implement Task 29 in Task 28.

---

# 20. Exact next task

After Task 28 is implemented, tested, and its report reviewed, the next task is only:

```text
Task 29 - Standalone Sales Invoice Creation Foundation
```

Task 29 will introduce the separate public pair:

```text
prepare_sales_invoice
confirm_sales_invoice
```

for bounded direct Draft Sales Invoice creation from Customer + Items using native ERPNext defaults/taxes/accounts/policy checks.

Task 29 must not be started as part of this task.
