"""Bounded guidance for the Purchase profile."""

PURCHASE_INSTRUCTIONS = """\\
Use `search_suppliers` or `resolve_supplier` to turn a user-described Supplier
into a canonical reference before authoring. Use `get_supplier`,
`query_suppliers`, and `aggregate_suppliers` for bounded, permission-aware
Supplier inspection; they do not create or update Suppliers.

Purchase Item search, resolution, get, query, and aggregate tools expose only
active purchase-enabled Items. Resolve the Supplier and each Item before calling
`prepare_purchase_order`. The Purchase Order flow is prepare -> explicit
approval -> `confirm_purchase_order`; naming series and omitted defaults remain
native ERPNext/server-owned. If preparation returns `needs_input`, collect only
the reported missing values and prepare again; never invent a default.

Use the typed Purchase Order get/query/aggregate/item-history tools for existing
orders. `prepare_document_update` is limited to Draft Purchase Order fields
`schedule_date`, `supplier_address`, `contact_person`, `shipping_address`,
`project`, and `cost_center`, plus dedicated `tc_name` and
`payment_terms_template` handling; use the paired confirm only after reviewing and
approving its preview. Add an eligible Item with `prepare_document_child_add`,
and remove one exact `Purchase Order Item` row with
`prepare_document_child_remove`; both require the paired explicit approval and
confirm. ERPNext owns Buying defaults, recalculation, validation, and linked
lifecycle behavior. Existing submit/cancel/delete, PDF rendering, and email
tools remain available within their published contracts. Purchase Receipt creation is available only through native submitted Purchase Order to Draft Purchase Receipt preparation and explicit approval. Use `get_purchase_receipt` for exact reads, `query_purchase_receipts` for filtered headers, `aggregate_purchase_receipts` for currency-aware summaries, and `query_purchase_receipt_items` for item history and PO lineage. Never submit a Purchase Receipt. Purchase Invoice, Supplier Payment, Material Request, and Supplier Quotation remain unavailable.

Terms and Conditions are commercial text; Payment Terms Template defines the
native payment schedule. When the user requests a template, use
`resolve_buying_terms_and_conditions` or `resolve_payment_terms_template` and
pass the selected `reference.name` as `tc_name` or `payment_terms_template` to
`prepare_purchase_order`. For ambiguity, ask for one candidate, then resolve
its exact name again. Never guess a template. Do not call a resolver merely
because an optional template was omitted.

Explicit choices override company/site `mcp_business_defaults` for Purchase
Order; absent configuration retains native Company Buying Terms and
Supplier/Supplier Group/Company payment defaults. No template is required by
MCP. Missing or inaccessible configured templates return `needs_input`; obtain
an explicit permitted selection or ask the operator to correct configuration.

On a Draft PO, use `prepare_document_update` with `tc_name` and/or
`payment_terms_template` set to an exact permitted name, or null to clear.
Review the resulting rendered terms and payment schedule before approval.
ERPNext generates the replacement schedule; clearing the payment template
creates its native no-template schedule, not arbitrary editable schedule rows.
Do not supply raw Terms text or Payment Schedule rows. Template changes after
preview require preparing again. PDF/email shows transaction terms only if the
active print format includes them.
"""
