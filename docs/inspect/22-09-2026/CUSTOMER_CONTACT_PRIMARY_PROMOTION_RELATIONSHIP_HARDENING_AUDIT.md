# Customer Contact Primary Promotion and Relationship Hardening Audit

## 1. Status and scope

This is the completed Task 62 audit/design report. No primary-promotion tool,
service, contract, schema change, migration, or business-record mutation was
implemented.

The audit covers the current checked-out Frappe, ERPNext, CRM, and
`mcp_erpnext` sources and read-only runtime metadata on `praveg.localhost`.

## 2. Confirmed context

- Repository: `apps/mcp_erpnext`, branch `master`.
- Existing public Contact capability: search, create/link, and the Task 61
  Customer-scoped detail/communication update pair.
- Task 57 explicitly deferred promotion of an existing Contact because
  `Contact.is_primary_contact` has cross-party semantics.
- Current worktree already contained the untracked Task 62 task file. This
  report is the only file added by this audit.
- Runtime installed apps: `frappe`, `erpnext`, `hrms`, `crm`, `praveg`, and
  `insights`.
- Runtime Contact override:
  `crm.overrides.contact.CustomContact`.
- Runtime Contact validate events include ERPNext lead-phone maintenance and
  `crm.api.contact.validate`; Customer had no additional runtime `doc_events`
  entry.

## 3. Primary-state model

### Contact primary state

`Contact.is_primary_contact` is a stored Check field on the Contact document.
It is not a Dynamic Link child-row flag and is not stored per Customer,
Supplier, Lead, or other party. It is therefore global to the Contact record.

The native Contact controller treats every `(link_doctype, link_name)` pair in
the Contact `links` table as part of the primary scope. When the flag is true,
`Contact.validate_primary_contact()`:

1. collects all Dynamic Links on the Contact;
2. locks every linked document, grouped by doctype and sorted by doctype and
   name;
3. finds every other Contact marked primary that has any of those same links;
4. demotes those Contacts with `frappe.db.set_value("Contact", ..., 0)`.

Consequences:

- The flag is per Contact record, not per Dynamic Link.
- It is global across all links of that Contact.
- A Contact linked to ABC and XYZ cannot be primary for ABC while being
  non-primary for XYZ.
- A shared Contact promotion can demote another party's primary Contact.
- The native query does not update other parties' stored
  `customer_primary_contact` fields.

### Customer primary state

`Customer.customer_primary_contact` is a stored Link field to Contact. It is
Customer-scoped and is the authoritative Customer pointer for the selected
Contact. The runtime metadata confirms:

| Field | Runtime type | Native role |
|---|---|---|
| `Contact.is_primary_contact` | Check | global Contact primary marker |
| `Contact.links` | Table | Dynamic Link relationship rows |
| `Customer.customer_primary_contact` | Link(Contact) | Customer's selected Contact |
| `Customer.email_id` | Read Only | fetch from selected Contact |
| `Customer.mobile_no` | Read Only | fetch from selected Contact |
| `Customer.first_name` | Read Only | fetch from selected Contact |
| `Customer.last_name` | Read Only | fetch from selected Contact |

The Customer JSON metadata describes the four projection fields as
`fetch_from="customer_primary_contact.<field>"`; they are not independent
public write fields.

The two primary states can diverge in pre-existing data. Contact validation
does not write `Customer.customer_primary_contact`, and Customer validation
does not verify that the selected Contact has a Customer Dynamic Link.

## 4. Native call-chain audit

### Path A: Contact save with `is_primary_contact = 1`

`Document.save()` checks Contact write permission, runs Contact validation,
then runs the CRM Contact validate hook. Contact validation derives the
parent email/phone values, deduplicates Dynamic Links, and invokes
`validate_primary_contact()`.

The primary validator locks linked party documents with `FOR UPDATE` in stable
order. It then finds all other primary Contacts sharing any linked pair and
demotes them by direct `frappe.db.set_value`. This path preserves normal
Contact save validation and the installed CRM Contact validate hook for the
selected Contact. The internal demotion does not run a normal save on every
demoted Contact and does not invoke their Contact validation/hooks.

### Path B: Customer save with `customer_primary_contact` set

`Customer.on_update()` calls `create_primary_contact()`. If the field is set,
the current ERPNext code executes:

```python
frappe.set_value("Contact", self.customer_primary_contact, "is_primary_contact", 1)
```

This is an internal ensure operation. It is not a substitute for an explicit
public Contact save: it does not itself establish the Contact save/validation
boundary needed by a promotion service, and it does not verify that the
selected Contact is linked to this Customer.

Customer save is still the native path needed to refresh the stored
`fetch_from` projections. Direct assignment to `Customer.email_id`,
`mobile_no`, `first_name`, or `last_name` must not be used.

### Chosen future sequence

For a future dedicated promotion operation, use this sequence in one outer
transaction:

1. Reload and validate the exact Customer and Contact.
2. Require the exact Customer Dynamic Link.
3. Reject any additional Contact Dynamic Link in V1.
4. Set the selected Contact's `is_primary_contact` in memory and call normal
   `Contact.save(ignore_permissions=False)`.
5. Set `Customer.customer_primary_contact` in memory and call normal
   `Customer.save(ignore_permissions=False)`.
6. Commit once only after both saves succeed; roll back on every failure.

This preserves Contact native demotion/locking and CRM hooks, then lets native
Customer saving refresh projections. Customer-only save is rejected as the
public mutation seam because its internal `frappe.set_value()` has broader
side effects and lacks membership enforcement. Contact-only save is rejected
because it does not update the Customer pointer/projections.

## 5. Membership enforcement

The selected Contact must satisfy both checks at prepare and confirm:

```python
contact.has_link("Customer", customer.name)
customer.customer_primary_contact in {None, selected_contact.name} or any(...)
```

The first check is mandatory even though the Customer Link field accepts a
Contact name. A selected Contact that is not linked to the target Customer
must return the existing canonical code:

```text
CONTACT_NOT_LINKED_TO_CUSTOMER
```

The operation must not add the Dynamic Link as a side effect. Linking remains
Task 57's separate operation.

## 6. Shared Contact safety decision

V1 must reject promotion when the selected Contact has any Dynamic Link other
than the exact target Customer link. This includes another Customer, Supplier,
Lead, Prospect, CRM Deal, or any other Dynamic Link doctype.

Reason: native Contact promotion is global. It locks all linked records and
demotes every other primary Contact sharing any link. It does not update other
Customers' `customer_primary_contact` pointers, so a shared promotion can
create pointer/flag divergence in another party. The operation also cannot
prove that the caller is authorized to alter every affected party.

Recommended error:

```text
CONTACT_SHARED_WITH_OTHER_PARTIES
```

No unrelated party names or link identities should be returned.

## 7. Single-Customer cases and inconsistent state

### One Customer link, no current Customer primary

Promoting the selected Contact should result in:

- selected Contact primary flag = true;
- all other Contacts linked to that Customer demoted by native Contact
  validation;
- `Customer.customer_primary_contact` = selected Contact;
- Customer email/mobile/name projections refreshed through Customer save.

### Existing Customer primary

The old Customer primary Contact is expected to be demoted when it shares the
Customer Dynamic Link and the selected Contact is saved through the native
Contact path. The old Customer pointer is then replaced by the selected
Contact in the same transaction. Projection fields must be observed after the
Customer save, not inferred from direct assignments.

### Existing inconsistent data

The future operation must not silently repair arbitrary corruption. Prepare
and confirm should return a retryable, explicit inconsistency error when any of
these are detected:

- Customer points to an unlinked Contact;
- selected Contact is not primary but Customer points to a different Contact;
- selected Contact is primary but Customer points to a different Contact;
- multiple Customer-linked Contacts are primary;
- Customer pointer and Contact relationship state changed after prepare.

Recommended code: `CONTACT_PRIMARY_STATE_INCONSISTENT`. A separate bounded
repair task may later define normalization. Promotion must not hide unrelated
data corruption.

## 8. Locking, races, and stale state

The native Contact validator locks linked party rows using sorted doctype/name
ordering. This serializes concurrent Contact primary saves that include the
same linked Customer and avoids deadlocks caused by inconsistent lock order.
The native logic does not lock the Customer row, does not update Customer
primary pointers, and does not cover the full two-document promotion
transaction.

The MCP approval fingerprint must supplement native locks. It must bind:

- site, authenticated user, profile, and action;
- Customer name and `modified` value;
- selected Contact name and `modified` value;
- exact sorted Dynamic Link `(link_doctype, link_name)` state internally;
- exact target Customer membership;
- selected Contact `is_primary_contact` value;
- current `Customer.customer_primary_contact` value;
- old Customer-primary Contact name, `modified`, and primary state if present;
- bounded expected post-state.

Unrelated relationship identities must remain internal to the fingerprint and
must not be returned in public previews. Confirm must reload all affected
documents, repeat the membership/share/inconsistency checks, compare the
fingerprint, and claim the shared approval using a distinct action before any
write.

Concurrent “Amit versus Ravi for the same Customer” requests must both be
prepared against the observed state, but only the first valid confirm should
commit. The second must fail stale after reload or after native locking, and
must require a fresh prepare. A shared Contact race must fail if an additional
link appears between prepare and confirm.

## 9. Permission matrix

| Operation | Required boundary |
|---|---|
| Prepare target resolution | Customer read + Contact read |
| Inspect exact links | Contact read, with no permission bypass |
| Prepare promotion | Customer write + Contact write preflight |
| Confirm promotion | Customer write + Contact write rechecked |
| Native demotion of old Contacts | Native internal `db.set_value`; MCP still requires Contact write on the selected Contact and Customer write on the target Customer |
| Refresh Customer projections | Customer write |

The public implementation must use normal Frappe permissions and must not
hard-code roles or use `ignore_permissions=True`. The native demotion can
bypass a separate normal save permission check for demoted Contacts, which is
why shared Contacts are rejected and why a selected Contact/Customer write
preflight is still required.

## 10. Projection and transaction behavior

The Customer projection fields are read-only fetch fields. A promotion must
not write them directly or use `frappe.db.set_value` for them. A normal
Customer save after changing `customer_primary_contact` is the authoritative
refresh seam.

Historical transaction snapshots such as `contact_email` remain unchanged.
Future Customer-based party resolution can select the promoted Contact through
ERPNext's native default-contact logic. The generic ERPNext party helper
filters Dynamic Links and orders `is_primary_contact` first; it does not
rewrite historical documents.

Quotation, Sales Order, and Sales Invoice creation should continue to use
native party/contact defaulting. The promotion service must not reimplement
email-recipient or transaction-default logic.

## 11. CRM side effects

The runtime CRM app overrides the Contact class and registers
`crm.api.contact.validate` on Contact validate. That hook updates snapshots for
CRM Deals whose CRM Contact row is primary when Contact email/mobile changes.
The selected Contact's normal save must therefore be retained. A Customer-only
`frappe.set_value` path is not sufficient evidence that Contact validation and
CRM hooks will run, and must not be the sole public promotion seam.

## 12. Task 57 transaction-boundary audit

The current Task 57 `confirm_customer_contact()` still commits internally in
both create and link branches and rolls back inside those branches. Task 60
and Task 61 follow the newer one-outer-confirmation pattern for compound
operations, while the Task 57 branch remains a single Contact write.

Classification:

- For the existing isolated Task 57 create/link operations: recommended
  non-blocking hardening; no behavior change is included in Task 62.
- For primary promotion: a blocking design rule, not necessarily a blocker
  requiring Task 57 code changes first. The new promotion pair must own one
  outer transaction and must not call a helper that commits internally.
- If future work wants one composite create/link/promote operation, Task 57
  commit ownership must be hardened first or the composite must be rejected.

This is intentionally a separate hardening task because changing Task 57's
commit behavior is outside this audit and could alter existing callers.

## 13. Relationship-count semantics

Current `customer_contact._projection()` exposes `other_party_link_count` as
the number of every Dynamic Link row other than the exact target Customer
row. It does not identify “party” links using a framework party-type helper.
Therefore its current name is not exact: it can count non-party relationship
rows and is not safe as an authorization decision.

The count must not drive primary-promotion authorization. The promotion
preflight should inspect the exact sorted Dynamic Link pairs internally and
apply the conservative “any additional link means shared” rule.

If the public projection is revised later, the accurate compatibility choice
is a separately versioned field such as `additional_link_count`; changing the
meaning of the existing field silently is not recommended.

## 14. Definition of relationship sharing

The source-proven rule selected for V1 is Option A: every additional Dynamic
Link row counts as sharing. This is more conservative than an incomplete
hard-coded list of Customer/Supplier/Lead/etc. and matches native Contact's
actual primary algorithm, which does not classify link doctypes as party or
non-party before locking and demotion.

A future generic relationship policy may use framework metadata if a stable
native helper is introduced, but no such helper was found in the inspected
Contact, Dynamic Link, Customer, or party-default code that would be safer than
the all-link rule.

## 15. Public tool design for the next implementation

Use a dedicated pair:

```text
prepare_customer_primary_contact
confirm_customer_primary_contact
```

This is clearer than adding `mode="make_primary"` to create/link, and keeps
relationship-primary semantics separate from Task 61's primary email/phone/
mobile operations. It also gives the multi-document operation a distinct
approval action:

```text
customer_primary_contact
```

Do not add this capability to the communication-update operation.

### Prepare

Prepare must remain non-mutating and must:

1. load Customer and selected Contact with permission-aware reads;
2. require Customer and Contact write permission for the planned write;
3. require exact Customer Dynamic Link membership;
4. reject any additional Dynamic Link;
5. detect inconsistent primary/pointer state;
6. inspect the current Customer primary and selected Contact state;
7. construct a bounded before/after preview;
8. store the internal relationship/primary fingerprint in the shared approval
   store.

The preview may expose only Customer/Contact references, current and proposed
primary state, and projection refresh status. It must not expose unrelated
party names, raw Dynamic Link rows, or raw Contact JSON.

### Confirm

Confirm must use `ApprovalStore.claim_for_confirm_write()` with action
`customer_primary_contact`, rebind the authenticated user/site/profile, reload
Customer and Contact, repeat all checks, compare the stored fingerprint, then
execute Contact save followed by Customer save inside one transaction. It must
return a retryable stale result for changed relationship, pointer, selected
Contact, old primary, or Customer state.

`confirm=false` must not be treated as approval and must preserve the shared
interaction/approval contract.

## 16. Runtime verification evidence

Read-only command used:

```text
./env/bin/bench --site praveg.localhost execute ...
```

Verified runtime facts:

- installed apps listed above;
- Contact override and Contact/Customer event metadata;
- effective field types and fetch/read-only metadata;
- effective Contact and Customer permission rows.

The runtime permission rows contain duplicate/role-specific entries from the
installed site; the future MCP must call normal document permission APIs rather
than infer authorization from a copied role list. No Customer, Contact, Dynamic
Link, or CRM record was created, updated, deleted, or migrated.

## 17. Exact next task

### Task 63 — Implement Customer Primary Contact Promotion V1

Scope:

- dedicated Sales-only prepare/confirm pair;
- existing Contact already linked to exactly one Customer;
- reject all additional Dynamic Links;
- exact membership and inconsistent-state checks;
- shared approval action `customer_primary_contact`;
- relationship and primary-state fingerprints;
- normal Contact save followed by normal Customer save;
- one outer commit and rollback on failure;
- native Contact demotion, Customer projection refresh, and CRM hooks;
- focused static/unit coverage and authorized local-live read/write verification.

Keep Task 57 commit hardening as a separate prerequisite/hardening task. Do
not combine communication-primary updates, arbitrary Dynamic Link mutation,
unlink/delete/merge, Supplier support, or data-repair normalization with Task
63.

## 18. Actions not performed

- No production implementation of primary promotion.
- No changes to Task 57, Task 61, contracts, services, tools, registries, or
  generated catalogs.
- No database mutation, migration, cache clear, service restart, deployment,
  commit, or push.
- No live business-record promotion test.
