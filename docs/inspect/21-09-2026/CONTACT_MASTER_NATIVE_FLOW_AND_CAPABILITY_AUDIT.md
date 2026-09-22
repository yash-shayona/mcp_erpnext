# Contact Master Native Flow and Customer-Linked Capability Audit

**Task:** 56 — Contact Master Native Flow and Customer-Linked Capability Audit
**Audit date:** 2026-09-21
**Primary profile:** `sales`
**Scope:** existing/new ERPNext Customer to Frappe Contact behavior
**Mode:** source and runtime audit only; no Contact capability was implemented

This report is based on the checked-out source and the effective metadata of the
read-only inspection site `praveg.localhost`. The installed source is the
authority; upstream documentation or GitHub branches were not used to override
it.

## 1. Executive summary

The current Customer capability already has a valid native initial-creation
path. `prepare_customer` flattens the narrow nested Contact input into the
Customer payload, stores that complete payload in the shared approval store, and
`confirm_customer` calls `frappe.get_doc(...).insert(ignore_permissions=False,
ignore_links=False, ignore_mandatory=False)` followed by the service-level
commit (`mcp_erpnext/services/masters/customer.py:250-261,
400-431,435-467`). ERPNext `Customer.on_update` then calls
`create_primary_contact`. When Contact details are present and there is no
existing primary Contact, `make_contact(self)` creates a native Contact linked
to the Customer, and Customer stores the resulting primary Contact reference
(`apps/erpnext/erpnext/selling/doctype/customer/customer.py:275-310,
928-970`).

The later-contact gap is real, but it is not a reason to treat Contact as a
scalar Customer field:

* `customer_primary_contact` is a Link to an already-existing Contact. Frappe
  validates that the referenced Contact exists, but the Customer controller does
  not verify that the Contact is linked to this Customer before marking it
  primary (`customer.py:302-310`; `frappe/model/base_document.py:985-1076`).
* Customer `email_id`, `mobile_no`, `first_name`, and `last_name` are stored
  fetch projections from `customer_primary_contact`, not independent Contact
  records (`customer.json:324-345,601-614`). They cannot represent “add a
  second person.”
* The generic lifecycle validator currently checks `DocField.read_only`, but it
  does not reject a field whose `fieldtype` is literally `Read Only`
  (`mcp_erpnext/services/common/lifecycle.py:196-243`). Runtime metadata
  reports the Customer projection fields as `fieldtype=Read Only` and
  `read_only=0`. Consequently, a generic scalar update can reach the native
  Customer controller. That is an existing lifecycle-boundary gap, not a safe
  Contact capability: with no primary it can accidentally create the Customer's
  first Contact, while with a primary it only reasserts that primary; it cannot
  add/link a selected additional person and does not enforce Customer-Contact
  relationship intent.

The exact native boundary for the next task is:

1. Create a new Contact with a Customer Dynamic Link in the Contact document and
   call normal `Contact.insert(ignore_permissions=False)`. Let Contact
   `autoname`, email/phone projection, duplicate-link cleanup, validation, CRM
   hooks, and primary-contact locking run normally.
2. Link an existing Contact by loading that Contact, checking
   `contact.has_link("Customer", customer_name)`, appending exactly one
   Customer Dynamic Link if absent, and calling normal
   `contact.save(ignore_permissions=False)`. Do not expose arbitrary
   `link_doctype` or mutate the Dynamic Link child DocType directly.
3. Do not expose existing-Contact promotion to primary in V1. The installed
   Frappe semantics make `Contact.is_primary_contact` global across every party
   linked to that Contact, while Customer `on_update` also marks a selected
   Contact primary without synchronizing the Customer link. This cross-party
   effect is too broad for a Customer-scoped public intent without an additional
   explicit design.

### Exact Task 57 recommendation

Implement only these public capabilities in the Sales profile:

* `search_contacts`: permission-aware, bounded search; Customer-scoped name
  search and exact global Contact identity/email/phone lookup only.
* `prepare_customer_contact`: one bounded business intent with explicit
  `mode=create|link`, Customer reference, and either new Contact details or an
  existing Contact reference. It may accept `make_primary` only for a newly
  created Contact whose only public link is the target Customer; default it to
  false for a new Contact unless the product explicitly chooses native
  Customer-primary creation semantics.
* `confirm_customer_contact`: shared pending-approval confirmation. It must use
  the existing approval store and `claim_for_confirm_write`, never a caller
  supplied approval flag.

Defer `prepare_contact_update`/`confirm_contact_update`, email/phone row
replacement/removal, existing-Contact promotion to primary, unlink, delete,
merge, Supplier Contact behavior, and arbitrary Dynamic Link mutation to later
tasks. Task 57 can still return the bounded Contact reference and linked-party
count needed for a safe result without exposing unrelated party names.

## 2. Repository/app versions and source inspected

### Repository state

The bench root is not a Git repository. The relevant app repositories were
inspected directly:

| Component | Branch | HEAD inspected | Version evidence |
|---|---|---|---|
| `mcp_erpnext` | `master` | `bf2ccb1ea2e0444ecfaf026957629555abe39d94` | source checkout |
| Frappe | `version-16` | `c1f1e8ec3708750d7254f7f99d869ffb9886f19f` | Frappe 16.34.0 |
| ERPNext | `version-16` | `12cd563fb9a79731f75ae2a45b1446a0a2dd9e74` | ERPNext 16.35.0 |
| CRM | `develop` | `c8ed011ebd8823bbcb45067c4d533e21bef00212` | CRM 2.0.0-dev |
| HRMS | `version-16` | `7e0fba4bf11a63ac7b21a717610e235310815c1a` | HRMS 16.19.0 |
| Praveg | `livecode` | `ed3cbfc66312e1dac818b7539caf8f86bf3c1ccb` | Praveg app checkout |

The `mcp_erpnext` worktree already contained the untracked task specification
`docs/tasks/audits/56_TASK_CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md`.
Frappe also had pre-existing untracked `frappe/locale/test.po` and
`frappe/twilio_whatsapp_notification/` paths. No existing production file was
modified by this audit.

The read-only command `./env/bin/bench --site praveg.localhost
execute frappe.get_installed_apps` reported:

```text
["frappe", "erpnext", "hrms", "crm", "praveg", "insights"]
```

India Compliance exists in the bench checkout but is not installed on the
inspected site. Its static hooks were checked for scope; they add Customer
validation/after-insert behavior but no Contact hook
(`apps/india_compliance/india_compliance/hooks.py:146-149`).

The installed versions were obtained by a read-only bench execution and were:

```text
site: praveg.localhost
frappe: 16.34.0
erpnext: 16.35.0
hrms: 16.19.0
crm: 2.0.0-dev
praveg: 0.0.1
insights: 3.11.0
```

### Installed optional Contact behavior

CRM is installed and changes the effective Contact boundary in two ways:

* `override_doctype_class` maps Contact to
  `crm.overrides.contact.CustomContact`, which subclasses the installed Frappe
  `Contact` without replacing its controller methods
  (`apps/crm/crm/hooks.py:135-138`; `apps/crm/crm/overrides/contact.py:1-65`).
* CRM adds `crm.api.contact.validate` to Contact validation
  (`apps/crm/crm/hooks.py:144-147`). That hook updates the email/mobile snapshot
  of primary linked CRM Deals using `frappe.db.set_value`
  (`apps/crm/crm/api/contact.py:5-26`). A future Contact write must therefore
  use normal Contact document validation and account for this same-transaction
  side effect.

## 3. Current MCP Customer capability baseline

The current public Customer creation contract is intentionally narrow:

* `CustomerContactInput` exposes only `first_name`, `last_name`, `email`, and
  `mobile` (`mcp_erpnext/contracts/masters/customer.py:12-23`).
* `CONTACT_FIELD_MAP` maps these to Customer fields
  `first_name`, `last_name`, `email_id`, and `mobile_no`
  (`mcp_erpnext/config/masters/customer.py:21-27`).
* `_customer_data` performs that flattening and does not build a Contact child
  table or call a Contact helper (`mcp_erpnext/services/masters/customer.py:208-261`).
* `_create_permissions` requires Customer create and conditionally Contact
  create when those flattened values are present
  (`customer.py:351-363`).
* `prepare_customer` validates and previews without inserting a business
  record; `confirm_customer` rechecks permission/duplicates, claims the shared
  approval, inserts normally, commits once, and rolls back on failure
  (`customer.py:400-467`).

Customer reads are also bounded. The read service allowlist includes stored
Customer projections `email_id` and `mobile_no`, checks document permission for
exact reads, and uses `frappe.get_list(..., ignore_permissions=False)` for
queries (`mcp_erpnext/services/masters/customer_read.py:19-37,133-161`).
There is no Contact-specific public tool or Contact in the current registry.

The shared lifecycle service exposes Customer in the Sales profile for update,
child-add, submit/cancel/delete action maps
(`mcp_erpnext/services/common/lifecycle.py:19-49`). Sales registration includes
the Customer tools, lifecycle tools, Customer reads, and email tools but no
Contact tools (`mcp_erpnext/profiles/sales.py:8-38`; `tools/__init__.py:35-67`).
REST parity is explicitly registry-based; Sales handlers for Customer and
shared lifecycle operations are in `mcp_erpnext/remote_operations.py:300-334`
and `650-654`, while public contract metadata is in
`mcp_erpnext/contracts/registry.py:308-334`.

Relevant existing tests cover bounded Customer preparation, duplicate
Customer detection, Customer reads, lifecycle profile restrictions, REST typed
dispatch, and native Contact recipient fallback. They do not yet cover the
Customer-linked Contact capability described here.

## 4. Current Customer + nested Contact creation call chain

The current call chain is:

```text
CustomerPrepareInput
  -> CustomerContactInput
  -> to_service_payload()
  -> _customer_data()
  -> flattened Customer payload:
       first_name / last_name / email_id / mobile_no
  -> prepare_customer()
  -> ApprovalStore.create(action="create_customer", site, user, payload)
  -> confirm_customer(token, confirm=True)
  -> ApprovalStore.claim_for_confirm_write()
  -> frappe.get_doc(Customer payload)
  -> Customer.insert(ignore_permissions=False, ignore_links=False, ...)
  -> Customer.on_update()
  -> Customer.create_primary_contact()
  -> make_contact(self)
  -> Contact.insert()
  -> Customer.db_set(customer_primary_contact, Contact.name)
  -> Customer.db_set(mobile_no/email_id, effective values)
  -> outer frappe.db.commit()
```

The Contact side effect is not implemented by MCP. It is entirely in
ERPNext's Customer controller:

* `Customer.on_update` invokes `create_primary_contact`
  (`apps/erpnext/erpnext/selling/doctype/customer/customer.py:275-310`).
* If no primary Contact exists, the Customer has no Lead source, and any of
  `mobile_no`, `email_id`, `first_name`, or `last_name` is present, it calls
  `make_contact(self)`.
* `make_contact` creates a Contact payload with
  `is_primary_contact=1` and one Dynamic Link row containing the Customer
  (`customer.py:928-954`). It adds email and mobile through Contact helpers,
  copies first/last name overrides, then calls normal Contact insert
  (`customer.py:956-970`).
* Customer stores the created Contact name and its current mobile/email values
  using `db_set` (`customer.py:302-308`).

### Creation cases

| Customer creation input | Native result |
|---|---|
| Customer name only | No Contact is created because the four trigger fields are empty. |
| Email only | A primary Contact is created. Company customers get `company_name=customer_name`; Individual customers get parsed name values from `customer_name`. Email is a primary `Contact Email` row. |
| Mobile only | A primary Contact is created with a primary-mobile `Contact Phone` row. |
| First/last name only | A primary Contact is created; the Contact name is derived by Contact `autoname`. |
| Email/mobile/name plus existing `customer_primary_contact` | `create_primary_contact` takes the existing-contact branch and marks that referenced Contact primary; it does not create a second Contact. |

Contact first name, email, mobile, and link fields are not mandatory in the
installed Contact metadata. Customer `customer_type` is mandatory with default
`Company`; Customer name is mandatory
(`praveg.localhost` runtime query; static `customer.json:1-16,114-172` and
`contact.json:51-76,184-207,243-253`).

### Atomicity

`Customer.insert()` runs controller hooks and the nested Contact insert in the
same Frappe database transaction. The Contact insert is not caught or committed
by ERPNext. The current MCP confirmation then commits once after the full insert
chain and explicitly rolls back on any exception
(`mcp_erpnext/services/masters/customer.py:458-467`). Therefore a Contact
validation/permission failure should roll back the Customer in this MCP path.
This is source/transaction evidence, not a live failure-injection test.

## 5. Current Customer update limitation/root cause

### Runtime metadata

The effective `praveg.localhost` metadata query reported:

| Field | Fieldtype | Options | reqd | `read_only` property | `fetch_from` | hidden |
|---|---|---|---:|---:|---|---:|
| `customer_primary_contact` | Link | Contact | 0 | 0 | — | 0 |
| `mobile_no` | Read Only | Mobile | 0 | 0 | `customer_primary_contact.mobile_no` | 0 |
| `email_id` | Read Only | Email | 0 | 0 | `customer_primary_contact.email_id` | 0 |
| `first_name` | Read Only | — | 0 | 0 | `customer_primary_contact.first_name` | 1 |
| `last_name` | Read Only | — | 0 | 0 | `customer_primary_contact.last_name` | 1 |

The metadata is consistent with static `customer.json:324-345,601-614`. The
`Read Only` fieldtype is a stored fetch projection, not a live SQL join.

### Generic lifecycle behavior

`_validate_change` rejects fields with `meta.read_only`, system fields, table
fields, and a set of layout fieldtypes. It checks Link values with a
permission-aware `frappe.get_list` lookup, but does not reject `fieldtype ==
"Read Only"` (`mcp_erpnext/services/common/lifecycle.py:196-250`). Runtime
metadata reports the five relevant fields with `read_only=0`, so the current
generic validator does not reject them on either criterion.

This produces three different behaviors:

1. `customer_primary_contact = "existing-contact-name"` can pass generic Link
   existence validation if the Contact is visible to the user. The validator
   does not check the Contact's Dynamic Link back to the Customer. Saving the
   Customer invokes `Customer.create_primary_contact`, which calls
   `frappe.set_value("Contact", contact, "is_primary_contact", 1)`; it does not
   add the Customer link (`customer.py:302-310`). This can create an incorrect
   Customer-to-Contact association and can affect another party linked to that
   Contact.
2. `email_id`, `mobile_no`, `first_name`, or `last_name` can technically reach
   Customer save because their effective `read_only` property is zero. If the
   Customer has no primary Contact, the native Customer controller may create
   the first Contact from those values. If a primary Contact already exists,
   the controller does not create a new person; it only reasserts the selected
   primary Contact. This accidental path does not support adding a separate
   linked Contact or selecting an existing Contact.
3. A scalar `Table` value cannot be used for `Contact.links`, `email_ids`, or
   `phone_nos`: the lifecycle service rejects table fields as scalar updates
   (`lifecycle.py:218-223`). Even if that guard were removed, Contact-specific
   validation and primary-row semantics would be bypassed by an unconstrained
   generic table mutation contract.

### Root-cause classification

The observed gap is **both**:

* an existing generic-lifecycle boundary bug/gap, because the validator does
  not treat the `Read Only` fieldtype as non-writable and does not validate
  Customer-Contact membership; and
* a missing dedicated Customer-linked Contact capability, because adding a
  person requires Contact creation or Dynamic Link mutation, child email/phone
  semantics, duplicate handling, and an explicit approval-bound business
  intent.

The correct fix for Task 57 is not to broaden generic Customer updates. Contact
creation/linking must use a dedicated, Customer-scoped service. A separate
future task may decide whether generic lifecycle should reject all `Read Only`
fieldtypes; that unrelated hardening is not part of Task 56.

## 6. Runtime Customer metadata relevant to Contact

The runtime query on `praveg.localhost` found:

* `customer_type`: mandatory Select, options `Company`, `Individual`,
  `Partnership`, default `Company`.
* `customer_name`: mandatory Data, `no_copy=1`.
* `customer_primary_contact`: Link to Contact, not mandatory, not read-only.
* `mobile_no` and `email_id`: Read Only stored projections fetched from the
  selected Contact.
* `first_name` and `last_name`: hidden Read Only stored projections fetched from
  the selected Contact.
* `lead_name`: read-only Link to Lead and is excluded from generic public
  Customer creation.

`Customer.on_update` and `make_contact` are the authoritative native behavior;
the Customer JSON only describes the fields and fetch metadata. The Customer
form query for `customer_primary_contact` is Customer-scoped through
`erpnext.selling.doctype.customer.customer.get_customer_primary`, which joins
Contact/Dynamic Link rows to the current Customer
(`apps/erpnext/erpnext/selling/doctype/customer/customer.js:75-83`; backend
`customer.py:1012-1035`). The generic API does not inherit that UI query filter.

## 7. Runtime Contact metadata

The effective installed Contact metadata reported:

| Field | Fieldtype | Options | reqd | read-only property | hidden | authority |
|---|---|---|---:|---:|---:|---|
| `first_name` | Data | — | 0 | 0 | 0 | caller input for a person, then native full-name calculation |
| `middle_name` | Data | — | 0 | 0 | 0 | caller input if supported later |
| `last_name` | Data | — | 0 | 0 | 0 | caller input for a person |
| `full_name` | Data | — | 0 | 1 | 1 | Frappe-derived from name fields/company |
| `company_name` | Data | — | 0 | 0 | 0 | caller input only if a company-only Contact is intentionally supported |
| `designation` | Data | — | 0 | 0 | 0 | caller input in a later detail capability |
| `email_id` | Data | Email | 0 | 1 | 0 | Frappe-derived from primary email child row |
| `phone` | Data | Phone | 0 | 1 | 0 | Frappe-derived from primary-phone child row |
| `mobile_no` | Data | Phone | 0 | 1 | 0 | Frappe-derived from primary-mobile child row |
| `email_ids` | Table | Contact Email | 0 | 0 | 0 | native child rows; not scalar input |
| `phone_nos` | Table | Contact Phone | 0 | 0 | 0 | native child rows; not scalar input |
| `links` | Table | Dynamic Link | 0 | 0 | 0 | Customer-scoped native relationship input |
| `is_primary_contact` | Check | — | 0 | 0 | 0 | native Contact primary flag, global over the Contact's links |

These values are confirmed by runtime metadata and static
`apps/frappe/frappe/contacts/doctype/contact/contact.json:51-207,243-267`.
There is no framework-required Contact first name, email, phone, or Dynamic
Link. Task 57 should nevertheless require a target Customer and either a
non-empty person/company identity or a permitted exact existing Contact
reference; it should not make a nameless, unlinked Contact publicly creatable.

## 8. Contact Email child-table semantics

The effective `Contact Email` metadata is:

| Field | Fieldtype | Options | reqd | read-only |
|---|---|---|---:|---:|
| `email_id` | Data | Email | 1 | 0 |
| `is_primary` | Check | — | 0 | 0 |

This is defined in `apps/frappe/frappe/contacts/doctype/contact_email/contact_email.json:7-29` and confirmed by runtime metadata. The child table has no standalone
permissions; its parent Contact controls read/write access.

`Contact.validate` calls `set_primary_email` before saving
(`contact.py:65-75`):

* no rows clears parent `Contact.email_id`;
* one row automatically becomes primary;
* more than one primary row raises a validation error;
* one primary row copies its trimmed email to parent `email_id`;
* rows can exist with no primary, in which case parent `email_id` is empty.

`add_email` checks for an exact existing child row and appends only when absent
(`contact.py:154-160`). Its `autosave=True` path calls
`save(ignore_permissions=True)`, so it is suitable as a local append helper
inside a native creation preparation only when the outer insert still enforces
normal permission, but it is not suitable as a public write seam with
`autosave=True`. Task 57 should construct bounded child rows and call normal
Contact insert; Task 58 should use normal Contact save after an exact stale
check, not a permission-bypassing helper.

Email validity is enforced by Frappe Data-field validation for fields with
`options="Email"` (`apps/frappe/frappe/model/base_document.py:1131-1169`).
There is no native Contact-level duplicate merge or identity policy; duplicate
email rows are only prevented by `add_email`'s exact in-document/database
lookup, not by a global Contact uniqueness constraint.

## 9. Contact Phone child-table semantics

The effective `Contact Phone` metadata is:

| Field | Fieldtype | Options | reqd | read-only |
|---|---|---|---:|---:|
| `phone` | Data | Phone | 1 | 0 |
| `is_primary_phone` | Check | — | 0 | 0 |
| `is_primary_mobile_no` | Check | — | 0 | 0 |

The static definition is
`apps/frappe/frappe/contacts/doctype/contact_phone/contact_phone.json:7-39`;
runtime metadata matches it. `Contact.validate` independently calls
`set_primary("phone")` and `set_primary("mobile_no")`
(`contact.py:65-75,196-220`):

* zero phone rows clears both parent projections;
* at most one row may have `is_primary_phone=1`;
* at most one row may have `is_primary_mobile_no=1`;
* the same child row may carry both flags because the controller validates the
  two flags independently;
* absence of a flag clears the corresponding parent projection;
* exact duplicate child numbers are skipped by `add_phone`, but there is no
  global Contact phone uniqueness rule.

Frappe validates `Phone` options with its normal phone validator
(`base_document.py:1142-1169`). `add_phone` has the same permission-bypassing
`autosave=True` behavior as `add_email` (`contact.py:161-173`). Public tools
must never accept parent `phone`, `mobile_no`, or `email_id` as authoritative
independent scalars; they must let the Contact controller derive them from
child rows.

## 10. Dynamic Link semantics

The Dynamic Link child DocType contains exactly:

| Field | Fieldtype | Options | reqd | read-only |
|---|---|---|---:|---:|
| `link_doctype` | Link | DocType | 1 | 0 |
| `link_name` | Dynamic Link | `link_doctype` | 1 | 0 |
| `link_title` | Read Only | — | 0 | 1 |

This is defined in
`apps/frappe/frappe/core/doctype/dynamic_link/dynamic_link.json:7-35` and
confirmed at runtime. Frappe's `deduplicate_dynamic_links` removes repeated
`(link_doctype, link_name)` pairs within one Contact document during Contact
validation (`apps/frappe/frappe/core/doctype/dynamic_link/dynamic_link.py:32-44`;
called from `contact.py:73-75`). It is not a global database uniqueness
constraint.

Contact exposes native relationship helpers:

* `has_link(doctype, name)` checks an exact in-memory pair
  (`contact.py:143-146`);
* `get_link_for(doctype)` returns the first link for a type
  (`contact.py:135-141`);
* `get_contacts_linking_to(doctype, docname, fields)` uses a permission-aware
  `frappe.get_list` filter over Dynamic Link
  (`contact.py:489-498`);
* `get_default_contact` prefers a primary Contact for a party and otherwise
  returns no default in the current implementation of ERPNext
  (`apps/erpnext/erpnext/accounts/party.py:1065-1090`).

One Contact can carry multiple links, including multiple Customers and a mix of
Customer/Supplier links. This is the reason a public “link Contact to Customer”
intent must hard-code `link_doctype="Customer"` server-side. The caller must
not provide arbitrary Dynamic Link types.

The safest existing-link mutation is an ordinary Contact document mutation:

```python
contact = frappe.get_doc("Contact", contact_name)
if not contact.has_link("Customer", customer.name):
    contact.append("links", {"link_doctype": "Customer", "link_name": customer.name})
    contact.save(ignore_permissions=False)
```

This follows ERPNext's own `Customer.link_address_and_contact` pattern, which
loads linked documents, checks `has_link`, appends a Customer link, and saves
the parent document (`apps/erpnext/erpnext/selling/doctype/customer/customer.py:330-356`).
The ERPNext helper uses `ignore_permissions=self.flags.ignore_permissions` because
it is a controller-internal migration/link-forwarding operation; Task 57 must
not inherit an ignore-permissions flag from that internal path.

An identical link should be treated as idempotent success in a prepared
operation, with `idempotent=true` and no Contact save. A link added after
prepare must either be detected as the expected idempotent final state or cause
the approved operation to be re-evaluated; it must never append a duplicate row.

## 11. Contact naming/mandatory-input behavior

Contact has `naming_rule="By script"` and no mandatory parent fields in the
installed JSON (`contact.json:255-267`). Its controller:

1. computes `full_name` from first/middle/last, falling back to company name
   (`contact.py:221-222,514-524`);
2. sets `name` to that full name;
3. appends the first link name to the generated name when a link exists;
4. calls `append_number_if_name_exists` when the resulting name already exists
   (`contact.py:54-63`).

Therefore Contact names are unique through suffixing but are not identity.
Company-only Contacts are technically valid because `get_full_name` falls back
to `company_name`; no email/phone or Customer link is framework-required.

Task 57 business requirements should be stricter than the framework:

| Category | Task 57 decision |
|---|---|
| Framework-required | Target Customer must resolve and be readable; new Contact must pass native Contact validation; Contact child values must satisfy Email/Phone validators. |
| Capability-required | New Contact must carry a Customer Dynamic Link and a bounded identity (`first_name`, `last_name`, or an explicitly supported `company_name`); Contact create permission and Customer read permission are required. |
| Optional | Designation, middle name, secondary rows, arbitrary user/Google fields, and unrelated party links are not V1 inputs. |

Do not deduplicate by generated Contact name. Exact name collision only causes
Frappe to suffix the new Contact; exact email/mobile or Customer-link evidence
must drive reuse/ambiguity handling.

## 12. Native new Contact -> existing Customer flow

### Candidate comparison

| Candidate | Permission behavior | Native semantics | Decision |
|---|---|---|---|
| ERPNext `make_contact(customer)` | Normal Contact insert, but inherits caller Customer fields and internal primary behavior | Designed for Customer/Supplier creation; derives identity from the party name and makes it primary by default. It cannot represent a different person without mutating/translating Customer fields. | Reject for a new person on an existing Customer. |
| `Contact.add_email`/`add_phone` with autosave | `autosave=True` calls `save(ignore_permissions=True)` | Useful local append helpers, but public autosave bypasses Contact write/create permissions. | Do not use as public mutation seam. |
| `frappe.get_doc({...}).insert(ignore_permissions=False)` | Normal Contact create, Link validation, Contact controller, child inserts, CRM hook | Accepts a bounded Contact payload with one server-derived Customer Dynamic Link. Runs Contact `autoname`, child-table validation, dynamic-link deduplication, and primary locking. | **Recommended.** |
| Direct `frappe.db.insert`/child SQL | Bypasses controller validation, permissions, hooks, and naming | Can corrupt projections/rows. | Prohibited. |

### Recommended native seam

Task 57 should:

1. Resolve the exact Customer with normal read permission and require a target
   Customer reference, never only free-form display text at confirm time.
2. Require Customer write permission if the operation may set Customer primary;
   for link-only creation, require Customer read and Contact create, with the
   final policy kept explicit in the contract.
3. Search exact visible Contact email/mobile/name signals before preparing. If
   an exact visible match exists, return a duplicate/reuse selection state; do
   not create automatically.
4. Build a Contact payload with only permitted parent values, child email/phone
   rows, `links=[{"link_doctype":"Customer","link_name":customer.name}]`,
   and an explicit native primary choice.
5. Run `contact.run_method("validate")` during prepare only if this preserves
   effective native values without a write; otherwise use an unsaved Contact
   document and project only the bounded preview.
6. On confirm, recheck existence, permissions, duplicate/link state, and the
   approval fingerprint, then call normal `contact.insert(ignore_permissions=False)`.
7. Leave commit/rollback to the outer MCP confirmation service. The normal
   Frappe request transaction covers Contact, child rows, CRM validation hooks,
   and any optional Customer update.

If `make_primary` is later enabled for a new Contact, it must be an explicit
reviewed flag. A new Contact with only the target Customer link can safely use
the native `is_primary_contact=1` path with no other linked party, but the
service still needs a second normal Customer save to set
`customer_primary_contact`; that compound behavior should be separately tested.

## 13. Native existing Contact -> Customer linking flow

The authoritative relationship is a Dynamic Link row under the Contact, not a
Customer scalar and not an MCP-owned association table. The native flow is:

```text
resolve/read Customer
  -> resolve/read Contact
  -> require Contact.has_permission("write")
  -> require Customer.has_permission("read")
  -> Contact.has_link("Customer", customer.name)
  -> if absent: append {link_doctype: "Customer", link_name: customer.name}
  -> Contact.save(ignore_permissions=False)
```

The Customer write permission is required only when the operation also changes
`customer_primary_contact`; a link-only operation must not silently write the
Customer. The service should nevertheless verify Customer read permission to
keep the public intent Customer-scoped and avoid linking against an inaccessible
party.

Already-linked Contact behavior is idempotent success. Contact not found,
Customer not found, and normal read/write permission failure are terminal
user-correctable results. A Contact linked to another Customer is not inherently
invalid: one Contact can have many Dynamic Link rows. The service must preview
that there are other links without disclosing unrelated party names, and must
not auto-link based only on an email/name match.

The existing Contact may also be linked to Supplier. That is native-valid, but
because primary Contact state is global over the Contact's complete link set,
Task 57 must not promote an already cross-party Contact to primary. Supplier
Contact tools remain out of scope.

## 14. Primary Contact state-transition analysis

There are two fields with different storage responsibilities:

* `Contact.is_primary_contact` is a Contact-level flag. During validation it
  demotes every other primary Contact sharing **any** `(link_doctype,
  link_name)` pair with the saving Contact (`contact.py:80-129`). It locks all
  linked documents in stable doctype/name order before querying and demoting
  existing primaries, which serializes concurrent promotion for the linked
  parties.
* `Customer.customer_primary_contact` is a Customer Link field. The Customer
  controller, when this field is set, calls `frappe.set_value` to make the
  referenced Contact primary (`customer.py:302-310`). It does not add a missing
  Customer Dynamic Link or validate membership.

The native state transitions are:

| Starting state | Operation | Contact flags after | Customer link after | Other contacts after | Native path |
|---|---|---|---|---|---|
| Customer has no Contact; new Contact linked with `is_primary_contact=0` | Contact insert | New Contact false | Customer field unchanged | Existing primaries unchanged | Contact insert/validate |
| Customer has no primary; new Contact linked with `is_primary_contact=1` | Contact insert | New Contact true | Customer field still unchanged by Contact controller | Any existing primary linked to Customer is demoted | Contact `validate_primary_contact` |
| Customer has primary A; Contact B linked with flag 0 | Contact save | A remains true, B false | Customer still points to A | No demotion | `has_link` + Contact save |
| Customer has primary A; linked Contact B saved with flag 1 | Contact save | B true | Customer field remains whatever it was | Every primary Contact sharing any B link is demoted, including A if both link Customer | Contact lock/query/set_value path |
| Customer has existing linked B; Customer field set to B | Customer save | `Customer.on_update` sets B true; Contact validation then demotes other primaries sharing B's links | Customer field B; fetch projections refreshed during link validation | Other primary Contacts sharing B's full link set are demoted | Customer `on_update` -> `frappe.set_value(Contact,...)` |
| Customer field set to existing Contact X not linked to Customer | Customer save | X becomes primary globally over X's links | Customer field X, but Dynamic Link remains absent | Primaries sharing X's unrelated links may be demoted | Customer `on_update`; no membership check |
| Contact primary flag changed | Contact save | Contact controller does not write any Customer's `customer_primary_contact` field | Customer fields unchanged unless separately saved | Other linked primary flags may be demoted | Contact `validate_primary_contact` |
| Customer primary field cleared | Customer save | No Contact is demoted by `create_primary_contact` | Customer field cleared; projections may clear/fetch on save | Existing Contact flags unchanged | Customer controller |

`get_default_contact` selects a primary Contact for the party; the Contact list
helper orders primary Contacts before creation time
(`contact.py:317-339,527-566`). Primary is therefore not independently scoped
per Customer when one Contact has multiple party links. The native state is
fully source-proven, but its cross-party effect makes existing-Contact
promotion a deferred capability.

## 15. Email/phone mutation analysis

Parent Contact fields are projections. Child rows are authoritative:

```text
Contact.email_ids[*].email_id + is_primary -> Contact.email_id
Contact.phone_nos[*].phone + is_primary_phone -> Contact.phone
Contact.phone_nos[*].phone + is_primary_mobile_no -> Contact.mobile_no
```

The `Contact.validate` order is important: it derives all three parent values,
sets a User from primary email when applicable, sets Dynamic Link titles,
deduplicates Dynamic Links, and validates primary-contact state
(`contact.py:65-75,131-194`). Updating a parent projection directly would be
overwritten or would leave child rows inconsistent.

The future public operation matrix is:

| Operation | Native support | V1 decision |
|---|---|---|
| Replace primary email | Set one child row primary and save; controller rejects multiple primaries | Defer to Task 58 because deletion/replacement and stale child-row identity need a dedicated contract. |
| Add secondary email | Append one child row with `is_primary=0`; exact duplicate should be a no-op/selection result | Defer. |
| Remove email | Remove child row, then controller may clear parent projection or select remaining primary | Defer; destructive and needs explicit fallback semantics. |
| Replace primary mobile | Set one phone row `is_primary_mobile_no=1`, clear that flag on others, save | Defer. |
| Add secondary phone | Append one Contact Phone row with both primary flags false | Defer. |
| Remove phone | Remove child row and let controller recalculate phone/mobile | Defer; destructive and potentially changes transaction/email behavior. |
| Set primary phone and mobile on same row | Native controller permits both independent flags | Defer; contract must make this explicit if later supported. |

Existing CRM exposes `create_new` and `set_as_primary` methods that check
Contact write permission and call normal save, but they are CRM API behavior,
not a generic ERPNext Contact seam (`apps/crm/crm/api/contact.py:66-112`).
They also have a narrower field vocabulary and different UX assumptions. MCP
should not call them as a replacement for a Customer-scoped Contact service.

## 16. Duplicate/reuse analysis

The installed native signals are:

* exact Contact `name`;
* `full_name`, which is derived and collision-suffixed, so it is not identity;
* exact `Contact Email.email_id` child rows or parent primary projection;
* exact/normalized `Contact Phone.phone` child rows or parent projections;
* existing Customer Dynamic Link rows;
* the Contact's `modified` value for stale state.

Native helpers are not sufficient as a complete duplicate policy:

* `get_contact_name(email_id)` searches exact Contact Email rows but is not
  Customer-scoped (`apps/frappe/frappe/contacts/doctype/contact/contact.py:480-487`).
* `get_contact_with_phone_number(number)` uses a suffix `LIKE` query and returns
  only the first row, so it cannot decide identity safely
  (`contact.py:469-477`).
* Contact autoname only suffixes same generated names; it does not merge or
  reject duplicate people (`contact.py:54-63`).

### Recommended strategy

Use a bounded combination, not automatic merging:

1. For a Customer context, search visible Contact rows linked to that Customer
   by exact name/full-name token, exact normalized email, or exact phone. An
   exact existing link is an idempotent link result.
2. For a new Contact request, search visible exact email and exact normalized
   phone across Contacts. If a match exists but is not already linked to the
   target Customer, return `CONTACT_DUPLICATE_SUSPECTED` with a minimal
   selection candidate; do not create automatically.
3. A same name without exact email/phone/link evidence is not enough to reuse a
   Contact. Present it as an ambiguity candidate only when the user explicitly
   searches/selects it.
4. Never merge Contacts or silently copy data between Contacts.

## 17. Search/read/data-minimization analysis

The minimum useful read surface is one bounded `search_contacts` capability,
with Customer scope whenever possible. It should support:

* `customer`: exact Customer reference, optional for exact global identity
  lookup;
* `query`: bounded non-empty text;
* `match`: server-selected `name_or_full_name`, exact email, or exact phone;
* pagination with a small hard limit.

Recommended server behavior:

* fuzzy/name search requires a Customer context;
* global search without Customer context requires exact Contact name, exact
  email, or exact phone to prevent broad personal-data enumeration;
* every query uses normal Frappe permission-aware `frappe.get_list` or
  `get_contacts_linking_to`, never `ignore_permissions=True`;
* email and phone searches join/filter Contact Email and Contact Phone child
  tables, not only parent projections;
* Customer-scoped results require both Contact read visibility and Customer
  read visibility.

The output should be limited to:

| Output | Why needed | Sensitivity / rule |
|---|---|---|
| `doctype="Contact"`, `name` | Stable selection/approval reference | Business identifier; return only permitted rows. |
| `full_name` | User selection label | Personal/business identity; required for disambiguation. |
| `company_name` | Distinguishes organization-only contacts | Return only when present and permission allows. |
| `email_id` | Exact duplicate/reuse and recipient selection | Sensitive business contact data; only permitted candidate. |
| `mobile_no` and optionally `phone` | Exact duplicate/reuse and user confirmation | Sensitive; return only in bounded candidate output. |
| `is_primary_contact` | Shows native Customer-scoped default status | Boolean only; does not disclose other links. |
| `linked_to_target_customer` | Idempotent link result | Derived boolean. |
| `other_party_link_count` | Warns about cross-party primary side effects | Count only; do not return unrelated party names. |
| `modified` | Prepare/confirm stale fingerprint | Internal approval-bound value; do not expose unless contract needs a safe opaque state. |

Do not return full Contact JSON, all Dynamic Links, User, Google Contacts,
communications, comments, addresses, CRM Deals, child-row internals, or private
framework fields. The existing native `get_contact_display_list` is too broad
for an MCP default because it requests `fields=["*"]` and then loads secondary
emails, phones, and optionally a condensed Address
(`contact.py:527-566`). Reuse its permission principle, not its full projection.

## 18. Permission analysis

Effective runtime permissions on `praveg.localhost` reported no standalone
permissions for Contact Email, Contact Phone, or Dynamic Link; those child rows
are governed by the parent Contact permission. Contact has read/create/write
for the installed Sales roles, while Customer create/write is more restricted
to the installed Sales User and Sales Master Manager roles. Exact role rows are
site configuration and must not be hard-coded into MCP contracts.

The required checks are:

| Operation | Required normal permission |
|---|---|
| Search/read linked Contacts | Contact read and Customer read for Customer-scoped intent |
| Create new Contact for Customer | Contact create; Customer read; Customer write only if setting Customer primary |
| Link existing Contact | Contact write and Customer read; Customer write only if changing Customer primary |
| Update Contact details later | Contact write; also re-check target Customer context if the public operation is Customer-scoped |
| Update Customer primary | Customer write and Contact write because native Customer `on_update` writes Contact primary state |
| Unlink/delete later | Contact write/delete plus all native linked-document and transaction checks; deferred |

Normal `Contact.insert(ignore_permissions=False)` calls parent create
permission, link validation, Contact validation, child inserts, and hooks
(`apps/frappe/frappe/model/document.py:438-515`). Normal `Contact.save` calls
parent write permission, link validation, Contact validation, child-table
synchronization, and hooks (`document.py:555-618`). Task 57 must not use
`ignore_permissions=True`, `frappe.db.set_value` for the primary business
mutation, or direct child SQL.

The `Customer.link_address_and_contact` internal helper uses an inherited
`ignore_permissions` flag when saving linked documents
(`customer.py:351-356`). That is not a public MCP-safe seam. The MCP service
must make explicit normal permission checks and call normal document APIs.

## 19. Customer read interoperability

Customer `email_id`, `mobile_no`, `first_name`, and `last_name` are stored
fetch-from projections, not live joins. Frappe refreshes fetch values while
validating a link through `BaseDocument.get_invalid_links`
(`apps/frappe/frappe/model/base_document.py:1024-1065`), and Customer's own
JSON tells users to reselect the Contact if it is edited after save
(`customer.json:324-345`). Contact validation does not save the linked Customer.

Therefore:

1. Creating a Contact does not automatically populate
   `Customer.customer_primary_contact` unless the future service explicitly
   saves/sets that Customer field.
2. Editing a Contact's email/mobile later does not immediately refresh stored
   Customer projections. Subsequent MCP Customer reads can remain stale until
   the Customer link is reselected/saved through the native Customer path.
3. Changing Customer primary through a normal Customer save causes fetch values
   to be refreshed for that save and the controller marks the selected Contact
   primary.
4. MCP must keep exposing Customer projections as convenience fields, but must
   not create a second Contact state store or claim that they are authoritative
   after an unrelated Contact edit.

Task 57 result payloads should return the authoritative Contact fields from a
fresh permission-checked Contact document and, when relevant, state that
Customer projections are not independently updated by a Contact-only mutation.

## 20. Email capability interoperability

The existing MCP email service already uses native party/Contact resolution:

* it reads a permission-checked party's native `email_id`
  (`mcp_erpnext/services/common/email.py:119-127`);
* it enumerates Contacts through Frappe's
  `get_contacts_linking_to` with a bounded field list and then permission-checks
  each Contact (`email.py:130-173`);
* a transaction's copied `contact_email` is authoritative, preventing a later
  fallback to another Contact (`email.py:191-207`);
* if no transaction Contact is selected, Customer/Supplier's native primary
  email is preferred before linked Contact candidates (`email.py:209-231`).

A new Contact linked to a Customer becomes eligible for fallback only when it
has a valid email and the native resolution order reaches linked Contacts. A
new primary Contact is preferred only after the relevant Customer primary
projection/default is native-consistent. Existing Sales Orders, Quotations, and
Sales Invoices retain their copied Contact/email values; a later Contact edit
must not rewrite historical transaction snapshots.

Required regression checks for Task 57 are: new primary Contact is usable by
native Customer fallback after the Customer projection is refreshed; existing
transaction recipient behavior is unchanged; an unrelated Contact email cannot
be selected; and Contact permission filtering remains effective.

## 21. Sales transaction interoperability

ERPNext derives party contact defaults through `set_contact_details`, which uses
`get_default_contact` and then reads Contact `name`, `full_name`, `email_id`,
`mobile_no`, `phone`, designation, and department
(`apps/erpnext/erpnext/accounts/party.py:313-352`). New transaction defaults
therefore select a native primary Contact when one exists.

The Accounts controller validates that a selected transaction Contact belongs to
the transaction's Customer/Supplier through Dynamic Link rows
(`apps/erpnext/erpnext/controllers/accounts_controller.py:615-653`). Sales
transaction fields such as `contact_person`, `contact_email`, and
`contact_mobile` are copied at transaction creation. The existing Sales Order,
Quotation, and Sales Invoice code contains these fields and their native
set-missing/default flows; no Contact-specific transaction mutation is needed
for Task 57.

A later Contact update must not change existing transaction snapshots. New
transactions may see the Contact after native primary/default state and Customer
projection state are consistent. Task 56 therefore adds no transaction write.

## 22. Generic lifecycle reuse vs dedicated service comparison

| Option | Strength | Unsafe/insufficient part | Decision |
|---|---|---|---|
| A. Generic lifecycle only | Existing prepare/confirm, stale `modified`, normal `save` | No Contact-specific create/link intent, no bounded Dynamic Link policy, no child-table policy, Read Only gap, arbitrary Customer primary membership gap | Reject. |
| B. Dedicated Contact service only | Correct bounded business intent and native document path | Duplicating safe shared approval/transport/interaction patterns would be unnecessary | Reject as “only”; reuse shared infrastructure. |
| C. Dedicated Customer-linked creation/linking plus shared lifecycle for safe edits | Dedicated service owns scope/duplicates/links; shared approval store and native save remain common | Contact detail/child-table edits still need a later explicit contract | **Recommend for Task 57, with detail edits deferred.** |
| D. Arbitrary Dynamic Link/Contact CRUD | Maximum theoretical reuse | Leaks and permits cross-party mutation, bypasses business intent and primary semantics | Prohibit. |

The exact architecture is therefore **Option C**: a dedicated
Customer-scoped Contact service and contracts for search plus create/link, using
the shared `InteractionDirective`, approval store, fingerprint style, remote
operation dispatcher, and Sales profile registration. It must call native
Frappe/ERPNext documents rather than implement a parallel Contact engine.

## 23. Approval/fingerprint/concurrency recommendation

All future Contact writes require prepare/confirm. `prepare_customer_contact`
must bind at least:

* site, authenticated user, action, profile, and target Customer name;
* Customer `modified` and existence/permission state;
* operation mode (`create` or `link`);
* for link mode, exact Contact name, Contact `modified`, and existence/permission
  state;
* the target Customer Dynamic Link existence and, for create, the exact visible
  duplicate candidates used for the preview;
* current `customer_primary_contact` and `Contact.is_primary_contact` only if a
  primary operation is included;
* for any future child-row edit, complete bounded email/phone row fingerprints
  including child row names, values, flags, and parent `modified`.

Confirm must re-load fresh documents, re-check normal permissions, and reject
stale state if:

* Customer or Contact is deleted or modified after prepare;
* an existing link was added or removed after prepare, except a final identical
  link that the operation explicitly treats as idempotent success;
* an exact duplicate candidate appeared or changed;
* primary state changed for a future primary operation;
* an email/phone child row changed for a future detail operation.

The approval token must be claimed with
`ApprovalStore.claim_for_confirm_write()` under the existing site/user/action
binding. No Contact-specific approval store, `confirm=true` trust, or public
approval-mode argument is allowed. Use the current shared interaction and error
conventions; do not add `approval_needed` or client-specific identifiers.

Concurrency is natively handled for Contact primary promotion by stable locks on
all linked party documents (`contact.py:94-129`). Task 57 avoids the broadest
race by deferring existing-Contact promotion. Link creation still needs a
confirm-time `has_link` check and idempotent no-duplicate behavior.

## 24. Atomicity/idempotency recommendation

For link-only operations, one Contact `save` updates the Contact and Dynamic
Link children in the current Frappe transaction. For new Contact creation, one
Contact `insert` writes the parent and child rows in the same transaction. If
the operation also changes Customer primary, it becomes a multi-document
transaction: Contact insert/save plus normal Customer save.

MCP service code must not call `frappe.db.commit()` inside those native helpers.
The outer confirm boundary owns commit/rollback, matching current Customer
confirmation (`customer.py:458-467`) and lifecycle confirmation patterns.

Failure halfway through a multi-document operation must roll back the whole
transaction. CRM Contact validation updates linked CRM Deal snapshots in the
same database transaction; that side effect must be allowed to roll back with
the Contact operation.

Idempotency rules:

* Approval claims are one-shot, so replay cannot execute a second write.
* An already-existing exact Customer Dynamic Link is idempotent success.
* A lost response after new Contact creation is recoverable by a fresh exact
  Customer-scoped duplicate search and should return the already-linked Contact,
  not create another one.
* An exact email/mobile match on another Contact is `CONTACT_DUPLICATE_SUSPECTED`
  and requires an explicit selection; it is not automatically reused.

## 25. Profile placement

Register the Task 57 Contact capability **Sales-only**. The current problem is
Customer Contact management in the Sales profile, and current Sales registration
already owns Customer master and lifecycle tools (`mcp_erpnext/profiles/sales.py:8-38`).

Do not register it in Purchase merely because Contact can link to Supplier. Do
not add a generic core profile, because the public operation is deliberately
Customer-scoped and the current profile inventory has only Sales, Purchase, and
Accounts (`mcp_erpnext/tools/__init__.py:14-32`). Purchase Contact behavior can
be audited separately if required.

Task 57 integration points, not to be changed in Task 56, are:

1. `contracts/masters/contact.py` or a Customer-scoped master contract module;
2. `services/masters/customer_contact.py`;
3. `tools/masters/customer_contact.py`;
4. `profiles/sales.py` and `tools/__init__.py` registration;
5. `contracts/registry.py` metadata and interaction kinds;
6. `remote_operations.py` typed Sales handlers;
7. focused service/contract/profile/REST tests;
8. any generated catalog or `docs/COMMANDS.md` entry only if a reusable project
   command is actually introduced.

## 26. V1 vs deferred decision matrix

| Capability | Native source/helper | Public tool needed? | Approval? | Profile | V1 / deferred | Reason |
|---|---|---:|---:|---|---|---|
| Search linked Contact | `get_contacts_linking_to`, Dynamic Link filters | Yes, `search_contacts` | No | Sales | V1 | Required for selection and duplicate checks. |
| Read one bounded Contact | `frappe.get_doc` + permission + projection | Covered by exact `search_contacts`; no separate broad get | No | Sales | V1 | Avoid two overlapping read tools. |
| Create Contact for Customer | Normal `Contact.insert`; native controller | Yes, `prepare_customer_contact`/`confirm_customer_contact` | Yes | Sales | V1 | Core missing business intent. |
| Link existing Contact to Customer | `has_link` + append Dynamic Link + normal Contact save | Same bounded prepare/confirm operation | Yes | Sales | V1 | Core missing relationship intent. |
| Make new Contact primary | Contact primary validation plus normal Customer save if selected | Optional field only for new single-Customer Contact | Yes | Sales | Conditional V1 | Safe only when no cross-party link is involved; must be tested. |
| Make existing Contact primary | Contact primary global semantics + Customer save | No separate tool | Yes if later | Sales | Deferred | Cross-party side effects and Customer membership mismatch. |
| Update Contact name/details | Contact controller `save` | `prepare_contact_update`/confirm later | Yes | Sales | Deferred | Needs dedicated field allowlist and stale model. |
| Replace/add email | `set_primary_email`, child rows, normal save | Later dedicated tool | Yes | Sales | Deferred | Child-table authority and destructive fallback rules. |
| Replace/add phone/mobile | `set_primary`, Contact Phone rows, normal save | Later dedicated tool | Yes | Sales | Deferred | Independent primary flags and row identity. |
| Unlink Contact | Remove Dynamic Link via normal Contact save | No | Yes if later | Sales | Deferred | Multi-party and history implications. |
| Clear primary Contact | Customer field clear plus projection behavior | No | Yes if later | Sales | Deferred | Fallback semantics not a Task 57 need. |
| Delete Contact | Native delete/link blocker checks | No | Yes if later | Sales | Deferred | Destructive, shared-party, User/portal/history risks. |
| Arbitrary Dynamic Link mutation | Contact `links` child table | No | Yes if later | None | Deferred/prohibited | Customer-scoped intent is safer. |
| Supplier Contact support | Same Dynamic Link model | No | Yes if later | Purchase | Deferred | Not required by current business scope. |

### Deletion and unlink scope

The installed native deletion helper is not a safe V1 unlink API. ERPNext
Customer `on_trash` calls `delete_contact_and_address("Customer", self.name)`
(`apps/erpnext/erpnext/selling/doctype/customer/customer.py:429-437`). The
helper loads every Contact/Address Dynamic Link for that Customer; if the
Contact has only one link it deletes the whole Contact, otherwise it removes
the one link and saves the parent
(`apps/frappe/frappe/contacts/address_and_contact.py:90-109`). This means an
apparently simple unlink can delete a Contact, affect another party if links
are incomplete, or interact with User/portal/communication history. Native
document deletion also checks linked-document blockers through Frappe's delete
path. Task 57 must therefore implement neither unlink, clear-primary, nor
delete. A later destructive task needs an explicit preview, multi-party link
analysis, transaction/reference checks, and a separate approval-bound action.

## 27. Recommended Task 57 public tool surface

### `search_contacts`

Read-only typed input:

```text
query: bounded non-empty string
customer: optional exact Customer reference
match: optional enum {name, email, phone, auto}
limit: bounded positive integer
offset: bounded non-negative integer
```

Rules:

* Customer-scoped fuzzy name search is allowed after Customer read permission.
* Without Customer context, `email` and `phone` require exact normalized input;
  `name` requires exact Contact name, not unrestricted fuzzy personal-data
  search.
* The server always fixes the target relationship to Customer when a Customer
  scope is supplied.

Bounded output:

```text
status: ok | not_found | ambiguous | error
contacts: [{doctype, name, full_name, company_name?, email_id?, mobile_no?,
            phone?, is_primary_contact, linked_to_target_customer,
            other_party_link_count}]
count / limit / offset
```

### `prepare_customer_contact` and `confirm_customer_contact`

`prepare_customer_contact` input:

```text
customer: {doctype: "Customer", name: exact_name}
mode: "create" | "link"
existing_contact: {doctype: "Contact", name: exact_name} | null
new_contact: {
  first_name?, middle_name?, last_name?, company_name?, email?, mobile?
} | null
make_primary: bool = false
```

Contract rules:

* `mode=create` requires `new_contact` and rejects `existing_contact`.
* `mode=link` requires `existing_contact` and rejects new Contact payload data.
* `Customer` and `Contact` doctype values are server-fixed and cannot be
  arbitrary.
* Public `links`, `email_ids`, `phone_nos`, parent projection fields,
  `user`, Google fields, and arbitrary custom fields are not accepted.
* `make_primary=true` is accepted only for a newly created Contact under the
  single-target-Customer restriction; existing Contact promotion is returned as
  a deferred/unsupported interaction state.

Prepare output must use the existing interaction contract and include a bounded
preview of Customer reference, Contact mode, Contact identity, authoritative
child email/phone rows, link action, duplicate/reuse result, and primary effect.
It must not expose a raw document dump.

`confirm_customer_contact` accepts only the opaque approval token and
`confirm: bool`. It claims the approval through the shared approval guard,
revalidates all bound state and permissions, performs the native insert/link,
commits once at the outer boundary, and returns:

```text
status: linked | created | error
customer: bounded Customer reference
contact: bounded Contact reference and authoritative Contact projection
idempotent: bool
primary: {requested, applied, customer_primary_contact_updated} | null
```

There is no `create_any_contact`, `link_any_doctype`,
`mutate_dynamic_link`, `update_any_contact_field`, or `upsert_contact_everything`
tool.

### Recommended end-to-end user flows

#### Flow 1 — Customer exists, person is new

```text
User: Add Amit Shah to ABC Pvt Ltd with amit@example.com and 999...
  -> current resolve_customer resolves one exact Customer or requests selection
  -> search_contacts performs Customer-scoped duplicate checks
  -> prepare_customer_contact(mode=create) builds a bounded preview
  -> user continuation supplies explicit approval
  -> confirm_customer_contact claims the shared approval
  -> fresh Customer permission/identity and duplicate checks run
  -> native Contact.insert() creates Contact Email/Phone rows and Customer link
  -> optional new-contact primary path runs only under the single-target rule
  -> bounded Contact/Customer result is returned
```

#### Flow 2 — Customer exists, Contact already exists

```text
User: Link existing Amit Shah to ABC Pvt Ltd
  -> resolve Customer
  -> search_contacts finds an exact permitted Contact candidate
  -> prepare_customer_contact(mode=link) binds both exact references and link state
  -> user continuation supplies explicit approval
  -> confirm rechecks Customer/Contact permissions, modified values, and has_link()
  -> if already linked, return idempotent success without saving
  -> otherwise append only {link_doctype: Customer, link_name: ...}
  -> native Contact.save(ignore_permissions=False)
  -> bounded linked result is returned
```

#### Flow 3 — Change the Contact email later

```text
User: Change Amit's email to accounts@abc.com
  -> resolve Contact in Customer context
  -> future Task 58 prepare_contact_update previews the exact child row change
  -> explicit approval binds Contact modified and email child-row fingerprint
  -> future Task 58 confirm rechecks the child row and calls normal Contact.save()
  -> Contact.email_id is re-derived by Contact.validate()
  -> bounded Contact result is returned; existing transaction snapshots remain unchanged
```

Flow 3 is deliberately **deferred from Task 57**. The audit proves the native
rules, but the safe public contract still needs explicit child-row identity,
replace/remove semantics, stale checks, and regression coverage for stored
Customer projections and CRM hooks.

## 28. Recommended Task 57 contracts/inputs/outputs

Use the existing `PublicContractModel`, `InteractionDirective`, typed
discriminated status results, and `ToolError` conventions. The new contract
should introduce only stable public values:

* `CustomerReference` and `ContactReference` with literal doctypes;
* `CustomerContactCreateInput` with an explicit allowlist of person/company
  and primary email/mobile inputs;
* `CustomerContactLinkInput` containing only an exact Contact reference;
* a discriminated `CustomerContactPrepareResult` with `ready`, `duplicate_suspected`,
  `needs_selection`, `permission_denied`, `not_found`, and bounded `error`
  states;
* `CustomerContactConfirmInput` containing `approval_token` and `confirm` only;
* a bounded result projection as described above.

The contract must not expose raw Frappe `Document` JSON, dynamic field maps,
arbitrary child rows, public approval-policy modes, or a `confirm=true` value as
approval. Natural-language interpretation and continuation state remain in the
Agent/client; MCP returns the shared semantic interaction directive.

### Bounded error model

Use the existing typed interaction/error convention. Recommended semantic
codes are:

| Condition | Recommended code/state | User-correctable? | Retry behavior |
|---|---|---:|---|
| Customer missing or not visible | `CUSTOMER_NOT_FOUND` | Yes | Resolve/select again. |
| Contact missing or not visible | `CONTACT_NOT_FOUND` | Yes | Search/select again. |
| Missing Customer/Contact permission | `PERMISSION_DENIED` with bounded missing doctype | Yes, by an administrator | Do not retry unchanged. |
| Exact email/phone/name collision | `CONTACT_DUPLICATE_SUSPECTED` | Yes | Select an existing Contact or change input. |
| Existing identical link | `linked`, `idempotent=true` | No action needed | No write retry. |
| Invalid email or phone | `CONTACT_INVALID_EMAIL` / `CONTACT_INVALID_PHONE` | Yes | Correct the value and prepare again. |
| Existing-contact primary requested | `CONTACT_PRIMARY_UNSUPPORTED` in V1 | Yes | Use the deferred Task 58 capability. |
| State changed after preview | `CONTACT_STALE_STATE` or `CONTACT_LINK_STALE_STATE` | Yes | Prepare again. |
| User did not continue with approval | shared `CONFIRMATION_REQUIRED` | Yes | Re-present the preview/continuation. |
| Expired, replayed, wrong-user, or wrong-site token | shared approval-expired/invalid state | Yes | Prepare again; never replay the write. |

Unexpected native validation or hook failures should use the existing bounded
`ToolError`/safe public error mechanism, with a server reference and no raw
stack trace, SQL, or personal data.

## 29. Recommended Task 57 test matrix

Task 57 must add tests before implementation is considered complete.

### Existing Customer creation regression

* Customer plus nested Contact still creates the ERPNext-native primary Contact.
* Customer name only still creates no Contact.
* Email-only and mobile-only Customer creation follow the installed native
  `make_contact` behavior.
* Missing Contact create permission is returned before confirm/write.
* Customer creation still rolls back if native Contact insert fails.

### New Contact for existing Customer

* Valid new Contact inserts with exactly one Customer Dynamic Link.
* Customer not found/read denied is bounded and non-mutating.
* Contact create denied is bounded and non-mutating.
* Missing identity is rejected by capability contract even though framework
  Contact fields are optional.
* Invalid email/phone is rejected by native validation before commit.
* Exact duplicate/suspected duplicate email or phone requires selection.
* Primary creation, if enabled, updates Contact and Customer consistently.

### Existing Contact linking

* Valid existing Contact links to Customer through normal Contact save.
* Already-linked Contact returns idempotent success without duplicate row.
* Contact not found/read/write denied and Customer denied are covered.
* Contact already linked to another Customer is permitted only with explicit
  user selection and bounded cross-party warning.
* Contact linked to Supplier and Customer remains valid but is not promoted to
  primary by default.

### Primary Contact

* Contact primary validation demotes the prior Customer-linked primary.
* Native locking behavior is covered at the framework test boundary or via an
  authorized isolated integration test.
* Existing-Contact primary promotion is rejected/deferred in V1.
* Customer `customer_primary_contact` is never set to an unlinked Contact.

### Email/phone and deferred behavior

* Task 57 rejects parent scalar email/phone child-table payloads.
* Task 58 tests primary email, secondary email, removal, primary phone/mobile,
  duplicate rows, invalid values, and stale child-row fingerprints.

### Approval/stale state

* Contact changes after prepare, Customer changes after prepare, link added after
  prepare, Contact deleted after prepare, token replay, wrong user/site,
  expiration, and `confirm=false` are all covered.

### Transport/profile

* Sales exposes intended tools only.
* Accounts does not expose them.
* Purchase behavior remains unchanged.
* Stdio and HTTP/REST use the same typed handlers.
* Contract registry and remote-operation registry are both complete.

### Read/data minimization

* Customer-scoped name search, exact email, exact phone, exact Contact name,
  primary lookup, permission filtering, bounded projection, and no unrelated
  Contact leakage.

### Email interoperability

* A newly valid primary Contact is usable by native recipient fallback after
  Customer state is consistent.
* Existing Sales Order/Quotation/Sales Invoice recipient snapshots are unchanged.
* An unrelated Contact email cannot be selected for a Customer document.

## 30. Security/data-leak review

Contact contains personal names and communication data. The LLM needs only
enough information to identify a permitted person, review a proposed Customer
link, and confirm a bounded mutation. The proposed tool therefore:

* requires the verified Frappe user from the existing MCP identity boundary;
* uses normal Contact and Customer permissions for every read/write;
* fixes Dynamic Link type to Customer server-side;
* does not reveal unrelated linked party names, communications, User linkage,
  addresses, comments, or CRM Deal rows;
* exposes child email/phone values only when needed for exact duplicate
  selection or an approved create preview;
* does not trust LLM-provided Contact names, Customer names, or approval state
  without exact server resolution and revalidation;
* does not use `ignore_permissions=True`, raw SQL mutation, direct child-row
  insertion, or an MCP-owned shadow Contact store.

The installed CRM Contact validation hook can update CRM Deal email/mobile
snapshots. That is a native side effect and must be included in the approval
preview only at a bounded semantic level, not exposed as raw CRM data.

## 31. Limitations / unknowns

The following are source/runtime boundaries rather than unresolved design
assumptions:

* No Contact or Customer business record was inserted, updated, linked, or
  deleted during this audit. Primary state transitions and failure atomicity are
  source-proven and covered by existing Frappe/ERPNext test code where noted;
  they were not reproduced against a live business record.
* Runtime metadata was inspected on `praveg.localhost`, which is the selected
  development site for this audit. Other sites may add Custom Fields, Property
  Setters, permissions, CRM hooks, or app overrides; Task 57 must use effective
  metadata and normal runtime validation rather than assuming this site's exact
  role configuration.
* India Compliance is present in the checkout but not installed on the inspected
  site. Its Customer-only hooks were inspected statically; no India Compliance
  Contact behavior is claimed.
* The generic lifecycle `Read Only` validator gap is documented, not fixed. A
  separate hardening task should decide whether `fieldtype == "Read Only"`
  should be rejected for all generic scalar updates.
* CRM's Contact hook updates linked CRM Deal snapshots. Other custom apps or
  site-specific hooks may add additional Contact side effects on other sites.
* The combined focused MCP test run had two existing approval-policy failures:
  `CustomerServiceTests.test_model_confirm_true_cannot_self_grant_approval`
  returned no expected `code`, and
  `EmailServiceTests.test_confirm_requires_trusted_approval_in_default_policy`
  returned `PROFILE_MISMATCH` instead of `TRUSTED_APPROVAL_UNAVAILABLE`. Those
  failures were not changed by Task 56. The independent read/lifecycle/profile/
  REST group and targeted Customer/email tests passed.

## 32. Exact Task 57 recommendation

Task 57 is **Customer-Linked Contact V1 Implementation** with this exact
boundary:

1. Add a bounded Sales-only `search_contacts` read capability.
2. Add one Customer-scoped `prepare_customer_contact` /
   `confirm_customer_contact` mutation pair supporting only:
   * create a new Contact with a server-derived Customer Dynamic Link; or
   * link one explicitly selected existing Contact to that Customer.
3. Use normal Frappe Contact insert/save and normal Customer permission checks;
   reuse the shared approval store, interaction directives, stale fingerprints,
   typed contract registry, and REST dispatcher.
4. Allow new-contact primary behavior only as an explicit, tested,
   single-target-Customer option. Do not promote an already-linked existing
   cross-party Contact in V1.
5. Keep current `prepare_customer`/`confirm_customer` nested Contact input
   unchanged. It is an established ERPNext-native initial Customer flow and
   must receive regression coverage rather than being split into extra tools.
6. Defer Contact name/detail updates, email/phone child-row editing, unlink,
   clear-primary, delete, merge, arbitrary Dynamic Link editing, Supplier
   Contact support, portal User behavior, and bulk operations.

This is the smallest vertical slice that handles the missing business intent
without duplicating Frappe/ERPNext Contact truth or broadening the public MCP
surface into arbitrary master-data mutation.

## Verification performed for Task 56

Read-only/source checks performed:

* repository branch, HEAD, and worktree status for `mcp_erpnext`, Frappe,
  ERPNext, and installed optional apps;
* source searches and line-level inspection of the MCP Customer contract/config/
  service/tools, Customer read service/tools, lifecycle service/tools, email
  service/tools, Sales registration, contract registry, and REST registry;
* source inspection of Frappe Contact, Contact Email, Contact Phone, Dynamic
  Link, document validation/permission/transaction code, and relevant helpers;
* source inspection of ERPNext Customer, Customer JSON/form query, party contact
  defaults, transaction Contact validation, and Customer tests;
* source inspection of installed CRM Contact override/hook and static India
  Compliance Customer hooks;
* effective runtime metadata, installed apps, hooks, and versions on
  `praveg.localhost` using read-only `bench execute` calls.

Focused MCP verification:

```text
../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_customer_read \
  mcp_erpnext.tests.test_lifecycle \
  mcp_erpnext.tests.test_profiles \
  mcp_erpnext.tests.test_rest_backend
```

Result: **52 tests passed**.

Targeted checks also passed:

```text
../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_customer_service -k valid_preparation_does_not_write

../../env/bin/python -m unittest \
  mcp_erpnext.tests.test_email -k sales_invoice_resolves_customer_party
```

Result: **1 test passed in each command**.

The broader combined command ran 85 tests and ended with one error and one
failure in the existing approval-policy expectations described in section 31.
No Frappe/ERPNext integration test was run against the development site because
that would require a test database/site boundary and could mutate business
fixtures. No production Python, hooks, DocTypes, fixtures, permissions, profile
registration, or site data was changed.
