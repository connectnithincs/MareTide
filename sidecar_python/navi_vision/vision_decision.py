import time

def evaluate(detection, manager=None):
    """
    Evaluates a raw detection dictionary and returns an alert dictionary.
    
    A detection dictionary contains:
    - category: 'Cargo', 'Ballast', 'Crew Safety', or 'Sea'
    - type: The event type (e.g., 'normal', 'misplaced', 'leak', 'intrusion', 'obstacle')
    - camera: Camera source name (e.g., 'Cam 1 - Deck View')
    - confidence: Float (0.0 to 1.0)
    - extra_data: Dict (optional details like bounding box info)
    
    Returns an alert dictionary or None if camera is manually disabled:
    - category: Category of the alert
    - severity: 'INFO', 'WARNING', 'CRITICAL', or 'EMERGENCY'
    - confidence: Confidence score from the detection
    - message: Descriptive message
    - recommendation: Actionable recommendation text
    - camera: Camera source name
    - timestamp: Float timestamp
    """
    camera = detection.get("camera")
    if not camera:
        raise KeyError("Detection dictionary must contain a 'camera' key")
    
    # Lazy import of config's map
    from .vision_config import CAMERA_MAP
    
    camera_key = CAMERA_MAP.get(camera)
    if camera_key is None:
        raise KeyError(f"Unmapped camera label '{camera}' — add it to CAMERA_MAP")
        
    if manager and not manager.is_camera_enabled(camera_key):
        return None  # hard stop — disabled cameras never produce alerts
        
    category = detection.get("category", "Unknown")
    det_type = detection.get("type", "normal")
    confidence = detection.get("confidence", 1.0)
    
    severity = "INFO"
    message = "System status normal."
    recommendation = "No action required."
    
    if category == "Cargo":
        if det_type == "misplaced":
            severity = "CRITICAL"
            message = "Unsecured or misaligned cargo container detected on main deck."
            recommendation = "Dispatch deck officer to inspect lashing bridges and secure cargo container."
        else:
            severity = "INFO"
            message = "Cargo deck stowage scan: all containers secure."
            recommendation = "No action required."
            
    elif category == "Ballast":
        if det_type == "leak":
            severity = "CRITICAL"
            message = "Ballast pump compartment fluid leak/spraying detected."
            recommendation = "Trigger remote isolation valves for Tank Pump Block B2. Dispatch technician to check pump seal integrity."
        elif det_type == "abnormal_level":
            severity = "WARNING"
            message = "Ballast level visual mismatch detected against sensor expectations."
            recommendation = "Cross-reference visual level with digital twin sensor; check valve feedback status."
        else:
            severity = "INFO"
            message = "Ballast pumping station and tanks show visual integrity."
            recommendation = "No action required."
            
    elif category == "Crew Safety":
        if det_type == "intrusion":
            severity = "EMERGENCY"
            message = "Unauthorized crew entry detected in high-voltage / restricted deck zone."
            recommendation = "Initiate bridge safety announcement for restricted zone. Verify crew tracker location."
        else:
            severity = "INFO"
            message = "Restricted safety passage clear."
            recommendation = "No action required."
            
    elif category == "Sea":
        if det_type == "obstacle":
            severity = "EMERGENCY"
            message = "Visual contact: Obstacle or vessel detected in close proximity at bow."
            recommendation = "Sound collision warning. Notify watchstander to verify radar range and prepare manual steering override."
        else:
            severity = "INFO"
            message = "Clear sea lane ahead. Visibility normal."
            recommendation = "No action required."
            
    else:
        # Fallback
        if det_type != "normal":
            severity = "WARNING"
            message = f"Abnormal event of type '{det_type}' detected."
            recommendation = "Review camera log and verify telemetry status."
            
    return {
        "id": None, # Will be set by store/db
        "category": category,
        "severity": severity,
        "confidence": float(confidence),
        "message": message,
        "recommendation": recommendation,
        "camera": camera,
        "timestamp": time.time()
    }
