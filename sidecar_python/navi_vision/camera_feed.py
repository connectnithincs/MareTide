import cv2
import threading
import time
import os
from PIL import Image, ImageDraw
from .ballast_detector import BallastLeakDetector
from . import vision_decision
from . import alert_store
from .live_camera import SharedWebcam

class LoopingVideoFeed:
    """
    Reads either a looping video file ('simulated' mode) or a live shared
    webcam ('live' mode) and exposes the latest frame, with an alert-driven
    overlay drawn on top (no ML inference). Runs specialized motion leak
    detector on ballast camera when enabled.
    """
    SEVERITY_COLORS = {
        "INFO": (56, 189, 248),      # Light Blue
        "WARNING": (233, 179, 8),     # Amber/Yellow
        "CRITICAL": (220, 38, 38),    # Red
        "EMERGENCY": (220, 38, 38),   # Dark Red
    }

    def __init__(self, camera_id, video_path, manager=None):
        self.camera_id = camera_id
        self.manager = manager
        
        # Handle absolute path resolutions
        if not os.path.isabs(video_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.video_path = os.path.join(base_dir, video_path)
        else:
            self.video_path = video_path
            
        self.running = False
        self.enabled = True
        self.thread = None
        self.lock = threading.Lock()
        self.latest_frame = None
        self.latest_alert = None
        
        # Source mode: 'simulated' (recorded loop) or 'live' (shared webcam)
        self.mode = "simulated"
        self.live_device = 0
        self._mode_lock = threading.Lock()
        self._mode_changed = threading.Event()
        
        # Initialize ballast leak detector for ballast camera
        self.leak_detector = BallastLeakDetector() if camera_id == "ballast" else None

    def set_enabled(self, enabled: bool):
        with self.lock:
            self.enabled = enabled

    def is_enabled(self) -> bool:
        with self.lock:
            return self.enabled

    def set_source(self, mode: str, device_index: int = 0):
        """Switch between 'simulated' (recorded loop video) and 'live' (shared webcam)."""
        if mode not in ("simulated", "live"):
            raise ValueError(f"Unknown source mode '{mode}' — expected 'simulated' or 'live'")
        with self._mode_lock:
            self.mode = mode
            self.live_device = device_index
            self._mode_changed.set()

    def update_alert(self, alert: dict | None):
        with self.lock:
            self.latest_alert = alert

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def get_frame(self):
        with self.lock:
            return self.latest_frame

    def _run_loop(self):
        cap = None
        shared_cam = None

        def open_current_source():
            """(Re)opens whichever source is currently selected, releasing the old one first."""
            nonlocal cap, shared_cam
            if cap is not None:
                cap.release()
                cap = None
            if shared_cam is not None:
                shared_cam.release()
                shared_cam = None

            with self._mode_lock:
                mode = self.mode
                device_index = self.live_device
                self._mode_changed.clear()

            if mode == "live":
                shared_cam = SharedWebcam.get(device_index)
                shared_cam.acquire()
            else:
                cap = cv2.VideoCapture(self.video_path)
            return mode

        current_mode = open_current_source()
        sleep_time = 0.05  # ~20 FPS for a smooth look and low CPU
        
        while self.running:
            if self._mode_changed.is_set():
                current_mode = open_current_source()

            if not self.is_enabled():
                time.sleep(0.3)
                continue

            if current_mode == "live":
                frame = shared_cam.get_frame() if shared_cam else None
                if frame is None:
                    time.sleep(0.1)
                    continue
            else:
                ret, frame = cap.read()
                if not ret:
                    cap.release()
                    time.sleep(1.0)  # Prevent CPU spinning on EOF or read failure
                    cap = cv2.VideoCapture(self.video_path)
                    continue

            # Convert BGR (OpenCV) to RGB (PIL)
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            # Run motion-based ballast leak detector if enabled on this camera
            if self.camera_id == "ballast" and self.leak_detector:
                result = self.leak_detector.detect(frame)
                if result:
                    alert = vision_decision.evaluate(result, manager=self.manager)
                    if alert:
                        # Save alert to SQLite if available, else in-memory
                        if self.manager and self.manager.db is not None:
                            self.manager.db.add_alert(alert)
                        else:
                            alert_store.add_alert(alert)
                        self.update_alert(alert)

            with self.lock:
                alert = self.latest_alert

            # Draw alert overlay box and text
            if alert and alert.get("severity") in self.SEVERITY_COLORS and alert.get("severity") != "INFO":
                draw = ImageDraw.Draw(img)
                color = self.SEVERITY_COLORS[alert["severity"]]
                w, h = img.size
                box = (int(w * 0.2), int(h * 0.25), int(w * 0.8), int(h * 0.8))
                draw.rectangle(box, outline=color, width=4)
                
                label_text = f"{alert.get('category').upper()}: {alert.get('severity')}"
                draw.text((box[0] + 5, box[1] - 22), label_text, fill=color)

            with self.lock:
                self.latest_frame = img

            time.sleep(sleep_time)
            
        if cap is not None:
            cap.release()
        if shared_cam is not None:
            shared_cam.release()
