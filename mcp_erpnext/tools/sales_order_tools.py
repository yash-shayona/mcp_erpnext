"""Compatibility import for the former flat Sales Order-tool path."""

from .selling.sales_order import register_sales_order_tools

__all__ = ["register_sales_order_tools"]
