import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maretide.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    
    conn.commit()
    conn.close()

def log_ballast_operation(op_type, pump_mode, source, dest, qty, remaining_src, final_dest, score_before, score_after, trigger_source):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO cargo_operations 
        (timestamp, event, container_id, weight, bay, side, tier, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, event, container_id, weight, bay, side, tier, source))
    conn.commit()
    conn.close()

def get_ballast_operations(limit=100):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ballast_operations")
    cursor.execute("DELETE FROM cargo_operations")
    conn.commit()
    conn.close()
