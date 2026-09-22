# Customer Advance and Payment Reconciliation Native Flow Audit

## 1. Executive conclusion

This audit confirms that ERPNext already provides the native business flow required for customer advances:

1. A submitted Sales Order can receive a Customer Payment Entry.
2. ERPNext treats a Sales Order reference as an advance rather than as invoice settlement.
3. The submitted Payment Entry updates the Sales Order advance state and creates the native accounting and payment-ledger records.
4. A later Sales Invoice can discover and allocate eligible customer advances through ERPNext's existing Accounts Controller and Payment Entry machinery.
5. Native Payment Reconciliation can reconcile unallocated or order-linked customer payments against submitted Sales Invoices.
6. Separate customer advance accounts, exchange rates, Payment Terms, partial billing, permissions, cancellation, and concurrency checks are already represented in ERPNext's native implementation.

The smallest safe future MCP surface is therefore a bounded, typed wrapper around native ERPNext operations. MCP should not calculate accounting effects, write Payment Entry Reference rows directly, implement a second reconciliation algorithm, or expose arbitrary query access.

Task 53 should implement only the first bounded capability:

- prepare and confirm a Customer Advance Payment Entry against a submitted Sales Order;
- preserve normal ERPNext permissions, validation, hooks, ledgers, and cancellation behavior;
- use the shared MCP approval flow for the confirm write;
- return a deterministic summary and continuation directive where the conversational contract requires one;
- leave Payment Reconciliation, multi-invoice allocation, and manual advance allocation for a later task.

Payment reconciliation is sufficiently different from advance creation that it should remain a separate capability. It should be designed only after its exact typed contract, allocation policy, permission behavior, and approval semantics are separately specified.

This report is inspection-only. No ERPNext production code, MCP Python code, DocType JSON, tests, profiles, registries, settings, site data, or database records were changed.

## 2. Scope and evidence boundary

The audited task requested a native-flow audit covering:

- Customer advance creation against a Sales Order;
- Payment Entry submit and cancel behavior;
- Sales Invoice advance discovery and allocation;
- separate advance account behavior;
- Payment Reconciliation;
- currencies and exchange rates;
- Payment Terms and partial billing;
- permissions and identity;
- approval and concurrency implications;
- optional regional application behavior;
- a future MCP capability recommendation.

The primary evidence is static source and test inspection in the local Bench:

- ERPNext checkout: apps/erpnext;
- Frappe checkout: apps/frappe;
- MCP app: apps/mcp_erpnext;
- installed optional application: apps/india_compliance.

Static evidence confirms implementation paths and unit-test intent. It does not prove behavior on the live yob.localhost site, current site permissions, current company defaults, Redis state, database records, browser behavior, queue execution, or an end-to-end MCP-to-ERPNext request.

## 3. Repository and installed-version context

The MCP app checkout is on branch master and has existing user changes:

- tracked modification: apps/mcp_erpnext/mcp_erpnext/remote_operations.py;
- pre-existing untracked task document: apps/mcp_erpnext/docs/tasks/audits/52_TASK_CUSTOMER_ADVANCE_AND_PAYMENT_RECONCILIATION_NATIVE_FLOW_AUDIT.md.

Those changes were preserved. The audit report is the only file added for this implementation.

The locally inspected application versions are:

- ERPNext 16.35.0;
- Frappe 16.34.0.

The source checkout is the relevant version for this audit. Version drift between this checkout and a deployed site remains a live-verification boundary.

## 4. Native Sales Order advance factory

### 4.1 Native entry point

ERPNext exposes the general Payment Entry factory:

- apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py
- function: get_payment_entry

The factory accepts a source document type and name, party amount, bank account, bank amount, party type, payment type, reference date, and Payment Request context.

For a Customer Sales Order advance, the important source input is:

- source doctype: Sales Order;
- source name: submitted Sales Order name;
- party type: Customer;
- payment type: Receive.

The factory creates an unsaved Payment Entry document. It does not submit or insert the document itself.

### 4.2 Permission behavior

get_payment_entry checks Payment Entry create permission before constructing the result. It also loads the source document through Frappe and checks source-document permission.

This means a future MCP wrapper should not bypass the factory with raw document construction. The native factory is already the correct seam for permission-aware preparation.

The eventual confirm operation must still use normal Payment Entry insert/submit behavior. Factory permission checks do not replace submit-time permission checks or document validation.

### 4.3 Source document state

The factory requires the source document to be in a state suitable for payment generation. The source document is loaded and its totals and outstanding state are used to derive amounts.

A future Customer Advance capability should require a submitted Sales Order explicitly. This is consistent with ERPNext's submitted-reference validation and prevents an advance from being attached to an unsubmitted source order.

The final confirm path must re-read the Sales Order. A prepared preview must not be treated as a permanent snapshot of current outstanding or advance state.

### 4.4 Amount and payment direction

For a Customer advance:

- party type is Customer;
- payment type is Receive;
- party amount is positive;
- paid amount and received amount are derived through the native currency and exchange-rate helpers;
- the Payment Entry reference row points to the Sales Order.

The native factory sets grand total and outstanding amount for the source document, then fills Payment Entry amounts using native currency handling. A wrapper should accept a bounded positive amount and let native validation decide whether the resulting allocation is valid.

The wrapper should reject obviously invalid input early, such as:

- missing amount;
- zero amount;
- negative amount;
- non-finite amount;
- more than one mutually exclusive bank or Mode of Payment input.

Early rejection is only input hygiene. Native ERPNext validation remains authoritative.

### 4.5 Reference-row behavior

For the simple source-document branch, get_payment_entry appends a Payment Entry Reference row containing the source doctype, source name, and allocated amount.

Sales Order is a valid Customer reference doctype in Payment Entry's reference validation. On submit, the Payment Entry is therefore processed as a Sales Order advance rather than as ordinary invoice settlement.

The reference row must be created using the native factory and not by accepting arbitrary child-row fields from the client.

### 4.6 Payment Terms branch

The factory has a Payment Terms branch. When a source document contains Payment Terms, it can construct reference rows from the source term schedule rather than only appending one undifferentiated reference.

A future MCP wrapper should not reproduce this branch. It should pass the source document to the native factory and preserve the result. If the task's contract intentionally excludes Payment Terms, the service should reject unsupported cases explicitly rather than silently collapsing the schedule.

## 5. Native Payment Entry validation, submit, and cancel behavior

### 5.1 Validation chain

Payment Entry.validate performs the relevant native preparation and validation chain, including:

- party-account setup;
- missing-value derivation;
- liability-account setup;
- missing reference details;
- exchange-rate setup;
- mandatory-field validation;
- reference validation;
- allocated amount validation;
- amount and currency validation;
- unallocated amount calculation.

Relevant source:

- apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py
- PaymentEntry.validate
- PaymentEntry.set_missing_values
- PaymentEntry.set_missing_ref_details
- PaymentEntry.validate_reference_documents
- PaymentEntry.validate_allocated_amount
- PaymentEntry.set_unallocated_amount

This chain is the business boundary for a Customer Advance capability.

### 5.2 Submitted reference validation

Payment Entry reference validation checks that:

- the referenced document exists;
- the party matches;
- the reference doctype is permitted for the party type;
- the reference document is submitted;
- the reference amount is valid.

This protects against a stale preview being submitted after the Sales Order or Customer changed.

### 5.3 Separate advance account selection

PaymentEntry.set_liability_account reads the Company setting:

- book_advance_payments_in_separate_party_account.

When enabled, it resolves the Customer's default advance-received account and uses that account for the advance side of the transaction. When disabled, it retains the normal party account behavior.

The native account resolver is in:

- apps/erpnext/erpnext/accounts/party.py
- get_party_account
- get_party_advance_account

A future MCP service should not accept an arbitrary debit or credit account as a substitute for this resolution.

### 5.4 Submit effects

PaymentEntry.on_submit:

- creates native GL entries;
- updates outstanding and advance state;
- creates or updates native payment-ledger records;
- runs normal document hooks.

Payment Entry's accounting path recognizes Sales Order references as advances. The Payment Entry Reference row is not merely informational: it participates in the accounting and advance-ledger flow.

### 5.5 Cancel effects

PaymentEntry.on_cancel reverses native ledger effects and delinks advance references. The resulting Sales Order advance state is recalculated by native ERPNext code.

A future MCP capability should expose cancellation only through the existing generic lifecycle rules and should not implement a special advance reversal algorithm.

## 6. Evidence from native tests for advance submit and cancel

The ERPNext Payment Entry tests cover the basic Sales Order advance lifecycle:

- create a Sales Order;
- create a Payment Entry against the order;
- insert and submit it;
- verify the order advance state;
- cancel the Payment Entry;
- verify the advance state returns to the expected value.

Relevant test file:

- apps/erpnext/erpnext/accounts/doctype/payment_entry/test_payment_entry.py

The same test module covers foreign-currency order advances. The Payment Entry uses source and received amounts with an exchange rate, and cancellation restores the native advance state.

The tests also cover partial advance allocation followed by Sales Invoice creation and allocation. This establishes that the native model is not limited to full-order advances.

These are source-level and unit-test signals. They do not establish that the live site currently has the required Company accounts, permissions, currencies, or optional hooks configured.

## 7. Sales Invoice advance discovery and allocation

### 7.1 Sales Invoice validation and submit

Sales Invoice uses Accounts Controller validation and clears or calculates advance-related state during validation.

On submit, Sales Invoice calls the native journal/document reconciliation path after normal GL processing. The path updates references and outstanding values through ERPNext's accounting utilities.

Relevant source:

- apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py
- SalesInvoice.validate
- SalesInvoice.on_submit
- SalesInvoice.on_cancel

### 7.2 Automatic advance discovery

Accounts Controller provides the native advance discovery flow:

- get_advance_entries;
- get_advance_payment_entries_for_regional;
- get_advance_payment_entries;
- set_advances.

When automatic advance allocation is enabled, the controller finds eligible submitted Payment Entries, clears/rebuilds the invoice advance child rows, and appends native references containing:

- reference type;
- reference name;
- reference row;
- remarks;
- advance amount;
- allocated amount;
- exchange-rate information;
- difference date;
- account.

This is the correct native seam for Sales Invoice advance allocation.

### 7.3 Eligible advance sources

The common native query can include:

- Payment Entries linked to the Sales Order;
- submitted Customer Payment Entries with unallocated amount;
- separate advance-account entries when the Company configuration requires them.

The query is party-, company-, account-, payment-type-, and submission-state-aware. It is not a generic “find all payments” query.

### 7.4 Sales Order mapping behavior

The Sales Order to Sales Invoice mapper calls target.set_advances when automatic allocation is enabled. This lets the standard document mapping flow carry eligible advances into the invoice.

A future MCP wrapper should preserve this behavior by using native document mapping or native controller methods, rather than assembling Sales Invoice advance rows itself.

### 7.5 Ledger and outstanding updates

ERPNext's payment-ledger utilities create advance payment ledger entries for GL entries that represent advances. Reconciliation utilities update references, rebuild relevant payment ledgers, and update voucher outstanding values.

For Sales Orders, update_voucher_outstanding calls native Sales Order advance recalculation. For Sales Invoices, outstanding values are maintained through Payment Ledger and related accounting logic.

## 8. Interoperability with Task 50 standalone Customer Payment Entry

Task 50 already established a bounded standalone Customer Payment Entry capability in MCP. Its design is compatible with the native advance flow when the Payment Entry is created without a specific Sales Order reference:

- Customer and Company are explicit;
- amount is positive and finite;
- exactly one of Mode of Payment or Bank Account is selected;
- raw accounting accounts are not exposed as public input;
- Payment Entry native validation resolves party account, currency, and defaults;
- confirm rebuilds stale prepared state before insertion/submission.

The distinction is important:

- a Sales Order advance is explicitly linked to a submitted order;
- a standalone Customer receipt is initially unallocated or may be allocated later by native advance/reconciliation behavior.

Task 53 should reuse Task 50's approval, identity, stale-preview, error, and response patterns where applicable, but should use the Payment Entry factory with an explicit Sales Order reference. It should not turn the standalone payment tool into an implicit reconciliation tool.

Task 50's focused tests provide static contract evidence. Live account resolution, site permissions, Redis-backed approval behavior, and full database insertion/submission remain live verification boundaries.

## 9. Separate customer advance account behavior

ERPNext supports a Company-level setting to book advances in a separate party account. The native behavior is distributed across:

- Company fields;
- party account resolution;
- Payment Entry liability-account setup;
- advance payment queries;
- Payment Reconciliation queries;
- Payment Ledger and Advance Payment Ledger Entry creation.

When the setting is enabled:

1. Payment Entry resolves the Customer's advance account.
2. The advance account is used in the accounting entry.
3. Later queries include the advance account where appropriate.
4. Reconciliation can consider payments held in the separate account.
5. Invoice allocation can move the economic effect through native reconciliation and ledger updates.

Payment Entry's outstanding-reference query explicitly handles the separate-account case by resolving the normal and advance accounts and adjusting the query path.

The separate-account option must therefore be treated as a native configuration branch, not as a task-local flag. Task 53 should not expose it as a public override.

## 10. Native Payment Reconciliation architecture

### 10.1 Payment Reconciliation is a virtual operational document

Payment Reconciliation is implemented as a non-persistent operational DocType:

- load_from_db builds an in-memory document;
- save is a no-op;
- db_insert, db_update, and db_delete are no-ops.

This is materially different from Payment Entry. A future MCP tool must not model a Payment Reconciliation preview as if it were a persistent approval document.

Relevant source:

- apps/erpnext/erpnext/accounts/doctype/payment_reconciliation/payment_reconciliation.py

### 10.2 Payment and invoice discovery

Payment Reconciliation retrieves:

- payment entries through regional advance-payment query hooks;
- invoice entries through receivable and default advance accounts;
- submitted, party-matched, company-matched records;
- unallocated and order-linked payments according to the selected account and party filters.

The DocType includes a default advance account field and permission metadata for Accounts Manager and Accounts User.

### 10.3 Allocation and reconciliation

The native sequence is:

1. load eligible payments;
2. load eligible invoices;
3. calculate difference;
4. allocate rows;
5. validate allocation;
6. call reconcile_against_document;
7. refresh the result.

The reconciliation utility updates submitted Payment Entry references, handles split allocations where required, refreshes native amounts, rebuilds payment-ledger state, and updates invoice outstanding.

This is not equivalent to simply setting allocated_amount on a child row.

### 10.4 Background process

Process Payment Reconciliation provides a background implementation for larger allocations. It checks whether another reconciliation process is already running for the same company, party, and account, and can pause or resume work.

This reinforces that reconciliation is a separate operational capability with concurrency and queue semantics.

## 11. Reconciliation validation and mutation chain

### 11.1 Validation

Native allocation validation checks at least:

- allocated amount is not greater than the payment amount available for reconciliation;
- allocation is not greater than the invoice outstanding amount;
- the source payment and target document remain valid;
- current submitted data has not changed in a conflicting way.

Advance-specific checks verify:

- Payment Entry is submitted;
- party matches;
- current unallocated or reference amount is sufficient;
- the reference has not been modified incompatibly.

### 11.2 Mutation

The native reconcile_against_document path:

- groups reconciliation rows;
- checks source records for modification;
- updates submitted Payment Entry references;
- can append or split reference rows;
- refreshes native amounts and exchange-rate fields;
- updates Payment Entry internal state;
- rebuilds payment-ledger entries;
- updates voucher outstanding amounts.

This path may mutate a submitted Payment Entry through ERPNext's internal reconciliation mechanism. It must not be replaced by a generic MCP child-row update tool.

### 11.3 Concurrency

Payment Reconciliation checks for a running process. The document-level validation also re-reads current values before mutation.

A future MCP reconciliation capability needs:

- approval bound to the user, site, action, and exact payload;
- a current-state revalidation at confirm time;
- deterministic stale/conflict errors;
- protection against duplicate confirmation;
- handling for a reconciliation process already running;
- a clear policy for background versus synchronous execution.

Task 53 should avoid this scope and implement only the single Payment Entry creation path.

## 12. Currency and exchange-rate behavior

The native flow has at least three related monetary concepts:

- party amount;
- bank or company amount;
- reference/document amount.

Payment Entry derives these through party-account currency, bank-account currency, source-document currency, and exchange rates. The factory sets party account and currency fields, grand total, outstanding amount, and paid/received amounts using native helpers.

Advance and reconciliation rows retain exchange-rate information. Payment Entry and reconciliation utilities refresh these values when current submitted data is used.

A future MCP contract should:

- accept an amount in an explicitly documented currency context;
- return the resolved account and currency summary in prepare output;
- avoid allowing arbitrary stored exchange rates unless the native API requires them;
- revalidate the rate and amount at confirm time;
- expose differences or rounding as native validation results.

The wrapper must not calculate gains, losses, or exchange differences. ERPNext's reconciliation utility includes a native gain/loss journal path where required.

The local source and tests cover foreign-currency Sales Order advances. Live verification is still required before claiming site-specific currency configuration or account setup.

## 13. Payment Terms and partial billing

Payment Terms affect how Payment Entry references may be generated and how a later invoice may be allocated.

The native factory includes a Payment Terms branch. Accounts Controller and Sales Invoice mapping also support native advance allocation across partial billing scenarios.

Observed native behavior supports:

- partial Sales Order advances;
- partial Sales Invoice billing;
- later allocation of the remaining advance;
- multiple payment entries;
- cancellation and recalculation.

Task 53 should choose one of these contract positions explicitly:

Recommended:

- support a submitted Sales Order and a single positive advance amount;
- let native factory and validation preserve Payment Terms behavior;
- return an explicit unsupported/needs-review result only where native preparation cannot produce a deterministic single Payment Entry.

Not recommended:

- manually expand Payment Term rows in MCP;
- silently convert a term-based schedule into one arbitrary amount;
- expose client-controlled reference child rows.

If a future implementation needs Payment Terms-specific user choices, those choices should be added as a typed capability contract after a separate audit.

## 14. Permissions and identity

### 14.1 ERPNext permissions

The native paths enforce permissions at multiple points:

- source-document read permission;
- Payment Entry create permission;
- party and reference read permission;
- Accounts Controller and Payment Reconciliation permissions;
- submit and cancel permissions;
- company/account visibility and validation;
- optional regional application hooks.

The future MCP service must invoke these native paths under the resolved ERPNext user identity.

### 14.2 MCP transport identity

Current MCP conventions distinguish transport/process identity from ERPNext user identity:

- stdio resolves ERPNext identity through MCP_FRAPPE_USER;
- Streamable HTTP resolves X-MCP-User-Email;
- HTTP does not silently fall back to the stdio identity variable;
- Linux process ownership is not the ERPNext user.

Task 53 must preserve that distinction. The service should not accept a public user field that overrides authenticated transport identity.

### 14.3 Permission failure behavior

Permission failures must remain distinguishable from:

- missing source document;
- invalid amount;
- stale prepared state;
- account configuration failure;
- native validation failure;
- approval failure.

The MCP error should be bounded and user-safe while preserving the existing error-code and reference conventions.

## 15. Approval, stale state, and confirmation

The shared MCP approval contract requires server-authoritative confirmation. A client-supplied confirm=true is not approval by itself.

Task 53 should use the existing shared pattern:

1. prepare a typed proposal;
2. bind the proposal to site, authenticated ERPNext user, operation, and canonical payload;
3. return native-derived preview information;
4. require the shared confirm-write approval guard;
5. rebuild or re-read the Payment Entry at confirmation;
6. insert and submit through normal Frappe lifecycle;
7. reject stale or changed source state deterministically.

The approval store uses shared Frappe-native persistence and concurrency-safe claim behavior. A tool-specific in-memory approval map or approval-mode branch must not be introduced.

The preparation output should include enough information to explain what will happen without leaking unnecessary accounting data:

- source Sales Order;
- Customer;
- Company;
- amount and currency;
- payment direction;
- resolved payment method summary;
- whether a separate advance account branch was detected;
- native warnings or required continuation;
- a proposal identifier/reference.

The confirm payload should not permit changing the source document, Customer, amount, account, or allocation after approval binding.

## 16. Optional application and regional behavior

The installed india_compliance application contributes hooks and overrides around:

- Payment Entry validation;
- Payment Entry submit;
- Payment Entry update-after-submit;
- Payment Entry cancellation;
- Sales Invoice validation/submit/cancel;
- regional advance payment queries;
- Payment Reconciliation tax allocation;
- GST reversal behavior.

ERPNext exposes regional wrappers such as get_advance_payment_entries_for_regional. A future MCP service should call native document/controller methods and allow installed hooks to run, rather than importing only the base ERPNext helper and bypassing regional behavior.

The exact live effect depends on site installation, company configuration, GST registration, and document data. Static source confirms the extension points; it does not prove which branches execute on yob.localhost.

## 17. Public MCP capability options

### Option A: Customer advance against Sales Order

Recommended for Task 53.

Bounded input:

- submitted Sales Order name;
- positive advance amount;
- exactly one supported payment-method selector;
- optional bounded reference date if native behavior requires it;
- no arbitrary accounts;
- no arbitrary child rows.

Native path:

- load and permission-check Sales Order;
- call Payment Entry.get_payment_entry;
- apply only typed, bounded payment-method fields;
- run native validation;
- prepare preview;
- confirm through shared approval;
- insert and submit Payment Entry normally.

Result:

- Payment Entry name;
- Sales Order name;
- Customer and Company;
- paid/received amounts and currencies;
- native unallocated amount;
- native advance summary;
- continuation directive if required.

### Option B: Standalone Customer receipt

Already covered by Task 50's scope and should remain a separate capability. It creates a receipt that may be unallocated or later applied by native invoice/advance flows.

### Option C: Reconcile customer advance/payment against invoice

Defer to a separate task.

Required design work includes:

- whether one payment to one invoice is supported first;
- whether multiple payments or invoices are supported;
- whether order-linked advances are included;
- how separate advance accounts are selected;
- how exchange differences are reported;
- synchronous versus background execution;
- approval payload and stale conflict policy;
- idempotency and retry behavior;
- permission model;
- whether the result is a virtual preview or a persistent reconciliation record.

Option C should not be hidden behind Option A.

## 18. Data minimization and typed contract boundaries

The public contract should not expose:

- arbitrary SQL filters;
- arbitrary Payment Entry Reference rows;
- debit or credit account overrides;
- arbitrary company or party-account overrides;
- internal Payment Ledger Entry mutation;
- direct GL Entry creation;
- a generic “reconcile anything” payload;
- client-controlled native flags that bypass validation.

The public read projection should be limited to the fields needed for:

- source identification;
- customer and company;
- amount/currency;
- payment method summary;
- native status;
- resulting document reference;
- bounded warnings and error references.

The existing field-aware MCP read pattern should be followed. A fields argument, where available, must remain a projection allowlist and not become arbitrary query access.

## 19. Error model

The future capability should preserve the existing MCP distinction between typed input errors, ERPNext permission failures, native validation failures, approval failures, stale state, and unexpected internal failures.

Expected error categories include:

- source Sales Order does not exist;
- source Sales Order is not submitted;
- source Sales Order is not readable;
- Payment Entry creation is not permitted;
- Customer or Company mismatch;
- invalid or non-positive amount;
- unsupported payment method combination;
- missing account or currency configuration;
- amount exceeds native allowable amount;
- Payment Terms require a separate user decision;
- prepared proposal is stale;
- approval is missing, expired, already used, or bound to another identity;
- native submit or hook validation failed;
- reconciliation process is already running, for future reconciliation tools.

The service should log a bounded error reference and preserve internal traceability without returning stack traces, SQL, credentials, or raw sensitive configuration to the caller.

## 20. Direct, REST, and profile parity

The existing MCP Accounts profile is intentionally narrow. It contains Payment Entry lifecycle and bounded Accounts operations; it does not currently expose a Customer Advance or Payment Reconciliation capability.

The current REST implementation is fixed-operation and loopback-HTTP-oriented in development. A future Task 53 addition must update all required surfaces together if it becomes an actual public tool:

- typed contract;
- service implementation;
- profile/catalog/registry;
- REST dispatch if exposed;
- focused tests;
- tool documentation;
- command or configuration documentation only if an actual reusable command changes.

This audit itself does not change any of those surfaces.

The public capability should be DocType-specific and should preserve the distinction between:

- prepare;
- shared confirm-write;
- normal Frappe insert/submit;
- generic lifecycle operations such as cancel.

## 21. Future implementation test matrix

Task 53 should add focused tests for at least the following.

### Contract and validation

- valid submitted Customer Sales Order;
- missing Sales Order;
- draft Sales Order;
- cancelled or closed Sales Order;
- zero, negative, non-finite, and excessive amount;
- wrong party type;
- unsupported payment-method combination;
- missing required payment method;
- invalid reference-date input if exposed;
- deterministic typed response shape.

### Native preparation

- native factory receives the correct source doctype and name;
- Payment Entry is unsaved during prepare;
- Sales Order reference row is present;
- Customer, Company, payment type, and currencies are native-derived;
- Payment Terms branch is preserved or explicitly rejected according to contract;
- separate advance account is reflected in native preview, not client-selected.

### Confirm and lifecycle

- approval is bound to exact source, user, site, operation, and payload;
- missing approval fails;
- wrong-user approval fails;
- expired or already-used approval fails;
- confirm re-reads the Sales Order;
- changed Sales Order or conflicting payment state produces stale/native validation failure;
- successful confirm inserts and submits Payment Entry;
- normal submit hooks execute;
- cancellation uses existing lifecycle behavior and restores native advance state.

### Accounting and allocation

- Sales Order advance is reflected in native advance state;
- partial advance is preserved;
- later Sales Invoice can discover eligible advance;
- standalone Task 50 receipt remains interoperable;
- separate advance account branch works when enabled;
- ordinary party-account branch works when disabled;
- foreign-currency amount and exchange rate remain native-derived;
- native ledger and outstanding values are not manually written by MCP.

### Permissions and identity

- source read permission failure;
- Payment Entry create permission failure;
- submit permission failure;
- transport identity maps to the expected ERPNext user;
- HTTP header identity does not fall back to stdio configuration;
- user cannot override authenticated identity.

### Live verification, separately

After implementation and with explicit permission, live verification should be performed on yob.localhost using a safe test company/customer/order and normal permissions. It should separately record:

- app and version state;
- Company advance-account setting;
- account and currency defaults;
- permissions;
- Redis/approval behavior;
- document names and resulting ledger state;
- cancellation behavior;
- optional app hooks;
- queue behavior if any.

Focused unit tests cannot establish those live facts.

## 22. Risks and deferred questions

### 22.1 Risks for Task 53

- Site-specific account defaults may prevent native preparation or submission.
- Payment Terms may produce a reference schedule that does not fit a single-amount public contract.
- Regional hooks may add validation or accounting effects.
- A prepared proposal can become stale when another user creates or cancels a payment.
- Separate advance-account configuration changes which records are eligible for later allocation.
- Foreign-currency rounding and exchange differences can change between prepare and confirm.
- Generic lifecycle permissions may not exactly match every native document permission branch.
- Existing MCP REST or profile registration may be incomplete if a new tool is added without updating all catalogs.

### 22.2 Deferred to reconciliation task

- multi-payment to one invoice;
- one payment to multiple invoices;
- multiple advances across multiple Sales Orders;
- automatic allocation policy;
- manual allocation selection;
- Payment Reconciliation virtual-document semantics;
- background reconciliation;
- reconciliation idempotency;
- gain/loss treatment in the public result;
- concurrent reconciliation conflict UX;
- tax and regional reconciliation behavior;
- cancellation or reversal of a reconciliation after submitted reference mutation.

## 23. Exact Task 53 recommendation

Task 53 should be titled:

Sales Order Customer Advance Payment V1 Implementation

It should implement one narrow native flow:

1. Resolve the authenticated ERPNext user and site.
2. Load and permission-check a submitted Sales Order.
3. Validate a positive, finite advance amount and bounded payment-method input.
4. Call ERPNext's native Payment Entry factory for the Sales Order.
5. Run native validation and produce a typed prepare result.
6. Require the shared CONFIRM_WRITE approval guard.
7. Re-read/rebuild the native Payment Entry at confirm time.
8. Insert and submit it through normal Frappe lifecycle.
9. Return the resulting Payment Entry, Sales Order, amount/currency summary, and native status.
10. Keep cancellation on the existing lifecycle path.
11. Add focused tests for permissions, stale state, approval binding, submit/cancel, separate advance account, partial amount, foreign currency, and interoperability with later invoice allocation.
12. Update registry/profile/docs only as part of the actual Task 53 implementation.

Task 53 must explicitly exclude:

- Payment Reconciliation;
- multi-invoice allocation;
- direct Payment Entry Reference mutation;
- direct GL or Payment Ledger writes;
- arbitrary account selection;
- arbitrary child-row input;
- generic accounting queries;
- client-side approval bypass.

A later reconciliation task should introduce a separate typed capability only after its allocation, concurrency, accounting-difference, regional-hook, and background-processing semantics are specified and tested.

## Final audit disposition

The native ERPNext flow is sufficient for a safe Customer Advance Payment Entry capability. No new native accounting implementation is required.

The recommended implementation boundary is:

MCP typed prepare/confirm and approval
-> native Payment Entry factory and validation
-> normal Frappe insert/submit
-> native GL, Payment Ledger, advance state, hooks, and permissions

Payment Reconciliation is a separate native operational flow and should remain outside Task 53.

No production code or runtime data was changed by this audit implementation.
