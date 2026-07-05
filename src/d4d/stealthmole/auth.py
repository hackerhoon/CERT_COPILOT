"""JWT authentication for the StealthMole API.

The API uses an HS256 JWT bearer token. Per the manual, the same JWT must not
be reused — the second call with a reused token returns 401 — so a fresh token
with a new `nonce` and `iat` is generated for every request.

This implementation is dependency-free (standard library only). If `PyJWT` is
installed it produces an identical token to `jwt.encode(payload, secret)`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid


def _b64url(data: bytes) -> str:
    """URL-safe base64 without padding, per the JWS spec."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def encode_hs256(payload: dict, secret: str) -> str:
    """Encode a signed HS256 JWT from `payload` using `secret`."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{_b64url(signature)}"


def build_token(access_key: str, secret_key: str) -> str:
    """Build a single-use JWT for one API request.

    A new `nonce` (UUID) and `iat` (current UTC epoch seconds) are generated on
    every call, so the returned token must not be cached.
    """
    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
        "iat": int(time.time()),
    }
    return encode_hs256(payload, secret_key)


def make_auth_header(access_key: str, secret_key: str) -> str:
    """Return a fresh `Authorization: Bearer <jwt>` header value.

    Never cache the result — call this immediately before each request.
    """
    return f"Bearer {build_token(access_key, secret_key)}"
