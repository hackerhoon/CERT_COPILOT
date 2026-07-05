"""Operations Mode repository port and storage adapters."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator, Protocol

from d4d.config import project_root


class OperationsRepository(Protocol):
    """Persistence port for Operations Mode state."""

    backend_name: str

    def next_sequence(self, name: str) -> int:
        """Return the next durable sequence number for `name`."""

    def seed_units(self, units: list[dict[str, Any]]) -> None:
        """Insert or update synthetic unit seed data."""

    def list_units(self) -> list[dict[str, Any]]:
        """List synthetic units in display order."""

    def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        """Load one synthetic unit by id."""

    def save_incident(self, incident: dict[str, Any]) -> None:
        """Insert or update an Operations incident snapshot."""

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        """Load one incident snapshot."""

    def list_incidents(self) -> list[dict[str, Any]]:
        """List incident snapshots."""

    def save_notifications(self, notifications: list[dict[str, Any]]) -> None:
        """Insert or update notification snapshots."""

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        """Load one notification snapshot."""

    def save_notification(self, notification: dict[str, Any]) -> None:
        """Insert or update one notification snapshot."""

    def list_notifications(self) -> list[dict[str, Any]]:
        """List notification snapshots."""

    def save_knowledge(self, item: dict[str, Any]) -> None:
        """Insert or update one knowledge item snapshot (B-11)."""

    def get_knowledge(self, knowledge_id: str) -> dict[str, Any] | None:
        """Load one knowledge item snapshot."""

    def find_knowledge_by_source(self, source_type: str, source_id: str) -> dict[str, Any] | None:
        """Load a knowledge item by its origin record (dedup key)."""

    def list_knowledge(self) -> list[dict[str, Any]]:
        """List knowledge item snapshots, newest first."""

    def save_inquiry(self, inquiry: dict[str, Any]) -> None:
        """Insert or update one helpdesk inquiry snapshot (B-12)."""

    def get_inquiry(self, inquiry_id: str) -> dict[str, Any] | None:
        """Load one helpdesk inquiry snapshot."""

    def list_inquiries(self) -> list[dict[str, Any]]:
        """List helpdesk inquiry snapshots, newest first."""


class InMemoryOperationsRepository:
    """Non-persistent adapter for narrow unit tests."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._counter: dict[str, int] = {}
        self._units: dict[str, dict[str, Any]] = {}
        self._incidents: dict[str, dict[str, Any]] = {}
        self._notifications: dict[str, dict[str, Any]] = {}
        self._knowledge: dict[str, dict[str, Any]] = {}
        self._inquiries: dict[str, dict[str, Any]] = {}

    def next_sequence(self, name: str) -> int:
        self._counter[name] = self._counter.get(name, 0) + 1
        return self._counter[name]

    def seed_units(self, units: list[dict[str, Any]]) -> None:
        for unit in units:
            self._units[unit["unit_id"]] = deepcopy(unit)

    def list_units(self) -> list[dict[str, Any]]:
        return [deepcopy(unit) for unit in sorted(self._units.values(), key=lambda item: item.get("sort_order", 999))]

    def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        unit = self._units.get(unit_id)
        return deepcopy(unit) if unit is not None else None

    def save_incident(self, incident: dict[str, Any]) -> None:
        self._incidents[incident["incident_id"]] = deepcopy(incident)

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        incident = self._incidents.get(incident_id)
        return deepcopy(incident) if incident is not None else None

    def list_incidents(self) -> list[dict[str, Any]]:
        return [deepcopy(incident) for incident in self._incidents.values()]

    def save_notifications(self, notifications: list[dict[str, Any]]) -> None:
        for notification in notifications:
            self.save_notification(notification)

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        notification = self._notifications.get(notification_id)
        return deepcopy(notification) if notification is not None else None

    def save_notification(self, notification: dict[str, Any]) -> None:
        self._notifications[notification["notification_id"]] = deepcopy(notification)

    def list_notifications(self) -> list[dict[str, Any]]:
        return [deepcopy(notification) for notification in self._notifications.values()]

    def save_knowledge(self, item: dict[str, Any]) -> None:
        self._knowledge[item["knowledge_id"]] = deepcopy(item)

    def get_knowledge(self, knowledge_id: str) -> dict[str, Any] | None:
        item = self._knowledge.get(knowledge_id)
        return deepcopy(item) if item is not None else None

    def find_knowledge_by_source(self, source_type: str, source_id: str) -> dict[str, Any] | None:
        for item in self._knowledge.values():
            if item.get("source_type") == source_type and item.get("source_id") == source_id:
                return deepcopy(item)
        return None

    def list_knowledge(self) -> list[dict[str, Any]]:
        items = sorted(
            self._knowledge.values(),
            key=lambda item: (str(item.get("created_at", "")), item.get("knowledge_id", "")),
            reverse=True,
        )
        return [deepcopy(item) for item in items]

    def save_inquiry(self, inquiry: dict[str, Any]) -> None:
        self._inquiries[inquiry["inquiry_id"]] = deepcopy(inquiry)

    def get_inquiry(self, inquiry_id: str) -> dict[str, Any] | None:
        inquiry = self._inquiries.get(inquiry_id)
        return deepcopy(inquiry) if inquiry is not None else None

    def list_inquiries(self) -> list[dict[str, Any]]:
        items = sorted(
            self._inquiries.values(),
            key=lambda item: (str(item.get("created_at", "")), item.get("inquiry_id", "")),
            reverse=True,
        )
        return [deepcopy(item) for item in items]


class SQLiteOperationsRepository:
    """SQLite adapter for local Operations Mode development and E2E tests."""

    backend_name = "sqlite"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def next_sequence(self, name: str) -> int:
        with self._lock, self._transaction() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value FROM ops_counters WHERE name = ?", (name,)).fetchone()
            next_value = int(row["value"]) + 1 if row else 1
            conn.execute(
                """
                INSERT INTO ops_counters (name, value)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET value = excluded.value
                """,
                (name, next_value),
            )
            return next_value

    def seed_units(self, units: list[dict[str, Any]]) -> None:
        with self._lock, self._transaction() as conn:
            for unit in units:
                conn.execute(
                    """
                    INSERT INTO ops_units (unit_id, parent_unit_id, role, sort_order, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(unit_id) DO UPDATE SET
                      parent_unit_id = excluded.parent_unit_id,
                      role = excluded.role,
                      sort_order = excluded.sort_order,
                      payload_json = excluded.payload_json,
                      updated_at = excluded.updated_at
                    """,
                    (
                        unit["unit_id"],
                        unit.get("parent_unit_id"),
                        unit.get("role", "field"),
                        int(unit.get("sort_order", 999)),
                        _dumps(unit),
                    ),
                )

    def list_units(self) -> list[dict[str, Any]]:
        with self._lock, self._transaction() as conn:
            rows = conn.execute("SELECT payload_json FROM ops_units ORDER BY sort_order, unit_id").fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        with self._lock, self._transaction() as conn:
            row = conn.execute("SELECT payload_json FROM ops_units WHERE unit_id = ?", (unit_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def save_incident(self, incident: dict[str, Any]) -> None:
        with self._lock, self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO ops_incidents (incident_id, unit_id, status, severity, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(incident_id) DO UPDATE SET
                  unit_id = excluded.unit_id,
                  status = excluded.status,
                  severity = excluded.severity,
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    incident["incident_id"],
                    incident["unit_id"],
                    incident["status"],
                    incident["severity"],
                    _dumps(incident),
                    incident["created_at"],
                ),
            )

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._lock, self._transaction() as conn:
            row = conn.execute("SELECT payload_json FROM ops_incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_incidents(self) -> list[dict[str, Any]]:
        with self._lock, self._transaction() as conn:
            rows = conn.execute("SELECT payload_json FROM ops_incidents ORDER BY created_at DESC, incident_id DESC").fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def save_notifications(self, notifications: list[dict[str, Any]]) -> None:
        with self._lock, self._transaction() as conn:
            for notification in notifications:
                self._save_notification(conn, notification)

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        with self._lock, self._transaction() as conn:
            row = conn.execute(
                "SELECT payload_json FROM ops_notifications WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def save_notification(self, notification: dict[str, Any]) -> None:
        with self._lock, self._transaction() as conn:
            self._save_notification(conn, notification)

    def list_notifications(self) -> list[dict[str, Any]]:
        with self._lock, self._transaction() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM ops_notifications ORDER BY read ASC, created_at DESC, notification_id DESC"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def save_knowledge(self, item: dict[str, Any]) -> None:
        with self._lock, self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO ops_knowledge (
                  knowledge_id, source_type, source_id, unit_id, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(knowledge_id) DO UPDATE SET
                  source_type = excluded.source_type,
                  source_id = excluded.source_id,
                  unit_id = excluded.unit_id,
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    item["knowledge_id"],
                    item["source_type"],
                    item["source_id"],
                    item.get("unit_id"),
                    _dumps(item),
                    item["created_at"],
                ),
            )

    def get_knowledge(self, knowledge_id: str) -> dict[str, Any] | None:
        with self._lock, self._transaction() as conn:
            row = conn.execute("SELECT payload_json FROM ops_knowledge WHERE knowledge_id = ?", (knowledge_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def find_knowledge_by_source(self, source_type: str, source_id: str) -> dict[str, Any] | None:
        with self._lock, self._transaction() as conn:
            row = conn.execute(
                "SELECT payload_json FROM ops_knowledge WHERE source_type = ? AND source_id = ?",
                (source_type, source_id),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_knowledge(self) -> list[dict[str, Any]]:
        with self._lock, self._transaction() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM ops_knowledge ORDER BY created_at DESC, knowledge_id DESC"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def save_inquiry(self, inquiry: dict[str, Any]) -> None:
        with self._lock, self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO ops_inquiries (inquiry_id, unit_id, status, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(inquiry_id) DO UPDATE SET
                  unit_id = excluded.unit_id,
                  status = excluded.status,
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    inquiry["inquiry_id"],
                    inquiry.get("unit_id"),
                    inquiry["status"],
                    _dumps(inquiry),
                    inquiry["created_at"],
                ),
            )

    def get_inquiry(self, inquiry_id: str) -> dict[str, Any] | None:
        with self._lock, self._transaction() as conn:
            row = conn.execute("SELECT payload_json FROM ops_inquiries WHERE inquiry_id = ?", (inquiry_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_inquiries(self) -> list[dict[str, Any]]:
        with self._lock, self._transaction() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM ops_inquiries ORDER BY created_at DESC, inquiry_id DESC"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def _save_notification(self, conn: sqlite3.Connection, notification: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO ops_notifications (
              notification_id, incident_id, to_unit_id, read, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(notification_id) DO UPDATE SET
              incident_id = excluded.incident_id,
              to_unit_id = excluded.to_unit_id,
              read = excluded.read,
              payload_json = excluded.payload_json,
              updated_at = excluded.updated_at
            """,
            (
                notification["notification_id"],
                notification["incident_id"],
                notification["to_unit_id"],
                1 if notification.get("read") else 0,
                _dumps(notification),
                notification["created_at"],
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ops_counters (
                  name TEXT PRIMARY KEY,
                  value INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_units (
                  unit_id TEXT PRIMARY KEY,
                  parent_unit_id TEXT,
                  role TEXT NOT NULL,
                  sort_order INTEGER NOT NULL,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_incidents (
                  incident_id TEXT PRIMARY KEY,
                  unit_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  severity TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_notifications (
                  notification_id TEXT PRIMARY KEY,
                  incident_id TEXT NOT NULL,
                  to_unit_id TEXT NOT NULL,
                  read INTEGER NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ops_knowledge (
                  knowledge_id TEXT PRIMARY KEY,
                  source_type TEXT NOT NULL,
                  source_id TEXT NOT NULL,
                  unit_id TEXT,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (source_type, source_id)
                );

                CREATE TABLE IF NOT EXISTS ops_inquiries (
                  inquiry_id TEXT PRIMARY KEY,
                  unit_id TEXT,
                  status TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )


class PostgresOperationsRepository:
    """PostgreSQL adapter behind the same Operations repository port."""

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
                cur.execute("INSERT INTO ops_counters (name, value) VALUES (%s, 0) ON CONFLICT (name) DO NOTHING", (name,))
                cur.execute("UPDATE ops_counters SET value = value + 1 WHERE name = %s RETURNING value", (name,))
                row = cur.fetchone()
                return int(row[0])

    def seed_units(self, units: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                for unit in units:
                    cur.execute(
                        """
                        INSERT INTO ops_units (unit_id, parent_unit_id, role, sort_order, payload_json, updated_at)
                        VALUES (%s, %s, %s, %s, %s::jsonb, now())
                        ON CONFLICT (unit_id) DO UPDATE SET
                          parent_unit_id = excluded.parent_unit_id,
                          role = excluded.role,
                          sort_order = excluded.sort_order,
                          payload_json = excluded.payload_json,
                          updated_at = excluded.updated_at
                        """,
                        (
                            unit["unit_id"],
                            unit.get("parent_unit_id"),
                            unit.get("role", "field"),
                            int(unit.get("sort_order", 999)),
                            _dumps(unit),
                        ),
                    )

    def list_units(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_units ORDER BY sort_order, unit_id")
                rows = cur.fetchall()
        return [_loads(row[0]) for row in rows]

    def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_units WHERE unit_id = %s", (unit_id,))
                row = cur.fetchone()
        return _loads(row[0]) if row else None

    def save_incident(self, incident: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ops_incidents (incident_id, unit_id, status, severity, payload_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, now())
                    ON CONFLICT (incident_id) DO UPDATE SET
                      unit_id = excluded.unit_id,
                      status = excluded.status,
                      severity = excluded.severity,
                      payload_json = excluded.payload_json,
                      updated_at = excluded.updated_at
                    """,
                    (
                        incident["incident_id"],
                        incident["unit_id"],
                        incident["status"],
                        incident["severity"],
                        _dumps(incident),
                        incident["created_at"],
                    ),
                )

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_incidents WHERE incident_id = %s", (incident_id,))
                row = cur.fetchone()
        return _loads(row[0]) if row else None

    def list_incidents(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_incidents ORDER BY created_at DESC, incident_id DESC")
                rows = cur.fetchall()
        return [_loads(row[0]) for row in rows]

    def save_notifications(self, notifications: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                for notification in notifications:
                    self._save_notification(cur, notification)

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_notifications WHERE notification_id = %s", (notification_id,))
                row = cur.fetchone()
        return _loads(row[0]) if row else None

    def save_notification(self, notification: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._save_notification(cur, notification)

    def list_notifications(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_notifications ORDER BY read ASC, created_at DESC, notification_id DESC")
                rows = cur.fetchall()
        return [_loads(row[0]) for row in rows]

    def save_knowledge(self, item: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ops_knowledge (knowledge_id, source_type, source_id, unit_id, payload_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, now())
                    ON CONFLICT (knowledge_id) DO UPDATE SET
                      source_type = excluded.source_type,
                      source_id = excluded.source_id,
                      unit_id = excluded.unit_id,
                      payload_json = excluded.payload_json,
                      updated_at = excluded.updated_at
                    """,
                    (
                        item["knowledge_id"],
                        item["source_type"],
                        item["source_id"],
                        item.get("unit_id"),
                        _dumps(item),
                        item["created_at"],
                    ),
                )

    def get_knowledge(self, knowledge_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_knowledge WHERE knowledge_id = %s", (knowledge_id,))
                row = cur.fetchone()
        return _loads(row[0]) if row else None

    def find_knowledge_by_source(self, source_type: str, source_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload_json FROM ops_knowledge WHERE source_type = %s AND source_id = %s",
                    (source_type, source_id),
                )
                row = cur.fetchone()
        return _loads(row[0]) if row else None

    def list_knowledge(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_knowledge ORDER BY created_at DESC, knowledge_id DESC")
                rows = cur.fetchall()
        return [_loads(row[0]) for row in rows]

    def save_inquiry(self, inquiry: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ops_inquiries (inquiry_id, unit_id, status, payload_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s::jsonb, %s, now())
                    ON CONFLICT (inquiry_id) DO UPDATE SET
                      unit_id = excluded.unit_id,
                      status = excluded.status,
                      payload_json = excluded.payload_json,
                      updated_at = excluded.updated_at
                    """,
                    (
                        inquiry["inquiry_id"],
                        inquiry.get("unit_id"),
                        inquiry["status"],
                        _dumps(inquiry),
                        inquiry["created_at"],
                    ),
                )

    def get_inquiry(self, inquiry_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_inquiries WHERE inquiry_id = %s", (inquiry_id,))
                row = cur.fetchone()
        return _loads(row[0]) if row else None

    def list_inquiries(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM ops_inquiries ORDER BY created_at DESC, inquiry_id DESC")
                rows = cur.fetchall()
        return [_loads(row[0]) for row in rows]

    def _save_notification(self, cur: Any, notification: dict[str, Any]) -> None:
        cur.execute(
            """
            INSERT INTO ops_notifications (notification_id, incident_id, to_unit_id, read, payload_json, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, now())
            ON CONFLICT (notification_id) DO UPDATE SET
              incident_id = excluded.incident_id,
              to_unit_id = excluded.to_unit_id,
              read = excluded.read,
              payload_json = excluded.payload_json,
              updated_at = excluded.updated_at
            """,
            (
                notification["notification_id"],
                notification["incident_id"],
                notification["to_unit_id"],
                bool(notification.get("read")),
                _dumps(notification),
                notification["created_at"],
            ),
        )

    def _connect(self):
        return self._psycopg.connect(self.database_url)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops_counters (
                      name TEXT PRIMARY KEY,
                      value BIGINT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops_units (
                      unit_id TEXT PRIMARY KEY,
                      parent_unit_id TEXT,
                      role TEXT NOT NULL,
                      sort_order INTEGER NOT NULL,
                      payload_json JSONB NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops_incidents (
                      incident_id TEXT PRIMARY KEY,
                      unit_id TEXT NOT NULL,
                      status TEXT NOT NULL,
                      severity TEXT NOT NULL,
                      payload_json JSONB NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops_notifications (
                      notification_id TEXT PRIMARY KEY,
                      incident_id TEXT NOT NULL,
                      to_unit_id TEXT NOT NULL,
                      read BOOLEAN NOT NULL,
                      payload_json JSONB NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops_knowledge (
                      knowledge_id TEXT PRIMARY KEY,
                      source_type TEXT NOT NULL,
                      source_id TEXT NOT NULL,
                      unit_id TEXT,
                      payload_json JSONB NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL,
                      UNIQUE (source_type, source_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops_inquiries (
                      inquiry_id TEXT PRIMARY KEY,
                      unit_id TEXT,
                      status TEXT NOT NULL,
                      payload_json JSONB NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )


def create_operations_repository_from_env() -> OperationsRepository:
    """Create the configured Operations repository adapter.

    Environment follows the training repository:
    - `D4D_STORAGE_BACKEND`: `sqlite` (default), `postgres`, or `memory`
    - `D4D_SQLITE_PATH`: SQLite file path shared with the training repository
    - `D4D_DATABASE_URL`: PostgreSQL URL when backend is `postgres`
    """

    database_url = os.environ.get("D4D_DATABASE_URL", "")
    backend = os.environ.get("D4D_STORAGE_BACKEND", "").strip().lower()
    if not backend and database_url.startswith(("postgres://", "postgresql://")):
        backend = "postgres"
    backend = backend or "sqlite"

    if backend == "memory":
        return InMemoryOperationsRepository()
    if backend == "postgres":
        if not database_url:
            raise RuntimeError("D4D_DATABASE_URL is required when D4D_STORAGE_BACKEND=postgres.")
        return PostgresOperationsRepository(database_url)
    if backend != "sqlite":
        raise RuntimeError(f"Unsupported D4D_STORAGE_BACKEND: {backend}")

    sqlite_path = os.environ.get("D4D_SQLITE_PATH")
    if sqlite_path:
        return SQLiteOperationsRepository(sqlite_path)
    return SQLiteOperationsRepository(project_root() / "data" / "runtime" / "readiness.sqlite3")


def _dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    return json.loads(value)
