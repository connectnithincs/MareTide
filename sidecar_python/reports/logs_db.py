import sqlite3
import os
import datetime
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("reports.logs_db")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maretide.db")
_db_initialized = False


def get_db_connection() -> sqlite3.Connection:
    """Returns an optimized SQLite connection configured with WAL mode and memory cache."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    return conn


def init_db():
    global _db_initialized
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ballast operations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ballast_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            op_type TEXT,
            pump_mode TEXT,
            source TEXT,
            dest TEXT,
            qty REAL,
            remaining_src REAL,
            final_dest REAL,
            score_before REAL,
            score_after REAL,
            trigger_source TEXT
        )
    """)
    
    # Cargo operations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cargo_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event TEXT,
            container_id TEXT,
            weight REAL,
            bay INTEGER,
            side TEXT,
            tier INTEGER,
            source TEXT
        )
    """)

    # Phase 3B Container Loading Audit Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS container_loading_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            container_number TEXT,
            gross_weight_t REAL,
            gross_weight_kg REAL,
            bay INTEGER,
            side TEXT,
            tier INTEGER,
            stability_before_score REAL,
            stability_before_risk TEXT,
            stability_after_score REAL,
            stability_after_risk TEXT,
            operator_confirmed INTEGER,
            operation_result TEXT,
            error_message TEXT
        )
    """)

    # Phase 5 Complete Operational Traceability & Audit Events Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operation_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            container_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            source TEXT NOT NULL,
            previous_state TEXT,
            new_state TEXT,
            relevant_metrics TEXT,
            reason TEXT,
            success INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_op_id ON operation_audit_events(operation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_cntr_id ON operation_audit_events(container_id)")
    
    conn.commit()
    conn.close()
    _db_initialized = True


# Initialize schema on module import
init_db()


def log_ballast_operation(op_type, pump_mode, source, dest, qty, remaining_src, final_dest, score_before, score_after, trigger_source):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO ballast_operations 
        (timestamp, op_type, pump_mode, source, dest, qty, remaining_src, final_dest, score_before, score_after, trigger_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, op_type, pump_mode, source, dest, qty, remaining_src, final_dest, score_before, score_after, trigger_source))
    conn.commit()
    conn.close()


def log_cargo_operation(event, container_id, weight, bay, side, tier, source):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO cargo_operations 
        (timestamp, event, container_id, weight, bay, side, tier, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, event, container_id, weight, bay, side, tier, source))
    conn.commit()
    conn.close()


def log_container_loading_audit(
    container_number: str,
    gross_weight_t: float,
    gross_weight_kg: float,
    bay: int,
    side: str,
    tier: int,
    stability_before_score: float,
    stability_before_risk: str,
    stability_after_score: float,
    stability_after_risk: str,
    operator_confirmed: bool,
    operation_result: str,
    error_message: str = None
) -> int:
    """Logs an audit entry for container loading confirmation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO container_loading_audit 
        (timestamp, container_number, gross_weight_t, gross_weight_kg, bay, side, tier,
         stability_before_score, stability_before_risk, stability_after_score, stability_after_risk,
         operator_confirmed, operation_result, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp, container_number, gross_weight_t, gross_weight_kg, bay, side, tier,
        stability_before_score, stability_before_risk, stability_after_score, stability_after_risk,
        1 if operator_confirmed else 0, operation_result, error_message
    ))
    audit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return audit_id


def get_container_loading_audits(limit=100):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM container_loading_audit ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "container_number": r["container_number"],
            "gross_weight_t": r["gross_weight_t"],
            "gross_weight_kg": r["gross_weight_kg"],
            "bay": r["bay"],
            "side": r["side"],
            "tier": r["tier"],
            "stability_before_score": r["stability_before_score"],
            "stability_before_risk": r["stability_before_risk"],
            "stability_after_score": r["stability_after_score"],
            "stability_after_risk": r["stability_after_risk"],
            "operator_confirmed": bool(r["operator_confirmed"]),
            "operation_result": r["operation_result"],
            "error_message": r["error_message"]
        }
        for r in rows
    ]


def get_ballast_operations(limit=100):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ballast_operations ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "timestamp": r["timestamp"],
            "op_type": r["op_type"],
            "pump_mode": r["pump_mode"],
            "source": r["source"],
            "dest": r["dest"],
            "qty": r["qty"],
            "remaining_src": r["remaining_src"],
            "final_dest": r["final_dest"],
            "score_before": r["score_before"],
            "score_after": r["score_after"],
            "trigger": r["trigger_source"]
        }
        for r in rows
    ]


def get_cargo_operations(limit=100):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cargo_operations ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "time": r["timestamp"],
            "event": r["event"],
            "container": r["container_id"],
            "weight": r["weight"],
            "bay": r["bay"],
            "side": r["side"],
            "tier": r["tier"],
            "source": r["source"]
        }
        for r in rows
    ]


def clear_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ballast_operations")
    cursor.execute("DELETE FROM cargo_operations")
    cursor.execute("DELETE FROM container_loading_audit")
    cursor.execute("DELETE FROM operation_audit_events")
    conn.commit()
    conn.close()


# ---------------------------------------------------------
# Phase 5: Complete Operational Traceability & Audit Logging
# ---------------------------------------------------------

PROVENANCE_ALLOWED = {
    "DOCUMENT_AI",
    "CALCULATED",
    "OPERATOR",
    "HARDWARE_SENSOR",
    "SIMULATED_TELEMETRY"
}

FORBIDDEN_METRIC_KEYS = {
    "cargo_kg", "scale_kg", "hx711", "hx711_raw", "load_cell", "loadcell",
    "sensor_derived_weight", "sensor_weight", "hardware_weight", "cargo_mass_sensor",
    "weight_sensor", "sensor_derived_container_weight", "load_cell_kg", "scale_weight_kg"
}



def _sanitize_metrics(metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensures load-cell data is never stored in SQLite metrics."""
    if not metrics or not isinstance(metrics, dict):
        return {}
    clean = {}
    for k, v in metrics.items():
        if k.lower() not in FORBIDDEN_METRIC_KEYS:
            clean[k] = v
    return clean


def log_operation_audit_event(
    operation_id: str,
    event_type: str,
    container_id: str,
    actor: str,
    source: str,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    relevant_metrics: Optional[Dict[str, Any]] = None,
    reason: str = "",
    success: bool = True,
    timestamp: Optional[str] = None
) -> int:
    """
    Logs a discrete lifecycle milestone event into SQLite operation_audit_events.
    """
    norm_source = (source or "CALCULATED").upper()
    if norm_source not in PROVENANCE_ALLOWED:
        if "DOCUMENT" in norm_source:
            norm_source = "DOCUMENT_AI"
        elif "OPERATOR" in norm_source:
            norm_source = "OPERATOR"
        elif "HARDWARE" in norm_source:
            norm_source = "HARDWARE_SENSOR"
        elif "SIMULAT" in norm_source:
            norm_source = "SIMULATED_TELEMETRY"
        else:
            norm_source = "CALCULATED"

    clean_metrics = _sanitize_metrics(relevant_metrics)
    metrics_json = json.dumps(clean_metrics)
    event_time = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO operation_audit_events
        (operation_id, timestamp, event_type, container_id, actor, source,
         previous_state, new_state, relevant_metrics, reason, success)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        operation_id,
        event_time,
        event_type,
        container_id or "UNKNOWN",
        actor or "SYSTEM",
        norm_source,
        previous_state,
        new_state,
        metrics_json,
        reason,
        1 if success else 0
    ))
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_operation_timeline(operation_id: str) -> List[Dict[str, Any]]:
    """Retrieves chronologically ordered audit events for an operation ID."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM operation_audit_events
        WHERE operation_id = ?
        ORDER BY id ASC
    """, (operation_id,))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        try:
            metrics = json.loads(r["relevant_metrics"]) if r["relevant_metrics"] else {}
        except Exception:
            metrics = {}

        events.append({
            "id": r["id"],
            "operation_id": r["operation_id"],
            "timestamp": r["timestamp"],
            "event_type": r["event_type"],
            "container_id": r["container_id"],
            "actor": r["actor"],
            "source": r["source"],
            "previous_state": r["previous_state"],
            "new_state": r["new_state"],
            "relevant_metrics": metrics,
            "reason": r["reason"],
            "success": bool(r["success"])
        })
    return events


def get_all_audit_events(limit: int = 100, container_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recent audit events across all operations."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if container_id:
        cursor.execute("""
            SELECT * FROM operation_audit_events
            WHERE container_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (container_id, limit))
    else:
        cursor.execute("""
            SELECT * FROM operation_audit_events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        try:
            metrics = json.loads(r["relevant_metrics"]) if r["relevant_metrics"] else {}
        except Exception:
            metrics = {}

        events.append({
            "id": r["id"],
            "operation_id": r["operation_id"],
            "timestamp": r["timestamp"],
            "event_type": r["event_type"],
            "container_id": r["container_id"],
            "actor": r["actor"],
            "source": r["source"],
            "previous_state": r["previous_state"],
            "new_state": r["new_state"],
            "relevant_metrics": metrics,
            "reason": r["reason"],
            "success": bool(r["success"])
        })
    return events


def get_recent_operation_summaries(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns summaries of recent operations with event counts and timestamps."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT operation_id, container_id, COUNT(*) as event_count,
               MIN(timestamp) as started_at, MAX(timestamp) as updated_at
        FROM operation_audit_events
        GROUP BY operation_id
        ORDER BY MAX(id) DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "operation_id": r["operation_id"],
            "container_id": r["container_id"],
            "event_count": r["event_count"],
            "started_at": r["started_at"],
            "updated_at": r["updated_at"]
        }
        for r in rows
    ]
