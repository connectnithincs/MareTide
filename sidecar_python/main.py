import io
import time
import cv2
from PIL import Image
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Initialize databases
from reports.logs_db import init_db, get_ballast_operations, get_cargo_operations, clear_logs
init_db()

import state
from voyage.ship_profile import get_current_ship_profile
from voyage.myshiptracking import MyShipTrackingClient
from serial_reader import SerialTelemetryReader

app = FastAPI(title="MareTide Python Sidecar", version="3.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="http://localhost:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frame encoding helper
def encode_frame(frame):
    if frame is None:
        return None
    # If PIL Image (used by looping feeds)
    if isinstance(frame, Image.Image):
        buf = io.BytesIO()
        frame.save(buf, format="JPEG")
        return buf.getvalue()
    # If NumPy array (used by YOLO runner)
    elif hasattr(frame, "shape"):
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        success, encoded = cv2.imencode(".jpg", frame_bgr)
        if success:
            return encoded.tobytes()
    # If already raw bytes
    elif isinstance(frame, bytes):
        return frame
    return None

# Camera MJPEG frame generator
def frame_generator(cam_id):
    manager = state.get_vision_manager()
    while True:
        frame = None
        if cam_id in ["crew_safety", "sea"]:
            yolo_key = "Crew Safety" if cam_id == "crew_safety" else "Sea"
            frame = manager.get_latest_frame(yolo_key)
        else:
            frame = manager.get_camera_frame(cam_id)
            
        encoded = encode_frame(frame)
        if encoded:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + encoded + b'\r\n')
        else:
            # Fallback blank frame if offline/loading
            time.sleep(0.1)
        time.sleep(0.05)  # Cap at ~20 FPS

# --- REST ENDPOINTS ---

_is_manual_pumping = False

@app.get("/api/vessel-state")
async def get_vessel_state():
    ship = state.get_current_ship()
    telemetry = state.latest_telemetry
    
    score, label, risk = state.get_normalized_stability(ship, telemetry["roll"], telemetry["pitch"])
    
    # Format ballast tanks
    tanks_dict = {}
    for k, tank in ship.tanks.items():
        tanks_dict[k] = {
            "name": tank.name,
            "current_volume": tank.current_volume,
            "capacity": tank.capacity,
            "fill_ratio": tank.fill_ratio
        }
        
    # Format cargo containers
    containers_list = [
        {
            "id": c.id,
            "weight": c.weight,
            "bay": c.bay,
            "side": c.side,
            "tier": c.tier
        }
        for c in ship.containers
    ]
    
    return {
        "ship_name": ship.name,
        "roll": telemetry["roll"],
        "pitch": telemetry["pitch"],
        "distance": telemetry["distance"],
        "ballast_pct": telemetry["ballast_pct"],
        "cargo_kg": telemetry["cargo_kg"],
        "cargo_t": telemetry["cargo_kg"] * 10.0,
        "status": telemetry["status"],
        "stability_score": score,
        "stability_label": label,
        "stability_risk": risk,
        "is_simulated": state.get_current_reader().is_simulated,
        "iot_flow_stage": state.iot_flow_stage,
        "planned_container": state.planned_container,
        "active_rec_bay": state.active_rec_bay,
        "active_rec_side": state.active_rec_side,
        "ballast_tanks": tanks_dict,
        "containers": containers_list,
        "is_pumping": _is_manual_pumping
    }

@app.post("/api/ballast/calculate-compensation")
async def calculate_compensation(req: Request):
    body = await req.json()
    planned_id = body.get("id", "").strip()
    bay = int(body.get("bay", 1))
    side = body.get("side", "port")
    tier = int(body.get("tier", 1))
    
    if not planned_id:
        raise HTTPException(status_code=400, detail="Container ID cannot be empty")
        
    cargo_kg = state.latest_telemetry["cargo_kg"]
    cargo_t = cargo_kg * 10.0
    
    ship = state.get_current_ship()
    already_loaded = sum(c.weight for c in ship.containers if c.bay == bay and c.side.lower() == side.lower())
    tank_key = f"{side.lower()}_{bay}"
    tank_capacity = ship.tanks[tank_key].capacity if tank_key in ship.tanks else 300.0
    remaining_capacity = tank_capacity - already_loaded
    
    if cargo_t > remaining_capacity:
        raise HTTPException(
            status_code=400, 
            detail=f"NO SPACE: Cargo weight {cargo_t:.1f}t exceeds remaining tank capacity {remaining_capacity:.1f}t"
        )
        
    state.planned_container = {
        "id": planned_id,
        "bay": bay,
        "side": side,
        "tier": tier,
        "weight": cargo_t
    }
    state.iot_flow_stage = "CONFIRM_COMPENSATION"
    return {"success": True, "stage": state.iot_flow_stage}

@app.post("/api/ballast/confirm-drain")
async def confirm_drain():
    cargo_kg = state.latest_telemetry["cargo_kg"]
    reader = state.get_current_reader()
    reader.send_drain_command(cargo_kg)
    state.iot_flow_stage = "DRAINING"
    return {"success": True, "stage": state.iot_flow_stage}

@app.post("/api/ballast/clear-scale")
async def clear_scale():
    if state.get_current_reader().is_simulated:
        state.get_current_reader().reset_simulated_cargo()
    state.iot_flow_stage = "WAITING_FOR_CARGO"
    state.planned_container = {}
    return {"success": True, "stage": state.iot_flow_stage}

@app.post("/api/ballast/adjust")
async def ballast_adjust(req: Request):
    body = await req.json()
    tank_key = body.get("tank_key")
    action = body.get("action")  # "fill" or "drain"
    qty = float(body.get("qty", 10.0))
    
    ship = state.get_current_ship()
    if tank_key in ship.tanks:
        tank = ship.tanks[tank_key]
        score_before, _, _ = state.get_normalized_stability(ship, state.latest_telemetry["roll"], state.latest_telemetry["pitch"])
        
        if action == "fill":
            tank.current_volume = min(tank.capacity, tank.current_volume + qty)
        else:
            tank.current_volume = max(0.0, tank.current_volume - qty)
            
        score_after, _, _ = state.get_normalized_stability(ship, state.latest_telemetry["roll"], state.latest_telemetry["pitch"])
        
        from reports.logs_db import log_ballast_operation
        log_ballast_operation(
            op_type=action.capitalize(),
            pump_mode="Manual",
            source="Manual Input" if action == "fill" else f"{tank_key.upper()}",
            dest=f"{tank_key.upper()}" if action == "fill" else "Sea",
            qty=qty,
            remaining_src=tank.current_volume,
            final_dest=tank.current_volume,
            score_before=score_before,
            score_after=score_after,
            trigger_source="User"
        )
        return {"success": True, "volume": tank.current_volume}
    raise HTTPException(status_code=400, detail="Invalid tank key")

import asyncio

async def gradual_ballast_pump(p_from: str, p_to: str, p_amt: float, score_before: float, from_bay: str, to_bay: str):
    global _is_manual_pumping
    try:
        ship = state.get_current_ship()
        rate_t_per_sec = 8.5  # 0.85 L/s scale = 8.5 t/s virtual
        tick_interval_sec = 0.1
        increment_per_tick = rate_t_per_sec * tick_interval_sec  # 0.85 t per tick
        
        remaining = p_amt
        total_moved = 0.0
        
        while remaining > 0.0:
            step = min(remaining, increment_per_tick)
            
            # Perform step
            if p_to == "Drain (Sea)":
                to_drain = step
                drained_in_step = 0.0
                tanks_to_drain = []
                for key, tank in ship.tanks.items():
                    if key.startswith(p_from):
                        bay_num = key.split("_")[1]
                        if from_bay == "All" or str(from_bay) == str(bay_num):
                            tanks_to_drain.append(tank)
                for tank in tanks_to_drain:
                    if to_drain > 0:
                        rem = tank.remove_water(to_drain)
                        to_drain -= rem
                        drained_in_step += rem
                if drained_in_step <= 0.0:
                    break
                total_moved += drained_in_step
            else:
                src_tanks = []
                for key, tank in ship.tanks.items():
                    if key.startswith(p_from):
                        bay_num = key.split("_")[1]
                        if from_bay == "All" or str(from_bay) == str(bay_num):
                            src_tanks.append(tank)
                dest_tanks = []
                for key, tank in ship.tanks.items():
                    if key.startswith(p_to):
                        bay_num = key.split("_")[1]
                        if to_bay == "All" or str(to_bay) == str(bay_num):
                            dest_tanks.append(tank)
                moved_in_step = 0.0
                to_move = step
                src_drained = 0.0
                drained_from_each = {}
                for tank in src_tanks:
                    if to_move > 0:
                        rem = tank.remove_water(to_move)
                        to_move -= rem
                        src_drained += rem
                        drained_from_each[tank] = rem
                to_add = src_drained
                for tank in dest_tanks:
                    if to_add > 0:
                        space = tank.capacity - tank.current_volume
                        added = min(to_add, space)
                        tank.current_volume += added
                        to_add -= added
                        moved_in_step += added
                if to_add > 0:
                    for tank, rem in drained_from_each.items():
                        if to_add > 0:
                            put_back = min(to_add, rem)
                            tank.current_volume += put_back
                            to_add -= put_back
                            moved_in_step -= put_back
                if moved_in_step <= 0.0:
                    break
                total_moved += moved_in_step
                
            remaining -= step
            await asyncio.sleep(tick_interval_sec)
            
        # Log to DB when complete
        from reports.logs_db import log_ballast_operation
        src_label = f"{p_from.upper()} Bay {from_bay}" if from_bay != "All" else f"{p_from.upper()} Tanks"
        dest_label = "Sea" if p_to == "Drain (Sea)" else (f"{p_to.upper()} Bay {to_bay}" if to_bay != "All" else f"{p_to.upper()} Tanks")
        
        if p_to == "Drain (Sea)":
            score_after, _, _ = state.get_normalized_stability(ship, state.latest_telemetry["roll"] - (total_moved * 0.05 if p_from == "port" else -total_moved * 0.05), state.latest_telemetry["pitch"])
            log_ballast_operation(
                op_type="Drain",
                pump_mode="Manual",
                source=src_label,
                dest=dest_label,
                qty=total_moved,
                remaining_src=ship.ballast_port() if p_from == "port" else ship.ballast_starboard(),
                final_dest=0.0,
                score_before=score_before,
                score_after=score_after,
                trigger_source="Manual"
            )
        else:
            score_after, _, _ = state.get_normalized_stability(ship, state.latest_telemetry["roll"], state.latest_telemetry["pitch"])
            log_ballast_operation(
                op_type="Transfer",
                pump_mode="Manual",
                source=src_label,
                dest=dest_label,
                qty=total_moved,
                remaining_src=ship.ballast_port() if p_from == "port" else ship.ballast_starboard(),
                final_dest=ship.ballast_port() if p_to == "port" else ship.ballast_starboard(),
                score_before=score_before,
                score_after=score_after,
                trigger_source="Manual"
            )
    except Exception as e:
        print("Error in gradual_ballast_pump:", e)
    finally:
        _is_manual_pumping = False

@app.post("/api/ballast/pump")
async def manual_pump(req: Request, background_tasks: BackgroundTasks):
    global _is_manual_pumping
    if _is_manual_pumping:
        raise HTTPException(status_code=400, detail="A pumping operation is already in progress.")
        
    body = await req.json()
    p_from = body.get("from_side")  # "port" or "starboard"
    p_to = body.get("to_side")      # "starboard", "port", or "Drain (Sea)"
    p_amt = float(body.get("amount", 50.0))
    from_bay = body.get("from_bay", "All")
    to_bay = body.get("to_bay", "All")

    ship = state.get_current_ship()
    
    src_water = 0.0
    for key, tank in ship.tanks.items():
        if key.startswith(p_from):
            bay_num = key.split("_")[1]
            if from_bay == "All" or str(from_bay) == str(bay_num):
                src_water += tank.current_volume
                
    dest_capacity = 0.0
    dest_water = 0.0
    if p_to in ["port", "starboard"]:
        for key, tank in ship.tanks.items():
            if key.startswith(p_to):
                bay_num = key.split("_")[1]
                if to_bay == "All" or str(to_bay) == str(bay_num):
                    dest_capacity += tank.capacity
                    dest_water += tank.current_volume
                    
    dest_space = dest_capacity - dest_water

    if p_from == p_to and from_bay == to_bay:
        raise HTTPException(status_code=400, detail="Cannot pump to the exact same tank.")
    if src_water <= 0:
        raise HTTPException(status_code=400, detail=f"Failed: Selected source has no water available.")
    if p_to in ["port", "starboard"] and dest_space <= 0:
        raise HTTPException(status_code=400, detail=f"Failed: Selected destination is at maximum capacity.")

    score_before, _, _ = state.get_normalized_stability(ship, state.latest_telemetry["roll"], state.latest_telemetry["pitch"])

    _is_manual_pumping = True
    background_tasks.add_task(gradual_ballast_pump, p_from, p_to, p_amt, score_before, from_bay, to_bay)
    
    src_msg = f"{p_from.upper()} (Bay {from_bay})" if from_bay != "All" else p_from.upper()
    dest_msg = "the SEA" if p_to == "Drain (Sea)" else (f"{p_to.upper()} (Bay {to_bay})" if to_bay != "All" else p_to.upper())
    return {"success": True, "message": f"Draining/pumping initiated from {src_msg} to {dest_msg}."}

def generate_explainable_ai_recs(ship, list_v, trim_v, roll, pitch, risk_label, risk_level, score):
    # If Stability Risk = SAFE, AI must not display warnings/actions.
    if risk_level == "SAFE":
        return [{
            "condition": "Vessel is stable and operating within safe design limits.",
            "cause": "Cargo and ballast weights are symmetrically distributed.",
            "bays": "All Bays (1 to 4)",
            "tanks": "All Tanks (Port and Starboard)",
            "action": "Maintain current loading condition. Ready for transit.",
            "water": 0,
            "pred_score": score,
            "priority": "LOW",
            "confidence": 99.0,
            "engineering": "Transverse center of gravity (TCG) and longitudinal center of gravity (LCG) are close to centerline and midship respectively, minimizing list and trim moments."
        }]
        
    from ship import StabilityAnalyzer
    p_cargo = StabilityAnalyzer.port_cargo_weight(ship)
    s_cargo = StabilityAnalyzer.starboard_cargo_weight(ship)
    p_ballast = ship.ballast_port()
    s_ballast = ship.ballast_starboard()
    
    if p_cargo + p_ballast > s_cargo + s_ballast:
        heavy_side = "Port"
        light_side = "Starboard"
    else:
        heavy_side = "Starboard"
        light_side = "Port"
        
    imbalance = abs((p_cargo + p_ballast) - (s_cargo + s_ballast))
    needed_transfer = imbalance / 2.0
    
    feasible_transfer = 0.0
    source_tanks_list = []
    dest_tanks_list = []
    
    # Check transfer capacity constraints
    for i in range(1, 5):
        s_key = f"{heavy_side.lower()}_{i}"
        d_key = f"{light_side.lower()}_{i}"
        s_tank = ship.tanks.get(s_key)
        d_tank = ship.tanks.get(d_key)
        
        if s_tank and d_tank:
            water_avail = s_tank.current_volume
            space_avail = d_tank.capacity - d_tank.current_volume
            
            pair_transfer = min(needed_transfer - feasible_transfer, water_avail, space_avail)
            if pair_transfer > 0.0:
                feasible_transfer += pair_transfer
                source_tanks_list.append(f"{heavy_side}-{i}")
                dest_tanks_list.append(f"{light_side}-{i}")
                
    action_type = "Transfer"
    dest_name = f"{light_side} Tanks"
    
    # Fallback to draining to sea if transfer is insufficient and heavy side has water
    if feasible_transfer < needed_transfer:
        drain_needed = needed_transfer - feasible_transfer
        drainable = 0.0
        for i in range(1, 5):
            s_key = f"{heavy_side.lower()}_{i}"
            s_tank = ship.tanks.get(s_key)
            if s_tank:
                pair_drain = min(drain_needed - drainable, s_tank.current_volume)
                if pair_drain > 0.0:
                    drainable += pair_drain
                    source_tanks_list.append(f"{heavy_side}-{i}")
        if drainable > 0.0:
            feasible_transfer += drainable
            action_type = "Drain"
            dest_name = "Sea"
            
    p_amt_rec = round(feasible_transfer)
    
    if p_amt_rec < 10:
        return [{
            "condition": f"List/Trim imbalance detected: {imbalance:.0f} t.",
            "cause": "Asymmetric load distribution on deck.",
            "bays": "N/A",
            "tanks": "N/A",
            "action": "Manual load redistribution required. Ballast correction capacity limits reached.",
            "water": 0,
            "pred_score": score,
            "priority": "HIGH",
            "confidence": 85.0,
            "engineering": "Ballast compensation is constrained by physical limits. Tanks are either empty or full."
        }]
        
    # Simulate correction
    import copy
    temp_ship = copy.deepcopy(ship)
    if action_type == "Transfer":
        temp_ship.pump_ballast(heavy_side.lower(), light_side.lower(), p_amt_rec)
    else:
        rem = p_amt_rec
        for key, tank in temp_ship.tanks.items():
            if key.startswith(heavy_side.lower()) and rem > 0:
                rem -= tank.remove_water(rem)
                
    list_new = StabilityAnalyzer.calculate_list(temp_ship)
    trim_new = StabilityAnalyzer.calculate_trim(temp_ship)
    roll_new = roll * (list_new / list_v) if list_v != 0 else 0.0
    pitch_new = pitch * (trim_new / trim_v) if trim_v != 0 else 0.0
    score_new, _, _ = state.get_normalized_stability(temp_ship, roll_new, pitch_new)
    
    affected_bays_list = sorted(list(set(c.bay for c in ship.containers if c.side.lower() == heavy_side.lower())))
    bays_str = ", ".join(f"Bay {b}" for b in affected_bays_list) if affected_bays_list else "None"
    
    priority_level = "CRITICAL" if risk_level == "CRITICAL" else "HIGH"
    
    return [{
        "condition": f"{heavy_side} side is heavier because {heavy_side} cargo + ballast exceeds {light_side} by {imbalance:.0f} t.",
        "cause": f"Asymmetric load distribution towards the {heavy_side} side.",
        "bays": bays_str,
        "tanks": ", ".join(source_tanks_list) if source_tanks_list else "None",
        "action": f"{action_type} {p_amt_rec} t ballast from {heavy_side} tanks to {dest_name}.",
        "water": p_amt_rec,
        "pred_score": score_new,
        "priority": priority_level,
        "confidence": 95.0,
        "engineering": f"Transferring ballast shifts the center of gravity towards the centerline, restoring the transverse metacentric height (GM) and reducing the listing angle."
    }]

@app.get("/api/recommendations")
async def get_recommendations():
    from ship import StabilityAnalyzer, RecommendationEngine
    ship = state.get_current_ship()
    cargo_kg = state.latest_telemetry["cargo_kg"]
    cargo_t = cargo_kg * 10.0
    rec_bay, rec_side, rec_score = RecommendationEngine.best_position(ship, cargo_t)
    
    # Calculate explainable recommendations
    telemetry = state.latest_telemetry
    roll_val = telemetry["roll"]
    pitch_val = telemetry["pitch"]
    list_v = StabilityAnalyzer.calculate_list(ship)
    trim_v = StabilityAnalyzer.calculate_trim(ship)
    score, label, risk = state.get_normalized_stability(ship, roll_val, pitch_val)
    
    explainable = generate_explainable_ai_recs(ship, list_v, trim_v, roll_val, pitch_val, label, risk, score)
    
    return {
        "best_bay": rec_bay,
        "best_side": rec_side,
        "best_score": rec_score,
        "explainable_recs": explainable
    }

@app.get("/api/deck-plan")
async def get_deck_plan():
    ship = state.get_current_ship()
    return {
        "num_bays": ship.num_bays,
        "containers": [
            {
                "id": c.id,
                "weight": c.weight,
                "bay": c.bay,
                "side": c.side,
                "tier": c.tier
            }
            for c in ship.containers
        ]
    }

@app.get("/api/reports/cargo-manifest")
async def cargo_manifest():
    return get_cargo_operations(limit=100)

@app.get("/api/reports/ballast-log")
async def ballast_log():
    return get_ballast_operations(limit=100)

@app.get("/api/reports/ops-log")
async def ops_log():
    # Cargo manifest logs serve as the operational sequence logs
    return get_cargo_operations(limit=100)

@app.post("/api/reports/clear")
async def clear_all_logs():
    clear_logs()
    # Also clear vision alerts
    manager = state.get_vision_manager()
    manager.clear_alerts()
    return {"success": True}

@app.post("/api/telemetry/simulate/cargo")
async def telemetry_simulate_cargo(req: Request):
    body = await req.json()
    weight_t = float(body.get("weight_t", 0.0))
    reader = state.get_current_reader()
    reader.set_simulated_cargo(weight_t / 10.0) # convert tonnes to scale kg
    return {"success": True}

@app.post("/api/telemetry/simulate/tilt")
async def telemetry_simulate_tilt(req: Request):
    body = await req.json()
    roll = body.get("roll")
    pitch = body.get("pitch")
    
    roll_val = float(roll) if roll is not None else None
    pitch_val = float(pitch) if pitch is not None else None
    
    reader = state.get_current_reader()
    reader.set_simulated_tilt(roll_val, pitch_val)
    return {"success": True}

@app.post("/api/telemetry/connect")
async def telemetry_connect(req: Request):
    body = await req.json()
    port = body.get("port")
    is_simulated = bool(body.get("is_simulated", True))
    state.reconnect_reader(port, is_simulated)
    return {"success": True, "is_simulated": is_simulated, "port": port}

@app.post("/api/telemetry/disconnect")
async def telemetry_disconnect():
    state.reconnect_reader(None, is_simulated=True)
    return {"success": True, "is_simulated": True}

@app.get("/api/telemetry/ports")
async def telemetry_ports():
    ports = SerialTelemetryReader.get_available_ports()
    return {"ports": ports}

@app.post("/api/vision/scenario")
async def vision_scenario(req: Request):
    body = await req.json()
    scenario = body.get("scenario", "Normal Voyage")
    manager = state.get_vision_manager()
    manager.set_scenario(scenario)
    return {"success": True, "scenario": scenario}

@app.get("/api/vision/status")
async def vision_status():
    manager = state.get_vision_manager()
    return {
        "source_mode": manager.get_source_mode(),
        "camera_states": manager.camera_states
    }

@app.post("/api/vision/camera/{camera_id}/toggle")
async def vision_camera_toggle(camera_id: str, req: Request):
    body = await req.json()
    enabled = bool(body.get("enabled", True))
    manager = state.get_vision_manager()
    try:
        manager.set_camera_enabled(camera_id, enabled)
        return {"success": True, "camera_id": camera_id, "enabled": enabled}
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid camera ID")

@app.post("/api/vision/source-mode")
async def vision_source_mode_toggle(req: Request):
    body = await req.json()
    mode = body.get("mode")  # "simulated" or "live"
    device_input = body.get("device_index", "0")
    
    # Parse as int if it's a simple index, otherwise keep as string (IP camera URL)
    device_index = device_input
    if isinstance(device_input, str) and device_input.strip().isdigit():
        device_index = int(device_input.strip())
        
    manager = state.get_vision_manager()
    try:
        manager.set_source_mode(mode, device_index)
        return {"success": True, "mode": mode}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/vision/alerts")
async def vision_alerts():
    manager = state.get_vision_manager()
    alerts = manager.get_alerts(limit=50)
    return alerts

@app.post("/api/vision/alerts/clear")
async def clear_vision_alerts():
    manager = state.get_vision_manager()
    manager.clear_alerts()
    return {"success": True}

@app.get("/api/voyage/profile")
async def voyage_profile():
    profile = get_current_ship_profile()
    if profile:
        return {
            "ship_name": profile.ship_name,
            "imo": profile.imo,
            "total_bays": profile.total_bays,
            "tank_capacity": profile.tank_capacity,
            "ship_configuration": profile.ship_configuration,
            "cargo_data": profile.cargo_data,
            "ballast_configuration": profile.ballast_configuration
        }
    return JSONResponse(status_code=404, content={"message": "Ship profile not initialized"})

@app.get("/api/voyage/track")
async def voyage_track(imo: str):
    # Retrieve MyShipTracking credentials and fetch tracking history
    client = MyShipTrackingClient()
    track_data = client.get_current_track(imo)
    return track_data

# --- VIDEO STREAM ENDPOINTS ---

@app.get("/api/video/{camera_id}")
async def video_stream(camera_id: str):
    valid_ids = ["crew_safety", "sea", "cargo", "ballast"]
    if camera_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Invalid camera feed ID")
    return StreamingResponse(
        frame_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, log_level="info")
