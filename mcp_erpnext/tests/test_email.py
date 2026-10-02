from __future__ import annotations

import os
import unittest
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe

from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.services.common import email
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import (
    FakeSharedApprovalBackend,
    read_record,
)


class FakeDocument:
    def __init__(
        self,
        *,
        doctype="Sales Order",
        name="SO-001",
        contact_email="customer@example.com",
        permissions=None,
    ):
        self.doctype = doctype
        self.name = name
        self.modified = "2026-09-09 10:00:00"
        self.docstatus = 0
        self.values = {
            "customer": "CUST-001",
            "contact_email": contact_email,
            "contact_display": "Primary Contact",
            "contact_person": "CONTACT-001",
            "quotation_to": "Customer",
            "party_name": "CUST-001",
            "supplier": "SUP-001",
        }
        self.permissions = permissions or {
            permission: True for permission in ("read", "email", "print")
        }

    def get(self, fieldname, default=None):
        return self.values.get(fieldname, default)

    def has_permission(self, permission):
        return self.permissions.get(permission, False)


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.email_mode = patch.dict(
            os.environ, {"MCP_EMAIL_MODE": "approval_required"}
        )
        self.email_mode.start()
        self.doc = FakeDocument()
        self.store = ApprovalStore(
            ApprovalMode.AGENT_DELEGATED, backend=FakeSharedApprovalBackend()
        )
        self.get_doc = patch.object(email.frappe, "get_doc", return_value=self.doc)
        self.get_doc.start()
        self.runtime = [
            patch.object(
                email.frappe, "session", SimpleNamespace(user="user@example.com")
            ),
            patch.object(email.frappe, "local", SimpleNamespace(site="test.localhost")),
            patch.object(email, "approvals", self.store),
            patch.object(email, "_check_email_account", return_value=None),
            patch.object(
                email.pdf_service,
                "render_document_pdf",
                return_value={
                    "status": "ok",
                    "doctype": "Sales Order",
                    "name": "SO-001",
                    "print_format_used": "Standard",
                    "filename": "SO-001.pdf",
                    "mime_type": "application/pdf",
                    "_pdf": b"approved-pdf",
                },
            ),
        ]
        for item in self.runtime:
            item.start()

    def tearDown(self):
        for item in reversed(self.runtime):
            item.stop()
        self.get_doc.stop()
        self.email_mode.stop()

    def test_prepare_resolves_native_contact_and_does_not_send(self):
        sendmail = Mock()
        with patch.object(email.frappe, "sendmail", sendmail):
            result = email.prepare_document_email("Sales Order", "SO-001", "sales")

        self.assertEqual(result["status"], "ready_for_approval")
        self.assertEqual(result["preview"]["recipient"], "customer@example.com")
        self.assertEqual(
            result["preview"]["message"], "Please find attached Sales Order SO-001."
        )
        self.assertEqual(result["preview"]["attachment_filename"], "SO-001.pdf")
        sendmail.assert_not_called()
        approval = read_record(self.store, result["approval_token"])
        self.assertEqual(
            approval.payload["attachment_sha256"], sha256(b"approved-pdf").hexdigest()
        )

    def test_disabled_email_never_plans_claims_or_queues(self):
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "disabled"}),
            patch.object(email.approvals, "create") as create,
            patch.object(email.approvals, "claim_for_confirm_write") as claim,
            patch.object(email.frappe, "sendmail") as sendmail,
        ):
            prepared = email.prepare_document_email("Sales Order", "SO-001", "sales")
            executed = email.execute_document_email("Sales Order", "SO-001", "sales")
            confirmed = email.confirm_document_email("unused", "sales")
        self.assertEqual(
            [prepared["code"], executed["code"], confirmed["code"]],
            ["EMAIL_DISABLED"] * 3,
        )
        create.assert_not_called()
        claim.assert_not_called()
        sendmail.assert_not_called()

    def test_direct_email_prepare_is_preview_only_and_execute_is_store_inert(self):
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}),
            patch.object(email.approvals, "create") as create,
            patch.object(email.approvals, "claim_for_confirm_write") as claim,
            patch.object(
                email.frappe, "sendmail", return_value=SimpleNamespace(name="QUEUE-1")
            ) as sendmail,
            patch.object(
                email.frappe, "db", SimpleNamespace(commit=Mock(), rollback=Mock())
            ),
        ):
            preview = email.prepare_document_email("Sales Order", "SO-001", "sales")
            rejected = email.confirm_document_email("unused", "sales")
            queued = email.execute_document_email("Sales Order", "SO-001", "sales")
        self.assertEqual(preview["status"], "preview")
        self.assertNotIn("approval_token", preview)
        self.assertEqual(rejected["code"], "DIRECT_EXECUTION_REQUIRED")
        self.assertEqual(queued["status"], "queued")
        create.assert_not_called()
        claim.assert_not_called()
        sendmail.assert_called_once()

    def test_wrong_mode_confirm_preserves_generic_approval_for_later_confirmation(self):
        prepared = email.prepare_document_email("Sales Order", "SO-001", "sales")
        token = prepared["approval_token"]

        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}),
            patch.object(email.frappe, "sendmail") as sendmail,
        ):
            rejected = email.confirm_document_email(token, "sales")
        self.assertEqual(rejected["code"], "DIRECT_EXECUTION_REQUIRED")
        self.assertIsNone(read_record(self.store, token).consumed_at)
        sendmail.assert_not_called()

        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "approval_required"}),
            patch.object(
                email.frappe,
                "sendmail",
                return_value=SimpleNamespace(name="EMAIL-QUEUE-RETRIED"),
            ) as sendmail,
            patch.object(
                email.frappe, "db", SimpleNamespace(commit=Mock(), rollback=Mock())
            ),
        ):
            confirmed = email.confirm_document_email(token, "sales")
        self.assertEqual(confirmed["status"], "queued")
        sendmail.assert_called_once()

    def test_final_email_mode_change_blocks_generic_direct_and_approval_enqueue(self):
        first_render = {
            "status": "ok",
            "doctype": "Sales Order",
            "name": "SO-001",
            "print_format_used": "Standard",
            "filename": "SO-001.pdf",
            "mime_type": "application/pdf",
            "_pdf": b"approved-pdf",
        }
        with self.subTest(mode="direct"):
            renders = [first_render]

            def flip_to_disabled(*_args):
                if renders:
                    return renders.pop()
                os.environ["MCP_EMAIL_MODE"] = "disabled"
                return first_render

            with (
                patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}),
                patch.object(
                    email.pdf_service,
                    "render_document_pdf",
                    side_effect=flip_to_disabled,
                ),
                patch.object(email.frappe, "sendmail") as sendmail,
                patch.object(
                    email.frappe, "db", SimpleNamespace(commit=Mock(), rollback=Mock())
                ) as db,
            ):
                result = email.execute_document_email("Sales Order", "SO-001", "sales")
            self.assertEqual(result["code"], "EMAIL_DISABLED")
            sendmail.assert_not_called()
            db.commit.assert_not_called()

        with self.subTest(mode="approval_required"):
            prepared = email.prepare_document_email("Sales Order", "SO-001", "sales")
            def flip_approval_mode(*_args):
                os.environ["MCP_EMAIL_MODE"] = "direct"
                return first_render

            with (
                patch.dict(os.environ, {"MCP_EMAIL_MODE": "approval_required"}),
                patch.object(
                    email.pdf_service,
                    "render_document_pdf",
                    side_effect=flip_approval_mode,
                ),
                patch.object(email.frappe, "sendmail") as sendmail,
                patch.object(
                    email.frappe, "db", SimpleNamespace(commit=Mock(), rollback=Mock())
                ) as db,
            ):
                result = email.confirm_document_email(
                    prepared["approval_token"], "sales"
                )
            self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
            sendmail.assert_not_called()
            db.commit.assert_not_called()

    def test_document_email_approval_is_independent_of_create_mode(self):
        for mode in ("disabled", "direct"):
            with (
                self.subTest(mode=mode),
                patch.dict(os.environ, {"MCP_CREATE_MODE": mode}),
            ):
                prepared = email.prepare_document_email(
                    "Sales Order", "SO-001", "sales"
                )
                self.assertEqual(prepared["status"], "ready_for_approval")
                self.assertIn("approval_token", prepared)

    def test_confirm_queues_exact_attachment_and_replay_does_not_resend(self):
        prepared = email.prepare_document_email(
            "Sales Order",
            "SO-001",
            "sales",
            subject="Approved subject",
            message="Approved body",
        )
        sendmail = Mock(return_value=SimpleNamespace(name="EMAIL-QUEUE-001"))
        commit = Mock()
        rollback = Mock()
        with (
            patch.object(email.frappe, "sendmail", sendmail),
            patch.object(
                email.frappe, "db", SimpleNamespace(commit=commit, rollback=rollback)
            ),
        ):
            result = email.confirm_document_email(prepared["approval_token"], "sales")
            replay = email.confirm_document_email(prepared["approval_token"], "sales")

        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["queue_reference"], "EMAIL-QUEUE-001")
        self.assertEqual(replay["code"], "CONFIRMATION_CONSUMED")
        sendmail.assert_called_once()
        kwargs = sendmail.call_args.kwargs
        self.assertEqual(kwargs["recipients"], ["customer@example.com"])
        self.assertEqual(kwargs["subject"], "Approved subject")
        self.assertEqual(kwargs["message"], "Approved body")
        self.assertEqual(kwargs["attachments"][0]["fname"], "SO-001.pdf")
        self.assertEqual(kwargs["attachments"][0]["fcontent"], b"approved-pdf")
        self.assertEqual(kwargs["attachments"][0]["content_type"], "application/pdf")
        commit.assert_called_once()

    def test_confirm_requires_trusted_approval_in_default_policy(self):
        store = ApprovalStore(
            ApprovalMode.TRUSTED_HUMAN, backend=FakeSharedApprovalBackend()
        )
        with patch.object(email, "approvals", store):
            token = store.create(
                action=email.EMAIL_ACTION,
                site="test.localhost",
                user="user@example.com",
                payload={},
            )
            result = email.confirm_document_email(token, "sales")

        self.assertEqual(result["code"], "TRUSTED_APPROVAL_UNAVAILABLE")

    def test_self_scope_uses_only_the_authenticated_user_email_and_revalidates(self):
        with patch.object(
            email.frappe,
            "db",
            SimpleNamespace(get_value=lambda *args: "user@example.com"),
        ):
            prepared = email.prepare_document_email(
                "Sales Order", "SO-001", "sales", recipient_scope="self"
            )
            self.assertEqual(prepared["preview"]["recipient"], "user@example.com")
            self.assertEqual(prepared["preview"]["recipient_scope"], "self")
            self.assertEqual(
                email.prepare_document_email(
                    "Sales Order",
                    "SO-001",
                    "sales",
                    "other@example.com",
                    recipient_scope="self",
                )["code"],
                "INVALID_RECIPIENT",
            )

    def test_confirm_rejects_changed_pdf_without_sending(self):
        prepared = email.prepare_document_email("Sales Order", "SO-001", "sales")
        with (
            patch.object(
                email.pdf_service,
                "render_document_pdf",
                return_value={
                    "status": "ok",
                    "doctype": "Sales Order",
                    "name": "SO-001",
                    "print_format_used": "Standard",
                    "filename": "SO-001.pdf",
                    "mime_type": "application/pdf",
                    "_pdf": b"changed-pdf",
                },
            ),
            patch.object(email.frappe, "sendmail") as sendmail,
            patch.object(
                email.frappe, "db", SimpleNamespace(commit=Mock(), rollback=Mock())
            ),
        ):
            result = email.confirm_document_email(prepared["approval_token"], "sales")

        self.assertEqual(result["code"], "PREPARED_STATE_CHANGED")
        sendmail.assert_not_called()

    def test_confirm_rejects_recipient_no_longer_associated(self):
        prepared = email.prepare_document_email("Sales Order", "SO-001", "sales")
        self.doc.values["contact_email"] = "changed@example.com"
        with patch.object(email.frappe, "sendmail") as sendmail:
            result = email.confirm_document_email(prepared["approval_token"], "sales")

        self.assertEqual(result["code"], "PREPARED_STATE_CHANGED")
        sendmail.assert_not_called()

    def test_missing_and_ambiguous_recipients_are_safe(self):
        self.doc.values["contact_email"] = None
        with (
            patch.object(email, "_party_email", return_value=None),
            patch.object(
                email,
                "_contact_candidates",
                return_value=[
                    {"email": "one@example.com", "label": "One"},
                    {"email": "two@example.com", "label": "Two"},
                ],
            ),
        ):
            result = email.prepare_document_email("Sales Order", "SO-001", "sales")

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(
            [candidate["email"] for candidate in result["candidates"]],
            ["one@example.com", "two@example.com"],
        )
        self.assertTrue(result["interaction"]["required"])

    def test_explicit_unrelated_recipient_is_rejected(self):
        result = email.prepare_document_email(
            "Sales Order", "SO-001", "sales", recipient_email="attacker@example.com"
        )
        self.assertEqual(result["code"], "INVALID_RECIPIENT")

    def test_same_service_resolves_quotation_and_purchase_order(self):
        for doctype, profile in (
            ("Quotation", "sales"),
            ("Purchase Order", "purchase"),
        ):
            with self.subTest(doctype=doctype):
                self.doc.doctype = doctype
                result = email.prepare_document_email(doctype, "DOC-001", profile)
                self.assertEqual(result["status"], "ready_for_approval")
                self.assertEqual(result["preview"]["doctype"], doctype)
            self.doc.doctype = "Sales Order"

    def test_sales_invoice_resolves_customer_party(self):
        self.doc.doctype = "Sales Invoice"
        result = email.prepare_document_email("Sales Invoice", "SINV-001", "sales")
        self.assertEqual(result["status"], "ready_for_approval")
        self.assertEqual(result["preview"]["doctype"], "Sales Invoice")
        self.assertEqual(result["preview"]["recipient"], "customer@example.com")

    def test_purchase_profile_rejects_sales_invoice_email(self):
        result = email.prepare_document_email("Sales Invoice", "SINV-001", "purchase")
        self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")

    def test_missing_or_invalid_recipient_is_rejected(self):
        self.doc.values["contact_email"] = None
        with (
            patch.object(email, "_party_email", return_value=None),
            patch.object(email, "_contact_candidates", return_value=[]),
        ):
            missing = email.prepare_document_email("Sales Order", "SO-001", "sales")
            invalid = email.prepare_document_email(
                "Sales Order", "SO-001", "sales", recipient_email="not-an-email"
            )
        self.assertEqual(missing["code"], "RECIPIENT_NOT_FOUND")
        self.assertEqual(invalid["code"], "INVALID_EMAIL")

    def test_permissions_and_profile_boundary_fail_before_pdf(self):
        for permission in ("read", "email", "print"):
            with self.subTest(permission=permission):
                self.doc.permissions[permission] = False
                result = email.prepare_document_email("Sales Order", "SO-001", "sales")
                self.assertEqual(result["code"], "PERMISSION_DENIED")
                self.doc.permissions[permission] = True

        with patch.object(email.frappe, "get_doc") as get_doc:
            result = email.prepare_document_email("Purchase Order", "PO-001", "sales")
        self.assertEqual(result["code"], "DOCTYPE_NOT_ALLOWED")
        get_doc.assert_not_called()

    def test_pdf_service_is_called_directly_with_render_inputs(self):
        with patch.object(
            email.pdf_service,
            "render_document_pdf",
            wraps=email.pdf_service.render_document_pdf,
        ) as render:
            # The service is already patched in setUp; this assertion only verifies
            # the email layer calls the shared service rather than a public tool.
            result = email.prepare_document_email(
                "Sales Order",
                "SO-001",
                "sales",
                print_format="Standard",
                letterhead="Letter Head",
                language="en",
            )

        self.assertEqual(result["status"], "ready_for_approval")
        render.assert_called_once_with(
            "Sales Order", "SO-001", "sales", "Standard", "Letter Head", "en"
        )

    def test_all_profile_supports_the_existing_sales_purchase_email_union(self):
        for doctype in ("Sales Order", "Purchase Order"):
            with self.subTest(doctype=doctype):
                self.doc.doctype = doctype
                self.assertEqual(
                    email.prepare_document_email(doctype, "DOC-001", "all")["status"],
                    "ready_for_approval",
                )
        self.assertEqual(
            email.prepare_document_email("Customer", "CUST-001", "all")["code"],
            "DOCTYPE_NOT_ALLOWED",
        )


if __name__ == "__main__":
    unittest.main()
