# Sales Invoice Existing-Document Capabilities Implementation Report

Date: 2026-09-11  
Task: 28 - Sales Invoice Existing-Document Capabilities and Action-Scoped Lifecycle Policy  
Project: `mcp_erpnext`  
Profile: `sales`

## A. Result

Implemented existing Sales Invoice capabilities for the Sales profile:

* exact get and bounded search;
* native permission-checked PDF rendering;
* approval-bound email preparation and confirmation with a native PDF attachment;
* approval-bound submit, cancel, and delete through the shared lifecycle service.

Generic Sales Invoice update and generic child-row add remain denied. Standalone
Sales Invoice creation remains deferred to Task 29. Task 27 Sales Order to
Sales Invoice conversion was not changed.

## B. Existing architecture inspected

Before changing code, the implementation inspected:

* `mcp_erpnext/services/common/read.py`, `contracts/read.py`, and `tools/read.py`;
* `mcp_erpnext/services/common/pdf.py`, `contracts/pdf.py`, and `tools/pdf.py`;
* `mcp_erpnext/services/common/email.py`, `contracts/email.py`, and `tools/email.py`;
* `mcp_erpnext/services/common/lifecycle.py`, `contracts/lifecycle.py`, and `tools/lifecycle.py`;
* `mcp_erpnext/profiles/sales.py`, `profiles/purchase.py`, `tools/__init__.py`, and `contracts/registry.py`;
* approval, runtime, observability, and the existing read/PDF/email/lifecycle,
  registration, profile, contract, and Task 27 tests;
* `docs/inspect/SALES_INVOICE_NATIVE_FLOW_AUDIT.md` and the Task 27 implementation report;
* installed ERPNext Sales Invoice/controller source and Frappe document/delete
  source, with India Compliance kept as an optional native hook boundary.

## C. Action-policy design

Previously lifecycle target authorization used one broad
`PROFILE_DOCTYPES` set for update, child add, submit, cancel, and delete.
Adding Sales Invoice there would have exposed generic update and the lifecycle
target gate for child-row operations.

The service now keeps that set as the legacy baseline and adds a deterministic
`LIFECYCLE_ACTION_DOCTYPES` mapping. Existing profile/doctypes retain their
previous target behavior. Sales Invoice is added only to these Sales actions:

| Profile | Doctype | update | child_add | submit | cancel | delete |
| --- | --- | --- | --- | --- | --- | --- |
| Sales | Sales Invoice | deny | deny | allow | allow | allow |
| Purchase | Sales Invoice | deny | deny | deny | deny | deny |

Each prepare path supplies its action to target loading, and confirmation
revalidates both the prepared action and action-scoped target policy before the
native mutation. Update and child-add therefore fail before approval creation,
document mutation, or child-table configuration.

## D. Files changed

* `mcp_erpnext/services/common/read.py`
* `mcp_erpnext/contracts/read.py`
* `mcp_erpnext/tools/read.py`
* `mcp_erpnext/services/common/pdf.py`
* `mcp_erpnext/contracts/pdf.py`
* `mcp_erpnext/services/common/email.py`
* `mcp_erpnext/contracts/email.py`
* `mcp_erpnext/services/common/lifecycle.py`
* `mcp_erpnext/contracts/registry.py`
* `mcp_erpnext/tests/test_read.py`
* `mcp_erpnext/tests/test_pdf.py`
* `mcp_erpnext/tests/test_email.py`
* `mcp_erpnext/tests/test_lifecycle.py`
* `mcp_erpnext/tests/test_tool_registration.py`
* `docs/TOOLS.md` (generated)
* this report

The common service files also contained pre-existing uncommitted formatting
edits in the starting worktree; those unrelated edits were preserved.

## E. Read/search implementation

The shared document definition now maps Sales Invoice to:

* party: `customer`;
* normalized public primary date: `posting_date` exposed as `transaction_date`;
* secondary date: `due_date`;
* child table: bounded `items` projection using the existing item fields.

Search date filters and ordering use the definition's primary field, so Sales
Invoice queries use `posting_date` while Quotation, Sales Order, and Purchase
Order continue using `transaction_date`. Frappe list reads retain
`ignore_permissions=False`. Sales-only `get_sales_invoice` and
`search_sales_invoices` wrappers were added; the Purchase profile cannot target
Sales Invoice.

## F. PDF implementation

Sales Invoice was added to the existing typed PDF contract and shared document
definition. The service continues to require both read and print permission
and calls native `frappe.get_print(..., as_pdf=True)` with the existing print
format, letterhead, language, and artifact behavior. No Sales Invoice-specific
renderer or India Compliance import was added.

## G. Email implementation

Sales Invoice now resolves its party as `Customer` through `invoice.customer`.
The existing document contact email, permission-safe Customer/Contact fallback,
associated-recipient restriction, ambiguous-recipient input result, native PDF
rendering, outgoing Email Account check, approval binding, stale document/PDF/
recipient checks, and Frappe queue path remain shared.

Confirmation queues one email through `frappe.sendmail`; `queued` is not
reported as delivered. Preparation does not send or queue an email.

## H. Lifecycle implementation

Sales Invoice submit, cancel, and delete use the existing generic prepare and
confirm tools. Prepare performs the shared exact-load, native state, permission,
and linked-document preflight. Confirmation claims the one-shot shared approval,
rechecks profile/action/document state, then calls native `doc.submit()`,
`doc.cancel()`, or the existing delete path. Submitted deletion retains the
existing cancel-then-delete plan. No cascade deletion was added.

No generic Sales Invoice update or child-add target was added. No separate
Sales Invoice lifecycle engine was created.

## I. Permission/security behavior

The implementation preserves the authenticated Frappe session identity and
normal permission checks. It adds no Administrator fallback, client-selected
user, direct SQL write, direct ledger write, permission bypass, approval-policy
argument, or secret. Cross-profile Sales Invoice access is rejected before
document lookup in the shared read/PDF/email services and before lifecycle
approval creation.

## J. India Compliance / ERPNext-only behavior

The installed ERPNext and Frappe source was inspected, including the native
Sales Invoice controller and Frappe deletion/document lifecycle seams. The
implementation does not import India Compliance at shared module load time or
duplicate GST, GL, stock, e-Invoice, e-Waybill, or cancellation logic. Native
print, submit, cancel, and delete hooks remain the final authority.

Unit tests verify the native call seams and optional-app-safe imports. Actual
India Compliance hook execution and ERPNext-only live behavior were not run.

## K. Tests run

* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest mcp_erpnext.tests.test_read mcp_erpnext.tests.test_pdf mcp_erpnext.tests.test_email mcp_erpnext.tests.test_lifecycle mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_tool_contracts mcp_erpnext.tests.test_sales_order_to_sales_invoice` — **73 passed**.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'` — **230 passed**.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m compileall -q mcp_erpnext` — passed.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py` — completed.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check` — passed.
* `git diff --check` — passed.

The full suite emitted the repository's existing Python 3.14/pydantic settings
warning, HTTP-authentication warnings, and the existing mocked India
Compliance Item diagnostic; all tests passed.

## L. Task 27 regression

`prepare_sales_order_to_sales_invoice` and
`confirm_sales_order_to_sales_invoice` were not modified. The focused Task 27
test remained green as part of the 73-test focused run and the 230-test full
suite.

## M. Live verification

* Read/search: **NOT VERIFIED LIVE**; verified with permission-aware unit doubles and installed source inspection.
* PDF: **NOT VERIFIED LIVE**; native print seam verified by unit tests.
* Email: **NOT VERIFIED LIVE**; queue and stale/approval behavior verified with unit doubles. No delivery claim.
* Submit: **NOT VERIFIED LIVE**; no Sales Invoice accounting write was performed.
* Cancel: **NOT VERIFIED LIVE**; no Sales Invoice cancellation was performed.
* Delete: **NOT VERIFIED LIVE**; no Sales Invoice deletion was performed.

No live database record, ledger entry, email delivery, e-Invoice, e-Waybill,
or destructive lifecycle operation was created or changed.

## N. Known limitations

Task 28 intentionally does not implement standalone Sales Invoice creation,
generic Sales Invoice update, generic item-row mutation, Delivery Note
conversion, POS or `update_stock=1` workflows, returns/Credit Notes, Debit
Notes, Payment Entries, advance allocation, Timesheet/Project billing,
inter-company/consolidated/recurring variants, or explicit e-Invoice/e-Waybill
tools.

## O. Exact next task

`Task 29 - Standalone Sales Invoice Creation Foundation`
