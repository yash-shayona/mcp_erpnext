# HF-01 — Approval Fingerprint Stability Audit and Fix

## Objective

Audit approval-bound prepare/confirm flows for false `STALE_CONFIRMATION`
responses caused by non-material native runtime state, while preserving stale
detection for real business changes.

## Scope

Inspect the current source, native mapper output, approval payload, and tests
for Customer, Item, Quotation, Sales Order, Purchase Order, Sales Invoice,
Delivery Note, Payment Entry, and the Quotation/Sales Order/Delivery Note
conversion flows. Include direct and REST execution boundaries.

The audit is broader than the implementation. Only fields proven to be
transient or display-only may be excluded or normalized. Material header,
child-row, accounting, stock, tax, party, and source-eligibility state must
remain fingerprinted.

## Classification rules

1. Material business state remains in the fingerprint.
2. Stable native-derived business state remains in the fingerprint.
3. Proven runtime-generated state may be excluded at its exact projection path.
4. Display-only state may remain in the user preview without affecting the
   fingerprint.
5. Collection order is preserved unless the native business semantics prove it
   is non-material.

## Implemented changes

- Added the shared `stable_fingerprint()` helper for ordered collection
  preservation, mapping-key canonicalization, and date/decimal normalization.
- Excluded only `Delivery Note.posting_time` from the Sales Order to Delivery
  Note conversion fingerprint. ERPNext regenerates this timestamp when the
  native mapper is called again during confirmation.
- Kept Delivery Note posting date, items, quantities, rates, warehouse,
  source-row lineage, totals, and source Sales Order state fingerprinted.
- Reused the helper across the existing fingerprinted Sales, conversion, and
  payment flows without changing their business projections.

## Required verification

- A changed Delivery Note posting time does not cause a false stale result.
- A changed material amount, item, quantity, source, payment reference, or
  accounting state still causes a stale result in the relevant flow.
- Approval token, action, user, site, payload binding, and final permission
  checks remain unchanged.
- Direct and REST paths use the same service and fingerprint behavior.
- Live verification must be run only after the target MCP/ERPNext workers load
  the updated source.

## Out of scope

- Removing fields solely because they are timestamps.
- Sorting child rows without proof that order is non-material.
- Changing ApprovalStore policy or public approval arguments.
- Broad refactoring of native ERPNext calculations or mappers.
