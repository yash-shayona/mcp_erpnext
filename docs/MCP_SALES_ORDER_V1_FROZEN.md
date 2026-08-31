# MCP ERPNext Sales Order V1 — Frozen Scope

Status: implementation baseline

> Historical scope notice: this document describes the original Sales Order V1
> baseline. The current ERPNext MCP Server has since expanded with additional
> reusable Master and Selling capabilities. Refer to
> [`ERPNext_MCP_ARCHITECTURE.md`](ERPNext_MCP_ARCHITECTURE.md) for the current
> architecture and tool catalog.

This document freezes the first workflow for `mcp_erpnext`. Changes to this
scope require an explicit V1 amendment or a new version; they must not be
introduced silently through prompt changes.

## Objective

Allow a trusted, authenticated Frappe service user to request an ERPNext Sales
Order in natural language. The workflow resolves the customer and items, asks
for missing or ambiguous information, shows a final preview, and creates a
**Draft** Sales Order only after explicit confirmation.

## V1 user inputs

The user may provide:

- Customer name or customer identifier.
- One or more item names or item codes.
- Quantity for each item when known.
- Optional delivery date.
- Optional company only when the authenticated user's default company is not
  the intended company.

The server must ask for a quantity when an item quantity is missing. It must
not invent a quantity.

## V1 defaults

- Order type: `Sales`.
- Transaction date: current site date.
- Delivery date: current site date when the user does not provide one.
- Company: authenticated user's Frappe default company.
- Price list, currency, UOM, conversion factor, rate, taxes, and other
  commercial values: ERPNext's standard missing-value and pricing logic.
- `skip_delivery_note`: false.

If the company or price list cannot be resolved safely, the workflow asks the
user instead of choosing an arbitrary value.

## Resolution rules

1. Search only records visible to the configured Frappe service user.
2. Ignore disabled customers and items.
3. Exact identifier/name matches may be selected automatically.
4. A single strong spelling correction may be selected and reported as a
   correction.
5. Multiple plausible matches must be returned to the user for selection.
6. No document may be created while customer or item resolution is ambiguous.

The final document uses the exact Customer and Item document names returned by
Frappe, never the raw natural-language text.

## Approval boundary

The workflow has two operations:

```text
prepare_sales_order -> preview + short-lived approval token
confirm_sales_order  -> insert Draft Sales Order
```

Preparation is read-only. Confirmation requires an explicit `confirm=true`,
binds the token to the current site and Frappe user, and is idempotent for the
token lifetime. V1 does not submit, cancel, amend, or update Sales Orders.

## ERPNext persistence boundary

Creation must use `frappe.get_doc(...).insert()` with normal permissions and
links. It must call the standard Sales Order `set_missing_values()` before
insertion and must not use direct SQL or `ignore_permissions=True`.

## V1 tools

- `search_customers(query)`
- `search_items(query)`
- `prepare_sales_order(customer, items, company=None, delivery_date=None,
  selling_price_list=None)`
- `confirm_sales_order(approval_token, confirm)`

## Backend phases

V1 runs as a local stdio MCP process and connects directly to the selected
Frappe site through its ORM. This preserves ERPNext's normal permission,
pricing, missing-value, and document-validation lifecycle.

The planned next phase keeps the same MCP tool contract but replaces the
backend with HTTPS calls to an ERPNext site using `ERPNEXT_BASE_URL`,
`ERPNEXT_API_KEY`, and `ERPNEXT_API_SECRET` from the process environment. The
REST client must use a server-side method or endpoint that preserves the same
Sales Order lifecycle; generic resource CRUD alone must not silently bypass
`set_missing_values`, permissions, or the approval boundary. The REST backend
is not enabled in V1.

## Out of scope for V1

- Submitting or cancelling Sales Orders.
- Delivery schedules other than one document-level delivery date.
- Customer or Item creation.
- Arbitrary ERPNext document access.
- Arbitrary SQL.
- Automatic payment, stock reservation, or delivery-note creation.
- Multi-worker persistent approval storage.

The in-memory approval store is intentional for the local stdio MVP. A future
remote or multi-worker deployment must replace it with a persistent, expiring
server-side store before enabling that deployment mode.

## Acceptance criteria

- A unique customer and item with a supplied positive quantity produces a
  preview without writing a Sales Order.
- Ambiguous customer or item input produces candidates and no write.
- Missing quantity produces a question and no write.
- A confirmed request creates one Draft Sales Order with exact resolved links.
- A repeated confirmation for the same token returns the existing Sales Order
  instead of creating a duplicate.
- Frappe permission and standard Sales Order validation failures stop creation.
- A missing ERPNext permission returns the stable safe error envelope
  (`status=error`, machine-readable `code`, human-friendly `message`, and
  correlation `reference`); framework permission details and tracebacks are
  logged server-side and are never surfaced to the caller.
