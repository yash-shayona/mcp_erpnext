# Customer-Scoped Contact Detail and Email/Phone Update Audit

Status: completed audit/design. No Contact or Customer update capability was implemented by this task.

## 1. Executive summary

The checked-out Frappe/ERPNext/CRM sources support a narrow, native update
boundary for an existing Contact that is already linked to an explicitly
selected Customer. The Contact document remains the authority. MCP should
only resolve the Customer and Contact, bind the exact current state, prepare a
bounded semantic preview, and then call normal `Contact.save()` with
`ignore_permissions=False` after shared approval.

The recommended next slice is:

```text
search_contacts
prepare_contact_update
confirm_contact_update
```

`search_contacts` is already implemented by Task 57 and should remain
unchanged. Task 59 should add the two update tools with one typed operation per
prepare request. The V1 operation set should allow:

- parent details: `first_name`, `middle_name`, `last_name`, `company_name`,
  `designation`, and `department`;
- `add_email`, `replace_primary_email`, and `set_primary_email`;
- `add_phone`, `replace_primary_phone`, `replace_primary_mobile`,
  `set_primary_phone`, and `set_primary_mobile`.

The V1 operation set should not allow removal of email/phone rows, clearing a
primary value, arbitrary child-table patches, Dynamic Link mutation, existing
Contact primary promotion, delete, unlink, merge, or Supplier/Purchase
management. Removal is destructive and has no native fallback selection.
Existing-Contact primary promotion is a separate future task because
`Contact.is_primary_contact` is global across all links and native Contact
validation demotes other primary Contacts for every linked party.

Shared Contacts should be rejected in V1 when the target Contact has any other
party link. An edit changes one Contact record for every linked party, while a
Customer-scoped MCP request gives no safe way to imply consent for those other
usages. The preview may expose only the count, never unrelated party names.

If the edited Contact is `Customer.customer_primary_contact`, the future
confirm must require Customer write permission, save Contact and Customer in
one outer transaction, and let normal Customer link validation refresh the
stored `email_id`, `mobile_no`, `first_name`, and `last_name` fetch
projections. If Customer write permission is absent, fail before Contact
mutation. If the Contact is linked but not the Customer primary, do not touch
Customer.

Evidence labels used below:

- **Runtime verified**: observed through read-only `bench execute` on
  `praveg.localhost`.
- **Source verified**: observed in the checked-out Frappe/ERPNext/CRM or
  `mcp_erpnext` source.
- **Inferred / unverified**: a design consequence that was not exercised on a
  live business record.

## 2. Repository state and versions

The relevant checkout is `/home/frappe/frappe-bench` with the application
checkout at `apps/mcp_erpnext`.

| Component | Branch | Revision | Evidence |
|---|---|---|---|
| `mcp_erpnext` | `master` | `bf2ccb1` | `git -C apps/mcp_erpnext branch --show-current`, `rev-parse --short HEAD` |
| Frappe | `version-16` | `c1f1e8ec37` | same read-only Git checks |
| ERPNext | `version-16` | `12cd563fb9` | same read-only Git checks |
| CRM | `develop` | `c8ed011` | same read-only Git checks |

The `mcp_erpnext` working tree already contains uncommitted Task 57 changes
and new Task 56/57 artifacts. They were inspected and preserved. This report
is the only new artifact created for Task 58.

`bench version` was attempted but could not produce a version report because
the installed `india_compliance` checkout has an empty/damaged Git reference
and GitPython raised `ValueError: SHA is empty`. Per-app revisions above were
therefore collected directly without changing Git configuration or the
checkout.

## 3. Task 57 implementation baseline

Task 57 currently provides:

| Surface | Current implementation | Reuse decision |
|---|---|---|
| Contract | `mcp_erpnext/contracts/masters/contact.py` | Reuse `ContactReference`, `CustomerReference`, `ContactProjection`, `ToolError`, and shared `InteractionDirective`; add update-specific models in the same module. |
| Search | `services/masters/customer_contact.py:188-259`, exposed by `tools/masters/customer_contact.py:38-62` | Keep unchanged. It scopes fuzzy/name search to a Customer and keeps global matching exact. |
| Prepare | `services/masters/customer_contact.py:319-421` | Reuse the service shape, but use a new action and update-specific approval payload. |
| Confirm | `services/masters/customer_contact.py:434-498` | Reuse shared approval claim and normal document mutation patterns; do not copy its create/link-specific logic. |
| Projection | `_projection()` in `services/masters/customer_contact.py:96-120` | Reuse the bounded parent projection. Add only the selected child row/current and resulting primary values to update previews. |
| Duplicate helpers | `_normalised_phone()`, `_child_values()`, `_duplicate_contacts()` | Reuse phone comparison for selection/search only. Do not treat it as native storage normalization or uniqueness. |
| Permission helpers | `_load_customer()` and `_load_contact()` | Reuse exact document permission checks and add explicit Customer write preflight for primary projection refresh. |
| Approval | `_ACTION = "customer_contact"`, `ApprovalStore`, `stable_fingerprint` | Use a new action such as `customer_contact_update`; continue using the shared store and `claim_for_confirm_write()`. |
| Registration | `contracts/registry.py`, `remote_operations.py`, `tools/__init__.py`, Sales profile registration, REST typed dispatch | Add update entries to each existing registry/dispatcher; no transport-specific implementation. |
| Tests | `mcp_erpnext/tests/test_customer_contact.py`, profile/REST/tool-registration tests | Extend with a separate update test module plus registry/profile/REST parity coverage. |

Task 57's public Contact projection intentionally does not expose child row
names or all email/phone rows. That remains the right default. A future update
prepare may internally bind row names and values, but should expose only the
minimum selected-row information required for user review.

### Task 57 defects kept separate

Two observations are not silently folded into Task 59:

1. `confirm_customer_contact()` calls `frappe.db.commit()` inside both the
   create and link paths (`services/masters/customer_contact.py:459-461` and
   `489-491`). That is acceptable only as a single-document Task 57 boundary;
   it conflicts with the repository's broader rule that a combined native
   operation should let the outer confirm boundary own commit/rollback. Task
   59 must not copy this for Contact + Customer refresh. A separate Task 57
   hardening fix may remove those internal commits after its existing tests are
   reviewed.
2. `_projection()` counts every non-target Dynamic Link, not only party links.
   The field name `other_party_link_count` therefore has broader semantics
   than its name suggests. Task 59 must either use a clearly defined
   party-link count helper or classify all non-target links conservatively; it
   must not disclose link identities.

These are source findings, not changes made by this audit.

## 4. Runtime metadata re-check

The mandatory read-only checks were attempted on `praveg.localhost`:

```text
./env/bin/bench --site praveg.localhost execute frappe.get_installed_apps
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Contact"]'
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Contact Email"]'
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Contact Phone"]'
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Dynamic Link"]'
./env/bin/bench --site praveg.localhost execute frappe.get_meta --args '["Customer"]'
```

All six commands exited successfully. Installed apps were:

```text
["frappe", "erpnext", "hrms", "crm", "praveg", "insights"]
```

The following compact runtime queries also exited successfully:

```text
./env/bin/bench --site praveg.localhost execute frappe.get_all --args '["DocField"]' --kwargs '{"filters":{"parent":"Contact","fieldname":["in",["first_name","middle_name","last_name","full_name","email_id","designation","department","phone","mobile_no","company_name","email_ids","phone_nos","links","is_primary_contact"]]},"fields":["parent","fieldname","fieldtype","options","read_only","fetch_from","reqd"],"order_by":"parent,fieldname","limit_page_length":100}'
./env/bin/bench --site praveg.localhost execute frappe.get_all --args '["DocField"]' --kwargs '{"filters":{"parent":"Customer","fieldname":["in",["customer_primary_contact","email_id","mobile_no","first_name","last_name"]]},"fields":["parent","fieldname","fieldtype","options","read_only","fetch_from","reqd"],"order_by":"parent,fieldname","limit_page_length":100}'
./env/bin/bench --site praveg.localhost execute frappe.get_all --args '["DocPerm"]' --kwargs '{"filters":{"parent":["in",["Contact","Customer"]]},"fields":["parent","role","permlevel","read","write","create","delete"],"order_by":"parent,idx","limit_page_length":100}'
```

Runtime-confirmed Contact fields:

| Field | Type/options | Runtime read-only | Fetch source |
|---|---|---:|---|
| `first_name`, `middle_name`, `last_name`, `company_name`, `designation`, `department` | Data | no | none |
| `full_name` | Data | yes | none |
| `email_id` | Data / Email | yes | none |
| `email_ids` | Table / Contact Email | no | none |
| `phone` | Data / Phone | yes | none |
| `mobile_no` | Data / Phone | yes | none |
| `phone_nos` | Table / Contact Phone | no | none |
| `links` | Table / Dynamic Link | no | none |
| `is_primary_contact` | Check | no | none |

Runtime-confirmed Customer fields:

| Field | Type/options | Fetch source |
|---|---|---|
| `customer_primary_contact` | Link / Contact | none |
| `email_id` | Read Only / Email | `customer_primary_contact.email_id` |
| `mobile_no` | Read Only / Mobile | `customer_primary_contact.mobile_no` |
| `first_name` | Read Only | `customer_primary_contact.first_name` |
| `last_name` | Read Only | `customer_primary_contact.last_name` |

The runtime `DocPerm` query returned no standalone permission rows for
`Contact Email`, `Contact Phone`, or `Dynamic Link`; child mutations are
governed by the parent Contact permission. The configured Contact and Customer
role rows were returned and match the installed JSON. Role names are evidence
of this site only and must not be hard-coded into MCP.

Runtime hook checks:

```text
./env/bin/bench --site praveg.localhost execute frappe.get_hooks --args '["override_doctype_class"]' --kwargs '{"app_name":"crm"}'
```

returned `Contact: crm.overrides.contact.CustomContact`. A direct runtime
`doc_events` serialization attempt failed because `frappe.get_hooks()` returns
non-JSON tuple-keyed structures in this version. The effective hook is source
verified in `apps/crm/crm/hooks.py:144-147` and is recorded below. No mutation
or business-record fixture was run.

## 5. Installed Contact, Customer, and CRM authority

### Contact controller

`apps/frappe/frappe/contacts/doctype/contact/contact.py` is authoritative:

- `Contact.autoname()` (`:54-63`) computes the name only for insert and may
  append the first linked party name and a numeric suffix.
- `Contact.validate()` (`:65-78`) recomputes `full_name`, derives primary
  email/phone/mobile parent fields, sets a User if absent and email matches,
  updates Dynamic Link titles, deduplicates links, and validates primary
  Contact state.
- `set_primary_email()` (`:175-194`) rejects multiple primary email rows,
  makes a sole email row primary, and leaves the parent `email_id` empty when
  multiple rows have no primary.
- `set_primary()` (`:196-219`) independently derives `phone` and
  `mobile_no` from `is_primary_phone` and `is_primary_mobile_no`. It permits
  the same row to carry both flags; it does not automatically mark the first
  phone row primary.
- `add_email()` and `add_phone()` (`:154-173`) are convenience appenders. Their
  `autosave=True` path calls `save(ignore_permissions=True)`, so they are not a
  public MCP write seam. With `autosave=False` they only mutate an in-memory
  document and do not enforce the final permission boundary themselves.
- `validate_primary_contact()` (`:80-129`) locks linked party documents in a
  stable order, finds other primary Contacts for every link, and demotes them
  using `frappe.db.set_value`. This is global across the Contact's links.

The Contact JSON (`apps/frappe/frappe/contacts/doctype/contact/contact.json`)
marks `email_id`, `phone`, `mobile_no`, and `full_name` read-only, while the
child tables and the six selected detail fields are writable. Read-only here
means derived UI/document fields, not that the controller cannot assign them;
the future service must mutate the child rows and let `validate()` derive the
parent values.

### Child tables and Dynamic Link

`contact_email.json` defines required `email_id` with Email option and an
`is_primary` Check. `contact_phone.json` defines required `phone` with Phone
option and independent `is_primary_phone` and `is_primary_mobile_no` Checks.
Neither child DocType has permissions of its own. `dynamic_link.json` defines
required `link_doctype` and `link_name`, plus read-only `link_title`.

`Document.save()` (`apps/frappe/frappe/model/document.py:559-618`) performs
write permission, optimistic modified-time checking, link validation,
controller validation, parent update, child-table synchronization, and hooks.
`update_child_table()` (`:647-689`) identifies retained rows by child `name`
and deletes persisted child rows omitted from the in-memory table. This is why
future approval state must bind row names, not only mutable email/phone values.

Frappe's `_validate_data_fields()` (`apps/frappe/frappe/model/base_document.py:1131-1170`)
validates Email and Phone data fields. It does not provide Contact-wide
uniqueness or canonical storage normalization.

### CRM override and event

Runtime and source both show:

```text
override_doctype_class["Contact"] = "crm.overrides.contact.CustomContact"
doc_events["Contact"]["validate"] = ["crm.api.contact.validate"]
```

`CustomContact` currently only customizes list columns. The CRM validation
hook (`apps/crm/crm/api/contact.py:5-25`) finds primary CRM Deal links and
updates each linked Deal's `email` and `mobile_no` snapshot using
`frappe.db.set_value`. This is an expected native side effect of normal
Contact save. The MCP must not bypass it. It should be disclosed in the
preview as a bounded possible CRM snapshot refresh, without exposing Deal
names or CRM data.

No `erpnext` Contact override was found. Customer behavior is in
`apps/erpnext/erpnext/selling/doctype/customer/customer.py`.

## 6. Field-authority map

| Field | DocType | Native authority | Writable? | Derived? | V1 candidate? | Reason |
|---|---|---|---:|---:|---:|---|
| `first_name` | Contact | Contact parent/controller | yes | no | yes | Bounded detail correction; affects `full_name` and Customer fetch projection when primary. |
| `middle_name` | Contact | Contact parent/controller | yes | no | yes | Same as above; does not rename the document. |
| `last_name` | Contact | Contact parent/controller | yes | no | yes | Explicitly supports common correction intent. |
| `company_name` | Contact | Contact parent/controller | yes | no | yes | Native bounded detail; preview must show full-name result and stable document name. |
| `designation` | Contact | Contact parent/controller | yes | no | yes | Native detail field. |
| `department` | Contact | Contact parent/controller | yes | no | yes | Native detail field. |
| `full_name` | Contact | `Contact.validate()` from name fields | no | yes | no | Read-only derived display projection. |
| `email_ids[]` | Contact Email | child rows plus Contact controller | yes | no | yes, bounded actions | Child table is authoritative. Do not set parent `email_id`. |
| `email_id` | Contact | `Contact.set_primary_email()` | no | yes | no | Derived from the sole/flagged child row. |
| `phone_nos[]` | Contact Phone | child rows plus Contact controller | yes | no | yes, bounded actions | Child table is authoritative. |
| `phone` | Contact | `Contact.set_primary("phone")` | no | yes | no | Derived from `is_primary_phone`. |
| `mobile_no` | Contact | `Contact.set_primary("mobile_no")` | no | yes | no | Derived from `is_primary_mobile_no`. |
| `links[]` | Dynamic Link children | relationship authority | no in update V1 | no | no | Customer membership is the authorization boundary; arbitrary relationship mutation is out of scope. |
| `is_primary_contact` | Contact | Contact controller and linked party semantics | technically yes | no | no | Global cross-party effect; separate promotion task. |
| `user`, Google fields, status, image, address, custom fields | Contact | native/installed features | mixed | mixed | no | Not required for the bounded Customer Contact use case. |

### Name, full-name, and rename distinction

Changing the six selected parent fields changes the derived `full_name` during
`validate()`. It does not rerun `autoname()` on update, so the persisted Contact
`name` stays stable. Frappe permits Contact rename (`allow_rename=1`), but rename
is a separate operation with Dynamic Link and reference consequences; it is not
part of detail editing and must not be exposed by Task 59. The preview should
show old/new `full_name` and the unchanged Contact reference.

Changing person/company fields can affect duplicate suspicion and future
selection. It does not rewrite historical Sales transactions. On any save,
`set_user()` may populate an empty Contact `user` when the primary email
matches a User; Task 59 must not expose or directly mutate that field and must
document this native possibility as an unverified side effect for a live
record.

## 7. Email child-table behavior

| Operation | Native behavior | Permission | Stale state | Recommended public semantic | V1/defer |
|---|---|---|---|---|---|
| Add first | Append one row; `set_primary_email()` marks the sole row primary and derives `email_id`. | Customer read + Contact write | Parent modified + complete email-row fingerprint | `add_email`; preview says it becomes primary. | V1 |
| Add secondary | Append row with `is_primary=0`; existing primary remains. | Customer read + Contact write | Parent modified + all relevant row names/flags/values | `add_email` with `make_primary=false`. | V1 |
| Replace current primary value | Mutate the selected primary child row in place; native validation derives parent projection. No native global uniqueness check. | Customer read + Contact write; Customer write if target is Customer primary | Selected row name/value/primary + parent modified | `replace_primary_email`; current value is required when more than one row exists. | V1 |
| Promote secondary | Set selected row `is_primary=1` and every other row `0`; preserve rows. | Customer read + Contact write; Customer write if target is Customer primary | All email child row names/values/flags + parent modified | `set_primary_email`; exact child selection required. | V1 |
| Remove secondary | Omitting the row from a normal save deletes it; no special native helper. | Customer read + Contact write | Selected row name/value/flag + parent modified | Explicit remove action only. | Defer |
| Remove primary | Remaining rows are not automatically promoted; parent `email_id` becomes empty if no row remains primary. | Same as remove secondary, plus Customer write if primary projection would be affected | Same, plus resulting primary state | No V1 remove/clear semantics; require a later explicit replacement/fallback design. | Defer |
| Exact duplicate on same Contact | Child metadata/controller do not reject duplicate rows. `add_email()` avoids an exact database duplicate, but direct append/save can represent one. | Contact write | Current row set | Return idempotent success if the exact email is already present and requested state is already satisfied; otherwise `CONTACT_DUPLICATE_SUSPECTED`. | V1 policy |
| Exact email on another Contact | No global uniqueness enforcement. | Contact write | Scoped visible duplicate candidate set | Do not merge. If an exact duplicate is visible in the target Customer scope, return `CONTACT_DUPLICATE_SUSPECTED` requiring explicit continuation/selection; do not enumerate unrelated parties. | V1 policy |

Email values are validated as Email fields. Whitespace is stripped when the
primary parent projection is assigned (`d.email_id.strip()`), but the child
row itself is not a canonicalized uniqueness key. Case-insensitive comparison
is appropriate for MCP duplicate detection because the existing email service
uses `casefold()` (`services/common/email.py:108-116`); it is not a claim that
Frappe rewrites stored child values.

The safest meaning of “change primary email” is to distinguish replacement
from promotion. Replacement mutates the selected existing child row and
preserves row identity. Promotion changes only primary flags and keeps the old
primary as a secondary row. The service must not infer which one the user
meant.

## 8. Phone child-table behavior

| Operation | Native behavior | Permission | Stale state | Recommended public semantic | V1/defer |
|---|---|---|---|---|---|
| Add first mobile | Append a row; only `is_primary_mobile_no=1` derives `mobile_no`. A first row is not automatically primary. | Customer read + Contact write; Customer write if primary projection refresh | Parent + row fingerprint | `add_phone(kind="mobile", make_primary=true|false)`; require explicit primary choice when no mobile primary exists. | V1 |
| Add secondary phone/mobile | Append with one or both flags false; parent projections remain unchanged. | Customer read + Contact write | Parent + row fingerprint | `add_phone(kind="phone"|"mobile", make_primary=false)`. | V1 |
| Replace primary phone | Mutate the row carrying `is_primary_phone=1`; native save derives `phone`. | Customer read + Contact write; Customer write if primary | Selected row name/value/flags + parent modified | `replace_primary_phone`. | V1 |
| Replace primary mobile | Mutate the row carrying `is_primary_mobile_no=1`; native save derives `mobile_no`. | Customer read + Contact write; Customer write if primary | Selected row name/value/flags + parent modified | `replace_primary_mobile`. | V1 |
| Promote secondary phone/mobile | Set the selected flag on one row and clear that flag on the others. The two flag families are independent. | Customer read + Contact write; Customer write if primary | All affected row names/values/flags + parent modified | `set_primary_phone` or `set_primary_mobile`; “phone” and “mobile” must be explicit. | V1 |
| Same row as primary phone and mobile | Native controller permits both independent flags; both parent projections become the same value. | Contact write; Customer write if Customer primary and either projection changes | Full affected row set | Do not expose a `both` public kind in V1. It can occur natively and must be preserved/read, but user intent must name one projection. | V1 read / write defer |
| Remove phone/mobile | Omitting a row deletes it; no automatic fallback is selected. Clearing one flag can leave the other projection intact. | Contact write; Customer write if Customer primary projection changes | Row name/value/flags + parent modified | No V1 removal or clear-primary action. | Defer |
| Duplicates | No Contact-wide or cross-Contact uniqueness enforcement. Formatting variants are not canonicalized by the Contact controller. | Contact write | Relevant row set | Use Task 57's normalized comparison only to detect a scoped duplicate suspicion; do not silently merge or rewrite format. | V1 policy |

Phone and mobile are not one field with a type. They are two independent
primary projections over the same `phone_nos` rows. A request saying “change
phone” must therefore return `needs_input` when both a primary phone and a
primary mobile exist and the intended projection is not explicit.

## 9. Child-row identity strategy

The server must resolve and bind the child `name` internally. For each selected
email or phone operation, approval state should include:

```text
parent Contact name
child doctype and parentfield
child row name
current child value
current primary flags
parent modified
complete affected-row fingerprint
target value and requested primary action
```

Child row names should not be required in the public LLM-facing input. Public
input should use a stable semantic selector: an exact current value is
acceptable only when it selects one row; otherwise the tool returns
`needs_selection` with the minimum permitted candidate rows. At confirm, the
server re-loads the Contact and checks both the row name and current value.

This prevents a mutable value from silently selecting a different row after
prepare, while avoiding unnecessary exposure of internal child identifiers.

## 10. Customer-scoped authorization and shared Contacts

Every update requires:

```text
Customer reference
+ exact Contact reference
+ normal Customer read permission
+ normal Contact read/write permission
+ Contact.has_link("Customer", customer.name)
```

Fuzzy Contact name resolution without a Customer is not an update boundary.
The target link must exist at prepare and confirm. A link added after prepare
is stale unless the requested operation was already fully idempotent; a link
removed after prepare is `CONTACT_STALE_STATE` and must be re-prepared.

For Task 59, any additional party link is a hard V1 block:

| Contact relationship | Detail update | Email update | Mobile/phone update | Primary promotion |
|---|---|---|---|---|
| One Customer only | Permit with preview | Permit with preview | Permit with preview | Separate task |
| Multiple Customers | Reject `CONTACT_SHARED_WITH_OTHER_PARTIES` | Reject | Reject | Separate task |
| Customer + Supplier/other party | Reject | Reject | Reject | Separate task |

The preview may say “linked to the target Customer and N other parties” only
if that count is permission-safe. It must not return unrelated party names or
links. This is Option B from the task: rejecting shared Contact updates in V1
is safer than changing a record for parties outside the explicit request.

## 11. Customer projection refresh

ERPNext Customer has a writable `customer_primary_contact` Link and read-only
stored fetch fields:

```text
email_id  <- customer_primary_contact.email_id
mobile_no <- customer_primary_contact.mobile_no
first_name <- customer_primary_contact.first_name
last_name  <- customer_primary_contact.last_name
```

The Customer JSON explicitly tells users to reselect the Contact after it is
edited. Contact validation does not load and save linked Customers. Therefore a
Contact-only save leaves these stored Customer values potentially stale.

`BaseDocument.get_invalid_links()` fetches link projections while a document
with a Link field is being validated (`apps/frappe/frappe/model/base_document.py:1024-1065`).
A normal `Customer.save(ignore_permissions=False)` with the existing
`customer_primary_contact` therefore refreshes the fetch fields as part of
the native document lifecycle. This conclusion is source verified; it was not
reproduced by changing a live business record.

| Case | Customer touched? | Required permission | Recommended outcome |
|---|---:|---|---|
| Edited Contact is `customer_primary_contact` | yes | Customer read + write and Contact write | Prepare includes refresh; confirm saves Contact then Customer in one transaction. |
| Edited Contact linked but not Customer primary | no | Customer read + Contact write | Save Contact only; do not rewrite Customer projections. |
| Primary Contact, Customer write available | yes | both writes | Permit and return refreshed projection fields. |
| Primary Contact, Customer write absent | would become stale | Contact write is insufficient | Fail at prepare with `CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED`; no Contact write. |
| Customer link/reference changed after prepare | uncertain target | re-check both documents | Return `CONTACT_STALE_STATE`; do not guess. |

The future service must not use `frappe.db.set_value` to patch Customer
projection fields. It should set no read-only projection directly and should
use a normal Customer document save. The outer confirmation boundary owns the
single commit/rollback. If Customer save or any native hook fails, Contact and
Customer state must both roll back.

## 12. Existing-Contact primary promotion

Keep this as a separate later task.

`Contact.is_primary_contact` is not a per-Customer flag. On Contact validation,
setting it true locks every linked party document and demotes other primary
Contacts for every `(link_doctype, link_name)` on that Contact. Customer's
`create_primary_contact()` also ensures the configured
`customer_primary_contact` has `is_primary_contact=1`, but the stored Customer
Link and the Contact flag are distinct concepts (`customer.py:302-310`).

Promotion therefore needs a separate multi-document contract covering Customer
membership, global primary side effects, Customer projection refresh,
concurrency, and permissions. It must require Customer write + Contact write,
use native locking/save behavior, and never promote an unlinked Contact. It is
not necessary to edit Contact detail or communication rows safely.

## 13. CRM, email, and Sales interoperability

### CRM side effects

Normal Contact save runs `crm.api.contact.validate`, which can update primary
CRM Deal email/mobile snapshots. This is an expected native side effect and
must remain inside the same transaction. The preview should disclose a
bounded statement such as “native CRM contact snapshots may refresh”; it must
not expose Deal names or records. No MCP-specific permission bypass is needed
or allowed.

### Customer and email recipients

The MCP email service (`services/common/email.py:130-173, 176-269`) uses a
transaction's copied `contact_email` first. If absent, it uses the Customer's
stored `email_id` and then permitted linked Contact candidates. A changed
Contact therefore affects future fallback resolution after Customer primary
projection state is refreshed, but does not retroactively change a copied
transaction value.

### Sales transaction fields

ERPNext party detail resolution (`apps/erpnext/erpnext/accounts/party.py:313-352`)
selects the native default Contact and copies `full_name`, `email_id`,
`mobile_no`, and related values into transaction fields. The Accounts
Controller validates that a selected `contact_person` belongs to the party
(`apps/erpnext/erpnext/controllers/accounts_controller.py:645-653`). Quotation,
Sales Order, and Sales Invoice contain `contact_person`, `contact_display`,
`contact_email`, and `contact_mobile` fields and their normal set-missing flows.

The result is:

- existing Quotation/Sales Order/Sales Invoice contact snapshots are not
  rewritten by Contact save;
- future documents may derive changed Contact values through native default
  Contact/party resolution;
- the update service must not update historical transactions or their copied
  recipient fields.

## 14. Permission matrix

No role names are part of the contract. The service must use document
permission APIs and normal save behavior.

| Operation | Required normal permission |
|---|---|
| Select Contact in Customer context | Customer read + Contact read |
| Update parent details | Customer read + Contact write |
| Add/change/promote email row | Customer read + Contact write |
| Add/change/promote phone/mobile row | Customer read + Contact write |
| Update a Customer-primary Contact | Customer read + Customer write + Contact write |
| Refresh Customer projection | Customer write + Contact write |
| Existing Contact primary promotion | Customer write + Contact write; separate task |
| Remove/delete/link mutation | Not in V1; later task must re-audit native linked-document checks |

The runtime site has no independent child-row permissions. `Contact.has_permission`
and `Customer.has_permission`/normal `save()` are authoritative. No
`ignore_permissions=True`, `ignore_user_permissions=True`, raw child SQL, or
direct projection `db_set` is acceptable for Task 59.

## 15. Native helper/API comparison

| Native path | Behavior | Permission/autosave | Public MCP decision |
|---|---|---|---|
| `Contact.add_email()` | Exact DB duplicate check, append row, optional primary flag | `autosave=True` saves with `ignore_permissions=True` | Do not call as public seam; reproduce bounded append in loaded doc then normal save. |
| `Contact.add_phone()` | Exact DB duplicate check, append row, independent flags, optional autosave | Same unsafe autosave behavior | Do not call as public seam. |
| `Contact.set_primary_email()` | Native validation helper; sole row primary, rejects multiple primaries, derives parent | Runs through normal Contact validation | Reuse by normal `Contact.save()`, not by direct parent assignment. |
| `Contact.set_primary()` | Native validation helper for phone/mobile independently | Runs through normal Contact validation | Reuse by normal `Contact.save()`. |
| `Contact.validate_primary_contact()` | Locks linked party documents and demotes other primary Contacts | Native save side effect; global link scope | Do not trigger via V1 update because primary promotion is deferred. |
| `Customer.save()` | Normal validation fetches linked Contact projections and runs ERPNext hooks | Requires Customer write | Use only when edited Contact is Customer primary, in same outer transaction. |
| CRM `doc_events.Contact.validate` | Updates CRM Deal email/mobile snapshots | Runs with Contact save | Preserve; disclose bounded side effect. |
| Direct `frappe.db.set_value` | Bypasses document validation/child synchronization and can leave projections inconsistent | Not a public boundary | Prohibit for Contact/Customer business mutation. |

## 16. Public operation model

The alternatives were evaluated as follows:

| Option | Assessment | Decision |
|---|---|---|
| A. Generic `changes={...}` patch | Flexible but leaks arbitrary fields, child rows, read-only projections, and relationships. | Reject. |
| B. Typed operation list | Can express multiple actions but creates ordering, duplicate, stale-row, and partial-failure ambiguity. | Reject for V1. |
| C. One bounded intent per prepare | Clear user intent, small fingerprint, one native state transition, easy atomicity. | **Select.** |
| D. Separate detail and communication pairs | Semantically clear but doubles approval/registry/tool surface without a safety need when the operation is a typed discriminated union. | Reject as unnecessary. |

The exact future public tools are:

```text
prepare_contact_update
confirm_contact_update
```

They remain Sales-only and use the existing Task 57 `search_contacts`. They
must be registered in `contracts/masters/contact.py`,
`contracts/registry.py`, `remote_operations.py`,
`tools/masters/customer_contact.py` or a narrowly named sibling tool module,
Sales profile registration, REST fixed typed dispatch, `docs/TOOLS.md`, and
focused tests. Business logic belongs in a dedicated service module, not in
REST/MCP transport code.

## 17. Exact proposed contracts

The following is a design contract for Task 59, not production code in this
task. All public models should inherit the existing `PublicContractModel`
(`extra="forbid"`).

```text
ContactUpdateOperation =
  set_details(details: {first_name?, middle_name?, last_name?, company_name?,
                        designation?, department?})
  | add_email(email, make_primary: bool = false)
  | replace_primary_email(current_email, email)
  | set_primary_email(email)
  | add_phone(phone, kind: "phone" | "mobile", make_primary: bool = false)
  | replace_primary_phone(current_phone, phone)
  | replace_primary_mobile(current_mobile, phone)
  | set_primary_phone(phone)
  | set_primary_mobile(phone)
```

Recommended prepare input:

```text
{
  "customer": {"doctype": "Customer", "name": "..."},
  "contact": {"doctype": "Contact", "name": "..."},
  "operation": <one typed operation>
}
```

Rules:

- The Contact must already be linked to the Customer.
- `current_email`/`current_phone`/`current_mobile` are required for replace
  actions and must select exactly one current row.
- `set_primary_email` and the phone primary operations require an exact value
  that selects one row; ambiguous values return selection.
- `add_email` first-row primary behavior is native and is shown in preview.
- `add_phone` does not infer a primary flag; `make_primary` is explicit.
- Public input never contains `full_name`, `email_id`, `phone`, `mobile_no`,
  `links`, `is_primary_contact`, child row names, `user`, arbitrary fields, or
  `confirm=true` as approval.

Ready output:

```text
{
  "status": "ready",
  "approval_token": "opaque",
  "expires_in_seconds": 900,
  "preview": {
    "customer": CustomerReference,
    "contact": ContactReference,
    "full_name_before": "...",
    "full_name_after": "...",
    "operation": <typed bounded operation summary>,
    "selected_current_value": "..." | null,
    "proposed_value": "..." | null,
    "selected_row_is_primary": true | false | null,
    "resulting_primary_email": "..." | null,
    "resulting_primary_phone": "..." | null,
    "resulting_primary_mobile": "..." | null,
    "customer_projection_refresh": true | false,
    "crm_snapshot_refresh_may_occur": true | false,
    "other_party_link_count": 0
  },
  "interaction": InteractionDirective(kind=APPROVAL)
}
```

Confirm input remains only:

```text
{"approval_token": "opaque", "confirm": bool}
```

Confirm success should return a bounded `updated` result containing Customer
and Contact references, the selected operation summary, resulting primary
email/phone/mobile values, refreshed Customer projections when applicable,
and `idempotent`. It must not return raw Contact JSON, all links, all child
rows, CRM Deals, User data, comments, or addresses.

## 18. Error and interaction states

Use the existing `ToolError` envelope and shared `InteractionDirective`. Do not
add `approval_needed` or client-specific continuation identifiers.

| State/code | Meaning | Required continuation |
|---|---|---|
| `needs_selection` / `AMBIGUOUS_REFERENCE` | Multiple Contacts or child rows match | `SELECTION`, select one or cancel |
| `needs_input` / `CONTACT_EMAIL_AMBIGUOUS` or `CONTACT_PHONE_AMBIGUOUS` | User did not specify which communication projection/row | `INPUT`, provide exact current value/kind or cancel |
| `CONTACT_NOT_LINKED_TO_CUSTOMER` | Exact relationship is absent | Re-resolve/link separately; no update |
| `CONTACT_SHARED_WITH_OTHER_PARTIES` | V1 shared Contact block | User must use a single-target Contact or a later capability |
| `CONTACT_DUPLICATE_SUSPECTED` | Exact visible scoped target value exists elsewhere | `INPUT`/`SELECTION`; never merge silently |
| `CONTACT_EMAIL_NOT_FOUND` / `CONTACT_PHONE_NOT_FOUND` | Requested current child row is absent | Re-prepare |
| `CONTACT_INVALID_EMAIL` / `CONTACT_INVALID_PHONE` | Native validation rejects proposed value | `INPUT` with corrected value |
| `CONTACT_STALE_STATE` | Contact, Customer link, sharing, or parent modified state changed | Re-prepare |
| `CONTACT_CHILD_STALE_STATE` | Selected row value/flags/name changed or disappeared | Re-select and re-prepare |
| `CUSTOMER_PROJECTION_REFRESH_PERMISSION_REQUIRED` | Primary Contact edit cannot refresh stored Customer fields safely | Grant permission or do not edit |
| `PERMISSION_DENIED` | Normal Customer/Contact read or write denied | Terminal permission result |
| `CONFIRMATION_REQUIRED` | `confirm=false` or approval not interpreted by server | Shared approval continuation |
| `CONFIRMATION_UNAVAILABLE` / `STALE_CONFIRMATION` | Token expired, replayed, wrong site/user/action, or unavailable | Re-prepare |
| `updated` with `idempotent=true` | Requested state was already true | No additional user action |

The exact public typed unions should be added only in Task 59 after matching
the current registry's root-model conventions. The semantic states above do
not authorize the Agent or UI to infer approval; `APPROVE` must still pass the
existing `CONFIRM_WRITE` guard.

## 19. Approval and stale-state design

The approval payload must bind:

```text
site
authenticated user
Sales profile
action = customer_contact_update
Customer name and modified
Contact name and modified
Customer-Contact link existence
other-party link count and relevant relationship fingerprint
whether Contact is Customer.customer_primary_contact
selected operation and target values
selected child row name(s)
selected child row current values
selected child row primary flags
all affected child-row names/values/flags needed to prove primary uniqueness
duplicate candidate fingerprint for the target Customer scope
projected resulting primary values
```

Prepare must be non-mutating. Confirm must claim the shared approval
atomically with `ApprovalStore.claim_for_confirm_write()`, reload fresh
Customer and Contact documents, re-check permissions and Customer membership,
re-check the single-target/shared policy, compare Contact and Customer
`modified`, verify child names/current values/flags, rerun scoped duplicate
checks, and only then save.

Any of the following is stale and must not be guessed through: Contact or
Customer modified, Customer link removed, Contact becomes shared, selected row
removed/renamed/value-changed, primary flags changed, or a new scoped exact
duplicate appeared. The token remains bound to site/user/action and cannot be
reused.

## 20. Atomicity and idempotency

For non-primary updates:

```text
Contact.save(ignore_permissions=False)
```

For an edited Customer-primary Contact:

```text
Contact.save(ignore_permissions=False)
Customer.save(ignore_permissions=False)
```

The service must not commit inside either helper. The outer confirm boundary
must commit once only after both documents and native hooks succeed, and must
rollback both if either fails. CRM snapshot updates are part of the same
transactional native side effect.

Safe idempotency:

- add an email/phone already present with the requested flags: success with
  `idempotent=true`, no duplicate row;
- set a value that is already the requested primary: success with
  `idempotent=true`;
- set a detail field to its current value: success with
  `idempotent=true`, with no unnecessary save;
- replace with the same current value: only idempotent if the selected row and
  requested primary state still match.

Not idempotent through guessing:

- a removed selected row;
- a changed selected row;
- a new row that makes a value ambiguous;
- an operation whose Customer link or shared status changed.

## 21. Data minimization and duplicate policy

The minimum update preview is Contact/Customer references, full name before
and after, the selected current value, proposed value, selected primary flag,
resulting primary projections, Customer-refresh boolean, CRM-side-effect
boolean, and a count of other party links. It must not expose unrelated
Dynamic Links or party names.

Native Frappe permits duplicate email/phone values within a Contact and across
Contacts. MCP should not invent global uniqueness. It should:

- treat exact same-Contact state as idempotent when no state change is needed;
- reject a duplicate row creation on the same Contact unless the request is
  demonstrably idempotent;
- detect exact email and normalized-phone duplicates visible within the target
  Customer scope and return `CONTACT_DUPLICATE_SUSPECTED` requiring explicit
  resolution;
- never enumerate or block based on unrelated Contacts that the user cannot
  read;
- never merge Contacts or rewrite formatting as a side effect.

Task 57's `_normalised_phone()` removes non-alphanumeric characters for
matching. That is appropriate for bounded search/duplicate suspicion only. The
native stored phone value remains exactly the caller-provided validated value.

## 22. Destructive-operation decision

Task 59 should implement **add/replace/promote only**. It should not remove
email or phone rows and should not clear a primary projection. Native save
deletes omitted child rows, but the current Contact controller provides no
automatic fallback policy for removing a primary row. A later task may add
explicit removal with child-row name/value fingerprint, primary-row preview,
required replacement or explicit no-primary choice, and atomic Customer
projection handling.

## 23. Future implementation test matrix

Task 59 must add tests for:

### Resolution and security

- exact Customer + Contact membership succeeds;
- Contact not linked to Customer fails before write;
- link added/removed after prepare is stale;
- Customer read denied and Contact read denied;
- Contact write denied;
- shared Customer, multi-Customer, and Customer+Supplier Contacts are blocked;
- no unrelated party name/link is present in any result;
- global fuzzy Contact update resolution is unavailable.

### Parent details

- each six candidate fields changes through normal Contact save;
- `full_name` is recomputed;
- Contact document `name` remains unchanged;
- unchanged value is idempotent;
- stale Contact fails;
- invalid native field values fail without commit;
- native User auto-link possibility is not exposed as an MCP input.

### Email

- add first becomes primary;
- add secondary preserves primary;
- replace primary mutates the selected row rather than delete/recreate;
- secondary promotion clears the old primary flag;
- ambiguous duplicate current values require selection;
- same-Contact existing value is idempotent or a duplicate error as specified;
- scoped duplicate on another Contact returns `CONTACT_DUPLICATE_SUSPECTED`;
- invalid email is rejected by native validation;
- changed/removed child row returns `CONTACT_CHILD_STALE_STATE`;
- remove/clear operations are rejected as unsupported.

### Phone/mobile

- first mobile requires and respects explicit primary choice;
- primary phone and primary mobile are independently derived;
- replace primary phone and replace primary mobile select the correct flag;
- “change phone” with both projections requires input;
- same row carrying both native flags is preserved but cannot be newly
  requested as an ambiguous public `both` action;
- normalized formatting duplicate is detected only in the permitted scope;
- invalid phone is rejected by native validation;
- child-row stale state is rejected;
- remove/clear operations are rejected as unsupported.

### Customer projections and transactions

- editing Customer-primary Contact refreshes stored Customer email/mobile/name
  projections;
- non-primary Contact edit does not save Customer;
- missing Customer write permission blocks before Contact mutation;
- Contact + Customer failure rolls back both;
- CRM Contact validation hook remains active;
- existing Quotation/Sales Order/Sales Invoice copied contact fields do not
  change;
- future native party/contact resolution sees the updated values after state is
  consistent.

### Approval and registration

- prepare performs no mutation or commit;
- valid confirm performs one shared approval claim and normal save;
- wrong user/site/profile/action, replay, expiry, `confirm=false`, stale
  Contact, stale Customer, stale link, stale child row, and new duplicate are
  covered;
- Sales exposes search plus the update pair;
- Accounts/Purchase do not expose them;
- MCP and REST use the same typed handler;
- contract, remote-operation, tool, profile, catalog, and docs registration
  are all covered.

## 24. Limitations and unverified boundaries

- No Contact or Customer business record was inserted, updated, linked,
  deleted, or promoted during this audit. Native behavior is source-proven and
  metadata is runtime-verified, but live mutation/rollback/hook results remain
  unverified.
- Runtime metadata is from `praveg.localhost`; another site may add Property
  Setters, Custom Fields, permissions, overrides, or hooks.
- The installed CRM Contact validation hook is source/runtime registered, but
  its live Deal snapshot effect was not exercised.
- The direct `doc_events` runtime serialization query failed because of
  Frappe's tuple-keyed hook structure; the effective Contact hook is source
  verified and the installed CRM app is runtime verified.
- `bench version` remains unavailable until the damaged/untrusted
  `india_compliance` Git checkout is repaired by an authorized operator. No
  Git configuration or app state was changed.
- Task 57's internal commit behavior and broad link-count projection remain
  separate findings. This report does not modify them.
- This report does not prove live OAuth/HTTP readiness, queue behavior, email
  delivery, or browser behavior.

## 25. Exact next implementation task

The next task should be:

```text
Task 59 — Customer-Scoped Contact Detail and Communication Update Implementation
```

Task 59 should implement only the bounded operation set in Section 17, using
the existing Task 57 search/projection/approval/interaction/registry patterns,
with shared Contact rejection and Customer-primary projection refresh as
mandatory safety rules. It must not begin Contact primary promotion, removal,
unlink, delete, merge, arbitrary Dynamic Link edits, Supplier/Purchase
support, or generic lifecycle hardening.

## 26. Actions not performed

- No production Contact update tools were added.
- No Contact, Customer, CRM Deal, Sales transaction, child row, Dynamic Link,
  or permission record was modified.
- No migration, build, cache clear, service restart, or deployment command was
  run.
- No Task 57 code or unrelated dirty change was overwritten.
