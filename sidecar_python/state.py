"""
Global State & Telemetry Integration Coordinator for MareTide.
Connects the decoupled TelemetryManager to the vessel model, Digital Twin,
and operational flow stage.
"""

import threading
import time
import datetime
from ship import Ship, BallastTank, Container, StabilityAnalyzer, RecommendationEngine
from navi_vision.vision_manager import get_global_manager
from serial_reader import SerialTelemetryReader
from reports.logs_db import log_ballast_operation, log_cargo_operation
from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    ALLOWED_WEIGHT_SOURCES,
    FORBIDDEN_WEIGHT_SOURCES,
    DOCUMENT_AI_CARGO_MASS,
    LOAD_CELL_CARGO_MASS,
    HARDWARE_TELEMETRY_LABEL,
    assert_authoritative_source
)
from telemetry.manager import TelemetryManager
from telemetry.models import TelemetrySource, ConnectionStatus


# --- SINGLETON STATE ACCESSORS ---
_ship = None
_reader = None
_vision_manager = None
_state_lock = threading.Lock()

# --- STATE MACHINE VARIABLES ---
iot_flow_stage = "WAITING_FOR_CARGO"
planned_container = {}
last_loaded_weight = 0.0

def reset_ship():
    global _ship
    with _state_lock:
        _ship = Ship(name="MareTide Vessel", num_bays=4)
        for i in range(1, 5):
            _ship.tanks[f"port_{i}"] = BallastTank(f"Port-{i}", 300, 300)
            _ship.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)
    return _ship

def reset_state():
    global _ship, iot_flow_stage, planned_container, last_loaded_weight
    with _state_lock:
        _ship = Ship(name="MareTide Vessel", num_bays=4)
        for i in range(1, 5):
            _ship.tanks[f"port_{i}"] = BallastTank(f"Port-{i}", 300, 300)
            _ship.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)
        iot_flow_stage = "WAITING_FOR_CARGO"
        planned_container = {}
        last_loaded_weight = 0.0
    return _ship

active_rec_bay = 1
active_rec_side = "port"
last_rec_bay = None
last_rec_side = None
rec_change_time = 0.0

latest_telemetry = {
    "roll": 0.0,
    "pitch": 0.0,
    "distance": 30.0,
    "ballast_pct": 100.0,
    "cargo_kg": 0.0,
    "status": "IDLE",
    "risk": "SAFE"
}

# --- STABILITY UTILS ---
def get_normalized_stability(ship_obj, roll, pitch):
    list_v = StabilityAnalyzer.calculate_list(ship_obj)
    trim_v = StabilityAnalyzer.calculate_trim(ship_obj)
    
    # 1. Roll Component (Safe ±5°, Critical at 15°)
    roll_norm = (abs(roll) / 5.0) * 20.0
    # 2. Pitch Component (Safe ±3°, Critical at 9°)
    pitch_norm = (abs(pitch) / 3.0) * 20.0
    # 3. List Component (Safe ±50t, Critical at 250t)
    list_norm = (abs(list_v) / 100.0) * 40.0
    # 4. Trim Component (Safe ±50t, Critical at 250t)
    trim_norm = (abs(trim_v) / 100.0) * 40.0
    
    # Combine (worst-case maximum logic)
    score = max(roll_norm, pitch_norm, list_norm, trim_norm)
    score = max(0.0, min(100.0, score))  # strict clamping
    
    if score <= 20:
        label = "Excellent"
        risk = "SAFE"
    elif score <= 40:
        label = "Good"
        risk = "SAFE"
    elif score <= 60:
        label = "Moderate"
        risk = "WARNING"
    elif score <= 80:
        label = "Warning"
        risk = "WARNING"
    else:
        label = "Critical"
        risk = "CRITICAL"
        
    return score, label, risk

# --- STATE LIFECYCLE ---
def get_current_ship() -> Ship:
    global _ship
    with _state_lock:
        if _ship is None:
            _ship = Ship(name="MareTide Vessel", num_bays=4)
            for i in range(1, 5):
                _ship.tanks[f"port_{i}"] = BallastTank(f"Port-{i}", 300, 300)
                _ship.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)
        return _ship

def get_current_reader() -> SerialTelemetryReader:
    global _reader
    with _state_lock:
        if _reader is None:
            _reader = SerialTelemetryReader(is_simulated=True)
            _reader.start()
        return _reader

def get_vision_manager():
    global _vision_manager
    with _state_lock:
        if _vision_manager is None:
            _vision_manager = get_global_manager()
        return _vision_manager

def reconnect_reader(port: str, is_simulated: bool):
    global _reader
    with _state_lock:
        if _reader:
            _reader.stop()
        
        if is_simulated:
            _reader = SerialTelemetryReader(is_simulated=True)
            TelemetryManager.get_instance().select_source(TelemetrySource.SIMULATED_TELEMETRY)
        else:
            _reader = SerialTelemetryReader(port=port, is_simulated=False)
            TelemetryManager.get_instance().select_source(TelemetrySource.HARDWARE_SENSOR, port=port)
        _reader.start()
    return _reader

# --- TELEMETRY STATE MACHINE TICK ---
def process_telemetry_tick(roll_val, pitch_val, cargo_kg_val, distance_val, ballast_pct_val, status_val, reader_connected_val):
    global iot_flow_stage, planned_container, last_loaded_weight
    global active_rec_bay, active_rec_side, last_rec_bay, last_rec_side, rec_change_time
    global latest_telemetry

    ship = get_current_ship()
    
    # Store latest telemetry values (Strict Phase 5 Policy: cargo_kg is always 0.0)
    latest_telemetry = {
        "roll": roll_val,
        "pitch": pitch_val,
        "distance": distance_val,
        "ballast_pct": ballast_pct_val,
        "cargo_kg": 0.0,
        "status": status_val,
        "risk": get_normalized_stability(ship, roll_val, pitch_val)[2]
    }

    current_stage = iot_flow_stage

    if current_stage == "DRAINING" and str(status_val).strip().upper() == "READY":
        if planned_container:
            cid = planned_container["id"]
            bay = planned_container["bay"]
            side = planned_container["side"]
            tier = planned_container["tier"]
            weight_t = planned_container["weight"]

            # Auto-increment tier if slot is occupied
            actual_tier = tier
            while ship.slot_occupied(bay, side, actual_tier):
                actual_tier += 1

            score_before, _, _ = get_normalized_stability(ship, roll_val, pitch_val)

            c = Container(id=cid, weight=weight_t, bay=bay, side=side, tier=actual_tier)
            ship.add_container(c)

            # Sync virtual ballast tank
            tank_key = f"{side}_{bay}"
            if tank_key in ship.tanks:
                starting_vol = ship.tanks[tank_key].current_volume
                final_vol = (ballast_pct_val / 100.0) * ship.tanks[tank_key].capacity
                ship.tanks[tank_key].current_volume = final_vol
                qty_drained = max(0.0, starting_vol - final_vol)

                score_after, _, _ = get_normalized_stability(ship, roll_val, pitch_val)

                log_ballast_operation(
                    op_type="Drain",
                    pump_mode="Automatic",
                    source=f"{side.upper()}-TANK-{bay}",
                    dest="Sea",
                    qty=qty_drained,
                    remaining_src=final_vol,
                    final_dest=0.0,
                    score_before=score_before,
                    score_after=score_after,
                    trigger_source="AI"
                )

            src_mode = "ESP32" if reader_connected_val else "Simulation"
            log_cargo_operation("LOAD", cid, weight_t, bay, side, actual_tier, src_mode)

            iot_flow_stage = "COMPLETED"

    # --- RECOMMENDATION COMPONENT (Based on 20t standard reference or planned cargo) ---
    rec_bay, rec_side, rec_score = RecommendationEngine.best_position(ship, 20.0)

    now = time.time()
    if last_rec_bay is None or last_rec_side is None:
        last_rec_bay = rec_bay
        last_rec_side = rec_side
        rec_change_time = now
        active_rec_bay = rec_bay if rec_bay else 1
        active_rec_side = rec_side if rec_side else "port"

    if rec_bay != last_rec_bay or rec_side != last_rec_side:
        last_rec_bay = rec_bay
        last_rec_side = rec_side
        rec_change_time = now

    if now - rec_change_time >= 5.0:
        active_rec_bay = rec_bay if rec_bay else 1
        active_rec_side = rec_side if rec_side else "port"

# --- RUN STATE LOOP ---
def run_telemetry_loop():
    while True:
        try:
            mgr = TelemetryManager.get_instance()
            norm = mgr.get_latest_telemetry()
            
            # Extract first tank level / distance
            first_tank = next(iter(norm.ballast_tanks.values()), None)
            dist_val = first_tank.distance_cm if first_tank else 10.0
            ballast_val = first_tank.level_pct if first_tank else 100.0
            
            process_telemetry_tick(
                roll_val=norm.vessel_state.roll_deg,
                pitch_val=norm.vessel_state.pitch_deg,
                cargo_kg_val=0.0,  # Zero load-cell coupling
                distance_val=dist_val,
                ballast_pct_val=ballast_val,
                status_val=norm.operational_telemetry.status,
                reader_connected_val=(norm.source == TelemetrySource.HARDWARE_SENSOR and norm.connection_status == ConnectionStatus.CONNECTED)
            )
        except Exception as e:
            pass
        time.sleep(0.05)  # 20 Hz tick with proper sleep

# --- PHASE 5 OPERATIONAL INTEGRATION HELPERS ---
def get_operational_status():
    ship = get_current_ship()
    mgr = TelemetryManager.get_instance()
    norm = mgr.get_latest_telemetry()
    legacy_dict = mgr.get_legacy_telemetry_dict()
    
    score, label, risk = get_normalized_stability(ship, norm.vessel_state.roll_deg, norm.vessel_state.pitch_deg)
    
    total_cargo_t = round(float(ship.total_cargo_weight()), 2)
    total_ballast_t = round(float(ship.total_ballast_weight()), 2)
    list_t = round(float(StabilityAnalyzer.calculate_list(ship)), 2)
    trim_t = round(float(StabilityAnalyzer.calculate_trim(ship)), 2)
    
    return {
        "operational_stage": iot_flow_stage,
        "ship_name": ship.name,
        "total_containers": len(ship.containers),
        "total_cargo_weight_t": total_cargo_t,
        "total_ballast_weight_t": total_ballast_t,
        "list_t": list_t,
        "trim_t": trim_t,
        "stability_score": round(float(score), 2),
        "risk_level": risk,
        "telemetry": legacy_dict,
        "normalized_telemetry": norm.model_dump(),
        "telemetry_source": norm.source.value,
        "connection_status": norm.connection_status.value,
        "data_quality": norm.metadata.data_quality.value,
        "authoritative_weight_source": PROVENANCE_LABEL,
        "container_weight_source": CONTAINER_WEIGHT_SOURCE,
        "document_ai_cargo_mass": DOCUMENT_AI_CARGO_MASS,
        "load_cell_cargo_mass": LOAD_CELL_CARGO_MASS,
        "hardware_telemetry_label": HARDWARE_TELEMETRY_LABEL,
        "load_cell_policy": "FORBIDDEN_FOR_CARGO_AND_STABILITY"
    }


def reset_operational_stage():
    global iot_flow_stage, planned_container, last_loaded_weight
    with _state_lock:
        iot_flow_stage = "WAITING_FOR_CARGO"
        planned_container = {}
        last_loaded_weight = 0.0
    return True

# Start telemetry integration loop inside daemon thread
threading.Thread(target=run_telemetry_loop, daemon=True).start()
