"""StealthMole live-data collector.

Pulls a small, safe sample from the StealthMole hackathon API to confirm the
integration works and to seed enrichment fixtures for the D4D readiness
simulator.

Usage (from the repo root):

    python -m d4d.collect_stealthmole --profile safe
    python -m d4d.collect_stealthmole --profile full --sync-query "domain:example.com"

or, if `src` is not on PYTHONPATH:

    python src/d4d/collect_stealthmole.py --profile safe

Profiles:
    safe  quotas + monitoring feeds (rm/gm/lm) + async target lists.
          Low quota cost, no leaked-credential payloads.
    full  safe + one sync credential search (cl/cds) + one async tt search.
          Charges quota and may return sensitive data (masked on output).

Outputs (per run, under data/stealthmole/):
    raw/<run_id>/*.json         unmasked responses  (GIT-IGNORED — sensitive)
    sanitized/<run_id>/*.json   masked, demo-safe view models
    sanitized/<run_id>/summary.json  run summary
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Allow `python src/d4d/collect_stealthmole.py` by putting `src` on the path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from d4d.config import load_stealthmole_config  # noqa: E402
from d4d.stealthmole import errors, sanitize  # noqa: E402
from d4d.stealthmole.client import StealthMoleClient  # noqa: E402


@dataclass
class StepResult:
    """Outcome of one collection step."""

    name: str
    status: str  # "ok" | "error" | "skip"
    raw: Any = None
    view: Any = None
    note: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


def _run_step(name: str, fn: Callable[[], tuple[Any, Any, dict[str, Any]]]) -> StepResult:
    """Execute one step, converting known API errors into a recorded status."""
    try:
        raw, view, summary = fn()
        return StepResult(name=name, status="ok", raw=raw, view=view, summary=summary)
    except errors.QuotaExceeded as exc:
        return StepResult(name=name, status="skip", note=f"quota exceeded: {exc.detail or exc}")
    except errors.PermissionDenied as exc:
        return StepResult(name=name, status="skip", note=f"no permission: {exc.detail or exc}")
    except errors.StealthMoleError as exc:
        return StepResult(name=name, status="error", note=str(exc))
    except Exception as exc:  # noqa: BLE001 - collector should never hard-crash
        return StepResult(name=name, status="error", note=f"{type(exc).__name__}: {exc}")


# -- individual collection steps ---------------------------------------


def step_quotas(client: StealthMoleClient) -> tuple[Any, Any, dict[str, Any]]:
    raw = client.get_quotas()
    view = sanitize.sanitize_quotas(raw)
    return raw, view, {"services": len(view["services"]), "remaining": view["total_remaining"]}


def step_ransomware(client: StealthMoleClient, limit: int) -> tuple[Any, Any, dict[str, Any]]:
    raw = client.monitoring_search("rm", limit=limit)
    view = sanitize.sanitize_ransomware(raw)
    return raw, view, {"totalCount": view["totalCount"], "returned": view["returned"]}


def step_monitoring(client: StealthMoleClient, service: str, limit: int) -> tuple[Any, Any, dict[str, Any]]:
    raw = client.monitoring_search(service, limit=limit)
    view = sanitize.sanitize_monitoring(raw)
    return raw, view, {"totalCount": view["totalCount"], "returned": view["returned"]}


def step_async_targets(client: StealthMoleClient, service: str, indicator: str) -> tuple[Any, Any, dict[str, Any]]:
    raw = client.get_targets(service, indicator)
    view = sanitize.sanitize_targets(raw)
    return raw, view, {"targets": view["targets"]}


def step_sync_search(client: StealthMoleClient, service: str, query: str, limit: int) -> tuple[Any, Any, dict[str, Any]]:
    raw = client.sync_search(service, query, limit=limit)
    view = sanitize.sanitize_credentials(service, raw)
    return raw, view, {
        "totalCount": view["totalCount"],
        "returned": view["returned"],
        "with_password": view["records_with_password"],
    }


def step_async_search(
    client: StealthMoleClient, service: str, indicator: str, targets: str, text: str, limit: int
) -> tuple[Any, Any, dict[str, Any]]:
    initial = client.async_search(service, indicator, targets, text, limit=limit, wait=True)
    resolved = client.wait_until_completed(service, initial, limit=limit)
    view = sanitize.sanitize_async_targets(resolved)
    returned = sum(t.get("returned", 0) for t in view.values() if isinstance(t, dict))
    return resolved, view, {"targets": list(view.keys()), "returned": returned}


# -- orchestration ------------------------------------------------------


def collect(profile: str, limit: int, sync_query: str) -> list[StepResult]:
    config = load_stealthmole_config()
    print(f"[config] {json.dumps(config.redacted())}")
    client = StealthMoleClient(config)

    steps: list[StepResult] = []

    # Always start with quotas (never charged) — this is the smoke test.
    steps.append(_run_step("quotas", lambda: step_quotas(client)))

    # Monitoring feeds: public threat data, low quota cost.
    steps.append(_run_step("ransomware_rm", lambda: step_ransomware(client, min(limit, 10))))
    steps.append(_run_step("government_gm", lambda: step_monitoring(client, "gm", min(limit, 10))))
    steps.append(_run_step("leaked_lm", lambda: step_monitoring(client, "lm", min(limit, 10))))

    # Async target lists: not charged, confirms tt/cdf indicator access.
    steps.append(_run_step("tt_targets_domain", lambda: step_async_targets(client, "tt", "domain")))
    steps.append(_run_step("tt_targets_ip", lambda: step_async_targets(client, "tt", "ip")))
    steps.append(_run_step("cdf_targets_ip", lambda: step_async_targets(client, "cdf", "ip")))

    if profile == "full":
        # Charged steps that may return sensitive data (masked on output).
        steps.append(_run_step("cl_search", lambda: step_sync_search(client, "cl", sync_query, min(limit, 10))))
        steps.append(_run_step("cds_search", lambda: step_sync_search(client, "cds", sync_query, min(limit, 10))))
        steps.append(
            _run_step(
                "tt_search_domain",
                lambda: step_async_search(client, "tt", "domain", "domain", sync_query.split(":")[-1], min(limit, 10)),
            )
        )

    return steps


# -- persistence + reporting -------------------------------------------


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def persist(steps: list[StepResult], out_dir: Path, run_id: str, save_raw: bool) -> dict[str, Any]:
    raw_dir = out_dir / "raw" / run_id
    san_dir = out_dir / "sanitized" / run_id

    summary_steps = []
    for step in steps:
        if step.status == "ok":
            if save_raw and step.raw is not None:
                _write_json(raw_dir / f"{step.name}.json", step.raw)
            if step.view is not None:
                _write_json(san_dir / f"{step.name}.json", step.view)
        summary_steps.append(
            {"name": step.name, "status": step.status, "note": step.note, "summary": step.summary}
        )

    summary = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_saved": save_raw,
        "steps": summary_steps,
    }
    _write_json(san_dir / "summary.json", summary)
    return summary


def _print_report(steps: list[StepResult], summary: dict[str, Any], out_dir: Path, run_id: str) -> None:
    print("\n=== StealthMole collection report ===")
    for step in steps:
        marker = {"ok": "[ ok ]", "skip": "[skip]", "error": "[err ]"}.get(step.status, "[????]")
        extra = json.dumps(step.summary, ensure_ascii=False) if step.summary else step.note
        print(f"  {marker} {step.name:22} {extra}")
    counts = {"ok": 0, "skip": 0, "error": 0}
    for step in steps:
        counts[step.status] = counts.get(step.status, 0) + 1
    print(
        f"\n  totals: {counts['ok']} ok, {counts['skip']} skipped, {counts['error']} error"
    )
    print(f"  sanitized -> {out_dir / 'sanitized' / run_id}")
    if summary["raw_saved"]:
        print(f"  raw (git-ignored) -> {out_dir / 'raw' / run_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect a sample of live StealthMole data.")
    parser.add_argument("--profile", choices=["safe", "full"], default="safe")
    parser.add_argument("--limit", type=int, default=5, help="max records per search (capped per service)")
    parser.add_argument("--sync-query", default="domain:example.com", help="query for full-profile credential search")
    parser.add_argument("--out", default=None, help="output directory (default: <repo>/data/stealthmole)")
    parser.add_argument("--no-raw", action="store_true", help="do not write raw (unmasked) responses to disk")
    args = parser.parse_args(argv)

    if args.out:
        out_dir = Path(args.out).resolve()
    else:
        out_dir = Path(__file__).resolve().parents[2] / "data" / "stealthmole"

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        steps = collect(args.profile, args.limit, args.sync_query)
    except RuntimeError as exc:
        print(f"[fatal] {exc}", file=sys.stderr)
        return 2

    summary = persist(steps, out_dir, run_id, save_raw=not args.no_raw)
    _print_report(steps, summary, out_dir, run_id)

    # Non-zero exit only if every step failed (a hard connectivity/auth problem).
    if all(s.status == "error" for s in steps):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
