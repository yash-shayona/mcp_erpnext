# Task 41 — Delivery Note Native Flow Audit

## 0. Task Identity

**Project:** `mcp_erpnext`  
**Profile:** `sales`  
**Task number:** `41`  
**Task type:** Architecture / native-flow inspection only  
**Implementation changes:** **Not allowed in this task**  
**Current baseline ZIP:** `mcp_erpnext_2026-09-14T06-01-23Z.zip`  
**Primary ERPNext target:** The exact ERPNext/Frappe version installed on the configured target site  
**Expected report:** `docs/inspect/DELIVERY_NOTE_NATIVE_FLOW_AUDIT.md`

---

# 1. Background / Why This Task Exists

The Sales profile is now able to cover the current service-oriented selling path through Sales Invoice:

```text
Customer
  -> Item
  -> Quotation
  -> Sales Order
  -> Sales Invoice
```

However, the project is intended to be a **generic ERPNext MCP server**, not a server hard-coded only for the current company's service business.

A future client may sell:

- stock products only;
- services only;
- both stock products and services;
- goods requiring a separate shipment / fulfilment step;
- goods sold directly through Sales Invoice with stock update;
- partially delivered orders;
- orders containing a mixture of deliverable and delivery-exempt rows.

ERPNext supports a Delivery Note between Sales Order and Sales Invoice when native business configuration and transaction state require or use it.

The current MCP implementation does **not** yet expose Delivery Note capabilities.

The latest repository already contains an important signal: standalone Sales Invoice creation can return a bounded `DELIVERY_NOTE_REQUIRED` prerequisite when native ERPNext rejects direct invoicing, but the MCP server currently has no Delivery Note workflow to continue from that state.

Therefore, before moving the main development sequence into Accounts / Payment Entry, inspect the complete native Delivery Note behavior and determine the correct MCP V1 architecture.

This task must **not** implement Delivery Note yet.

---

# 2. Confirmed Current Repository State to Re-Verify

Do not trust this section blindly. Re-verify it against the current repository before writing the report.

At the Task 41 baseline, the repository appears to have:

```text
mcp_erpnext/tools/selling/
    quotation.py
    quotation_read.py
    quotation_to_sales_order.py
    sales_order.py
    sales_order_read.py
    sales_order_to_sales_invoice.py
    sales_invoice.py
    sales_invoice_read.py
```

and corresponding Sales services/contracts, but no Delivery Note tool/service/read/contract modules.

The Sales profile currently registers:

- Customer create/read/query/aggregate;
- Item create/read/query/aggregate;
- Quotation create/read/query/aggregate;
- Quotation -> Sales Order conversion;
- Sales Order create/read/query/aggregate;
- Sales Order -> Sales Invoice conversion;
- Sales Invoice standalone create/read/query/aggregate;
- current generic lifecycle capabilities under the Sales lifecycle policy;
- generic document PDF;
- generic document email.

Also re-verify these current boundaries:

1. `Delivery Note` is not registered as a Sales public tool capability.
2. `Delivery Note` is not currently included in the Sales lifecycle action policy.
3. The standalone Sales Invoice service recognizes native Sales Order / Delivery Note prerequisite failures in a bounded form.
4. The REST backend static operation registry has no Delivery Note operations.
5. No Delivery Note-specific public typed contracts currently exist.
6. Purchase profile behavior is separate and must remain unchanged.

If any of the above is no longer true in the actual repository being inspected, document the difference first and base the audit on the actual current state.

---

# 3. Objective

Inspect the exact current `mcp_erpnext` implementation and the exact installed ERPNext/Frappe native Delivery Note flow, then produce a source-backed architecture decision for Delivery Note V1.

The audit must determine:

1. When ERPNext expects or permits a Delivery Note.
2. When a Delivery Note is not needed.
3. How Selling Settings, Customer exceptions, Item properties, Sales Order row state, and other native ERPNext rules affect that decision.
4. How a submitted Sales Order is natively mapped to a Delivery Note.
5. Whether and how ERPNext supports a standalone Delivery Note without a Sales Order.
6. How partial deliveries work.
7. How mixed stock/service Sales Orders work.
8. How service-item delivery skipping works in the installed version.
9. What happens when a Delivery Note is submitted.
10. What stock, ledger, Sales Order, serial/batch, warehouse, packed-item, reservation, and installed-app side effects occur.
11. How cancellation and deletion behave.
12. How a Delivery Note is natively converted/mapped to Sales Invoice.
13. What happens for already invoiced, already delivered, returned, closed, or otherwise non-eligible source rows.
14. Which Delivery Note capabilities belong in the public Sales MCP V1.
15. Which mechanics should reuse existing generic MCP foundations.
16. Which business rules must remain owned by ERPNext rather than duplicated in MCP.
17. How the capability must work consistently with both the direct backend and the new REST backend.
18. What exact Task 42 implementation scope should be.

The result must be a design that supports generic ERPNext businesses without forcing every client to manually define a custom Quotation -> Sales Order -> Delivery Note -> Sales Invoice workflow configuration.

---

# 4. Frozen Architecture Principles for This Audit

These principles are already decided for Task 41. Do not reopen them unless exact current ERPNext behavior makes one technically impossible; if so, document evidence rather than silently changing the decision.

## 4.1 ERPNext remains the business authority

MCP must not duplicate ERPNext rules for:

- whether Sales Order is mandatory;
- whether Delivery Note is mandatory before Sales Invoice;
- whether a Customer is exempt;
- which Sales Order rows require delivery;
- which service/non-stock rows may skip delivery;
- remaining deliverable quantity;
- over-delivery tolerance;
- warehouse requirements;
- serial/batch behavior;
- Product Bundle behavior;
- stock availability and stock validation;
- native status and percentage calculations;
- document mapping rules;
- accounting/stock side effects;
- installed-app hooks.

Where ERPNext provides a native mapper/helper/controller path, inspect and prefer it.

## 4.2 Do not introduce client-specific business-type configuration

Do **not** propose or implement configuration such as:

```text
BUSINESS_TYPE=service
BUSINESS_TYPE=product
USES_DELIVERY_NOTE=true/false
USES_QUOTATION=true/false
USES_SALES_ORDER=true/false
USES_SALES_INVOICE=true/false
```

A single company may sell stock goods, non-stock services, mixed orders, or direct stock sales at the same time. A global product/service switch is therefore not an acceptable substitute for ERPNext's native transaction rules.

## 4.3 Profile selection remains coarse domain capability selection

Conceptually:

```text
MCP_PROFILE=sales
```

means the supported Sales-domain capabilities are available.

It must **not** mean every client must separately configure each normal sales document in MCP.

ERPNext configuration and transaction state determine whether a particular native path is valid.

## 4.4 MCP capability permission and ERP business validity are different concerns

A future deployment-level capability restriction may decide whether an AI/client is permitted to use a particular MCP capability.

That is distinct from ERPNext deciding whether the business operation itself is valid.

For Task 41:

- inspect whether current profile/action allowlists can support future Delivery Note capability restrictions cleanly;
- do not implement a new capability-toggle system;
- do not turn ERP business workflow into MCP configuration.

## 4.5 Public business tools may be explicit while internals remain shared

Existing project architecture permits patterns such as:

```text
explicit business MCP tool
        -> shared internal mechanics
        -> ERPNext native authority
```

Do not expose a generic arbitrary `convert_document` just because mapping mechanics can be shared internally.

## 4.6 Purchase profile is frozen

Task 41 concerns the Sales profile only.

Purchase may be inspected only where a shared internal mechanism must be understood.

Do not redesign, extend, rename, or refactor Purchase behavior.

## 4.7 Accounts work is not part of Task 41

Do not implement or redesign:

- Accounts profile;
- Payment Entry;
- Journal Entry;
- Purchase Invoice;
- Payment Reconciliation;
- Accounts Receivable tools;
- Accounts Payable tools.

Delivery Note closes a missing fulfilment capability in the Sales domain before the project continues into Accounts.

---

# 5. Site / Runtime Boundary — No Hard-Coded Site

The audit must be **site-agnostic**.

Do not hard-code names such as:

```text
shayona.localhost
yob.localhost
roughnote.localhost
```

or any other specific site name into production design, tests, task recommendations, runtime helpers, or future implementation contracts.

Use the project's existing configuration/runtime authority.

For the direct backend, inspect/use the configured site from the existing runtime path, including the existing `MCP_FRAPPE_SITE` mechanism and current runtime context behavior.

For the REST backend, respect the configured `ERPNEXT_BASE_URL` and the existing bounded remote-operation architecture.

The audit report may state which site was actually inspected as test evidence, but the resulting design must work for **whatever valid site is configured**.

Also verify that site/user binding, approval binding, permissions, and runtime context remain consistent with the current project architecture.

---

# 6. Allowed Changes

This is an inspection-only task.

The only repository file that may be created or modified is:

```text
docs/inspect/DELIVERY_NOTE_NATIVE_FLOW_AUDIT.md
```

If the existing repository has a materially different exact report naming convention, follow that convention, but create only one inspection report.

Do not alter the supplied Task 41 file merely to claim completion.

---

# 7. Explicitly Forbidden Changes

Do not modify production or test implementation in this task.

Specifically do **not** add/change:

```text
mcp_erpnext/tools/**
mcp_erpnext/services/**
mcp_erpnext/contracts/**
mcp_erpnext/config/**
mcp_erpnext/profiles/**
mcp_erpnext/settings.py
mcp_erpnext/runtime.py
mcp_erpnext/remote_operations.py
mcp_erpnext/remote_api.py
mcp_erpnext/approvals.py
mcp_erpnext/hooks.py
mcp_erpnext/tests/**
scripts/generate_tool_catalog.py
docs/TOOLS.md
```

Also do not:

- add Delivery Note tools;
- register Delivery Note in the profile;
- change lifecycle allowlists;
- add remote REST operations;
- add contracts;
- add migrations/patches/fixtures;
- mutate ERPNext data just to complete the audit;
- submit/cancel/delete production documents;
- change Selling Settings;
- change Customer exceptions;
- change Stock Settings;
- change Items/Warehouses;
- change permissions/roles;
- add custom fields;
- add a new `MCP_PROFILE`;
- add workflow configuration flags;
- refactor unrelated code.

Read-only inspection is the default.

If safe throwaway test transactions are absolutely required to distinguish native behavior that cannot be proven from source/tests/metadata alone, the report must clearly separate them from production data and state exactly what was created. Prefer existing test infrastructure or source tracing first.

---

# 8. Repository Inputs to Inspect First

Before looking at ERPNext source, trace the current MCP architecture completely enough to know what a Delivery Note implementation would need to integrate with.

At minimum inspect the actual current versions of:

## 8.1 Profile and tool registration

```text
mcp_erpnext/settings.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/profiles/purchase.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/tools/selling/__init__.py
mcp_erpnext/tests/test_profiles.py
mcp_erpnext/tests/test_tool_registration.py
```

Answer:

- what is currently exposed by `sales`;
- what is intentionally isolated to `purchase`;
- where Delivery Note would eventually register;
- whether tool registration has any hidden/static assumptions that affect adding another Sales document.

## 8.2 Existing Sales create/conversion patterns

Inspect:

```text
mcp_erpnext/tools/selling/quotation.py
mcp_erpnext/services/selling/quotation.py
mcp_erpnext/contracts/selling/quotation.py

mcp_erpnext/tools/selling/sales_order.py
mcp_erpnext/services/selling/sales_order.py
mcp_erpnext/contracts/selling/sales_order.py

mcp_erpnext/tools/selling/quotation_to_sales_order.py
mcp_erpnext/services/selling/quotation_to_sales_order.py
mcp_erpnext/contracts/selling/quotation_to_sales_order.py

mcp_erpnext/tools/selling/sales_order_to_sales_invoice.py
mcp_erpnext/services/selling/sales_order_to_sales_invoice.py
mcp_erpnext/contracts/selling/sales_order_to_sales_invoice.py

mcp_erpnext/tools/selling/sales_invoice.py
mcp_erpnext/services/selling/sales_invoice.py
mcp_erpnext/contracts/selling/sales_invoice.py
```

Determine which patterns are sound and reusable for Delivery Note, especially:

- typed public contracts;
- bounded outputs;
- prepare -> explicit approval -> confirm;
- native mapping;
- fresh remapping at confirmation;
- stale confirmation detection;
- one-shot approval claim;
- site/user/action binding;
- Draft-only creation behavior;
- normal Frappe permissions;
- safe exception mapping;
- no internal ERP message leakage.

Do not automatically copy a pattern where Delivery Note stock behavior creates different safety requirements. Document required differences.

## 8.3 Existing read/query/aggregate patterns

Inspect:

```text
mcp_erpnext/tools/selling/sales_order_read.py
mcp_erpnext/services/selling/sales_order_read.py
mcp_erpnext/contracts/selling/sales_order_read.py

mcp_erpnext/tools/selling/sales_invoice_read.py
mcp_erpnext/services/selling/sales_invoice_read.py
mcp_erpnext/contracts/selling/sales_invoice_read.py

mcp_erpnext/services/common/read.py
mcp_erpnext/services/common/aggregate.py
```

Determine whether Delivery Note can reuse the same field-aware read/query/aggregate foundations without introducing a parallel query engine.

## 8.4 Lifecycle architecture

Inspect:

```text
mcp_erpnext/tools/lifecycle.py
mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/contracts/lifecycle.py
mcp_erpnext/tests/test_lifecycle.py
```

Specifically document current Sales action-scoped allowlists and explain exactly what future Delivery Note submit/cancel/delete support would require.

Do not change the policy in Task 41.

## 8.5 PDF and email foundations

Inspect:

```text
mcp_erpnext/tools/pdf.py
mcp_erpnext/services/common/pdf.py
mcp_erpnext/contracts/pdf.py

mcp_erpnext/tools/email.py
mcp_erpnext/services/common/email.py
mcp_erpnext/contracts/email.py
```

Determine whether Delivery Note can safely participate in the existing Sales-profile generic document PDF/email foundations merely through a DocType allowlist/policy change, or whether special handling is required.

## 8.6 Approval / interaction / observability foundations

Inspect:

```text
mcp_erpnext/approvals.py
mcp_erpnext/contracts/interaction.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/observability.py
```

Document how Delivery Note mutating operations should bind to the existing approval model and bounded error model.

## 8.7 Direct + REST backend architecture

Task 40 introduced a REST backend. Delivery Note must not become a direct-backend-only feature.

Inspect:

```text
mcp_erpnext/runtime.py
mcp_erpnext/rest_client.py
mcp_erpnext/remote_operations.py
mcp_erpnext/remote_api.py
mcp_erpnext/tests/test_rest_backend.py
docs/inspect/REST_BACKEND_IMPLEMENTATION_REPORT.md
```

Determine what Task 42 will need so every new Delivery Note public capability has the same behavior in:

```text
MCP_BACKEND=direct
```

and

```text
MCP_BACKEND=rest
```

Do not create generic remote dispatch or arbitrary DocType CRUD.

## 8.8 Existing task/report history

Inspect relevant task files and implementation/audit reports, including at minimum:

```text
docs/tasks/audits/26_TASK_SALES_INVOICE_NATIVE_FLOW_INSPECTION.md
docs/tasks/implementation/27_TASK_SALES_ORDER_TO_SALES_INVOICE_NATIVE_CONVERSION_FOUNDATION.md
docs/tasks/implementation/28_TASK_SALES_INVOICE_EXISTING_DOCUMENT_CAPABILITIES_AND_ACTION_SCOPED_LIFECYCLE_POLICY.md
docs/tasks/implementation/29_TASK_STANDALONE_SALES_INVOICE_CREATION_FOUNDATION.md
docs/tasks/implementation/31_TASK_SHARED_INTERNAL_AGGREGATE_FOUNDATION.md
docs/tasks/audits/35_TASK_SALES_MUTATION_ARCHITECTURE_AUDIT.md
docs/tasks/audits/36_TASK_FRAPPE_ERP_AUTHORITY_DUPLICATION_AUDIT.md
docs/tasks/implementation/37_TASK_REMOVE_CONFIRMED_SALES_BUSINESS_RULE_DUPLICATION.md
docs/tasks/audits/38_TASK_SHARED_APPROVAL_STORE_FRAPPE_CACHE_AUDIT.md
docs/tasks/implementation/39_TASK_IMPLEMENT_FRAPPE_NATIVE_SHARED_APPROVAL_STORE.md
docs/tasks/implementation/40_TASK_IMPLEMENT_REST_BACKEND.md
```

Previous tasks are context, not a substitute for inspecting current code.

---

# 9. Exact Installed Frappe / ERPNext Source Must Be Inspected

The installed source on the configured ERPNext environment is authoritative for implementation design.

Do not design Delivery Note from memory or from generic accounting/ERP assumptions.

Locate the actual installed source responsible for:

- Sales Order -> Delivery Note mapping;
- Delivery Note controller validation;
- Delivery Note submit/cancel behavior;
- stock ledger behavior;
- Sales Order delivered quantity/status updates;
- Delivery Note -> Sales Invoice mapping;
- Delivery Note return handling;
- serial/batch handling;
- Product Bundle / packed item handling;
- warehouse validation;
- stock reservation interaction;
- Selling Settings requirement validation;
- Customer exceptions;
- service-item delivery skipping;
- permissions and mapping permission behavior.

Search by symbol/behavior instead of assuming the exact file layout.

Useful search terms include:

```text
make_delivery_note
DeliveryNote
Delivery Note
Delivery Note Item
make_sales_invoice
against_sales_order
sales_order
so_detail
dn_detail
delivery_note
per_delivered
delivered_qty
skip_delivery
skip_delivery_note
is_stock_item
is_fixed_asset
product_bundle
delivered_by_supplier
warehouse
serial_no
batch_no
serial_and_batch_bundle
Stock Ledger Entry
GL Entry
update_stock_ledger
update_prevdoc_status
validate_with_previous_doc
Sales Order required
Delivery Note required
allow_sales_invoice_creation_without_sales_order
allow_sales_invoice_creation_without_delivery_note
```

Possible source areas may include, but are not limited to:

```text
apps/erpnext/erpnext/selling/doctype/sales_order/**
apps/erpnext/erpnext/stock/doctype/delivery_note/**
apps/erpnext/erpnext/accounts/doctype/sales_invoice/**
apps/erpnext/erpnext/controllers/**
apps/erpnext/erpnext/stock/**
apps/erpnext/erpnext/selling/doctype/customer/**
apps/frappe/frappe/model/**
```

Do not assume these paths are identical in every installed version. Find the actual callable/source in the environment.

Official Frappe/ERPNext documentation and the official `frappe/erpnext` GitHub repository may be used as secondary evidence, but the exact installed code remains primary for runtime behavior.

---

# 10. Mandatory Native Flow Questions

The report must answer every question below with source evidence.

## 10.1 Sales Order -> Delivery Note mapper

Find the exact native ERPNext callable used by the installed version when the ERPNext UI performs the equivalent of:

```text
Submitted Sales Order
    -> Create
    -> Delivery Note
```

Document:

- exact callable/module;
- source permission behavior;
- required source docstatus;
- target DocType;
- item row mapping rules;
- source-row lineage fields;
- remaining quantity logic;
- already delivered quantity behavior;
- partial delivery behavior;
- returned quantity behavior;
- over-delivery allowance behavior;
- item filtering behavior;
- service-row filtering/skip behavior;
- Product Bundle behavior;
- drop-ship rows;
- reserved stock arguments/options;
- any optional mapper arguments/flags;
- postprocess functions/default setters;
- taxes/terms/address fields mapped;
- warehouses and stock fields mapped;
- serial/batch data mapped or derived;
- how target Draft validation/defaulting occurs.

Do not reimplement any native mapping algorithm in MCP.

## 10.2 Source eligibility

Determine what makes a Sales Order eligible or ineligible for Delivery Note creation.

Cover at minimum:

- Draft Sales Order;
- Submitted Sales Order;
- Cancelled Sales Order;
- Closed Sales Order;
- fully delivered Sales Order;
- partially delivered Sales Order;
- partially returned Sales Order;
- fully billed but not delivered state if possible;
- service-only order;
- mixed stock/service order;
- drop-shipped rows;
- product bundles;
- rows with no remaining deliverable quantity.

Identify whether the native mapper returns an empty target, throws a validation, filters rows, or uses another behavior for each important case.

## 10.3 Selling Settings and Customer exceptions

Trace the exact native fields and validation functions controlling:

- whether Sales Order is required before Delivery Note;
- whether Delivery Note is required before Sales Invoice;
- Customer-level exceptions;
- service-item Delivery Note skipping;
- any order-type-specific delivery skipping;
- same-rate enforcement across Sales Order / Delivery Note / Sales Invoice;
- over-delivery allowance if relevant.

Do not propose MCP mirrors of these settings.

The MCP design must defer to native settings at operation time.

## 10.4 Service-only and mixed orders

This is mandatory because the current company primarily sells services while the MCP server is intended for generic businesses.

Verify exact installed behavior for:

```text
A. service-only Sales Order
B. stock-only Sales Order
C. stock + service Sales Order
D. fixed asset rows if relevant
E. Product Bundle rows containing stock items
F. supplier-delivered/drop-shipped rows
```

Determine:

- which rows need Delivery Note;
- which rows are skipped;
- how `% Delivered` is calculated;
- whether a service-only order can complete through billing;
- whether mixed orders create Delivery Notes only for deliverable rows;
- whether this depends on a global Selling Setting, per-order flag, item state, or a combination in the installed version.

The report must distinguish confirmed installed behavior from documentation-only behavior.

## 10.5 Standalone Delivery Note

Inspect whether ERPNext supports creation of a Delivery Note without a Sales Order and under what native configuration/permission conditions.

Determine:

- whether this is a legitimate ERPNext flow;
- which fields must be provided/derived;
- how Customer/company/posting date/warehouse/items/rates/taxes/defaults are resolved;
- which native controller validations apply;
- whether a standalone MCP Delivery Note V1 is necessary immediately or should be deferred;
- whether implementing only SO -> DN would leave a meaningful generic-business gap.

Do not assume the answer before inspecting installed source and UI behavior.

## 10.6 Delivery Note submit side effects

Trace `Delivery Note` submission end-to-end.

At minimum determine whether and under what conditions it causes:

- Stock Ledger Entries;
- GL Entries or stock-accounting entries;
- Sales Order delivered quantity update;
- Sales Order `% Delivered` update;
- Sales Order status change;
- packed item updates;
- serial/batch bundle submission/updates;
- stock reservation updates;
- project/accounting dimension effects;
- shipment-related state;
- any installed-app hooks;
- any background jobs;
- any irreversible/external side effects.

Do **not** state "Delivery Note only changes stock" unless exact installed source proves the complete behavior.

This section is critical to future approval/safety design.

## 10.7 Delivery Note cancel side effects

Trace cancellation and rollback behavior.

Determine:

- what stock effects reverse;
- what Sales Order delivery state reverses;
- serial/batch implications;
- linked Sales Invoice restrictions;
- return-document restrictions;
- immutable-ledger/backdated implications;
- whether cancellation can fail because of downstream links;
- installed-app restrictions.

The MCP should use normal ERPNext cancellation authority and must not manually reverse side effects.

## 10.8 Delivery Note delete behavior

Determine the valid native delete states and linked-document restrictions.

Task 42 must not silently delete linked Sales Invoices, returns, packing slips, shipment records, or any other records merely to make a Delivery Note deletable.

Document how the current generic lifecycle delete foundation would behave and whether Delivery Note requires narrower handling.

## 10.9 Delivery Note -> Sales Invoice native conversion

Find the exact native ERPNext flow/callable used to create a Sales Invoice from a Delivery Note.

Trace:

- source eligibility;
- required source docstatus;
- already billed quantities;
- partial billing;
- source-row lineage (`delivery_note`, `dn_detail`, and any Sales Order lineage);
- customer/company/currency;
- rates/taxes/addresses;
- warehouses/stock fields;
- payment terms/schedule;
- project/accounting dimensions;
- already-returned or otherwise ineligible rows;
- native target defaults;
- permissions;
- installed-app hooks.

Determine whether generic product-flow completion requires Task 42 itself to implement DN -> SI conversion or whether it should be a separate immediately-following task.

Give a recommendation based on cohesion, risk, and current project task sizing—not arbitrary preference.

## 10.10 Sales Invoice direct-stock alternative

Inspect how Delivery Note fits beside ERPNext's direct Sales Invoice stock flow.

The report must explain the architecture without encoding a hard-coded rule such as:

```text
stock item => always Delivery Note
```

Verify how a direct Sales Invoice with stock update differs from:

```text
Sales Order -> Delivery Note -> Sales Invoice
```

and why MCP should continue letting native ERPNext policy/intent govern valid paths.

This is an architecture explanation only; do not modify Sales Invoice behavior in Task 41.

---

# 11. Stock-Specific Audit Requirements

Delivery Note is materially different from Quotation/Sales Order because submission may mutate stock state.

The audit must therefore inspect these areas even if V1 does not expose every feature.

## 11.1 Warehouse requirements

Determine:

- when source warehouse is required;
- how warehouse is inherited/defaulted from Sales Order/item/company/user settings;
- per-row warehouse behavior;
- target warehouse relevance for returns;
- warehouse permission checks;
- rejected/no-stock cases.

## 11.2 Serial and Batch

Determine the installed-version behavior for:

- serial-numbered items;
- batch-numbered items;
- Serial and Batch Bundle if used by the installed version;
- whether the SO -> DN mapper can pre-populate anything;
- what input remains required from the user at Draft/Submit time;
- what data would be unsafe or overly verbose to expose to the LLM;
- how native validation should be preserved.

Do not design custom serial/batch allocation algorithms in MCP.

## 11.3 Product Bundle / packed items

Trace native handling for Product Bundles and packed items.

Determine:

- what the user-facing Delivery Note item row represents;
- what packed stock rows are generated;
- how source linkage is preserved;
- whether partial delivery is supported and how;
- what must be included in a bounded MCP preview.

## 11.4 Stock Reservation

If the installed ERPNext version supports stock reservation for Sales Orders, inspect how the native Delivery Note mapper interacts with it.

Determine whether mapper arguments/flags exist for reserved stock and whether MCP V1 should expose, derive, or defer those choices.

Do not expose raw internal flags merely because the native function accepts them.

## 11.5 Over-delivery

Trace actual installed over-delivery validation and tolerance ownership.

Do not calculate tolerance manually in MCP.

If current upstream code/issues reveal edge cases, note them separately, but base Task 42 on the installed version's behavior and supported native APIs.

---

# 12. Installed Optional Apps / India Compliance Audit

Check installed apps on the configured site using normal read-only mechanisms.

If `india_compliance` is installed, inspect its exact installed hooks/source/runtime metadata for Delivery Note integration.

Search for relevant behavior such as:

```text
Delivery Note
Delivery Note Item
GST
gst_hsn_code
place_of_supply
gstin
e-Waybill
e_waybill
transporter
vehicle
shipping
e_invoice
doc_events
override_doctype_class
override_whitelisted_methods
validate
on_submit
on_cancel
```

Determine:

- whether India Compliance adds required/custom fields;
- whether it adds validations during save/submit;
- whether e-Waybill or transport behavior is automatic, optional, or a separate explicit action;
- whether Task 42 needs any integration-specific bridge or can rely entirely on normal native hooks.

Do not assume India Compliance is installed on every future client.

The design must remain valid when it is absent.

If another installed official app hooks Delivery Note, note it as well.

---

# 13. Runtime Metadata Audit

Use Frappe runtime DocType metadata as evidence for actual fieldnames and child tables.

At minimum inspect runtime metadata for:

```text
Delivery Note
Delivery Note Item
Sales Order
Sales Order Item
Sales Invoice
Sales Invoice Item
Customer
Item
Warehouse
```

and any directly relevant child DocTypes discovered by source tracing.

Document:

- mandatory fields;
- conditional mandatory behavior that metadata alone cannot express;
- Link fields;
- child tables;
- permission-relevant fields;
- status/docstatus behavior;
- fields needed for bounded read/query output;
- fields that should **not** be exposed to LLMs by default.

Do not use runtime metadata as a replacement for controller validation; use both.

---

# 14. Permissions and Identity Audit

Verify how every proposed future Delivery Note path should preserve the authenticated Frappe user's permissions.

The report must explicitly cover:

- read permission on source Sales Order;
- create permission on Delivery Note;
- submit permission on Delivery Note;
- cancel permission;
- delete permission;
- Warehouse permissions;
- Customer/Item/Company Link visibility where relevant;
- mapper `ignore_permissions` behavior;
- current MCP direct backend user context;
- current REST backend API-user context;
- approval token user/site/action binding.

The future implementation must not use:

```text
ignore_permissions=True
frappe.flags.ignore_permissions
administrator impersonation
permission bypass flags
```

unless an exact native API internally uses a framework-controlled mechanism that is not caller-controlled. If discovered, explain it precisely.

---

# 15. Transaction and Approval Safety Audit

Delivery Note creation and especially submission can affect real inventory.

Evaluate the existing MCP prepare/confirm architecture against this risk.

For future creation/conversion, determine the required flow, likely conceptually:

```text
exact source / bounded request
        -> native ERPNext mapping/defaulting
        -> effective Draft Delivery Note preview
        -> deterministic business fingerprint
        -> shared approval token
        -> explicit confirmation
        -> atomic claim
        -> reload source
        -> native remap / revalidate
        -> stale-state comparison
        -> insert Draft only
```

But do not freeze exact implementation until the audit proves it fits.

For submit/cancel/delete, inspect whether the existing lifecycle approval foundation is sufficient or needs Delivery Note-specific preview details because of stock impact.

At minimum evaluate whether a Delivery Note submit preview should show bounded fields such as:

- document identity;
- customer;
- company;
- posting date/time when materially relevant;
- source Sales Order linkage;
- item code/name;
- quantity;
- warehouse;
- serial/batch summary when relevant;
- stock-impact indicator;
- totals only when relevant.

Do not expose entire ERPNext documents or internal fields by default.

---

# 16. LLM Data-Minimization Audit

This project is intended to expose only the business data the model needs.

For each proposed Delivery Note public capability, identify:

1. what input the LLM/client truly needs to provide;
2. what ERPNext can derive natively;
3. what output the LLM needs to understand the result;
4. what should remain server-internal;
5. what fields may contain unnecessary/sensitive/internal data;
6. how previews can remain bounded.

Specifically avoid passing full documents, unrestricted child rows, raw metadata, raw exception text, internal cache state, secrets, or arbitrary system fields when a bounded business contract is sufficient.

The report must include a proposed minimal input/output table for each candidate Delivery Note V1 capability.

---

# 17. Mandatory Candidate Capability Review

Do not implement these in Task 41. Audit each and classify it as one of:

- `Include in Task 42`
- `Implement immediately after Task 42`
- `Defer from V1`
- `Do not expose publicly`

Candidates to evaluate:

## A. Sales Order -> Delivery Note conversion

Potential explicit public pair:

```text
prepare_sales_order_to_delivery_note
confirm_sales_order_to_delivery_note
```

Determine if this should be the primary V1 creation path.

## B. Standalone Delivery Note creation

Potential explicit public pair:

```text
prepare_delivery_note
confirm_delivery_note
```

Determine whether this is generically necessary now or should be deferred.

## C. Existing Delivery Note read

Potential explicit tool:

```text
get_delivery_note
```

## D. Field-aware Delivery Note query

Potential explicit tool:

```text
query_delivery_notes
```

Naming must follow the current normalized project convention, not historical naming.

## E. Delivery Note aggregate

Potential explicit tool:

```text
aggregate_delivery_notes
```

Evaluate useful V1 aggregates such as count/sum only through the existing safe aggregate foundation.

## F. Submit / cancel / delete

Prefer the current generic lifecycle public capability if architecture audit shows it is still the correct public boundary, with strict Sales action-scoped Delivery Note allowlisting.

Do not create Delivery Note-specific lifecycle tools merely for symmetry unless there is a proven safety/contract reason.

## G. Delivery Note -> Sales Invoice conversion

Potential explicit public pair:

```text
prepare_delivery_note_to_sales_invoice
confirm_delivery_note_to_sales_invoice
```

Evaluate whether this must ship together with Task 42 to avoid leaving the standard goods-sales path incomplete.

## H. PDF / email

Evaluate whether the existing generic document PDF/email tools should support Delivery Note once its DocType is included in the correct Sales allowlist/policy.

## I. Return Delivery Note

Evaluate but likely defer unless the native flow indicates it is essential to safe cancellation/correction behavior.

Do not accidentally implement Sales Return just because Delivery Note supports returns natively.

## J. Packing Slip / Pick List / Delivery Trip

Inspect interactions but do not automatically include these in Delivery Note V1.

Classify each clearly.

---

# 18. Direct and REST Backend Parity Requirement

The Task 42 recommendation must explicitly preserve parity between:

```text
backend = direct
```

and

```text
backend = rest
```

For every public capability recommended for Task 42, document:

- tool wrapper;
- typed contract;
- native service;
- direct execution path;
- REST `rest_arguments` payload;
- fixed remote-operation registry entry;
- remote Frappe execution context;
- bounded result contract;
- test coverage needed for both modes.

Do not recommend:

- arbitrary method names over REST;
- arbitrary DocType CRUD over REST;
- remote import paths supplied by the caller;
- user identity supplied by the model;
- broad generic proxy behavior.

The same business service should remain the authority behind both backends wherever the current architecture supports that pattern.

---

# 19. Required Audit Procedure / Steps

Follow this order.

## Step 1 — Establish current repository baseline

Record:

- current task numbering;
- current Sales profile inventory;
- current lifecycle policies;
- current Delivery Note references;
- current direct/REST backend architecture;
- current tests relevant to adding a new Sales transaction DocType.

## Step 2 — Trace the current `DELIVERY_NOTE_REQUIRED` path

Start from standalone Sales Invoice creation and trace exactly:

```text
MCP prepare_sales_invoice
 -> typed request
 -> service
 -> ERPNext native validation/defaulting
 -> native prerequisite failure
 -> bounded DELIVERY_NOTE_REQUIRED result
```

Identify the exact native check that causes the prerequisite failure.

This provides the current bridge point where a future agent/client may decide to create a Delivery Note.

## Step 3 — Trace native SO -> DN creation

Trace the installed ERPNext UI/server path from submitted Sales Order to Draft Delivery Note.

Document exact native APIs and source/target behavior.

## Step 4 — Trace Draft DN validation

Identify what happens during Draft construction/save and which values ERPNext calculates/defaults.

Separate:

- mapper-derived values;
- controller/default-derived values;
- user-required values;
- conditional values.

## Step 5 — Trace DN submit

Follow every important submit side effect and downstream update.

Do not stop at the Delivery Note controller method if it delegates to stock/accounting/controllers.

## Step 6 — Trace DN cancel/delete

Follow rollback and linked-document restrictions.

## Step 7 — Trace DN -> SI

Locate and inspect the native conversion path and remaining billable behavior.

## Step 8 — Inspect service/mixed/direct-stock variations

Verify service-only, stock-only, mixed, and direct-invoice alternatives.

## Step 9 — Inspect optional apps

Check installed apps and Delivery Note hooks, especially India Compliance when present.

## Step 10 — Map native behavior to existing MCP foundations

For each future capability, identify what can be reused and what is Delivery Note-specific.

## Step 11 — Design bounded public contracts conceptually

Do not write Python contracts. Define only the proposed minimal public input/output shapes in the report.

## Step 12 — Define Task 42

Produce one concrete implementation recommendation, with exact scope and explicitly deferred features.

---

# 20. Required Report Structure

Create:

```text
docs/inspect/DELIVERY_NOTE_NATIVE_FLOW_AUDIT.md
```

The report must contain at least these sections:

## 1. Executive conclusion

A short answer to:

- Is Delivery Note needed to complete the generic Sales profile?
- What should Task 42 implement?
- What should remain deferred?

## 2. Current MCP state

List current Delivery Note gaps and current related capabilities.

## 3. Native ERPNext flow diagram

Show the relevant variations, for example based on actual installed behavior:

```text
Sales Order
   -> Delivery Note
   -> Sales Invoice
```

versus service/direct flows.

Do not present a path as universally mandatory if ERPNext treats it as optional/configurable.

## 4. Native source evidence

List exact installed files/classes/functions/methods traced.

## 5. Sales Order -> Delivery Note mapping

Full mapping/eligibility findings.

## 6. Standalone Delivery Note behavior

Findings and V1 decision.

## 7. Selling Settings / Customer / service-skip behavior

Exact authority and conditions.

## 8. Mixed item behavior

Stock/service/fixed-asset/Product-Bundle/drop-ship findings.

## 9. Draft validation and defaults

What native ERPNext derives versus what a user must provide.

## 10. Submit effects

Stock, ledger, source status, reservation, serial/batch, hooks.

## 11. Cancel/delete behavior

Rollback and linked-document restrictions.

## 12. Delivery Note -> Sales Invoice mapping

Exact native path and recommendation.

## 13. Permission model

Direct and REST identity/permission behavior.

## 14. Optional-app integrations

India Compliance and any other relevant installed app.

## 15. MCP reuse matrix

Example format:

| Concern | Existing foundation | Reuse? | Delivery Note-specific work |
|---|---|---:|---|
| Approval | shared approval store | Yes/No | ... |
| Typed tool wrapper | current explicit sales wrappers | Yes/No | ... |
| Read | common read engine | Yes/No | ... |
| Aggregate | common aggregate engine | Yes/No | ... |
| Lifecycle | common lifecycle | Yes/No | ... |
| PDF | generic PDF | Yes/No | ... |
| Email | generic email | Yes/No | ... |
| REST | fixed remote registry | Yes/No | ... |

## 16. Candidate capability classification

Use the categories from Section 17.

## 17. Proposed minimal public contracts

For each recommended capability, list only needed model inputs and bounded outputs.

## 18. Data-minimization / leakage review

State what must not be returned to the LLM.

## 19. Test matrix for implementation

Detailed Task 42 tests.

## 20. Risks / limitations

Clearly separate:

- confirmed behavior;
- version-specific behavior;
- features intentionally deferred;
- anything not live-tested.

## 21. Exact Task 42 recommendation

One precise implementation task proposal.

---

# 21. Mandatory Implementation Test Matrix to Design for Task 42

Task 41 itself does not implement tests, but the audit report must design the future test matrix.

At minimum include cases for:

## Registration / profile isolation

1. Delivery Note tools appear only in Sales profile.
2. Purchase profile is unchanged.
3. Existing Sales tool inventory remains present.
4. Tool names are normalized and deterministic.

## SO -> DN preparation

5. valid submitted Sales Order -> ready Draft DN preview.
6. Draft Sales Order -> bounded rejection.
7. cancelled Sales Order -> bounded rejection.
8. fully delivered Sales Order -> no remaining deliverable items / bounded result.
9. partially delivered Sales Order -> only remaining deliverable quantity.
10. source permission denied -> bounded permission result.
11. target create permission denied -> bounded permission result.
12. native mapper receives no permission-bypass flag.

## Service / mixed behavior

13. service-only order behavior matches installed native setting.
14. stock-only order maps deliverable rows.
15. mixed order maps only rows native ERPNext considers deliverable.
16. Product Bundle behavior matches native mapper.
17. drop-ship behavior matches native mapper.

## Warehouse / stock fields

18. warehouse/default behavior is native.
19. missing required warehouse produces bounded native validation.
20. MCP does not invent a warehouse.

## Serial/batch

21. serial/batch requirements remain native.
22. no custom allocation algorithm is introduced.
23. bounded errors do not leak raw internal exception details.

## Approval

24. prepare does not insert a Delivery Note.
25. prepare produces existing approval interaction contract.
26. approval token is site/user/action bound.
27. confirm=false does not write.
28. approval is one-shot.
29. expired approval fails safely.
30. wrong action/user/site fails safely.
31. concurrent confirmation cannot create duplicate writes.
32. material source change after preview -> stale confirmation.
33. confirmation re-runs native mapping rather than persisting stale preview payload.

## Draft-only creation

34. successful conversion creates `docstatus=0` Delivery Note only.
35. creation does not submit automatically.
36. creation does not intentionally create stock ledger entries.
37. target source-row lineage is preserved.

## Lifecycle

38. submit requires existing lifecycle approval.
39. submit performs native Delivery Note submission.
40. submit side effects are not duplicated in MCP.
41. cancel uses native cancellation.
42. delete respects native linked-document restrictions.
43. MCP does not auto-delete downstream documents.

## Read/query/aggregate if included

44. exact get respects permission.
45. field-aware query uses runtime metadata/shared read engine.
46. arbitrary unsafe fields are rejected/bounded according to existing policy.
47. aggregate uses shared aggregate foundation.
48. count works for Delivery Note.
49. unsupported aggregate operations remain bounded.

## DN -> SI if included

50. valid submitted DN -> Draft SI preview.
51. partially billed DN -> only remaining billable quantities.
52. fully billed DN -> no mappable rows / bounded result.
53. DN source-row lineage is preserved.
54. Sales Order lineage is preserved where native mapping provides it.
55. approval/staleness protections match existing conversion pattern.
56. confirm inserts Draft SI only.

## PDF/email if included

57. Delivery Note default/selected ERPNext Print Format works through generic PDF foundation.
58. Delivery Note email reuses generic email foundation.
59. no HTML/CSS must be supplied by the model for ordinary ERPNext printing.

## Backend parity

60. direct backend path calls the same Delivery Note service authority.
61. REST backend uses a fixed typed operation name.
62. REST payload is bounded and typed.
63. REST does not allow arbitrary DocType/method dispatch.
64. remote user permissions remain authoritative.
65. remote approval token remains stored/claimed on remote Frappe side.
66. safe errors are equivalent between direct and REST modes.

## Regression

67. existing Quotation tests remain green.
68. existing Sales Order tests remain green.
69. existing Sales Invoice tests remain green.
70. current `DELIVERY_NOTE_REQUIRED` result remains bounded.
71. Customer/Item behavior remains unchanged.
72. Purchase behavior remains unchanged.
73. existing REST backend tests remain green.
74. existing approval-store tests remain green.

Expand this matrix when installed native behavior reveals additional mandatory cases.

---

# 22. Acceptance Criteria for Task 41

Task 41 is complete only when all of the following are true:

1. No production code was modified.
2. No test implementation was modified.
3. No ERPNext business data/settings were changed merely for the audit.
4. One report exists under `docs/inspect/`.
5. Current MCP Delivery Note gap is proven from current code.
6. Existing Sales lifecycle/registration/REST boundaries are documented.
7. Exact installed SO -> DN native callable is identified.
8. Exact installed DN -> SI native callable/path is identified.
9. Native source eligibility and remaining-quantity behavior are documented.
10. Partial-delivery behavior is documented.
11. Service-only behavior is documented.
12. Mixed stock/service behavior is documented.
13. Selling Settings and Customer exception authority are documented.
14. Standalone Delivery Note support is investigated and classified.
15. Warehouse/default behavior is documented.
16. Serial/batch behavior is documented.
17. Product Bundle/packed item behavior is documented.
18. Stock reservation interaction is inspected when applicable.
19. Submit side effects are traced beyond the top-level controller.
20. Cancel/delete restrictions are documented.
21. Any GL/accounting impact of Delivery Note in the exact installed version is verified rather than assumed.
22. Optional-app/India Compliance Delivery Note hooks are inspected when installed.
23. Permission behavior is documented.
24. Approval/staleness requirements are documented.
25. LLM input/output minimization is documented.
26. Direct/REST parity requirements are documented.
27. Purchase remains explicitly out of scope.
28. Accounts remains explicitly out of scope.
29. No custom global product/service/Delivery-Note workflow switch is proposed as ERP authority.
30. Candidate capabilities are classified.
31. A concrete Task 42 implementation recommendation is provided.
32. The report separates confirmed facts from inference/version-sensitive findings.

---

# 23. Expected Result

After Task 41, we should be able to answer this without guessing:

> "For any ERPNext client using the Sales profile, what exact Delivery Note capability should MCP expose, which native ERPNext rules decide when it is needed, what data/actions does the model need, what stock/business side effects occur, and how do we implement it safely without making the MCP server client-specific?"

Expected architecture direction, subject to source verification:

```text
                     SALES PROFILE

Customer / Item
      |
      v
Quotation
      |
      v
Sales Order
   |       \
   |        \ native valid direct billing path
   v         v
Delivery    Sales Invoice
Note            ^
   |            |
   +------------+
     native DN -> SI path
```

For service-only/current-company use cases, Delivery Note capabilities may simply remain unused.

For product/mixed clients, the same generic Sales profile should be able to follow native fulfilment flow without a custom client-specific MCP workflow definition.

The exact included tools and implementation boundaries must come from the audit evidence.

---

# 24. Limitations / Non-Goals

Task 41 must not attempt to solve all future selling/stock workflows.

Unless native inspection proves they are necessary for the first safe Delivery Note implementation, defer detailed implementation of:

- Sales Return / return Delivery Note;
- Pick List;
- Packing Slip;
- Delivery Trip;
- Shipment;
- advanced stock reservation UX;
- automatic serial/batch selection;
- barcode scanning;
- e-Waybill generation actions;
- transporter workflow;
- POS;
- manufacturing fulfilment;
- subcontracting fulfilment;
- custom workflow engine;
- client-specific workflow DSL;
- new Accounts profile;
- Payment Entry.

Inspect interactions where needed, but keep Task 42 focused.

---

# 25. Exact Next Task After This Audit

Do **not** begin Task 42 automatically.

After `docs/inspect/DELIVERY_NOTE_NATIVE_FLOW_AUDIT.md` is produced, return it for review.

The expected next task is:

```text
Task 42 — Delivery Note V1 Implementation Foundation
```

Task 42's exact public tools must be frozen from the Task 41 evidence.

The strongest expected core is:

```text
Sales Order -> Delivery Note native conversion
Delivery Note existing-document read/query/aggregate as justified
Delivery Note lifecycle support through the existing action-scoped lifecycle foundation
Delivery Note PDF/email through existing generic foundations when safe
Direct + REST backend parity
```

Task 41 must explicitly decide whether these should be part of the same Task 42 or a separate immediately-following task:

```text
standalone Delivery Note creation
Delivery Note -> Sales Invoice native conversion
```

Do not start Accounts/Payment Entry implementation until the Delivery Note Sales-domain gap and its intended V1 boundary are reviewed.

---

# 26. Completion Response Required From the Coding Agent

When Task 41 is complete, the coding agent should respond concisely with:

```text
Task 41 completed as inspection-only.

Created:
- docs/inspect/DELIVERY_NOTE_NATIVE_FLOW_AUDIT.md

Production code changed: No
Tests changed: No
ERPNext data/settings changed: No

Key conclusion:
- <one short paragraph>

Recommended Task 42:
- <exact implementation scope from audit>
```

Do not paste the entire audit into chat if the report file has already been created.
