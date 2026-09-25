"""Sales-only MCP authoring guidance."""

SALES_INSTRUCTIONS = """\
For `prepare_quotation`, only the Customer and item rows are required from the
user. If `valid_till` is not supplied, omit it from the tool call so the server
applies its configured validity policy from the transaction date; show the
resulting date in the preview, but do not ask the user to select a date or a
default period.

For Sales document Terms, pass `tc_name` only when the user explicitly chose
or specified that exact Terms and Conditions template. Otherwise omit it and
let the server apply the Company default (or no Terms). Never guess a Terms
template from names or document type.
"""
