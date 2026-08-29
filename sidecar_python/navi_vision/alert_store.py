import threading
import time
import uuid

class InMemoryAlertStore:
    """
    An in-memory, thread-safe store for vision alerts.
    """
    def __init__(self):
        self.alerts = []
        self.lock = threading.Lock()

    def add_alert(self, alert_dict):
        with self.lock:
            if "id" not in alert_dict or alert_dict["id"] is None:
                alert_dict["id"] = str(uuid.uuid4())
            if "timestamp" not in alert_dict or alert_dict["timestamp"] is None:
                alert_dict["timestamp"] = time.time()
            self.alerts.append(alert_dict)
            return alert_dict

    def get_all_alerts(self, limit=50):
        with self.lock:
            sorted_alerts = sorted(self.alerts, key=lambda x: x.get("timestamp", 0), reverse=True)
            return sorted_alerts[:limit]

    def clear_alerts(self):
        with self.lock:
            self.alerts.clear()

# Global module-level instance for easy import and usage
_store = InMemoryAlertStore()

def add_alert(alert_dict):
    return _store.add_alert(alert_dict)

def get_all_alerts(limit=50):
    return _store.get_all_alerts(limit)

def clear_alerts():
    _store.clear_alerts()
