"""Redaction helpers for sensitive threat-intel fields.

Raw StealthMole responses can contain leaked credentials and personal data.
Per the project data-safety rules, nothing raw may be rendered in the UI,
logged, or committed. These helpers turn sensitive values into masked,
demo-safe forms while preserving enough shape to be useful (domain of an
email, length of a password, network of an IP).
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

REDACTED = "***"

# Matches emails embedded in free text / URL paths (possibly %40-encoded).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+(?:@|%40)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def mask_generic(value: str | None, keep: int = 2) -> str:
    """Mask a generic secret, keeping the first `keep` characters."""
    if not value:
        return ""
    text = str(value)
    if len(text) <= keep:
        return REDACTED
    return f"{text[:keep]}{REDACTED}"


def mask_password(value: str | None) -> str:
    """Never reveal a password; expose only that one existed and its length."""
    if not value:
        return ""
    return f"{REDACTED}(len={len(str(value))})"


def mask_email(value: str | None) -> str:
    """Mask an email to `f***@d***.tld` form."""
    if not value or "@" not in str(value):
        return mask_generic(value)
    local, _, domain = str(value).partition("@")
    local_masked = (local[:1] + REDACTED) if local else REDACTED
    if "." in domain:
        name, _, tld = domain.rpartition(".")
        domain_masked = f"{name[:1]}{REDACTED}.{tld}" if name else f"{REDACTED}.{tld}"
    else:
        domain_masked = f"{domain[:1]}{REDACTED}" if domain else REDACTED
    return f"{local_masked}@{domain_masked}"


def mask_ip(value: str | None) -> str:
    """Mask the host portion of an IPv4 address: `1.2.3.x`."""
    if not value:
        return ""
    text = str(value)
    parts = text.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.{parts[2]}.x"
    # IPv6 or unexpected form: keep only a short prefix.
    return mask_generic(text, keep=4)


def mask_user(value: str | None) -> str:
    """Mask a username or account id; route emails through `mask_email`."""
    if not value:
        return ""
    if "@" in str(value):
        return mask_email(value)
    return mask_generic(value, keep=2)


def scrub_emails(value: str | None) -> str:
    """Replace any email embedded in free text with a masked form."""
    if not value:
        return ""
    return _EMAIL_RE.sub(lambda m: mask_email(m.group(0).replace("%40", "@")), str(value))


def mask_host(value: str | None) -> str:
    """Reduce a login-site host/URL to `scheme://netloc`, dropping the path.

    CDS `host` values are login-page URLs whose path or query can embed the
    victim's email (e.g. `.../register/user%40gmail.com`). We keep only the
    site origin — which is the useful "where was this leaked" signal — and
    scrub any residual email as defense-in-depth.
    """
    if not value:
        return ""
    text = str(value)
    if "://" in text:
        parts = urlsplit(text)
        base = f"{parts.scheme}://{parts.netloc}" if parts.netloc else text.split("/", 1)[0]
    else:
        base = text.split("/", 1)[0]
    return scrub_emails(base)
