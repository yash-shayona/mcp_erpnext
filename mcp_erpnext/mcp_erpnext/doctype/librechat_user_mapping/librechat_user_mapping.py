"""Validation for the one-to-one LibreChat-to-Frappe user mapping."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class LibreChatUserMapping(Document):
    """Keep mapping administration separate from Frappe roles and permissions."""

    def validate(self) -> None:
        self.librechat_user_id = (self.librechat_user_id or "").strip()
        self.frappe_user = (self.frappe_user or "").strip()

        if not self.librechat_user_id:
            frappe.throw(_("LibreChat User ID is required."))
        if not self.frappe_user:
            frappe.throw(_("Frappe User is required."))

        user = frappe.db.get_value(
            "User", self.frappe_user, ["name", "enabled"], as_dict=True
        )
        if not user:
            frappe.throw(_("The selected Frappe User does not exist."))
        if user.name in {"Guest", "guest"}:
            frappe.throw(_("Guest cannot be used as a mapped Frappe User."))
        if cint(self.enabled) and not cint(user.enabled):
            frappe.throw(_("A disabled Frappe User cannot be enabled for LibreChat."))

        self._reject_duplicate(
            "librechat_user_id", _("This LibreChat User ID is already mapped.")
        )
        self._reject_duplicate("frappe_user", _("This Frappe User is already mapped."))

    def _reject_duplicate(self, fieldname: str, message: str) -> None:
        if frappe.db.exists(
            "LibreChat User Mapping",
            {fieldname: self.get(fieldname), "name": ["!=", self.name]},
        ):
            frappe.throw(message)
