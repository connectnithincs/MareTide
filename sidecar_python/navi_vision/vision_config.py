# vision_config.py
"""
Configuration settings for the NAVI-AI Vision Monitoring system.
"""

# If True, the system simulates camera detections. If False, it uses real video / YOLOv8.
SIMULATION_MODE = False

# Toggle database logging (SQLite)
ENABLE_SQLITE = True

# Toggle MQTT decoupling (optional phase)
ENABLE_MQTT = False

# Toggle running YOLOv8 detection for Crew Safety and Sea
ENABLE_YOLO = True

# Active camera sources and their associated categories
ACTIVE_CAMERAS = {
    "Cam 1 - Deck View": "Cargo",
    "Cam 2 - Ballast Room": "Ballast",
    "Cam 4 - Bow Camera": "Sea"
}

# Paths to the simulated camera background loops
CAMERA_ASSETS = {
    "cargo":   "navi_vision/assets/cargo/deck_loop.mp4",
    "ballast": "navi_vision/assets/ballast/room_loop.mp4",
}

# Canonical Camera IDs
CAMERA_IDS = ["cargo", "ballast", "sea"]

# Canonical display labels matching app.py UI
CAMERA_LABELS = {
    "cargo": "Cam 1 - Deck View",
    "ballast": "Cam 2 - Ballast Room",
    "sea": "Cam 4 - Bow Camera (YOLO)"
}

# Translation map for any incoming user-facing names or keys
CAMERA_MAP = {
    "Cam 1 - Deck View": "cargo",
    "Cam 2 - Ballast Room": "ballast",
    "Cam 4 - Bow Camera": "sea",
    "Cam 4 - Bow Camera (YOLO)": "sea",
    "cargo": "cargo",
    "ballast": "ballast",
    "sea": "sea"
}

# Default enable states for cameras
DEFAULT_CAMERA_STATES = {
    "cargo": True,
    "ballast": True,
    "sea": True,
}
