import sqlite3
import os
import time

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision_alerts.db")

def _get_connection():
    """Helper to return a database connection and cursor."""
    conn = sqlite3.connect(DB_FILE)
    # Return rows as dictionaries
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the SQLite database and creates the alerts table if needed."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vision_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                message TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                camera TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()

def add_alert(alert_dict):
    """Inserts a new alert into the database. Returns the alert dict with its assigned ID."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        timestamp = alert_dict.get("timestamp") or time.time()
        
        cursor.execute("""
            INSERT INTO vision_alerts (category, severity, confidence, message, recommendation, camera, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_dict.get("category", "Unknown"),
            alert_dict.get("severity", "INFO"),
            float(alert_dict.get("confidence", 1.0)),
            alert_dict.get("message", ""),
            alert_dict.get("recommendation", ""),
            alert_dict.get("camera", "Unknown Camera"),
            timestamp
        ))
        conn.commit()
        
        # Update the dict with the new database ID and timestamp
        alert_dict["id"] = cursor.lastrowid
        alert_dict["timestamp"] = timestamp
        return alert_dict
    finally:
        conn.close()

def get_all_alerts(limit=50):
    """Retrieves all alerts sorted by timestamp descending, up to the specified limit."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, category, severity, confidence, message, recommendation, camera, timestamp
            FROM vision_alerts
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        alerts = []
        for r in rows:
            alerts.append({
                "id": r["id"],
                "category": r["category"],
                "severity": r["severity"],
                "confidence": r["confidence"],
                "message": r["message"],
                "recommendation": r["recommendation"],
                "camera": r["camera"],
                "timestamp": r["timestamp"]
            })
        return alerts
    finally:
        conn.close()

def clear_alerts():
    """Clears all records in the vision_alerts table."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vision_alerts")
        conn.commit()
    finally:
        conn.close()
