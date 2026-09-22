# Standalone Contact Master Capability Audit

Status: completed audit/design. No standalone Contact capability was implemented by this task.

Runtime site used for this audit: `yob.localhost`. No business records were created or modified.

## 1. Executive summary

Standalone native Contact creation is valid and should be exposed as a bounded
Sales-profile capability in a later implementation task. It must remain a
separate business intent from Task 57 Customer-linked creation:

```text
Create contact Amit Shah
    -> prepare_contact -> confirm_contact

Create Amit Shah for ABC Pvt Ltd
    -> prepare_customer_contact(mode=create)
```

The recommended V1 boundary is:

```text
prepare_contact
confirm_contact
```

The public create payload should accept only:

```text
first_name?, middle_name?, last_name?, company_name?,
designation?, department?, email?, mobile?, phone?
```

At least one of `first_name`, `last_name`, or `company_name` is required.
Email, mobile, and phone are optional. V1 supports at most one email, one
mobile, and one phone. The server constructs child rows and primary flags;
callers never submit `email_ids`, `phone_nos`, `links`, or
`is_primary_contact`.

Exact visible email or normalized-phone matches return
`CONTACT_DUPLICATE_SUSPECTED` with the existing bounded Contact projection.
Same name alone is not a duplicate decision. Hidden Contacts are not
enumerated or disclosed; permission-filtered lookup simply cannot establish a
duplicate.

Prepare is strictly non-mutating and must not invoke the full hook-bearing
Contact validation chain. Confirm rechecks permission and duplicate state, then
uses `frappe.get_doc(payload).insert(ignore_permissions=False)` inside the
normal confirmation transaction. Native Contact validation and installed hooks
remain authoritative.

## 2. Evidence and repository state

### 2.1 Worktree and versions

The `mcp_erpnext` checkout is on branch `master`, with the Task 57 Contact
implementation at commit `6b88b01 feat(contact): add customer-linked contact
creation and linking`. The relevant installed application checkouts report:

| Component | Evidence |
|---|---|
| Frappe | `apps/frappe`, release commit `c1f1e8ec37 chore(release): Bumped to Version 16.34.0` |
| ERPNext | `apps/erpnext`, release commit `12cd563fb9 chore(release): Bumped to Version 16.35.0` |
| CRM | `apps/crm`, checkout commit `c8ed011 CSS Updated` |
| mcp_erpnext | `apps/mcp_erpnext`, commit `6b88b01` |
| Runtime site | `yob.localhost` |

The worktree already contained the user’s uncommitted Task 59 specification
and Customer-scoped update audit. Those files were not modified.

### 2.2 Sources inspected

The conclusions below were traced through:

- `docs/tasks/audits/56_TASK_CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md`;
- `docs/tasks/implementation/57_TASK_CUSTOMER_LINKED_CONTACT_V1_IMPLEMENTATION.md`;
- `docs/inspect/CUSTOMER_LINKED_CONTACT_V1_IMPLEMENTATION_REPORT.md`;
- `docs/tasks/audits/58_TASK_CUSTOMER_SCOPED_CONTACT_DETAIL_EMAIL_PHONE_UPDATE_AUDIT.md`;
- current Contact contracts, service, tool registration, Sales profile,
  registry, REST dispatch, tests, and `docs/TOOLS.md`;
- Frappe Contact, Contact Email, Contact Phone, Dynamic Link, document insert,
  email/phone validators, and dynamic-link helpers;
- CRM Contact override and Contact validate hook;
- effective metadata and hooks on `yob.localhost`.

## 3. Runtime verification on `yob.localhost`

### 3.1 Commands and results

The following read-only commands were used:

```text
./env/bin/bench --site yob.localhost execute frappe.get_installed_apps --args '[]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Contact"]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Contact Email"]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Contact Phone"]'
./env/bin/bench --site yob.localhost execute frappe.get_meta --args '["Dynamic Link"]'
./env/bin/bench --site yob.localhost execute frappe.get_hooks --kwargs '{"hook":"override_doctype_class","app_name":"crm"}'
./env/bin/bench --site yob.localhost execute frappe.get_hooks --kwargs '{"hook":"doc_events","app_name":"crm"}'
./env/bin/bench --site yob.localhost execute frappe.get_hooks --kwargs '{"hook":"doc_events","app_name":"erpnext"}'
```

Effective installed apps were:

```text
frappe, yob_core, yob_auth, erpnext, payments, india_compliance,
yob_storefront, mcp_erpnext, mcp_identity
```

The initial un-escalated attempt failed before database access with
`MySQLdb.OperationalError: (2004, "Can't create TCP/IP socket (1)")`.
The same read-only commands succeeded after the environment’s required
escalation. No write, migration, cache clear, or business-record operation was
run.

### 3.2 Effective metadata

| DocType | Runtime result | Relevance |
|---|---|---|
| Contact | non-single, non-table, `naming_rule="By script"`; identity and relationship fields are not required; `full_name`, `email_id`, `phone`, and `mobile_no` are read-only projections | A no-link Contact is structurally supported; callers must use source fields and child rows |
| Contact Email | table; `email_id` required; `is_primary` optional check | One bounded email row is sufficient for V1 |
| Contact Phone | table; `phone` required; independent `is_primary_phone` and `is_primary_mobile_no` checks | Mobile and phone are independent semantics over phone rows |
| Dynamic Link | table; `link_doctype` and `link_name` required when a row exists | An empty Contact `links` table is valid; public standalone input must not expose rows |

The runtime Contact permission metadata includes create/read/write for the
configured business roles, but the implementation must call native permission
APIs rather than hard-code role names. Runtime Property Setter/Custom Field
changes were represented in the effective Contact metadata; no extra required
field affecting the proposed V1 payload was observed.

### 3.3 Effective overrides and events

Runtime hook inspection returned:

```text
override_doctype_class:
Contact -> crm.overrides.contact.CustomContact
```

CRM `doc_events` returned:

```text
Contact.validate -> crm.api.contact.validate
```

ERPNext’s checked-out hooks contribute Contact `validate`, `after_insert`, and
`on_trash` behavior. The source hook lists are in
`apps/erpnext/erpnext/hooks.py:405-409` and the CRM hook is in
`apps/crm/crm/hooks.py:135-147`.

The aggregate `frappe.get_hooks("doc_events")` query was not used as evidence
because Bench’s JSON printer cannot serialize its tuple-keyed result. The
app-specific hook queries above are the runtime evidence used here.

## 4. Native standalone Contact validity

### 4.1 Contact controller behavior

`apps/frappe/frappe/contacts/doctype/contact/contact.py:39-76` shows that:

1. `autoname()` sets the name from `_get_full_name()`.
2. The first Dynamic Link, if present, is appended to the generated name.
3. Existing names are passed through `append_number_if_name_exists()`.
4. `validate()` derives `full_name`, primary email, primary phone, and primary
   mobile, then deduplicates links and validates primary-contact behavior.
5. `validate_primary_contact()` returns immediately when
   `is_primary_contact` is false, and also returns without party work when
   there are no links.

The source therefore proves that Contact creation does not require a Customer
link, Supplier link, any link, email, or phone. The effective runtime metadata
confirms that none of those fields is required.

### 4.2 Naming and identity limits

`get_full_name()` at
`apps/frappe/frappe/contacts/doctype/contact/contact.py:514-522` joins
first/middle/last names and falls back to `company_name` when no person-name
component exists. With no link, the generated name is therefore:

```text
<person full name>
or
<company name>
```

No link suffix is added for a standalone Contact. A collision receives a
numeric suffix from `append_number_if_name_exists()` rather than being treated
as an existing identity.

The controller does not require a non-empty identity component in Python, but
the checked-out source does not by itself prove that an empty generated name
will pass every database/document insertion constraint. The public MCP rule
must therefore be stricter: require a person or company identity and never
create a nameless Contact. This also keeps later exact search and Customer
linking useful.

## 5. Identity policy

| Option | Rule | Assessment | Decision |
|---|---|---|---|
| A | `first_name` required | Excludes company-style Contacts and “Accounts Desk” records | Reject |
| B | one of `first_name`, `last_name`, `company_name` | Matches native naming, supports person and business labels, prevents nameless records | **Select** |
| C | one of identity fields, email, or mobile | Allows email/phone-only records with weak human searchability and ambiguous duplicate recovery | Reject |
| D | another rule | No source-supported safety advantage over B | Reject |

Exact rule:

```text
at least one of first_name, last_name, company_name must be non-empty
after whitespace trimming
```

Email or phone alone is not sufficient identity. A standalone Contact can have
no email and no phone. `is_primary_contact` is always omitted/false and is not
public input; a no-link Contact has no party for which “primary” would have
meaning.

## 6. Candidate create fields

| Public input | Native target | Validation | Required/optional | V1/defer | Reason |
|---|---|---|---|---|---|
| `first_name` | `Contact.first_name` | Trimmed non-empty string when supplied | Identity alternative | V1 | Native person naming |
| `middle_name` | `Contact.middle_name` | Trimmed string | Optional | V1 | Native full-name derivation |
| `last_name` | `Contact.last_name` | Trimmed non-empty string when supplied | Identity alternative | V1 | Supports surname-only/business-label use |
| `company_name` | `Contact.company_name` | Trimmed string | Identity alternative | V1 | Native fallback for company-style Contact |
| `designation` | `Contact.designation` | Trimmed string | Optional | V1 | Direct native detail field; no relationship side effect |
| `department` | `Contact.department` | Trimmed string | Optional | V1 | Direct native detail field |
| `email` | one `Contact Email.email_id` row | Trim, validate one address, reject comma/multiple-address value | Optional | V1 | Bounded communication input; parent `email_id` is derived |
| `mobile` | one `Contact Phone.phone` row with `is_primary_mobile_no=1` | Trim and project phone validation | Optional | V1 | Explicit mobile semantic |
| `phone` | one `Contact Phone.phone` row with `is_primary_phone=1` | Trim and project phone validation | Optional | V1 | Explicit office/landline semantic |

The public contract must reject `full_name`, `email_id`, `mobile_no`, raw
`email_ids`, raw `phone_nos`, `links`, `link_doctype`, `link_name`,
`is_primary_contact`, `name`, system fields, User/Google fields, and arbitrary
custom fields. `phone` is accepted only as a semantic input that creates a
Contact Phone row; it is not the read-only parent `Contact.phone` projection.

## 7. Email semantics

The Contact controller’s `set_primary_email()` at
`contact.py:143-165` makes a single email row primary, rejects multiple primary
rows, and copies the primary child value to the read-only parent `email_id`.
`Contact Email.email_id` is required by metadata. The current MCP service also
uses Frappe’s `validate_email_address()` and rejects multi-address results
(`services/masters/customer_contact.py:268-281`). The standalone service should
reuse that bounded validation behavior.

V1 accepts one trimmed email only and constructs:

```text
email_ids = [{"email_id": email, "is_primary": 1}]
```

It must not accept raw child rows or multiple emails. Whitespace around the
public value is removed. Case-insensitive comparison (`casefold`) is suitable
for duplicate suspicion, but it does not rewrite stored values or claim that
Frappe enforces cross-Contact uniqueness. A duplicate email on another visible
Contact is a duplicate suspicion, not an automatic reuse or merge.

## 8. Phone and mobile semantics

The Contact controller’s `set_primary()` at `contact.py:167-188` treats
`is_primary_phone` and `is_primary_mobile_no` as independent flag families and
derives the read-only parent `phone` and `mobile_no` projections. A single
phone row can technically carry both flags, but the public API should not make
that ambiguity expressible.

V1 supports one `mobile` and one `phone` input:

| Public shape | Constructed rows |
|---|---|
| mobile only | `{phone: mobile, is_primary_mobile_no: 1}` |
| phone only | `{phone: phone, is_primary_phone: 1}` |
| mobile + phone | two rows, one with only mobile-primary and one with only phone-primary |
| multiple phones | rejected; child-table management is deferred |
| ambiguous “both” primary | rejected/not represented |

Phone validation should use the existing project/Frappe phone validation
boundary. No caller-supplied flags are accepted. The native Contact save
derives `mobile_no` and `phone`.

### Communication matrix

| Shape | V1 result |
|---|---|
| email only | Allowed; one primary email row |
| mobile only | Allowed; one primary-mobile row |
| phone only | Allowed; one primary-phone row |
| email + mobile | Allowed; independent child tables |
| mobile + phone | Allowed; two bounded phone rows |
| multiple emails | Rejected/deferred |
| multiple phones | Rejected/deferred |

## 9. No-link behavior

The preferred standalone payload omits `links` entirely. An explicit empty
`links=[]` is also native-compatible, but omission avoids constructing a child
table with no semantic rows. The server must never fabricate a Customer,
Supplier, or other Dynamic Link.

Expected native result:

```text
Contact
  links = []
  is_primary_contact = 0/default
```

No Customer/Supplier permission is required because no party is referenced.
No Customer projection is touched and no party-primary logic is triggered.
The public caller cannot set `is_primary_contact`.

## 10. Duplicate and reuse policy

Standalone creation has no Customer scope, so it must not silently reuse a
Contact. The service checks only permission-visible exact candidates using the
existing bounded search primitives.

| Signal | Policy | State |
|---|---|---|
| Same full name/company only | Do not infer identity; native autoname collision may create a suffixed Contact | Allowed with warning-free preview |
| Exact Contact document name | Not public create input; if native naming collides, suffix behavior applies | Not reuse/idempotency |
| Exact email visible to user | Return minimal candidate projection; do not create until user resolves whether to reuse/link | `CONTACT_DUPLICATE_SUSPECTED` / needs selection |
| Case-varied email visible | Compare with `casefold`; same duplicate policy | `CONTACT_DUPLICATE_SUSPECTED` |
| Exact normalized phone visible | Compare after the existing non-alphanumeric normalization; do not merge | `CONTACT_DUPLICATE_SUSPECTED` |
| Formatted phone variant visible | Same normalized-phone policy | `CONTACT_DUPLICATE_SUSPECTED` |
| Hidden email/phone duplicate | Do not disclose existence and do not query around permissions | Creation may proceed; no uniqueness claim |
| Duplicate appears after prepare | Recheck at confirm and stop if now visible | Retryable stale/duplicate result |

The duplicate candidate projection reuses Task 57’s bounded Contact projection:
doctype, name, full_name, company_name, email_id, mobile_no, phone,
is_primary_contact, and a safe link count. It does not return full links,
addresses, CRM data, child row names, or User data.

Exact duplicate detection is a safety signal, not idempotent reuse. Same-name
records are not automatically merged. If the user decides the visible Contact
is the intended record, the Agent should route to `search_contacts` and then
Task 57 `prepare_customer_contact(mode=link)` when a Customer is known.

## 11. Search reuse and later linking

Existing `search_contacts` can be reused unchanged:

- global exact name, email, and phone matching remains bounded;
- broad fuzzy global personal-name search remains prohibited;
- Customer-scoped fuzzy/name matching remains available only with Customer
  context;
- the existing Contact projection is sufficient for duplicate selection and
  later Customer linking.

No new search mode is required for standalone creation. `other_party_link_count`
is useful only as a bounded count; Task 57’s helper currently counts every
non-target Dynamic Link, not strictly business parties. That is a non-blocking
hardening item for projection semantics, not a reason to broaden search or
block standalone creation.

The later native flow is:

```text
prepare_contact -> confirm_contact
    -> standalone Contact exists

search_contacts
    -> prepare_customer_contact(mode=link)
    -> confirm_customer_contact
```

If the Customer relationship is known at the original request, do not create a
standalone Contact first. Use Task 57’s Customer-linked create flow directly.

## 12. Routing and profile placement

| User intent | Route |
|---|---|
| “Create contact Amit Shah” | `prepare_contact` |
| “Create Amit Shah with email, customer unknown” | `prepare_contact` |
| “Create Amit Shah as a contact for ABC Pvt Ltd” | `prepare_customer_contact(mode=create)` |
| “Link Amit Shah to ABC Pvt Ltd” | `search_contacts`, then `prepare_customer_contact(mode=link)` |
| “Create Amit now; I’ll assign him later” | `prepare_contact` |

The pair should be Sales-only for V1 because the current Contact capability,
Task 57 flow, and user need are registered in the Sales profile. Contact is not
theoretically Sales-only, but adding a generic/core or Purchase surface would
expand Supplier/Purchase semantics without an audited business boundary.
Future Purchase/Accounts exposure requires a separate capability audit.

## 13. Public API design

| Design | Assessment | Decision |
|---|---|---|
| Nullable `customer` on `prepare_customer_contact` | Blurs party-bound and standalone intent and weakens contract meaning | Reject |
| Dedicated `prepare_contact` / `confirm_contact` | Preserves intent, approval, and profile boundaries | **Select** |
| Generic create-master tool | Too broad; risks arbitrary fields and generic CRUD | Reject |
| Other architecture | No source-supported advantage over dedicated pair | Reject |

Exact names:

```text
prepare_contact
confirm_contact
```

The approval action should be `contact_create`, following the action-specific
write vocabulary while keeping `MCP_APPROVAL_MODE` server-controlled. The
implementation must use `ApprovalStore.claim_for_confirm_write()` and the
shared `InteractionDirective`; it must not add a public approval-policy field
or treat `confirm=true` as approval by itself.

## 14. Proposed typed contract

This is the next implementation contract, not code implemented by Task 59.
All public models inherit the existing `PublicContractModel` with
`extra="forbid"`.

```text
ContactCreateInput {
  first_name?: string
  middle_name?: string
  last_name?: string
  company_name?: string
  designation?: string
  department?: string
  email?: string
  mobile?: string
  phone?: string
}

PrepareContactInput {
  contact: ContactCreateInput
}

ConfirmContactInput {
  approval_token: string
  confirm: bool
}
```

The ready preview should contain only the accepted semantic fields, derived
`full_name`, `linked_to_customer=false`, `link_count=0`, and communication
summary. It must not contain raw child-row names, raw `links`, or internal
system fields.

The created result should reuse the bounded Contact projection and explicitly
report `linked_to_customer=false` and `other_party_link_count=0`.

## 15. Prepare behavior and CRM side effects

Required prepare flow:

```text
typed validation
  -> Contact create permission
  -> trim and validate semantic inputs
  -> construct exact unsaved native payload
  -> duplicate lookup under normal read permissions
  -> bounded preview and fingerprint
  -> shared approval record
```

Prepare must not insert, save, commit, create Dynamic Links, or write child
rows. It must not call `contact.run_method("validate")` on the preview
document. Frappe’s `Document.run_method()` dispatches controller methods and
hooks; Contact’s normal validation is followed by the CRM
`crm.api.contact.validate` event. That CRM hook queries CRM Contacts and can
write CRM Deal snapshots (`apps/crm/crm/api/contact.py:5-25`). Calling the
full hook-bearing chain during prepare would violate the non-mutating prepare
contract.

Instead, prepare should use safe in-memory input validation plus deterministic
preview derivation matching the native rules. Confirm remains the point where
native Contact validation and all installed hooks execute.

## 16. Confirm, transaction, and approval

Conceptual confirm flow:

```text
claim_for_confirm_write(action="contact_create")
  -> re-check Contact create permission
  -> re-run visible duplicate checks
  -> rebuild exact approved payload
  -> frappe.get_doc(payload)
  -> Contact.insert(ignore_permissions=False)
  -> native validation and installed hooks
  -> one outer transaction commit
  -> bounded projection
```

The standalone implementation should not copy Task 57’s internal service
commits blindly. Task 58 identified those commits as hardening work. The new
implementation should have one confirmation boundary and one outer commit,
with rollback on native failure. A separate Task 57 transaction-hardening task
is recommended but is not a prerequisite for the read/search reuse decision.

Approval state must bind:

```text
site = frappe.local.site
user = authenticated Frappe user
profile = sales / operation context
action = contact_create
exact normalized typed payload
duplicate candidate fingerprint
create-permission decision context
```

The existing shared approval store already binds action/site/user and protects
one-shot replay through `claim_for_confirm_write()`.

## 17. Stale state and idempotency

Because the Contact does not exist at prepare time, stale state is primarily:

- permission changed;
- a visible exact email or normalized-phone duplicate appeared;
- native name collision state changed;
- site/user/profile/action mismatch;
- the request may already have succeeded while the response was lost.

Confirm must stop on a newly visible duplicate rather than create a second
record. A replayed approval token must be rejected by the shared approval
store. If a response is lost, a new prepare with the same email/phone should
return duplicate suspicion; it must not claim `already_created` without a
stronger server-side idempotency key and exact identity evidence. Same name
alone is insufficient because native collision suffixing intentionally permits
distinct Contacts with the same displayed identity.

If true automatic lost-response recovery is required later, add a separate
server-side idempotency design bound to the exact user/site/payload and created
Contact. Do not add a caller-controlled Contact name or silently merge by
name.

## 18. Permission matrix

| Operation | Required permission |
|---|---|
| Prepare | `Contact` create via native permission API |
| Visible duplicate lookup | `Contact` read; permission-filtered query only |
| Confirm | Re-check `Contact` create; native `insert(ignore_permissions=False)` |
| Return existing duplicate candidate | `Contact` read for that candidate |
| Return newly created result | Bounded projection from the inserted document; if the implementation needs a reload, require normal Contact read |
| Customer linking later | Existing Task 57 Customer read + Contact read/write rules |

No Customer permission is required for standalone creation. No role names may
be hard-coded, and `ignore_permissions=True` is prohibited.

## 19. Data minimization and interaction states

The standalone result projection is:

```text
doctype
name
full_name
company_name?
email_id?
mobile_no?
phone?
is_primary_contact
linked_to_customer = false
other_party_link_count = 0
```

It must exclude all Dynamic Link rows, addresses, comments, CRM Deal data,
User data, child row names, system metadata, and arbitrary custom fields.

Use existing semantic interaction/error patterns:

| Condition | Result |
|---|---|
| Missing identity | `CONTACT_INVALID_IDENTITY` plus input directive |
| Invalid email | `CONTACT_INVALID_EMAIL` |
| Invalid phone/mobile | `CONTACT_INVALID_PHONE` |
| No create permission | `PERMISSION_DENIED` |
| Visible exact duplicate | `CONTACT_DUPLICATE_SUSPECTED`; minimal candidates and selection directive |
| Approval backend unavailable | existing confirmation-unavailable error |
| Token expired/consumed/wrong user/site/action | existing confirmation failure mapping |
| Duplicate/permission change at confirm | retryable stale/duplicate error |

Hidden Contacts must not be mentioned in messages or candidate output.

## 20. Task 57 dependency assessment

| Existing finding | Classification | Required follow-up |
|---|---|---|
| Task 57 commits inside create/link branches | Non-blocking hardening for Task 59 design; blocking for a shared transaction-quality claim | Create a separate transaction-boundary hardening task before relying on Task 57 for multi-document atomicity |
| `other_party_link_count` counts all non-target Dynamic Links | Non-blocking hardening for standalone create | Narrow the helper to the intended party-count semantics before using it for sensitive shared-Contact decisions |
| Existing exact global search is bounded and permission-aware | Not a blocker | Reuse unchanged |

Task 59 must not silently modify Task 57.

## 21. Implementation test matrix

### Contracts

- accept the nine V1 semantic fields;
- reject missing identity;
- reject extra fields;
- reject `links`, `email_ids`, `phone_nos`, `is_primary_contact`;
- reject `name`, `full_name`, `email_id`, `mobile_no`, system, User, and Google fields.

### Prepare

- no insert/save/child-table DB write;
- no commit;
- Contact create permission required;
- email trim/validation and multi-address rejection;
- mobile and phone validation;
- deterministic native-name/full-name preview;
- one email and one/two bounded phone rows;
- visible duplicate email and normalized phone handling;
- same-name-only creation remains allowed;
- CRM validate hook is not run during prepare.

### Confirm

- normal Contact insert with `ignore_permissions=False`;
- no Dynamic Link rows;
- native name collision suffix behavior;
- email child row and derived `email_id`;
- phone child flags and derived `phone`/`mobile_no`;
- normal installed hooks execute;
- one outer commit;
- native failure rolls back;
- bounded result contains no unrelated data.

### Approval and stale state

- valid approval;
- wrong user/site/action/profile;
- expiry;
- replay;
- `confirm=false`;
- self-approval policy remains server-controlled;
- duplicate appears after prepare;
- permission changes after prepare;
- lost-response recovery returns duplicate suspicion rather than a second write.

### Profile and transport

- Sales exposes both tools;
- Purchase and Accounts do not;
- contract registry and MCP output schema parity;
- REST fixed typed dispatch parity;
- generated tool catalog documentation;
- Task 57 tools remain unchanged;
- `search_contacts` remains unchanged.

## 22. Exact next implementation task

Create a follow-up implementation task titled:

```text
Task 60 — Standalone Contact Creation V1
```

It should modify only the necessary Contact contract/service/tool,
Sales-profile registration, registry, REST dispatch, focused tests, and tool
catalog documentation. It must implement the dedicated
`prepare_contact`/`confirm_contact` pair exactly as specified here, use the
shared approval and interaction contracts, preserve normal Frappe/CRM hooks,
and keep Customer-linked Contact creation/linking on Task 57’s separate route.

## 23. Limitations and unverified boundaries

- No live standalone Contact was inserted, by design; native insert behavior
  is source-verified and runtime metadata-verified, not live-write verified.
- Empty/nameless Contact insertion was not attempted; the public contract
  intentionally rejects it.
- Runtime effective permissions were inspected as metadata, but no
  permission-matrix mutation or user impersonation was performed.
- Runtime hook aggregation has a Bench JSON serialization limitation for the
  tuple-keyed aggregate result; app-specific CRM and ERPNext hook results plus
  checked-out source were used.
- Hidden duplicate behavior cannot be proven without access to hidden records;
  the report defines the non-enumerating permission-safe policy.

## 24. Actions not performed

No production standalone Contact capability, contract, service, tool,
registration, migration, build, database write, or business-record mutation
was performed by Task 59. The only added deliverable is this audit report.
