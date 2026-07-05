"""FastAPI app entrypoint for the D4D readiness simulator."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from d4d.api.envelope import ApiError, api_error_handler
from d4d.api.routers import (
    adapters,
    dashboard,
    health,
    helpdesk,
    knowledge,
    operations,
    ops_cases,
    scenarios,
    training_sessions,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cyber Defense Readiness Simulator API",
        version="0.1.0",
        description=(
            "Fixture-first API for the D4D T5 cyber-defense readiness simulator. "
            "All default data is synthetic and public-safe."
        ),
    )
    # 프론트엔드(app/)를 정적 서버·file://에서 열고 이 API에 붙일 수 있도록 로컬
    # 개발용 CORS를 허용한다. 로컬 origin과 file:// (Origin: null)만 대상으로 한다.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|null)$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(health.router)
    app.include_router(adapters.router)
    app.include_router(scenarios.router)
    app.include_router(training_sessions.router)
    app.include_router(operations.router)
    app.include_router(ops_cases.router)
    app.include_router(knowledge.router)
    app.include_router(helpdesk.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
