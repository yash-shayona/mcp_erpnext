"""Developer-changeable Item capability policy and input contract."""

from __future__ import annotations

SEARCH_FILTERS = {"disabled": ["!=", 1], "is_sales_item": 1}
SEARCH_FIELDS = ("name", "item_code", "item_name", "description")
DISPLAY_FIELDS = ("item_code", "item_name", "stock_uom", "description")

# These are the Item DocFields accepted by the controlled sales-item capability.
# Runtime metadata, not this tuple, determines which values are mandatory.
CREATION_FIELDS = (
    "item_code",
    "item_name",
    "item_group",
    "stock_uom",
    "is_stock_item",
    "is_sales_item",
)
# Link targets are always derived from runtime DocField metadata. Item Groups
# must remain leaf nodes for Item creation; this is a capability candidate rule.
REFERENCE_FILTERS = {
	"item_group": {"is_group": 0},
	"stock_uom": {},
}

# This capability creates Items intended for Selling workflows. It is deliberate
# MCP policy, distinct from an ERPNext metadata requirement or default.
POLICY_VALUES = {"is_sales_item": 1}
