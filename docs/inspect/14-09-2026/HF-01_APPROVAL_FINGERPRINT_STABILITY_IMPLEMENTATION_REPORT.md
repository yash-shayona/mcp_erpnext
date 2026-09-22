# HF-01 — Approval Fingerprint Stability Implementation Report

## Confirmed defect

Sales Order `SAL-ORD-2026-00018` was submitted successfully, but two actual
REST-backed Sales Order to Delivery Note confirmations returned
`STALE_CONFIRMATION` (`MCP-ERR-C272D81E` and `MCP-ERR-0E65F0F1`). No Delivery
Note was created; a live Delivery Note query returned zero records.

The native mapper is called once during prepare and again during confirm. The
Delivery Note preview included the native `posting_time` field, which changes
between those calls. The full preview was hashed, so the confirmation treated
the regenerated runtime timestamp as business drift.

Evidence: `mcp_erpnext/services/selling/sales_order_to_delivery_note.py`
included `delivery_note.posting_time` in `_preview()` and compared a new
native mapping fingerprint during confirmation.

## Audit inventory

| Flow | Fingerprint boundary | Result |
| --- | --- | --- |
| Quotation -> Sales Order | source eligibility plus stable mapped Sales Order projection | Reused canonical hashing; material state retained |
| Sales Order -> Sales Invoice | stable source/target projection | Reused canonical hashing; no proven volatile field removed |
| Sales Order -> Delivery Note | mapped Delivery Note projection | Fixed proven transient `posting_time` path |
| Delivery Note -> Sales Invoice | stable source/target projection | Reused canonical hashing; no proven volatile field removed |
| Standalone Sales Invoice | request plus native calculated preview | Reused canonical hashing; no proven volatile field removed |
| Single-invoice Payment Entry | request plus native payment preview/account | Reused canonical hashing; no proven volatile field removed |
| Multi-invoice Customer Receipt | request, invoice sources, destination, preview | Reused canonical hashing; material invoice state retained |
| Generic lifecycle update/child-add/submit/cancel/delete | exact document modified/docstatus and action-specific checks | No fingerprint rewrite; native lifecycle checks retained |
| Customer, Item, Quotation, Sales Order, Purchase Order creates | approval-bound prepared payloads | No false-stale fingerprint path identified |
| Direct and REST | shared service boundary | Same service implementation; live REST reload remains required |

## Code changes

- `mcp_erpnext/services/common/fingerprint.py` adds canonical hashing.
- `mcp_erpnext/services/selling/sales_order_to_delivery_note.py` ignores only
  `("delivery_note", "posting_time")` for this conversion fingerprint.
- Existing fingerprinted flows use the shared helper for consistent encoding.
- No approval policy, permission, native mapper, or public MCP contract was
  changed.

## Verification

Focused unit tests passed:

```text
46 tests, OK
```

Coverage includes canonicalization, material-field and row-order sensitivity,
fresh native child object identity for Quotation conversion, and changing
native Delivery Note posting time between prepare and confirm.

Live MCP confirmation after worker reload is still required. The earlier live
confirmation was intentionally not retried after the stale failure, and no
Delivery Note write was performed by this implementation turn.

## Remaining risks

- A live target worker must reload the updated service before the fix can be
  observed through REST.
- Other flows retain their existing projections by design; future volatility
  must be proven at the exact field/path before exclusion.
- Full-suite verification was not run in this turn.
