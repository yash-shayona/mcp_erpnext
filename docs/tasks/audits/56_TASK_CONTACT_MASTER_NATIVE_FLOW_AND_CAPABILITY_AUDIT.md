# Task 56 — Contact Master Native Flow and Customer-Linked Capability Audit

## 1. Task Identity

**Task Number:** 56  
**Title:** Contact Master Native Flow and Customer-Linked Capability Audit  
**Primary Profile Under Review:** `sales`  
**Primary Business Scope:** existing/new ERPNext Customer ↔ Frappe Contact capability  
**Mode:** architecture / native-flow audit only  
**Production implementation:** **NOT allowed in this task**  
**Primary deliverable:** `docs/inspect/CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md`

---

## 2. Why This Task Exists

The current MCP already supports Customer creation, Customer read/query, and generic lifecycle operations for existing supported documents.

The observed gap is this business flow:

```text
1. User creates a Customer with only the Customer name/business details.
2. Customer is successfully created.
3. Later, user wants to add a person/contact to that existing Customer.
4. The person may be completely new, or may already exist as a Contact.
5. User may also want to add/change email/mobile/phone later.
6. Current MCP has no dedicated Contact master capability.
```

The current generic Customer update path is not sufficient evidence that this should be solved as a normal scalar Customer update.

Current source already suggests an important distinction:

```text
Customer != Contact
```

and:

```text
Customer.customer_primary_contact -> Link(Contact)
Contact.links -> Dynamic Link rows to Customer / Supplier / other parties
Contact.email_ids -> Contact Email child rows
Contact.phone_nos -> Contact Phone child rows
```

The purpose of Task 56 is to determine the exact Frappe/ERPNext-native seam for exposing this safely through MCP **before any Contact tools are implemented**.

---

## 3. Current Confirmed MCP Baseline

Inspect the current worktree and verify this baseline rather than trusting this task file blindly.

At the time this task was written, the current `mcp_erpnext` source contains:

```text
mcp_erpnext/contracts/masters/customer.py
mcp_erpnext/config/masters/customer.py
mcp_erpnext/services/masters/customer.py
mcp_erpnext/tools/masters/customer.py
mcp_erpnext/services/masters/customer_read.py
mcp_erpnext/tools/masters/customer_read.py
mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/services/common/email.py
mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
```

Current Customer creation accepts a narrow nested contact input approximately shaped as:

```text
contact:
  first_name
  last_name
  email
  mobile
```

Current Customer configuration maps those values onto Customer creation payload fields such as:

```text
first_name
last_name
email_id
mobile_no
```

The Customer creation service checks Contact create permission when those fields are supplied.

The final Customer write currently uses the normal Customer document insertion path:

```text
frappe.get_doc(payload)
    -> Customer.insert(...)
    -> ERPNext Customer controller hooks
```

The audit must confirm the installed ERPNext behavior after that insertion, including whether and how the ERPNext Customer controller creates the primary Contact.

Current generic lifecycle update validation also appears to enforce:

```text
read-only fields -> not writable
Link values -> referenced document must already exist and be permitted
Table fields -> cannot be updated as scalar values
```

Therefore a value like:

```text
customer_primary_contact = "Amit"
```

must not be treated as "create a new Contact named Amit" unless native framework behavior explicitly proves such semantics.

The audit must verify all of this against current source and runtime metadata.

---

## 4. Problem Statement

We need a safe MCP answer for all of these user intents:

```text
A. Create Customer with Contact in the same initial Customer creation request.

B. Add a brand-new Contact to an already existing Customer.

C. Link an already existing Contact to an existing Customer.

D. Make a linked Contact the Customer's primary Contact.

E. Update the Contact's name/designation/email/mobile/phone later.

F. Add or change primary/secondary email or phone rows without corrupting Contact child tables.

G. Search/read Contacts related to a Customer without leaking unrelated Contact data.
```

Task 56 must determine which of these belong in the first implementation and which must be deferred.

Do not assume that all seven should become V1 tools.

---

## 5. Core Architecture Principle

Preserve the project rule:

```text
MCP exposes business capability.
Frappe / ERPNext owns Contact and Customer truth.
```

MCP may own:

- bounded public inputs;
- user-intent interpretation at the tool contract boundary;
- permission-preserving reads;
- duplicate/ambiguity handling;
- preview generation;
- approval token creation;
- stale-state fingerprinting;
- idempotency/retry guards where needed;
- profile/tool registration;
- bounded result projection;
- user-safe error translation.

Frappe / ERPNext must continue to own:

- Contact DocType validation;
- Contact naming;
- Contact email validation;
- Contact Email child-table semantics;
- Contact Phone child-table semantics;
- Dynamic Link storage and deduplication;
- primary email logic;
- primary phone/mobile logic;
- primary Contact conflict behavior;
- Customer primary-contact behavior;
- permission enforcement;
- hooks;
- document events;
- any installed app extension behavior.

Do **not** build a second Contact engine in `mcp_erpnext`.

---

## 6. Critical Non-Goal

Task 56 is **not**:

```text
"add Contact tools"
```

Task 56 is:

```text
"find the exact installed Frappe/ERPNext Contact boundary and define the
smallest safe Customer-linked MCP Contact capability for the next task"
```

During Task 56:

- do not add production Python code;
- do not add MCP tools;
- do not register Contact in any profile;
- do not change Customer create/update behavior;
- do not add lifecycle policy for Contact;
- do not add arbitrary Dynamic Link mutation;
- do not create/delete/edit real business Contacts on a production site;
- do not change ERPNext/Frappe code;
- do not broaden permission behavior.

---

## 7. Required Inputs / Source of Truth

Use the **current checked-out worktree** and the **installed app source** as source of truth.

At minimum inspect:

```text
apps/mcp_erpnext
apps/frappe
apps/erpnext
```

Also inspect installed optional apps if they hook Customer/Contact behavior.

If present and relevant, include:

```text
apps/india_compliance
```

Do not assume GitHub `develop` matches the installed version.

Official Frappe/ERPNext repository code may be used as supporting reference, but installed source wins for runtime behavior.

Record the actual versions/commits inspected in the report.

---

## 8. Required Existing MCP Files to Inspect

At minimum trace these current MCP areas:

```text
mcp_erpnext/contracts/masters/customer.py
mcp_erpnext/config/masters/customer.py
mcp_erpnext/services/masters/customer.py
mcp_erpnext/tools/masters/customer.py

mcp_erpnext/contracts/masters/customer_read.py
mcp_erpnext/services/masters/customer_read.py
mcp_erpnext/tools/masters/customer_read.py

mcp_erpnext/contracts/lifecycle.py
mcp_erpnext/services/common/lifecycle.py
mcp_erpnext/tools/lifecycle.py

mcp_erpnext/services/common/email.py
mcp_erpnext/tools/email.py

mcp_erpnext/profiles/sales.py
mcp_erpnext/tools/__init__.py
mcp_erpnext/contracts/registry.py
mcp_erpnext/remote_operations.py
```

Also inspect tests covering those paths.

The report must explain how Contact capability would fit the existing architecture rather than creating a parallel pattern without reason.

---

## 9. Required Frappe Contact Areas to Inspect

Verify exact installed paths first.

At minimum inspect the installed implementation around:

```text
frappe/contacts/doctype/contact/contact.py
frappe/contacts/doctype/contact/contact.json
frappe/contacts/doctype/contact_email/
frappe/contacts/doctype/contact_phone/
frappe/contacts/doctype/dynamic_link/
frappe/contacts/address_and_contact.py
```

Search for and trace concepts/functions including, where present:

```text
Contact.validate
Contact.autoname
Contact.validate_primary_contact
Contact.set_primary_email
Contact.set_primary
Contact.add_email
Contact.add_phone
Contact.has_link
Contact.get_link_for
get_contacts_linking_to
get_default_contact
get_contact_display_list
deduplicate_dynamic_links
Dynamic Link
is_primary_contact
email_ids
phone_nos
email_id
mobile_no
phone
links
```

Do not merely list functions.

Trace the actual mutation and validation chain.

---

## 10. Required ERPNext Customer Areas to Inspect

At minimum inspect the installed implementation around:

```text
erpnext/selling/doctype/customer/customer.py
erpnext/selling/doctype/customer/customer.json
erpnext/selling/doctype/customer/mapper.py
```

Search for and trace concepts/functions including, where present:

```text
Customer.on_update
Customer.create_primary_contact
Customer.create_primary_address
Customer.link_address_and_contact
customer_primary_contact
email_id
mobile_no
first_name
last_name
make_contact
get_customer_primary
```

Also inspect any shared party/address/contact helper used by Customer or Sales transactions.

---

## 11. Audit Question A — What Really Happens During Current Customer Creation?

Trace this exact current MCP flow:

```text
prepare_customer
    -> approval payload
    -> confirm_customer
    -> Customer.insert()
    -> ERPNext Customer hooks
    -> ?
```

Answer with exact evidence:

1. If nested contact fields are provided during Customer creation, does current ERPNext automatically create a Contact?
2. Which Customer hook triggers it?
3. Which helper creates the Contact?
4. Which Contact fields/child rows are created?
5. Which Dynamic Link is added?
6. Is the new Contact marked `is_primary_contact`?
7. Is `customer_primary_contact` populated on Customer?
8. Are Customer `email_id`, `mobile_no`, `first_name`, `last_name` stored independently or fetched/derived from Contact?
9. What happens if only email is given and no first name?
10. What happens if only mobile is given?
11. What happens if Contact permission is missing?
12. Does Customer insertion remain atomic if Contact creation fails?
13. What happens when an optional installed app modifies Customer quick-entry behavior?

The report must clearly separate:

```text
MCP behavior
ERPNext Customer behavior
Frappe Contact behavior
```

---

## 12. Audit Question B — Why Does Existing Customer Update Not Create a Contact?

Trace the current generic lifecycle update path for Customer.

Prove from runtime metadata and code whether these are writable:

```text
customer_primary_contact
email_id
mobile_no
first_name
last_name
```

For each field state:

- fieldtype;
- read_only;
- fetch_from;
- options;
- current lifecycle validation behavior;
- whether assigning it can safely represent "create Contact".

Specifically explain:

```text
customer_primary_contact is Link -> Contact
```

and whether current lifecycle validation requires the Contact to already exist.

The report must answer whether the existing failure is:

```text
A. a bug in generic Customer update
B. correct Link validation exposing a missing Contact capability
C. both
D. another cause proven by source
```

Do not decide from assumption.

---

## 13. Audit Question C — Exact Native Contact Data Model

Document the effective installed Contact model.

At minimum identify:

### Parent Contact fields

Examples to inspect, not blindly expose:

```text
first_name
middle_name
last_name
full_name
salutation
designation
gender
company_name
is_primary_contact
user
email_id
phone
mobile_no
```

### Contact Email child table

Determine exact fields and validation semantics around:

```text
email_id
is_primary
```

### Contact Phone child table

Determine exact fields and validation semantics around:

```text
phone
is_primary_phone
is_primary_mobile_no
```

### Dynamic Link child table

Determine exact fields and validation semantics around:

```text
link_doctype
link_name
link_title
```

For every relevant field, distinguish:

```text
caller-provided public input
server-derived value
Frappe-derived value
read-only projection
internal-only value
```

---

## 14. Audit Question D — Contact Naming and Mandatory Inputs

Do not hard-code assumptions such as:

```text
first_name is always mandatory
```

Inspect runtime metadata and controller behavior.

Determine:

1. effective mandatory fields;
2. naming/autoname behavior;
3. how full name is calculated;
4. what happens when a same-named Contact already exists;
5. whether Contact names are guaranteed unique through suffixing;
6. whether a company-only Contact is valid;
7. whether at least one email/phone is required;
8. whether Customer linkage is required;
9. whether Dynamic Link rows influence naming;
10. which inputs should V1 require even if Frappe technically allows less.

The report must distinguish:

```text
framework-required
business-capability-required
optional
```

---

## 15. Audit Question E — Creating a New Contact for an Existing Customer

Determine the smallest native mutation path for:

```text
existing Customer
+
new Contact person details
->
new Contact linked to that Customer
```

Compare candidate native approaches such as:

```text
frappe.new_doc("Contact") / frappe.get_doc({...}).insert()
ERPNext/Frappe helper functions
Customer-specific helper paths
```

Do not prefer a helper merely because it exists.

For each candidate, document:

- permission behavior;
- validation behavior;
- Dynamic Link behavior;
- primary Contact behavior;
- child email/phone behavior;
- hooks;
- atomicity;
- suitability for prepare/confirm;
- whether it bypasses permissions;
- whether it is intended only for internal controller use.

Recommend one native seam for the future implementation.

---

## 16. Audit Question F — Linking an Existing Contact to a Customer

This is mandatory for the audit.

Example intent:

```text
Contact "Amit Shah" already exists.
Customer "ABC Pvt Ltd" already exists.
User says: link Amit Shah as a contact for ABC Pvt Ltd.
```

Determine the correct native mutation.

Answer:

1. Is adding a Dynamic Link row to Contact the authoritative relationship?
2. Is there a Frappe helper for this that should be reused?
3. Does Contact validation deduplicate duplicate Dynamic Link rows?
4. Can one Contact link to multiple Customers?
5. Can one Contact link to both Customer and Supplier?
6. Are there security/user-permission implications when reading or linking cross-party Contacts?
7. What permissions are required on Contact and Customer?
8. Does linking an existing Contact automatically make it primary?
9. Should V1 ever allow caller-supplied arbitrary `link_doctype`?
10. How should an already-existing identical link behave: idempotent success, error, or no-op?

The audit should strongly prefer a **Customer-scoped public intent** over arbitrary Dynamic Link editing unless source evidence proves a broader surface is necessary.

---

## 17. Audit Question G — Primary Contact Semantics

This is a high-risk area and must be traced completely.

There are potentially two related concepts:

```text
Contact.is_primary_contact
Customer.customer_primary_contact
```

Do not assume they are always synchronized automatically.

Determine exactly:

1. What happens when `Contact.is_primary_contact = 1` and Contact is saved?
2. Does Frappe unset other primary Contacts linked to the same party?
3. Is concurrency locking used?
4. Does that operation update `Customer.customer_primary_contact`?
5. What happens when Customer's `customer_primary_contact` is changed directly to an existing Contact?
6. Does Customer validate that the selected Contact is actually linked to that Customer?
7. Does Customer setting ensure `Contact.is_primary_contact = 1`?
8. If a Customer has several Contacts, what does the UI/native helper treat as default?
9. What happens if Contact A is primary and Contact B is selected as Customer primary?
10. What happens if one Contact is linked to more than one party and marked primary?
11. Does Frappe define primary independently per linked party or globally per Contact record?

This section must produce an exact state-transition table.

Example required report format:

```text
Starting State | Operation | Contact flags after | Customer link after | Other contacts after | Native code path
```

---

## 18. Audit Question H — Updating Contact Email and Phone Correctly

The future MCP must not treat Contact email/mobile as ordinary unrelated scalars if native source derives them from child rows.

Trace:

```text
Contact.email_ids
Contact.phone_nos
Contact.email_id
Contact.phone
Contact.mobile_no
```

Answer:

1. How primary email is chosen.
2. Whether a single email automatically becomes primary.
3. Whether multiple primary emails are rejected.
4. How primary phone is chosen.
5. How primary mobile is chosen.
6. Whether the same phone row can be both primary phone and primary mobile.
7. How duplicate emails are handled.
8. How duplicate phone rows are handled.
9. What helper methods such as `add_email` / `add_phone` do.
10. Whether those helpers save with `ignore_permissions=True` internally and therefore are suitable or unsuitable as the public mutation seam.
11. How email validation is enforced.
12. Whether modifying child rows through generic lifecycle update would preserve Contact controller logic.
13. Whether V1 should support:
    - replace primary email;
    - add secondary email;
    - remove email;
    - replace primary mobile;
    - add secondary phone;
    - remove phone.

Do not automatically include every operation in V1.

---

## 19. Audit Question I — Duplicate Contact Detection

Contact names alone are not enough to establish identity.

Determine native duplicate/reuse signals available from installed source.

Inspect at least:

```text
exact Contact name
full_name
email_ids / Contact Email
phone_nos / Contact Phone
existing Dynamic Links
```

Determine whether the future MCP should:

```text
A. always create a new Contact
B. always force selection if same email exists
C. search and propose reuse before create
D. use a bounded combination of exact email/mobile/name/link evidence
```

The report must define a safe duplicate/ambiguity strategy.

Do not invent fuzzy identity merging without source evidence.

Do not automatically merge Contacts.

---

## 20. Audit Question J — Search and Read Capability

Determine the minimum read surface needed before mutation.

Potential user intents:

```text
"find Amit"
"show contacts for ABC Pvt Ltd"
"does amit@example.com already exist?"
"who is ABC's primary contact?"
```

Audit whether native query helpers can be reused safely.

Define safe filters/outputs for a future Contact search/read capability.

The report must address data minimization.

Do not expose entire Contact documents to the LLM by default.

Candidate bounded fields to evaluate:

```text
name
full_name
first_name
last_name
company_name
email_id
mobile_no
phone
is_primary_contact
customer linkage summary
```

The audit must decide what is actually necessary.

Also determine whether querying by email/mobile requires joining child tables rather than only parent projected fields.

---

## 21. Audit Question K — Permission Model

Trace exact permission behavior for:

```text
Contact read
Contact create
Contact write
Customer read
Customer write
Dynamic Link child mutation
Contact Email child mutation
Contact Phone child mutation
```

Determine whether normal `doc.insert()` / `doc.save()` is sufficient to preserve permission checks.

Audit any native helper that uses:

```text
ignore_permissions=True
```

and explain whether the future MCP may call it safely or should reproduce the intended native document operation while preserving caller permission.

Preserve the project identity model:

```text
authenticated MCP request
-> verified Frappe user
-> normal Frappe permissions
```

Do not create a special Contact permission bypass.

---

## 22. Audit Question L — Existing Customer Creation Must Not Regress

Task 56 must explicitly decide whether the existing Customer creation flow should remain as-is.

Current desired behavior:

```text
Create Customer + contact details in one request
-> Customer is created
-> ERPNext-native Contact behavior occurs
```

A future dedicated Contact capability must not require users to split that already-valid initial creation into unnecessary multiple tools unless the audit proves the current path is unsafe.

The report must answer:

```text
Should current prepare_customer/confirm_customer nested contact input remain supported?
```

If yes, state why and define regression tests.

If no, provide exact source-grounded reason and migration impact.

---

## 23. Audit Question M — Customer Read Interoperability

Current Customer read capability exposes fields such as:

```text
email_id
mobile_no
```

Audit their actual runtime source after Contact creation/update.

Determine:

1. whether they are `fetch_from` projections from `customer_primary_contact`;
2. when they refresh;
3. whether a Contact update is immediately reflected in subsequent Customer reads;
4. whether Customer needs save/reload;
5. whether changing primary Contact changes those projections;
6. whether MCP Customer read should continue exposing them as convenience projections.

Do not duplicate Contact state into MCP-owned storage.

---

## 24. Audit Question N — Email Capability Interoperability

The current generic document email service already inspects native document/party Contact information.

Trace current behavior in:

```text
mcp_erpnext/services/common/email.py
```

Determine how a new Contact created/linked through future tools would affect:

```text
Sales Order recipient resolution
Quotation recipient resolution
Sales Invoice recipient resolution
Customer recipient fallback
selected contact handling
primary contact handling
```

The future Contact capability should strengthen existing native recipient resolution, not create a second recipient store.

Document required regression tests.

---

## 25. Audit Question O — Sales Transaction Interoperability

Current Sales transactions may contain fields such as:

```text
contact_person
contact_display
contact_email
contact_mobile
contact_phone
```

Audit the relevant installed ERPNext transaction helper flow to determine:

1. how a Customer's primary Contact is selected on new Sales documents;
2. whether any linked Contact can be selected;
3. whether transactions copy Contact values at creation time;
4. whether later Contact edits alter existing transaction values;
5. whether new Contact tools need any transaction-specific update behavior.

Do not add transaction mutation to Task 56.

This is only to prevent an incorrect Contact design.

---

## 26. Audit Question P — Generic Lifecycle Reuse vs Dedicated Contact Service

Compare these future implementation strategies:

### Option A — Generic lifecycle only

```text
create/update Contact through generic document lifecycle
```

### Option B — Dedicated Contact service only

```text
explicit Contact contracts/services/tools
```

### Option C — Dedicated creation/linking + shared lifecycle for safe existing Contact edits

### Option D — Another hybrid proven by current architecture

Evaluate each against:

- nested child-table mutation;
- Dynamic Link semantics;
- primary Contact behavior;
- duplicate detection;
- explicit approval;
- stale-state checks;
- permissions;
- data minimization;
- REST transport registry;
- profile registration;
- current project conventions.

Recommend exactly one architecture for Task 57.

Do not choose based on code reuse alone.

---

## 27. Audit Question Q — Public Tool Surface for V1

The report must recommend the **minimum** public tool surface for Task 57.

Possible capabilities to evaluate include:

```text
search_contacts
get_contact
query_contacts
resolve_contact

prepare_customer_contact
confirm_customer_contact

prepare_contact_update
confirm_contact_update

prepare_customer_contact_link
confirm_customer_contact_link

prepare_customer_primary_contact
confirm_customer_primary_contact
```

These names are candidates only.

Do **not** assume all should exist.

The report must answer whether creation + link + optional make-primary should be one bounded business operation such as:

```text
prepare_customer_contact
confirm_customer_contact
```

or separate operations.

Prefer fewer tools when one tool represents one coherent business intent without hiding materially different destructive effects.

Avoid tools such as:

```text
create_any_contact
link_any_doctype
mutate_dynamic_link
update_any_contact_field
upsert_contact_everything
```

unless the audit proves such a surface is necessary and safe.

---

## 28. Audit Question R — Profile Placement

Current business need is Customer Contact management in the Sales domain.

Determine Task 57 registration scope.

At minimum compare:

```text
sales-only Contact capability
shared master capability registered in sales and purchase
future generic core profile
```

Current project direction does not require Purchase Contact behavior merely because Contact can technically link to Supplier.

Do not broaden V1 just for theoretical reuse.

The report must state the exact recommended profile registration for Task 57.

---

## 29. Audit Question S — Approval / Stale-State Model

All Contact writes must fit the existing explicit approval architecture unless the operation is demonstrably read-only.

For each recommended write operation, define prepare-time and confirm-time state.

Potential stale-state inputs include:

```text
Customer identity/existence
Contact identity/existence
existing Dynamic Link rows
current customer_primary_contact
current is_primary_contact state
current email child rows
current phone child rows
modified timestamp
```

The report must define which of these belong in a future fingerprint.

Example race conditions to consider:

```text
- Contact created after prepare but before confirm.
- Same existing Contact linked to Customer after prepare.
- Another user changes Customer primary Contact before confirm.
- Another user edits Contact email before confirm.
- Another user deletes Contact before confirm.
- Two users concurrently mark different Contacts primary.
```

Reuse the shared approval store/fingerprint architecture where appropriate.

Do not create a Contact-specific approval store.

---

## 30. Audit Question T — Atomicity and Transaction Boundaries

Determine transaction requirements for future flows such as:

```text
create Contact
+
append Customer Dynamic Link
+
make Contact primary
+
update Customer primary Contact if native behavior requires it
```

Answer:

1. Can this be one normal Frappe document insert/save transaction?
2. Are multiple document writes required?
3. Does native controller code already perform them atomically?
4. Where should `frappe.db.commit()` live according to current MCP architecture?
5. What must happen on validation/permission failure halfway through?
6. How should retries avoid duplicate Contact creation?

Do not add manual commits inside arbitrary helpers unless consistent with current service architecture.

---

## 31. Audit Question U — Deletion / Unlink Scope

Task 56 must inspect but **not necessarily recommend** destructive Contact operations for V1.

Determine native semantics for:

```text
unlink Contact from Customer
delete Contact
remove one email
remove one phone
clear primary Contact
```

Document risks such as:

- same Contact linked to multiple parties;
- transaction references;
- portal user linkage;
- communication/history implications;
- primary-contact fallback behavior.

Default Task 57 recommendation should defer destructive Contact operations unless a clear immediate business need and safe native path are proven.

---

## 32. Audit Question V — REST / HTTP / stdio Parity

Any future Contact tools must work through the existing runtime boundary, including supported transports.

Audit required changes that Task 57 would need in areas such as:

```text
tool registration
contracts registry
remote operation registry
REST argument serialization
profile tests
tool catalog/docs generation
```

Do not implement them in Task 56.

The report must list exact integration points.

---

## 33. Allowed Changes During Task 56

Task 56 is inspection-only.

Allowed production-repository change:

```text
docs/inspect/CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md
```

Optionally, if the repository convention requires it, the agent may update a purely documentary index that lists inspection reports, but only if no production behavior changes.

Not allowed:

```text
mcp_erpnext/**/*.py production changes
hooks changes
DocType changes
patches
fixtures
profile registration
new MCP tools
permission changes
ERPNext/Frappe modifications
site data mutation
```

Do not use this audit as permission for cleanup/refactoring unrelated files.

---

## 34. Required Audit Procedure

Follow this order.

### Step 1 — Record current repository state

Capture:

```text
branch
HEAD commit
worktree status
installed Frappe version
installed ERPNext version
installed optional relevant app versions
```

Do not discard or overwrite pre-existing dirty worktree changes.

### Step 2 — Trace current MCP Customer create flow

Document exact files/functions and current nested Contact handling.

### Step 3 — Trace current Customer generic update restrictions

Use current runtime metadata plus lifecycle code.

### Step 4 — Trace Frappe Contact parent + child DocTypes

Inspect controller and runtime metadata.

### Step 5 — Trace Dynamic Link behavior

Include deduplication and permissions.

### Step 6 — Trace primary Contact behavior

Cover both Contact and Customer sides completely.

### Step 7 — Trace new-Contact-for-existing-Customer native flow

Find the smallest permission-preserving seam.

### Step 8 — Trace existing-Contact-to-Customer linking flow

Include idempotency and cross-party implications.

### Step 9 — Trace Contact email/phone update semantics

Identify what must remain controller-owned.

### Step 10 — Trace read/search helpers

Design a minimal safe data projection.

### Step 11 — Check current MCP email + sales interoperability

Do not design in isolation.

### Step 12 — Compare architecture options

Recommend one future implementation architecture.

### Step 13 — Define exact Task 57 scope

Include exact public tools, inputs, outputs, profile, permissions, approval, fingerprint, tests, and explicit exclusions.

### Step 14 — Write only the audit report

No production implementation.

---

## 35. Required Runtime Metadata Checks

Where a runnable development site is available, inspect effective runtime metadata rather than relying only on JSON files.

At minimum verify metadata for:

```text
Customer
Contact
Contact Email
Contact Phone
Dynamic Link
```

For relevant fields record:

```text
fieldname
fieldtype
options
reqd
read_only
fetch_from
hidden
no_copy
allow_on_submit
```

Do not hard-code one site name.

Use the configured/current development site only.

If runtime inspection is not possible, state that limitation explicitly and distinguish static-source conclusions from runtime-verified conclusions.

---

## 36. No Destructive Production Testing

Do not mutate real customer/contact data merely to prove behavior.

Permitted verification hierarchy:

```text
1. installed source inspection
2. existing automated tests
3. isolated unit tests or existing test fixtures
4. explicitly authorized throwaway/development-site reproduction
```

If a write test is necessary and a safe test site is not explicitly available, specify the test for Task 57 instead of performing it.

---

## 37. Required Future V1 Test Matrix

The Task 56 report must define a Task 57 test matrix covering at least the following.

### Existing Customer creation regression

```text
Customer + contact in initial create still works
Customer with name only still works
Customer + email only behavior
Customer + mobile only behavior
missing Contact create permission
```

### New Contact for existing Customer

```text
valid new Contact
Customer not found
Customer read denied
Contact create denied
missing required Contact input
invalid email
duplicate/suspected duplicate email
```

### Existing Contact linking

```text
link existing Contact to Customer
already-linked Contact is idempotent/safely handled
Contact not found
Contact read/write denied
Customer denied
Contact already linked to another Customer
Contact linked to Supplier + Customer where native model permits
```

### Primary Contact

```text
first Customer Contact becomes primary if V1 chooses that behavior
make second linked Contact primary
existing primary Contact is demoted correctly
Customer.customer_primary_contact stays consistent
concurrent primary changes
```

### Email / phone update

```text
replace primary email
add secondary email if supported
single email auto-primary behavior
reject multiple primary emails
replace primary mobile
phone/mobile primary semantics
invalid email
no duplicate child row corruption
```

### Approval / stale state

```text
Contact changed after prepare
Customer primary changed after prepare
link added after prepare
Contact deleted after prepare
approval token replay
wrong user/site token
expired token
confirm=false
```

### Transport / profile

```text
sales profile exposes intended tools only
accounts profile does not accidentally expose them
purchase profile behavior matches Task 56 decision
stdio path
HTTP/REST backend path
remote operation registry parity
```

### Read/data minimization

```text
search by name
search by exact email
contacts for Customer
primary Contact lookup
no unrelated Contact leakage
permission-filtered results
bounded output only
```

### Existing email capability regression

```text
new primary Contact becomes usable by native recipient resolution
existing Sales document recipient behavior unchanged
no arbitrary unrelated email becomes selectable
```

---

## 38. Required Security / Data-Leak Review

Because Contact contains personal/business communication data, the audit must explicitly review what the LLM actually needs.

For every recommended Contact read/search tool, document:

```text
input fields
output fields
why each output is necessary
whether the value is sensitive/business data
whether permission filtering applies
whether a narrower projection is possible
```

Do not return:

```text
full Contact document JSON
all linked documents
all communications
all comments
all metadata
all child-table internals
User linkage
private framework fields
```

unless a specific future business capability needs them and the report justifies it.

---

## 39. Required Error Model Recommendation

Recommend bounded future errors for conditions such as:

```text
CUSTOMER_NOT_FOUND
CONTACT_NOT_FOUND
CONTACT_PERMISSION_DENIED
CONTACT_DUPLICATE_SUSPECTED
CONTACT_ALREADY_LINKED
CONTACT_INVALID_EMAIL
CONTACT_INVALID_PHONE
CONTACT_PRIMARY_CONFLICT
CONTACT_STALE_STATE
CONTACT_LINK_STALE_STATE
CONFIRMATION_REQUIRED
APPROVAL_EXPIRED / invalid approval state
```

Names above are examples only.

Reuse existing shared error/interaction conventions instead of inventing a second response style.

The report must state which errors should be user-correctable versus terminal/retryable.

---

## 40. Required Decision Matrix

The audit report must include a compact decision matrix with at least these rows:

```text
Capability
Native source/helper
Public tool needed?
Approval needed?
Profile
V1 / deferred
Reason
```

Rows must include:

```text
search Contact
read Contact
create new Contact for Customer
link existing Contact to Customer
make Contact primary
update Contact name/details
replace/add email
replace/add phone/mobile
unlink Contact
clear primary Contact
delete Contact
arbitrary Dynamic Link mutation
Supplier Contact support
```

---

## 41. Required Recommended V1 User Flows

The report must provide concrete end-to-end flows for at least these three scenarios.

### Flow 1 — Customer already exists, person is new

```text
User: Add Amit Shah to ABC Pvt Ltd with amit@example.com and 999...
    -> search/resolve Customer
    -> duplicate Contact check
    -> prepare bounded Contact creation/link
    -> preview
    -> user approval
    -> confirm
    -> native Contact insert + Customer link
    -> optional primary behavior according to audited rule
    -> bounded result
```

### Flow 2 — Customer already exists, Contact already exists

```text
User: Link existing Amit Shah to ABC Pvt Ltd
    -> resolve Customer
    -> resolve Contact
    -> verify not already linked / idempotent state
    -> prepare link
    -> preview
    -> approval
    -> confirm
    -> native link mutation
    -> bounded result
```

### Flow 3 — Change Customer's Contact email later

```text
User: Change Amit's email to accounts@abc.com
    -> resolve Contact in Customer context
    -> prepare Contact email update
    -> preview old/new primary email
    -> approval
    -> confirm
    -> native Contact child-table/controller path
    -> bounded result
```

If the audit recommends deferring Flow 3 from V1, explain why and move it explicitly to a later task.

---

## 42. Expected Result of Task 56

At completion, we should know with source evidence:

1. exactly why Customer-only creation can currently produce a Contact when contact data is supplied;
2. exactly why a later Customer scalar update cannot safely substitute for Contact creation;
3. exact Contact parent/child/link data model;
4. exact native path to create a Contact for an existing Customer;
5. exact native path to link an existing Contact to a Customer;
6. exact primary Contact synchronization semantics;
7. exact native email/phone update rules;
8. duplicate/reuse strategy;
9. minimum safe Contact read/search projection;
10. required permissions;
11. approval and stale-state model;
12. profile placement;
13. minimum Task 57 tool surface;
14. what Contact capabilities remain deferred.

The result must be strong enough that Task 57 can be implementation-only and does not need to rediscover basic architecture.

---

## 43. Required Report Structure

Create:

```text
docs/inspect/CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md
```

Use at least this structure:

```text
# Contact Master Native Flow and Customer-Linked Capability Audit

1. Executive summary
2. Repository/app versions and source inspected
3. Current MCP Customer capability baseline
4. Current Customer + nested Contact creation call chain
5. Current Customer update limitation/root cause
6. Runtime Customer metadata relevant to Contact
7. Runtime Contact metadata
8. Contact Email child-table semantics
9. Contact Phone child-table semantics
10. Dynamic Link semantics
11. Contact naming/mandatory-input behavior
12. Native new Contact -> existing Customer flow
13. Native existing Contact -> Customer linking flow
14. Primary Contact state-transition analysis
15. Email/phone mutation analysis
16. Duplicate/reuse analysis
17. Search/read/data-minimization analysis
18. Permission analysis
19. Customer read interoperability
20. Email capability interoperability
21. Sales transaction interoperability
22. Generic lifecycle reuse vs dedicated service comparison
23. Approval/fingerprint/concurrency recommendation
24. Atomicity/idempotency recommendation
25. Profile placement
26. V1 vs deferred decision matrix
27. Recommended Task 57 public tool surface
28. Recommended Task 57 contracts/inputs/outputs
29. Recommended Task 57 test matrix
30. Security/data-leak review
31. Limitations / unknowns
32. Exact Task 57 recommendation
```

Every material claim about behavior must point to the exact installed file/function/metadata evidence used.

---

## 44. Acceptance Criteria

Task 56 is complete only when all of the following are true.

### AC-01 — Current flow traced

The report proves the current MCP Customer create path and native Contact side effect, if any.

### AC-02 — Root cause established

The report proves why adding a Contact later cannot currently be represented by ordinary Customer update.

### AC-03 — Runtime metadata inspected

Customer, Contact, Contact Email, Contact Phone, and Dynamic Link effective metadata are documented or an explicit runtime-inspection limitation is recorded.

### AC-04 — Native creation seam identified

One permission-preserving native approach for creating a Contact linked to an existing Customer is recommended.

### AC-05 — Existing Contact link seam identified

One safe approach for linking an existing Contact to a Customer is recommended, including idempotency semantics.

### AC-06 — Primary Contact semantics proven

The report contains an exact state-transition analysis for `is_primary_contact` and `customer_primary_contact`.

### AC-07 — Email/phone semantics proven

The report explains parent projection vs child-row authority and how primary values are maintained.

### AC-08 — Duplicate strategy defined

The report recommends a bounded duplicate/reuse/selection strategy without automatic merging.

### AC-09 — Permissions defined

Required Customer/Contact permissions and any native helper permission bypasses are documented.

### AC-10 — Data minimization defined

Future read/search outputs are bounded and justified field-by-field.

### AC-11 — Existing Customer create regression decision made

The report explicitly says whether current nested Contact input stays unchanged in future work.

### AC-12 — Existing email/sales interoperability covered

The report explains how Contact changes interact with native recipient resolution and sales transaction Contact fields.

### AC-13 — Architecture choice made

Dedicated service vs generic lifecycle vs hybrid is decided with evidence.

### AC-14 — V1 tool surface is exact

The report names the exact Task 57 tools to implement and excludes unnecessary generic tools.

### AC-15 — Approval/fingerprint model defined

Future write operations have an explicit prepare/confirm and stale-state recommendation.

### AC-16 — Test matrix complete

Task 57 has a concrete regression, permission, stale-state, profile, transport, and data-leak test matrix.

### AC-17 — No production behavior changed

Only the audit report/documentary changes allowed by this task are present.

### AC-18 — Exact next task stated

The report ends with one exact Task 57 recommendation.

---

## 45. Tests / Verification for Task 56 Itself

Because Task 56 is audit-only, verification is mostly documentary and repository-based.

Run/check at minimum:

```text
1. git status before inspection
2. current task numbering confirms 56 is next
3. source searches for all Contact/Customer helpers cited
4. runtime metadata inspection where a safe configured dev site is available
5. existing relevant MCP unit tests to understand current behavior
6. git diff at end
```

Final diff must show no unintended production-code changes.

If existing tests are executed, record commands and results in the report.

Do not claim a runtime behavior was tested if it was only inferred from source.

---

## 46. Limitations / Guardrails

Task 56 must not solve unrelated master-data design.

Explicitly out of scope unless required only for dependency understanding:

```text
Address CRUD
Supplier Contact implementation
Lead Contact implementation
Prospect Contact implementation
portal User creation/invitation
Google Contacts sync
communication timeline changes
CRM app-specific Contact UI
bulk Contact import
Contact merge
Contact deduplication engine
marketing consent
WhatsApp-specific Contact model
arbitrary party relationship management
```

Supplier and other party links may be inspected only to understand the generic Dynamic Link model and prevent a Customer-specific implementation from breaking framework semantics.

---

## 47. Exact Next Task After Task 56

If Task 56 confirms the expected architecture, the next task must be:

```text
Task 57 — Customer-Linked Contact V1 Implementation
```

Task 57 should implement **only the smallest safe vertical slice proven by Task 56**.

Expected Task 57 direction, subject to Task 56 evidence:

```text
- bounded Contact search/read needed for selection;
- create a Contact for an existing Customer;
- reuse/link an existing Contact rather than duplicate it;
- optional primary Contact behavior only if native semantics are fully proven;
- explicit prepare/confirm for mutations;
- shared approval/fingerprint architecture;
- permission-preserving native Frappe/ERPNext document path;
- sales-profile registration only unless Task 56 proves another scope;
- no destructive unlink/delete in V1 unless audit evidence requires it.
```

Task 57 must **not** be written from assumptions in this task file.

Its exact contracts, tools, services, profile integration, and tests must come from:

```text
docs/inspect/CONTACT_MASTER_NATIVE_FLOW_AND_CAPABILITY_AUDIT.md
```

If Task 56 proves that Contact update/email-phone mutation is too broad for the same V1, Task 57 must implement creation/linking first and name a separate later task for Contact detail updates.

---

## 48. Final Instruction to the Coding Agent

Do not implement Contact capability yet.

First inspect the **current** `mcp_erpnext`, installed Frappe, installed ERPNext, effective DocType metadata, native Contact controller logic, Customer controller logic, Dynamic Link behavior, and existing MCP patterns.

Prefer framework-native behavior over custom logic.

Do not treat `customer_primary_contact` as a magical create-if-missing field.

Do not write directly to Customer `email_id` / `mobile_no` simply to make the UI appear updated.

Do not expose raw Dynamic Link editing to the LLM unless the audit proves it is unavoidable.

Do not create duplicate Contacts merely because a name does not resolve uniquely.

Produce the source-grounded audit report only, including the exact smallest Task 57 implementation recommendation.
