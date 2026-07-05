"""Training home and scenario catalog routers."""

from __future__ import annotations

from fastapi import APIRouter, Query

from d4d.api.envelope import ok
from d4d.services.scenario_catalog import ScenarioCatalogService, TrainingHomeService

router = APIRouter(tags=["training"])
home_service = TrainingHomeService()
catalog_service = ScenarioCatalogService()


@router.get("/api/training/home")
def get_training_home() -> dict:
    return ok(home_service.get_home(), request_id_prefix="req-home")


@router.get("/api/scenarios")
def list_scenarios(
    difficulty: str | None = None,
    goal: str | None = None,
    max_minutes: int | None = Query(default=None, ge=1),
) -> dict:
    return ok(
        catalog_service.list_scenarios(difficulty=difficulty, goal=goal, max_minutes=max_minutes),
        request_id_prefix="req-scenarios",
    )


@router.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    return ok(catalog_service.get_briefing(scenario_id), request_id_prefix="req-scenario")
