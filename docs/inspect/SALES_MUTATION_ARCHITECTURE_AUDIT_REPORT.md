# Sales Mutation Architecture Audit Report

## 1. Executive summary

**Result: COMPLETE for architecture review; no production or business code was changed.**

The current Sales profile contains five business DocTypes in its mutation
surface: Customer, Item, Quotation, Sales Order, and Sales Invoice. It exposes:

- typed, DocType-specific prepare/confirm creation for all five DocTypes;
- typed, DocType-specific native conversions for Quotation -> Sales Order and
  Sales Order -> Sales Invoice;
- generic, approval-bound existing-document update and child-row-add tools;
- generic, approval-bound submit/cancel/delete tools; and
- a separate generic approval-bound document-email side effect.

The current implementation is permission-aware and preserves native Frappe /
ERPNext calls. The main architecture defect is at the **public update
boundary**, not in the shared engine: `LifecycleChange` accepts arbitrary
runtime field names, arbitrary `Any` values, and arbitrary valid child-table
names. The Sales update allowlist also reaches Customer and Item even though no
DocType-specific update policy or business service exists for either master.

The current child-add capability is narrower than update, but its public
contract is still generic and its result is a generic `dict[str, Any]` preview.
It is a business operation specifically for Quotation and Sales Order item
rows, with item resolution, duplicate prevention, ERPNext defaults, tax
calculation, validation, and approval. It should therefore become two explicit
Sales public capability pairs while retaining a shared internal engine.

Submit, cancel, and delete should remain generic public lifecycle tools for
the transactional Sales documents. Their input is only an exact target, and
the operation's semantics are the native document lifecycle semantics; adding
five duplicated DocType-specific wrappers would not add equivalent safety or
model value. Customer and Item should be removed from public submit/cancel
addressability because both are non-submittable in the inspected metadata.
Master deletion should also be restricted from the Sales lifecycle surface
until a separate, explicit master-deletion requirement exists.

### Recommended next implementation task

Implement one focused **Sales transaction mutation public-boundary hardening**
task:

1. Add typed, DocType-specific prepare/confirm pairs for Quotation and Sales
   Order field updates.
2. Add typed, DocType-specific prepare/confirm pairs for Quotation Item and
   Sales Order Item addition.
3. Retire the generic update and child-add registrations from the Sales
   profile only.
4. Keep the shared update and child-add engines generic and reuse them from the
   new wrappers.
5. Keep Purchase registrations, schemas, allowlists, services, and behavior
   unchanged.
6. Remove Customer and Item from Sales submit/cancel/delete lifecycle policy;
   retain their explicit creation tools.

The exact tool names, policy changes, tests, and compatibility requirements are
specified in [Section 17](#17-exact-next-implementation-task).

## 2. Repository areas inspected

The audit inspected the current `apps/mcp_erpnext` checkout on branch
`master`. The checkout already contained unrelated working-tree changes from
the preceding typed-create migration; those changes were preserved.

| Area | Current source inspected |
| --- | --- |
| Profile registration | `mcp_erpnext/profiles/sales.py`, `mcp_erpnext/profiles/purchase.py`, `mcp_erpnext/tools/__init__.py` |
| Public mutation wrappers | `mcp_erpnext/tools/masters/customer.py`, `mcp_erpnext/tools/masters/item.py`, `mcp_erpnext/tools/selling/quotation.py`, `mcp_erpnext/tools/selling/sales_order.py`, `mcp_erpnext/tools/selling/sales_invoice.py`, `mcp_erpnext/tools/selling/quotation_to_sales_order.py`, `mcp_erpnext/tools/selling/sales_order_to_sales_invoice.py`, `mcp_erpnext/tools/lifecycle.py` |
| Contracts and registry | `mcp_erpnext/contracts/common.py`, `interaction.py`, `lifecycle.py`, master/selling contracts, `contracts/registry.py`, `contracts/audit.py` |
| Shared mutation internals | `mcp_erpnext/services/common/lifecycle.py`, `creation_contract.py`, `effective_requirements.py`, `field_value_resolver.py`, `entity_resolution.py` |
| Business services | `services/masters/customer.py`, `services/masters/item.py`, `services/selling/quotation.py`, `sales_order.py`, `sales_invoice.py`, and both conversion services |
| Approval/runtime boundary | `mcp_erpnext/approvals.py`, `runtime.py`, `settings.py`, `observability.py` |
| Tests/catalog | `mcp_erpnext/tests/test_lifecycle.py`, `test_profiles.py`, `test_tool_registration.py`, `test_tool_contracts.py`, creation and conversion tests, `scripts/generate_tool_catalog.py`, generated `docs/TOOLS.md` |
| Historical architecture decisions | `docs/architecture/MCP_TOOL_CONTRACT_STANDARD.md`, `docs/architecture/MCP_CONVERSATIONAL_INTERACTION_CONTRACT.md`, Task 34 report, Sales Invoice flow reports |
| Native ERPNext/Frappe | Installed `apps/erpnext` DocType JSON/controllers plus official Frappe Document API and version-16 source links in Section 13 |

## 3. Confirmed environment and verification boundary

The inspected bench interpreter is `../../env/bin/python` from the app
checkout. It reports:

| Component | Version/evidence |
| --- | --- |
| Frappe | `16.33.1` |
| ERPNext | `16.34.2` |
| India Compliance | `16.8.4` on `yob.localhost` |
| Pydantic | `2.12.5` |
| MCP SDK | `mcp 1.29.0`, read from installed package metadata |
| Runtime metadata site | `yob.localhost`, queried read-only with `bench --site yob.localhost execute frappe.get_meta` |

The five runtime metadata calls for Customer, Item, Quotation, Sales Order,
and Sales Invoice completed successfully. The installed ERPNext source JSON
confirms `is_submittable = 1` for Quotation, Sales Order, and Sales Invoice,
while Customer and Item have no `is_submittable` flag and are therefore
non-submittable. Site metadata remains authoritative where custom fields or
property setters are present.

The Yob runtime differs from the earlier non-Yob baseline: it has India
Compliance `16.8.4`, and its Customer metadata includes `alias` in
`search_fields` together with Yob-specific modification and permission
metadata. The mutation architecture conclusion is unchanged because
the public lifecycle policy is source- and registry-controlled, while Yob is
the authority for site-specific fields, property setters, permissions, and
installed-app behavior. Future runtime checks for this MCP project must use
`yob.localhost`.

No authenticated MCP mutation call, document insertion, update, submission,
cancellation, deletion, or conversion was run for this audit. The evidence is
source, registry/schema, mocked-service, generated-catalog, and read-only
runtime metadata evidence.

## 4. Current Sales-profile public tool inventory

The actual FastMCP registration returned **48 Sales tools**. The mutation and
other write-related subset is:

| Family | Current public tools | Contract status |
| --- | --- | --- |
| Customer create | `prepare_customer`, `confirm_customer` | Explicit typed contracts |
| Item create | `prepare_item`, `confirm_item` | Explicit typed contracts |
| Sales Order create | `prepare_sales_order`, `confirm_sales_order` | Explicit typed contracts |
| Quotation create | `prepare_quotation`, `confirm_quotation` | Explicit typed contracts |
| Quotation -> Sales Order | `prepare_quotation_to_sales_order`, `confirm_quotation_to_sales_order` | Explicit typed contracts |
| Sales Order -> Sales Invoice | `prepare_sales_order_to_sales_invoice`, `confirm_sales_order_to_sales_invoice` | Explicit typed contracts |
| Sales Invoice create | `prepare_sales_invoice`, `confirm_sales_invoice` | Explicit typed contracts |
| Existing-document update | `prepare_document_update`, `confirm_document_update` | Generic typed envelope; dynamic mutation payload |
| Child-row add | `prepare_document_child_add`, `confirm_document_child_add` | Generic typed envelope; generic preview/result |
| Submit | `prepare_document_submit`, `confirm_document_submit` | Generic typed target/action pair |
| Cancel | `prepare_document_cancel`, `confirm_document_cancel` | Generic typed target/action pair |
| Delete | `prepare_document_delete`, `confirm_document_delete` | Generic typed target/action pair |
| Existing-document email | `prepare_document_email`, `confirm_document_email` | Generic explicit typed contract; separate side effect |

The remaining registered tools are reads/resolution, PDF rendering, and
aggregation: Customer, Item, Quotation, Sales Order, and Sales Invoice reads;
Sales Order item query; and `render_document_pdf`. They are outside the main
mutation analysis.

Evidence: `profiles/sales.py:8-36`, `tools/__init__.py:30-48`,
`contracts/registry.py:215-577,771-805`, and generated `docs/TOOLS.md:10-61`.

## 5. Current mutation capability matrix

The cells use the required classification and include the actual public tool
names. “Generic” describes the public MCP API; it does not mean the internal
service is unrestricted.

| Operation | Customer | Item | Quotation | Sales Order | Sales Invoice |
| --- | --- | --- | --- | --- | --- |
| Create | **Explicit public tool** — `prepare_customer` / `confirm_customer` | **Explicit public tool** — `prepare_item` / `confirm_item` | **Explicit public tool** — `prepare_quotation` / `confirm_quotation` | **Explicit public tool** — `prepare_sales_order` / `confirm_sales_order` | **Explicit public tool** — `prepare_sales_invoice` / `confirm_sales_invoice` |
| Update | **Generic public tool** — `prepare_document_update` / `confirm_document_update` | **Generic public tool** — same generic pair | **Generic public tool** — same generic pair | **Generic public tool** — same generic pair | **Denied by policy** — Sales Invoice is absent from Sales `update` allowlist |
| Child Add | **Denied by policy** — `prepare_document_child_add` / confirm pair reject target | **Denied by policy** — same | **Generic public tool** — `prepare_document_child_add` / `confirm_document_child_add` | **Generic public tool** — same pair | **Denied by policy** — absent from `CHILD_ADD_TARGETS` and update action policy |
| Submit | **Generic public tool** — policy-addressable, then native `NOT_SUBMITTABLE` | **Generic public tool** — policy-addressable, then native `NOT_SUBMITTABLE` | **Generic public tool** — `prepare_document_submit` / `confirm_document_submit` | **Generic public tool** — same pair | **Generic public tool** — same pair |
| Cancel | **Generic public tool** — policy-addressable, then native non-submittable/state rejection | **Generic public tool** — same | **Generic public tool** — `prepare_document_cancel` / `confirm_document_cancel` | **Generic public tool** — same pair | **Generic public tool** — same pair |
| Delete | **Generic public tool** — `prepare_document_delete` / `confirm_document_delete` | **Generic public tool** — same pair | **Generic public tool** — same pair | **Generic public tool** — same pair | **Generic public tool** — same pair |
| Convert | **Not applicable** | **Not applicable** | **Explicit public tool** — Quotation -> Sales Order pair | **Explicit public tool** — Sales Order -> Sales Invoice pair | **Not applicable** as a source conversion |

The “policy-addressable” Customer/Item submit and cancel cells are current
exposure, not successful business capabilities: `_prepare_action()` checks
`doc.meta.is_submittable` and returns `NOT_SUBMITTABLE` before approval. This
is why the recommendation removes those no-op routes rather than creating
wrappers for them.

## 6. Actual action and DocType allowlists

### 6.1 Shared lifecycle policy

`services/common/lifecycle.py:17-47` currently defines:

```text
Sales profile base DocTypes: Quotation, Sales Order, Customer, Item
Purchase profile base DocTypes: Purchase Order, Supplier, Item

Sales update:      Quotation, Sales Order, Customer, Item
Sales child_add:   Quotation, Sales Order, Customer, Item (target stage)
Sales submit:      Quotation, Sales Order, Customer, Item, Sales Invoice
Sales cancel:      Quotation, Sales Order, Customer, Item, Sales Invoice
Sales delete:      Quotation, Sales Order, Customer, Item, Sales Invoice

Sales child tables:
  Quotation   -> items / Quotation Item
  Sales Order -> items / Sales Order Item

Purchase policy and child table:
  Purchase Order -> items / Purchase Order Item
```

The `child_add` action first passes the action DocType set, then
`_child_add_target()` rejects every target not in the exact child-table map.
The `update` action has no field allowlist beyond runtime metadata checks.

### 6.2 Create and conversion policy

Create policy is in the business services and master config rather than one
central DocType/action map. Customer creation accepts the fields listed in
`config/masters/customer.py:9-46`; Item creation accepts the fields listed in
`config/masters/item.py:18-37`, with `is_sales_item = 1` as server policy.
Quotation, Sales Order, and Sales Invoice each have their own service and
typed contract.

Conversion policy is fixed in the conversion services. Quotation conversion
requires a submitted Customer Quotation and Sales Order create permission;
Sales Order conversion requires a submitted Sales Order and Sales Invoice
create permission. Neither conversion accepts an arbitrary source or target
DocType.

## 7. Current call-flow diagrams

### 7.1 Explicit creation

```text
Typed public request
  -> business-specific FastMCP wrapper
  -> execute_tool_with_context()
  -> existing Customer / Item / Quotation / Sales Order / Sales Invoice service
  -> resolver + runtime metadata/defaults + permission checks
  -> ERPNext/Frappe validation/calculation
  -> ApprovalStore.create(action, site, user, payload)
  -> typed preview + shared InteractionDirective(APPROVAL)
  -> confirm wrapper
  -> ApprovalStore.claim_for_confirm_write()
  -> permission recheck + native insert(ignore_permissions=False, ...)
  -> commit or rollback
```

Evidence: typed wrappers in `tools/masters/*.py` and `tools/selling/*.py`;
service entrypoints in `services/masters/customer.py:400-475`,
`services/masters/item.py:345-415`, `services/selling/quotation.py:252-422`,
`services/selling/sales_order.py:170-319`, and
`services/selling/sales_invoice.py:436-575`.

### 7.2 Generic update

```text
PrepareUpdateInput(target, changes[])
  -> tools/lifecycle.py:prepare_document_update()
  -> runtime context + observability
  -> lifecycle.prepare_update()
  -> target DocType/action allowlist
  -> frappe.get_doc() + write permission
  -> runtime doc.meta field lookup
  -> optional child-table metadata + row selector
  -> Select/Link checks; arbitrary remaining value accepted
  -> approval preview of old/new values

confirm_document_update(token, confirm)
  -> claim action-bound approval
  -> profile/action/modified/docstatus revalidation
  -> apply scalar or child-row changes
  -> doc.save(ignore_permissions=False)
  -> native validation/hooks + commit, or rollback
```

Evidence: `contracts/lifecycle.py:13-35`,
`services/common/lifecycle.py:91-242,285-308,550-641`, and
`tools/lifecycle.py:26-32`.

### 7.3 Generic child-row add

```text
PrepareChildAddInput(target, resolved Item, qty, rate)
  -> target write permission and Draft-state check
  -> exact Quotation/Sales Order items table metadata check
  -> visible sales-enabled Item lookup
  -> qty/rate validation and duplicate item_code check
  -> append unsaved row
  -> set_missing_values() + calculate_taxes_and_totals() + validate()
  -> approval token bound to child table, child DocType, row, item, site, user

confirm_document_child_add(token, confirm)
  -> claim and document revalidation
  -> duplicate recheck
  -> restore date/datetime types from approval payload
  -> append + native defaults/calculation + doc.save()
  -> commit or rollback
```

Evidence: `services/common/lifecycle.py:311-459,589-623` and
`tests/test_lifecycle.py:199-268`.

### 7.4 Generic lifecycle actions

```text
PrepareActionInput(target)
  -> action-specific DocType allowlist
  -> exact get_doc + read permission
  -> submittable/state checks
  -> cancel/delete link blocker preflight
  -> approval token bound to lifecycle action, target, profile, site, user,
     modified timestamp, and docstatus

Confirm(token, confirm)
  -> atomic claim
  -> profile/action/modified/docstatus revalidation
  -> doc.submit() / doc.cancel() / doc.delete()
     (submitted delete may native-cancel then delete)
  -> commit or rollback
```

Evidence: `services/common/lifecycle.py:462-577,580-705`.

## 8. Update architecture findings

### 8.1 Current behavior by DocType

| DocType | Current update exposure | Current writable surface | Submitted-document behavior | Finding |
| --- | --- | --- | --- | --- |
| Customer | Generic Sales update pair | Any runtime metadata field that is not system/read-only/Table/layout/Button; child changes can name any runtime Table field | Prepare blocks only Cancelled; native `doc.save()` performs normal write and update-after-submit validation | **Over-broad public schema / policy gap**; no Customer update policy or service exists |
| Item | Generic Sales update pair | Same dynamic scalar and child-table path | Same native save boundary | **Over-broad public schema / policy gap**; Item accounting, stock, tax, and classification fields are not narrowed |
| Quotation | Generic Sales update pair | Same dynamic field/value path | Native save and ERPNext controller validation remain authoritative | **Contract gap**; transaction update is business-relevant but public semantics are not explicit |
| Sales Order | Generic Sales update pair | Same dynamic field/value path | Native save and ERPNext controller validation remain authoritative | **Contract gap**; delivery/commercial/item semantics are not explicit |
| Sales Invoice | Denied by action policy | No public update route | Not reachable through this service | **Correct V1 restriction**; do not broaden without accounting-specific policy |

### 8.2 Exact current validation boundaries

`_validate_change()` uses runtime metadata (`doc.meta.get_field()` and
`frappe.get_meta(row.doctype)`) and rejects system/read-only/layout fields. It
validates Select membership and permission-aware Link existence. It does not
have a field allowlist, type-specific coercion/range policy for ordinary
fields, or a business-level allowed-values map. `LifecycleChange.value` is
`Any` in `contracts/lifecycle.py:25-30`.

Child updates use one of `row_name`, `item_code`, or `idx`; the service then
requires exactly one matching row. The public model does not enforce that
exactly one selector is present, and the service accepts a child-table field
name as long as runtime metadata calls it a Table. Thus the public contract
exposes internal field names, child-table names, and arbitrary values even
though the service has useful runtime and permission checks.

The final `doc.save(ignore_permissions=False)` preserves Frappe's native
permission, validation, hooks, link, and submitted-document checks. That is a
strong internal boundary, but it is not a substitute for a narrow public MCP
contract.

### 8.3 Recommendation

Do not add Customer or Item update merely because the old profile set includes
them. The evidence shows a legacy/base-set inclusion rather than a documented
master-update business capability. Remove them from the Sales public update
surface pending an explicit master-update requirement.

For Quotation and Sales Order, expose explicit typed update tools with a
small, reviewed, runtime-aware field policy. Keep child-row mutation out of
that update request; item addition has a different state, defaulting,
duplicate, and preview contract.

Do not add any Sales Invoice update route in this task family. The existing
Sales Invoice audit explicitly found that generic update would reach sensitive
accounting, tax, stock, and compliance fields without a safe V1 field policy.

## 9. Child-add architecture findings

### 9.1 Current supported targets

Only Quotation and Sales Order can reach a successful child-add preparation.
The exact runtime child fields are `items`, with child DocTypes Quotation Item
and Sales Order Item respectively, as enforced by
`CHILD_ADD_TARGETS` and `doc.meta.get_field()`.

Customer, Item, and Sales Invoice are rejected before approval. Customer and
Item are not treated as item-bearing transaction documents; Sales Invoice is
deliberately outside the safe V1 child-add policy.

### 9.2 Business semantics already present

The operation is not a generic row append:

- it requires an exact resolved Item reference and profile-enabled, non-disabled
  Item;
- it accepts positive quantity and optional non-negative rate;
- the service rejects boolean/non-finite/non-positive numeric values when called
  directly;
- it blocks an existing row with the same `item_code`;
- it lets ERPNext populate row defaults such as UOM, conversion factor, rate,
  warehouse, delivery date, and calculations;
- it runs native calculation and validation before issuing approval;
- it previews the effective row and binds the row payload to approval; and
- confirmation rechecks the document and duplicate state before native save.

The public `float` field is not strict: a direct contract probe showed
`PrepareChildAddInput(qty=True)` becomes `1.0` before the service's direct bool
guard. This is a small **contract gap** to close in the future explicit
contracts; it does not weaken the internal service when called outside the
public Pydantic boundary.

### 9.3 Recommendation

Replace the Sales generic child-add public pair with two explicit pairs:

```text
prepare_quotation_item_add / confirm_quotation_item_add
prepare_sales_order_item_add / confirm_sales_order_item_add
```

The public contracts should require the fixed document reference, resolved
Item reference, strict positive quantity, and optional non-negative rate. They
should expose a bounded, typed preview and shared approval interaction. The
wrappers should call the existing generic child-add engine with a fixed Sales
profile and fixed target DocType; they must not duplicate ERPNext row
defaulting, calculation, validation, duplicate, or approval logic.

## 10. Submit, cancel, and delete findings

### 10.1 Current input and guard behavior

The public prepare input is `PrepareActionInput(target: LifecycleTarget)`,
where `LifecycleTarget` contains only non-empty `doctype` and `name`.
Confirmation takes `LifecycleConfirmInput(approval_token, confirm)`. The
wrapper hides `Context`, profile, and action from the MCP schema.

Prepare loads the exact document with `frappe.get_doc`, checks the requested
permission, validates submittable/state requirements, and performs link
preflight for cancel/delete. Delete of a submitted document plans a
cancel-then-delete sequence and requires cancel permission as well as delete
permission. Confirm claims the action-specific approval, revalidates profile,
action, modified timestamp, and docstatus, calls the native document method,
and commits only after success.

### 10.2 Native behavior and genericity decision

The official Frappe Document API states that `doc.insert()` and `doc.save()`
run permission checks and controller validation/hooks, `doc.submit()` and
`doc.cancel()` are document lifecycle methods, and `doc.delete()` removes a
document and its children. The installed Frappe source implements these
methods in `frappe/model/document.py`; the official API and source links are
listed in Section 13.

Submit/cancel/delete have no Sales-specific payload beyond target identity and
native lifecycle state. Unlike item add or update, there is no meaningful
business field contract to improve by duplicating the wrapper for every
DocType. Keep these public tools generic for Quotation, Sales Order, and Sales
Invoice, while keeping the internal engine shared.

The current Customer/Item submit/cancel routes are accidental addressability:
the allowlist reaches them, but metadata rejects them as non-submittable. They
should be removed from the Sales action allowlist. Master delete should be
restricted from public Sales V1 because it is irreversible and has no current
master-specific review contract; the native link/dependency preflight remains
valuable for future explicit enablement.

Replay protection is strong at the approval layer: a token is bound to action,
site, user, and payload and is atomically consumed before persistence. A stale
document or failed business action therefore requires a fresh prepare. The
operation is not idempotent by document key; successful mutation returns a
result without an idempotency key.

## 11. Create architecture consistency findings

The current create pattern is consistent with the intended boundary:

```text
business-specific typed public contract
  -> thin wrapper conversion and shared interaction attachment
  -> existing business service
  -> ApprovalStore
  -> normal permission-enforced ERPNext/Frappe insert
```

Task 34 migrated Customer, Item, and Sales Order create wrappers in place.
Quotation, Sales Invoice, and Purchase Order already used the same typed
RootModel/TypeAdapter/`structured_output=True` pattern. The current registry
has `FROZEN_LEGACY_TOOL_NAMES = frozenset()` and all inspected registered tools
have explicit contracts. No create change is recommended in this audit.

Important preserved behavior:

- Customer uses runtime creation metadata/defaults and the native India
  Compliance bridge; it does not call side-effecting GST lookup during prepare.
- Item uses runtime creation metadata, effective requirements, and the native
  India Compliance HSN/SAC preflight while keeping `is_sales_item = 1` server
  controlled.
- Quotation, Sales Order, and Sales Invoice use their existing resolvers,
  native defaults/calculation, and final validation/insert paths.

Evidence: Task 34 report, typed contracts under `contracts/masters` and
`contracts/selling`, and the service entrypoints cited in Section 7.

## 12. Conversion/mapping findings

### Quotation -> Sales Order

`prepare_quotation_to_sales_order` and `confirm_quotation_to_sales_order` are
already explicit business tools. The service requires an exact Submitted
Customer Quotation, checks source read and target create permission, calls
ERPNext's native `make_sales_order`, applies the audited delivery-date parity
rule, validates the mapped Draft, previews lineage/economics, and uses a
fingerprint to reject changed source/mapped state at confirmation.

Evidence: `services/selling/quotation_to_sales_order.py:20-69,246-340`,
`tools/selling/quotation_to_sales_order.py`, and the existing conversion report.

### Sales Order -> Sales Invoice

`prepare_sales_order_to_sales_invoice` and
`confirm_sales_order_to_sales_invoice` are already explicit business tools.
The service requires a Submitted Sales Order, checks source read and target
Sales Invoice create permission, calls ERPNext's native
`make_sales_invoice(..., ignore_permissions=False)`, bounds the mapped Draft
preview, fingerprints it, and revalidates before insert.

Evidence: `services/selling/sales_order_to_sales_invoice.py:21-71,220-380`,
`tools/selling/sales_order_to_sales_invoice.py`, and the existing conversion
report.

Quotation has a native ERPNext Quotation -> Sales Invoice mapper in the
installed source, but no public MCP tool exposes it. This is a deliberate
scope boundary, not an accidental generic conversion route. Do not add it as a
side effect of the mutation hardening task.

## 13. Approval, runtime, and native-source findings

### Approval guarantees

All final writes use prepare/confirm. `ApprovalStore.create()` binds the
operation to a cryptographically random token, action, site, user, payload
digest, and fifteen-minute TTL (`approvals.py:16-85`).

`claim_for_confirm_write()` validates the same action/site/user, optionally
requires server-recorded trusted human approval, and consumes the token before
the database write (`approvals.py:121-140`). This prevents concurrent replay,
but the store is process-local and therefore not shared across MCP workers.

The two server-selected modes are `trusted_human` and `agent_delegated`
(`settings.py:15-19,70-115`). `MCP_APPROVAL_MODE` is not a public tool
argument. `record_trusted_user_approval()` remains internal transport plumbing;
natural-language approval interpretation remains outside MCP.

The shared `InteractionDirective` uses only semantic kinds/actions and is
client-neutral (`contracts/interaction.py:12-89`). Future wrappers must keep
the existing `CONFIRM_WRITE` guard and must not add public approval-mode or
client-specific fields.

### Runtime identity and Context

`execute_tool_with_context()` resolves STDIO versus HTTP runtime identity and
executes within the Frappe site/user scope (`runtime.py:41-150`). `Context` is
present for wrapper execution but absent from the generated public schemas.
The current contract audit checks both this runtime-field boundary and the
shared interaction schema (`contracts/audit.py:13-147,175-275`).

### Official native references

The native behavior used in this audit was checked against the installed
version-16 source and the official references below:

- [Frappe Document API](https://docs.frappe.io/framework/user/en/api/document) — `insert`, `save`, `submit`, `cancel`, `delete`, permissions, and `get_meta`.
- [Frappe version-16 `frappe/model/document.py`](https://github.com/frappe/frappe/blob/version-16/frappe/model/document.py) — native document save/lifecycle implementation.
- [ERPNext version-16 Quotation controller](https://github.com/frappe/erpnext/blob/version-16/erpnext/selling/doctype/quotation/quotation.py) — native Quotation validation and mapping entrypoints.
- [ERPNext version-16 Sales Order controller](https://github.com/frappe/erpnext/blob/version-16/erpnext/selling/doctype/sales_order/sales_order.py) — native Sales Order validation and Sales Invoice mapping entrypoint.
- [Frappe controller lifecycle documentation](https://docs.frappe.io/framework/user/en/basics/doctypes/controllers) — validation and lifecycle hooks for insert/save/submit/cancel/update-after-submit.

## 14. Security and exposure audit

| Current surface | Classification | Evidence and impact |
| --- | --- | --- |
| Generic lifecycle `doctype` | **Acceptable genericity** for currently allowed transactional targets | `LifecycleTarget` exposes an exact target, but `_target()` applies action-scoped profile allowlists before loading the document. |
| Generic update `field` | **Over-broad public schema** | Any non-empty runtime field name can be attempted; system/read-only and unsupported field types are rejected only after request arrival. |
| Generic update `value` | **Contract gap** | `LifecycleChange.value: Any`; only Select and Link receive early checks, while other type/range/semantic validation is deferred to native save. |
| Generic update `child_table` | **Over-broad public schema / policy gap** | Any runtime Table on an allowed parent can be named for update; the policy does not restrict child tables to business-approved tables. |
| Child-add `doctype` | **Acceptable genericity internally; over-generic public API** | Runtime exact target and `CHILD_ADD_TARGETS` restrict successful targets to Quotation/Sales Order, but the model does not tell the client which business operation it is invoking. |
| Child-add `qty` bool coercion | **Contract gap** | Pydantic `float` accepts `True` as `1.0` before the service's direct bool guard. |
| Lifecycle output dictionaries | **Documentation/contract gap** | `LifecycleResult.preview`, `document`, and `blockers` are generic dictionaries; actual services keep them bounded, but DocType-specific typed result schemas would improve model accuracy for update/item-add. |
| `Context`, user, site, approval mode | **No issue** | Hidden from input schemas and sourced server-side by runtime/approval infrastructure. |
| Conversion source/target | **No issue** | Fixed explicit conversion services and typed contracts do not accept arbitrary DocTypes. |
| Preview/result business data | **No issue for current V1** | Previews are bounded by each service; Item creation explicitly omits pricing/valuation/accounting/tax data, and lifecycle results expose only action-relevant fields. |

The security conclusion is not that the generic engine is unsafe. Its runtime
metadata, permission, native validation, action allowlist, and approval checks
are useful. The conclusion is that the **LLM-facing shape communicates and
permits more mutation vocabulary than the Sales V1 business capabilities
justify**.

## 15. Public-vs-internal architecture decision matrix

| Operation family | Current public API | Recommended public API | Recommended internal architecture | Why |
| --- | --- | --- | --- | --- |
| Create | Explicit typed business pairs | Keep explicit typed pairs for Customer, Item, Quotation, Sales Order, Sales Invoice | Keep business services and shared creation-contract/effective-requirement helpers | Creation inputs, defaults, resolution, and previews differ materially by DocType |
| Update | Generic typed envelope for Customer/Item/Quotation/Sales Order | Explicit typed Quotation and Sales Order pairs; Customer/Item/Sales Invoice denied until separately justified | Keep shared metadata-aware update engine, with fixed target/policy calls from wrappers | Transaction fields and child boundaries need business contracts; mechanics are reusable |
| Child Add | Generic pair, successful only for Quotation/Sales Order | Explicit Quotation Item and Sales Order Item pairs | Keep generic append/default/calculate/validate/approval engine | Item addition is a distinct business operation with typed quantity/rate/duplicate semantics |
| Submit | Generic target/action pair for Q/SO/SI plus no-op master routes | Keep generic pair for Q/SO/SI; remove Customer/Item policy routes | Keep native lifecycle engine and action-scoped policy | Target identity is sufficient; native lifecycle semantics are the value |
| Cancel | Generic target/action pair for Q/SO/SI plus no-op master routes | Keep generic pair for Q/SO/SI; remove Customer/Item policy routes | Keep native lifecycle engine and link preflight | No useful DocType-specific payload; native dependency semantics must remain central |
| Delete | Generic pair for all five | Keep generic pair for Q/SO/SI; restrict Customer/Item from Sales V1 | Keep link-aware native delete/cancel-delete engine | Irreversible master deletion needs a separately reviewed business capability |
| Convert | Explicit pairs for Q->SO and SO->SI | Keep both explicit pairs; do not add Q->SI in this task | Keep native ERPNext mapper services and fingerprint/revalidation | Source/target lineage and native mapping are business-specific and already correct |

## 16. Per-DocType recommendation

### Customer

Current: explicit typed create; generic update, submit, cancel, and delete
addressability; child add rejected.

Recommendation: keep typed Customer creation and all GST/Contact/Address
native-bridge behavior. Remove Customer from the Sales generic update,
submit/cancel, and delete public policy. Do not create a Customer-specific
update/delete wrapper in the next task. Revisit only with a concrete master
maintenance use case and a field/side-effect policy that covers Customer,
Contact, Address, and India Compliance behavior.

### Item

Current: explicit typed sales-item creation; generic update, submit, cancel,
and delete addressability; child add rejected.

Recommendation: keep typed sales-item creation, runtime HSN/SAC requirements,
and `is_sales_item` server policy. Remove Item from Sales generic update,
submit/cancel, and delete public policy. Do not expose generic Item update;
stock, valuation, accounting, tax, supplier, and classification fields require
a separate narrow business decision.

### Quotation

Current: explicit typed create; generic update, child add, submit, cancel,
delete; explicit Quotation -> Sales Order conversion.

Recommendation: keep create, conversion, and generic submit/cancel/delete.
Replace public generic update and child add with typed Quotation update and
Quotation Item-add pairs backed by the shared engines. Keep native quotation
calculation, validation, submitted-state, lineage, and approval behavior.

### Sales Order

Current: explicit typed create; generic update, child add, submit, cancel,
delete; explicit Sales Order -> Sales Invoice conversion.

Recommendation: keep create, conversion, and generic submit/cancel/delete.
Replace public generic update and child add with typed Sales Order update and
Sales Order Item-add pairs backed by the shared engines. Preserve delivery-date
defaulting, commercial defaults, item resolution, native calculations,
validation, and approval behavior.

### Sales Invoice

Current: explicit typed standalone create; generic submit/cancel/delete;
explicit Sales Order -> Sales Invoice target conversion; update and child add
denied.

Recommendation: keep exactly this V1 boundary. Do not add generic or explicit
Sales Invoice update/child-add tools. Keep standalone creation and native
Sales Order conversion separate from lifecycle state changes. Submit/cancel/
delete remain generic and permission/link guarded.

No additional Sales DocType was found in the Sales document mutation policy.
The generic email side effect can address Quotation, Sales Order, and Sales
Invoice through its own typed contract, but it is not a document mutation
family and should not be folded into lifecycle/update design.

## 17. Exact next implementation task

### Task name

**Sales Transaction Mutation Public-Boundary Hardening**

### Exact DocTypes

- Quotation
- Sales Order

Customer and Item are explicitly out of scope for new update tools. Sales
Invoice remains update/child-add denied.

### Exact public tools to add

```text
prepare_quotation_update
confirm_quotation_update

prepare_sales_order_update
confirm_sales_order_update

prepare_quotation_item_add
confirm_quotation_item_add

prepare_sales_order_item_add
confirm_sales_order_item_add
```

Each prepare tool must return an explicit typed discriminated result with
bounded preview/error states and the shared `InteractionDirective` approval
semantics. Each confirm tool must accept only the existing opaque token and
confirmation decision shape appropriate to the established contract pattern;
the public boundary must not expose `Context`, user, site, approval mode, or
trusted-approval internals.

### Exact public tools to retire from Sales only

Do not register these four generic tools in the Sales profile:

```text
prepare_document_update
confirm_document_update
prepare_document_child_add
confirm_document_child_add
```

They must remain registered and behaviorally unchanged in the Purchase
profile. No tool rename or v2 alias is needed for Purchase.

The generic submit/cancel/delete tools remain registered in Sales for
Quotation, Sales Order, and Sales Invoice. Their profile registration can stay
generic only if the service policy prevents Customer/Item targets; otherwise
the Sales wrapper registration/policy must be split without changing Purchase.

### Exact policy changes

In the Sales-facing policy:

1. Remove Customer and Item from `update`, `submit`, `cancel`, and `delete`
   public addressability.
2. Keep Quotation and Sales Order as the only transaction targets for the
   shared internal update and child-add engine.
3. Keep Sales Invoice out of update and child-add.
4. Keep Quotation, Sales Order, and Sales Invoice in submit/cancel/delete.
5. Keep `CHILD_ADD_TARGETS` fixed to `Quotation.items / Quotation Item` and
   `Sales Order.items / Sales Order Item`.
6. Add explicit field-policy maps for Quotation and Sales Order updates. The
   maps must be derived/validated against `frappe.get_meta()` at runtime and
   must not accept arbitrary field names or child-table updates.

The exact business fields must be selected during implementation from current
runtime metadata and native `allow_on_submit`/controller behavior. This audit
does not invent a field list. A field absent from the approved policy must be
rejected before approval.

### Exact shared internals to reuse

- `services/common/lifecycle._load()` and action-scoped target validation;
- `services/common/lifecycle._validate_change()` after adding the explicit
  wrapper/policy boundary;
- `services/common/lifecycle.prepare_update()` and `confirm("update", ...)`;
- `services/common/lifecycle.prepare_child_add()` and
  `confirm("child_add", ...)`;
- `ApprovalStore.claim_for_confirm_write()` and current server approval mode;
- runtime `frappe.get_meta()` and native `doc.save()`;
- existing Item resolution and ERPNext row default/calculation/validation
  path; and
- shared `InteractionDirective`, typed RootModel/TypeAdapter, and
  `structured_output=True` wrapper conventions.

Do not duplicate native Quotation/Sales Order validation, pricing, UOM,
delivery-date, tax, duplicate, permission, transaction, or approval logic in
the wrappers.

### Backward-compatibility approach

- Preserve all existing explicit create and conversion tool names and payload
  behavior.
- Preserve Purchase public tool names, schemas, registrations, allowlists,
  service calls, and business behavior byte-for-byte where possible.
- Retiring the four generic Sales names is an intentional public API change;
  document it in the generated catalog and migration notes.
- Do not expose aliases that keep the over-broad Sales schema reachable.
- If an existing caller needs update/item-add, it must migrate to the
  DocType-specific typed pair and prepare a fresh approval token.
- Existing pending generic Sales tokens must fail closed after the registration
  boundary change; never reinterpret one as a new explicit operation.

### Required tests

1. Registration: Sales contains the eight new explicit names and excludes the
   four generic update/child-add names; Purchase still contains the original
   generic names and no Sales-specific names.
2. Contract audit: all new tools have explicit input/output schemas, no
   arbitrary public objects, no `Context`, shared interaction schema, and
   `CONFIRM_WRITE` approval guard.
3. Policy: Customer, Item, and Sales Invoice update/child-add are denied;
   Customer/Item submit/cancel/delete are denied; Q/SO update and item-add
   remain reachable only through their explicit tools; Q/SO/SI lifecycle
   actions remain reachable through generic tools.
4. Update fields: approved scalar fields succeed through the shared engine;
   unknown, read-only, system, unsupported, wrong-type, and unapproved fields
   fail before approval; child-table changes cannot enter the explicit update
   contract.
5. Item add: exact Item reference, strict numeric qty/rate, duplicate item
   rejection, Draft-only state, runtime child-table verification, native row
   defaults, calculation, validation, preview, and stale confirmation.
6. Approval: action/site/user/payload binding, trusted-human and
   agent-delegated server modes, single-use consumption, rejection/cancel,
   stale document, and concurrent confirmation behavior.
7. Native behavior: final save uses normal permission enforcement and preserves
   Quotation/Sales Order controller validation and hooks.
8. Regression: all existing Sales create/conversion/lifecycle tests and the
   full app suite remain green.
9. Catalog: regenerate/check `docs/TOOLS.md` and inspect both profiles.

### Behavior that must remain unchanged

- Purchase profile observable behavior.
- Customer GST/India Compliance bridge and transient address behavior.
- Item HSN/SAC effective runtime requirement and sales-item policy.
- Quotation/Sales Order native defaults, calculations, validation, and Draft
  creation behavior.
- Sales Invoice update/child-add denial and standalone/conversion boundaries.
- Native submit/cancel/delete, link preflight, permission checks, rollback,
  commit, and action-specific approval semantics.
- Client-neutral interaction directives and Agent-owned language
  interpretation.

## 18. Purchase compatibility boundary

Purchase was inspected but not redesigned. Its current public inventory still
contains `prepare_purchase_order`/`confirm_purchase_order`, the generic
update/child-add/submit/cancel/delete pairs, and purchase reads/email/PDF.
`profiles/purchase.py:8-29` and `tests/test_profiles.py:64-108` establish the
separate profile boundary.

The next task must either keep `register_lifecycle_tools(mcp, "purchase")`
unchanged or introduce a profile-specific Sales registration branch that does
not alter Purchase's effective tool list, schemas, policy, service calls, or
business results. Any shared-engine change must be regression-tested against
Purchase before merge.

## 19. Risks and migration concerns

- Removing generic Sales update/child-add names is a deliberate breaking public
  contract change and requires client/catalog communication.
- Narrow field policies must account for site custom fields/property setters;
  hard-coded ERPNext core assumptions are not sufficient.
- Submitted-document updates depend on `allow_on_submit` and native controller
  rules. The explicit contract must not promise fields that native ERPNext
  rejects.
- Approval storage remains process-local. A future multi-worker deployment
  still needs shared approval persistence, but that is not part of the next
  mutation-boundary task.
- Confirmation claims are consumed before persistence. Failures after claim
  require reprepare; tests and client guidance must retain this behavior.
- Runtime metadata checks and native validation can differ by site. Static
  contract tests cannot prove every custom field or permission combination.
- No live authenticated MCP mutation was run in this audit, so real user-role,
  custom-field, queue, and database behavior remain unverified.

## 20. What should not be changed

This audit does not authorize changes to:

- Purchase tools, schemas, allowlists, or business behavior;
- Customer/Item/Quotation/Sales Order/Sales Invoice create services or create
  contracts;
- India Compliance rules or GST/HSN behavior;
- approval storage, approval modes, or trusted-human recording;
- native ERPNext/Frappe controllers or database data;
- Sales Invoice accounting policy or direct-create restrictions;
- conversion mappers, source lineage, or conversion approval semantics;
- PDF/email behavior;
- reads, queries, aggregation, or generated catalog format beyond reflecting a
  verified registration change.

## 21. Verification performed

The following safe checks were run from `apps/mcp_erpnext`:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python -m unittest discover -s mcp_erpnext/tests -p 'test_*.py'
```

Result: **264 tests, OK**. The suite emitted the existing Pydantic settings
forward-reference warning and an expected mocked India Compliance error log;
neither failed a test.

```bash
PYTHONDONTWRITEBYTECODE=1 ../../env/bin/python scripts/generate_tool_catalog.py --check
```

Result: **passed**; generated `docs/TOOLS.md` matches the registered catalog.

The direct FastMCP inspection returned 48 Sales tools, object input/output
schemas for the lifecycle prepares, no visible `ctx`, and
`audit_tool_contracts(...) == []`.

Read-only runtime metadata checks used:

```bash
./env/bin/bench --site yob.localhost list-apps
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Customer"]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Item"]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Quotation"]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Sales Order"]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Sales Invoice"]'
```

All six completed successfully after the read-only commands were retried with
the required local runtime access. Yob reported Frappe `16.33.1`, ERPNext
`16.34.2`, India Compliance `16.8.4`, and the installed Yob/MCP apps. No live
write or mutation was performed.

## 22. Acceptance checklist

- [x] Full current Sales tool surface inspected.
- [x] Customer, Item, Quotation, Sales Order, and Sales Invoice evaluated.
- [x] Recommendations derived from current code, policy, tests, metadata, and native behavior.
- [x] Generic update exposure traced end-to-end.
- [x] Generic child-add exposure traced end-to-end.
- [x] Submit/cancel/delete evaluated rather than assumed.
- [x] Create and conversion consistency checked.
- [x] Approval behavior and security exposure reviewed.
- [x] Shared internal engines distinguished from public contracts.
- [x] Current action/DocType allowlists documented.
- [x] Purchase profile was not redesigned or changed.
- [x] Purchase compatibility requirements defined for future shared changes.
- [x] Final generic-vs-explicit decision matrix produced.
- [x] Per-DocType recommendations produced.
- [x] Risks and migration concerns documented.
- [x] One exact next implementation task defined.
- [x] No production/business code changed during the audit.
