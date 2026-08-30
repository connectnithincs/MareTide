import threading
import time
import random

class VisionSimulator:
    """
    Simulates camera detection events for Cargo, Ballast, Crew Safety, and Sea categories.
    Emits raw detection events via a callback, checking camera enablement.
    """
    def __init__(self, callback=None, categories=None, manager=None):
        self.callback = callback
        self.categories = categories or ["Cargo", "Ballast", "Crew Safety", "Sea"]
        self.manager = manager
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Scenarios: "Normal Voyage", "Cargo Misplacement", "Ballast Leak", "Crew Intrusion", "Sea Obstacle"
        self.scenario = "Normal Voyage"
        self.last_emitted_scenario = None

    def _is_enabled(self, category):
        """Checks if the camera associated with a category is enabled in the manager."""
        if not self.manager:
            return True
        mapping = {
            "Cargo": "cargo",
            "Ballast": "ballast",
            "Crew Safety": "crew_safety",
            "Sea": "sea"
        }
        return self.manager.is_camera_enabled(mapping.get(category))

    def set_scenario(self, scenario_name):
        """Sets the active scenario and forces an immediate re-evaluation."""
        with self.lock:
            self.scenario = scenario_name

    def start(self):
        """Starts the simulator thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the simulator thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def _run_loop(self):
        while self.running:
            with self.lock:
                current_scenario = self.scenario
                force_emit = (current_scenario != self.last_emitted_scenario)
                if force_emit:
                    self.last_emitted_scenario = current_scenario
            
            detections = []
            
            # Normal Voyage: everything is secure and safe
            if current_scenario == "Normal Voyage":
                if force_emit:
                    if "Cargo" in self.categories and self._is_enabled("Cargo"):
                        detections.append({"category": "Cargo", "type": "normal", "camera": "Cam 1 - Deck View", "confidence": random.uniform(0.95, 0.99)})
                    if "Ballast" in self.categories and self._is_enabled("Ballast"):
                        detections.append({"category": "Ballast", "type": "normal", "camera": "Cam 2 - Ballast Room", "confidence": random.uniform(0.96, 0.99)})
                    if "Crew Safety" in self.categories and self._is_enabled("Crew Safety"):
                        detections.append({"category": "Crew Safety", "type": "normal", "camera": "Cam 3 - Restricted Passage", "confidence": random.uniform(0.98, 0.99)})
                    if "Sea" in self.categories and self._is_enabled("Sea"):
                        detections.append({"category": "Sea", "type": "normal", "camera": "Cam 4 - Bow Camera", "confidence": random.uniform(0.95, 0.98)})
            
            # Cargo Misplacement scenario
            elif current_scenario == "Cargo Misplacement":
                if "Cargo" in self.categories and self._is_enabled("Cargo"):
                    detections.append({"category": "Cargo", "type": "misplaced", "camera": "Cam 1 - Deck View", "confidence": random.uniform(0.85, 0.93)})
                if force_emit:
                    if "Ballast" in self.categories and self._is_enabled("Ballast"):
                        detections.append({"category": "Ballast", "type": "normal", "camera": "Cam 2 - Ballast Room", "confidence": random.uniform(0.96, 0.99)})
                    if "Crew Safety" in self.categories and self._is_enabled("Crew Safety"):
                        detections.append({"category": "Crew Safety", "type": "normal", "camera": "Cam 3 - Restricted Passage", "confidence": random.uniform(0.98, 0.99)})
                    if "Sea" in self.categories and self._is_enabled("Sea"):
                        detections.append({"category": "Sea", "type": "normal", "camera": "Cam 4 - Bow Camera", "confidence": random.uniform(0.95, 0.98)})
            
            # Ballast Leak scenario
            elif current_scenario == "Ballast Leak":
                if "Ballast" in self.categories and self._is_enabled("Ballast"):
                    detections.append({"category": "Ballast", "type": "leak", "camera": "Cam 2 - Ballast Room", "confidence": random.uniform(0.87, 0.94)})
                if force_emit:
                    if "Cargo" in self.categories and self._is_enabled("Cargo"):
                        detections.append({"category": "Cargo", "type": "normal", "camera": "Cam 1 - Deck View", "confidence": random.uniform(0.95, 0.99)})
                    if "Crew Safety" in self.categories and self._is_enabled("Crew Safety"):
                        detections.append({"category": "Crew Safety", "type": "normal", "camera": "Cam 3 - Restricted Passage", "confidence": random.uniform(0.98, 0.99)})
                    if "Sea" in self.categories and self._is_enabled("Sea"):
                        detections.append({"category": "Sea", "type": "normal", "camera": "Cam 4 - Bow Camera", "confidence": random.uniform(0.95, 0.98)})
            
            # Crew Intrusion scenario
            elif current_scenario == "Crew Intrusion":
                if "Crew Safety" in self.categories and self._is_enabled("Crew Safety"):
                    detections.append({"category": "Crew Safety", "type": "intrusion", "camera": "Cam 3 - Restricted Passage", "confidence": random.uniform(0.92, 0.97)})
                if force_emit:
                    if "Cargo" in self.categories and self._is_enabled("Cargo"):
                        detections.append({"category": "Cargo", "type": "normal", "camera": "Cam 1 - Deck View", "confidence": random.uniform(0.95, 0.99)})
                    if "Ballast" in self.categories and self._is_enabled("Ballast"):
                        detections.append({"category": "Ballast", "type": "normal", "camera": "Cam 2 - Ballast Room", "confidence": random.uniform(0.96, 0.99)})
                    if "Sea" in self.categories and self._is_enabled("Sea"):
                        detections.append({"category": "Sea", "type": "normal", "camera": "Cam 4 - Bow Camera", "confidence": random.uniform(0.95, 0.98)})
            
            # Sea Obstacle scenario
            elif current_scenario == "Sea Obstacle":
                if "Sea" in self.categories and self._is_enabled("Sea"):
                    detections.append({"category": "Sea", "type": "obstacle", "camera": "Cam 4 - Bow Camera", "confidence": random.uniform(0.88, 0.95)})
                if force_emit:
                    if "Cargo" in self.categories and self._is_enabled("Cargo"):
                        detections.append({"category": "Cargo", "type": "normal", "camera": "Cam 1 - Deck View", "confidence": random.uniform(0.95, 0.99)})
                    if "Ballast" in self.categories and self._is_enabled("Ballast"):
                        detections.append({"category": "Ballast", "type": "normal", "camera": "Cam 2 - Ballast Room", "confidence": random.uniform(0.96, 0.99)})
                    if "Crew Safety" in self.categories and self._is_enabled("Crew Safety"):
                        detections.append({"category": "Crew Safety", "type": "normal", "camera": "Cam 3 - Restricted Passage", "confidence": random.uniform(0.98, 0.99)})

            # Fire callback if configured
            if self.callback and detections:
                for det in detections:
                    self.callback(det)
            
            # Sleep for 3 seconds, polling at 10Hz to catch scenario changes quickly
            for _ in range(30):
                if not self.running:
                    break
                with self.lock:
                    if self.scenario != current_scenario:
                        break
                time.sleep(0.1)
