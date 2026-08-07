"""Concrete Meta WhatsApp Cloud API client.

The client deliberately uses the Graph API over HTTP instead of a provider SDK.
This keeps the integration small, makes the exact Meta requests visible, and
avoids coupling the domain module to a third-party WhatsApp library.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adapters import AdapterMessageResult
from .models import (
    IntegrationType,
    WhatsAppCloudApiCredentials,
    WhatsAppIntegration,
    WhatsAppMessage,
)
from .phone_numbers import format_phone_number_for_meta

META_CLOUD_API_ADAPTER = "whatsapp_cloud"
GRAPH_API_BASE_URL = "https://graph.facebook.com"


class MetaCloudApiError(RuntimeError):
    """An error returned by Meta or raised while reaching the Graph API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: int | str | None = None,
        fbtrace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.fbtrace_id = fbtrace_id


@dataclass(frozen=True)
class CloudApiPhoneNumber:
    id: str
    display_phone_number: str | None = None
    verified_name: str | None = None
    quality_rating: str | None = None


@dataclass(frozen=True)
class CloudApiConnectionInfo:
    app_id: str
    business_account_id: str
    business_account_name: str | None
    phone_number_id: str
    display_phone_number: str | None
    verified_name: str | None
    quality_rating: str | None


@dataclass(frozen=True)
class MediaDownload:
    """A media file fetched from the Meta Graph API."""

    data: bytes
    mime_type: str | None
    filename: str | None = None


@dataclass(frozen=True)
class CloudApiMessageTemplate:
    id: str
    name: str
    language: str
    status: str
    category: str | None
    components: list[dict[str, Any]]
    quality_score: dict[str, Any] | None
    rejected_reason: str | None


@dataclass(frozen=True)
class CloudApiMessageTemplatePage:
    data: list[CloudApiMessageTemplate]
    next_cursor: str | None


def _error_from_payload(
    payload: Any,
    *,
    status_code: int | None = None,
) -> MetaCloudApiError:
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        error = {}
    message = error.get("message") or "Meta Graph API request failed"
    return MetaCloudApiError(
        str(message),
        status_code=status_code,
        error_code=error.get("code"),
        fbtrace_id=error.get("fbtrace_id"),
    )


def _required_mapping(metadata: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = metadata.get(key)
    if not isinstance(value, Mapping):
        raise MetaCloudApiError(
            f"{key} must be an object for this WhatsApp message",
            status_code=422,
        )
    return dict(value)


def _media_body(
    *,
    message: WhatsAppMessage,
    message_type: str,
) -> dict[str, Any]:
    metadata = message.metadata_json
    source = message.media_url or metadata.get("media_id")
    if not isinstance(source, str) or not source.strip():
        raise MetaCloudApiError(
            f"A {message_type} message requires a Meta media ID or public URL",
            status_code=422,
        )
    source = source.strip()
    media: dict[str, Any] = {
        "link" if source.startswith(("http://", "https://")) else "id": source
    }
    if message.content and message_type in {"image", "video", "document"}:
        media["caption"] = message.content
    filename = metadata.get("filename")
    if message_type == "document" and isinstance(filename, str) and filename:
        media["filename"] = filename

    return media


def _build_message_payload(*, to: str, message: WhatsAppMessage) -> dict[str, Any]:
    """Build the documented Cloud API envelope from a normalized message."""

    message_type = message.message_type.strip().lower()
    metadata = message.metadata_json
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": message_type,
    }

    if message_type == "text":
        body = (message.content or "").strip()
        if not body:
            raise MetaCloudApiError(
                "A text message must contain content", status_code=422
            )
        payload["text"] = {
            "preview_url": metadata.get("preview_url") is True,
            "body": body,
        }
    elif message_type == "audio":
        payload[message_type] = _media_body(
            message=message,
            message_type=message_type,
        )

        payload["audio"] = {
            "link": message.media_url,
            "voice": True
        }
    elif message_type in {"image",  "video", "document", "sticker"}:
        payload[message_type] = _media_body(
            message=message,
            message_type=message_type,
        )
    elif message_type == "location":
        payload["location"] = _required_mapping(metadata, "location")
    elif message_type == "contacts":
        contacts = metadata.get("contacts")
        if not isinstance(contacts, list) or not contacts:
            raise MetaCloudApiError(
                "A contacts message requires a non-empty contacts array",
                status_code=422,
            )
        payload["contacts"] = contacts
    elif message_type == "interactive":
        payload["interactive"] = _required_mapping(metadata, "interactive")
    elif message_type == "template":
        payload["template"] = _required_mapping(metadata, "template")
    elif message_type == "reaction":
        payload["reaction"] = _required_mapping(metadata, "reaction")
    else:
        raise MetaCloudApiError(
            f"Unsupported Meta WhatsApp message type: {message_type}",
            status_code=422,
        )

    return payload


class MetaCloudApiClient:
    """Small synchronous client for the Meta Graph API endpoints we need."""

    def __init__(
        self,
        credentials: WhatsAppCloudApiCredentials | Mapping[str, Any],
        *,
        timeout: float = 15.0,
    ) -> None:
        self.credentials = (
            credentials
            if isinstance(credentials, WhatsAppCloudApiCredentials)
            else WhatsAppCloudApiCredentials.model_validate(credentials)
        )
        self.timeout = timeout

    @property
    def _versioned_base_url(self) -> str:
        return f"{GRAPH_API_BASE_URL}/{self.credentials.api_version}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = urlencode(params or {})
        url = f"{self._versioned_base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        body = None
        headers = {"Authorization": f"Bearer {self.credentials.access_token}"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_body = response.read()
                status_code = getattr(response, "status", 200)
        except HTTPError as exc:
            response_body = exc.read()
            try:
                error_payload = json.loads(response_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                error_payload = {}
            raise _error_from_payload(
                error_payload, status_code=exc.code) from exc
        except URLError as exc:
            raise MetaCloudApiError(
                "Could not reach Meta Graph API", status_code=502
            ) from exc

        try:
            response_payload = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MetaCloudApiError(
                "Meta Graph API returned an invalid JSON response",
                status_code=status_code,
            ) from exc
        if not isinstance(response_payload, dict):
            raise MetaCloudApiError(
                "Meta Graph API returned an unexpected response",
                status_code=status_code,
            )
        if "error" in response_payload:
            raise _error_from_payload(
                response_payload, status_code=status_code)
        return response_payload

    def get_business_account(self) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/{self.credentials.business_account_id}",
            params={"fields": "id,name"},
        )

    def get_phone_numbers(self) -> list[CloudApiPhoneNumber]:
        response = self._request(
            "GET",
            f"/{self.credentials.business_account_id}/phone_numbers",
            params={"fields": (
                "id,display_phone_number,verified_name,quality_rating")},
        )
        items = response.get("data", [])
        if not isinstance(items, list):
            raise MetaCloudApiError(
                "Meta returned an invalid phone number list")
        return [
            CloudApiPhoneNumber(
                id=str(item["id"]),
                display_phone_number=item.get("display_phone_number"),
                verified_name=item.get("verified_name"),
                quality_rating=item.get("quality_rating"),
            )
            for item in items
            if isinstance(item, dict) and item.get("id")
        ]

    def verify_connection(self) -> CloudApiConnectionInfo:
        business_account = self.get_business_account()
        phone = next(
            (
                item
                for item in self.get_phone_numbers()
                if item.id == self.credentials.phone_number_id
            ),
            None,
        )
        if phone is None:
            raise MetaCloudApiError(
                "The phone number ID does not belong to the configured WABA",
                status_code=422,
            )
        return CloudApiConnectionInfo(
            app_id=self.credentials.app_id,
            business_account_id=self.credentials.business_account_id,
            business_account_name=business_account.get("name"),
            phone_number_id=phone.id,
            display_phone_number=phone.display_phone_number,
            verified_name=phone.verified_name,
            quality_rating=phone.quality_rating,
        )

    def subscribe_to_business_account(self) -> bool:
        response = self._request(
            "POST",
            f"/{self.credentials.business_account_id}/subscribed_apps",
        )
        return response.get("success") is True or response.get("success") == "true"

    def retrieve_media(self, media_id: str) -> MediaDownload:
        """Fetch a media object and its bytes from the Graph API.

        Media webhook payloads carry only a media ``id``. This method resolves
        the media URL and downloads the file so it can be stored permanently.
        """
        info = self._request(
            "GET",
            f"/{media_id}",
            params={"fields": "url,mime_type,file_size,sha256"},
        )
        url = info.get("url")
        if not isinstance(url, str) or not url:
            raise MetaCloudApiError(
                "Meta returned a media object without a downloadable URL",
                status_code=422,
            )
        request = Request(url, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read()
        except HTTPError as exc:
            raise MetaCloudApiError(
                f"Could not download Meta media: {exc}", status_code=exc.code
            ) from exc
        except URLError as exc:
            raise MetaCloudApiError(
                "Could not reach Meta media server", status_code=502
            ) from exc
        mime_type = info.get("mime_type")
        filename = info.get("filename")
        return MediaDownload(
            data=data,
            mime_type=str(mime_type) if isinstance(mime_type, str) else None,
            filename=str(filename) if isinstance(filename, str) else None,
        )

    def get_message_templates(
        self, *, limit: int = 100, after: str | None = None
    ) -> CloudApiMessageTemplatePage:
        """Read the current template catalog directly from the connected WABA."""

        params = {
            "fields": (
                "id,name,language,status,category,components,quality_score,"
                "rejected_reason"
            ),
            "limit": str(limit),
        }
        if after:
            params["after"] = after
        response = self._request(
            "GET",
            f"/{self.credentials.business_account_id}/message_templates",
            params=params,
        )
        items = response.get("data", [])
        if not isinstance(items, list):
            raise MetaCloudApiError(
                "Meta returned an invalid template catalog")

        templates: list[CloudApiMessageTemplate] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id") or not item.get("name"):
                continue
            components = item.get("components")
            quality_score = item.get("quality_score")
            templates.append(
                CloudApiMessageTemplate(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    language=str(item.get("language") or ""),
                    status=str(item.get("status") or "UNKNOWN"),
                    category=(str(item["category"])
                              if item.get("category") else None),
                    components=[
                        part for part in components if isinstance(part, dict)]
                    if isinstance(components, list)
                    else [],
                    quality_score=quality_score
                    if isinstance(quality_score, dict)
                    else None,
                    rejected_reason=(
                        str(item["rejected_reason"])
                        if item.get("rejected_reason")
                        else None
                    ),
                )
            )
        paging = response.get("paging")
        cursors = paging.get("cursors") if isinstance(paging, dict) else None
        next_cursor = cursors.get("after") if isinstance(
            cursors, dict) else None
        return CloudApiMessageTemplatePage(data=templates, next_cursor=next_cursor)

    def create_message_template(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Submit a template to Meta's review workflow."""

        return self._request(
            "POST",
            f"/{self.credentials.business_account_id}/message_templates",
            payload=payload,
        )

    def delete_message_template(
        self, *, name: str, hsm_id: str | None = None
    ) -> bool:
        """Delete a template from the connected WABA.

        Per the Meta template-management contract, deleting by ``name`` removes
        every language variant that shares the name. Pass ``hsm_id`` to remove a
        single variant of that name.
        """

        params: dict[str, str] = {"name": name}
        if hsm_id:
            params["hsm_id"] = hsm_id
        response = self._request(
            "DELETE",
            f"/{self.credentials.business_account_id}/message_templates",
            params=params,
        )
        return response.get("success") is True or response.get("success") == "true"

    def send_message(
        self,
        *,
        to: str,
        message: WhatsAppMessage,
    ) -> AdapterMessageResult:
        try:
            normalized_to = format_phone_number_for_meta(to)
        except ValueError as exc:
            raise MetaCloudApiError(str(exc), status_code=422) from exc

        try:
            payload = _build_message_payload(to=normalized_to, message=message)
            response = self._request(
                "POST",
                f"/{self.credentials.phone_number_id}/messages",
                payload=payload,
            )
            
            messages = response.get("messages", [])

            external_id = messages[0].get("id") if messages else None
        except ValueError as exc:
            raise MetaCloudApiError(str(exc), status_code=422) from exc

        return AdapterMessageResult(
            external_id=external_id,
            status="sent",
            raw=response,
        )


class MetaCloudApiAdapter:
    """Adapter registry entry for the non-coexistence Cloud API connector."""

    name = META_CLOUD_API_ADAPTER
    integration_type = IntegrationType.OFFICIAL

    def send_message(
        self,
        *,
        integration: WhatsAppIntegration,
        message: WhatsAppMessage,
    ) -> AdapterMessageResult:
        metadata = integration.credentials_json
        client = MetaCloudApiClient(metadata)
        recipient = message.metadata_json.get("recipient_phone_number")
        if not isinstance(recipient, str) or not recipient.strip():
            raise MetaCloudApiError(
                "recipient_phone_number is required in message metadata",
                status_code=422,
            )
        return client.send_message(to=recipient.strip(), message=message)


def verify_webhook_signature(
    payload: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    """Validate Meta's ``X-Hub-Signature-256`` header."""

    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = (
        "sha256="
        + hmac.new(app_secret.encode("utf-8"),
                   payload, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)
