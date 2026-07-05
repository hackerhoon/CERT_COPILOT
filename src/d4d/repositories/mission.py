"""Mission session repository port and storage adapters.

The application service talks to `MissionSessionRepository`, not to SQLite,
PostgreSQL, or in-memory dictionaries directly. SQLite is the default local
adapter so a development server can persist sessions across restarts. PostgreSQL
is available behind the same port when `psycopg` is installed.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol

from d4d.config import project_root


class MissionSessionRepository(Protocol):
    """Persistence port for training sessions and operations cases."""

    backend_name: str

    def next_sequence(self, name: str) -> int:
        """Return the next durable sequence number for `name`."""

    def save_session(self, session: dict[str, Any]) -> None:
        """Insert or update a full training session snapshot."""

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Load a training session snapshot, or `None` if missing."""

    def save_ops_case(self, case: dict[str, Any]) -> None:
        """Persist an Operations Mode draft generated from training evidence."""


class InMemoryMissionSessionRepository:
    """Non-persistent adapter for narrow unit tests only."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._counter: dict[str, int] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._ops_cases: dict[str, dict[str, Any]] = {}

    def next_sequence(self, name: str) -> int:
        self._counter[name] = self._counter.get(name, 0) + 1
        return self._counter[name]

    def save_session(self, session: dict[str, Any]) -> None:
        self._sessions[session["session_id"]] = deepcopy(session)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        return deepcopy(session) if session is not None else None

    def save_ops_case(self, case: dict[str, Any]) -> None:
        self._ops_cases[case["case_id"]] = deepcopy(case)


class SQLiteMissionSessionRepository:
    """SQLite adapter for local development and E2E tests."""

    backend_name = "sqlite"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def next_sequence(self, name: str) -> int:
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value FROM storage_counters WHERE name = ?", (name,)).fetchone()
            next_value = int(row["value"]) + 1 if row else 1
            conn.execute(
                """
                INSERT INTO storage_counters (name, value)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET value = excluded.value
                """,
                (name, next_value),
            )
            return next_value

    def save_session(self, session: dict[str, Any]) -> None:
        payload = _dumps(session)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO training_sessions (session_id, scenario_id, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(session_id) DO UPDATE SET
                  scenario_id = excluded.scenario_id,
                  status = excluded.status,
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                (session["session_id"], session["scenario_id"], session["status"], payload),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM training_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def save_ops_case(self, case: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ops_cases (case_id, source_session_id, status, payload_json, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(case_id) DO UPDATE SET
                  status = excluded.status,
                  payload_json = excluded.payload_json
                """,
                (case["case_id"], case["source_session_id"], case["status"], _dumps(case)),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS storage_counters (
                  name TEXT PRIMARY KEY,
                  value INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS training_sessions (
                  session_id TEXT PRIMARY KEY,
                  scenario_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_cases (
                  case_id TEXT PRIMARY KEY,
                  source_session_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )


class PostgresMissionSessionRepository:
    """PostgreSQL adapter behind the same repository port.

    Requires `psycopg`. This adapter intentionally stores the same session
    snapshots as JSONB so the MVP can move from SQLite to PostgreSQL without
    changing application services. More normalized tables can be added later
    without changing the port.
    """

    backend_name = "postgres"

    def __init__(self, database_url: str) -> None:
        try:
            import psycopg  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PostgreSQL storage requires `psycopg[binary]` to be installed.") from exc
        self._psycopg = psycopg
        self.database_url = database_url
        self._init_schema()

    def next_sequence(self, name: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO storage_counters (name, value) VALUES (%s, 0) ON CONFLICT (name) DO NOTHING", (name,))
                cur.execute("UPDATE storage_counters SET value = value + 1 WHERE name = %s RETURNING value", (name,))
                row = cur.fetchone()
                return int(row[0])

    def save_session(self, session: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO training_sessions (session_id, scenario_id, status, payload_json, updated_at)
                    VALUES (%s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (session_id) DO UPDATE SET
                      scenario_id = excluded.scenario_id,
                      status = excluded.status,
                      payload_json = excluded.payload_json,
                      updated_at = excluded.updated_at
                    """,
                    (session["session_id"], session["scenario_id"], session["status"], _dumps(session)),
                )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM training_sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
        if not row:
            return None
        payload = row[0]
        return payload if isinstance(payload, dict) else json.loads(payload)

    def save_ops_case(self, case: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ops_cases (case_id, source_session_id, status, payload_json, created_at)
                    VALUES (%s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (case_id) DO UPDATE SET
                      status = excluded.status,
                      payload_json = excluded.payload_json
                    """,
                    (case["case_id"], case["source_session_id"], case["status"], _dumps(case)),
                )

    def _connect(self):
        return self._psycopg.connect(self.database_url)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS storage_counters (
                      name TEXT PRIMARY KEY,
                      value BIGINT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS training_sessions (
                      session_id TEXT PRIMARY KEY,
                      scenario_id TEXT NOT NULL,
                      status TEXT NOT NULL,
                      payload_json JSONB NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops_cases (
                      case_id TEXT PRIMARY KEY,
                      source_session_id TEXT NOT NULL,
                      status TEXT NOT NULL,
                      payload_json JSONB NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )


def create_mission_repository_from_env() -> MissionSessionRepository:
    """Create the configured mission repository adapter.

    Environment:
    - `D4D_STORAGE_BACKEND`: `sqlite` (default), `postgres`, or `memory`
    - `D4D_SQLITE_PATH`: SQLite file path for local development/tests
    - `D4D_DATABASE_URL`: PostgreSQL URL when backend is `postgres`
    """
    database_url = os.environ.get("D4D_DATABASE_URL", "")
    backend = os.environ.get("D4D_STORAGE_BACKEND", "").strip().lower()
    if not backend and database_url.startswith(("postgres://", "postgresql://")):
        backend = "postgres"
    backend = backend or "sqlite"

    if backend == "memory":
        return InMemoryMissionSessionRepository()
    if backend == "postgres":
        if not database_url:
            raise RuntimeError("D4D_DATABASE_URL is required when D4D_STORAGE_BACKEND=postgres.")
        return PostgresMissionSessionRepository(database_url)
    if backend != "sqlite":
        raise RuntimeError(f"Unsupported D4D_STORAGE_BACKEND: {backend}")

    sqlite_path = os.environ.get("D4D_SQLITE_PATH")
    if sqlite_path:
        return SQLiteMissionSessionRepository(sqlite_path)
    return SQLiteMissionSessionRepository(project_root() / "data" / "runtime" / "readiness.sqlite3")


def _dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
