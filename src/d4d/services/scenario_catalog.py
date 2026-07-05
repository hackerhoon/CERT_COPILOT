"""Fixture-backed home and scenario catalog services."""

from __future__ import annotations

from typing import Any

from d4d.api.envelope import ApiError
from d4d.fixtures.readiness import ADAPTER_STATUS, AVAILABLE_EQUIPMENT, HOME_FIXTURE, SCENARIOS, clone

_EQUIPMENT_LABELS = {item["port"]: item["label"] for item in AVAILABLE_EQUIPMENT}


class AdapterStatusService:
    """Expose mock/live adapter availability without leaking vendor details."""

    def get_status(self) -> dict[str, Any]:
        return {"items": clone(ADAPTER_STATUS)}


class TrainingHomeService:
    """Build the training home view model."""

    def get_home(self) -> dict[str, Any]:
        return clone(HOME_FIXTURE)


class ScenarioCatalogService:
    """List scenarios and return public-safe briefing details."""

    def list_scenarios(
        self,
        *,
        difficulty: str | None = None,
        goal: str | None = None,
        max_minutes: int | None = None,
    ) -> dict[str, Any]:
        items = []
        for scenario in SCENARIOS.values():
            if difficulty and scenario["difficulty"] != difficulty:
                continue
            if goal and goal not in scenario["training_goals"]:
                continue
            if max_minutes is not None and scenario["estimated_minutes"] > max_minutes:
                continue
            items.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "title": scenario["title"],
                    "difficulty": scenario["difficulty"],
                    "estimated_minutes": scenario["estimated_minutes"],
                    "training_goals": clone(scenario["training_goals"]),
                    "available_equipment": clone(scenario["available_equipment"]),
                    "tags": clone(scenario["tags"]),
                }
            )
        return {"items": items}

    def get_briefing(self, scenario_id: str) -> dict[str, Any]:
        scenario = SCENARIOS.get(scenario_id)
        if scenario is None:
            raise ApiError(
                "SCENARIO_NOT_FOUND",
                "요청한 시나리오를 찾을 수 없습니다.",
                status_code=404,
                details={"scenario_id": scenario_id},
            )

        available = [
            {"port": port, "label": _EQUIPMENT_LABELS.get(port, port)}
            for port in scenario["available_equipment"]
        ]
        return {
            "scenario_id": scenario["scenario_id"],
            "title": scenario["title"],
            "difficulty": scenario["difficulty"],
            "estimated_minutes": scenario["estimated_minutes"],
            "briefing": clone(scenario["briefing"]),
            "available_equipment": available,
            "rubric_summary": clone(scenario["rubric_summary"]),
        }
