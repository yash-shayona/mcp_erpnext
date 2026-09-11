# Standalone Sales Invoice Creation Implementation Report

Date: 2026-09-11  
Task: 29 - Standalone Sales Invoice Creation Foundation  
Project: `mcp_erpnext`  
Profile: `sales`

## 1. Exact result

Implemented exactly two new public business tools:

```text
prepare_sales_invoice
confirm_sales_invoice
```

They are registered only in the Sales profile. The workflow creates a genuine
direct Draft Sales Invoice from a Customer and bounded Item rows. It does not
create or convert a Sales Order or Delivery Note implicitly.

## 2. Existing architecture inspected

The implementation inspected and reused:

* typed Quotation contracts and wrappers;
* Sales Order creation and its Customer/Item resolver usage;
* Task 27 `sales_order_to_sales_invoice` service, contract, wrapper, approval,
  projection, and stale-confirmation pattern;
* shared `ApprovalStore.claim_for_confirm_write()`;
* `InteractionDirective` input and approval directives;
* permission-aware Customer and sales-Item resolver configuration;
* Sales profile registration, contract registry, tool metadata, and generated
  catalog flow;
* existing profile, registration, contract, and conversion regression tests.

Task 28 shared Sales Invoice read, PDF, email, and action-scoped lifecycle
services were not changed.

## 3. Installed source inspected

The installed source inspected was:

* `apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py`;
* `apps/erpnext/erpnext/controllers/selling_controller.py`;
* `apps/erpnext/erpnext/controllers/accounts_controller.py`;
* `apps/frappe/frappe/model/document.py`.

The direct-invoice policy is implemented by the installed
`SalesInvoice.so_dn_required()` method. It reads `Selling Settings.so_required`
and `dn_required`, then checks the corresponding Customer exceptions. The
installed `SalesInvoice.set_missing_values()` resolves the party account and
due date before delegating to Selling/Accounts controller defaults. Native
tax calculation is delegated through `calculate_taxes_and_totals()`.

Frappe `Document.insert()` was confirmed to perform normal create permission,
link, mandatory, hook, and validation processing.

## 4. Files changed for Task 29

* `mcp_erpnext/contracts/selling/sales_invoice.py`
* `mcp_erpnext/services/selling/sales_invoice.py`
* `mcp_erpnext/tools/selling/sales_invoice.py`
* `mcp_erpnext/contracts/registry.py`
* `mcp_erpnext/tools/__init__.py`
* `mcp_erpnext/tests/test_sales_invoice.py`
* `mcp_erpnext/tests/test_profiles.py`
* `mcp_erpnext/tests/test_tool_registration.py`
* `mcp_erpnext/tests/test_tool_contracts.py`
* `docs/TOOLS.md` (generated)
* this report

The worktree already contained unrelated Task 28 changes and Task 28/29 task
documents. Those changes were preserved.

## 5. Public contracts and input boundary

`SalesInvoicePrepareInput` accepts:

* a resolved `CustomerReference`;
* a non-empty list of resolved `ItemReference` rows;
* positive `qty` per row;
* optional non-negative `rate` per row;
* optional `company`, `posting_date`, `selling_price_list`,
  `customer_address`, `shipping_address_name`, and `contact_person`.

The public Pydantic models use `extra="forbid"`. No arbitrary `extra_fields`,
calculated totals, accounting overrides, source-lineage fields, payment rows,
stock/POS/return/debit flags, GST/e-Invoice fields, or approval-policy fields
are exposed.

The preview is bounded to effective header values, dates, currency, price list,
contact/address links, debit account, item commercial values, taxes, payment
schedule, and totals. The result explicitly identifies `Sales Invoice` and
`docstatus=0`.

## 6. Customer and Item resolver behavior

The service revalidates the exact selected Customer through the existing
permission-aware resolver filters (`disabled != 1`) and revalidates each Item
through the existing sales-item filters (`disabled != 1`, `is_sales_item=1`).
The checks use `ignore_permissions=False`. Missing or no-longer-permitted
references produce safe errors during preparation and stale confirmation during
confirmation. The conversational client remains responsible for calling the
existing resolver/selection tools before passing typed references.

## 7. Rate policy

The V1 contract supports the same bounded explicit `rate` override already
used by Quotation. If omitted, ERPNext item and price-list logic supplies the
rate. If supplied, it is stored in the normalized approval request and passed
only as the item row `rate`; native defaulting/calculation produces the
effective preview. The effective value, amount, and totals are what the user
reviews and what the fingerprint binds. `base_rate`, `amount`, `net_amount`,
and calculated totals are not inputs.

## 8. Native defaulting and calculation sequence

The service uses this unsaved native sequence:

```text
frappe.new_doc("Sales Invoice")
  -> bounded Customer/company/date/link values
  -> fixed V1 flags: non-POS, non-return, non-debit-note, update_stock=0
  -> bounded Sales Invoice Item rows
  -> SalesInvoice.set_missing_values()
  -> calculate_taxes_and_totals()
  -> bounded preview and fingerprint
```

Preparation does not call `run_method("validate")`. Final native validation is
deferred to `Document.insert()` during confirmation because the installed
Sales Invoice validation path can mutate unsaved child state and perform
additional reference/bundle operations.

## 9. Sales Order / Delivery Note prerequisite policy

Before approval, the service performs a read-only equivalent of the installed
`SalesInvoice.so_dn_required()` decision for a normal V1 invoice. It reads:

* `Selling Settings.so_required`;
* `Selling Settings.dn_required`;
* `Customer.so_required`;
* `Customer.dn_required`.

If a prerequisite is required and the Customer is not exempt, preparation
returns a structured `blocked` result with the required prerequisite. Both
Sales Order and Delivery Note requirements can be reported together. The
service never creates either prerequisite and never uses POS, return, or debit
flags to bypass the policy. Confirmation repeats the policy check and returns
the current prerequisite result without inserting when configuration changed.

## 10. Prepare side-effect analysis

Preparation only creates an in-memory Frappe document. It does not call
`insert`, `submit`, `db_set`, SQL writes, commit, email, payment creation,
source-document creation, GL/stock-ledger writes, compliance API calls, or
compliance generation jobs. The only native methods used before approval are
the audited unsaved defaulting and calculation methods described above.

## 11. Approval and stale confirmation

The existing process-local approval store is reused with action
`create_sales_invoice`. Its payload contains only the normalized bounded
request, direct-invoice policy state, bounded effective preview, and a SHA-256
fingerprint over those values. The approval remains bound by the shared store
to site, authenticated user, action, TTL, and one-shot consumption.

Confirmation first claims the shared approval, then rechecks create permission,
revalidates Customer and Items, re-reads policy, rebuilds a fresh unsaved
Sales Invoice, reruns native defaults/calculation, and compares the new
fingerprint. Material changes to masters, policy, price/default values,
addresses, taxes, accounts, payment schedule, or totals therefore fail with
`STALE_CONFIRMATION` or return the current prerequisite block. A consumed or
failed token must be prepared again.

## 12. Final insert behavior

Only confirmation inserts the freshly rebuilt target using:

```python
target.insert(
    ignore_permissions=False,
    ignore_links=False,
    ignore_mandatory=False,
)
frappe.db.commit()
```

Rollback is called for permission, native validation, and other insert errors.
The service never calls `submit()` and returns only a Draft result with
`docstatus=0`. No direct GL, stock, payment, email, source-document, or
cascade action is introduced.

## 13. Permissions and security

The authenticated Frappe user must have Sales Invoice create permission.
Company, Price List, Address, and Contact inputs are checked through normal
permission-aware list reads. Final Frappe Link validation and native hooks
remain active. There is no Administrator fallback, user override, permission
bypass, direct SQL, public approval-mode argument, or secret handling.

## 14. India Compliance and ERPNext-only behavior

The standalone module has no hard India Compliance import. It relies on
standard ERPNext metadata/controller behavior and permits installed native
hooks to run during final insert. No GST, HSN, e-Invoice, or E-Waybill
algorithm was copied into MCP, and no compliance external call or enqueue is
made during Draft preparation.

## 15. Tests and commands run

Observed results:

* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest mcp_erpnext.tests.test_sales_invoice mcp_erpnext.tests.test_tool_registration mcp_erpnext.tests.test_profiles mcp_erpnext.tests.test_tool_contracts` — **20 passed**.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'` — **235 passed**.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m compileall -q mcp_erpnext` — passed.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py` — completed.
* `PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check` — passed.
* `git diff --check` — passed.

The test runs emitted the repository's existing Python 3.14/pydantic settings
warning, HTTP authentication warnings, and the existing mocked India
Compliance Item diagnostic. The suites still passed.

## 16. Live verification

**NOT VERIFIED LIVE.** No Sales Invoice, Sales Order, Delivery Note, ledger
entry, Payment Entry, email, e-Invoice, or E-Waybill was created or changed.
Actual ERPNext native insert hooks, site settings, accounting defaults,
database permissions, and installed India Compliance execution remain outside
the unit/static verification performed here.

## 17. Limitations retained

The following remain intentionally separate capabilities:

* Sales Invoice draft update or item-row mutation;
* Delivery Note to Sales Invoice conversion;
* `update_stock=1` and POS invoice workflows;
* Credit Note/Return and Debit Note workflows;
* Payment Entry, advances, and payment allocation;
* Timesheet, Project, inter-company, consolidated, recurring, or subscription
  billing;
* explicit e-Invoice or E-Waybill operational tools.

## 18. Regression and next-task recommendation

Task 27 conversion behavior and Task 28 existing Sales Invoice
read/PDF/email/action-scoped lifecycle behavior were not weakened; the full
235-test suite remained green. Generic Sales Invoice update and child-add
remain denied, and the Purchase profile does not register the new tools.

Based on the implemented boundary and the absence of live payment evidence,
the next recommended task is a separately audited **Payment Entry / Accounts
profile foundation**. It is not implemented by Task 29.
