# Customer Payment Advance to Sales Invoice Reconciliation — Native Capability Audit

**Audit date:** 2026-09-17
**Task:** `54_TASK_CUSTOMER_PAYMENT_ADVANCE_TO_SALES_INVOICE_RECONCILIATION_NATIVE_CAPABILITY_AUDIT.md`
**Scope:** static source, metadata, existing tests, and current MCP checkout only

## 1. Decision summary

The installed ERPNext version already has a native reconciliation path for applying an existing submitted Customer Payment Entry to a submitted Sales Invoice. It supports the important source variants needed for a narrow capability:

1. an unallocated submitted Customer Payment Entry; and
2. a submitted Customer Payment Entry that currently carries a Sales Order advance reference.

The native mutation is not a direct child-table update and does not submit a new Payment Entry. The safe native seam is:

```text
Payment Reconciliation.reconcile_allocations()
    -> erpnext.accounts.utils.reconcile_against_document(...)
        -> update_reference_in_payment_entry(...)
        -> submitted Payment Entry save/update-after-submit
        -> native Payment Ledger / Advance Payment Ledger / GL maintenance
        -> update_voucher_outstanding(Sales Invoice)
```

The recommended first MCP capability is therefore **Option A: one existing submitted Customer Payment Entry to one submitted Sales Invoice, one positive allocation**. It must be a prepare/confirm operation using the shared MCP approval store and a server-side freshness fingerprint. It must not expose a generic “reconcile anything” interface.

Payment Terms allocation, multi-invoice allocation, Journal Entry advances, returns/credit-note reconciliation, reversal, and asynchronous bulk reconciliation are outside this first capability. They have native pieces, but require a different public contract and separate regression coverage.

This audit is inspection-only. No production code, tests, settings, database records, queues, or live accounting documents were changed by this audit.

## 2. Evidence boundary and repository state

### 2.1 Confirmed versions

| Component | Evidence | Version/commit | Boundary |
|---|---|---|---|
| Frappe | `apps/frappe/frappe/__init__.py` | `16.34.0` / `c1f1e8ec3708750d7254f7f99d869ffb9886f19f` | local source only |
| ERPNext | `apps/erpnext/erpnext/__init__.py` | `16.35.0` / `12cd563fb9a79731f75ae2a45b1446a0a2dd9e74` | local source only |
| India Compliance | `apps/india_compliance/india_compliance/__init__.py` | `16.9.0` | local installed source; no tag was assumed |
| mcp_erpnext | `git -C apps/mcp_erpnext` | branch `master`, commit `9486dbc1b496a9017450c7ef9cf982f993d4a01a` | local checkout only |

No claim is made here about the currently running site, database contents, enabled regional configuration, queue workers, Redis state, HTTP listeners, or browser/UI behavior. Those require live verification against the authoritative site and authenticated identity.

### 2.2 Pre-existing mcp_erpnext worktree state

Before this report was created, the mcp_erpnext checkout already contained Task 53 and related changes. They were preserved. The relevant pre-existing status was:

```text
 M docs/TOOLS.md
 M mcp_erpnext/contracts/accounts/__init__.py
 M mcp_erpnext/contracts/registry.py
 M mcp_erpnext/profiles/accounts.py
 M mcp_erpnext/remote_operations.py
 M mcp_erpnext/tests/test_profiles.py
 M mcp_erpnext/tests/test_rest_backend.py
 M mcp_erpnext/tests/test_tool_contracts.py
?? docs/inspect/CUSTOMER_ADVANCE_AND_PAYMENT_RECONCILIATION_NATIVE_FLOW_AUDIT.md
?? docs/inspect/SALES_ORDER_CUSTOMER_ADVANCE_PAYMENT_IMPLEMENTATION_REPORT.md
?? docs/tasks/audits/52_TASK_CUSTOMER_ADVANCE_AND_PAYMENT_RECONCILIATION_NATIVE_FLOW_AUDIT.md
?? docs/tasks/audits/54_TASK_CUSTOMER_PAYMENT_ADVANCE_TO_SALES_INVOICE_RECONCILIATION_NATIVE_CAPABILITY_AUDIT.md
?? docs/tasks/implementation/53_TASK_SALES_ORDER_CUSTOMER_ADVANCE_PAYMENT_V1_IMPLEMENTATION.md
?? mcp_erpnext/contracts/accounts/sales_order_advance_payment.py
?? mcp_erpnext/services/accounts/sales_order_advance_payment.py
?? mcp_erpnext/tests/test_sales_order_advance_payment.py
?? mcp_erpnext/tools/accounts/sales_order_advance_payment.py
```

The audit report is the only file added for Task 54. The existing broad Task 52 audit and Task 53 implementation report were used as context but were not rewritten.

## 3. Current MCP baseline

The Accounts profile currently exposes the existing Customer Payment Entry, Sales Invoice payment, multi-invoice receipt, Payment Entry read, Sales Order advance payment, and lifecycle capabilities through:

- `mcp_erpnext/profiles/accounts.py`
- `mcp_erpnext/contracts/accounts/__init__.py`
- `mcp_erpnext/contracts/registry.py`
- `mcp_erpnext/remote_operations.py`
- the corresponding `mcp_erpnext/services/accounts/` and `tools/accounts/` modules

The existing `mcp_erpnext/services/accounts/sales_invoice_payment.py` creates a new Draft Payment Entry for a Sales Invoice. It is not reconciliation of an already submitted Payment Entry. The future capability must have a distinct name and contract, for example:

```text
prepare_customer_payment_reconciliation
confirm_customer_payment_reconciliation
```

The future capability must be added consistently to the typed contract, service, tool, Accounts profile, fixed registry/catalog, REST dispatch, focused tests, and generated/tool documentation. This audit does not add those production surfaces.

The existing approval and fingerprint mechanisms are suitable for the future capability:

- `mcp_erpnext/approvals.py` — shared `ApprovalStore`, including atomic `claim_for_confirm_write()`;
- `mcp_erpnext/services/common/fingerprint.py` — canonical SHA-256 fingerprinting;
- existing Accounts prepare/confirm services — server-derived identity and bounded confirmation results.

The future tool must use the authenticated `frappe.session.user` and current site. It must not accept a public user, site, approval mode, or `confirm=true` flag as authority.

## 4. Native flow map

```text
submitted Customer Payment Entry
        |
        | native discovery: get_advance_payment_entries_for_regional()
        | accepts unallocated PE or eligible Sales Order reference row
        v
virtual Payment Reconciliation.payment rows
        + submitted Sales Invoice
        | native outstanding discovery: get_outstanding_invoices()
        v
virtual one-payment/one-invoice allocation
        |
        | PaymentReconciliation.reconcile_allocations()
        v
reconcile_against_document()
        |
        + check_if_advance_entry_modified()
        + validate_allocated_amount()
        + update_reference_in_payment_entry()
        |     - append invoice reference for unallocated source
        |     - split Sales Order reference row for an advance source
        + submitted Payment Entry save with native after-submit flags
        + rebuild/repost native ledger entries
        + update_voucher_outstanding(Sales Invoice)
        v
bounded post-confirm result after reloading both documents
```

## 5. Payment Reconciliation is a virtual operational document

`erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.py` is not an ordinary persisted business document:

- `load_from_db()` fabricates the operational object in memory (`:83-109`);
- `save()` returns without persistence (`:111-112`);
- list/count/stats and database insert/update/delete methods are no-ops (`:114-133`);
- the DocType JSON has `"is_virtual": 1` and `"issingle": 1`;
- its roles are Accounts User and Accounts Manager.

The payment, invoice, and allocation child rows are also virtual. The operational object is a native calculator and mutation coordinator, not an approval record or durable audit record. MCP approval state must therefore remain in the shared MCP approval store, while ERPNext remains authoritative for the accounting mutation.

The native `reconcile()` method first validates and reconciles allocations and then refreshes the virtual unreconciled entries. `reconcile_allocations()` is the narrower mutation seam for an already constructed exact allocation and is the recommended confirm-time native call.

## 6. Source Payment Entry discovery

### 6.1 Native discovery path

`PaymentReconciliation.get_payment_entries()` calls:

```python
get_advance_payment_entries_for_regional(
    self.party_type,
    self.party,
    party_account,
    order_doctype="Sales Order",
    default_advance_account=self.default_advance_account,
    against_all_orders=True,
    ...
)
```

The base implementation is in `erpnext/controllers/accounts_controller.py`:

- `get_advance_payment_entries_for_regional()` (`:3469-3471`) is the regional extension point;
- `get_advance_payment_entries()` (`:3474-3528`) discovers Payment Entry reference rows against Sales Orders and, when requested, unallocated Payment Entries;
- `get_common_query()` (`:3531-3624`) restricts the source to submitted Payment Entries with the correct payment direction, party type, party, company, and account.

For a narrow MCP operation, the server must additionally filter the native discovery to the exact requested Payment Entry and, when applicable, the exact Payment Entry Reference row. It must not accept a name merely because the document exists.

### 6.2 Eligible source forms

The native source forms relevant to V1 are:

| Source | Native eligibility | V1 decision |
|---|---|---|
| Submitted Customer `Receive` PE with positive `unallocated_amount` | discovered by the unallocated branch | support |
| Submitted Customer `Receive` PE with eligible submitted `Sales Order` reference row and remaining allocation | discovered by order-reference branch | support as an SO advance source |
| Draft/cancelled PE | filtered by `docstatus=1` | reject |
| Supplier/payment direction or wrong party/company | native filters reject | reject |
| Journal Entry customer advance | native reconciliation can handle it in other paths | exclude from V1 |
| PE whose available amount is already allocated to an invoice | no remaining eligible source amount | reject |

The query itself does not enforce all normal document permissions. It also does not prove that an exact source remains unchanged between prepare and confirm. Those are MCP responsibilities in addition to native revalidation.

### 6.3 Sales Order advance semantics

An SO-linked advance and an unallocated standalone Customer Payment Entry use the same native reconciliation machinery after discovery. The distinction is in the source reference state:

- an unallocated source receives a new Sales Invoice reference row;
- an SO-linked source has its existing SO reference allocation reduced and a new Sales Invoice reference row appended;
- the new row retains the original advance voucher metadata where required, so native advance ledger behavior remains connected to the originating Sales Order advance.

The source code does not require the target Sales Invoice to have originated from the same Sales Order. The native operation is party/company/account based, with current outstanding and source-reference validation. A future V1 must not invent a same-SO rule, but must also not expose a broader cross-party or cross-company operation.

## 7. Target Sales Invoice outstanding authority

`PaymentReconciliation.get_invoice_entries()` uses `erpnext.accounts.utils.get_outstanding_invoices()` and the Payment Ledger, not a direct unvalidated read of `Sales Invoice.outstanding_amount`.

`get_outstanding_invoices()` (`erpnext/accounts/utils.py:1239-1315`) and `QueryPaymentLedger` (`:2240-2489`) derive outstanding values from non-delinked Payment Ledger entries, account/party filters, dimensions, posting date, and account currency. The invoice is returned only when its account-currency outstanding is above the native precision threshold.

This is the authoritative amount for the prepare projection and the confirm-time freshness check. A stale or manually supplied outstanding amount must never be trusted.

The separate `get_outstanding_reference_documents()` helper in `payment_entry.py` is term-aware and performs party permission checks, but it is a different Payment Entry reference-document path. It is not what the generic Payment Reconciliation invoice list uses.

## 8. Exact native mutation and submitted PE behavior

### 8.1 Mutation chain

`erpnext.accounts.utils.reconcile_against_document()` (`:508-578`) is the exact native mutation utility used by both Payment Reconciliation and Sales Invoice advance allocation. For Payment Entries it:

1. groups source entries by source voucher;
2. checks the source has not changed since discovery with `check_if_advance_entry_modified()`;
3. validates the allocated amount with `validate_allocated_amount()`;
4. calls `update_reference_in_payment_entry(..., do_not_save=True, ...)`;
5. saves the submitted Payment Entry with `ignore_permissions=True` and native after-submit flags;
6. handles separate advance-account reclassification through `make_advance_gl_entries()` when configured; otherwise rebuilds the relevant Payment Ledger/advance ledger state;
7. calls `update_voucher_outstanding()` for the target invoice.

The utility does not directly submit the Payment Entry. The source is already submitted; the operation is a controlled update-after-submit of its reference allocation and accounting ledgers.

### 8.2 Unallocated source

`update_reference_in_payment_entry()` appends a new target `Payment Entry Reference` for the Sales Invoice, sets the allocated and exchange fields, invokes native missing-reference-detail and exchange-gain/loss logic, and saves through the Payment Entry lifecycle.

### 8.3 Sales Order advance source

When a source reference row is supplied, the same helper:

- loads the existing source child row;
- reduces the existing SO allocation;
- appends a submitted target invoice reference row;
- retains the advance voucher information needed by native advance accounting;
- lets Payment Entry and ledger hooks rebuild the resulting state.

This is why MCP must not append or edit `Payment Entry Reference` rows itself.

### 8.4 Native stale-source guard

`check_if_advance_entry_modified()` compares the prepared source against the current submitted Payment Entry. It checks either:

- the exact source reference row and its allocated amount; or
- the source Payment Entry’s current unallocated amount when no reference row was used.

It fails with the native “Payment Entry has been modified after you pulled it” path when the source no longer matches. MCP should add a clearer pre-confirm stale fingerprint, but must retain the native guard as the final source validation.

### 8.5 Native current-target guard

The subsequent Payment Entry save runs `validate_allocated_amount_with_latest_data()` (`payment_entry.py:428-511`). It re-reads current outstanding reference documents and checks the requested allocation against current invoice and, where applicable, payment-term outstanding. `update_voucher_outstanding()` then recomputes the target outstanding from the Payment Ledger.

## 9. Sales Invoice lifecycle and native advance allocation comparison

The normal Sales Invoice lifecycle provides a second proof of the same native accounting seam:

- `SalesInvoice.on_submit()` invokes `update_against_document_in_jv()`;
- `AccountsController.get_advance_entries()` discovers Sales Order and unallocated advances;
- `update_against_document_in_jv()` constructs target-invoice reconciliation arguments;
- it calls `reconcile_against_document()` with `is_advance="Yes"`;
- the target invoice outstanding and source Payment Entry references are updated through the same native utility.

This confirms that applying an existing SO advance to a later Sales Invoice is an established ERPNext operation. It does not authorize MCP to duplicate that internal implementation; MCP should supply a bounded typed request and delegate the mutation to the native seam.

## 10. Standalone receipt interoperability

The existing MCP standalone Customer Payment Entry path creates a new Draft Payment Entry. Native interoperability is therefore:

```text
MCP standalone receipt -> native submitted Payment Entry
MCP reconciliation    -> native update of that submitted Payment Entry
```

Both paths use the same submitted Payment Entry reference, party, company, account, currency, and ledger model. The reconciliation capability must not create a second receipt, duplicate the payment amount, or treat an already allocated invoice receipt as an advance.

## 11. Separate advance account behavior

The company setting `book_advance_payments_in_separate_party_account` changes both discovery and mutation:

- `Payment Entry.set_liability_account()` selects the Customer advance account when enabled;
- `get_common_query()` accepts the configured advance account only when the setting permits it;
- `PaymentReconciliation.get_invoice_entries()` includes the normal receivable account and configured default advance account where appropriate;
- `reconcile_against_document()` calls `PaymentEntry.make_advance_gl_entries(entry=...)` for the reclassification path;
- the reconciliation posting date is selected by the native `reconciliation_takes_effect_on` setting, including Advance Payment Date, Reconciliation Date, or the configured oldest applicable date.

Existing ERPNext tests cover separate-account reconciliation dates and ledger effects. A future MCP preview may report that the separate-account path applies and the effective allocation date, but must not expose or let the caller override raw account, GL, or ledger details.

## 12. Payment Terms boundary

Generic Payment Reconciliation invoice rows do not carry a `payment_term` field. Its invoice discovery uses `get_outstanding_invoices()`, and its allocation is invoice-level.

The native Payment Entry helper `get_outstanding_reference_documents()` can split a Sales Invoice into Payment Schedule rows through `split_refdocs_based_on_payment_terms()`. That path includes `payment_term` and `payment_term_outstanding`, and `PaymentEntry.validate_allocated_amount_with_latest_data()` requires the exact term when a template has `allocate_payment_based_on_payment_terms` enabled.

Therefore:

- invoice-level allocation is acceptable when no term-specific allocation is active;
- a Sales Invoice with active payment-term allocation must be rejected by V1 with a stable `PAYMENT_TERMS_UNSUPPORTED` error;
- MCP must not silently allocate against the invoice total or choose the first schedule;
- a later term-aware capability must accept an exact payment-term identity and use the term-aware native reference path.

## 13. Currency, exchange gain/loss, rounding, and amount semantics

Native reconciliation uses the source and target account currencies, source/target exchange rates, and the invoice exchange map. `PaymentReconciliation.allocate_entries()` calculates allocation and difference amounts and uses the company exchange gain/loss account where required. `Payment Entry.make_exchange_gain_loss_journal()` handles the native exchange adjustment path.

The public V1 amount must be defined as:

```text
amount = positive decimal in the native reconciliation/account currency shown by prepare
```

The caller must not provide exchange rates, company-currency amounts, gain/loss accounts, or posting dates. The server derives those values from the current documents and company settings.

The prepare response should return only the bounded allocation currency, available source amount, target outstanding, requested amount, and effective native allocation. It must not return raw Payment Ledger, GL, exchange-map, or bank-account rows.

The native precision and tolerance rules remain authoritative. MCP must reject non-finite, zero, negative, or over-available amounts before confirm, while native validation remains the final guard for rounding and over-allocation.

## 14. India Compliance and regional hooks

The installed India Compliance app overrides the native extension points through `india_compliance/hooks.py`:

- `get_advance_payment_entries_for_regional` is overridden to adjust eligible advance amounts for pending GST behavior;
- `PaymentReconciliation.adjust_allocations_for_taxes` is overridden to adjust allocation rows for tax proportions;
- Payment Entry validate, submit, update-after-submit, and cancel hooks can create or reverse GST-related ledger effects.

The regional implementation is in `gst_india/overrides/payment_entry.py`. It can change the effective allocation amount and create GST reversal GL/Payment Ledger effects during reconciliation. Existing India Compliance tests cover inclusive/exclusive tax cases, separate advance accounts, foreign currency, exchange differences, and multiple invoices.

The future MCP implementation must call the regional-decorated native entry point and the native reconciliation method. It must not import the base implementation directly or recompute GST in MCP. Prepare should expose a bounded regional adjustment warning/effective amount when the native projection can determine it; confirm must re-run the regional path. Live site region, hooks, and company tax configuration remain unverified by this audit.

## 15. Permissions, identity, and trust boundary

Native internal reconciliation intentionally saves the submitted Payment Entry with `ignore_permissions=True`. The MCP boundary must compensate with explicit authorization before invoking it.

The future service should require, at minimum:

1. authenticated current-site `frappe.session.user`;
2. permission to use Payment Reconciliation / the Accounts capability;
3. read access to the exact Customer, Payment Entry, Sales Invoice, Company, and relevant account records;
4. write capability on the exact submitted Payment Entry, including the submitted-reference update path;
5. party/company/account consistency checked from server-loaded documents;
6. no caller-supplied user, site, company, customer, account, or permission bypass.

The exact framework permission combination should be confirmed with focused tests against the supported roles before Task 55 is merged. The static source proves that native reconciliation can bypass document permissions internally; it does not prove which live user roles are currently assigned on `yob.localhost`.

## 16. Synchronous versus background behavior

Direct `PaymentReconciliation.reconcile()` is synchronous. ERPNext also has the persistent `Process Payment Reconciliation` flow:

- it queues broad filter-based work when Accounts Settings enables auto reconciliation;
- it persists logs and allocations;
- it enqueues fetch/allocate and reconcile jobs;
- Frappe captures the initiating user in the queued job arguments and commits successful jobs or rolls back failed jobs.

The exact one-PE/one-SI V1 should be synchronous. It should not create a `Process Payment Reconciliation` document or a custom queue job. Before mutation, it should detect the matching native running/paused reconciliation condition and fail closed with `RECONCILIATION_ALREADY_RUNNING` when the native settings make concurrent broad reconciliation possible.

If a later bulk capability is required, it should delegate to the native Process Payment Reconciliation DocType rather than reproduce its queue, persistence, retry, or status model in MCP.

## 17. Concurrency and idempotency

The native path has useful but incomplete concurrency defenses:

- source Payment Entry stale-reference/unallocated checks;
- current target outstanding validation during Payment Entry save;
- native Payment Ledger recomputation;
- a running-process guard for configured auto reconciliation.

It does not provide a public idempotency key for MCP and does not make a timed-out external request safe to replay blindly. The future approval fingerprint must include at least:

- exact Payment Entry and Sales Invoice names;
- source docstatus, modified value, party/company/payment type, source account and currency;
- exact unallocated amount or exact source `Payment Entry Reference` identity, reference type/name, allocated amount, and advance voucher metadata;
- all current source reference rows relevant to split/replay;
- current native invoice outstanding and Sales Invoice modified value;
- invoice company/customer/debit-to account/currency/conversion rate;
- payment-term state;
- separate-advance-account and reconciliation-date settings;
- relevant regional capability/version/configuration state when it affects the projection;
- requested amount and authenticated site/user context as appropriate for the approval binding.

The fingerprint must be built from canonical server-derived data, not arbitrary caller JSON. On confirm, the service must reload both documents, reconstruct the native projection, compare the fingerprint, and stop with `APPROVAL_STALE`/`SOURCE_CHANGED` before mutation when it differs. The native stale guard remains mandatory.

For an ambiguous timeout after a possible commit, the client must inspect the exact source and target before requesting a new approval. MCP must not automatically replay the mutation.

## 18. Reversal and cancellation

ERPNext has a native `Unreconcile Payment` DocType for unlinking Payment Entry/Journal Entry allocations and native cancellation flows for Payment Entries and Sales Invoices. Its source is:

```text
erpnext/accounts/doctype/unreconcile_payment/unreconcile_payment.py
```

It discovers linked payments from Payment Ledger and Advance Payment Ledger entries, unlinks native references, reverses exchange effects where needed, and updates voucher outstanding. Payment Entry cancellation and Sales Invoice cancellation have their own native restrictions and ledger reversal behavior.

V1 must not implement a custom reverse-by-editing-reference-rows action. Reversal should be a later, separately specified capability that delegates to the native Unreconcile Payment/cancellation workflow and has its own approval and tests.

## 19. Candidate V1 contract

### 19.1 Public inputs

Recommended prepare input:

```json
{
  "payment_entry": "ACC-PAY-00001",
  "sales_invoice": "ACC-SINV-00001",
  "amount": "100.00"
}
```

Only exact document names and a positive amount are caller-supplied. Customer, company, payment direction, source reference row, account, currency, rates, payment term, gain/loss account, regional behavior, and posting date are server-derived.

Recommended confirm input:

```json
{
  "approval_token": "opaque-server-issued-token"
}
```

The approval token must be claimed through `ApprovalStore.claim_for_confirm_write()`. No public approval mode or user/site field is permitted.

### 19.2 Accepted scope

V1 accepts only:

- submitted Customer `Receive` Payment Entry;
- exact current eligible unallocated amount or exact eligible Sales Order advance reference;
- submitted ordinary Sales Invoice with positive native outstanding;
- same customer, company, compatible party/account context;
- one positive allocation in the native allocation currency;
- no active payment-term allocation requirement;
- no unsupported return/reversal or Journal Entry path;
- no conflicting native background reconciliation.

### 19.3 Prepare behavior

Prepare should:

1. load the exact documents with server permissions;
2. run exact native source discovery through the regional extension point;
3. run exact native invoice outstanding discovery through Payment Ledger;
4. construct a one-payment/one-invoice virtual Payment Reconciliation projection;
5. apply the native allocation and regional tax adjustment logic in memory where possible;
6. derive a bounded preview and canonical freshness fingerprint;
7. create a shared approval record bound to the current user, site, action, payload/fingerprint, and expiry.

This is a projection, not a guaranteed side-effect-free native dry run: ERPNext exposes no native dry-run version of `reconcile_against_document()`. Prepare must not call the mutation method or save accounting documents.

### 19.4 Confirm behavior

Confirm should:

1. atomically claim the shared approval;
2. reload and permission-check the exact source and target;
3. reject any fingerprint, terms, party, company, account, amount, or running-process change;
4. reconstruct the exact native virtual allocation;
5. call `PaymentReconciliation.reconcile_allocations()` and therefore `reconcile_against_document()`;
6. allow the normal request transaction to commit or roll back the complete operation;
7. reload the source Payment Entry and Sales Invoice;
8. return a bounded result containing the applied amount, source/target names, resulting target outstanding, and relevant warnings.

The service must not call `frappe.db.commit()` in the middle of the native mutation, append child rows directly, call a generic arbitrary document update, or use a caller-controlled `ignore_permissions` flag.

### 19.5 Bounded output

The response may include:

- source Payment Entry and target Sales Invoice names;
- customer and company names derived from the documents;
- source kind: `unallocated` or `sales_order_advance`;
- allocation amount and native allocation currency;
- target outstanding before/after when freshly available;
- separate-advance-account and regional-adjustment warnings;
- stable status, error, reference, and retryability fields following existing MCP conventions.

It must not include raw GL rows, Payment Ledger rows, bank account details, arbitrary document fields, hidden reference rows, secrets, internal stack traces, or unrestricted database-query output.

## 20. Error and outcome model

The future service should map native failures into stable bounded categories while retaining a server log/reference for diagnostics:

| Category | Meaning |
|---|---|
| `PAYMENT_ENTRY_NOT_FOUND` | exact source does not exist or is not visible |
| `SALES_INVOICE_NOT_FOUND` | exact target does not exist or is not visible |
| `PERMISSION_DENIED` | explicit MCP authorization failed |
| `PARTY_MISMATCH` | source and target customer context differs |
| `COMPANY_MISMATCH` | source and target company differs |
| `ACCOUNT_MISMATCH` | native party/account context cannot reconcile |
| `INVALID_PAYMENT_ENTRY_STATE` | source is not a submitted Customer receipt or has no eligible amount |
| `INVOICE_NOT_OUTSTANDING` | native Payment Ledger shows no positive target outstanding |
| `PAYMENT_TERMS_UNSUPPORTED` | active term-specific allocation cannot be represented by V1 |
| `AMOUNT_EXCEEDS_AVAILABLE` | requested amount exceeds native source or target availability |
| `SOURCE_CHANGED` | source reference/unallocated state changed after prepare |
| `APPROVAL_STALE` | fingerprint or approval binding no longer matches |
| `APPROVAL_ALREADY_USED` | confirmation token was already claimed |
| `RECONCILIATION_ALREADY_RUNNING` | native matching background reconciliation is active |
| `REGIONAL_VALIDATION_FAILED` | India Compliance or another regional hook rejected the operation |
| `NATIVE_VALIDATION_FAILED` | ERPNext validation rejected the exact operation |
| `NATIVE_RECONCILIATION_UNAVAILABLE` | the pinned native seam is absent or incompatible |
| `RECONCILIATION_FAILED` | bounded unexpected failure with diagnostic reference |

Existing native exception messages must not be exposed wholesale when they contain implementation details or sensitive data.

## 21. REST, profile, and registry implications for Task 55

Task 55 must keep stdio and REST behavior equivalent:

- typed contract in `mcp_erpnext/contracts/accounts/`;
- registry/catalog entry in `mcp_erpnext/contracts/registry.py`;
- Accounts profile exposure in `mcp_erpnext/profiles/accounts.py`;
- tool adapter under `mcp_erpnext/tools/accounts/`;
- service under `mcp_erpnext/services/accounts/`;
- fixed remote operation/REST dispatch in `mcp_erpnext/remote_operations.py`;
- focused contract, profile, REST, service, approval, and native-seam tests;
- corresponding `docs/TOOLS.md` and generated documentation updates.

The public contract must remain DocType-specific and fixed-operation. `fields`, if present in an unrelated read tool, must not become an arbitrary query or projection escape hatch for this write capability.

## 22. Task 55 implementation/test matrix

Task 55 should be a separate implementation task with the following minimum matrix. No live mutation is implied by this audit.

### Contract and registry

- prepare and confirm names, schemas, descriptions, and Accounts profile exposure;
- stdio and REST dispatch parity;
- unknown/arbitrary fields rejected;
- no public user/site/approval-mode/permission-bypass fields;
- bounded output contains no raw ledger or bank data.

### Source and target validation

- unallocated submitted Customer receipt PE;
- submitted SO-linked Customer advance PE;
- draft, cancelled, Supplier, wrong party, wrong company, and already-allocated sources rejected;
- submitted ordinary Sales Invoice with positive outstanding;
- missing, cancelled, return, non-outstanding, wrong-party, wrong-company, and account-mismatch targets rejected;
- amount zero, negative, non-finite, over-source, over-invoice, and precision-boundary cases;
- source and target modified between prepare and confirm;
- exact SO reference-row split and exact unallocated append behavior.

### Native accounting

- source Payment Entry reference rows after confirmation;
- Sales Invoice outstanding and status after confirmation;
- Payment Ledger and Advance Payment Ledger effects through native code;
- separate advance account enabled and disabled;
- each supported `reconciliation_takes_effect_on` setting;
- exchange-rate differences, gain/loss, rounding, and account-currency boundaries;
- native transaction rollback on validation failure;
- no direct child-table or direct GL mutation by MCP.

### Payment Terms and regional behavior

- no active term allocation accepted;
- active term allocation rejected with `PAYMENT_TERMS_UNSUPPORTED`;
- India Compliance installed and regional hooks active;
- GST-inclusive/exclusive or equivalent regional allocation adjustment;
- regional validation failure and bounded error mapping;
- optional regional app absent, if the support matrix permits that environment.

### Security, approval, and concurrency

- exact authenticated user/site binding;
- Accounts/Payment Reconciliation and document permission failures;
- approval expiry, wrong user, wrong site, wrong action, changed payload, and single-use claim;
- competing native Process Payment Reconciliation job;
- second confirm and ambiguous-timeout recovery guidance;
- no acceptance of caller `confirm=true`, public approval mode, or public user.

### Regression and interoperability

- existing MCP standalone Customer Payment Entry remains unchanged;
- existing Sales Invoice payment creates a new receipt and is not confused with reconciliation;
- existing Task 53 Sales Order advance capability remains unchanged;
- native ERPNext Payment Reconciliation and Payment Entry tests remain green;
- focused mcp_erpnext unit/unittest workflow and REST/profile/registry tests;
- live `yob.localhost` prepare/confirm only after explicit environment approval, using a disposable or clearly identified test document and no production accounting mutation.

## 23. Acceptance criteria cross-check

| Task 54 concern | Audit conclusion |
|---|---|
| native capability exists | yes, through virtual Payment Reconciliation and `reconcile_against_document()` |
| current MCP overlap | existing receipt/payment tools are distinct; no existing exact reconciliation tool found |
| virtual document semantics | operational, non-persisted calculator/coordinator |
| discovery | submitted Customer PE, unallocated or SO-reference source, exact server filter required |
| invoice outstanding | Payment Ledger via `get_outstanding_invoices()` |
| exact mutation | native `reconcile_allocations()` -> `reconcile_against_document()` |
| submitted PE mutation | native update-after-submit save; no new submission |
| SO advance interoperability | supported by same native path; no invented same-SO restriction |
| standalone receipt interoperability | same submitted PE/reference/ledger model |
| separate advance account | native account discovery and reclassification path supported |
| Payment Terms | active term-specific allocation excluded from V1 |
| currencies/gain/loss | native exchange map and gain/loss path retained |
| India Compliance | regional discovery/allocation/PE hooks must remain in path |
| permissions | MCP must explicitly authorize because native internal save ignores permissions |
| sync/background | V1 synchronous; detect conflicting native background process |
| concurrency/idempotency | fingerprint plus native stale/current-state checks; no blind replay |
| reversal | native Unreconcile Payment/cancellation exists; excluded from V1 |
| candidate contract | exact PE, exact SI, positive amount, prepare/confirm |
| output minimization | bounded accounting result only |
| approval | shared ApprovalStore, server-bound, atomic single-use claim |
| REST/profile/errors/tests | Task 55 must update all fixed surfaces consistently |
| next task | implement only narrow Option A and its focused matrix |

## 24. Actions not performed and remaining unknowns

Not performed:

- no production source code or tests changed;
- no database reads or writes against a live site;
- no Payment Entry, Sales Invoice, Payment Reconciliation, Unreconcile Payment, or queue operation executed;
- no cache clear, migration, build, service restart, or deployment;
- no live role/permission, company setting, regional configuration, or worker-state verification;
- no claim that focused static evidence proves live MCP-to-ERPNext behavior.

The remaining live boundary is to verify, on the approved test site and authenticated identity, the exact permissions, installed regional hooks, company advance-account settings, transaction behavior, and post-confirm ledger/result shape. That verification belongs in Task 55 or a separately authorized runtime validation task, not in this audit.
