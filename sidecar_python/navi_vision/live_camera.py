import threading
import time
import cv2


class SharedWebcam:
    """
    Singleton wrapper around a single physical camera device.

    Multiple camera tiles (cargo, ballast, crew_safety, sea) can all be
    switched to 'Live' mode at once, but they must NOT each open their own
    cv2.VideoCapture on the same device index — most camera drivers only
    allow one exclusive handle. Instead, every consumer calls
    SharedWebcam.get(device_index) to get back the *same* instance, which
    reads frames in a single background thread. Consumers acquire()/release()
    to reference-count usage so the device is only opened while at least one
    tile actually needs it, and cleanly released when none do.
    """
    _instances = {}
    _instances_lock = threading.Lock()

    def __init__(self, device_index=0):
        self.device_index = device_index
        try:
            self.source = int(device_index)
        except (ValueError, TypeError):
            self.source = device_index
            
        self.lock = threading.Lock()
        self.cap = None
        self.latest_frame = None
        self.running = False
        self.thread = None
        self.ref_count = 0

    @classmethod
    def get(cls, device_index=0):
        """Returns the shared instance for a given device index, creating it if needed."""
        with cls._instances_lock:
            if device_index not in cls._instances:
                cls._instances[device_index] = SharedWebcam(device_index)
            return cls._instances[device_index]

    def acquire(self):
        """Registers one more consumer of this webcam; opens the device on first use."""
        with self.lock:
            self.ref_count += 1
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self._run_loop, daemon=True)
                self.thread.start()

    def release(self):
        """Unregisters one consumer; closes the device once nobody needs it anymore."""
        with self.lock:
            self.ref_count = max(0, self.ref_count - 1)
            if self.ref_count == 0:
                self.running = False

    def _run_loop(self):
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            print(f"ERROR: Could not open live camera source: {self.source}")
        else:
            print(f"SUCCESS: Opened live camera source: {self.source}")

        while self.running:
            if not cap.isOpened():
                time.sleep(0.5)
                continue
            ret, frame = cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.latest_frame = frame
            else:
                time.sleep(0.1)
            time.sleep(0.03)  # cap capture rate around ~30 FPS

        cap.release()
        with self.lock:
            self.latest_frame = None
        print(f"INFO: Live camera device index {self.device_index} released")

    def get_frame(self):
        """Returns the most recent raw BGR frame, or None if not available yet."""
        with self.lock:
            return None if self.latest_frame is None else self.latest_frame.copy()
