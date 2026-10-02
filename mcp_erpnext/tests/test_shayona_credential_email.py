from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mcp_erpnext.approvals import ApprovalStore
from mcp_erpnext.contracts.shayona.credential_email import (
    CredentialEmailConfirmInput,
    CredentialEmailPrepareInput,
)
from mcp_erpnext.services.shayona import credential_email
from mcp_erpnext.services.shayona.config import load_business_defaults
from mcp_erpnext.settings import ApprovalMode
from mcp_erpnext.tests.approval_test_backend import (
    FakeSharedApprovalBackend,
    read_record,
)


class ShayonaCredentialEmailTests(unittest.TestCase):
    def setUp(self):
        self.email_mode = patch.dict(
            os.environ, {"MCP_EMAIL_MODE": "approval_required"}
        )
        self.email_mode.start()

    def tearDown(self):
        self.email_mode.stop()

    def test_disabled_email_blocks_all_credential_entry_paths_without_store_access(
        self,
    ):
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "disabled"}),
            patch.object(credential_email.approvals, "create") as create,
            patch.object(
                credential_email.approvals, "claim_for_confirm_write"
            ) as claim,
            patch.object(credential_email, "_plan") as plan,
            patch.object(credential_email.frappe, "sendmail") as sendmail,
        ):
            prepared = credential_email.prepare_customer_service_credential_email()
            executed = credential_email.execute_customer_service_credential_email()
            confirmed = credential_email.confirm_customer_service_credential_email(
                "unused"
            )
        self.assertEqual(
            [prepared["code"], executed["code"], confirmed["code"]],
            ["EMAIL_DISABLED"] * 3,
        )
        plan.assert_not_called()
        create.assert_not_called()
        claim.assert_not_called()
        sendmail.assert_not_called()

    def test_direct_credential_prepare_is_redacted_preview_without_approval(self):
        doc, password = self._credential_doc()
        with patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}):
            result, create, _outgoing = self._prepare_with_dependencies(doc=doc)
        self.assertEqual(result["status"], "preview")
        self.assertNotIn("approval_token", result)
        self.assertNotIn("username", str(result["preview"]).lower())
        self.assertNotIn("password", str(result["preview"]).lower())
        create.assert_not_called()
        password.assert_not_called()

    def test_direct_credential_execute_is_store_inert_under_trusted_human_policy(self):
        store = ApprovalStore(
            ApprovalMode.TRUSTED_HUMAN, backend=FakeSharedApprovalBackend()
        )
        payload = self._prepared_payload(self._template())
        doc = SimpleNamespace(
            get=lambda field: "user" if field == "username" else None,
            get_password=lambda _field: "pass",
        )
        snapshot = {
            "credential_name": "CSC-1",
            "customer": "Customer 1",
            "domain_name": "example.com",
            "credential_type": "cPanel",
            "account_name": "Main",
            "account_identity": "main",
            "control_panel_url": "https://panel.example.com",
        }
        template = self._template()
        template.get_formatted_email = lambda _context: {
            "subject": "Access CSC-1",
            "message": "body",
        }
        db = SimpleNamespace(commit=Mock(), rollback=Mock())
        with (
            patch.dict(
                os.environ,
                {
                    "MCP_EMAIL_MODE": "direct",
                    "MCP_APPROVAL_MODE": "trusted_human",
                },
            ),
            patch.object(credential_email, "approvals", store),
            patch.object(store, "create") as create,
            patch.object(store, "claim_for_confirm_write") as claim,
            patch.object(credential_email, "_plan", return_value=(payload, {})),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(doc, snapshot, template, "operator@example.com"),
            ),
            patch.object(credential_email.frappe, "db", db),
            patch.object(
                credential_email.frappe,
                "sendmail",
                return_value=SimpleNamespace(
                    name="EMAIL-QUEUE-1",
                    to=["recipient@example.com"],
                    cc=["customer@example.com", "operator@example.com"],
                ),
            ) as sendmail,
        ):
            result = credential_email.execute_customer_service_credential_email(
                credential_name="CSC-1", recipient_email="recipient@example.com"
            )

        self.assertEqual(result["status"], "queued")
        create.assert_not_called()
        claim.assert_not_called()
        sendmail.assert_called_once()
        self.assertTrue(sendmail.call_args.kwargs["redact_message_after_send"])

    def test_wrong_credential_confirm_mode_is_checked_before_claim(self):
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}),
            patch.object(
                credential_email.approvals, "claim_for_confirm_write"
            ) as claim,
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        claim.assert_not_called()

    def test_wrong_mode_confirm_preserves_credential_approval_for_later_confirmation(
        self,
    ):
        site = "shayona.localhost"
        user = "operator@example.com"
        store = ApprovalStore(
            ApprovalMode.AGENT_DELEGATED, backend=FakeSharedApprovalBackend()
        )
        payload = self._prepared_payload(self._template())
        token = store.create(
            action=credential_email.CREDENTIAL_EMAIL_ACTION,
            site=site,
            user=user,
            payload=payload,
        )
        credential_values = {
            "name": "CSC-1",
            "modified": "m1",
            "customer": "Customer 1",
            "domain_name": "example.com",
            "credential_type": "cPanel",
            "account_name": "Main",
            "account_identity": "main",
            "control_panel_url": "https://panel.example.com",
            "is_active": 1,
            "username": "user",
        }
        doc = SimpleNamespace(
            get=lambda field: credential_values.get(field),
            has_permission=lambda _permission: True,
            get_password=lambda _field: "pass",
        )
        template = self._template()
        template.get_formatted_email = lambda _context: {
            "subject": "Access CSC-1",
            "message": "body",
        }

        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}),
            patch.object(credential_email, "approvals", store),
            patch.object(
                credential_email.frappe,
                "session",
                SimpleNamespace(user=user),
            ),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site=site),
            ),
            patch.object(credential_email.frappe, "sendmail") as sendmail,
        ):
            rejected = credential_email.confirm_customer_service_credential_email(token)
        self.assertEqual(rejected["code"], "DIRECT_EXECUTION_REQUIRED")
        self.assertIsNone(read_record(store, token).consumed_at)
        sendmail.assert_not_called()

        db = SimpleNamespace(commit=Mock(), rollback=Mock())
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "approval_required"}),
            patch.object(credential_email, "approvals", store),
            patch.object(
                credential_email.frappe,
                "session",
                SimpleNamespace(user=user),
            ),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site=site),
            ),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(
                    doc,
                    {
                        "credential_name": "CSC-1",
                        "customer": "Customer 1",
                        "domain_name": "example.com",
                        "credential_type": "cPanel",
                        "account_name": "Main",
                        "account_identity": "main",
                        "control_panel_url": "https://panel.example.com",
                    },
                    template,
                    user,
                ),
            ),
            patch.object(credential_email.frappe, "db", db),
            patch.object(
                credential_email.frappe,
                "sendmail",
                return_value=SimpleNamespace(
                    name="EMAIL-QUEUE-1",
                    to=["recipient@example.com"],
                    cc=["customer@example.com", "operator@example.com"],
                ),
            ) as sendmail,
        ):
            result = credential_email.confirm_customer_service_credential_email(token)
        self.assertEqual(result["status"], "queued")
        self.assertIsNotNone(read_record(store, token).consumed_at)
        sendmail.assert_called_once()

    def test_credential_apply_checks_mode_before_secret_access(self):
        username = Mock(
            side_effect=AssertionError("username accessed before mode check")
        )
        password = Mock(
            side_effect=AssertionError("password accessed before mode check")
        )
        doc = SimpleNamespace(get=username, get_password=password)
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "approval_required"}),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(doc, {}, SimpleNamespace(), "operator@example.com"),
            ),
            patch.object(credential_email.frappe, "sendmail") as sendmail,
        ):
            result = credential_email._apply({}, credential_email.WriteMode.DIRECT)
        self.assertEqual(result["code"], "APPROVAL_REQUIRED")
        username.assert_not_called()
        password.assert_not_called()
        sendmail.assert_not_called()

    def test_credential_approval_apply_checks_mode_before_secret_access(self):
        username = Mock(
            side_effect=AssertionError("username accessed before mode check")
        )
        password = Mock(
            side_effect=AssertionError("password accessed before mode check")
        )
        doc = SimpleNamespace(get=username, get_password=password)
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(doc, {}, SimpleNamespace(), "operator@example.com"),
            ),
            patch.object(credential_email.frappe, "sendmail") as sendmail,
        ):
            result = credential_email._apply(
                {}, credential_email.WriteMode.APPROVAL_REQUIRED
            )
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        username.assert_not_called()
        password.assert_not_called()
        sendmail.assert_not_called()

    def test_credential_final_mode_guard_blocks_send_after_secret_render(self):
        doc = SimpleNamespace(
            get=lambda field: "user" if field == "username" else None,
            get_password=lambda _field: "pass",
        )
        snapshot = {
            "credential_name": "CSC-1",
            "customer": "Customer 1",
            "domain_name": "example.com",
            "credential_type": "cPanel",
            "account_name": "Main",
            "account_identity": "main",
            "control_panel_url": "https://panel.example.com",
        }

        def render(_context):
            os.environ["MCP_EMAIL_MODE"] = "disabled"
            return {"subject": "Approved subject", "message": "body"}

        template = SimpleNamespace(get_formatted_email=render)
        payload = {
            "credential_name": "CSC-1",
            "recipient_email": "recipient@example.com",
            "cc": ["operator@example.com"],
            "approved_subject": "Approved subject",
            "subject_override": False,
            "additional_note_variable": "additional_note",
            "additional_note": None,
        }
        db = SimpleNamespace(commit=Mock(), rollback=Mock())
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "direct"}),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(doc, snapshot, template, "operator@example.com"),
            ),
            patch.object(credential_email.frappe, "db", db),
            patch.object(credential_email.frappe, "sendmail") as sendmail,
        ):
            result = credential_email._apply(payload, credential_email.WriteMode.DIRECT)
        self.assertEqual(result["code"], "EMAIL_DISABLED")
        sendmail.assert_not_called()
        db.commit.assert_not_called()
        db.rollback.assert_called_once()

    def test_credential_approval_final_mode_guard_blocks_send_after_secret_render(self):
        doc = SimpleNamespace(
            get=lambda field: "user" if field == "username" else None,
            get_password=lambda _field: "pass",
        )
        snapshot = {
            "credential_name": "CSC-1",
            "customer": "Customer 1",
            "domain_name": "example.com",
            "credential_type": "cPanel",
            "account_name": "Main",
            "account_identity": "main",
            "control_panel_url": "https://panel.example.com",
        }

        def render(_context):
            os.environ["MCP_EMAIL_MODE"] = "direct"
            return {"subject": "Approved subject", "message": "body"}

        payload = {
            "credential_name": "CSC-1",
            "recipient_email": "recipient@example.com",
            "cc": ["operator@example.com"],
            "approved_subject": "Approved subject",
            "subject_override": False,
            "additional_note_variable": "additional_note",
            "additional_note": None,
        }
        db = SimpleNamespace(commit=Mock(), rollback=Mock())
        with (
            patch.dict(os.environ, {"MCP_EMAIL_MODE": "approval_required"}),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(
                    doc,
                    snapshot,
                    SimpleNamespace(get_formatted_email=render),
                    "operator@example.com",
                ),
            ),
            patch.object(credential_email.frappe, "db", db),
            patch.object(credential_email.frappe, "sendmail") as sendmail,
        ):
            result = credential_email._apply(
                payload, credential_email.WriteMode.APPROVAL_REQUIRED
            )
        self.assertEqual(result["code"], "DIRECT_EXECUTION_REQUIRED")
        sendmail.assert_not_called()
        db.commit.assert_not_called()
        db.rollback.assert_called_once()

    def test_credential_email_approval_is_independent_of_create_mode(self):
        for mode in ("disabled", "direct"):
            with (
                self.subTest(mode=mode),
                patch.dict(os.environ, {"MCP_CREATE_MODE": mode}),
            ):
                doc, password = self._credential_doc()
                result, create, _outgoing = self._prepare_with_dependencies(doc=doc)
                self.assertEqual(result["status"], "ready_for_approval")
                self.assertEqual(result["approval_token"], "opaque")
                create.assert_called_once()
                password.assert_not_called()

    def _credential_doc(self, *, active=True):
        password = Mock(side_effect=AssertionError("test accessed a secret too early"))
        values = {
            "name": "CSC-1",
            "modified": "m1",
            "customer": "Customer 1",
            "domain_name": "example.com",
            "credential_type": "cPanel",
            "account_name": "Main",
            "account_identity": "main",
            "control_panel_url": "https://panel.example.com",
            "is_active": active,
        }
        return (
            SimpleNamespace(
                get=lambda field: (
                    (_ for _ in ()).throw(
                        AssertionError("username read before revalidation")
                    )
                    if field == "username"
                    else values.get(field)
                ),
                has_permission=lambda _permission: True,
                get_password=password,
            ),
            password,
        )

    def _template(self, *, name="CP Template", modified="t1", subject=None):
        subject = subject or "Access {{ credential_name }}"
        return SimpleNamespace(
            name=name,
            modified=modified,
            subject=subject,
            response="{{ additional_note }} {{ changed_note }}",
            response_html=None,
            use_html=0,
            has_permission=lambda _permission: True,
            get_formatted_subject=lambda context: subject.replace(
                "{{ credential_name }}", context["credential_name"]
            )
            .replace("{{ username }}", context["username"])
            .replace("{{ password }}", context["password"]),
        )

    def _prepared_payload(self, template):
        return {
            "credential_name": "CSC-1",
            "credential_modified": "m1",
            "customer": "Customer 1",
            "domain_name": "example.com",
            "credential_type": "cPanel",
            "account_name": "Main",
            "account_identity": "main",
            "control_panel_url": "https://panel.example.com",
            "is_active": True,
            "recipient_email": "recipient@example.com",
            "customer_cc_email": "customer@example.com",
            "operator_email": "operator@example.com",
            "cc": ["customer@example.com", "operator@example.com"],
            "reply_to": "operator@example.com",
            **credential_email._template_state(template),
            "additional_note_variable": "additional_note",
            "approved_subject": "Access CSC-1",
            "subject_override": False,
            "additional_note": "note",
        }

    def _confirm_with_real_revalidation(
        self,
        *,
        customer_email="customer@example.com",
        operator_email="operator@example.com",
        config=None,
        template=None,
        payload_template=None,
        claim=None,
        successful_queue=False,
        doc=None,
    ):
        if doc is None:
            doc, password = self._credential_doc()
        else:
            password = Mock(return_value="pass")
        template = template or self._template()
        payload = self._prepared_payload(payload_template or self._template())
        config = config or SimpleNamespace(
            template_for=lambda _credential_type: "CP Template",
            additional_note_variable="additional_note",
        )
        customer = SimpleNamespace(
            get=lambda field: customer_email if field == "email_id" else None,
            has_permission=lambda _permission: True,
        )
        db = SimpleNamespace(
            get_value=Mock(return_value={"email": operator_email, "enabled": 1}),
            commit=Mock(),
            rollback=Mock(),
        )
        with (
            patch.object(
                credential_email, "_current_user", return_value="operator@example.com"
            ),
            patch.object(credential_email, "_load_credential", return_value=doc),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                side_effect=claim if claim is not None else None,
                return_value=(SimpleNamespace(payload=payload), "available"),
            ),
            patch.object(
                credential_email.frappe,
                "get_doc",
                side_effect=lambda doctype, _name: (
                    customer if doctype == "Customer" else template
                ),
            ),
            patch.object(credential_email.frappe, "db", db),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            patch.object(
                credential_email, "load_business_defaults", return_value=config
            ),
            patch.object(
                credential_email.EmailAccount, "find_outgoing", return_value=object()
            ),
            patch.object(
                credential_email.frappe,
                "sendmail",
                return_value=(
                    SimpleNamespace(
                        name="EMAIL-QUEUE-1",
                        to=["recipient@example.com"],
                        cc=["customer@example.com", "operator@example.com"],
                    )
                    if successful_queue
                    else None
                ),
            ) as sendmail,
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        return result, password, sendmail, db

    def _prepare_with_dependencies(
        self, *, doc, template=None, config=None, outgoing_account=True, real_conf=None
    ):
        customer = SimpleNamespace(
            get=lambda field: "customer@example.com" if field == "email_id" else None,
            has_permission=lambda _permission: True,
        )
        template = template or self._template()
        config = config or SimpleNamespace(
            template_for=lambda _credential_type: "CP Template",
            additional_note_variable="additional_note",
        )
        db = SimpleNamespace(
            get_value=Mock(return_value={"email": "operator@example.com", "enabled": 1})
        )
        defaults = (
            patch.object(
                credential_email,
                "load_business_defaults",
                side_effect=lambda **_kwargs: load_business_defaults(
                    frappe_module=SimpleNamespace(conf=real_conf)
                ),
            )
            if real_conf is not None
            else patch.object(
                credential_email, "load_business_defaults", return_value=config
            )
        )
        with (
            patch.object(credential_email.credentials, "credential_schema"),
            patch.object(
                credential_email.frappe,
                "get_doc",
                side_effect=lambda doctype, _name: (
                    doc
                    if doctype == credential_email.credentials.CREDENTIAL_DOCTYPE
                    else customer if doctype == "Customer" else template
                ),
            ),
            patch.object(
                credential_email, "_current_user", return_value="operator@example.com"
            ),
            patch.object(credential_email.frappe, "db", db),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            defaults,
            patch.object(
                credential_email.EmailAccount,
                "find_outgoing",
                return_value=object() if outgoing_account else None,
            ) as outgoing,
            patch.object(
                credential_email.approvals, "create", return_value="opaque"
            ) as create,
        ):
            result = credential_email.prepare_customer_service_credential_email(
                credential_name="CSC-1", recipient_email="recipient@example.com"
            )
        return result, create, outgoing

    def _confirm_with_claim_state(self, state):
        with (
            patch.object(
                credential_email.frappe,
                "session",
                SimpleNamespace(user="operator@example.com"),
            ),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                return_value=(None, state),
            ),
            patch.object(credential_email, "_revalidate") as revalidate,
            patch.object(credential_email.frappe, "sendmail") as sendmail,
            patch.object(
                credential_email.frappe,
                "db",
                SimpleNamespace(commit=Mock(), rollback=Mock()),
            ) as db,
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        return result, revalidate, sendmail, db

    def test_public_inputs_reject_secret_and_configuration_overrides(self):
        with self.assertRaises(ValueError):
            CredentialEmailPrepareInput(
                credential_name="CSC-1",
                recipient_email="a@example.com",
                password="secret",
            )
        with self.assertRaises(ValueError):
            CredentialEmailConfirmInput(approval_token="x", credential_name="CSC-1")

    def test_business_defaults_preserve_legacy_namespace_and_validate_exact_types(self):
        config = SimpleNamespace(
            conf={
                "mcp_shayona": {
                    "business_defaults": {
                        "version": 1,
                        "credential_email": {
                            "email_templates": {
                                "cPanel": "CP Template",
                                "Domain": "Domain Template",
                            },
                            "additional_note_variable": "additional_note",
                        },
                    }
                }
            }
        )
        loaded = load_business_defaults(frappe_module=config)
        self.assertEqual(loaded.template_for("cPanel"), "CP Template")

    def test_known_credential_email_errors_keep_capability_safe_messages(self):
        for code in (
            "INVALID_RECIPIENT",
            "EMAIL_TEMPLATE_INVALID",
            "EMAIL_QUEUE_FAILED",
        ):
            with (
                self.subTest(code=code),
                patch.object(
                    credential_email,
                    "logged_defined_error",
                    return_value={"status": "error", "code": code},
                ) as logged,
            ):
                with patch.object(
                    credential_email,
                    "_plan",
                    side_effect=credential_email.CredentialEmailError(code),
                ):
                    credential_email.prepare_customer_service_credential_email()
            self.assertEqual(logged.call_args.args[1], code)

        with patch.object(
            credential_email,
            "logged_defined_error",
            return_value={"status": "error", "code": "UNKNOWN"},
        ) as logged:
            with patch.object(
                credential_email,
                "_plan",
                side_effect=credential_email.CredentialEmailError("UNKNOWN"),
            ):
                credential_email.prepare_customer_service_credential_email()
        self.assertEqual(logged.call_args.args[1], "UNKNOWN")

    def test_approval_claim_failures_are_terminal_before_revalidation_or_secrets(self):
        expected = {
            "expired": "CONFIRMATION_EXPIRED",
            "consumed": "CONFIRMATION_CONSUMED",
            "unavailable": "CONFIRMATION_UNAVAILABLE",
            "not_trusted": "TRUSTED_APPROVAL_UNAVAILABLE",
        }
        for state, code in expected.items():
            with self.subTest(state=state):
                result, revalidate, sendmail, db = self._confirm_with_claim_state(state)
                self.assertEqual(result["code"], code)
                revalidate.assert_not_called()
                sendmail.assert_not_called()
                db.commit.assert_not_called()
                db.rollback.assert_not_called()

    def test_stale_state_failure_is_before_secret_access_and_send(self):
        password = Mock(side_effect=AssertionError("stale state read a secret"))
        doc = SimpleNamespace(
            get=lambda field: "USERNAME-SECRET" if field == "username" else None,
            get_password=password,
        )
        with (
            patch.object(
                credential_email, "_current_user", return_value="operator@example.com"
            ),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                return_value=(SimpleNamespace(payload={}), "available"),
            ),
            patch.object(
                credential_email,
                "_revalidate",
                side_effect=credential_email.CredentialEmailError(
                    "PREPARED_STATE_CHANGED"
                ),
            ) as revalidate,
            patch.object(credential_email.frappe, "sendmail") as sendmail,
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        self.assertEqual(result["code"], "PREPARED_STATE_CHANGED")
        revalidate.assert_called_once()
        password.assert_not_called()
        sendmail.assert_not_called()

    def test_changed_addresses_fail_closed_with_the_dedicated_safe_message(self):
        for change in (
            {"customer_email": "changed-customer@example.com"},
            {"operator_email": "changed-operator@example.com"},
        ):
            with self.subTest(change=change):
                result, password, sendmail, db = self._confirm_with_real_revalidation(
                    **change
                )
                self.assertEqual(result["code"], "PREPARED_STATE_CHANGED")
                self.assertEqual(
                    result["message"],
                    credential_email.defined_error("PREPARED_STATE_CHANGED")["message"],
                )
                password.assert_not_called()
                sendmail.assert_not_called()
                db.commit.assert_not_called()

    def test_changed_business_config_fails_before_secret_access(self):
        for config, template in (
            (
                SimpleNamespace(
                    template_for=lambda _credential_type: "New Template",
                    additional_note_variable="additional_note",
                ),
                self._template(name="New Template"),
            ),
            (
                SimpleNamespace(
                    template_for=lambda _credential_type: "CP Template",
                    additional_note_variable="changed_note",
                ),
                self._template(),
            ),
        ):
            with self.subTest(config=config):
                result, password, sendmail, db = self._confirm_with_real_revalidation(
                    config=config, template=template
                )
                self.assertEqual(result["code"], "PREPARED_STATE_CHANGED")
                password.assert_not_called()
                sendmail.assert_not_called()
                db.commit.assert_not_called()

    def test_changed_template_state_fails_before_secret_access(self):
        prepared_template = self._template()
        for template in (
            self._template(modified="t2"),
            self._template(subject="Changed access {{ credential_name }}"),
        ):
            with self.subTest(template=template.subject):
                result, password, sendmail, db = self._confirm_with_real_revalidation(
                    template=template, payload_template=prepared_template
                )
                self.assertEqual(result["code"], "PREPARED_STATE_CHANGED")
                password.assert_not_called()
                sendmail.assert_not_called()
                db.commit.assert_not_called()

    def test_changed_control_panel_url_blocks_before_secret_access(self):
        password = Mock(side_effect=AssertionError("stale URL read a secret"))
        doc = SimpleNamespace(
            get=lambda field: {
                "name": "CSC-1",
                "modified": "m1",
                "customer": "Customer 1",
                "domain_name": "example.com",
                "credential_type": "cPanel",
                "account_name": "Main",
                "account_identity": "main",
                "control_panel_url": "https://new-panel.example.com",
                "is_active": 1,
                "username": "user",
            }.get(field),
            has_permission=lambda _permission: True,
            get_password=password,
        )
        payload = {
            "credential_name": "CSC-1",
            "credential_modified": "m1",
            "customer": "Customer 1",
            "domain_name": "example.com",
            "credential_type": "cPanel",
            "account_name": "Main",
            "account_identity": "main",
            "control_panel_url": "https://old-panel.example.com",
            "is_active": True,
        }
        with (
            patch.object(
                credential_email, "_current_user", return_value="operator@example.com"
            ),
            patch.object(credential_email, "_load_credential", return_value=doc),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                return_value=(SimpleNamespace(payload=payload), "available"),
            ),
            patch.object(credential_email.frappe, "sendmail") as sendmail,
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        self.assertEqual(result["code"], "PREPARED_STATE_CHANGED")
        password.assert_not_called()
        sendmail.assert_not_called()

    def test_prepare_prerequisite_failures_do_not_read_secrets(self):
        password = Mock(side_effect=AssertionError("prepare read a secret"))
        doc = SimpleNamespace(
            name="CSC-1",
            is_active=1,
            get=lambda field: {
                "name": "CSC-1",
                "is_active": 1,
                "customer": "Customer 1",
                "domain_name": "example.com",
                "credential_type": "cPanel",
                "account_name": "Main",
                "account_identity": "main",
                "control_panel_url": "https://panel.example.com",
                "modified": "m1",
            }.get(field),
            has_permission=lambda _permission: True,
            get_password=password,
        )
        with patch.object(credential_email, "_load_credential", return_value=doc):
            result = credential_email.prepare_customer_service_credential_email(
                credential_name="CSC-1", recipient_email="not-an-email"
            )
        self.assertEqual(result["code"], "INVALID_RECIPIENT")
        password.assert_not_called()

    def test_prepare_inactive_and_unreadable_credentials_are_secret_free(self):
        inactive, inactive_password = self._credential_doc(active=False)
        unreadable, unreadable_password = self._credential_doc()
        unreadable.has_permission = lambda _permission: False
        for doc, password, code in (
            (inactive, inactive_password, "CREDENTIAL_INACTIVE"),
            (unreadable, unreadable_password, "PERMISSION_DENIED"),
        ):
            with self.subTest(code=code):
                result, create, outgoing = self._prepare_with_dependencies(doc=doc)
                self.assertEqual(result["code"], code)
                password.assert_not_called()
                create.assert_not_called()
                outgoing.assert_not_called()

    def test_prepare_rejects_missing_and_invalid_business_defaults_before_secrets(self):
        configurations = (
            (
                SimpleNamespace(get=Mock(return_value=None)),
                "EMAIL_TEMPLATE_NOT_CONFIGURED",
            ),
            (
                SimpleNamespace(
                    get=Mock(
                        return_value={
                            "business_defaults": {
                                "version": 1,
                                "credential_email": {
                                    "email_templates": {"cPanel": "CP Template"},
                                    "additional_note_variable": "additional_note",
                                },
                            }
                        }
                    )
                ),
                "EMAIL_TEMPLATE_INVALID",
            ),
        )
        for conf, code in configurations:
            doc, password = self._credential_doc()
            with self.subTest(code=code):
                result, create, outgoing = self._prepare_with_dependencies(
                    doc=doc, real_conf=conf
                )
                self.assertEqual(result["code"], code)
                password.assert_not_called()
                create.assert_not_called()
                outgoing.assert_not_called()

    def test_prepare_rejects_unsafe_subjects_and_missing_outgoing_account(self):
        cases = (
            ("Access {{ username }}", True, "EMAIL_TEMPLATE_UNSAFE"),
            ("Access {{ password }}", True, "EMAIL_TEMPLATE_UNSAFE"),
            ("Access {{ credential_name }}", False, "EMAIL_ACCOUNT_NOT_CONFIGURED"),
        )
        for subject, outgoing_account, code in cases:
            doc, password = self._credential_doc()
            with self.subTest(subject=subject, outgoing_account=outgoing_account):
                result, create, outgoing = self._prepare_with_dependencies(
                    doc=doc,
                    template=self._template(subject=subject),
                    outgoing_account=outgoing_account,
                )
                self.assertEqual(result["code"], code)
                password.assert_not_called()
                create.assert_not_called()
                if code == "EMAIL_TEMPLATE_UNSAFE":
                    outgoing.assert_not_called()

    @patch.object(credential_email, "_load_credential")
    @patch.object(
        credential_email, "_current_user", return_value="operator@example.com"
    )
    def test_prepare_never_reads_secrets_and_binds_control_panel_url(self, _user, load):
        doc = SimpleNamespace(
            name="CSC-1",
            modified="m1",
            customer="Customer 1",
            domain_name="example.com",
            credential_type="cPanel",
            account_name="Main",
            account_identity="main",
            control_panel_url="https://panel.example.com",
            is_active=1,
            get=lambda field: {
                "name": "CSC-1",
                "modified": "m1",
                "customer": "Customer 1",
                "domain_name": "example.com",
                "credential_type": "cPanel",
                "account_name": "Main",
                "account_identity": "main",
                "control_panel_url": "https://panel.example.com",
                "is_active": 1,
            }.get(field),
            has_permission=lambda _permission: True,
            get_password=Mock(side_effect=AssertionError("prepare decrypted a secret")),
        )
        load.return_value = doc
        customer = SimpleNamespace(
            email_id="customer@example.com",
            has_permission=lambda _p: True,
            get=lambda f: "customer@example.com" if f == "email_id" else None,
        )
        template = SimpleNamespace(
            name="CP Template",
            modified="t1",
            subject="Access {{ credential_name }}",
            response="{{ additional_note }} {{ username }} {{ password }}",
            response_html=None,
            use_html=0,
            has_permission=lambda _p: True,
            get_formatted_subject=lambda context: f"Access {context['credential_name']}",
        )
        with (
            patch.object(
                credential_email.frappe,
                "session",
                SimpleNamespace(user="operator@example.com"),
            ),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            patch.object(
                credential_email.frappe,
                "get_doc",
                side_effect=lambda doctype, _name: (
                    customer if doctype == "Customer" else template
                ),
            ),
            patch.object(
                credential_email.frappe,
                "db",
                SimpleNamespace(
                    get_value=Mock(
                        return_value={"email": "operator@example.com", "enabled": 1}
                    )
                ),
            ),
            patch.object(
                credential_email,
                "load_business_defaults",
                return_value=SimpleNamespace(
                    template_for=lambda _t: "CP Template",
                    additional_note_variable="additional_note",
                ),
            ),
            patch.object(
                credential_email.EmailAccount, "find_outgoing", return_value=object()
            ),
            patch.object(
                credential_email.approvals, "create", return_value="opaque"
            ) as create,
        ):
            result = credential_email.prepare_customer_service_credential_email(
                credential_name="CSC-1",
                recipient_email="customer@example.com",
                additional_note="note",
            )
        self.assertEqual(result["status"], "ready_for_approval")
        self.assertEqual(
            result["preview"]["control_panel_url"], "https://panel.example.com"
        )
        self.assertNotIn("username", result["preview"])
        self.assertNotIn("password", result["preview"])
        self.assertNotIn("username", create.call_args.kwargs["payload"])
        self.assertNotIn("password", create.call_args.kwargs["payload"])
        doc.get_password.assert_not_called()

    @patch.object(credential_email, "_revalidate")
    @patch.object(
        credential_email, "_current_user", return_value="operator@example.com"
    )
    def test_confirm_claims_target_approval_before_reading_secret(
        self, _user, revalidate
    ):
        password = Mock(return_value="PASSWORD-SECRET")
        doc = SimpleNamespace(
            get=lambda field: "USERNAME-SECRET" if field == "username" else None,
            get_password=password,
        )
        template = SimpleNamespace(
            get_formatted_email=lambda _context: {
                "subject": "Approved subject",
                "message": "credential message",
            }
        )
        revalidate.return_value = (
            doc,
            {
                "credential_name": "CSC-1",
                "control_panel_url": "https://panel.example.com",
                "customer": "Customer 1",
                "domain_name": "example.com",
                "credential_type": "cPanel",
                "account_name": "Main",
                "account_identity": "main",
            },
            template,
            "operator@example.com",
        )
        payload = {
            "credential_name": "CSC-1",
            "recipient_email": "customer@example.com",
            "cc": ["operator@example.com"],
            "approved_subject": "Approved subject",
            "subject_override": False,
            "additional_note_variable": "additional_note",
            "additional_note": "note",
        }
        approval = SimpleNamespace(payload=payload)
        with (
            patch.object(
                credential_email.frappe,
                "session",
                SimpleNamespace(user="operator@example.com"),
            ),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                return_value=(approval, "available"),
            ) as claim,
            patch.object(
                credential_email.frappe,
                "sendmail",
                return_value=SimpleNamespace(
                    name="EMAIL-Q-1",
                    to=["customer@example.com"],
                    cc=["operator@example.com"],
                ),
            ) as sendmail,
            patch.object(
                credential_email.frappe,
                "db",
                SimpleNamespace(commit=Mock(), rollback=Mock()),
            ) as db,
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        self.assertEqual(result["status"], "queued")
        claim.assert_called_once_with(
            "opaque",
            action=credential_email.CREDENTIAL_EMAIL_ACTION,
            site="shayona.localhost",
            user="operator@example.com",
        )
        password.assert_called_once_with("password")
        self.assertEqual(db.commit.call_count, 1)
        sendmail.assert_called_once_with(
            recipients=["customer@example.com"],
            cc=["operator@example.com"],
            reply_to="operator@example.com",
            subject="Approved subject",
            message="credential message",
            doctype=credential_email.credentials.CREDENTIAL_DOCTYPE,
            name="CSC-1",
            redact_message_after_send=True,
        )
        self.assertNotIn("USERNAME-SECRET", repr(result))
        self.assertNotIn("PASSWORD-SECRET", repr(result))

    def test_invalid_queue_rolls_back_without_commit(self):
        with (
            patch.object(
                credential_email, "_current_user", return_value="operator@example.com"
            ),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(
                    SimpleNamespace(
                        get=lambda field: "user" if field == "username" else None,
                        get_password=lambda _field: "pass",
                    ),
                    {
                        "credential_name": "CSC-1",
                        "customer": "Customer 1",
                        "domain_name": "example.com",
                        "credential_type": "cPanel",
                        "account_name": "Main",
                        "account_identity": "main",
                        "control_panel_url": "https://panel.example.com",
                    },
                    SimpleNamespace(
                        get_formatted_email=lambda _context: {
                            "subject": "Approved subject",
                            "message": "message",
                        }
                    ),
                    "operator@example.com",
                ),
            ),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                return_value=(
                    SimpleNamespace(
                        payload={
                            "credential_name": "CSC-1",
                            "recipient_email": "customer@example.com",
                            "cc": ["operator@example.com"],
                            "approved_subject": "Approved subject",
                            "subject_override": False,
                            "additional_note_variable": "additional_note",
                        }
                    ),
                    "available",
                ),
            ),
            patch.object(credential_email.frappe, "sendmail", return_value=None),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            patch.object(
                credential_email.frappe,
                "db",
                SimpleNamespace(commit=Mock(), rollback=Mock()),
            ) as db,
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        self.assertEqual(result["code"], "EMAIL_QUEUE_FAILED")
        db.commit.assert_not_called()
        db.rollback.assert_called_once()

    def test_queue_reference_rejects_missing_or_mismatched_recipients(self):
        payload = {
            "recipient_email": "customer@example.com",
            "cc": ["operator@example.com"],
        }
        queues = (
            None,
            SimpleNamespace(
                name="", to=["customer@example.com"], cc=["operator@example.com"]
            ),
            SimpleNamespace(name="Q-1", to=[], cc=["operator@example.com"]),
            SimpleNamespace(
                name="Q-1", to=["customer@example.com"], cc=["customer@example.com"]
            ),
            SimpleNamespace(name="Q-1", to=["customer@example.com"], cc=[]),
        )
        for queue in queues:
            with self.subTest(queue=queue):
                self.assertIsNone(credential_email._queue_reference(queue, payload))

    def test_send_exception_rolls_back_without_commit(self):
        with (
            patch.object(
                credential_email, "_current_user", return_value="operator@example.com"
            ),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(
                    SimpleNamespace(
                        get=lambda field: "user" if field == "username" else None,
                        get_password=lambda _field: "pass",
                    ),
                    {
                        "credential_name": "CSC-1",
                        "customer": "Customer 1",
                        "domain_name": "example.com",
                        "credential_type": "cPanel",
                        "account_name": "Main",
                        "account_identity": "main",
                        "control_panel_url": "https://panel.example.com",
                    },
                    SimpleNamespace(
                        get_formatted_email=lambda _context: {
                            "subject": "Approved subject",
                            "message": "message",
                        }
                    ),
                    "operator@example.com",
                ),
            ),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                return_value=(
                    SimpleNamespace(
                        payload={
                            "credential_name": "CSC-1",
                            "recipient_email": "customer@example.com",
                            "cc": ["operator@example.com"],
                            "approved_subject": "Approved subject",
                            "subject_override": False,
                            "additional_note_variable": "additional_note",
                        }
                    ),
                    "available",
                ),
            ),
            patch.object(
                credential_email.frappe, "sendmail", side_effect=RuntimeError("queue")
            ),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            patch.object(
                credential_email.frappe,
                "db",
                SimpleNamespace(commit=Mock(), rollback=Mock()),
            ) as db,
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        self.assertEqual(result["code"], "EMAIL_QUEUE_FAILED")
        db.commit.assert_not_called()
        db.rollback.assert_called_once()

    def test_send_permission_failure_is_safe_and_rolls_back(self):
        with (
            patch.object(
                credential_email, "_current_user", return_value="operator@example.com"
            ),
            patch.object(
                credential_email,
                "_revalidate",
                return_value=(
                    SimpleNamespace(
                        get=lambda field: "user" if field == "username" else None,
                        get_password=lambda _field: "pass",
                    ),
                    {
                        "credential_name": "CSC-1",
                        "customer": "Customer 1",
                        "domain_name": "example.com",
                        "credential_type": "cPanel",
                        "account_name": "Main",
                        "account_identity": "main",
                        "control_panel_url": "https://panel.example.com",
                    },
                    SimpleNamespace(
                        get_formatted_email=lambda _context: {
                            "subject": "Approved subject",
                            "message": "message",
                        }
                    ),
                    "operator@example.com",
                ),
            ),
            patch.object(
                credential_email.approvals,
                "claim_for_confirm_write",
                return_value=(
                    SimpleNamespace(
                        payload={
                            "credential_name": "CSC-1",
                            "recipient_email": "customer@example.com",
                            "cc": ["operator@example.com"],
                            "approved_subject": "Approved subject",
                            "subject_override": False,
                            "additional_note_variable": "additional_note",
                        }
                    ),
                    "available",
                ),
            ),
            patch.object(
                credential_email.frappe,
                "sendmail",
                side_effect=credential_email.frappe.PermissionError(),
            ),
            patch.object(
                credential_email.frappe,
                "local",
                SimpleNamespace(site="shayona.localhost"),
            ),
            patch.object(
                credential_email.frappe,
                "db",
                SimpleNamespace(commit=Mock(), rollback=Mock()),
            ) as db,
        ):
            result = credential_email.confirm_customer_service_credential_email(
                "opaque"
            )
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        db.commit.assert_not_called()
        db.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
