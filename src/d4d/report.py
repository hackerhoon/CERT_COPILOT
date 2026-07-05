"""Render collected StealthMole intel + built scenarios into human views.

Produces two artifacts from a sanitized collection run:

    - a Markdown report  (git/PR friendly)
    - a self-contained HTML report  (open in a browser; good for the demo)

and writes each built scenario as JSON. Everything consumes masked view
models only, so the output is safe to read and screen-share.

Usage (from repo root):

    python -m d4d.report                 # latest run
    python -m d4d.report --run 20260704T041030Z
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from d4d.scenario import Scenario, build_scenarios  # noqa: E402
from d4d.stealthmole import loader  # noqa: E402


# ======================================================================
# Markdown
# ======================================================================


def _mdcell(c: Any) -> str:
    """Escape a Markdown table cell so `|`/newlines don't break the columns."""
    return str(c).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_데이터 없음_\n"
    out = [
        "| " + " | ".join(_mdcell(h) for h in headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(_mdcell(c) for c in row) + " |")
    return "\n".join(out) + "\n"


def render_markdown(run_id: str, run: dict[str, Any], scenarios: list[Scenario]) -> str:
    lines: list[str] = []
    add = lines.append

    add(f"# StealthMole 인텔 리포트 · {run_id}")
    add("")
    add(f"> 생성: {datetime.now(timezone.utc).isoformat()}  ")
    add("> 데이터는 모두 마스킹된 view model이며, 조직·자산·계정은 합성값입니다.")
    add("")

    # -- Quota --
    quotas = run.get("quotas") or {}
    services = quotas.get("services") or {}
    if services:
        add("## 1. API Quota")
        add("")
        rows = [
            [svc, _num(info.get("allowed")), _num(info.get("used")), _num(info.get("remaining"))]
            for svc, info in services.items()
        ]
        add(_md_table(["서비스", "허용", "사용", "잔여"], rows))
        add(f"총 잔여 쿼리: **{_num(quotas.get('total_remaining'))}**")
        add("")

    # -- Threat feeds --
    add("## 2. 위협 인텔 피드")
    add("")
    rm = run.get("ransomware_rm") or {}
    if rm:
        add(f"### 2.1 랜섬웨어 모니터링 (rm) — 공개 피해 {_num(rm.get('totalCount'))}건")
        add("")
        add("상위 섹터: " + (", ".join(f"{k} ({v})" for k, v in (rm.get("top_sectors") or {}).items()) or "-"))
        add("")
        add("상위 국가: " + (", ".join(f"{k} ({v})" for k, v in (rm.get("top_countries") or {}).items()) or "-"))
        add("")
        rows = [
            [s.get("attack_group", "-"), s.get("sector", "-"), s.get("country", "-"), s.get("detected_at", "-")]
            for s in rm.get("samples", [])
        ]
        add(_md_table(["공격 그룹", "섹터", "국가", "탐지 시각"], rows))
        add("")

    for key, label in (("leaked_lm", "유출 모니터링 (lm)"), ("government_gm", "정부 모니터링 (gm)")):
        view = run.get(key) or {}
        if view:
            add(f"### {label} — 관측 {_num(view.get('totalCount'))}건")
            add("")
            rows = [[_clip(s.get("title")), s.get("author", "-"), s.get("detected_at", "-")] for s in view.get("samples", [])]
            add(_md_table(["제목(요약)", "작성자(마스킹)", "탐지 시각"], rows))
            add("")

    # -- Credentials --
    cred_views = [(k, run[k]) for k in ("cl_search", "cds_search") if run.get(k)]
    if cred_views:
        add("## 3. 유출 크리덴셜 (마스킹)")
        add("")
        for key, view in cred_views:
            add(
                f"### {view.get('service', key)} — 관측 {_num(view.get('totalCount'))}건 "
                f"(표본 {view.get('returned', 0)}, 비밀번호 포함 {view.get('records_with_password', 0)})"
            )
            add("")
            rows = [
                [
                    s.get("id", "-"),
                    s.get("host", s.get("domain", "-")),
                    s.get("email", s.get("user", "-")),
                    s.get("password", "-"),
                    s.get("ip", "-"),
                ]
                for s in view.get("samples", [])
            ]
            add(_md_table(["id", "host/domain", "email/user", "password", "ip"], rows))
            add("")

    # -- Scenarios --
    add("## 4. 생성된 방어 훈련 시나리오")
    add("")
    add(f"수집 데이터에서 **{len(scenarios)}개** 시나리오 생성.")
    add("")
    for sc in scenarios:
        add(f"### [{sc.id}] {sc.title}  ·  난이도: {sc.difficulty}")
        add("")
        add(f"**목표**: {sc.objective}")
        add("")
        add(f"**위협 맥락**: {sc.threat_context}")
        add("")
        add("**인젝트 타임라인**")
        add("")
        rows = [
            [f"T+{inj.offset_min}", inj.source_system, inj.visible_clue, ", ".join(inj.evidence_ids) or "-"]
            for inj in sc.injects
        ]
        add(_md_table(["시각", "출처 시스템", "관측 단서", "근거"], rows))
        add("")
        add("**기대 대응(방어)**")
        add("")
        for a in sc.expected_actions:
            flag = " _(승인 필요)_" if a.approval_required else ""
            add(f"{a.order}. {a.action}{flag} — {a.rationale}")
        add("")
        add("**AAR 채점 기준**")
        add("")
        for r in sc.rubric:
            add(f"- {r}")
        add("")
        add("**근거(evidence)**")
        add("")
        for ev in sc.evidence:
            add(f"- `{ev.id}` ({ev.source_type}, 신뢰도 {ev.confidence}): {ev.claim}")
            if ev.caveat:
                add(f"  - 주의: {ev.caveat}")
        add("")
        add(f"> {sc.safety_note}")
        add("")

    return "\n".join(lines)


# ======================================================================
# HTML
# ======================================================================

_CSS = """
:root{--bg:#0f1620;--card:#18212e;--ink:#e6edf3;--muted:#9fb0c3;--line:#2a3646;
--accent:#5ab0ff;--warn:#ffb454;--ok:#5ad19a;--pill:#243247}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:19px;margin:34px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:16px;margin:20px 0 8px;color:var(--accent)}
.sub{color:var(--muted);font-size:13px;margin-bottom:8px}
table{border-collapse:collapse;width:100%;margin:8px 0 4px;font-size:13.5px}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--pill);color:var(--muted);font-weight:600}
td code,code{background:#0c1118;padding:1px 5px;border-radius:4px;font-size:12.5px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:14px 0}
.pill{display:inline-block;background:var(--pill);color:var(--muted);border-radius:999px;padding:2px 10px;font-size:12px;margin-left:6px}
.pill.diff{background:#2a2140;color:#c9b6ff}
.tl{list-style:none;padding:0;margin:8px 0}
.tl li{border-left:2px solid var(--accent);padding:2px 0 12px 14px;margin-left:6px;position:relative}
.tl li::before{content:"";position:absolute;left:-6px;top:5px;width:9px;height:9px;border-radius:50%;background:var(--accent)}
.tl .t{color:var(--warn);font-weight:600;margin-right:8px}
.tl .src{color:var(--muted);font-size:12.5px}
.act{margin:4px 0}.approval{color:var(--warn);font-size:12px}
.ev{font-size:13px;color:var(--muted);margin:4px 0}
.note{background:#1c2432;border:1px dashed var(--line);border-radius:8px;padding:10px 12px;color:var(--muted);font-size:13px;margin-top:10px}
.kpi{display:inline-block;background:var(--pill);border-radius:8px;padding:8px 12px;margin:4px 8px 4px 0}
.kpi b{color:var(--ok);font-size:18px;display:block}
.mask{color:var(--muted)}
"""


def _h(v: Any) -> str:
    return escape(str(v if v is not None else "-"))


def _html_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return '<p class="sub">데이터 없음</p>'
    head = "".join(f"<th>{_h(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{_h(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(run_id: str, run: dict[str, Any], scenarios: list[Scenario]) -> str:
    p: list[str] = []
    add = p.append

    add(f"<h1>StealthMole 인텔 리포트</h1><div class='sub'>run <code>{_h(run_id)}</code> · "
        f"생성 {_h(datetime.now(timezone.utc).isoformat())} · 마스킹된 view model / 합성 조직 컨텍스트</div>")

    # KPIs + quota
    quotas = run.get("quotas") or {}
    services = quotas.get("services") or {}
    if services:
        add("<h2>1. API Quota</h2>")
        add(f"<div class='kpi'>총 잔여<b>{_h(_num(quotas.get('total_remaining')))}</b></div>")
        add(f"<div class='kpi'>서비스<b>{len(services)}</b></div>")
        add(f"<div class='kpi'>시나리오<b>{len(scenarios)}</b></div>")
        rows = [[s, _num(i.get("allowed")), _num(i.get("used")), _num(i.get("remaining"))] for s, i in services.items()]
        add(_html_table(["서비스", "허용", "사용", "잔여"], rows))

    # Threat feeds
    add("<h2>2. 위협 인텔 피드</h2>")
    rm = run.get("ransomware_rm") or {}
    if rm:
        add(f"<h3>랜섬웨어 모니터링 — 공개 피해 {_h(_num(rm.get('totalCount')))}건</h3>")
        add("<div class='sub'>상위 섹터: " + _h(", ".join(f"{k} ({v})" for k, v in (rm.get("top_sectors") or {}).items()) or "-") + "</div>")
        rows = [[s.get("attack_group"), s.get("sector"), s.get("country"), s.get("detected_at")] for s in rm.get("samples", [])]
        add(_html_table(["공격 그룹", "섹터", "국가", "탐지 시각"], rows))
    for key, label in (("leaked_lm", "유출 모니터링 (lm)"), ("government_gm", "정부 모니터링 (gm)")):
        view = run.get(key) or {}
        if view:
            add(f"<h3>{_h(label)} — 관측 {_h(_num(view.get('totalCount')))}건</h3>")
            rows = [[_clip(s.get("title")), s.get("author"), s.get("detected_at")] for s in view.get("samples", [])]
            add(_html_table(["제목(요약)", "작성자(마스킹)", "탐지 시각"], rows))

    # Credentials
    cred_views = [(k, run[k]) for k in ("cl_search", "cds_search") if run.get(k)]
    if cred_views:
        add("<h2>3. 유출 크리덴셜 <span class='mask'>(마스킹)</span></h2>")
        for key, view in cred_views:
            add(f"<h3>{_h(view.get('service', key))} — 관측 {_h(_num(view.get('totalCount')))}건 · "
                f"표본 {_h(view.get('returned', 0))} · 비밀번호 포함 {_h(view.get('records_with_password', 0))}</h3>")
            rows = [[s.get("id"), s.get("host", s.get("domain")), s.get("email", s.get("user")), s.get("password"), s.get("ip")]
                    for s in view.get("samples", [])]
            add(_html_table(["id", "host/domain", "email/user", "password", "ip"], rows))

    # Scenarios
    add("<h2>4. 생성된 방어 훈련 시나리오</h2>")
    add(f"<p class='sub'>수집 데이터에서 {len(scenarios)}개 시나리오를 구성했습니다.</p>")
    for sc in scenarios:
        add("<div class='card'>")
        add(f"<h3 style='color:#e6edf3'>[{_h(sc.id)}] {_h(sc.title)}"
            f"<span class='pill diff'>{_h(sc.difficulty)}</span></h3>")
        add(f"<div class='ev'><b>목표</b> {_h(sc.objective)}</div>")
        add(f"<div class='ev'><b>위협 맥락</b> {_h(sc.threat_context)}</div>")
        add("<b>인젝트 타임라인</b><ul class='tl'>")
        for inj in sc.injects:
            ev = (" · 근거 " + ", ".join(inj.evidence_ids)) if inj.evidence_ids else ""
            add(f"<li><span class='t'>T+{_h(inj.offset_min)}</span>"
                f"<span class='src'>{_h(inj.source_system)}{_h(ev)}</span><br>{_h(inj.visible_clue)}"
                f"<br><span class='sub'>숨은 사실: {_h(inj.hidden_truth)}</span></li>")
        add("</ul>")
        add("<b>기대 대응(방어)</b>")
        for a in sc.expected_actions:
            flag = " <span class='approval'>· 승인 필요</span>" if a.approval_required else ""
            add(f"<div class='act'>{_h(a.order)}. {_h(a.action)}{flag}<br><span class='sub'>{_h(a.rationale)}</span></div>")
        add("<b>AAR 채점 기준</b><ul>")
        for r in sc.rubric:
            add(f"<li>{_h(r)}</li>")
        add("</ul>")
        add("<b>근거(evidence)</b>")
        for ev in sc.evidence:
            add(f"<div class='ev'><code>{_h(ev.id)}</code> ({_h(ev.source_type)}, 신뢰도 {_h(ev.confidence)}): {_h(ev.claim)}"
                + (f"<br><span class='sub'>주의: {_h(ev.caveat)}</span>" if ev.caveat else "") + "</div>")
        add(f"<div class='note'>{_h(sc.safety_note)}</div>")
        add("</div>")

    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>StealthMole 인텔 리포트 · {_h(run_id)}</title><style>{_CSS}</style></head>"
        f"<body><div class='wrap'>{''.join(p)}</div></body></html>"
    )


# ======================================================================
# shared + CLI
# ======================================================================


def _num(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "-" if n is None else str(n)


def _clip(text: Any, length: int = 60) -> str:
    if text is None:
        return "-"
    s = str(text)
    return s if len(s) <= length else s[: length - 1] + "…"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render StealthMole intel + scenarios to HTML/Markdown.")
    parser.add_argument("--run", default=None, help="run id under data/stealthmole/sanitized (default: latest)")
    parser.add_argument("--out", default=None, help="output base dir (default: <repo>/data/stealthmole)")
    args = parser.parse_args(argv)

    sanitized_dir = loader.default_sanitized_dir()
    if args.run:
        run_dir = sanitized_dir / args.run
        if not run_dir.is_dir():
            print(f"[fatal] run not found: {run_dir}", file=sys.stderr)
            return 2
        run_id, run = args.run, loader.load_run(run_dir)
    else:
        run_id, run = loader.load_latest_run(sanitized_dir)
        if run_id is None:
            print("[fatal] no collection runs found. Run the collector first.", file=sys.stderr)
            return 2

    scenarios = build_scenarios(run)

    out_base = Path(args.out).resolve() if args.out else Path(__file__).resolve().parents[2] / "data" / "stealthmole"
    html_path = out_base / "reports" / f"{run_id}.html"
    md_path = out_base / "reports" / f"{run_id}.md"
    _write(html_path, render_html(run_id, run, scenarios))
    _write(md_path, render_markdown(run_id, run, scenarios))
    for sc in scenarios:
        _write(out_base / "scenarios" / f"{sc.id}.json", json.dumps(sc.to_dict(), ensure_ascii=False, indent=2))

    print(f"[report] run {run_id}")
    print(f"  scenarios: {len(scenarios)}")
    for sc in scenarios:
        print(f"    - [{sc.id}] {sc.title} ({sc.difficulty}), injects={len(sc.injects)}, actions={len(sc.expected_actions)}")
    print(f"  html -> {html_path}")
    print(f"  md   -> {md_path}")
    print(f"  scenarios -> {out_base / 'scenarios'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
