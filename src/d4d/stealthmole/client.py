"""StealthMole External API client (standard-library only).

Implements the minimal client shape from
`wiki/StealthMole_API_QUICK_REFERENCE.md`:

    - make_auth_header()   -> fresh JWT per request (never cached)
    - request()            -> low-level GET returning parsed JSON
    - get_quotas()
    - get_targets()        -> async indicator targets (no quota cost)
    - async_search() / async_search_all()
    - poll_search() / wait_until_completed()
    - sync_search()        -> cl / cb / cds
    - monitoring_search()  -> rm / gm / lm
    - get_node()           -> tt / cds detail

The client keeps raw responses separate from sanitized view models: it returns
raw parsed JSON, and callers pass it through `sanitize` before display.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..config import StealthMoleConfig
from . import errors
from .auth import make_auth_header

# Service groups (dt and ub are excluded from this hackathon).
ASYNC_SERVICES = frozenset({"tt", "cdf"})
SYNC_SERVICES = frozenset({"cl", "cb", "cds"})
MONITORING_SERVICES = frozenset({"rm", "gm", "lm"})

# Per-service max limits from the manual.
_ASYNC_MAX_LIMIT = 100
_SYNC_MAX_LIMIT = 50
_MONITORING_MAX_LIMIT = 50


def _clean_query(query: dict[str, Any] | None) -> dict[str, str]:
    """Drop `None` values and render booleans as lowercase strings."""
    if not query:
        return {}
    cleaned: dict[str, str] = {}
    for key, value in query.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        else:
            cleaned[key] = str(value)
    return cleaned


class StealthMoleClient:
    """Authenticated client for the StealthMole hackathon API."""

    def __init__(
        self,
        config: StealthMoleConfig,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        user_agent: str = "d4d-stealthmole-collector/1.0",
        rate_limit_retries: int = 5,
        rate_limit_backoff: float = 2.0,
    ):
        self.config = config
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        # 429 handling: retried separately from the auth/network retry budget,
        # with exponential backoff, because rate limits clear on their own.
        self.rate_limit_retries = rate_limit_retries
        self.rate_limit_backoff = rate_limit_backoff

    # -- low level -------------------------------------------------------

    def _auth_header(self) -> str:
        """A fresh Bearer token for exactly one request. Never cached."""
        return make_auth_header(self.config.access_key, self.config.secret_key)

    def request(self, path: str, query: dict[str, Any] | None = None) -> Any:
        """Perform a GET request and return parsed JSON.

        Raises a typed `StealthMoleError` subclass on any non-2xx status.
        A reused-token 401 or transient network error is retried once with a
        freshly generated JWT.
        """
        if not path.startswith("/"):
            path = "/" + path
        qs = urllib.parse.urlencode(_clean_query(query))
        url = f"{self.config.base_url}{path}"
        if qs:
            url = f"{url}?{qs}"

        last_exc: Exception | None = None
        rate_limit_hits = 0
        attempt = 0
        while attempt < self.max_retries:
            attempt += 1
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": self._auth_header(),  # new token each attempt
                    "Accept": "application/json",
                    "User-Agent": self.user_agent,
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read()
                    return self._parse_body(resp.getcode(), body)
            except urllib.error.HTTPError as exc:
                body = exc.read()
                status = exc.code
                detail = self._extract_detail(body)
                # A 401 can be a reused/expired token; retry once with a new JWT.
                if status == 401 and attempt < self.max_retries:
                    last_exc = errors.from_response(status, detail)
                    continue
                # 429: back off and retry without consuming the main attempt budget.
                if status == 429 and rate_limit_hits < self.rate_limit_retries:
                    rate_limit_hits += 1
                    time.sleep(self.rate_limit_backoff * rate_limit_hits)
                    attempt -= 1
                    continue
                raise errors.from_response(status, detail) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * attempt)
                    continue
                raise errors.StealthMoleError(f"Network error calling {path}: {exc}") from exc

        # Exhausted retries.
        if isinstance(last_exc, errors.StealthMoleError):
            raise last_exc
        raise errors.StealthMoleError(f"Request to {path} failed after {self.max_retries} attempts")

    @staticmethod
    def _parse_body(status: int, body: bytes) -> Any:
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            # Non-JSON payload (e.g. an export file). Return raw text.
            return {"_raw": body.decode("utf-8", errors="replace"), "_status": status}

    @staticmethod
    def _extract_detail(body: bytes) -> str | None:
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return body.decode("utf-8", errors="replace")[:200] or None
        if isinstance(parsed, dict):
            return parsed.get("detail") or parsed.get("message")
        return None

    # -- management ------------------------------------------------------

    def get_quotas(self) -> dict[str, Any]:
        """GET /user/quotas — service usage/allowance. Not quota-charged."""
        return self.request("/user/quotas")

    # -- async search (tt, cdf) -----------------------------------------

    def get_targets(self, service: str, indicator: str) -> dict[str, Any]:
        """GET /{service}/search/{indicator}/targets — not quota-charged."""
        self._require(service, ASYNC_SERVICES, "async target lookup")
        return self.request(f"/{service}/search/{indicator}/targets")

    def async_search(
        self,
        service: str,
        indicator: str,
        targets: str,
        text: str,
        *,
        limit: int = 20,
        order_type: str | None = None,
        order: str | None = None,
        wait: bool | None = None,
    ) -> dict[str, Any]:
        """GET /{service}/search/{indicator}/target — search specific targets."""
        self._require(service, ASYNC_SERVICES, "async search")
        query = {
            "targets": targets,
            "text": text,
            "limit": min(limit, _ASYNC_MAX_LIMIT),
            "orderType": order_type,
            "order": order,
            "wait": wait,
        }
        return self.request(f"/{service}/search/{indicator}/target", query)

    def async_search_all(
        self,
        service: str,
        indicator: str,
        text: str,
        *,
        limit: int = 20,
        wait: bool | None = None,
    ) -> dict[str, Any]:
        """GET /{service}/search/{indicator}/target/all — default targets."""
        self._require(service, ASYNC_SERVICES, "async search")
        query = {"text": text, "limit": min(limit, _ASYNC_MAX_LIMIT), "wait": wait}
        return self.request(f"/{service}/search/{indicator}/target/all", query)

    def poll_search(
        self,
        service: str,
        search_id: str,
        *,
        limit: int = 20,
        cursor: int | None = None,
    ) -> dict[str, Any]:
        """GET /{service}/search/{id} — polling + cursor paging."""
        self._require(service, ASYNC_SERVICES, "async polling")
        query = {"limit": min(limit, _ASYNC_MAX_LIMIT), "cursor": cursor}
        return self.request(f"/{service}/search/{search_id}", query)

    def wait_until_completed(
        self,
        service: str,
        target_map: dict[str, Any],
        *,
        limit: int = 20,
        max_polls: int = 4,
        interval: float = 2.0,
    ) -> dict[str, Any]:
        """Resolve an async target map into completed results.

        Takes the map returned by `async_search`/`async_search_all` and polls
        each still-running target (statusCode 202 / last=false) by its
        `id`/`cid`, up to `max_polls` times. Targets that time out (408) are
        recorded rather than raised, so one slow target does not sink the rest.
        """
        completed: dict[str, Any] = {}
        for target_name, state in (target_map or {}).items():
            if not isinstance(state, dict):
                completed[target_name] = {"error": "unexpected target payload"}
                continue

            merged = dict(state)
            data = list(state.get("data") or [])
            search_id = state.get("id") or state.get("cid")
            last = bool(state.get("last", True))
            polls = 0
            while not last and search_id and polls < max_polls:
                time.sleep(interval)
                polls += 1
                try:
                    page = self.poll_search(service, search_id, limit=limit)
                except errors.SearchTimeout as exc:
                    merged["_timeout"] = str(exc)
                    break
                except errors.StealthMoleError as exc:
                    merged["_poll_error"] = str(exc)
                    break
                data.extend(page.get("data") or [])
                last = bool(page.get("last", True))
                search_id = page.get("id") or page.get("cid") or search_id
                merged.update({k: v for k, v in page.items() if k != "data"})

            merged["data"] = data
            merged["_polls"] = polls
            merged["_last"] = last
            completed[target_name] = merged
        return completed

    # -- sync search (cl, cb, cds) --------------------------------------

    def sync_search(
        self,
        service: str,
        query: str,
        *,
        limit: int = 20,
        cursor: int = 0,
        order_type: str | None = None,
        order: str | None = None,
        include_gps: bool | None = None,
    ) -> dict[str, Any]:
        """GET /{cl,cb,cds}/search — one charged request, max limit 50."""
        self._require(service, SYNC_SERVICES, "sync search")
        params: dict[str, Any] = {
            "query": query,
            "limit": min(max(limit, 1), _SYNC_MAX_LIMIT),
            "cursor": cursor,
            "orderType": order_type,
            "order": order,
        }
        if service == "cds" and include_gps is not None:
            params["includeGps"] = include_gps
        return self.request(f"/{service}/search", params)

    def get_node(self, service: str, node_id: str, **extra: Any) -> dict[str, Any]:
        """GET /{tt,cds}/node — detail lookup."""
        if service not in {"tt", "cds"}:
            raise ValueError(f"node detail is only supported for tt/cds, got {service!r}")
        params = {"id": node_id, **extra}
        return self.request(f"/{service}/node", params)

    # -- monitoring (rm, gm, lm) ----------------------------------------

    def monitoring_search(
        self,
        service: str,
        query: str = "",
        *,
        limit: int = 10,
        cursor: int = 0,
        order_type: str | None = None,
        order: str | None = None,
        start: int | None = None,
        end: int | None = None,
    ) -> dict[str, Any]:
        """GET /{rm,gm,lm}/search — empty query returns the full feed."""
        self._require(service, MONITORING_SERVICES, "monitoring search")
        params = {
            "query": query,
            "limit": min(limit, _MONITORING_MAX_LIMIT),
            "cursor": cursor,
            "orderType": order_type,
            "order": order,
            "start": start,
            "end": end,
        }
        return self.request(f"/{service}/search", params)

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _require(service: str, allowed: frozenset[str], action: str) -> None:
        if service not in allowed:
            raise ValueError(
                f"service {service!r} is not valid for {action}; "
                f"expected one of {sorted(allowed)}"
            )
