"""Compatibility imports for the pre-platform Sales Order service path.

New capability code belongs in ``services.selling.sales_order``. Keeping this
thin module avoids breaking local callers while the public MCP tool surface is
unchanged.
"""

from .masters.customer import search_customers
from .masters.item import search_items
from .selling.sales_order import confirm_sales_order, prepare_sales_order

__all__ = ["confirm_sales_order", "prepare_sales_order", "search_customers", "search_items"]
