from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src import __version__
from src.domain.models import ConfirmedAddress, GeocodeResult, RouteResult, RowOutcome


SCHEMA_VERSION = "5"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class CacheRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    cache_key TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    cleaned_address_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS route_cache (
                    cache_key TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    origin_key TEXT NOT NULL,
                    destination_key TEXT NOT NULL,
                    vehicle_size INTEGER,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS confirmed_addresses (
                    address_id TEXT PRIMARY KEY,
                    original_city TEXT NOT NULL,
                    original_address TEXT NOT NULL,
                    cleaned_address TEXT NOT NULL,
                    query_address TEXT NOT NULL,
                    formatted_address TEXT NOT NULL,
                    province TEXT NOT NULL,
                    city TEXT NOT NULL,
                    district TEXT NOT NULL,
                    street TEXT NOT NULL,
                    number TEXT NOT NULL,
                    level TEXT NOT NULL,
                    longitude REAL,
                    latitude REAL,
                    confirmation_status TEXT NOT NULL,
                    confirmed_by TEXT NOT NULL DEFAULT '',
                    confirmed_at TEXT NOT NULL DEFAULT '',
                    data_source TEXT NOT NULL,
                    cleaner_version TEXT NOT NULL,
                    geocode_contract_version TEXT NOT NULL,
                    address_hash TEXT NOT NULL,
                    geocode_version TEXT NOT NULL,
                    city_conflict INTEGER NOT NULL DEFAULT 0,
                    risk_level TEXT NOT NULL,
                    risk_reason TEXT NOT NULL,
                    confirmation_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    source_sha256 TEXT NOT NULL,
                    selection_json TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    state TEXT NOT NULL,
                    output_path TEXT,
                    save_watermark INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS row_results (
                    task_id TEXT NOT NULL,
                    excel_row INTEGER NOT NULL,
                    input_digest TEXT NOT NULL,
                    outcome_json TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, excel_row),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_route_cache_mode ON route_cache(mode);
                CREATE INDEX IF NOT EXISTS idx_row_results_digest ON row_results(input_digest);
                CREATE INDEX IF NOT EXISTS idx_confirmed_address_hash ON confirmed_addresses(address_hash);
                CREATE INDEX IF NOT EXISTS idx_confirmed_address_status ON confirmed_addresses(confirmation_status);
                """
            )
            self._ensure_column("route_cache", "origin_address_id", "TEXT")
            self._ensure_column("route_cache", "destination_address_id", "TEXT")
            self._ensure_column("route_cache", "origin_geocode_version", "TEXT")
            self._ensure_column("route_cache", "destination_geocode_version", "TEXT")
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "app_version": __version__,
                "mode": "mock/driving_real/local_validation",
            }
            self._connection.executemany(
                "INSERT INTO schema_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                metadata.items(),
            )

    def _ensure_column(self, table: str, column: str, declaration: str) -> None:
        columns = {
            str(row["name"])
            for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    @property
    def journal_mode(self) -> str:
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "CacheRepository":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_geocode(self, cache_key: str, *, expected_mode: str | None = None) -> GeocodeResult | None:
        with self._lock:
            if expected_mode is None:
                row = self._connection.execute(
                    "SELECT payload_json FROM geocode_cache WHERE cache_key=?", (cache_key,)
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT payload_json FROM geocode_cache WHERE cache_key=? AND mode=?",
                    (cache_key, expected_mode),
                ).fetchone()
        return GeocodeResult(**json.loads(row[0])) if row else None

    def put_geocode(self, result: GeocodeResult, address_hash: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO geocode_cache VALUES(?,?,?,?,?)",
                (result.cache_key, result.mode, address_hash, json.dumps(asdict(result), ensure_ascii=False), _now()),
            )

    def get_route(self, cache_key: str, *, expected_mode: str | None = None) -> RouteResult | None:
        with self._lock:
            if expected_mode is None:
                row = self._connection.execute(
                    "SELECT payload_json FROM route_cache WHERE cache_key=?", (cache_key,)
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT payload_json FROM route_cache WHERE cache_key=? AND mode=?",
                    (cache_key, expected_mode),
                ).fetchone()
        if not row:
            return None
        return RouteResult(**json.loads(row[0]))

    def put_route(
        self,
        result: RouteResult,
        origin_key: str,
        destination_key: str,
        vehicle_size: int | None = None,
        origin_address_id: str = "",
        destination_address_id: str = "",
        origin_geocode_version: str = "",
        destination_geocode_version: str = "",
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO route_cache(
                       cache_key,mode,origin_key,destination_key,vehicle_size,payload_json,created_at,
                       origin_address_id,destination_address_id,origin_geocode_version,destination_geocode_version
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(cache_key) DO UPDATE SET
                     mode=excluded.mode,
                     origin_key=excluded.origin_key,
                     destination_key=excluded.destination_key,
                     vehicle_size=excluded.vehicle_size,
                     payload_json=excluded.payload_json,
                     created_at=excluded.created_at,
                     origin_address_id=excluded.origin_address_id,
                     destination_address_id=excluded.destination_address_id,
                     origin_geocode_version=excluded.origin_geocode_version,
                     destination_geocode_version=excluded.destination_geocode_version""",
                (
                    result.cache_key,
                    result.mode,
                    origin_key,
                    destination_key,
                    vehicle_size,
                    json.dumps(asdict(result), ensure_ascii=False),
                    _now(),
                    origin_address_id,
                    destination_address_id,
                    origin_geocode_version,
                    destination_geocode_version,
                ),
            )

    def list_geocode_entries(self, *, mode: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT cleaned_address_hash, payload_json
                   FROM geocode_cache WHERE mode=? ORDER BY cache_key""",
                (mode,),
            ).fetchall()
        return [
            {
                "cleaned_address_hash": str(row["cleaned_address_hash"]),
                "result": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def list_route_entries(self, *, mode: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT origin_key,destination_key,vehicle_size,payload_json,
                          COALESCE(origin_address_id, '') AS origin_address_id,
                          COALESCE(destination_address_id, '') AS destination_address_id,
                          COALESCE(origin_geocode_version, '') AS origin_geocode_version,
                          COALESCE(destination_geocode_version, '') AS destination_geocode_version
                   FROM route_cache WHERE mode=? ORDER BY cache_key""",
                (mode,),
            ).fetchall()
        return [
            {
                "origin_key": str(row["origin_key"]),
                "destination_key": str(row["destination_key"]),
                "vehicle_size": row["vehicle_size"],
                "origin_address_id": str(row["origin_address_id"]),
                "destination_address_id": str(row["destination_address_id"]),
                "origin_geocode_version": str(row["origin_geocode_version"]),
                "destination_geocode_version": str(row["destination_geocode_version"]),
                "result": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def invalidate_routes_for_address(self, address_id: str) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """DELETE FROM route_cache
                   WHERE origin_address_id=? OR destination_address_id=?""",
                (address_id, address_id),
            )
        return max(0, int(cursor.rowcount))

    def get_address(self, address_id: str) -> ConfirmedAddress | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM confirmed_addresses WHERE address_id=?", (address_id,)
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["city_conflict"] = bool(payload["city_conflict"])
        return ConfirmedAddress(**payload)

    def list_addresses(self) -> list[ConfirmedAddress]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM confirmed_addresses
                   ORDER BY confirmation_status, original_city, original_address"""
            ).fetchall()
        results: list[ConfirmedAddress] = []
        for row in rows:
            payload = dict(row)
            payload["city_conflict"] = bool(payload["city_conflict"])
            results.append(ConfirmedAddress(**payload))
        return results

    def put_address(self, address: ConfirmedAddress) -> int:
        old = self.get_address(address.address_id)
        values = asdict(address)
        values["city_conflict"] = int(address.city_conflict)
        columns = tuple(values)
        placeholders = ",".join("?" for _ in columns)
        updates = ",".join(
            f"{column}=excluded.{column}" for column in columns if column not in {"address_id", "created_at"}
        )
        with self._lock, self._connection:
            self._connection.execute(
                f"""INSERT INTO confirmed_addresses({','.join(columns)}) VALUES({placeholders})
                    ON CONFLICT(address_id) DO UPDATE SET {updates}""",
                tuple(values[column] for column in columns),
            )
        if old and old.geocode_version and old.geocode_version != address.geocode_version:
            return self.invalidate_routes_for_address(address.address_id)
        return 0

    def clear_route_cache(self, *, mode: str) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute("DELETE FROM route_cache WHERE mode=?", (mode,))
        return max(0, int(cursor.rowcount))

    def create_task(
        self,
        task_id: str,
        source_sha256: str,
        selection: dict[str, Any],
        mode: str,
        output_path: str | None = None,
    ) -> None:
        timestamp = _now()
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO tasks(task_id,source_sha256,selection_json,mode,state,output_path,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(task_id) DO NOTHING""",
                (task_id, source_sha256, json.dumps(selection, ensure_ascii=False), mode, "RUNNING", output_path, timestamp, timestamp),
            )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def update_task(
        self,
        task_id: str,
        state: str,
        *,
        output_path: str | None = None,
        save_watermark: int | None = None,
        error: str | None = None,
    ) -> None:
        fields = ["state=?", "updated_at=?"]
        values: list[Any] = [state, _now()]
        if output_path is not None:
            fields.append("output_path=?")
            values.append(output_path)
        if save_watermark is not None:
            fields.append("save_watermark=?")
            values.append(save_watermark)
        if error is not None:
            fields.append("error=?")
            values.append(error)
        values.append(task_id)
        with self._lock, self._connection:
            self._connection.execute(f"UPDATE tasks SET {','.join(fields)} WHERE task_id=?", values)

    def save_row_outcome(self, task_id: str, outcome: RowOutcome) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO row_results(task_id,excel_row,input_digest,outcome_json,completed_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(task_id,excel_row) DO UPDATE SET
                     input_digest=excluded.input_digest,
                     outcome_json=excluded.outcome_json,
                     completed_at=excluded.completed_at""",
                (task_id, outcome.excel_row, outcome.input_digest, json.dumps(outcome.as_dict(), ensure_ascii=False), _now()),
            )

    def load_row_outcome(self, task_id: str, excel_row: int, input_digest: str) -> RowOutcome | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT outcome_json,input_digest FROM row_results WHERE task_id=? AND excel_row=?",
                (task_id, excel_row),
            ).fetchone()
        if not row or row["input_digest"] != input_digest:
            return None
        return RowOutcome(**json.loads(row["outcome_json"]))

    def list_row_outcomes(self, task_id: str) -> list[RowOutcome]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT outcome_json FROM row_results WHERE task_id=? ORDER BY excel_row", (task_id,)
            ).fetchall()
        return [RowOutcome(**json.loads(row[0])) for row in rows]

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {
                table: int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("geocode_cache", "route_cache", "tasks", "row_results", "schema_meta")
            }

    def address_count(self) -> int:
        with self._lock:
            return int(self._connection.execute("SELECT COUNT(*) FROM confirmed_addresses").fetchone()[0])
