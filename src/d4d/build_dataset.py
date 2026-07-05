"""Bulk StealthMole dataset builder.

The `collect_stealthmole` collector pulls a *small* smoke sample (a few records
per feed, 5 masked samples in each view). This builder instead paginates each
feed with the cursor API and masks **every** record, producing a larger
demo-safe dataset (1000+ masked records) for enrichment / GraphRAG work.

Quota note: the hackathon API charges **1 quota unit per request**, not per
record. A 50-record page therefore costs 1 unit, so 1000+ records across feeds
costs only a few dozen units.

Safety:
    - Only masked records are written (same maskers as the demo sanitizer).
    - Raw responses are never persisted by this builder.
    - Output lives under data/stealthmole/dataset/<run_id>/ which is git-ignored.

Usage (from repo root, credentials in .env):

    python -m d4d.build_dataset                       # defaults: ~2200 records
    python -m d4d.build_dataset --rm 800 --lm 800 --cl 400 --cds 400 --gm 400
    python -m d4d.build_dataset --query "domain:gmail.com"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Gentle pacing between requests to stay under the API rate limit (HTTP 429).
_THROTTLE_SECONDS = 2.5

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from d4d.config import load_stealthmole_config  # noqa: E402
from d4d.stealthmole import errors, sanitize  # noqa: E402
from d4d.stealthmole.client import StealthMoleClient  # noqa: E402

_MONITORING_PAGE = 50  # per-request cap for rm/gm/lm
_SYNC_PAGE = 50        # per-request cap for cl/cds/cb


def _paginate(
    fetch_page: Callable[[int], dict[str, Any]],
    mask_record: Callable[[dict[str, Any]], dict[str, Any]],
    target: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pull pages by cursor until `target` masked records or the feed ends.

    Returns (masked_records, stats). Deduplicates by raw `id` when present so a
    feed that returns overlapping pages does not inflate the count.
    """
    masked: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_count = 0
    pages = 0
    cursor = 0
    while len(masked) < target:
        time.sleep(_THROTTLE_SECONDS)
        page = fetch_page(cursor)
        rows = page.get("data") or []
        total_count = page.get("totalCount", total_count)
        pages += 1
        if not rows:
            break
        for row in rows:
            key = str(row.get("id") or row.get("_id") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            masked.append(mask_record(row))
            if len(masked) >= target:
                break
        if len(rows) < page_size:
            break  # last page
        cursor += page_size
    return masked, {"requested": target, "collected": len(masked), "pages": pages, "totalCount": total_count}


def build(client: StealthMoleClient, targets: dict[str, int], query: str) -> dict[str, Any]:
    feeds: dict[str, Any] = {}

    def monitoring(service: str, masker: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        n = targets.get(service, 0)
        if n <= 0:
            return
        records, stats = _paginate(
            lambda cur: client.monitoring_search(service, limit=_MONITORING_PAGE, cursor=cur),
            masker,
            n,
            _MONITORING_PAGE,
        )
        feeds[service] = {"stats": stats, "records": records}
        print(f"  [ ok ] {service:4} {stats['collected']:>5} records ({stats['pages']} pages, feed total {stats['totalCount']})")

    def credential(service: str) -> None:
        n = targets.get(service, 0)
        if n <= 0:
            return
        records, stats = _paginate(
            lambda cur: client.sync_search(service, query, limit=_SYNC_PAGE, cursor=cur),
            sanitize.mask_credential_record,
            n,
            _SYNC_PAGE,
        )
        feeds[service] = {"stats": stats, "records": records, "query": query}
        print(f"  [ ok ] {service:4} {stats['collected']:>5} records ({stats['pages']} pages, feed total {stats['totalCount']})")

    for svc, masker in (
        ("rm", sanitize.mask_ransomware_record),
        ("gm", sanitize.mask_monitoring_record),
        ("lm", sanitize.mask_monitoring_record),
    ):
        try:
            monitoring(svc, masker)
        except errors.StealthMoleError as exc:
            feeds[svc] = {"error": str(exc)}
            print(f"  [err ] {svc:4} {exc}")

    for svc in ("cl", "cds"):
        try:
            credential(svc)
        except errors.StealthMoleError as exc:
            feeds[svc] = {"error": str(exc)}
            print(f"  [err ] {svc:4} {exc}")

    return feeds


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a larger masked StealthMole dataset via pagination.")
    parser.add_argument("--rm", type=int, default=600)
    parser.add_argument("--gm", type=int, default=400)
    parser.add_argument("--lm", type=int, default=500)
    parser.add_argument("--cl", type=int, default=400)
    parser.add_argument("--cds", type=int, default=400)
    parser.add_argument("--query", default="domain:gmail.com", help="credential search query for cl/cds")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    targets = {"rm": args.rm, "gm": args.gm, "lm": args.lm, "cl": args.cl, "cds": args.cds}
    out_root = Path(args.out).resolve() if args.out else Path(__file__).resolve().parents[2] / "data" / "stealthmole"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ds_dir = out_root / "dataset" / run_id

    config = load_stealthmole_config()
    print(f"[config] {json.dumps(config.redacted())}")
    client = StealthMoleClient(config)

    quota_before = {k: v.get("used", 0) for k, v in client.get_quotas().items()}

    print(f"[build] target ~{sum(targets.values())} masked records -> {ds_dir}")
    feeds = build(client, targets, args.query)

    quota_after = {k: v.get("used", 0) for k, v in client.get_quotas().items()}
    quota_spent = {k: quota_after[k] - quota_before.get(k, 0) for k in quota_after if quota_after[k] - quota_before.get(k, 0) > 0}

    total_records = sum(len(f.get("records", [])) for f in feeds.values())
    for service, feed in feeds.items():
        if "records" in feed:
            _write_json(ds_dir / f"{service}.json", {"service": service, **feed})

    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": total_records,
        "query": args.query,
        "feeds": {s: f.get("stats", {"error": f.get("error")}) for s, f in feeds.items()},
        "quota_spent": quota_spent,
        "masking": "all records masked via d4d.stealthmole.sanitize (no raw values)",
    }
    _write_json(ds_dir / "manifest.json", manifest)

    print(f"\n[done] {total_records} masked records across {len([f for f in feeds.values() if 'records' in f])} feeds")
    print(f"       quota spent: {quota_spent} (1 unit/request)")
    print(f"       dataset -> {ds_dir}")
    return 0 if total_records >= 1000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
