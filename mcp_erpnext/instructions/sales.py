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
`tc_name` and let the server apply the Company default (or no Terms).
"""
