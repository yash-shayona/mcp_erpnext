# Delivery Note Native Flow Audit

## 1. Executive conclusion

**Delivery Note is a missing Sales-domain capability, but it is not a universal
step.**  ERPNext v16.34.2 decides whether it is needed from the transaction,
Selling Settings, Customer exception flags, source-row state, and the chosen
native flow.  MCP must expose the normal fulfillment path without adding a
`BUSINESS_TYPE` or workflow switch.

The first Delivery Note implementation should be **Task 42: Sales Order to
Draft Delivery Note foundation**, plus permission-safe existing-document
read/query/aggregate, the existing generic lifecycle actions, and the generic
PDF/email capability.  Its only creation path should be the installed native
Sales Order mapper.  It must create a Draft only; submit, cancel, and delete
remain separately approved generic lifecycle actions.

Standalone Delivery Note creation and Delivery Note to Sales Invoice conversion
are both legitimate ERPNext capabilities.  They should not be silently
substituted for the SO mapper.  Standalone creation is deferred from V1; DN to
SI should be the immediately following small conversion task, so the standard
goods flow is complete without coupling a stock-risky fulfillment foundation to
a second mapping contract.

This is an inspection-only report.  No source, test, site data, or setting was
changed.

## 2. Current MCP state

### Confirmed repository baseline

The inspected app worktree is on `master` and already has unrelated modified
and untracked work.  It was preserved.  The requested report did not exist
before this audit.  The installed ERPNext checkout is branch `version-16`,
commit `4048fb70e14d1843956fcdabb7c3cca75a1cbcdd` (`v16.34.2` release bump).

`mcp_erpnext/profiles/sales.py` registers the existing Sales tools, generic
lifecycle, typed reads for Customer/Item/Quotation/Sales Order/Sales Invoice,
and generic PDF/email.  `tools/__init__.py` registers Quotation, Sales Order,
Quotation-to-Sales-Order, Sales-Order-to-Sales-Invoice, and standalone Sales
Invoice tools.  There is no `tools/selling/delivery_note.py`, Delivery Note
service, typed contract, read module, registry entry, or Sales profile
registration.

The absence is deliberate in the current code, not merely an omitted UI
listing:

| Boundary | Current state | Delivery Note implication |
|---|---|---|
| Sales profile | no Delivery Note registration | add only to Sales in Task 42 |
| Purchase profile | only supplier/item/Purchase Order and shared utilities | unchanged |
| lifecycle `PROFILE_DOCTYPES` / `LIFECYCLE_ACTION_DOCTYPES` | Sales Invoice is submit/cancel/delete-only; Delivery Note absent | add DN only to submit/cancel/delete, never generic update/child-add |
| legacy common read `_DOCUMENTS` | no Delivery Note | do not extend the legacy fixed-summary path; use the current field-aware Sales pattern |
| generic PDF/email allowlists | derive from `_DOCUMENTS` / profile doctype policy | add DN through the shared policy only |
| REST `_SALES_HANDLERS` | fixed typed operations, no Delivery Note operation | add one fixed handler per public DN tool; no generic dispatch |
| contracts registry/catalog | no typed DN contracts | add explicit typed entries with Task 42 |

The standalone Sales Invoice path is the present bridge point.  In
`services/selling/sales_invoice.py`, `_build()` creates an unsaved native
invoice, calls `set_missing_values()` and `calculate_taxes_and_totals()`, then
calls the narrow native `doc.so_dn_required()` seam.  A native validation whose
text identifies Delivery Note is converted to the bounded
`DELIVERY_NOTE_REQUIRED` prerequisite result.  It does not invent the policy.
The underlying authority is `SalesInvoice.so_dn_required()` in
`erpnext/accounts/doctype/sales_invoice/sales_invoice.py`.

### Existing MCP foundations that are sound to reuse

The explicit Sales conversions (`quotation_to_sales_order.py` and
`sales_order_to_sales_invoice.py`) already establish the correct model:

1. load an exact source with read permission and enforce target create
   permission;
2. call ERPNext's native mapper with normal permissions;
3. return a bounded Draft preview and an `InteractionDirective` approval;
4. store a deterministic fingerprint in the shared site/user/action-bound
   `ApprovalStore`;
5. atomically claim the one-shot approval, reload/remap, compare the fresh
   preview fingerprint, and insert with all `ignore_*` flags false.

Delivery Note can reuse that shape, but cannot reuse an unqualified Sales
Invoice preview: stock-impact fields, warehouse, and serial/batch summary must
be visible before a submit approval.  Conversion confirmation must still insert
only a Draft and must not call `submit()`.

The field-aware Sales read services use exact `frappe.get_doc` plus
`doc.has_permission("read")`, and permission-aware `frappe.get_list(...,
ignore_permissions=False)` for query/aggregate.  The shared aggregate helper
uses Frappe v16 dictionary expressions.  Delivery Note should get a parallel
DocType-local field policy on these shared foundations, not a second query
engine.

## 3. Native ERPNext flow diagram

```text
                                 ERPNext configuration and document state
                                                |
Customer / Item -> Quotation -> Submitted Sales Order
                                  |              |
                                  |              +-- skip_delivery_note, direct billing,
                                  |              |   or native-valid alternate flow
                                  |              v
                                  |        make_sales_invoice (SO -> Draft SI)
                                  |              |
                                  |              +-- may be rejected by native DN requirement
                                  |
                                  +--> make_delivery_note (SO -> Draft DN)
                                                |
                                  separately approved native submit
                                                |
                     stock/SLE, possible perpetual-stock GL, SO delivered state,
                     reservation/serial-batch/packed-item/linked-document effects
                                                |
                                                v
                               make_sales_invoice (DN -> Draft SI)

Standalone Sales Invoice with update_stock=1 is a distinct direct-stock route.
It is not evidence that every stock sale needs a Delivery Note, nor a reason to
make MCP choose the route with a global product/service setting.
```

## 4. Native source evidence

Primary evidence is the installed source, not generic ERP assumptions:

| Concern | Installed v16.34.2 evidence |
|---|---|
| SO -> DN mapper | `erpnext/selling/doctype/sales_order/sales_order.py`, `make_delivery_note()` |
| DN controller | `erpnext/stock/doctype/delivery_note/delivery_note.py`, `DeliveryNote.validate`, `on_submit`, `on_cancel`, `check_next_docstatus` |
| DN -> SI mapper | `erpnext/stock/doctype/delivery_note/delivery_note.py`, `make_sales_invoice()` |
| source delivered quantities / over-delivery | `erpnext/controllers/status_updater.py`, `StatusUpdater.update_prevdoc_status`, `update_qty`, `check_overflow_with_allowance` |
| stock / GL / SRE | `erpnext/controllers/selling_controller.py`, `update_stock_ledger`, `update_stock_reservation_entries`; `erpnext/controllers/stock_controller.py`, `make_gl_entries`, `update_billing_percentage` |
| direct SI prerequisite | `erpnext/accounts/doctype/sales_invoice/sales_invoice.py`, `SalesInvoice.so_dn_required` |
| settings / Customer exceptions | `selling/doctype/selling_settings/selling_settings.json`; `selling/doctype/customer/customer.json` |
| mapping permission semantics | `frappe/model/mapper.py`, `get_mapped_doc(..., ignore_permissions=False)` |
| installed optional app | `india_compliance/hooks.py`, `gst_india/overrides/delivery_note.py`, `gst_india/overrides/transaction.py` |

`get_mapped_doc` defaults `ignore_permissions=False`; with strict user
permissions disabled it checks target Create permission and it checks source
Read permission.  The SO mapper has a special reserved-stock submapper that
uses `ignore_permissions=True` internally after the parent mapper has loaded
the permitted SO.  MCP must not expose or pass a caller-controlled bypass flag;
it should call the public mapper's ordinary non-reserved path with normal
permissions.

## 5. Sales Order -> Delivery Note mapping and eligibility

### Exact callable and mapping

The UI-equivalent callable is:

```python
erpnext.selling.doctype.sales_order.sales_order.make_delivery_note(
    source_name, target_doc=None, kwargs=None
)
```

It maps a **Submitted** Sales Order to an unsaved Delivery Note through
`get_mapped_doc` with parent validation `docstatus == 1`.  It maps Sales Taxes
and Charges (reset) and Sales Team (add if empty).  `Sales Order Item` maps to
`Delivery Note Item` with `name -> so_detail`, `parent -> against_sales_order`,
and rate retained.  The postprocessor sets remaining quantity, amount and base
amount and resolves the cost center from project/item/item-group defaults.

The mapper's effective remaining quantity is:

```text
SO qty - SO delivered_qty - quantity already mapped into this target by so_detail
```

It admits a normal row only while the absolute delivered/mapped quantity is
below ordered absolute quantity, and rejects `delivered_by_supplier == 1`.
It also honors UI-only mapping options internally (`filtered_children`, delivery
dates, cutoff date, `ignore_pricing_rule`, `for_reserved_stock`, and
`skip_item_mapping`).  These are native mapper mechanics, not a suitable public
MCP contract.  Task 42 should call it with `target_doc=None` and an empty fixed
argument object, expose no raw flags, and reject an empty mapped item table as
`NO_MAPPABLE_ITEMS`.

After mapping it runs native `set_missing_values`, `set_po_nos`,
`calculate_taxes_and_totals`, `set_use_serial_batch_fields`, company-address
resolution/fetching, and `make_packing_list`.  The target remains a Draft.

### Eligibility findings

| Source condition | Installed mapper/controller behavior | MCP result |
|---|---|---|
| Draft SO | parent mapper validation requires `docstatus=1` | bounded `SOURCE_NOT_READY` before mapping |
| Submitted SO | eligible subject to row conditions and permissions | prepare Draft preview |
| Cancelled SO | fails mapper docstatus validation | bounded native conversion failure / source not ready |
| Closed or On Hold SO | mapper itself only asserts docstatus; DN validation calls `check_sales_order_on_hold_or_close` | run native Draft validation in prepare; final insert remains authority |
| fully delivered rows/SO | rows are filtered; target can be empty | `NO_MAPPABLE_ITEMS` |
| partial delivery | maps only remaining quantity | preview native remaining rows/qty |
| returned quantity | mapper bases selection on `delivered_qty`; ERPNext status-updater/return state remains authority | do not derive a separate MCP formula; fresh remap detects changed state |
| already billed but undelivered | billing does not alone make a submitted SO ineligible for DN; controller validation and native status govern | do not add an MCP billing gate |
| supplier-delivered/drop-ship row | `delivered_by_supplier != 1` condition filters it | do not manufacture a DN row |
| selected child rows | native supports `filtered_children` | defer partial row-selection UX; do not expose raw mapper options in Task 42 |
| product bundle | parent item can map; `make_packing_list(target)` generates packed rows | preserve native bundle behavior and show a bounded packed-stock summary |

The code does not add an independent row-level `is_stock_item` condition in
`make_delivery_note`.  Its UI's Create button tests remaining quantity and
`delivered_by_supplier`, not `is_stock_item`.  Therefore Task 42 must report
the actual native target that was mapped, rather than categorizing a service row
itself as non-deliverable.

## 6. Standalone Delivery Note behavior

ERPNext supports standalone Delivery Notes: the controller's `so_required()`
only rejects unlinked rows when Selling Settings `so_required == "Yes"`.
With that setting off, a user with Create permission can create a DN directly;
normal controller defaults/validation determine Customer, Company, posting
date/time, item details, price/tax details, and stock fields.  The Delivery
Note metadata declares Customer, Company, posting date/time, items, and naming
series as required; the controller adds conditional requirements such as a
warehouse for stock rows.

That legitimate flow is too broad for the first safe MCP delivery increment:
it needs a bounded Item/warehouse/serial/batch/defaulting contract and an
audit of all standalone native validations.  It is **deferred from Task 42**.
The SO mapper covers the high-value missing bridge from the current Sales
profile without forcing a client-specific workflow.  Deferral is not a claim
that standalone delivery is invalid; it is a deliberate V1 scope limit.

## 7. Selling Settings, Customer exceptions, and service skip behavior

The native authority is specific and must be evaluated at operation time:

| Rule | Native source behavior |
|---|---|
| SO required for DN | `DeliveryNote.so_required()` checks Selling Settings `so_required == "Yes"` and requires `against_sales_order` per item. |
| SO/DN required for direct SI | `SalesInvoice.so_dn_required()` checks Selling Settings `so_required`/`dn_required`. For a Customer whose check field is true it skips the corresponding prerequisite; Customer labels state “Allow sales invoice creation without …”.  For DN, an SI row is allowed without `delivery_note` if `update_stock` is true. |
| rate consistency | DN `validate_with_previous_doc()` applies `validate_rate_with_reference_doc` when `maintain_same_sales_rate` is enabled, except return/internal customer cases. |
| SO header skipping | `Sales Order.skip_delivery_note` controls status outcomes and date validation/UI availability. Status is To Bill/Completed when delivery is complete **or** this flag is set. |
| over-delivery | shared `StatusUpdater.check_overflow_with_allowance` uses Item and Stock Settings allowance plus a role permitted to override. |

There is no confirmed installed server-side rule that automatically flips
`skip_delivery_note` solely because all items are services.  The Sales Order
Desk client controls the delivery action from remaining non-supplier rows and
the header `skip_delivery_note`.  A service-only SO can be billed through the
native SO-to-SI path; if it is not marked skip, the native mapper can still
produce rows.  MCP must not invent an automatic service heuristic or alter the
header to make that happen.

## 8. Mixed item, warehouse, serial/batch, packed-item, and reservation behavior

### Source kinds

* **Stock-only:** stock rows need a warehouse at DN validation; submission
  creates stock effects.
* **Service/non-stock:** no stock ledger entry is generated by
  `SellingController.update_stock_ledger`, which gates on `Item.is_stock_item`
  and nonzero qty.  It is not a separate mapper category.
* **Mixed:** the mapper applies the native row conditions, can return both
  types, and DN submit emits stock effects only for stock/packed stock rows.
  The preview must show each mapped row's warehouse and whether it is a stock
  item; MCP should not filter a native result.
* **Fixed assets:** the native stock controller's GL decision includes an
  `is_fixed_asset` check.  Treat it as a material submit effect; do not add an
  asset-specific MCP flow in Task 42.
* **Drop ship:** `delivered_by_supplier` rows are excluded by the SO mapper.
* **Product Bundle:** the mapper calls `make_packing_list`; the visible parent
  and packed component rows are native state.  DN validates packing slips and
  creates bundles for sales/purchase return on submit.  A preview should show a
  concise parent/component qty/warehouse summary, not raw packed documents.

### Warehouse and stock validation

`DeliveryNote.validate_warehouse()` calls the inherited warehouse validation
and then requires `warehouse` for every stock item in `get_item_list()`.
`set_warehouse` can populate item defaults, while the SO mapper preserves and
then recalculates native default information.  Reservations can set an absent
DN row warehouse from the reserved warehouse or reject a mismatched one.
Warehouse/company, disabled warehouse, actual stock, quality inspection and
negative-stock validations remain native controller concerns.

### Serial/batch and Stock Reservation

The mapper calls `set_use_serial_batch_fields`; it does not implement an MCP
allocation algorithm.  In reserved-stock UI use, ERPNext accepts
`for_reserved_stock`, takes SRE details, creates separate DN rows with SRE
quantity/warehouse and, when legacy serial/batch fields are in use, copies a
Serial and Batch Bundle reference.  That is a special UI path and is deferred
from Task 42; no public raw `for_reserved_stock` input should be offered.

On submit, the native controller creates/uses Serial and Batch Bundles,
validates standalone serial-number customers, and updates SRE delivered qty and
reserved stock.  On cancel it rolls SRE delivered quantities back.  Task 42
can prepare a DN containing native serial/batch state, but must not expose
automatic allocation or an unbounded serial inventory to an LLM.  A bounded
preview may say that serial/batch selection is required and summarize assigned
identifiers/counts only when the caller is already permitted to read them.

## 9. Draft validation and defaults

The static installed DocType definitions show core fields, but runtime custom
fields/property setters can change a configured site's metadata.  This audit
did **not** query a configured site's database or resolve its secret-backed
runtime configuration, so runtime metadata and actual site settings are not
claimed as verified.  Task 42 needs runtime-metadata tests against its target
site for Delivery Note, Delivery Note Item, Sales Order/Item, Sales
Invoice/Item, Customer, Item, and Warehouse.

Source-backed minimums are:

| Derived by native mapper/controller | Conditional user/native validation |
|---|---|
| Customer/company/currency/address/taxes/team, prices/totals, SO linkage, rate, remaining qty, cost center, packed items, serial/batch mode | source must be Submitted; stock warehouse; linked source consistency; integer UOM rules; SO not on hold/closed; SRE warehouse; serial/batch/quality/stock validation; installed-app fields/hooks |

The conversion tool should accept only the exact Sales Order name.  It must not
accept Company, Customer, item, qty, rate, warehouse, tax, serial, bundle,
status, link, or bypass fields.  The native mapper/defaulting phase owns them.

## 10. Submit effects

Delivery Note is materially different from a commercial-only Draft.  Its
`on_submit()` executes all of the following under native transaction control:

1. validates packed quantities and updates Pick List status;
2. runs Authorization Control approval authority validation;
3. updates source quantities/status through `update_prevdoc_status()` and
   billing state through `update_billing_status()`;
4. checks credit limit for non-return DNs (or can create the configured return
   invoice path for a return with `issue_credit_note`);
5. creates serial/batch bundles from current or legacy fields and validates
   standalone serial customer restrictions;
6. updates Stock Reservation Entries;
7. writes Stock Ledger Entries through `update_stock_ledger()` for stock and
   packed stock items;
8. calls `make_gl_entries()` and `repost_future_sle_and_gle()`.

GL is not universally absent.  `StockController.make_gl_entries()` builds GL
when perpetual inventory needs an inventory map, provisional non-stock
accounting applies, or fixed-asset rows exist.  Therefore a submit preview must
say stock/accounting effects may occur and must include the bounded
customer/company/posting date or time/source SO/item/qty/warehouse and
serial-batch summary.  It must not promise exact ledger rows before ERPNext
does the native posting.

No background job was proven in the traced core submit path.  Installed app
hooks can still add synchronous behavior; this is why no MCP duplication or
manual stock/GL update is allowed.

## 11. Cancel and delete behavior

`DeliveryNote.on_cancel()` checks source SO hold/close state and submitted
downstream documents, updates source and billing state, reverses reservation
and stock updates, cancels submitted Packing Slips, updates Pick List status,
reverses GL entries, reposts future SLE/GLE, ignores only framework-controlled
ledger/bundle linked doctypes during cancellation, and deletes auto-created
batches.  It does not authorize deleting a submitted Sales Invoice or
Installation Note.

`check_next_docstatus()` explicitly refuses cancellation if a linked submitted
Sales Invoice or Installation Note exists.  Return records and immutable-ledger
or backdated constraints must remain normal ERPNext validation outcomes.  The
generic lifecycle delete path must retain Frappe's linked-document-aware delete
logic and must never cascade delete Sales Invoices, returns, Packing Slips,
shipment records, or delivery records.  Task 42 should permit Delivery Note in
Sales `submit`, `cancel`, and `delete` only; no generic field update or child
add after this conversion foundation.

## 12. Delivery Note -> Sales Invoice mapping

The installed callable is:

```python
erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice(
    source_name, target_doc=None, args=None
)
```

It loads a DN, maps only a Submitted DN parent (`docstatus == 1`) to a Sales
Invoice, maps `Delivery Note Item.name -> dn_detail`, `parent -> delivery_note`,
`so_detail -> so_detail`, `against_sales_order -> sales_order`, and cost center.
It calculates each row's pending quantity from submitted Sales Invoice Item
quantities for that DN, subtracts submitted return-DN quantity, supports an
internal `filtered_children` argument, and rejects an empty result in
`set_missing_values` with “already Invoiced/Returned”.  It preserves taxes,
sales team, customer/company/currency/address defaults and payment-term logic.

India Compliance's `after_mapping` hook copies defined e-Waybill invoice fields
from DN to SI.  That is an additional reason to call the native mapper rather
than reproduce the field map.

Recommendation: implement a separate, immediately following **Task 43 —
Delivery Note to Sales Invoice Native Conversion**.  It should clone the proven
SO-to-SI prepare/claim/remap/fingerprint/Draft-only pattern, use this exact
mapper, and have the same direct/REST parity.  Combining it with Task 42 would
make the first stock-document task significantly wider while requiring a
second mapper's returned/invoiced edge cases.  It is still the next priority.

## 13. Permission, identity, approval, and backend parity

### Direct backend

`runtime.execute_tool_with_context()` initializes the configured
`MCP_FRAPPE_SITE`; stdio uses `MCP_FRAPPE_USER`, while streamable HTTP resolves
the request identity and never falls back to that process user.  Future DN
operations must execute in that same authenticated Frappe context.

Prepare must require source SO Read and DN Create; lifecycle native methods
must require normal submit/cancel/delete permission through their current
lifecycle loader.  Warehouse, Customer, Company, Item and Link visibility must
continue to be checked by native mapping/validation and Frappe permissions.
Neither code path may use `ignore_permissions=True`, flags-based elevation, or
Administrator impersonation.

### REST backend

The Task 40 path is:

```text
typed MCP wrapper -> execute_tool_with_context(rest_arguments)
  -> fixed HTTPS REST client -> execute_mcp_operation
  -> static typed remote operation registry -> same native service
```

The remote Frappe API-token principal is the business authority.  REST is
stdio-only today; it deliberately rejects the local streamable-HTTP identity
mix.  The remote endpoint accepts a strict envelope and no arbitrary DocType,
method, import path, or model-supplied identity.  Its remote ApprovalStore owns
prepare/confirm tokens; the local client does not inspect them.

All future mutating actions must use the shared `ApprovalStore` and
`claim_for_confirm_write()` with action/site/user binding.  `confirm=true` is
only an execution request; it is not a new approval grant.  The standard
`InteractionDirective` is required—no `approval_needed` or client-specific
field may be invented.

## 14. Installed optional-app integrations

`sites/apps.txt` shows `india_compliance` is installed in this Bench.  This
does not prove it is installed/enabled on every configured target site, so Task
42 must remain optional-app neutral and let normal native hooks run.

The installed app declares Delivery Note hooks in `india_compliance/hooks.py`:
`onload`, `before_print`, `before_validate`, `validate`, `after_mapping`,
`before_update_after_submit`, and `before_cancel`.  The DN override validates
transactions and port address; e-Waybill state is surfaced on load.  The
transaction `after_mapping` hook explicitly copies e-Waybill fields from DN to
SI.  Transporter/address changes after submission can be restricted once an
e-Waybill exists, and the before-cancel hook can apply e-Waybill policy.

Task 42 needs no India Compliance bridge or e-Waybill-generation tool.  It must
not suppress native hooks, supply GST/transporter/e-Waybill fields from the
LLM, or claim that e-Waybill generation happens automatically.  These are
site/configuration-dependent native integrations and should be explicit future
capabilities if needed.

## 15. MCP reuse matrix

| Concern | Existing foundation | Reuse? | Delivery Note-specific work |
|---|---|---:|---|
| typed wrapper/contracts | explicit Sales create/conversion modules | Yes | DN contracts/output models and registry entries |
| approval | shared Frappe-cache ApprovalStore | Yes | exact action/fingerprint/projection |
| native conversion | SO-to-SI conversion service | Yes | call `make_delivery_note`; Draft-only preview including stock facts |
| read/query | field-aware Sales read service pattern | Yes | DN header/item allowlists and safe filters/sorts |
| aggregate | `services/common/aggregate.py` | Yes | DN-local permitted metrics/fields/currency grouping |
| lifecycle | `LIFECYCLE_ACTION_DOCTYPES` | Yes | DN only submit/cancel/delete allowlists, stock-aware preview review |
| PDF | generic `get_print(..., as_pdf=True)` | Yes | DN policy/typed DocType allowlist |
| email | generic prepare/confirm mail | Yes | DN policy/party-email branch and lifecycle-safe tests |
| observability | `public_error` / references | Yes | map native exceptions to bounded DN errors |
| REST | fixed remote operation registry | Yes | fixed typed handler per DN public operation |

## 16. Candidate capability classification

| Candidate | Classification | Decision |
|---|---|---|
| A. SO -> DN `prepare_*`/`confirm_*` | **Include in Task 42** | primary creation path |
| B. standalone DN | **Defer from V1** | legitimate but separate broad contract |
| C. `get_delivery_note` | **Include in Task 42** | required to inspect a created/submitted fulfillment record |
| D. `query_delivery_notes` | **Include in Task 42** | current normalized field-aware convention |
| E. `aggregate_delivery_notes` | **Include in Task 42** | limited count/sum through shared aggregate only |
| F. submit/cancel/delete | **Include in Task 42** | existing generic lifecycle boundary, strict action allowlist |
| G. DN -> SI conversion | **Implement immediately after Task 42** | separate native mapping task |
| H. PDF/email | **Include in Task 42** | generic foundations, policy extension only |
| I. return DN | **Defer from V1** | cancellation/return accounting semantics need a dedicated contract |
| J. Packing Slip/Pick List/Delivery Trip/Shipment | **Defer from V1** | inspect interaction only; no automatic expansion |

## 17. Proposed minimal public contracts

These are conceptual shapes, not implementation code.

| Capability | Minimal input | Bounded output | Server-internal / forbidden input |
|---|---|---|---|
| `prepare_sales_order_to_delivery_note` | exact `sales_order` name | ready approval token, expiry, source identity/status, target customer/company/posting date/currency, item code/name/qty/UOM/rate/amount/warehouse, SO row lineage, bounded packed and serial/batch indicator, totals | target doc, qty override, warehouse/rate/tax/serial allocation, mapper flags, permission flags |
| `confirm_sales_order_to_delivery_note` | opaque approval token, boolean confirm | created Draft DN name/docstatus/source SO/customer/company/totals | all target fields; no submit flag |
| `get_delivery_note` | exact name, controlled `fields` | allowed header and optionally bounded items | full document, arbitrary meta/system/GST/cache fields |
| `query_delivery_notes` | typed allowlisted filters/projection/sort/limit | bounded records/cursor-equivalent existing convention | SQL, arbitrary filter expressions, unbounded results |
| `aggregate_delivery_notes` | typed metric/filter/group selection | count/sum results according to local policy | raw aggregate/SQL expressions |
| generic submit/cancel/delete | existing exact `{doctype: "Delivery Note", name}` target | existing lifecycle preview/result | arbitrary update/child mutations |
| generic PDF/email | existing exact DN target and existing bounded arguments | native artifact / queued-email result | HTML/CSS/Jinja or arbitrary recipient discovery |

For submit, the generic lifecycle preview should be enhanced only if its shared
contract already supports an action-specific bounded snapshot; otherwise Task
42 should document the limitation and keep the existing lifecycle semantics.
It must show the operator enough stock-impact detail before approval without
leaking full rows or stock state.

## 18. Data-minimization and leakage review

Return only the source/target identity, customer/company/currency/date,
commercial totals, row-level item/UOM/qty/warehouse/lineage, and a bounded
serial/batch/packed-item indicator needed for a human to review the action.
Do not return raw ERPNext documents, all custom fields, all serial numbers,
Bin quantities, valuation rates, tax/account ledger internals, SRE records,
cache state, stack traces, native exception text, secrets, or arbitrary
metadata.  Safe public error codes must be mapped by the service and correlated
through the existing internal observability reference.

## 19. Task 42 implementation test matrix

Task 42 must add unit/static tests, with authenticated site/MCP verification
reported separately.  At minimum:

1. Sales-only registration and unchanged Purchase registration/catalog;
2. typed schemas reject extra fields and public names are deterministic;
3. submitted permitted SO maps to a native Draft DN preview; Draft/cancelled
   source and no remaining rows return bounded results;
4. source read and DN Create permission denial are bounded, and mapper receives
   no public permission bypass;
5. partial quantity, stock-only, service-only, mixed, drop-ship, bundle and
   unit-price-row behavior follows native mapper output;
6. warehouse missing/default/reservation mismatch, serial/batch requirement,
   stock/quality/native validation errors stay native and safely bounded;
7. prepare writes no DN or stock/ledger data; successful confirm inserts only
   `docstatus=0`, preserves `against_sales_order`/`so_detail`, and does not
   submit;
8. approval is site/user/action bound, one-shot, expiring, rejects false
   confirmation/wrong user/site/action/concurrent repeat, and fresh remap
   detects material SO/native preview change;
9. generic lifecycle requires approval, calls native submit/cancel/delete, and
   never auto-deletes downstream links; test submitted SI blocking cancel;
10. get/query/aggregate enforce existing read permissions and allowlists,
    aggregate uses Frappe v16 dict syntax, and unsupported fields/metrics fail
    closed;
11. PDF uses native print and email uses generic queued-mail behavior without
    raw HTML input;
12. every DN wrapper supplies typed JSON-safe REST arguments, every operation
    has a static Sales-only remote registry entry, unknown operation/payload
    fails closed, and direct/REST results/errors conform to the same contract;
13. regress Quotation, Sales Order, Sales Invoice,
    `DELIVERY_NOTE_REQUIRED`, approval-store, REST, Customer/Item, and Purchase
    tests.

Live tests must additionally verify the configured site's runtime metadata,
installed apps, permissions, available warehouse/stock behavior, remote API
principal, and an explicitly authorized throwaway transaction.  None were run
for this audit.

## 20. Risks and limitations

### Confirmed

The source files above establish mappers, Draft defaulting, stock/GL/SRE side
effects, downstream-cancellation restrictions, current MCP gaps, and Task 40
REST architecture.

### Version/site-sensitive

Configured Selling/Stock/Accounts/GST settings, Customer exceptions, custom
fields/property setters, actual warehouse/serial/batch requirements, immutable
ledger restrictions, exact installed apps per target site, permissions, and
runtime metadata were not queried.  Source-based claims must be revalidated in
Task 42's target-site test plan.  The Bench has India Compliance installed, but
that is not a global deployment assumption.

### Deferred deliberately

Standalone DN, DN->SI conversion (next task), returns, partial-row selection,
reserved-stock UI options, Pick List, Packing Slip, Delivery Trip, Shipment,
auto serial/batch allocation, e-Waybill/transporter actions, Accounts, Payment
Entry, and client-specific workflow configuration are out of Task 42.

## 21. Exact Task 42 recommendation

**Task 42 — Delivery Note V1 Implementation Foundation (Sales only)**

Implement only:

1. explicit typed `prepare_sales_order_to_delivery_note` and
   `confirm_sales_order_to_delivery_note` wrappers/contracts/service using
   ERPNext's `sales_order.make_delivery_note` with normal permissions;
2. prepare -> shared approval -> atomic claim -> fresh source/remap/fingerprint
   -> normal-permission **Draft-only** insertion, with bounded source/target
   preview and safe native error mapping;
3. `get_delivery_note`, `query_delivery_notes`, and
   `aggregate_delivery_notes` via current field-aware/common foundations and
   DocType-local allowlists;
4. Delivery Note in Sales generic lifecycle **submit/cancel/delete only**;
5. Delivery Note in Sales generic PDF/email policy only after read/print/email
   permission checks;
6. direct and REST implementations of every one of those public operations,
   using fixed typed remote-operation entries and the same service authority;
7. the test matrix in this report and necessary tool catalog/architecture
   documentation regeneration.

Do not implement standalone DN, returns, arbitrary mapper options, custom
stock/serial/warehouse allocation, DN->SI conversion, Accounts/Payment Entry,
or a product/service workflow configuration.  Freeze the immediately following
Task 43 as the native Delivery Note -> Sales Invoice conversion described in
Section 12.
