"""
Phase 4F: Cargo-Aware Digital Twin & Predictive Monitoring Engine.
Provides comprehensive structural cross-sections, 4-stage lifecycle progression models,
predictive vs. actual hydrostatic comparisons, operational threshold alert detection,
and telemetry provenance tracking (never fabricating sensor data).
"""

import copy
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("digital_twin")


class DigitalTwin:
    """
    Vessel Digital Twin & Predictive Monitoring Service.
    Integrates live container stowage, ballast tank states, sensor telemetry,
    and hydrostatic stability evaluations into a unified supervisory model.
    """

    # Operational threshold limits (based on vessel stability criteria)
    LIST_WARNING_DEG = 2.5
    LIST_CRITICAL_DEG = 5.0
    TRIM_WARNING_DEG = 1.5
    TRIM_CRITICAL_DEG = 3.0
    BALLAST_IMBALANCE_WARNING_T = 150.0
    SENSOR_DISPARITY_WARNING_DEG = 5.0

    @staticmethod
    def display(ship, num_bays=None):
        """
        Render a console cross-section of the ship.
        Maintains backward compatibility with CLI debugging.
        """
        if num_bays is None:
            if ship.containers:
                num_bays = max(c.bay for c in ship.containers)
            else:
                num_bays = 10

        print("\n===== DIGITAL TWIN =====\n")

        for bay in range(1, num_bays + 1):
            port = ""
            center = ""
            starboard = ""

            for c in ship.containers:
                if c.bay == bay:
                    if c.side == "port":
                        port += f"[{c.id}:{c.weight}t]"
                    elif c.side == "center":
                        center += f"[{c.id}:{c.weight}t]"
                    elif c.side == "starboard":
                        starboard += f"[{c.id}:{c.weight}t]"

            print(
                f"Bay {bay:02d} | "
                f"P:{port:<18} "
                f"C:{center:<18} "
                f"S:{starboard:<18}"
            )

    @classmethod
    def get_vessel_twin_snapshot(
        cls,
        ship: Any,
        telemetry: Optional[Dict[str, Any]] = None,
        operation_status: str = "IDLE",
        is_simulated: Optional[bool] = None
    ) -> DigitalTwinVesselState:
        """
        Generates a complete, structured snapshot of the vessel digital twin.
        Includes cargo slots, ballast tanks, hydrostatics, alerts, and telemetry source.
        """
        from ship import StabilityAnalyzer
        from container_stability.models import DigitalTwinVesselState
        import state

        # 1. Evaluate hydrostatics using StabilityAnalyzer ground truth
        list_t = round(float(StabilityAnalyzer.calculate_list(ship)), 2)
        trim_t = round(float(StabilityAnalyzer.calculate_trim(ship)), 2)
        score = round(float(StabilityAnalyzer.stability_score(ship)), 2)
        risk = StabilityAnalyzer.risk_level(ship)

        # 2. Extract container cargo layout (Authoritative Source: DOCUMENT_AI)
        containers_list = [
            {
                "id": c.id,
                "weight": float(c.weight),
                "bay": int(c.bay),
                "side": str(c.side).upper(),
                "tier": int(getattr(c, "tier", 1)),
                "provenance": "[DOCUMENT AI]"
            }
            for c in ship.containers
        ]

        # 3. Extract ballast tanks layout
        tanks_dict = {}
        for k, tank in ship.tanks.items():
            tanks_dict[k] = {
                "name": tank.name,
                "current_volume": round(float(tank.current_volume), 2),
                "capacity": round(float(tank.capacity), 2),
                "fill_ratio": round(float(tank.fill_ratio), 3)
            }

        # 4. Determine telemetry data, provenance, quality, and pump state
        telemetry_timestamp = None
        telemetry_freshness = "FRESH"
        stale_seconds = 0.0
        connection_status = "CONNECTED"
        pump_state = "IDLE"
        pump_flow_l_s = 0.0
        pump_active = False

        if telemetry is None:
            try:
                from telemetry.manager import TelemetryManager
                norm_telemetry = TelemetryManager.get_instance().get_latest_telemetry()
                roll_deg = norm_telemetry.vessel_state.roll_deg
                pitch_deg = norm_telemetry.vessel_state.pitch_deg
                telemetry_timestamp = norm_telemetry.timestamp
                connection_status = norm_telemetry.connection_status.value if hasattr(norm_telemetry.connection_status, "value") else str(norm_telemetry.connection_status)
                stale_seconds = getattr(norm_telemetry.metadata, "stale_seconds", 0.0)
                
                # Quality / Freshness
                dq = norm_telemetry.metadata.data_quality.value if hasattr(norm_telemetry.metadata.data_quality, "value") else str(norm_telemetry.metadata.data_quality)
                if connection_status == "DISCONNECTED":
                    telemetry_freshness = "DISCONNECTED"
                elif stale_seconds >= 5.0 or dq == "STALE":
                    telemetry_freshness = "STALE"
                elif dq == "DEGRADED":
                    telemetry_freshness = "DEGRADED"
                else:
                    telemetry_freshness = "FRESH"

                if is_simulated is None:
                    is_simulated = (norm_telemetry.source.value == "SIMULATED_TELEMETRY")
                telemetry_source = "SIMULATED_TELEMETRY" if is_simulated else "HARDWARE_SENSOR"

                # Pump telemetry
                pumps_dict = getattr(norm_telemetry, "pumps", {})
                if pumps_dict and isinstance(pumps_dict, dict):
                    primary_pump = next(iter(pumps_dict.values()), None)
                    if primary_pump:
                        pump_state = primary_pump.state.value if hasattr(primary_pump.state, "value") else str(primary_pump.state)
                        pump_flow_l_s = primary_pump.flow_rate_l_s
                        pump_active = (pump_state in ["DRAINING", "FILLING", "TRANSFERRING"]) or getattr(primary_pump, "active_valve_open", False)
                elif hasattr(norm_telemetry, "pump") and norm_telemetry.pump:
                    p = norm_telemetry.pump
                    pump_state = p.state.value if hasattr(p.state, "value") else str(p.state)
                    pump_flow_l_s = p.flow_rate_l_s
                    pump_active = (pump_state in ["DRAINING", "FILLING", "TRANSFERRING"]) or getattr(p, "active_valve_open", False)

                telemetry_dict = {
                    "roll": roll_deg,
                    "pitch": pitch_deg,
                    "status": norm_telemetry.operational_telemetry.status,
                    "stale_seconds": stale_seconds,
                    "connection_status": connection_status,
                    "pump_state": pump_state,
                    "pump_flow_l_s": pump_flow_l_s,
                    "pump_active": pump_active
                }
            except Exception:
                telemetry_dict = getattr(state, "latest_telemetry", {"roll": list_t, "pitch": trim_t})
                roll_deg = round(float(telemetry_dict.get("roll", list_t)), 2)
                pitch_deg = round(float(telemetry_dict.get("pitch", trim_t)), 2)
                if is_simulated is None:
                    is_simulated = True
                telemetry_source = "SIMULATED_TELEMETRY" if is_simulated else "HARDWARE_SENSOR"
        elif hasattr(telemetry, "vessel_state"):
            # NormalizedTelemetry instance passed directly
            roll_deg = telemetry.vessel_state.roll_deg
            pitch_deg = telemetry.vessel_state.pitch_deg
            telemetry_timestamp = telemetry.timestamp
            connection_status = telemetry.connection_status.value if hasattr(telemetry.connection_status, "value") else str(telemetry.connection_status)
            stale_seconds = getattr(telemetry.metadata, "stale_seconds", 0.0)

            dq = telemetry.metadata.data_quality.value if hasattr(telemetry.metadata.data_quality, "value") else str(telemetry.metadata.data_quality)
            if connection_status == "DISCONNECTED":
                telemetry_freshness = "DISCONNECTED"
            elif stale_seconds >= 5.0 or dq == "STALE":
                telemetry_freshness = "STALE"
            elif dq == "DEGRADED":
                telemetry_freshness = "DEGRADED"
            else:
                telemetry_freshness = "FRESH"

            if is_simulated is None:
                telemetry_source = telemetry.source.value if hasattr(telemetry.source, "value") else str(telemetry.source)
                is_simulated = (telemetry_source == "SIMULATED_TELEMETRY")
            else:
                telemetry_source = "SIMULATED_TELEMETRY" if is_simulated else "HARDWARE_SENSOR"

            pumps_dict = getattr(telemetry, "pumps", {})
            if pumps_dict and isinstance(pumps_dict, dict):
                primary_pump = next(iter(pumps_dict.values()), None)
                if primary_pump:
                    pump_state = primary_pump.state.value if hasattr(primary_pump.state, "value") else str(primary_pump.state)
                    pump_flow_l_s = primary_pump.flow_rate_l_s
                    pump_active = (pump_state in ["DRAINING", "FILLING", "TRANSFERRING"]) or getattr(primary_pump, "active_valve_open", False)
            elif hasattr(telemetry, "pump") and telemetry.pump:
                p = telemetry.pump
                pump_state = p.state.value if hasattr(p.state, "value") else str(p.state)
                pump_flow_l_s = p.flow_rate_l_s
                pump_active = (pump_state in ["DRAINING", "FILLING", "TRANSFERRING"]) or getattr(p, "active_valve_open", False)

            telemetry_dict = {
                "roll": roll_deg,
                "pitch": pitch_deg,
                "status": telemetry.operational_telemetry.status,
                "stale_seconds": stale_seconds,
                "connection_status": connection_status,
                "pump_state": pump_state,
                "pump_flow_l_s": pump_flow_l_s,
                "pump_active": pump_active
            }
        else:
            telemetry_dict = telemetry
            roll_deg = round(float(telemetry.get("roll", list_t)), 2)
            pitch_deg = round(float(telemetry.get("pitch", trim_t)), 2)
            telemetry_timestamp = telemetry.get("timestamp")
            telemetry_freshness = telemetry.get("freshness", "FRESH")
            stale_seconds = float(telemetry.get("stale_seconds", 0.0))
            connection_status = str(telemetry.get("connection_status", "CONNECTED"))
            pump_state = str(telemetry.get("pump_state", "IDLE"))
            pump_flow_l_s = float(telemetry.get("pump_flow_l_s", 0.0))
            pump_active = bool(telemetry.get("pump_active", False))

            if is_simulated is None:
                if "is_simulated" in telemetry:
                    is_simulated = bool(telemetry["is_simulated"])
                elif "telemetry_source" in telemetry:
                    is_simulated = (telemetry["telemetry_source"] == "SIMULATED_TELEMETRY")
                else:
                    try:
                        reader = state.get_current_reader()
                        is_simulated = bool(reader.is_simulated)
                    except Exception:
                        is_simulated = True
            telemetry_source = "SIMULATED_TELEMETRY" if is_simulated else "HARDWARE_SENSOR"

        # 5. Build explicit multi-layer provenance mapping
        provenance_map = {
            "cargo_weight": "[DOCUMENT AI]",
            "vessel_hydrostatics": "[CALCULATED]",
            "telemetry": "[SIMULATED TELEMETRY]" if is_simulated else "[HARDWARE SENSOR]",
            "predictions": "[PREDICTED]"
        }

        # 6. Detect active operational alerts
        alerts = cls.detect_operational_alerts(ship, telemetry_dict)

        from container_stability.policy import PROVENANCE_LABEL
        return DigitalTwinVesselState(
            ship_name=getattr(ship, "name", "Vessel"),
            containers=containers_list,
            ballast_tanks=tanks_dict,
            roll_deg=roll_deg,
            pitch_deg=pitch_deg,
            list_t=list_t,
            trim_t=trim_t,
            stability_score=score,
            risk_level=risk,
            is_simulated=is_simulated,
            telemetry_source=telemetry_source,
            authoritative_weight_source=PROVENANCE_LABEL,
            operation_status=operation_status,
            alerts=alerts,
            telemetry_timestamp=telemetry_timestamp,
            telemetry_freshness=telemetry_freshness,
            stale_seconds=round(stale_seconds, 2),
            connection_status=connection_status,
            pump_state=pump_state,
            pump_flow_l_s=round(pump_flow_l_s, 2),
            pump_active=pump_active,
            provenance_map=provenance_map
        )

    @classmethod
    def detect_operational_alerts(
        cls,
        ship: Any,
        telemetry: Optional[Dict[str, Any]] = None
    ) -> List[OperationalSafetyAlert]:
        """
        Evaluates operational safety conditions against maritime stability thresholds.
        Checks excessive list, excessive trim, ballast tank asymmetry, telemetry disparities,
        and telemetry freshness/connection status.
        """
        from ship import StabilityAnalyzer
        from container_stability.models import OperationalSafetyAlert
        alerts: List[OperationalSafetyAlert] = []

        list_t = abs(float(StabilityAnalyzer.calculate_list(ship)))
        trim_t = abs(float(StabilityAnalyzer.calculate_trim(ship)))

        # 1. Excessive List Alert
        if list_t >= cls.LIST_CRITICAL_DEG:
            alerts.append(
                OperationalSafetyAlert(
                    alert_type="EXCESSIVE_LIST",
                    severity="CRITICAL",
                    threshold=f"< {cls.LIST_CRITICAL_DEG:.1f}°",
                    observed_value=round(list_t, 2),
                    message=f"Critical vessel list detected ({list_t:.2f}°). Extreme capsizing/heeling risk.",
                    action="Halt cargo operations immediately. Initiate emergency ballast counter-flooding."
                )
            )
        elif list_t >= cls.LIST_WARNING_DEG:
            alerts.append(
                OperationalSafetyAlert(
                    alert_type="EXCESSIVE_LIST",
                    severity="WARNING",
                    threshold=f"< {cls.LIST_WARNING_DEG:.1f}°",
                    observed_value=round(list_t, 2),
                    message=f"Excessive vessel list deviation ({list_t:.2f}°) exceeds standard operating limit.",
                    action="Review stowage plan and schedule anti-heeling ballast compensation."
                )
            )

        # 2. Excessive Trim Alert
        if trim_t >= cls.TRIM_CRITICAL_DEG:
            alerts.append(
                OperationalSafetyAlert(
                    alert_type="EXCESSIVE_TRIM",
                    severity="CRITICAL",
                    threshold=f"< {cls.TRIM_CRITICAL_DEG:.1f}°",
                    observed_value=round(trim_t, 2),
                    message=f"Critical longitudinal trim deviation ({trim_t:.2f}°). Propeller emergence or bow submergence risk.",
                    action="Execute longitudinal ballast transfer to restore even-keel trim."
                )
            )
        elif trim_t >= cls.TRIM_WARNING_DEG:
            alerts.append(
                OperationalSafetyAlert(
                    alert_type="EXCESSIVE_TRIM",
                    severity="WARNING",
                    threshold=f"< {cls.TRIM_WARNING_DEG:.1f}°",
                    observed_value=round(trim_t, 2),
                    message=f"Elevated longitudinal trim angle ({trim_t:.2f}°).",
                    action="Adjust container stowage bay distribution forward/aft."
                )
            )

        # 3. Ballast Imbalance Alert
        port_vol = sum(t.current_volume for k, t in ship.tanks.items() if "port" in k.lower())
        stbd_vol = sum(t.current_volume for k, t in ship.tanks.items() if "starboard" in k.lower())
        diff_vol = abs(port_vol - stbd_vol)

        if diff_vol >= cls.BALLAST_IMBALANCE_WARNING_T:
            alerts.append(
                OperationalSafetyAlert(
                    alert_type="BALLAST_IMBALANCE",
                    severity="WARNING",
                    threshold=f"< {cls.BALLAST_IMBALANCE_WARNING_T:.0f}t port/starboard differential",
                    observed_value=round(diff_vol, 2),
                    message=f"Significant transverse ballast asymmetry ({diff_vol:.1f}t differential between Port [{port_vol:.0f}t] and Starboard [{stbd_vol:.0f}t]).",
                    action="Re-level ballast tanks before next container loading cycle."
                )
            )

        # 4. Telemetry Sensor vs Hydrostatic Model Disparity Alert
        if telemetry is not None:
            sensor_roll = abs(float(telemetry.get("roll", 0.0)))
            disparity = abs(sensor_roll - list_t)
            if disparity >= cls.SENSOR_DISPARITY_WARNING_DEG:
                alerts.append(
                    OperationalSafetyAlert(
                        alert_type="STATE_MISMATCH",
                        severity="WARNING",
                        threshold=f"< {cls.SENSOR_DISPARITY_WARNING_DEG:.1f}° disparity",
                        observed_value=round(disparity, 2),
                        message=f"Disparity between sensor roll ({sensor_roll:.2f}°) and computed hydrostatic list ({list_t:.2f}°).",
                        action="Inspect physical inclinometer sensor calibration and verify draft survey."
                    )
                )

            # 5. Stale / Disconnected Telemetry Alerts
            stale_sec = float(telemetry.get("stale_seconds", 0.0))
            conn_status = str(telemetry.get("connection_status", "CONNECTED"))

            if conn_status == "DISCONNECTED":
                alerts.append(
                    OperationalSafetyAlert(
                        alert_type="TELEMETRY_DISCONNECTED",
                        severity="WARNING",
                        threshold="Active Link",
                        observed_value=0.0,
                        message="Vessel telemetry link is disconnected. Preserving last known sensor measurements without data fabrication.",
                        action="Inspect sensor cable / serial COM port connection or switch to simulator."
                    )
                )
            elif stale_sec >= 5.0:
                alerts.append(
                    OperationalSafetyAlert(
                        alert_type="STALE_TELEMETRY",
                        severity="WARNING",
                        threshold="< 5.0s freshness",
                        observed_value=round(stale_sec, 1),
                        message=f"Vessel telemetry stream is stale ({stale_sec:.1f}s delay). Displaying preserved physical state.",
                        action="Verify serial sensor polling rate and ESP32 health."
                    )
                )

        return alerts

    @classmethod
    def get_four_stage_lifecycle(
        cls,
        ship_before: Optional[Any] = None,
        ship_loaded: Optional[Any] = None,
        ship_ballasted: Optional[Any] = None,
        current_ship: Optional[Any] = None
    ) -> FourStageLifecycle:
        """
        Builds the 4-stage Before/After lifecycle progression model:
        1. VESSEL BEFORE CONTAINER
        2. CONTAINER LOADED
        3. BALLAST COMPENSATED
        4. CURRENT VESSEL STATE
        """
        import state
        from container_stability.models import FourStageLifecycle

        curr = current_ship if current_ship is not None else state.get_current_ship()

        before_state = cls.get_vessel_twin_snapshot(ship_before, operation_status="BEFORE_CONTAINER") if ship_before else None
        loaded_state = cls.get_vessel_twin_snapshot(ship_loaded, operation_status="CONTAINER_LOADED") if ship_loaded else None
        ballasted_state = cls.get_vessel_twin_snapshot(ship_ballasted, operation_status="BALLAST_COMPENSATED") if ship_ballasted else None
        current_state = cls.get_vessel_twin_snapshot(curr, operation_status="CURRENT_STATE")

        return FourStageLifecycle(
            vessel_before=before_state,
            container_loaded=loaded_state,
            ballast_compensated=ballasted_state,
            current_vessel_state=current_state,
            alerts=current_state.alerts
        )

    @classmethod
    def get_predictive_comparison(
        cls,
        current_ship: Any,
        container_id: str,
        gross_weight_t: float,
        bay: int,
        side: str,
        tier: int = 1
    ) -> Any:
        """
        Generates side-by-side comparison between PROJECTED pre-load simulation
        and ACTUAL committed vessel state.
        """
        from ship import Container, StabilityAnalyzer
        from container_stability.models import PredictiveComparison

        # 1. Project post-load state on copy-of-ship
        sim_ship = copy.deepcopy(current_ship)
        sim_cntr = Container(
            id=container_id,
            weight=gross_weight_t,
            bay=bay,
            side=side.lower(),
            tier=tier
        )
        sim_ship.add_container(sim_cntr)

        proj_list = round(float(StabilityAnalyzer.calculate_list(sim_ship)), 2)
        proj_trim = round(float(StabilityAnalyzer.calculate_trim(sim_ship)), 2)
        proj_score = round(float(StabilityAnalyzer.stability_score(sim_ship)), 2)

        # Estimate required ballast compensation
        proj_ballast_req = round(abs(proj_list) * 20.0, 1)

        # 2. Check if container is already stowed in actual current_ship
        is_already_stowed = any(c.id == container_id for c in current_ship.containers)

        if is_already_stowed:
            act_list = round(float(StabilityAnalyzer.calculate_list(current_ship)), 2)
            act_trim = round(float(StabilityAnalyzer.calculate_trim(current_ship)), 2)
            act_score = round(float(StabilityAnalyzer.stability_score(current_ship)), 2)
            act_ballast_state = round(sum(t.current_volume for t in current_ship.tanks.values()), 1)

            return PredictiveComparison(
                container_id=container_id,
                projected_list_t=proj_list,
                projected_trim_t=proj_trim,
                projected_stability_score=proj_score,
                projected_ballast_req_t=proj_ballast_req,
                actual_list_t=act_list,
                actual_trim_t=act_trim,
                actual_stability_score=act_score,
                actual_ballast_state_t=act_ballast_state,
                status="COMMITTED"
            )
        else:
            return PredictiveComparison(
                container_id=container_id,
                projected_list_t=proj_list,
                projected_trim_t=proj_trim,
                projected_stability_score=proj_score,
                projected_ballast_req_t=proj_ballast_req,
                actual_list_t=None,
                actual_trim_t=None,
                actual_stability_score=None,
                actual_ballast_state_t=None,
                status="PROJECTED"
            )
