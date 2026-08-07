"""Cloudflare R2 object storage client.

The client uses AWS Signature Version 4 (the same protocol Cloudflare R2
implements) over ``urllib`` so no third-party SDK is required. Files are
referenced by a stable object key, and callers can resolve either a public
URL (when ``R2_PUBLIC_BASE_URL`` is configured) or a time-limited presigned
URL for private buckets.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.core.config import settings

SERVICE = "s3"
REGION = "auto"
_ALGORITHM = "AWS4-HMAC-SHA256"
_SHA256_EMPTY = hashlib.sha256(b"").hexdigest()
_UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"


class R2Error(RuntimeError):
    """An error returned by Cloudflare R2 while uploading or downloading."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True)
class R2Object:
    """Metadata for a stored object."""

    key: str
    url: str
    size_bytes: int
    content_type: str | None = None
    filename: str | None = None


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_uri(key: str) -> str:
    # Keys use the safe charset; '/' separates folders, everything else encoded.
    return quote(key, safe="/")


def _canonical_query(params: dict[str, str]) -> str:
    return urlencode(sorted(params.items()))


class R2Storage:
    """Minimal S3-compatible client for Cloudflare R2 object storage."""

    def __init__(self) -> None:
        self.bucket = settings.R2_BUCKET_NAME
        self.endpoint = settings.R2_API_ENDPOINT.rstrip("/")
        self.access_key = settings.R2_ACCESS_KEY_ID
        self.secret_key = settings.R2_SECRET_ACCESS_KEY
        self.public_base_url = settings.R2_PUBLIC_BASE_URL.rstrip("/")
        self.public_url_pattern = settings.R2_PUBLIC_URL_PATTERN.rstrip("/")
        self.timeout = 30.0

    @property
    def configured(self) -> bool:
        return bool(
            self.bucket and self.endpoint and self.access_key and self.secret_key
        )

    def _url_for_key(self, key: str) -> str:
        return f"{self.endpoint}/{self.bucket}/{key}"

    def _authorization(
        self,
        *,
        method: str,
        canonical_uri: str,
        canonical_query: str,
        amz_date: str,
        date_stamp: str,
        payload_hash: str,
        headers: dict[str, str],
        signed_headers: list[str],
    ) -> str:
        canonical_headers = "".join(
            f"{name}:{headers[name]}\n" for name in sorted(headers)
        )
        signed_header_names = ";".join(sorted(signed_headers))
        canonical_request = (
            f"{method}\n{canonical_uri}\n{canonical_query}\n"
            f"{canonical_headers}\n{signed_header_names}\n{payload_hash}"
        )
        scope = f"{date_stamp}/{REGION}/{SERVICE}/aws4_request"
        string_to_sign = "\n".join(
            [
                _ALGORITHM,
                amz_date,
                scope,
                _hash(canonical_request.encode("utf-8")),
            ]
        )
        signing_key = _signing_key(self.secret_key, date_stamp, REGION)
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return (
            f"{_ALGORITHM} Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_header_names}, Signature={signature}"
        )

    def _request(
        self,
        *,
        method: str,
        key: str,
        data: bytes | None = None,
        content_type: str | None = None,
        params: dict[str, str] | None = None,
        payload_hash: str | None = None,
    ) -> tuple[bytes, int]:
        if not self.configured:
            raise R2Error(
                "Cloudflare R2 is not configured. Set R2_* environment variables.",
                status_code=503,
            )

        canonical_uri = _canonical_uri(f"/{self.bucket}/{key}")
        canonical_query = _canonical_query(params or {})
        now = datetime.datetime.now(datetime.UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        body = data or b""
        body_hash = payload_hash or _hash(body)

        headers: dict[str, str] = {
            "host": self._host(),
            "x-amz-content-sha256": body_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            headers["content-type"] = content_type

        signed = ["host", "x-amz-content-sha256", "x-amz-date"]
        if content_type:
            signed.append("content-type")

        authorization = self._authorization(
            method=method,
            canonical_uri=canonical_uri,
            canonical_query=canonical_query,
            amz_date=amz_date,
            date_stamp=date_stamp,
            payload_hash=body_hash,
            headers=headers,
            signed_headers=signed,
        )

        url = self._url_for_key(key)
        if canonical_query:
            url = f"{url}?{canonical_query}"
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": authorization,
                "x-amz-content-sha256": body_hash,
                "x-amz-date": amz_date,
                "User-Agent": "Mozilla/5.0 (compatible; R2StorageClient/1.0)",
            },
        )
        if content_type:
            request.add_header("Content-Type", content_type)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read(), getattr(response, "status", 200)
        except HTTPError as exc:
            error_payload = exc.read()
            raise R2Error(
                f"Cloudflare R2 request failed ({exc.code}): "
                f"{error_payload.decode('utf-8', errors='replace')[:500]}",
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise R2Error(
                "Could not reach Cloudflare R2: " + str(exc), status_code=502
            ) from exc

    def _host(self) -> str:
        from urllib.parse import urlparse

        return urlparse(self.endpoint).netloc

    def put_object(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> R2Object:
        _, status = self._request(
            method="PUT",
            key=key,
            data=data,
            content_type=content_type,
        )
        if status not in {200, 201, 204}:
            raise R2Error(
                f"Cloudflare R2 rejected the upload with status {status}",
                status_code=status,
            )
        return R2Object(
            key=key,
            url=self.public_url(key=key),
            size_bytes=len(data),
            content_type=content_type,
        )

    def get_object(self, *, key: str) -> tuple[bytes, str | None]:
        body, _ = self._request(method="GET", key=key)
        return body, None

    def delete_object(self, *, key: str) -> None:
        _, status = self._request(method="DELETE", key=key)
        if status not in {200, 204}:
            raise R2Error(
                f"Cloudflare R2 rejected the deletion with status {status}",
                status_code=status,
            )

    def presigned_url(self, *, key: str, expires: int = 3600) -> str:
        if not self.configured:
            raise R2Error(
                "Cloudflare R2 is not configured. Set R2_* environment variables.",
                status_code=503,
            )
        canonical_uri = _canonical_uri(f"/{self.bucket}/{key}")
        now = datetime.datetime.now(datetime.UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{REGION}/{SERVICE}/aws4_request"
        credential = f"{self.access_key}/{scope}"
        signed_headers = ["host"]

        query = {
            "X-Amz-Algorithm": _ALGORITHM,
            "X-Amz-Credential": credential,
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": ";".join(signed_headers),
        }
        canonical_query = _canonical_query(query)

        headers = {"host": self._host()}
        authorization = self._authorization(
            method="GET",
            canonical_uri=canonical_uri,
            canonical_query=canonical_query,
            amz_date=amz_date,
            date_stamp=date_stamp,
            payload_hash=_UNSIGNED_PAYLOAD,   # <- era _SHA256_EMPTY
            headers=headers,
            signed_headers=signed_headers,
        )
        signature = authorization.rsplit("Signature=", 1)[-1].strip()
        query["X-Amz-Signature"] = signature
        separator = "?" if "?" not in self._url_for_key(key) else "&"
        return self._url_for_key(key) + separator + urlencode(query)

    def public_url(self, *, key: str) -> str:
        if self.public_url_pattern:
            return self.public_url_pattern.format(key=key)
        if self.public_base_url:
            return f"{self.public_base_url}/{quote(key, safe='/')}"
        return self.presigned_url(key=key)


def _signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, SERVICE)
    return _sign(k_service, "aws4_request")


r2 = R2Storage()
