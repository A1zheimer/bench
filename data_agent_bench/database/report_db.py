from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.report import EvaluationReport

logger = logging.getLogger(__name__)

_CREATE_REPORTS = """
CREATE TABLE IF NOT EXISTS reports (
    report_id     TEXT PRIMARY KEY,
    instance_id   TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    domain        TEXT,
    difficulty    TEXT,
    completion    REAL,
    accuracy      REAL,
    process       REAL,
    safety        REAL,
    tokens        INTEGER,
    cost_usd      REAL,
    wall_time     REAL,
    risk_level    TEXT,
    termination   TEXT,
    failure_cause TEXT,
    full_json     TEXT NOT NULL
)
"""

_CREATE_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
)
"""


class ReportDatabase:
    """
    SQLite-backed store for EvaluationReports.

    "Evolving" = schema migrates forward without dropping columns.
    aggregate_stats() provides the closed-loop feedback for fine-tuning.
    """

    CURRENT_VERSION = 2

    def __init__(self, db_path: str = "bench.db") -> None:
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(_CREATE_REPORTS + ";" + _CREATE_MIGRATIONS)
            cur.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            current = row[0] if row[0] is not None else 0

            if current < 1:
                # v1: base schema already created above
                cur.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
                    (datetime.utcnow().isoformat(),),
                )

            if current < 2:
                # v2: add model tracking and multi-run columns (non-destructive)
                for col_def in [
                    "ALTER TABLE reports ADD COLUMN model_id TEXT",
                    "ALTER TABLE reports ADD COLUMN run_index INTEGER DEFAULT 0",
                    "ALTER TABLE reports ADD COLUMN temperature REAL DEFAULT 0.0",
                    "ALTER TABLE reports ADD COLUMN run_seed INTEGER",
                    "ALTER TABLE reports ADD COLUMN llm_judge_score REAL",
                ]:
                    try:
                        cur.execute(col_def)
                    except sqlite3.OperationalError:
                        pass  # column already exists (idempotent)
                cur.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (2, ?)",
                    (datetime.utcnow().isoformat(),),
                )

            self._conn.commit()
            logger.debug("DB schema at version %d", self.CURRENT_VERSION)

    def save(self, report: EvaluationReport) -> str:
        d = report.to_dict()
        # Extract domain/difficulty from instance context if available
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO reports (
                    report_id, instance_id, timestamp, domain, difficulty,
                    completion, accuracy, process, safety, tokens,
                    cost_usd, wall_time, risk_level, termination, failure_cause, full_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    report.report_id,
                    report.instance_id,
                    report.timestamp.isoformat(),
                    None,  # domain not stored in report; caller can extend
                    None,
                    report.metrics.completion_rate,
                    report.metrics.result_accuracy,
                    report.metrics.process_quality,
                    report.metrics.safety_score,
                    report.metrics.total_tokens,
                    report.metrics.total_cost_usd,
                    report.metrics.wall_time_seconds,
                    report.risk.risk_level,
                    report.failure_attribution.primary_cause if report.failure_attribution else None,
                    report.failure_attribution.primary_cause if report.failure_attribution else None,
                    json.dumps(d, default=str),
                ),
            )
            self._conn.commit()
        logger.debug("Saved report %s", report.report_id)
        return report.report_id

    def save_with_meta(
        self,
        report: EvaluationReport,
        domain: str,
        difficulty: str,
        model_id: str = "simulated",
        run_index: int = 0,
        temperature: float = 0.0,
    ) -> str:
        self.save(report)
        with self._lock:
            self._conn.execute(
                "UPDATE reports SET domain=?, difficulty=?, model_id=?, run_index=?, temperature=? WHERE report_id=?",
                (domain, difficulty, model_id, run_index, temperature, report.report_id),
            )
            self._conn.commit()
        return report.report_id

    def aggregate_stats_by_model(
        self,
        domain: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Group by model_id, compute mean ± std for all metrics."""
        conditions = []
        params: List[Any] = []
        if domain:
            conditions.append("domain=?")
            params.append(domain)
        if difficulty:
            conditions.append("difficulty=?")
            params.append(difficulty)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT model_id,
                    COUNT(*) as cnt,
                    AVG(completion) as avg_c, AVG(accuracy) as avg_a,
                    AVG(process) as avg_p, AVG(safety) as avg_s,
                    AVG(tokens) as avg_t, AVG(cost_usd) as avg_cost,
                    AVG(wall_time) as avg_wt
                FROM reports {where}
                GROUP BY model_id
                ORDER BY avg_a DESC
                """,
                params,
            ).fetchall()

        result = {}
        for row in rows:
            mid = row["model_id"] or "simulated"
            result[mid] = {
                "count": row["cnt"],
                "avg_completion": round(row["avg_c"] or 0, 4),
                "avg_accuracy": round(row["avg_a"] or 0, 4),
                "avg_process": round(row["avg_p"] or 0, 4),
                "avg_safety": round(row["avg_s"] or 0, 4),
                "avg_tokens": int(row["avg_t"] or 0),
                "avg_cost_usd": round(row["avg_cost"] or 0, 6),
                "avg_wall_time": round(row["avg_wt"] or 0, 2),
            }
        return result

    def get(self, report_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT full_json FROM reports WHERE report_id=?", (report_id,)
            ).fetchone()
        return json.loads(row["full_json"]) if row else None

    def query(self, **filters: Any) -> List[Dict[str, Any]]:
        conditions = []
        params = []
        allowed = {"instance_id", "domain", "difficulty", "risk_level", "failure_cause"}
        for key, val in filters.items():
            if key in allowed and val is not None:
                conditions.append(f"{key}=?")
                params.append(val)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT full_json FROM reports {where} ORDER BY timestamp DESC",
                params,
            ).fetchall()
        return [json.loads(r["full_json"]) for r in rows]

    def aggregate_stats(
        self,
        domain: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> Dict[str, Any]:
        conditions = []
        params = []
        if domain:
            conditions.append("domain=?")
            params.append(domain)
        if difficulty:
            conditions.append("difficulty=?")
            params.append(difficulty)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                f"""
                SELECT
                    COUNT(*) as cnt,
                    AVG(completion) as avg_completion,
                    AVG(accuracy)   as avg_accuracy,
                    AVG(process)    as avg_process,
                    AVG(safety)     as avg_safety,
                    AVG(tokens)     as avg_tokens,
                    AVG(cost_usd)   as avg_cost,
                    AVG(wall_time)  as avg_wall_time
                FROM reports {where}
                """,
                params,
            ).fetchone()

            failure_rows = cur.execute(
                f"SELECT failure_cause, COUNT(*) as cnt FROM reports {where} "
                f"GROUP BY failure_cause",
                params,
            ).fetchall()

        if not row or row["cnt"] == 0:
            return {"count": 0}

        failure_dist = {
            r["failure_cause"] or "none": r["cnt"] for r in failure_rows
        }

        return {
            "count": row["cnt"],
            "avg_completion_rate": round(row["avg_completion"] or 0, 4),
            "avg_result_accuracy": round(row["avg_accuracy"] or 0, 4),
            "avg_process_quality": round(row["avg_process"] or 0, 4),
            "avg_safety_score": round(row["avg_safety"] or 0, 4),
            "avg_tokens": int(row["avg_tokens"] or 0),
            "avg_cost_usd": round(row["avg_cost"] or 0, 6),
            "avg_wall_time_seconds": round(row["avg_wall_time"] or 0, 2),
            "failure_distribution": failure_dist,
        }

    def export_jsonl(self, path: str) -> int:
        with self._lock:
            rows = self._conn.execute("SELECT full_json FROM reports ORDER BY timestamp").fetchall()
        count = 0
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(row["full_json"])
                f.write("\n")
                count += 1
        return count

    def list_all(self) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT report_id, instance_id, timestamp FROM reports ORDER BY timestamp DESC"
            ).fetchall()
        return [f"{r['report_id']} | {r['instance_id']} | {r['timestamp']}" for r in rows]
