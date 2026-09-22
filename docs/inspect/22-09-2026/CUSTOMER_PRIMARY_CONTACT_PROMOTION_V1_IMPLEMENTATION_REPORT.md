# Customer Primary Contact Promotion V1 — Implementation Report

## Result

Task 63 is implemented as a Sales-only, approval-bound promotion of an
existing Contact that has exactly one Dynamic Link to the target Customer.
The public pair is:

- `prepare_customer_primary_contact`
- `confirm_customer_primary_contact`

The implementation does not create, link, update, unlink, clear, merge, or
delete Contacts.

## Implementation

`services/masters/customer_primary_contact.py` resolves and permission-checks
the Customer and selected Contact, computes an internal sorted Dynamic Link
fingerprint, validates Customer-primary coherence, and rejects shared selected
Contacts or unsafe shared old primaries. Approval payloads bind Customer state,
selected/old Contact state, and the Customer-linked primary-state fingerprint.

Confirmation rechecks all of that state and uses the shared
`ApprovalStore.claim_for_confirm_write()` with action
`customer_primary_contact`. The native mutation sequence is one transaction:

1. set the selected Contact primary and call normal `Contact.save`;
2. set `Customer.customer_primary_contact` and call normal `Customer.save`;
3. verify the native result and commit once; roll back on failure.

This preserves native Contact primary demotion and CRM Contact validation, and
lets Customer save refresh its `fetch_from` projections. Existing Task 57
create/link behavior is unchanged.

## Public and transport surface

Typed strict contracts, MCP wrappers, the Sales tool registry, REST dispatch,
and generated `docs/TOOLS.md` were updated. The pair is not registered in
Purchase or Accounts profiles.

## Runtime evidence

Read-only inspection on `praveg.localhost` confirmed:

- `Contact.is_primary_contact` is a Check and `Contact.links` is a Dynamic
  Link table;
- `Customer.customer_primary_contact` links to Contact;
- Customer `email_id`, `mobile_no`, `first_name`, and `last_name` use native
  `fetch_from` projections from `customer_primary_contact`;
- CRM overrides Contact with `crm.overrides.contact.CustomContact` and its
  Contact validate hook is `crm.api.contact.validate`.

No live business record was mutated.

## Verification

- 55 focused/regression tests passed, including Tasks 57, 60, and 61 suites,
  profile/registration, and REST dispatch.
- `scripts/generate_tool_catalog.py --check` passed.
- AST parsing and `git diff --check` passed.

The tests are source/unit and local runtime-metadata evidence; no authorized
live business-record promotion was performed.
