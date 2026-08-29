import threading
import time
import os
import sys
import cv2
import numpy as np
from ultralytics import YOLO
from .live_camera import SharedWebcam

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
        sys.stdout.flush()
    except Exception:
        pass

class _ChannelSource:
    """
    Manages the active video source for a single YOLO channel (crew_safety
    or sea): either a recorded looping video file ('simulated') or a shared
    live webcam ('live'). Handles opening/reopening/releasing cleanly when
    the mode is switched at runtime.
    """
    def __init__(self, video_path):
        self.video_path = video_path
        self.mode = "simulated"
        self.device_index = 0
        self.cap = None
        self.shared_cam = None

    def set_mode(self, mode, device_index=0):
        self.mode = mode
        self.device_index = device_index

    def open(self):
        """(Re)opens whichever source is currently selected, releasing the old one first."""
        self.close()
        if self.mode == "live":
            self.shared_cam = SharedWebcam.get(self.device_index)
            self.shared_cam.acquire()
        else:
            self.cap = cv2.VideoCapture(self.video_path)

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.shared_cam is not None:
            self.shared_cam.release()
            self.shared_cam = None

    def read(self):
        """Returns (ret, frame) matching cv2.VideoCapture.read() semantics."""
        if self.mode == "live":
            frame = self.shared_cam.get_frame() if self.shared_cam else None
            return (frame is not None), frame
        if self.cap is None:
            return False, None
        ret, frame = self.cap.read()
        if not ret:
            # Loop the recorded video on EOF/read failure
            self.cap.release()
            time.sleep(1.0)  # Prevent CPU spinning on EOF or read failure
            self.cap = cv2.VideoCapture(self.video_path)
            ret, frame = self.cap.read()
        return ret, frame


class VisionYOLORunner:
    """
    Runs YOLOv8 object detection on the Crew Safety and Sea lane channels.
    Each channel's video source can independently be 'simulated' (recorded
    loop footage) or 'live' (shared physical webcam) via set_source().
    Updates annotated frames for real-time dashboard display.
    """
    def __init__(self, callback=None, manager=None):
        safe_print("DEBUG: VisionYOLORunner.__init__ starting")
        self.callback = callback
        self.manager = manager
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Latest annotated RGB frames
        self.frames = {
            "Crew Safety": None,
            "Sea": None
        }
        
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        model_path = os.path.join(os.path.dirname(self.base_dir), "yolov8n.pt")
        if not os.path.exists(model_path):
            model_path = os.path.join(os.path.dirname(os.path.dirname(self.base_dir)), "yolov8n.pt")
            if not os.path.exists(model_path):
                model_path = "yolov8n.pt"
        try:
            self.model = YOLO(model_path)
            safe_print(f"YOLO model loaded successfully from: {model_path}")
        except Exception as e:
            safe_print(f"ERROR: Failed to load YOLO model: {e}")
            self.model = YOLO("yolov8n.pt")

        crew_path = os.path.join(self.base_dir, "assets", "crew_safety", "video.mp4")
        sea_path = os.path.join(self.base_dir, "assets", "sea", "video.mp4")

        self._sources = {
            "crew_safety": _ChannelSource(crew_path),
            "sea": _ChannelSource(sea_path),
        }
        self._source_lock = threading.Lock()
        self._source_changed = threading.Event()

    def set_source(self, camera_key: str, mode: str, device_index: int = 0):
        """camera_key: 'crew_safety' or 'sea'. mode: 'simulated' or 'live'."""
        if camera_key not in self._sources:
            raise KeyError(f"Unknown camera_key '{camera_key}' — expected 'crew_safety' or 'sea'")
        if mode not in ("simulated", "live"):
            raise ValueError(f"Unknown source mode '{mode}' — expected 'simulated' or 'live'")
        with self._source_lock:
            self._sources[camera_key].set_mode(mode, device_index)
            self._source_changed.set()

    def start(self):
        """Starts the YOLO runner daemon thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the YOLO runner thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None

    def get_latest_frame(self, category):
        """Returns the latest annotated RGB frame for the specified category."""
        with self.lock:
            return self.frames.get(category)

    def _is_enabled(self, camera_key):
        if not self.manager:
            return True
        return self.manager.is_camera_enabled(camera_key)

    def _run_loop(self):
        safe_print("DEBUG: _run_loop thread has started executing")
        crew_source = self._sources["crew_safety"]
        sea_source = self._sources["sea"]

        crew_source.open()
        sea_source.open()

        if crew_source.mode == "simulated":
            if crew_source.cap and crew_source.cap.isOpened():
                safe_print(f"SUCCESS: Opened crew safety video path: {crew_source.video_path}")
            else:
                safe_print(f"ERROR: Failed to open crew safety video path: {crew_source.video_path}")

        if sea_source.mode == "simulated":
            if sea_source.cap and sea_source.cap.isOpened():
                safe_print(f"SUCCESS: Opened sea video path: {sea_source.video_path}")
            else:
                safe_print(f"ERROR: Failed to open sea video path: {sea_source.video_path}")

        frame_counter = 0

        while self.running:
            if self._source_changed.is_set():
                with self._source_lock:
                    self._source_changed.clear()
                crew_source.open()
                sea_source.open()

            crew_enabled = self._is_enabled("crew_safety")
            sea_enabled = self._is_enabled("sea")
            
            if not crew_enabled and not sea_enabled:
                time.sleep(0.3)
                continue
                
            # Process Crew Safety
            if crew_enabled:
                ret, frame = crew_source.read()
                    
                if ret and frame is not None:
                    # Run YOLOv8 on the frame (only filter for 'person', class 0)
                    results = self.model(frame, classes=[0], verbose=False)
                    
                    h, w, _ = frame.shape
                    # Define a restricted safety zone polygon in the center-right part of the corridor
                    poly = [
                        (int(w * 0.45), int(h * 0.2)), 
                        (int(w * 0.95), int(h * 0.2)), 
                        (int(w * 0.95), int(h * 0.95)), 
                        (int(w * 0.45), int(h * 0.95))
                    ]
                    pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                    
                    # Draw restricted passage zone polygon
                    cv2.polylines(frame, [pts], True, (0, 255, 255), 2)
                    cv2.putText(frame, "RESTRICTED PASSAGE ZONE", (poly[0][0], poly[0][1] - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                    
                    intrusion_detected = False
                    highest_conf = 0.0
                    
                    for result in results:
                        boxes = result.boxes
                        for box in boxes:
                            conf = float(box.conf[0])
                            xyxy = box.xyxy[0].cpu().numpy()
                            x1, y1, x2, y2 = map(int, xyxy)
                            
                            # Bounding box center
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                            
                            # Check if the person is inside the restricted zone
                            dist = cv2.pointPolygonTest(pts, (cx, cy), False)
                            in_zone = dist >= 0
                            
                            color = (0, 0, 255) if in_zone else (0, 255, 0) # Red if inside zone, else Green
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(frame, f"Person {conf * 100:.1f}%", (x1, y1 - 10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                            
                            if in_zone:
                                intrusion_detected = True
                                highest_conf = max(highest_conf, conf)
                                
                    # Emit alert periodically or immediately on change
                    try:
                        if intrusion_detected:
                            if self.callback:
                                self.callback({
                                    "category": "Crew Safety",
                                    "type": "intrusion",
                                    "camera": "Cam 3 - Restricted Passage",
                                    "confidence": highest_conf
                                })
                        else:
                            # Periodically emit normal status (e.g., every 30 frames)
                            if frame_counter % 30 == 0 and self.callback:
                                self.callback({
                                    "category": "Crew Safety",
                                    "type": "normal",
                                    "camera": "Cam 3 - Restricted Passage",
                                    "confidence": 0.99
                                })
                    except Exception as e:
                        safe_print(f"ERROR: Crew Safety detection callback failed: {e}")
                            
                    # Save annotated frame as RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    with self.lock:
                        self.frames["Crew Safety"] = frame_rgb

            # Process Sea Lane
            if sea_enabled:
                ret, frame = sea_source.read()
                    
                if ret and frame is not None:
                    # Run YOLOv8 on the frame (detect car/truck/boat; classes [2, 7, 8])
                    results = self.model(frame, classes=[2, 7, 8], verbose=False)
                    
                    obstacle_detected = False
                    highest_conf = 0.0
                    
                    for result in results:
                        boxes = result.boxes
                        for box in boxes:
                            conf = float(box.conf[0])
                            xyxy = box.xyxy[0].cpu().numpy()
                            x1, y1, x2, y2 = map(int, xyxy)
                            
                            # Estimate proximity using bounding box area
                            area = (x2 - x1) * (y2 - y1)
                            is_close = area > 28000 # Area threshold for close proximity obstacle
                            
                            color = (0, 0, 255) if is_close else (255, 0, 0) # Red if close, else Blue
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            label = "CLOSE OBSTACLE" if is_close else "TRACKED OBSTACLE"
                            cv2.putText(frame, f"{label} {conf * 100:.1f}%", (x1, y1 - 10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                            
                            if is_close:
                                obstacle_detected = True
                                highest_conf = max(highest_conf, conf)
                                
                    try:
                        if obstacle_detected:
                            cv2.putText(frame, "⚠️ COLLISION RISK WARNING", (30, 50), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                            if self.callback:
                                self.callback({
                                    "category": "Sea",
                                    "type": "obstacle",
                                    "camera": "Cam 4 - Bow Camera",
                                    "confidence": highest_conf
                                })
                        else:
                            if frame_counter % 30 == 0 and self.callback:
                                self.callback({
                                    "category": "Sea",
                                    "type": "normal",
                                    "camera": "Cam 4 - Bow Camera",
                                    "confidence": 0.99
                                })
                    except Exception as e:
                        safe_print(f"ERROR: Sea lane detection callback failed: {e}")
                            
                    # Save annotated frame as RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    with self.lock:
                        self.frames["Sea"] = frame_rgb
                        
            frame_counter += 1
            # Sleep slightly to maintain ~10 FPS (100ms cycle)
            time.sleep(0.1)
            
        # Clean up
        crew_source.close()
        sea_source.close()
