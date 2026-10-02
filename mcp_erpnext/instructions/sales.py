"""Sales-only MCP authoring guidance."""

SALES_INSTRUCTIONS = """\
For `prepare_quotation`, only the Customer and item rows are required from the
user. If `valid_till` is not supplied, omit it from the tool call so the server
applies its configured validity policy from the transaction date; show the
resulting date in the preview, but do not ask the user to select a date or a
default period.

When the user explicitly names or describes a Terms and Conditions template
but its canonical ERPNext name is not already known, call
`resolve_terms_and_conditions`. Use the resolved `reference.name` as `tc_name`
for Quotation, Sales Order, or Sales Invoice preparation. For `ambiguous`, get
one user selection and revalidate it with `select_resolved_candidate` before
using its canonical name. Never infer a Terms template from document type alone.
When the user did not request a Terms template, do not call the resolver: omit
`tc_name` and let the server apply its configured document default, then the
Company default (or no Terms).

For Draft Sales Invoices, use `prepare_document_update` only for the bounded parent fields or an existing item row's `qty`, `rate`, or `description`. Add an Item to a Draft Quotation, Sales Order, or Sales Invoice through `prepare_document_child_add`; remove one exact Draft item row through `prepare_document_child_remove`. All require the paired confirmation approval. Submitted and Cancelled sales transactions cannot be authored this way.

When the user explicitly names or describes a Payment Terms Template but its
canonical ERPNext name is not already known, call
`resolve_payment_terms_template`. Pass the resolved `reference.name` as
`payment_terms_template`. For `ambiguous`, use `select_resolved_candidate` in
the same way as Terms and Conditions. When the user did not request a Payment
Terms Template, omit the field and let the server apply its configured document
default or ERPNext's native Customer -> Customer Group -> Company fallback.
"""
