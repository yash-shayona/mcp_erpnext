"""Developer-changeable Customer capability policy and input contract."""

from __future__ import annotations

SEARCH_FILTERS = {"disabled": ["!=", 1]}
SEARCH_FIELDS = ("name", "customer_name")
DISPLAY_FIELDS = ("customer_name", "customer_group", "territory")

# These are the Customer DocFields that this narrow MCP capability may accept.
# Runtime metadata, not this tuple, decides which of them are mandatory.
CREATION_FIELDS = (
    "customer_name",
    "customer_type",
    "customer_group",
    "territory",
    "tax_id",
    "gstin",
)

# Contact and address data remain intentionally narrow nested input mappings.
CONTACT_FIELD_MAP = {
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email_id",
    "mobile": "mobile_no",
}
ADDRESS_FIELDS = (
    "address_line1",
    "address_line2",
    "city",
    "state",
    "pincode",
    "country",
)

# Customer creation has no MCP-forced field values. Runtime DocField defaults
# (for example Customer Type on the installed site) remain authoritative.
POLICY_VALUES: dict[str, object] = {}

# Link targets are always derived from runtime DocField metadata. These filters
# only narrow permitted candidates for fields this capability already exposes.
REFERENCE_FILTERS = {
	"customer_group": {},
	"territory": {},
}
