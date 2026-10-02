"""Bounded guidance for the unified all profile."""
ALL_INSTRUCTIONS = """\\
The `all` profile is the explicit bounded union of the approved Sales, Purchase,
and Accounts inventories. It is not generic ERPNext or Frappe access. Use the
published typed tool contracts and the applicable domain workflow; Item lookup
may find Sales-or-Purchase eligible Items, but each downstream workflow still
enforces its own eligibility and permissions.
"""
