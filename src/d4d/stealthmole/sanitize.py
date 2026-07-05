"""Turn raw StealthMole responses into masked, demo-safe view models.

Every function here takes a raw parsed response and returns a structure that is
safe to write to `data/stealthmole/sanitized/`, print to a console, or show in
a demo screen: sensitive fields are masked, and the emphasis is on counts,
aggregates, and shape rather than raw leaked values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import redaction

# How many masked sample records to keep per response.
SAMPLE_SIZE = 5


def _iso(ts: Any) -> str | None:
    """Convert a Unix timestamp (seconds) to an ISO-8601 UTC string."""
    if ts in (None, 0, "", "0"):
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, OSError, TypeError):
        return None


def _clip(text: Any, length: int = 120) -> str | None:
    if text is None:
        return None
    s = str(text)
    return s if len(s) <= length else s[:length] + "…"


# -- management ---------------------------------------------------------


def sanitize_quotas(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Add a `remaining` field and a sorted view over the quota map."""
    services: dict[str, Any] = {}
    total_allowed = total_used = 0
    for service, info in (raw or {}).items():
        if not isinstance(info, dict):
            continue
        allowed = int(info.get("allowed") or 0)
        used = int(info.get("used") or 0)
        services[service] = {
            "allowed": allowed,
            "used": used,
            "remaining": max(allowed - used, 0),
        }
        total_allowed += allowed
        total_used += used
    return {
        "services": dict(sorted(services.items())),
        "total_allowed": total_allowed,
        "total_used": total_used,
        "total_remaining": max(total_allowed - total_used, 0),
    }


# -- async targets ------------------------------------------------------


def sanitize_targets(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Target lists are not sensitive; pass them through with a count."""
    raw = raw or {}
    return {
        "totalCount": raw.get("totalCount", 0),
        "targets": raw.get("target", []),
    }


# -- monitoring (rm / gm / lm) ------------------------------------------


def mask_ransomware_record(row: dict[str, Any]) -> dict[str, Any]:
    """Demo-safe masked record for one /rm/search row."""
    return {
        "victim": _clip(row.get("victim"), 80),
        "attack_group": row.get("attack_group"),
        "sector": row.get("sector"),
        "country": row.get("country"),
        "detected_at": _iso(row.get("detection_datetime")),
        "has_proof_url": bool(row.get("proof_url")),
    }


def mask_monitoring_record(row: dict[str, Any]) -> dict[str, Any]:
    """Demo-safe masked record for one /gm|/lm/search row."""
    return {
        "title": _clip(row.get("title"), 100),
        "author": redaction.mask_generic(row.get("author"), keep=2),
        "detected_at": _iso(row.get("detection_datetime")),
        "has_proof_url": bool(row.get("proof_url")),
    }


def mask_credential_record(row: dict[str, Any]) -> dict[str, Any]:
    """Demo-safe masked record for one cl/cds/cb search row (no raw password)."""
    record = {
        "id": redaction.mask_generic(row.get("id"), keep=4),
        "host": redaction.mask_host(row.get("host")) if row.get("host") else None,
        "domain": redaction.mask_generic(row.get("domain"), keep=3) if row.get("domain") else None,
        "user": redaction.mask_user(row.get("user")),
        "email": redaction.mask_email(row.get("email")) if row.get("email") else None,
        "password": redaction.mask_password(row.get("password")),
        "ip": redaction.mask_ip(row.get("ip")) if row.get("ip") else None,
        "username": redaction.mask_generic(row.get("username"), keep=1) if row.get("username") else None,
        "computername": redaction.mask_generic(row.get("computername"), keep=2) if row.get("computername") else None,
        "stealer": row.get("stealertype"),
    }
    leaked = row.get("leaked_date") or row.get("leakeddate")
    record["leaked_date"] = _iso(leaked) if isinstance(leaked, (int, float)) else leaked
    return {k: v for k, v in record.items() if v is not None}


def sanitize_ransomware(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Masked view of /rm/search (public ransomware victim disclosures)."""
    raw = raw or {}
    rows = raw.get("data") or []
    samples = [mask_ransomware_record(row) for row in rows[:SAMPLE_SIZE]]
    sectors: dict[str, int] = {}
    countries: dict[str, int] = {}
    for row in rows:
        if row.get("sector"):
            sectors[row["sector"]] = sectors.get(row["sector"], 0) + 1
        if row.get("country"):
            countries[row["country"]] = countries.get(row["country"], 0) + 1
    return {
        "totalCount": raw.get("totalCount", 0),
        "returned": len(rows),
        "top_sectors": dict(sorted(sectors.items(), key=lambda kv: -kv[1])[:5]),
        "top_countries": dict(sorted(countries.items(), key=lambda kv: -kv[1])[:5]),
        "samples": samples,
    }


def sanitize_monitoring(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Masked view of /gm/search and /lm/search (threat posts)."""
    raw = raw or {}
    rows = raw.get("data") or []
    samples = [mask_monitoring_record(row) for row in rows[:SAMPLE_SIZE]]
    return {
        "totalCount": raw.get("totalCount", 0),
        "returned": len(rows),
        "samples": samples,
    }


# -- sync search (cl / cds / cb) ----------------------------------------


def sanitize_credentials(service: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    """Masked view of cl/cds/cb search results (leaked credential data).

    Passwords are never shown, emails/users/IPs are masked, and the output
    leans on counts and field-coverage stats.
    """
    raw = raw or {}
    rows = raw.get("data") or []
    samples = []
    with_password = 0
    with_ip = 0
    for row in rows:
        if row.get("password"):
            with_password += 1
        if row.get("ip"):
            with_ip += 1
    samples = [mask_credential_record(row) for row in rows[:SAMPLE_SIZE]]
    return {
        "service": service,
        "totalCount": raw.get("totalCount", 0),
        "returned": len(rows),
        "queryCost": raw.get("queryCost"),
        "records_with_password": with_password,
        "records_with_ip": with_ip,
        "samples": samples,
    }


# -- async search results (tt / cdf) ------------------------------------


def sanitize_async_targets(target_map: dict[str, Any] | None) -> dict[str, Any]:
    """Masked view of a resolved async target map (tt/cdf)."""
    out: dict[str, Any] = {}
    for target_name, state in (target_map or {}).items():
        if not isinstance(state, dict):
            out[target_name] = {"error": "unexpected payload"}
            continue
        rows = state.get("data") or []
        samples = []
        for item in rows[:SAMPLE_SIZE]:
            samples.append(
                {
                    "id": redaction.mask_generic(item.get("id"), keep=4),
                    "value": redaction.mask_generic(item.get("value"), keep=4),
                    "createDate": _iso(item.get("createDate")),
                }
            )
        out[target_name] = {
            "totalCount": state.get("totalCount", 0),
            "returned": len(rows),
            "statusCode": state.get("statusCode"),
            "last": state.get("_last", state.get("last")),
            "polls": state.get("_polls", 0),
            "timeout": state.get("_timeout"),
            "samples": samples,
        }
    return out
