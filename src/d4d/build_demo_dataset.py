"""Generate a fully synthetic StealthMole-shaped demo dataset.

수집 데이터(`data/stealthmole/dataset/`)는 마스킹본이라도 커밋 금지다. 하지만
클론만 받은 환경(팀원·심사)에서도 미션 데스크 ThreatIntel landscape가 보여야
하므로, 실제 유출과 무관한 **완전 합성** 데이터셋을 같은 스키마로 생성해
`data/stealthmole/demo/`(git 추적)에 둔다. dataset_loader는 실수집 데이터가
없을 때만 이 demo 런으로 폴백한다.

안전 규칙: 값은 전부 이 파일이 만들어낸 허구다 — 도메인은 example 계열,
IP는 RFC5737 문서용 대역, 이메일/계정/비밀번호는 마스킹 형식 문자열만 사용.

실행 (레포 루트):
    uv run python -m d4d.build_demo_dataset
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import project_root

RUN_NAME = "20260705T000000Z-demo"

# 랜섬웨어 그룹명은 공개적으로 알려진 위협 그룹 명칭(공개 정보)만 사용한다.
GROUPS = ["lockbit3", "ransomhub", "play", "akira", "qilin", "blackbasta"]
SECTORS = ["manufacturing", "healthcare", "education", "finance", "logistics", "public"]
COUNTRIES = ["US", "KR", "JP", "DE", "UK"]
DOMAINS = ["gma***", "nav***", "corp-a***", "corp-b***", "univ-c***"]
STEALERS = ["redline", "lumma", "vidar"]


def _rm_records(n: int = 60) -> list[dict[str, Any]]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "victim": f"demo-victim-{chr(97 + i % 26)}***",
                "attack_group": GROUPS[i % len(GROUPS)],
                "sector": SECTORS[i % len(SECTORS)],
                "country": COUNTRIES[i % len(COUNTRIES)],
                "detected_at": f"2026-0{5 + i % 3}-{(i % 27) + 1:02d}",
                "has_proof_url": i % 3 == 0,
            }
        )
    return rows


def _cl_records(n: int = 40) -> list[dict[str, Any]]:
    return [
        {
            "id": f"demo{i:04d}***",
            "domain": DOMAINS[i % len(DOMAINS)],
            "user": "",
            "email": f"u{i:02d}***@e***.com",
            "password": f"***(len={8 + i % 9})",
            "leaked_date": f"2026-0{4 + i % 3}",
        }
        for i in range(n)
    ]


def _cds_records(n: int = 30) -> list[dict[str, Any]]:
    return [
        {
            "id": f"demo-cds{i:04d}***",
            "host": "https://portal-***.example.com",
            "user": f"user{i:02d}***",
            "password": f"***(len={10 + i % 6})",
            "ip": f"203.0.113.{(i % 200) + 10}",
            "username": f"u***{i % 7}",
            "computername": f"PC-DEMO-***{i % 9}",
            "leaked_date": f"2026-0{4 + i % 3}",
            "stealer": STEALERS[i % len(STEALERS)],
        }
        for i in range(n)
    ]


def _board_records(prefix: str, n: int = 20) -> list[dict[str, Any]]:
    titles = [
        "[demo] 기관 대상 접속 판매 게시글 (합성)",
        "[demo] 크리덴셜 목록 공유 주장 (합성)",
        "[demo] 내부 문서 유출 주장 게시글 (합성)",
        "[demo] VPN 계정 판매 주장 (합성)",
    ]
    return [
        {
            "title": f"{titles[i % len(titles)]} #{i + 1}",
            "author": f"{prefix}-actor***{i % 5}",
            "detected_at": f"2026-0{5 + i % 3}-{(i % 27) + 1:02d}",
            "has_proof_url": i % 4 == 0,
        }
        for i in range(n)
    ]


def _feed(service: str, records: list[dict[str, Any]], total: int) -> dict[str, Any]:
    return {
        "service": service,
        "synthetic": True,
        "stats": {
            "requested": len(records),
            "collected": len(records),
            "pages": 1,
            "totalCount": total,
        },
        "records": records,
    }


def build() -> Path:
    out_dir = project_root() / "data" / "stealthmole" / "demo" / RUN_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    feeds = {
        "rm": _feed("rm", _rm_records(), total=12040),
        "cl": _feed("cl", _cl_records(), total=850000),
        "cds": _feed("cds", _cds_records(), total=41200),
        "gm": _feed("gm", _board_records("gm"), total=3200),
        "lm": _feed("lm", _board_records("lm"), total=58000),
    }
    for service, payload in feeds.items():
        (out_dir / f"{service}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    manifest = {
        "run": RUN_NAME,
        "synthetic": True,
        "note": (
            "완전 합성 demo 데이터셋 — 실제 유출/수집 데이터와 무관. "
            "실수집 데이터셋(data/stealthmole/dataset/, git-ignored)이 없을 때 "
            "dataset_loader가 이 런으로 폴백한다. 재생성: uv run python -m d4d.build_demo_dataset"
        ),
        "feeds": {service: payload["stats"] for service, payload in feeds.items()},
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out_dir


if __name__ == "__main__":
    print(f"synthetic demo dataset written: {build()}")
