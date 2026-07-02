from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from claims_app.config import settings
from claims_app.models import AssignmentCaseResult, AssignmentRunSummary, ClaimResult


DB_PATH = Path("data/claims_runs.sqlite3")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS claim_runs (
                run_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                case_name TEXT NOT NULL,
                status TEXT NOT NULL,
                decision TEXT,
                approved_amount REAL,
                confidence REAL,
                message TEXT,
                trace_reference TEXT,
                created_at TEXT NOT NULL,
                input_json TEXT,
                output_json TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS claim_stage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                details_json TEXT,
                FOREIGN KEY(run_id) REFERENCES claim_runs(run_id)
            )
            """
        )


def save_assignment_result(result: AssignmentCaseResult) -> None:
    init_db()
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO claim_runs (
                run_id, case_id, case_name, status, decision, approved_amount,
                confidence, message, trace_reference, created_at, input_json, output_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.trace_reference,
                result.case_id,
                result.case_name,
                result.status,
                result.decision,
                result.approved_amount,
                result.confidence,
                result.message,
                result.trace_reference,
                datetime.utcnow().isoformat(),
                json.dumps(result.raw_case, default=str),
                result.model_dump_json(),
            ),
        )
        connection.execute("DELETE FROM claim_stage_records WHERE run_id = ?", (result.trace_reference,))
        for record in result.stage_records:
            connection.execute(
                """
                INSERT INTO claim_stage_records (run_id, stage, status, message, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result.trace_reference,
                    record.stage.value,
                    record.status.value,
                    record.message,
                    json.dumps(record.details, default=str),
                ),
            )


def save_live_result(result: ClaimResult) -> None:
    init_db()
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO claim_runs (
                run_id, case_id, case_name, status, decision, approved_amount,
                confidence, message, trace_reference, created_at, input_json, output_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.claim_id,
                result.claim_id,
                result.claim_id,
                result.decision.value,
                result.decision.value,
                result.approved_amount,
                result.confidence,
                result.reason,
                result.trace_reference,
                datetime.utcnow().isoformat(),
                None,
                result.model_dump_json(),
            ),
        )
        connection.execute("DELETE FROM claim_stage_records WHERE run_id = ?", (result.claim_id,))
        for record in result.stage_records:
            connection.execute(
                """
                INSERT INTO claim_stage_records (run_id, stage, status, message, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result.claim_id,
                    record.stage.value,
                    record.status.value,
                    record.message,
                    json.dumps(record.details, default=str),
                ),
            )


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT run_id, case_id, case_name, status, decision, approved_amount,
                   confidence, message, trace_reference, created_at
            FROM claim_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_run(run_id: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as connection:
        row = connection.execute("SELECT * FROM claim_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        stage_rows = connection.execute(
            "SELECT stage, status, message, details_json FROM claim_stage_records WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
    data = dict(row)
    data["stage_records"] = [
        {
            "stage": stage_row["stage"],
            "status": stage_row["status"],
            "message": stage_row["message"],
            "details": json.loads(stage_row["details_json"]) if stage_row["details_json"] else {},
        }
        for stage_row in stage_rows
    ]
    return data
