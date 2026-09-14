"""Narrow authenticated client for the remote mcp_erpnext bridge."""

from __future__ import annotations

import base64
import binascii
import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .settings import MCPSettings

REMOTE_METHOD = "mcp_erpnext.remote_api.execute_mcp_operation"
_TIMEOUT_SECONDS = 15


class RestBackendError(RuntimeError):
    """The configured remote ERPNext bridge could not safely complete a call."""


class _NoRedirect(HTTPRedirectHandler):
    """Do not send an API token to a redirect target."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> Request | None:
        return None


@dataclass(frozen=True)
class ERPNextRestClient:
    """Call the single, application-owned remote Frappe method."""

    settings: MCPSettings

    def execute(
        self, *, operation: str, profile: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = self.settings.rest_endpoint_url()
        payload = json.dumps(
            {
                "payload": json.dumps(
                    {
                        "operation": operation,
                        "profile": profile,
                        "arguments": arguments,
                    },
                    separators=(",", ":"),
                )
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": "token %s:%s"
                % (self.settings.erpnext_api_key, self.settings.erpnext_api_secret),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with build_opener(_NoRedirect).open(
                request, timeout=_TIMEOUT_SECONDS
            ) as response:
                response_body = response.read()
        except HTTPError as error:
            # Do not expose remote body content: Frappe may include traceback/details.
            raise RestBackendError(
                "The remote ERPNext bridge rejected the request."
            ) from error
        except (URLError, socket.timeout, TimeoutError, OSError) as error:
            raise RestBackendError(
                "The remote ERPNext bridge is unavailable."
            ) from error

        try:
            envelope = json.loads(response_body)
            result = envelope["message"]
        except (KeyError, TypeError, ValueError) as error:
            raise RestBackendError(
                "The remote ERPNext bridge returned an invalid response."
            ) from error
        if not isinstance(result, dict):
            raise RestBackendError(
                "The remote ERPNext bridge returned an invalid response."
            )

        encoded_pdf = result.pop("_pdf_base64", None)
        if encoded_pdf is not None:
            if not isinstance(encoded_pdf, str):
                raise RestBackendError(
                    "The remote ERPNext bridge returned an invalid response."
                )
            try:
                result["_pdf"] = base64.b64decode(encoded_pdf, validate=True)
            except (ValueError, binascii.Error) as error:
                raise RestBackendError(
                    "The remote ERPNext bridge returned an invalid response."
                ) from error
        return result
