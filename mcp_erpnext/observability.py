"""Logging helpers for MCP tool failures."""

from __future__ import annotations

import hashlib
import os
import secrets
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import TypeVar

import frappe
from frappe.utils.logger import get_logger


ResultT = TypeVar("ResultT")
_LOGGER_LOCK = Lock()

_PUBLIC_MESSAGES = {
	"ERP_ACCESS_NOT_CONFIGURED": (
		"Your LibreChat account is not linked to an active ERPNext user. "
		"Please contact your administrator."
	),
	"ERP_IDENTITY_CONFIGURATION_ERROR": (
		"The ERPNext identity configuration is incomplete. Please contact your administrator."
	),
	"ERP_PERMISSION_DENIED": (
		"The configured ERPNext user does not have permission for that request. "
		"Please contact your administrator."
	),
	"ORDER_CREATE_UNAVAILABLE": (
		"I couldn't complete the Sales Order request right now. "
		"Please contact your administrator for assistance."
	),
	"ORDER_PREVIEW_UNAVAILABLE": "I couldn't prepare the Sales Order preview right now. Please try again later.",
	"ERP_REQUEST_FAILED": "I couldn't complete that ERPNext request right now. Please try again later.",
}

ERROR_REFERENCE_PREFIX = "MCP-ERR"


class MCPIdentityError(RuntimeError):
	"""Base exception for identity failures that need a safe public response."""

	public_code = "ERP_REQUEST_FAILED"


class MCPIdentityConfigurationError(MCPIdentityError):
	"""The server identity configuration cannot establish an execution user."""

	public_code = "ERP_IDENTITY_CONFIGURATION_ERROR"


class ERPAccessNotConfiguredError(MCPIdentityError):
	"""A LibreChat account has no active mapped ERPNext user."""

	public_code = "ERP_ACCESS_NOT_CONFIGURED"


def new_error_reference() -> str:
	"""Return a unique reference for correlating a safe response with its server log."""
	return f"{ERROR_REFERENCE_PREFIX}-{secrets.token_hex(4).upper()}"


def get_app_logger():
	"""Return a Frappe logger that writes bench and site log files.

	Frappe's logger resolves its relative log paths from the current directory,
	while Codex may launch this process from the bench root. Temporarily using
	the bench ``sites`` directory lets Frappe create its normal absolute-on-disk
	log locations without changing the process working directory permanently.
	"""

	site = getattr(frappe.local, "site", None)
	logger_name = f"mcp_erpnext-{site or 'all'}"
	if logger_name in frappe.loggers:
		return frappe.loggers[logger_name]

	sites_path = (
		getattr(frappe.local, "sites_path", None)
		or os.environ.get("MCP_FRAPPE_SITES_PATH")
		or os.environ.get("FRAPPE_SITES_PATH")
		or str(Path(__file__).resolve().parents[3] / "sites")
	)
	with _LOGGER_LOCK:
		if logger_name in frappe.loggers:
			return frappe.loggers[logger_name]
		if sites_path and Path(sites_path).is_dir():
			original_cwd = os.getcwd()
			try:
				os.chdir(sites_path)
				return get_logger(module="mcp_erpnext", stream_only=False)
			finally:
				os.chdir(original_cwd)
		return get_logger(module="mcp_erpnext", stream_only=False)


def public_error(
	code: str,
	*,
	message: str | None = None,
	reference: str | None = None,
	retryable: bool = False,
) -> dict[str, object]:
	"""Return an MCP error without exposing framework or database details."""
	return {
		"status": "error",
		"code": code,
		"message": message or _PUBLIC_MESSAGES.get(code, _PUBLIC_MESSAGES["ERP_REQUEST_FAILED"]),
		"reference": reference or new_error_reference(),
		"retryable": retryable,
	}


def _error_code_for_tool(tool_name: str) -> str:
	if tool_name == "confirm_sales_order":
		return "ORDER_CREATE_UNAVAILABLE"
	if tool_name == "prepare_sales_order":
		return "ORDER_PREVIEW_UNAVAILABLE"
	return "ERP_REQUEST_FAILED"


def _error_code_for_exception(tool_name: str, error: Exception) -> str:
	"""Keep public codes stable while retaining detailed failures only in the log."""
	if isinstance(error, MCPIdentityError):
		return error.public_code
	if isinstance(error, frappe.PermissionError):
		return "ERP_PERMISSION_DENIED"
	return _error_code_for_tool(tool_name)


def _fingerprint(value: object) -> str:
	if not value:
		return "missing"
	return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _log_tool_failure(
	level: str,
	*,
	reference: str,
	code: str,
	tool_name: str,
	site: str | None,
	user: object,
) -> None:
	"""Log an MCP failure without allowing an unavailable log file to mask it."""
	try:
		logger = get_app_logger()
		message = "MCP %s: reference=%%s code=%%s tool=%%s site=%%s user_fp=%%s" % level
		getattr(logger, level)(
			message,
			reference,
			code,
			tool_name,
			site or "unknown",
			_fingerprint(user),
		)
	except OSError as logging_error:
		# Stdio clients must still receive the original safe MCP error envelope.
		sys.stderr.write(
			"MCP log write failed: reference=%s code=%s tool=%s log_error=%s\n"
			% (reference, code, tool_name, type(logging_error).__name__)
		)


def execute_tool(tool_name: str, operation: Callable[[], ResultT]) -> ResultT:
	"""Run one tool and persist failures through Frappe's logger.

	Only operational context is logged. Natural-language inputs and approval
	tokens are intentionally excluded because they may contain business data or
	secrets.
	"""

	try:
		return operation()
	except frappe.PermissionError as error:
		site = getattr(frappe.local, "site", None)
		user = getattr(getattr(frappe.local, "session", None), "user", None)
		reference = new_error_reference()
		code = _error_code_for_exception(tool_name, error)
		_log_tool_failure(
			"warning",
			reference=reference,
			code=code,
			tool_name=tool_name,
			site=site,
			user=user,
		)
		return public_error(code, reference=reference)
	except Exception as error:
		site = getattr(frappe.local, "site", None)
		user = getattr(getattr(frappe.local, "session", None), "user", None)
		reference = new_error_reference()
		code = _error_code_for_exception(tool_name, error)
		_log_tool_failure(
			"exception",
			reference=reference,
			code=code,
			tool_name=tool_name,
			site=site,
			user=user,
		)
		return public_error(code, reference=reference)
