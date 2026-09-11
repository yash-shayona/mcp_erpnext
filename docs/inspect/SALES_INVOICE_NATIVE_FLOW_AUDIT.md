# Sales Invoice Native Flow Audit

Date: 2026-09-11  
Scope: Task 26 inspection only  
Authority: installed source and read-only `yob.localhost` runtime inspection

This report separates confirmed installed behavior from recommendations for
Tasks 27-29. No Sales Invoice, ledger entry, approval policy, profile, or site
record was created or changed for this audit.

## 1. Executive conclusion

Sales Invoice is not currently implemented as a public `mcp_erpnext`
capability. The existing app creates Quotations and Sales Orders and exposes
shared facilities only for the currently allowlisted documents. No current
MCP tool accepts `Sales Invoice`.

Both requested creation paths are feasible, but they must remain separate:

1. `Submitted Sales Order -> ERPNext native mapper -> Draft Sales Invoice`.
2. `Customer + bounded items -> ERPNext native new-document/default logic ->
   Draft Sales Invoice`, only when Selling Settings and the Customer permit a
   direct invoice.

The first path is source-backed and must preserve native remaining billable
quantities and row lineage. The second path has no source document and must
use native defaults and policy checks. A hidden Sales Order must not be used to
fake the second path.

The current shared lifecycle policy is not safe to broaden by simply adding
`Sales Invoice` to a broad profile set. That set currently gates update,
submit, cancel, and delete, while the update service accepts almost every
runtime-writable field. Sales Invoice contains accounting, tax, stock,
payment, compliance, and integration fields. Action-scoped policy is required
before adding it to shared lifecycle. Field-scoped update policy is also
required; the recommended V1 is no generic Sales Invoice update and no child
row add.

Recommended sequence:

* Task 27: implement only native Sales Order conversion to a Draft Sales
  Invoice.
* Task 28: add permission-safe read/search/PDF/email and narrowly allow
  submit/cancel/delete; leave update and child-add disabled.
* Task 29: implement only bounded direct Draft Sales Invoice creation with
  `update_stock=0`, non-POS, non-return, non-debit-note inputs and no implicit
  submit or payment.

## 2. Exact versions and site/app state

### Source versions

The installed source reports:

| Component | Evidence |
|---|---|
| Frappe | `apps/frappe/frappe/__init__.py:__version__` = `16.33.1`; source branch `version-16` |
| ERPNext | `apps/erpnext/erpnext/__init__.py:__version__` = `16.34.2`; source branch `version-16` |
| India Compliance | `apps/india_compliance/india_compliance/__init__.py:__version__` = `16.9.0` |
| mcp_erpnext | `apps/mcp_erpnext` branch `master`, app version `0.0.1` |

Relevant source commits inspected were ERPNext `4048fb70e14d1843956fcdabb7c3cca75a1cbcdd`,
Frappe `988e54f3c4c291e2077a83809663f123731abe76`, and India Compliance
`071b544ac4440636e643fc383ed67a116a276691`. These are traceability values,
not version gates.

### Runtime evidence

Read-only `./env/bin/bench --site yob.localhost execute ...` reported these
installed apps:

```text
frappe, yob_core, yob_auth, erpnext, payments, india_compliance,
yob_storefront, mcp_erpnext, mcp_identity
```

The same read-only runtime version map reported Frappe 16.33.1, ERPNext
16.34.2, India Compliance 16.9.0, and mcp_erpnext 0.0.1.

Runtime `Sales Invoice` metadata includes ERPNext and India Compliance fields.
Relevant merged metadata includes required `company`, `customer`, `posting_date`,
`currency`, `selling_price_list`, `debit_to`, and `items`; read-only/fetched
fields include `company_gstin`, `billing_address_gstin`, `gst_category`,
`gst_breakup_table`, `irn`, and `ewaybill`. `Sales Invoice Item` includes
`gst_hsn_code`, `gst_treatment`, GST amounts/rates, `sales_order`, `so_detail`,
`delivery_note`, and `dn_detail`.

The runtime hook map contains India Compliance hooks for `before_validate`,
`validate`, `on_submit`, `before_cancel`, `after_mapping`, `before_print`, and
post-submit events, plus ERPNext regional hooks. Runtime settings observed for
traceability were `Selling Settings.so_required=No`,
`Selling Settings.dn_required=No`, `Accounts Settings.automatically_fetch_payment_terms=0`,
`Selling Settings.maintain_same_sales_rate=0`, GST e-Invoice/e-Waybill
auto-generation enabled, and cancellation restriction for final e-Invoices
disabled. These values are site state, not defaults to hard-code into MCP.

## 3. Current `mcp_erpnext` Sales architecture

The Sales profile registration in `mcp_erpnext/profiles/sales.py` currently
registers:

```text
register_sales_tools
  -> Customer, Item, selection
  -> Sales Order creation
  -> Quotation creation
  -> Quotation -> Sales Order conversion
register_lifecycle_tools("sales")
register_sales_order_read_tools
register_customer_read_tools
register_item_read_tools
register_sales_read_tools
register_document_pdf_tools("sales")
register_document_email_tools("sales")
```

The public wrapper inventory is assembled in `mcp_erpnext/tools/__init__.py`.
Typed registry metadata is in `mcp_erpnext/contracts/registry.py`.

Current call patterns are:

| Capability | Current path | Sales Invoice status |
|---|---|---|
| Quotation creation | `tools/selling/quotation.py -> services/selling/quotation.py` | no SI |
| Sales Order creation | `tools/selling/sales_order.py -> services/selling/sales_order.py` | no SI |
| Quotation conversion | `tools/selling/quotation_to_sales_order.py -> services/selling/quotation_to_sales_order.py -> ERPNext mapper` | no SI target |
| Existing read | `tools/read.py -> services/common/read.py` | no SI |
| Existing PDF | `tools/pdf.py -> services/common/pdf.py -> frappe.get_print` | no SI |
| Existing email | `tools/email.py -> services/common/email.py -> PDF + Frappe queue` | no SI |
| Existing update | `tools/lifecycle.py -> services/common/lifecycle.py -> doc.save` | SI rejected by allowlist |
| Existing submit/cancel/delete | lifecycle wrapper -> `doc.submit/cancel/delete` | SI rejected by allowlist |

The current generic services therefore provide no indirect usable Sales Invoice
support. ERPNext itself has the native mapper and document controller, but
neither is currently registered by this app.

Future implementation will likely affect, without implying that this audit
changes them: `profiles/sales.py`, `tools/__init__.py`, new selling
tool/service/contract modules, `contracts/registry.py`, shared read/PDF/email
contracts and services, action-scoped lifecycle policy, tests, and generated
tool documentation. No such implementation change is made here.

## 4. Current lifecycle/read/PDF/email policy findings

### Read policy

`services/common/read.py:14-33` defines `_DOCUMENTS` for only `Sales Order`,
`Quotation`, and `Purchase Order`. The Sales profile set at
`services/common/read.py:132-136` is `{Quotation, Sales Order}`. The service
uses `frappe.get_list(..., ignore_permissions=False)` at lines 111-122 and
checks document read permission for exact reads at lines 95-108.

The corresponding `DocumentDoctype` literal in `contracts/read.py:13` and
`DocumentSummary` shape are also closed over the same three documents.

### PDF and email coupling

`services/common/pdf.py:12,89-101` requires both `_DOCUMENTS` membership and
profile membership, then checks read and print permission before native
`frappe.get_print` at lines 107-117. `contracts/pdf.py:12` limits the public
literal to the same three doctypes.

`services/common/email.py` reuses the same target/read/print policy and adds
approval-bound sending. Its party resolver currently handles Quotation, Sales
Order, and Purchase Order; Sales Invoice would need an explicit Customer
mapping. Email confirmation queues work; it is not delivery confirmation.

Adding Sales Invoice to `_DOCUMENTS` and the Sales profile would consequently
make it available to shared read, PDF, and email wrappers after their typed
contracts and party mapping are updated. That coupling is acceptable for
read/PDF/email because each operation still uses native permissions, and email
send remains approval-gated. It must not be used as a reason to broaden
lifecycle writes.

### Lifecycle coupling and risk

`services/common/lifecycle.py:17-27` uses one `PROFILE_DOCTYPES` set for target
validation and a separate `CHILD_ADD_TARGETS` map. `prepare_update` loads a
write-permitted document and accepts any non-system, non-read-only scalar or
child field that runtime metadata exposes (`:102-129`). Confirm calls
`doc.save(ignore_permissions=False)` (`:329-340`).

`prepare_submit`, `prepare_cancel`, and `prepare_delete` use native document
state, permissions, and linked-document checks (`:243-282`). Confirm calls
native `submit`, `cancel`, or delete with normal permissions (`:300-371`).
Deletion of a submitted document can be a cancel-then-delete plan.

The generic child-add path is currently bounded to configured item tables, but
adding Sales Invoice to `PROFILE_DOCTYPES` would still make generic update and
submit/cancel/delete targetable. A separate action policy is therefore needed
before SI enters the shared target set.

## 5. Native Sales Order -> Sales Invoice source path

The exact installed callable is:

```text
erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice(
    source_name, target_doc=None, args=None, ignore_permissions=False
)
```

It is at `apps/erpnext/erpnext/selling/doctype/sales_order/sales_order.py:1355-1361`.
It calls Frappe `get_mapped_doc` at lines 1510-1550. The installed mapper is
`apps/frappe/frappe/model/mapper.py:get_mapped_doc`.

The native flow is:

```text
make_sales_invoice
  -> count submitted Sales Invoice Item quantities by so_detail
  -> account for returns and an in-progress target_doc
  -> get_mapped_doc("Sales Order", source_name, table_maps)
       -> new Draft Sales Invoice
       -> source read/create permission checks when ignore_permissions=False
       -> parent and child field mapping
       -> native Sales Invoice set_missing_values
       -> set_po_nos, calculate_taxes_and_totals, serial/batch defaults
       -> company-address resolution and debit_to resolution
       -> after_mapping hooks
  -> add subcontracting self-RM rows when applicable
  -> set payment schedule when Accounts Settings enables it
  -> return unsaved target document
```

The parent map requires `Sales Order.docstatus == 1`, maps
`party_account_currency`, and deliberately excludes `payment_terms_template`
(`:1514-1521`). `Sales Order Item` maps to `Sales Invoice Item`, preserving
source row `name -> so_detail` and `parent -> sales_order` (`:1522-1528`).
Sales Taxes and Charges are reset and Sales Team is copied if needed
(`:1541-1545`).

The mapper returns a Draft target. It does not insert, submit, post GL, or
update source status itself. The future confirmation must insert with
`ignore_permissions=False`, `ignore_links=False`, and
`ignore_mandatory=False`, then commit only after success.

## 6. Native conversion eligibility matrix

### Source and row rules

| Case | Installed native result/design decision |
|---|---|
| Draft Sales Order | Parent map validation fails because `docstatus` must equal 1. Return safe source-not-ready result. |
| Cancelled Sales Order | Same parent validation fails; do not convert. |
| Submitted Sales Order | Eligible for mapping if permissions and at least one row remain billable. |
| Closed/on-hold Sales Order | Mapper itself does not provide a separate status rejection. Target validation/submit checks linked Sales Order state; Task 27 must preserve the native result and test it explicitly. |
| Fully billed Sales Order | Each ordinary row has no pending quantity and is filtered; a target with no items is not a usable conversion. Return no-mappable-items. |
| Partially billed Sales Order | Native mapper returns only remaining billable quantity/amount. Never reconstruct the remainder in MCP. |
| Mixed rows | Native row conditions independently retain only rows with pending quantity and billable amount. |
| Returned quantity | `get_qty_net_of_returns` returns `min(ordered_qty, max(ordered_qty-returned_qty, delivered_qty))`; submitted invoice quantities are then subtracted. |
| Existing invoice quantities | Submitted `Sales Invoice Item` rows joined by `so_detail` are summed and subtracted. |
| In-progress target | `get_qty_already_mapped(target_doc, "so_detail")` is subtracted so repeated UI-style mapping does not duplicate rows. |
| Source permission denied | `get_mapped_doc` checks source read and target create permission unless bypassed. MCP must leave bypass false. |

The ordinary row condition at `sales_order.py:1529-1539` also requires a
non-zero quantity, an amount within the native allowance, and pending quantity
greater than zero. Unit-price rows use their special source behavior. The
mapper supports `args.filtered_children` and `skip_item_mapping`; Task 27
should expose neither as unrestricted public business controls without a
separate contract decision.

Delivery Notes are a distinct native path, not part of the SO mapper. The
installed Delivery Note mapper is
`erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice` at
`delivery_note.py:833-925`; it preserves `dn_detail`, `delivery_note`,
`so_detail`, and `sales_order`, and excludes already invoiced/returned
quantities. Task 27 is intentionally only Sales Order -> Sales Invoice.

## 7. Native mapped Sales Invoice field analysis

### Source-derived and lineage fields

The SO parent provides the customer/company transaction context, currency and
common same-named commercial fields. Each mapped row carries item identity,
quantity and rate/amount fields, plus `sales_order` and `so_detail`. The latter
two are the critical source-of-truth lineage and must be previewed and checked
at confirm.

### Defaulted and resolved fields

The mapper invokes Sales Invoice `set_missing_values` at
`sales_order.py:1421-1442`. This resolves the party account (`debit_to`), party
account currency, due date/payment terms, selling details, company contact and
addresses through native helpers. It also calls `set_po_nos`, tax/total
calculation, serial/batch field setup, and company-address fetches. If
`Accounts Settings.automatically_fetch_payment_terms` is enabled, the mapper
rebuilds payment schedule at `:1555-1559`.

### Calculated fields

ERPNext calculates stock quantities, net values, taxes, totals, base totals,
rounding, words, payment schedule, income accounts and other derived values.
MCP must show selected effective values but must not recalculate tax,
accounting, pricing, stock, or GST formulas itself.

### Taxes, pricing, addresses and payment schedule

The Sales Taxes and Charges child table is mapped/reset natively. Item tax
templates, customer/address data, price lists, conversion rates, payment terms,
tax category and addresses can affect the target. These values should either
be included in the effective preview/fingerprint or the target must be remapped
and compared at confirmation. The stable preview should not include volatile
framework timestamps or raw child object internals.

### Stock, service and subcontracting fields

The SO mapper carries warehouse/project-related item data and can append
subcontracting self-RM rows. It does not post stock. Stock movement is a later
submit-time effect when `update_stock=1`. Delivery Note references are not
created by the SO mapper; if present through other mapping paths, native
validation prevents updating stock again against a Delivery Note.

### Safe preview/fingerprint projection

The future Task 27 projection should include:

* source name, docstatus, modified value, customer, company, currency, status,
  billing/delivery state, project, transaction/delivery dates, and relevant
  source totals;
* every source item identity, `name`, item code, UOM/conversion factor,
  ordered/delivered/returned/billed quantities, rate/amount, warehouse and
  project where present;
* generated target row `sales_order`/`so_detail`, quantity, rate, amount,
  taxes, payment schedule, debit account, addresses, and totals;
* configuration values that alter the mapper result when they are part of the
  effective target, including automatic payment-term behavior.

Do not put credentials, full arbitrary document serialization, or unrelated
accounting internals in the public preview.

## 8. Conversion prepare-side-effect audit

### Safe native mapper boundary

Calling the installed mapper with its default `ignore_permissions=False` is
appropriate for prepare. `get_mapped_doc` creates an in-memory Draft and runs
permission checks; it does not call `insert`, `submit`, or `cancel`. The mapper
queries existing submitted invoice rows, source rows, item defaults, company
address, account, payment terms, and stock information. It calculates the
target in memory.

The mapper sets an internal target flag
`target.flags.ignore_permissions=True` while running target defaulting
(`sales_order.py:1421`), but the target is not persisted there. Confirmation
must not carry this as a permission bypass: final insert must use normal
permissions and native validation.

India Compliance `after_mapping` runs as part of Frappe mapping. For SO -> SI,
both documents are sales transactions, so cross-direction GST reset is not
needed and the e-Waybill field copy is restricted to Delivery Note/Purchase
Receipt sources. The hook is still a runtime extension point and should be
included in Task 27 tests.

### Do not blindly validate during prepare

The native mapper itself does not call `SalesInvoice.validate()`. A full
`run_method("validate")` is not universally a pure read operation in this
installed version:

* base Accounts validation may delete zero-allocated child advance rows in
  `clear_unallocated_advances` (`accounts_controller.py:1564-1572`);
* pick-list serial/batch validation can duplicate a serial/batch bundle in
  `set_serial_and_batch_bundle_from_pick_list`
  (`selling_controller.py:1055-1084`);
* validation mutates the unsaved target and can perform broad reference,
  address, pricing, tax, account, stock-availability, and timesheet reads.

There is no GL/stock ledger submission or India Compliance enqueue in ordinary
mapping. India Compliance validation performs in-memory GST normalization and
database reads; India Compliance enqueue is in its `on_submit` hook, not
ordinary mapping/validation. Nevertheless, Task 27 prepare should use the
mapper plus a deliberately bounded, side-effect-audited preview projection.
Confirmation must be the first operation allowed to run final insert-time
validation. If future implementation requires early validation for a particular
branch, it must first prove no database mutation, external API call, or bundle
creation for that branch.

## 9. Conversion stale-confirmation design

At prepare, hold a process-local approval containing the source name, site,
user, action, and a digest of the projected source/target state. Use the shared
`ApprovalStore` and `claim_for_confirm_write()`; do not add an approval-mode
argument or tool-specific approval policy.

At confirm:

1. atomically claim the approval before any write;
2. recheck source read and target create permission;
3. reload the source and ensure it is still submitted;
4. rerun the native mapper with the same bounded arguments;
5. recompute the projected fingerprint, including submitted billing sums and
   returns, and reject as stale if it differs;
6. insert the freshly mapped Draft with all bypass flags false;
7. commit only after successful insert; rollback on any failure.

The source `modified` timestamp is useful but insufficient as the only
business explanation. Explicitly include row lineage and billing-state data so
an invoice submitted after prepare cannot be hidden by a preview that still
shows the old quantity. A stale or failed confirmation consumes the one-shot
approval; the client must prepare again rather than retrying a failed token.

## 10. Sales Invoice validation flow

The installed class is `erpnext.accounts.doctype.sales_invoice.sales_invoice.SalesInvoice`.
It extends `SellingController`, whose validation extends
`AccountsController`.

The Sales Invoice controller validates at `sales_invoice.py:305-390`:

* posting time and inherited selling/accounts validation;
* Sales Order/Delivery Note requirement policy;
* tax withholding, project/customer, POS/return, previous-document lineage,
  UOM precision, Sales Order state, debit account, advances, fixed assets,
  cost centers, currency/account validation;
* inter-company party, coupon, POS/payment, dropship and stock warehouse rules;
* Delivery Note/stock interaction, deferred revenue, timesheet state,
  multiple billing/overbilling, packing/serial-batch state, project/timesheet
  billing and status.

The inherited `AccountsController.validate` at
`controllers/accounts_controller.py:261-340` sets missing values during
validation, validates fiscal date, party accounts, rates, taxes/totals,
returns, schedules, party/currency/account state, advances and related
accounting constraints. `SellingController.validate` adds item, price,
quantity, income-account, customer-address, duplicate-item and serial/batch
rules (`selling_controller.py:51-68`).

The key native direct-invoice policy method is
`SalesInvoice.so_dn_required()` (`sales_invoice.py:1167-1185`). It checks
`Selling Settings.so_required` and `.dn_required`; if either is `Yes`, a
Customer-level truthy exception (`Customer.so_required` or `Customer.dn_required`)
permits the item. The check is skipped for returns, and the whole check is
skipped for POS or debit-note invoices. V1 must not use those flags to bypass
policy.

The India Compliance validate hook is called by Frappe's `run_method`, in the
runtime hook order reported above. It calls `validate_transaction` and then
invoice-specific checks: invoice naming, return/debit conflict, e-Invoice
requirements/status, unique HSN/UOM, export port warning, GST-aware advances,
and E-Waybill status (`overrides/sales_invoice.py:65-77`).

## 11. Sales Invoice submit effects

Submission is a high-impact operation and must remain a separately approved
native lifecycle action. ERPNext `SalesInvoice.on_submit()` at
`sales_invoice.py:469-551` performs, in order:

* POS payment and Authorization Control approval checks;
* previous-document status checks and Sales Order/Delivery Note status updates;
* tax-withholding submission;
* optional serial/batch/stock reservation and stock ledger work when
  `update_stock=1`;
* asset sale/depreciation work;
* GL entries and outstanding updates;
* Delivery Note/Sales Order billing status updates;
* credit-limit and overdue-billing checks;
* journal allocation updates, timesheet billing, company monthly sales and
  project updates;
* inter-company linkage, coupon usage, loyalty point creation/redemption,
  common party accounting, and subcontracting billing quantities.

The class builds GL entries for customer receivable, taxes, income, discounts,
rounding, loyalty, POS and write-off values (`sales_invoice.py:1591-1658`).
This is why Draft creation and submission must never be one implicit MCP write.

India Compliance `on_submit` first checks backdated GST restrictions and repeats
transaction validation. If API/settings/applicability conditions match, it
enqueues e-Invoice generation or E-Waybill generation after commit
(`overrides/sales_invoice.py:155-195`). A Draft confirmation must not trigger
these jobs; a later approved submit may trigger them through native hooks.

## 12. Cancel/delete and linked-document behavior

### Cancel

`SalesInvoice.before_cancel()` checks POS/consolidated closing-entry blockers,
runs inherited accounting cancellation validation, and unlinks timesheet
references (`sales_invoice.py:599-605`). `on_cancel()` then reverses or updates:

* payment/reference constraints and common accounting state;
* Sales Order and Delivery Note billing/status quantities;
* GST withholding and, when enabled, stock ledger/reservations;
* asset depreciation, reverse GL entries, projects, loyalty, coupons and
  inter-company links;
* timesheet links, serial/batch and repost records, and auto-created batches.

It finally marks the invoice Cancelled (`sales_invoice.py:607-685`).
Inherited AccountsController cancellation also removes/reverses payment ledger,
exchange gain/loss, common party journals, and optionally unlinks payment
references (`accounts_controller.py:2049-2069`).

India Compliance `before_cancel` loads GST integration state, checks whether an
IRN is cancellable, may auto-cancel e-Invoice/E-Waybill, enforces backdated GST
rules, updates invoice status, and reverses GST adjustments against submitted
Payment Entry references (`overrides/sales_invoice.py:198-222`). If a final
e-Invoice cannot be cancelled and the GST restriction is enabled, it throws and
directs the user to a Credit Note (`:225-237`).

### Delete and linked documents

Frappe cancel/delete checks linked and dynamically linked documents before the
action. The generic lifecycle service preflights those blockers using
`get_linked_docs` and `get_dynamic_linked_docs`. ERPNext's account controller
also has `on_trash` cleanup for repost/unreconcile, serial/batch, payment and
ledger-related records (`accounts_controller.py:510-530` onward).

Sales Invoice deletion must therefore remain native and approval-bound. Draft
invoices linked to a Sales Order can block Sales Order cancellation; native
Sales Order code explicitly reports that linked Draft invoices must be deleted
first (`sales_order.py:602-616`). No MCP cascade deletion should be introduced.

## 13. Standalone Sales Invoice native creation path

No single public ERPNext `make_sales_invoice()` is the direct/no-source
constructor. The native direct path is a fresh document followed by the same
controller defaults/calculation/validation used by Desk:

```text
frappe.new_doc("Sales Invoice")
  -> set Customer, optional permitted Company and transaction inputs
  -> append Sales Invoice Item rows
  -> SalesInvoice.set_missing_values()
       -> party/address/contact and price-list/item defaults
       -> debit_to, party account currency and due date
  -> calculate_taxes_and_totals()
  -> final native insert(ignore_permissions=False, ignore_links=False,
     ignore_mandatory=False)
```

`SalesInvoice.set_missing_values()` is at `sales_invoice.py:788-805` and calls
the inherited selling/accounting helpers. `SellingController.set_missing_values`
calls customer details, price-list/item details and company contact defaults
(`selling_controller.py:102-108`). `AccountsController.calculate_taxes_and_totals`
delegates to ERPNext's native tax engine (`accounts_controller.py:809-812`).

The future service must construct only the approved fields, run native defaults
on the unsaved document, project the effective state into the approval payload,
and re-create/revalidate from that payload at confirm. It must not use a hidden
Sales Order, `ignore_permissions=True`, Administrator, or a direct database
insert.

## 14. Standalone minimum input contract

Recommended Task 29 V1 input:

| Input | V1 treatment |
|---|---|
| Customer | Required resolved Customer reference, read-permission checked. |
| Items | Required non-empty list of resolved sales-enabled Items; each has positive qty. |
| Rate | Optional only if the explicit contract supports a reviewed rate override; otherwise let native price-list/item logic resolve it. Never silently overwrite a native rate. |
| Company | Optional only when omitted native user Company default is permission-visible; explicit Company must be read-permitted. |
| Posting date | Optional bounded date; native fiscal/date validation remains authoritative. |
| Selling price list | Optional permitted Price List; native customer/company/item defaults otherwise. |
| Taxes/template/terms | Optional only as explicitly permitted links in a later contract; native tax and terms logic owns the result. |
| Customer address/contact | Optional permitted references; native customer/address defaults resolve omitted values. |

The preview must include effective customer, company, posting/due dates,
currency, price list, item UOM/qty/rate/amount, taxes, debit account,
addresses, payment schedule and totals. Missing effective mandatory values
should produce a structured input result before approval when safely knowable.

Do not expose arbitrary `extra_fields`. Do not accept direct inputs for
`docstatus`, `name`, owner/audit fields, calculated totals, GL accounts,
`irn`, `ewaybill`, GST-derived read-only fields, `e_invoice_status`,
`e_waybill_status`, or hidden bypass flags. Payment rows, advances, write-offs,
loyalty redemption, and accounting overrides are out of the minimum contract.

## 15. Selling Settings / Customer policy matrix

The exact native decision is per item and per transaction:

| `Selling Settings` | Customer exception | No SO / no DN direct invoice |
|---|---|---|
| `so_required=No`, `dn_required=No` | irrelevant | Allowed by this policy gate; native validation still applies. |
| `so_required=Yes` | `Customer.so_required` truthy | SO requirement is exempted for that customer. |
| `so_required=Yes` | exception false | Blocked with native Sales Order-required validation. |
| `dn_required=Yes` | `Customer.dn_required` truthy | DN requirement is exempted for that customer. |
| `dn_required=Yes` | exception false and `update_stock=0` | Blocked with native Delivery Note-required validation. |
| Any | POS/debit/return flags | Native method has special bypass/branches; standalone V1 must reject these flags rather than rely on bypass behavior. |
| Any | `update_stock=1` | Native stock and Delivery Note rules apply; standalone V1 freezes this off. |

The method checks a Customer exception before checking each item reference. The
future MCP service should perform a read-only preflight for user-friendly
guidance, but must still let native validation decide at insert. It must return
an actionable blocked/needs-prerequisite result rather than create a source
document or bypass the setting.

On the inspected `yob.localhost`, both global requirement fields were `No`.
That makes a normal direct invoice policy-eligible on this site, not proof that
every customer/item or future site is eligible.

## 16. Standalone feature-scope matrix

| Feature | Task 29 V1 decision | Reason |
|---|---|---|
| Normal customer invoice, `update_stock=0` | Yes, bounded | Native document/default/tax path with no stock mutation. |
| Stock item with `update_stock=0` | Candidate only after focused native tests; no stock movement | ERPNext permits the non-stock-updating accounting path, but warehouse/item/account behavior must be verified. |
| `update_stock=1` | No | Submit can create stock ledger/reservation/repost effects; separate capability needed. |
| POS | No | POS profile/opening/payment/full-payment/consolidation behavior is a separate workflow. |
| Return/credit note | No | Requires `return_against`, negative quantities/payment/GST reversal behavior; separate native return capability. |
| Debit note/rate adjustment | No | Distinct accounting/GST semantics and validation. |
| Timesheet billing | No | Validation and submit mutate Timesheet detail/status/linkage. |
| Project billing | No in V1 | Submit updates project billed amount and margin. |
| Advances | No in V1 | Payment/advance allocation and India GST adjustment require a separate reviewed contract. |
| Subscription/Auto Repeat | No | Recurring generation is server-scheduled, not direct conversational creation. |
| Consolidated invoice | No | POS closing-entry and source aggregation constraints. |
| Inter-company invoice | No | Cross-company party/reference/linkage rules. |
| Payment Entry | No | Separate Accounts capability; invoice creation must not create payment. |

## 17. India Compliance Sales Invoice integration

### Installed hooks

`apps/india_compliance/india_compliance/hooks.py:236-253` registers:

* `onload` for GST/e-Invoice/E-Waybill information;
* `before_print` for GST breakup/e-commerce details;
* `before_validate` for place of supply/reverse-charge/address preparation;
* `validate` for GST transaction, HSN, e-Invoice, advance and E-Waybill rules;
* `on_submit` for backdated checks and optional queued e-Invoice/E-Waybill jobs;
* `before_update_after_submit` and `on_update_after_submit` compliance checks;
* `before_cancel` for IRN/E-Waybill cancellation and payment/GST restrictions;
* `after_mapping` for GST detail reset/copy behavior.

### Relevant fields

Runtime metadata confirms relevant Sales Invoice fields such as `place_of_supply`,
`gst_category`, `billing_address_gstin`, `company_gstin`, `is_reverse_charge`,
`is_export_with_gst`, `ecommerce_gstin`, `port_address`, `irn`, `einvoice_status`,
`ewaybill`, `e_waybill_status`, transporter fields, and GST breakup fields.
Sales Invoice Item includes `gst_hsn_code`, `gst_treatment`, `taxable_value`,
GST rates/amounts, and native source references.

### Requirements and lifecycle effects

The installed transaction validator (`overrides/transaction.py:1652-1722`)
sets GST tax types/treatments, validates item GST details, place of supply,
company GSTIN, GST category, HSN, reverse charge, GSTIN status, transporter
and e-commerce GSTIN, applicable GST accounts, taxable values and item tax
templates. HSN validation uses current GST Settings and the installed valid
length set `(4, 6, 8)`; it is not an MCP regex to copy.

Sales Invoice-specific validation (`overrides/sales_invoice.py:65-77`) also:

* validates invoice number format;
* rejects simultaneous return and debit-note flags;
* requires customer address and valid HSN when applicable for e-Invoice;
* validates unique HSN/UOM grouping, export port warnings, and GST-aware
  advance allocations;
* sets E-Waybill status.

`before_validate_transaction` fills place of supply and reverse-charge defaults
and tracks missing party address (`overrides/transaction.py:1611-1627`).
`validate_transaction` may update GST fields/taxes in memory when the native
address default is filled (`:1629-1649`).

Prepare should not call external GST APIs or enqueue compliance jobs. On submit,
India Compliance may enqueue external generation after commit when API/settings
and applicability conditions match. On cancel, auto-cancellation can cross an
external boundary; that is another reason to retain a separate approved cancel
action and report queued/remote status honestly.

## 18. ERPNext-only behavior

The core Sales Invoice implementation must remain portable to an ERPNext-only
site. India Compliance imports must be lazy and capability-detected; the core
service must use runtime metadata rather than assuming GST fields exist.

On a site without India Compliance:

* native ERPNext Sales Invoice controller/defaults/taxes/permissions remain the
  authority;
* no India Compliance fields or hooks are requested;
* no GST/e-Invoice/E-Waybill preflight is reported as applicable;
* no optional module import is performed at module import time.

The current `mcp_erpnext` app has no Sales Invoice-specific optional adapter.
Task 29 may need a small lazy compliance preflight only if implementation
evidence shows a requirement can be safely known before approval. It must not
copy India Compliance algorithms or API clients.

## 19. Shared existing-document capability design

### Read/search

Task 28 should add a Sales Invoice definition to the shared read service and
typed `DocumentDoctype`, with a Customer party field, posting date, due date,
status/docstatus, currency, grand total, and a bounded item projection. Search
must continue through `frappe.get_list(..., ignore_permissions=False)` and
never expose unpermitted rows.

### PDF

Add SI to the explicit PDF doctype contract and profile/read definitions. Keep
the existing native `frappe.get_print(..., as_pdf=True)` path and read+print
permission checks. India Compliance `before_print` may add GST breakup data;
the PDF service must not bypass it.

### Email

Add SI to the email doctype contract and `_party_reference` as
`Customer -> invoice.customer`. Preserve document/contact recipient resolution,
read/email/print permissions, native PDF rendering, approval-bound queueing,
and the distinction between queued and delivered.

### Lifecycle

Explicitly allow only native submit/cancel/delete after action policy is
introduced. Submit and cancel remain approval-bound and invoke `doc.submit()` /
`doc.cancel()` with normal permissions. Delete keeps linked-document preflight
and cancel-then-delete semantics. Generic update and child-add remain disabled.

### Safe draft updates

No safe generic draft field set has been proven by this audit. A future narrow
draft-edit capability would need an explicit allowlist that excludes customer,
company, posting date, debit account, currency, taxes/account heads, payment
rows/advances, stock flags, GST/e-Invoice fields, and source lineage unless a
separate source-aware workflow proves each field. Submitted updates should not
be supported through generic update: `doc.save()` can run post-submit hooks and
repost accounting when account/tax fields change (`sales_invoice.py:887-904`).

## 20. Lifecycle action-policy decision

Yes. Action-scoped policy is required before Sales Invoice is added.

Minimum policy shape:

```text
Sales profile
  Sales Invoice: READ, PRINT, EMAIL, SUBMIT, CANCEL, DELETE
  Sales Invoice: UPDATE = DENY
  Sales Invoice: CHILD_ADD = DENY
```

The exact implementation may use a shared action/doctype policy registry, but
must not make `PROFILE_DOCTYPES` alone the authorization decision. Separate
read/PDF/email eligibility from write actions. If draft update is later
approved, use a per-doctype and per-field allowlist with native validation and
stale fingerprints. Never expose accounting mutations merely because a field
is not marked read-only in metadata.

## 21. Recommended public MCP contracts

### Task 27: native source conversion only

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

The prepare tool accepts one exact submitted Sales Order reference and returns
the native remaining-billable Draft preview plus an opaque approval token. The
confirm tool re-maps and rechecks the source, then inserts a Draft only. It does
not submit, create Payment Entry, update stock, call GST APIs, or accept
arbitrary target overrides.

### Task 28: existing Sales Invoice capabilities

Use the existing shared names after policy/contract changes:

```text
get_sales_invoice
search_sales_invoices
render_document_pdf       # doctype=Sales Invoice
prepare_document_email    # doctype=Sales Invoice
confirm_document_email
prepare_document_submit
confirm_document_submit
prepare_document_cancel
confirm_document_cancel
prepare_document_delete
confirm_document_delete
```

Do not expose generic SI update or child-add in Task 28. All conversational
continuations use the shared `InteractionDirective`; no ad-hoc approval or UI
fields are introduced.

### Task 29: standalone creation only

```text
prepare_sales_invoice
confirm_sales_invoice
```

This pair accepts the bounded minimum contract from section 14, performs
read-only native-default preparation, enforces direct-invoice policy without
bypass, and inserts a Draft only. It must not overload the SO conversion pair.

## 22. Security and permission model

The authenticated Frappe identity is the only business identity. Every path
must preserve:

* source/document read permission;
* target DocType create/write/submit/cancel/delete/print/email permission as
  applicable;
* normal Link validation using `ignore_permissions=False`;
* site/user/action/payload-bound approval tokens;
* native Frappe/ERPNext/India Compliance validation and hooks.

Forbidden implementation shortcuts are `ignore_permissions=True`, Administrator
fallback, direct SQL inserts/updates, hidden source-document creation,
arbitrary field passthrough, direct ledger writes, copied GST algorithms,
client-provided approval policy, and implicit submit/payment.

Public errors should use existing safe error envelopes and MCP references. Do
not expose stack traces, SQL, credentials, IRN API details, or accounting data
the authenticated user cannot read. Compliance/API work must remain native and
its queued/remote result must not be represented as synchronous success.

## 23. Test plan for implementation tasks

### Task 27 unit/static/live matrix

| Boundary | Required verification |
|---|---|
| Source state | Submitted source succeeds; Draft/cancelled fail; closed/on-hold behavior matches native validation. |
| Billing | Fully billed returns no rows; partial/mixed rows preserve native remaining qty/amount; returns and submitted invoices are counted. |
| Lineage | `sales_order` and `so_detail` are present and stable. |
| Permission | Source read and SI create denial are safe; no bypass flag reaches insert. |
| Prepare safety | No SI insert, GL, stock ledger, queue, external compliance I/O, or business-record mutation. Include pick-list/serial-batch and zero-advance branches explicitly. |
| Approval | Site/user/action/payload binding, unapproved confirmation denial, one-shot replay protection, expired token and stale source/billing state. |
| Native fidelity | Same mapper on prepare/confirm; totals/taxes/payment schedule/default account behavior preserved; Draft status only. |
| Optional app | ERPNext-only site imports without India Compliance; installed site preserves after-mapping and native GST behavior. |

Live verification should use existing prepared/test data or a separately
authorized disposable fixture. Task 26 itself created no transaction.

### Task 28 unit/static/live matrix

* SI get/read and search are Sales-profile permission-scoped and unavailable in
  Purchase profile.
* PDF requires read and print permission and exercises India Compliance
  `before_print` when installed.
* Email resolves Customer/Contact recipients, requires email/print/read
  permission, remains approval-gated, and reports queued rather than delivered.
* Draft submit requires approval and native `doc.submit()`; submitted cancel
  requires approval and respects linked/compliance rules.
* Delete honors linked docs and cancel-then-delete; no cascade mutation occurs.
* Generic update and child-add are denied for SI; submitted account/tax edits
  cannot slip through the shared path.
* Adding SI does not broaden Customer, Item, Quotation, or Sales Order actions;
  Sales/Purchase profile separation remains intact.

### Task 29 unit/static/live matrix

* Normal direct invoice works when both global requirement settings are off.
* SO/DN-required without Customer exception produces a safe blocked/prerequisite
  result; a truthy exception follows native validation.
* Customer/item resolution, missing input and ambiguity use existing resolver
  semantics.
* Company, currency, price list, account, address, taxes and totals use native
  defaults/helpers; effective values are fully approval-bound.
* Prepare performs no insert, submit, payment, stock, ledger, queue or external
  compliance operation; confirm inserts Draft only.
* `update_stock`, POS, return, debit-note and hidden bypass inputs are rejected
  or fixed to the V1-safe state.
* Timesheet, project, advances, subscription, consolidated and inter-company
  variants are rejected or remain outside the contract.
* ERPNext-only and India Compliance-installed sites both behave portably;
  final insert still runs native validation.
* Permission denial, stale payload and approval replay are safe.

## 24. Known limitations and open questions

The following are the only material unresolved items from this inspection:

1. Closed/on-hold SO behavior should be covered by Task 27 live/native tests
   because the mapper's parent validation checks docstatus, while linked-state
   rejection occurs in later invoice validation.
2. Task 27 must decide, with targeted tests, whether any nonstandard SO branch
   involving pick-list serial/batch data can be previewed without triggering
   bundle creation. The safe default is not to run full validation during
   prepare for that branch.
3. Direct stock-item invoices with `update_stock=0` are technically distinct
   from stock-updating invoices but need focused native tests before being
   admitted to Task 29. The contract must remain explicit about no stock
   mutation.
4. Live PDF generation, email delivery, external e-Invoice/E-Waybill API
   responses, and browser/client rendering were not verified by this audit.
5. Runtime settings are site-specific and may change; implementation must
   re-read them rather than use the values recorded in section 2.

## 25. Final architecture decision

Freeze Sales Invoice into three deliberately separated capability families:

```text
Sales profile
  -> source-backed SO conversion
       Submitted SO -> native mapper -> approved Draft SI
  -> existing SI operations
       read/search/PDF/email + narrow submit/cancel/delete policy
  -> standalone SI creation
       Customer/items -> native defaults/policy -> approved Draft SI
```

ERPNext owns quantities, pricing, tax, GST, accounting, stock, document
status, linked-document state and side effects. MCP owns bounded input
contracts, permission-aware routing, preview projection, approval binding,
stale detection and safe error reporting. This preserves the two different
source-of-truth models and keeps accounting mutations explicit.

## 26. Exact next task

The next task is Task 27 only:

```text
Task 27 - Sales Order -> Sales Invoice Native Conversion Foundation
```

Task 27 should implement only:

```text
prepare_sales_order_to_sales_invoice
confirm_sales_order_to_sales_invoice
```

It should call the installed native
`erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice` with
normal permissions, produce a Draft preview, bind effective state to shared
approval, re-map/recheck at confirm, and insert without submitting. Do not
combine Task 28 or Task 29, and do not add generic Sales Invoice lifecycle or
standalone creation in that task.

## Final decision matrix

| Capability | Public tool strategy | V1 | Native authority | Approval | Notes |
|---|---|---:|---|---|---|
| SO -> SI conversion | explicit pair | Yes, Task 27 | ERPNext native SO mapper | Yes | Draft target only; remaining state native |
| Standalone SI creation | explicit pair | Yes, Task 29 | ERPNext new_doc/defaults/validation | Yes | No SO/DN bypass; bounded flags |
| SI read/search | shared generic with explicit SI read policy | Yes, Task 28 | permission-aware Frappe reads | No write approval | Customer party and bounded item projection |
| SI PDF | shared generic | Yes, Task 28 | native print/PDF | No write approval | Read + print permission; compliance before_print |
| SI email | shared generic | Yes, Task 28 | Frappe queue + native PDF | Yes | Queued is not delivered |
| SI submit | shared lifecycle, action-scoped | Yes, Task 28 | `doc.submit()` | Yes | GL/stock/GST/linked effects |
| SI cancel | shared lifecycle, action-scoped | Yes, Task 28 | `doc.cancel()` | Yes | Reversal and possible external compliance effects |
| SI delete | shared lifecycle, action-scoped | Bounded | `doc.delete()` | Yes | Linked docs and cancel-then-delete |
| Generic SI update | explicit field policy required | No | `doc.save()` | Yes if later enabled | Do not expose now; accounting repost risk |
| SI child add | explicit policy required | No | native document model | Yes if later enabled | Do not expose now |
| POS | separate capability | No | ERPNext POS | Yes | Not standalone V1 |
| Update Stock direct sale | separate/bounded | No | ERPNext stock/accounting | Yes | Stock ledger/reservation/repost |
| Return/credit note | separate explicit capability | No | ERPNext return mapper | Yes | Do not overload creation |
| Debit note | separate explicit capability | No | ERPNext accounting/GST | Yes | Distinct semantics |
| Timesheet/project billing | separate or later | No | ERPNext Timesheet/Project | Yes | Submit mutates linked records |
| Advances/payment | separate Accounts capability | No | ERPNext accounting | Yes | No implicit Payment Entry |
