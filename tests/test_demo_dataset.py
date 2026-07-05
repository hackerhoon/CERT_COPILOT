"""Synthetic demo dataset fallback tests (fresh-checkout UI data guarantee)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from d4d.config import project_root
from d4d.stealthmole.dataset_loader import _build_landscape, _demo_root


class DemoDatasetTest(unittest.TestCase):
    def demo_run(self) -> Path:
        runs = sorted(p for p in _demo_root().iterdir() if p.is_dir())
        self.assertTrue(runs, "커밋된 demo 런이 없습니다 — uv run python -m d4d.build_demo_dataset")
        return runs[-1]

    def test_demo_run_is_tracked_and_marked_synthetic(self) -> None:
        run = self.demo_run()
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["synthetic"])
        for service in ("rm", "cl", "cds", "gm", "lm"):
            feed = json.loads((run / f"{service}.json").read_text(encoding="utf-8"))
            self.assertTrue(feed["synthetic"], service)
            self.assertTrue(feed["records"], service)

    def test_demo_landscape_renders_all_sections(self) -> None:
        landscape = _build_landscape(self.demo_run())
        self.assertEqual(landscape["source"], "synthetic-demo")
        self.assertTrue(landscape["synthetic"])
        self.assertTrue(landscape["ransomware"]["top_groups"])
        self.assertTrue(landscape["credentials"]["recent_samples"])
        self.assertTrue(landscape["monitoring"]["recent_titles"])

    def test_demo_data_contains_no_leak_like_values(self) -> None:
        """demo 파일에는 마스킹/문서용 값만 있어야 한다 (합성 데이터 안전성)."""
        run = self.demo_run()
        re_email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        re_ip = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}\b")
        for path in run.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            for match in re_email.finditer(text):
                self.assertIn("***", match.group(0), f"{path.name}: 마스킹 안 된 이메일 형태")
            for match in re_ip.finditer(text):
                self.assertEqual((int(match.group(1)), int(match.group(2))), (203, 0),
                                 f"{path.name}: 문서용(203.0.113.x) 외 IP")
            for payload_match in re.finditer(r'"password":\s*"([^"]*)"', text):
                self.assertTrue(payload_match.group(1).startswith("***"), f"{path.name}: 마스킹 안 된 password")

    def test_collected_dataset_stays_ignored(self) -> None:
        """실수집 경로는 계속 git-ignore 대상이어야 한다 (커밋 금지 규칙)."""
        gitignore = (project_root() / ".gitignore").read_text(encoding="utf-8")
        for line in (
            "data/stealthmole/raw/",
            "data/stealthmole/sanitized/",
            "data/stealthmole/dataset/",
        ):
            self.assertIn(f"\n{line}", gitignore, f".gitignore에 {line} 규칙이 없습니다")


if __name__ == "__main__":
    unittest.main()
