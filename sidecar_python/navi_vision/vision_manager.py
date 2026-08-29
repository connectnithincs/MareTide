import threading
import time
from . import vision_config
from . import vision_decision
from . import alert_store
from .vision_simulator import VisionSimulator
from .camera_feed import LoopingVideoFeed
from .vision_config import CAMERA_ASSETS, DEFAULT_CAMERA_STATES

class VisionManager:
    """
    Orchestrator for the NAVI-AI Vision Monitoring system.
    Controls the simulation/detection workers, invokes the decision logic,
    and handles alert routing to storage and loop overlays.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.simulator = None
        self.yolo_runner = None
        self.db = None
        
        # Camera states lock and dictionary
        self._state_lock = threading.Lock()
        self.camera_states = {cam_id: True for cam_id in vision_config.CAMERA_IDS}
        
        # Feed source mode: 'simulated' (recorded loop footage) or 'live' (shared webcam)
        self.source_mode = "simulated"
        
        # Create looping video feeds for cargo & ballast
        self.video_feeds = {
            cam_id: LoopingVideoFeed(cam_id, path, manager=self)
            for cam_id, path in CAMERA_ASSETS.items()
        }
        
        # Setup database if enabled in config
        self._init_storage()

    def _init_storage(self):
        if vision_config.ENABLE_SQLITE:
            try:
                from . import vision_db
                self.db = vision_db
                self.db.init_db()
            except Exception as e:
                print(f"Warning: Failed to load SQLite database module: {e}. Falling back to in-memory.")
                self.db = None

    def handle_detection(self, detection):
        """Callback received from simulator or YOLO runner when detection occurs."""
        alert = vision_decision.evaluate(detection, manager=self)
        if alert is None:
            return
        
        camera_map = {
            "Cam 1 - Deck View": "cargo",
            "Cam 2 - Ballast Room": "ballast"
        }
        
        # Throttling check: only log alerts to database/store at most once every 3.0 seconds per category & severity
        now = time.time()
        category = alert.get("category")
        severity = alert.get("severity")
        if severity != "INFO":
            key = (category, severity)
            if hasattr(self, "_last_alert_time") and key in self._last_alert_time and (now - self._last_alert_time[key]) < 3.0:
                # Throttle DB log, but still update camera overlays in real-time
                feed_id = camera_map.get(alert.get("camera"))
                if feed_id and feed_id in self.video_feeds:
                    self.video_feeds[feed_id].update_alert(alert)
                return
            
            if not hasattr(self, "_last_alert_time"):
                self._last_alert_time = {}
            self._last_alert_time[key] = now
        
        # Save alert
        if vision_config.ENABLE_SQLITE and self.db is not None:
            self.db.add_alert(alert)
        else:
            alert_store.add_alert(alert)
            
        # Feed the alert details into the video overlays if it corresponds to cargo/ballast
        feed_id = camera_map.get(alert.get("camera"))
        if feed_id and feed_id in self.video_feeds:
            self.video_feeds[feed_id].update_alert(alert)

    def set_camera_enabled(self, camera_id: str, enabled: bool):
        """Toggles the manual enable state of a camera feed."""
        with self._state_lock:
            if camera_id not in self.camera_states:
                raise KeyError(f"Unknown camera_id '{camera_id}' — check for a typo/mismatch")
            self.camera_states[camera_id] = enabled
            
        if camera_id in self.video_feeds:
            self.video_feeds[camera_id].set_enabled(enabled)
            # If disabling, clear any active alert bounding box on it
            if not enabled:
                self.video_feeds[camera_id].update_alert(None)

    def is_camera_enabled(self, camera_id: str) -> bool:
        """Checks if a camera feed is currently enabled. Raises KeyError for unknown IDs."""
        with self._state_lock:
            if camera_id not in self.camera_states:
                raise KeyError(f"Unknown camera_id '{camera_id}' — check for a typo/mismatch")
            return self.camera_states[camera_id]

    def get_camera_frame(self, camera_id: str):
        """Gets the latest drawn frame from the looping video feed."""
        feed = self.video_feeds.get(camera_id)
        return feed.get_frame() if feed else None

    def start(self):
        """Starts background monitoring threads."""
        with self.lock:
            self.stop_unlocked()
            
            # Re-initialize storage in case config changed
            self._init_storage()
            
            # Start looping video feeds
            for feed in self.video_feeds.values():
                feed.start()
            
            if vision_config.SIMULATION_MODE:
                # Simulator mode: runs all categories
                self.simulator = VisionSimulator(callback=self.handle_detection, manager=self)
                self.simulator.start()
            else:
                # YOLO Mode: Start YOLO runner for Crew Safety & Sea, and Simulator specifically for Cargo & Ballast
                yolo_started = False
                try:
                    from .vision_yolo_runner import VisionYOLORunner
                    self.yolo_runner = VisionYOLORunner(callback=self.handle_detection, manager=self)
                    self.yolo_runner.start()
                    yolo_started = True
                except Exception as e:
                    print(f"Failed to start YOLO runner ({e}). Falling back fully to simulation.")
                    self.yolo_runner = None
                
                # Start simulator. If YOLO is active, only simulate Cargo & Ballast. Else simulate all categories.
                sim_categories = ["Cargo", "Ballast"] if yolo_started else None
                self.simulator = VisionSimulator(callback=self.handle_detection, categories=sim_categories, manager=self)
                self.simulator.start()

    def stop(self):
        """Stops background monitoring threads."""
        with self.lock:
            self.stop_unlocked()

    def stop_unlocked(self):
        # Stop looping video feeds
        for feed in self.video_feeds.values():
            feed.stop()
            
        if self.simulator:
            self.simulator.stop()
            self.simulator = None
        if self.yolo_runner:
            self.yolo_runner.stop()
            self.yolo_runner = None

    def get_latest_frame(self, category):
        """Retrieves the latest annotated frame from the YOLO runner if active."""
        with self.lock:
            if self.yolo_runner and not vision_config.SIMULATION_MODE:
                return self.yolo_runner.get_latest_frame(category)
            return None

    def get_alerts(self, limit=50):
        """Retrieves history of alerts from active storage."""
        if vision_config.ENABLE_SQLITE and self.db is not None:
            return self.db.get_all_alerts(limit)
        return alert_store.get_all_alerts(limit)

    def clear_alerts(self):
        """Clears all history in active storage and clears overlay alerts."""
        if vision_config.ENABLE_SQLITE and self.db is not None:
            self.db.clear_alerts()
        else:
            alert_store.clear_alerts()
            
        # Reset alert overlays on looping videos
        for feed in self.video_feeds.values():
            feed.update_alert(None)

    def set_scenario(self, scenario_name):
        """Updates active scenario in simulator. Also resets feed alert overlays if Normal Voyage."""
        with self.lock:
            if self.simulator:
                self.simulator.set_scenario(scenario_name)
            
            if scenario_name == "Normal Voyage":
                for feed in self.video_feeds.values():
                    feed.update_alert(None)

    def set_source_mode(self, mode: str, device_index: int = 0):
        """
        Switches all four camera feeds between 'simulated' (recorded loop
        footage) and 'live' (a single shared physical webcam). Each tile
        keeps drawing its own overlay/detection logic — only the underlying
        video source changes.
        """
        if mode not in ("simulated", "live"):
            raise ValueError(f"Unknown source mode '{mode}' — expected 'simulated' or 'live'")
        with self.lock:
            self.source_mode = mode
            for feed in self.video_feeds.values():
                feed.set_source(mode, device_index)
            if self.yolo_runner:
                self.yolo_runner.set_source("sea", mode, device_index)

    def get_source_mode(self) -> str:
        """Returns the currently active feed source mode: 'simulated' or 'live'."""
        with self.lock:
            return self.source_mode

_global_manager = None
_global_lock = threading.Lock()

def get_global_manager():
    global _global_manager
    with _global_lock:
        if _global_manager is None:
            _global_manager = VisionManager()
            _global_manager.start()
        return _global_manager
