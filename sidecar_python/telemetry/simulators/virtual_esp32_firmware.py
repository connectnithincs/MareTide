"""
Virtual ESP32 Microcontroller Firmware Simulation Engine.

Faithfully replicates the execution logic, timing, EMA filtering, Torricelli orifice physics,
servo actuation, boot banners, alert lines, and 9-line multi-line JSON stream of esp32_sensor_sketch.ino.

CRITICAL MARITIME SAFETY INVARIANT:
The HX711 scale interface on this virtual microcontroller is for isolated bench diagnostics only.
It MUST NEVER be used as a source for container cargo weight, VGM, or vessel stability calculations.
Cargo mass is verified exclusively through Document AI.
"""

import time
import math
import threading
from typing import Dict, Any, List, Optional, Tuple


class VirtualESP32Firmware:
    """
    Pure Python software emulator for esp32_sensor_sketch.ino running at 115200 baud.
    """

    # --- FIRMWARE CONSTANTS (Mirroring .ino line-for-line) ---
    BAUDRATE = 115200
    TELEMETRY_INTERVAL_MS = 100  # 10 Hz emission for responsive digital twin reactions
    LIST_LIMIT = 5.0             # degrees — roll alert threshold
    TRIM_LIMIT = 5.0             # degrees — pitch alert threshold
    TANK_FULL_DIST = 10.0        # cm — sensor distance when tank is full
    TANK_EMPTY_DIST = 30.0       # cm — sensor distance when tank is empty
    TANK_AREA_CM2 = 150.0        # cross-sectional area of ballast tank
    BALLAST_RATIO_L_PER_KG = 1.0 # 1L drained per 1kg of diagnostic weight
    
    GATE_CLOSED_ANGLE = 0        # degrees
    GATE_OPEN_ANGLE = 80         # degrees
    DISCHARGE_COEFFICIENT = 0.62 # orifice flow coefficient Cd
    GATE_OPEN_AREA_CM2 = 2.0     # gate open area in cm^2
    DRAIN_TIMEOUT_MS = 30000     # 30-second safety cutoff
    EMA_ALPHA = 0.25             # Exponential moving average filter weight

    # Supported Scenarios
    SCENARIOS = [
        "STABLE",
        "PORT_LIST",
        "STARBOARD_LIST",
        "FORWARD_PITCH",
        "AFT_PITCH",
        "TANK_FILLING",
        "TANK_DRAINING",
        "SENSOR_FAULT",
        "DISCONNECTED"
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self.running = False
        
        # Virtual Hardware Registers / Pins
        self.pump_led = False      # GPIO 23
        self.warn_led = False      # GPIO 19
        self.gate_servo_angle = self.GATE_CLOSED_ANGLE # GPIO 25
        
        # Virtual Sensor States
        self.current_roll = 0.0
        self.target_roll = 0.0
        self.current_pitch = 0.0
        self.target_pitch = 0.0
        
        self.raw_distance = self.TANK_FULL_DIST
        self.filtered_distance = self.TANK_FULL_DIST
        self.sensor_fault = False
        
        self.diagnostic_cargo_kg = 0.0 # HX711 isolated scale
        self.active_scenario = "STABLE"
        
        # State Machine Variables (Lines 61-70 of .ino)
        self.is_draining = false = False
        self.drain_target_dist = 0.0
        self.drain_start_time_ms = 0
        self.drain_start_dist = 0.0
        self.drain_start_vol = 0.0
        self.drain_target_vol_clamped = 0.0
        self.drain_predicted_flow = 0.0
        self.drain_predicted_sec = 0.0
        
        # Telemetry & Output Buffer
        self.last_telemetry_time_ms = 0
        self.boot_banner_sent = False
        self.serial_output_queue: List[str] = []
        self._internal_clock_ms = 0

    def boot(self):
        """Simulates microcontroller power-on reset & setup() banner emission."""
        with self._lock:
            self.running = True
            self.boot_banner_sent = True
            self.pump_led = False
            self.warn_led = False
            self.gate_servo_angle = self.GATE_CLOSED_ANGLE
            self._internal_clock_ms = int(time.time() * 1000)
            self.last_telemetry_time_ms = self._internal_clock_ms
            
            # Setup banners matching .ino lines 88-100
            self.serial_output_queue.extend([
                "MPU6050: OK\n",
                "HX711: Ready\n",
                "Gate Servo: Closed\n",
                "NAVI-AI ESP32 Ready\n",
                "-------------------\n"
            ])

    def set_scenario(self, scenario: str) -> bool:
        """Configures the active simulator scenario."""
        scenario_upper = scenario.upper()
        if scenario_upper not in self.SCENARIOS:
            return False
            
        with self._lock:
            self.active_scenario = scenario_upper
            self.sensor_fault = False

            if scenario_upper == "STABLE":
                self.target_roll = 0.0
                self.target_pitch = 0.0
                self.raw_distance = self.TANK_FULL_DIST
                self.diagnostic_cargo_kg = 0.0
                if self.is_draining:
                    self._stop_draining(timed_out=False)

            elif scenario_upper == "PORT_LIST":
                self.target_roll = -7.50
                self.target_pitch = 0.20

            elif scenario_upper == "STARBOARD_LIST":
                self.target_roll = 8.20
                self.target_pitch = -0.30

            elif scenario_upper == "FORWARD_PITCH":
                self.target_pitch = -6.50
                self.target_roll = 0.10

            elif scenario_upper == "AFT_PITCH":
                self.target_pitch = 5.80
                self.target_roll = -0.15

            elif scenario_upper == "TANK_FILLING":
                self.raw_distance = self.TANK_EMPTY_DIST
                self.target_roll = 0.0
                self.target_pitch = 0.0

            elif scenario_upper == "TANK_DRAINING":
                self.raw_distance = self.TANK_FULL_DIST
                self.start_draining(cargo_weight_kg=2.50)

            elif scenario_upper == "SENSOR_FAULT":
                self.sensor_fault = True

            elif scenario_upper == "DISCONNECTED":
                # Halts stream emission
                pass

            # Force immediate packet emission on next tick
            self.last_telemetry_time_ms = 0

        return True

    def send_command(self, cmd: str) -> None:
        """Processes incoming serial commands (e.g. 'DRAIN:<weight>\n')."""
        with self._lock:
            clean_cmd = cmd.strip()
            if clean_cmd.startswith("DRAIN:"):
                try:
                    weight_val = float(clean_cmd[6:])
                    if weight_val > 0.0 and not self.is_draining:
                        self.start_draining(cargo_weight_kg=weight_val)
                except ValueError:
                    pass

    def start_draining(self, cargo_weight_kg: float) -> None:
        """Initializes non-blocking Torricelli orifice discharge (matches .ino lines 189-225)."""
        start_dist = self._read_distance_filtered()
        start_depth = self._distance_to_depth(start_dist)
        start_vol_l = self._depth_to_volume_liters(start_depth)

        target_vol_l = cargo_weight_kg * self.BALLAST_RATIO_L_PER_KG
        target_vol_clamped = min(target_vol_l, start_vol_l)
        
        target_depth = max(0.0, start_depth - (target_vol_clamped * 1000.0) / self.TANK_AREA_CM2)
        target_dist = self.TANK_EMPTY_DIST - target_depth

        predicted_q = self._predict_flow_rate_lps(start_depth)
        predicted_sec = (target_vol_clamped / predicted_q) if predicted_q > 0 else 0.0

        self.is_draining = True
        self.drain_target_dist = target_dist
        self.drain_start_time_ms = self._internal_clock_ms
        self.drain_start_dist = start_dist
        self.drain_start_vol = start_vol_l
        self.drain_target_vol_clamped = target_vol_clamped
        self.drain_predicted_flow = predicted_q
        self.drain_predicted_sec = predicted_sec

        self.gate_servo_angle = self.GATE_OPEN_ANGLE
        self.pump_led = True

        self.serial_output_queue.extend([
            "=== BALLAST DRAIN STARTED ===\n",
            f"Cargo weight (kg): {cargo_weight_kg:.2f}\n",
            f"Target volume (L): {target_vol_clamped:.2f}\n",
            f"Target distance (cm): {target_dist:.2f}\n",
            f"Predicted flow (L/s): {predicted_q:.3f}\n",
            f"Predicted time (s): {predicted_sec:.1f}\n"
        ])

    def _stop_draining(self, timed_out: bool = False) -> None:
        """Concludes draining cycle and closes gate servo (matches .ino lines 245-267)."""
        self.gate_servo_angle = self.GATE_CLOSED_ANGLE
        self.pump_led = False
        self.is_draining = False

        elapsed_sec = (self._internal_clock_ms - self.drain_start_time_ms) / 1000.0
        current_dist = self._read_distance_filtered()
        end_depth = self._distance_to_depth(current_dist)
        end_vol_l = self._depth_to_volume_liters(end_depth)
        actual_vol_l = max(0.0, self.drain_start_vol - end_vol_l)
        actual_flow_lps = (actual_vol_l / elapsed_sec) if elapsed_sec > 0 else 0.0

        self.serial_output_queue.append("=== BALLAST DRAIN COMPLETE ===\n")
        if timed_out:
            self.serial_output_queue.append("STATUS: WARNING - Drain timeout reached. Gate closed for safety.\n")
        else:
            self.serial_output_queue.append("STATUS: SUCCESS - Target level achieved.\n")
        
        self.serial_output_queue.extend([
            f"Actual volume drained (L): {actual_vol_l:.2f}\n",
            f"Time taken (s): {elapsed_sec:.1f}\n",
            f"Actual flow rate (L/s): {actual_flow_lps:.3f}\n",
            "-------------------------------\n"
        ])

    def step(self, dt_sec: float = 0.05) -> str:
        """
        Executes one clock cycle step (dt) of the virtual microcontroller.
        Returns any newly emitted serial text stream data.
        """
        with self._lock:
            self._internal_clock_ms += int(dt_sec * 1000)
            now_ms = self._internal_clock_ms

            if self.active_scenario == "DISCONNECTED":
                # No serial output emitted
                return ""

            # 1. Smoothly interpolate Roll and Pitch toward target
            alpha_motion = min(1.0, dt_sec * 5.0)
            self.current_roll += (self.target_roll - self.current_roll) * alpha_motion
            self.current_pitch += (self.target_pitch - self.current_pitch) * alpha_motion

            # 2. Update Draining Physics / Filling Simulation
            if self.is_draining:
                current_depth = self._distance_to_depth(self.filtered_distance)
                flow_lps = self._predict_flow_rate_lps(current_depth)
                vol_drained_step = flow_lps * dt_sec
                depth_drop_cm = (vol_drained_step * 1000.0) / self.TANK_AREA_CM2
                self.raw_distance = min(self.TANK_EMPTY_DIST, self.raw_distance + depth_drop_cm)

                # Check completion
                if self.filtered_distance >= self.drain_target_dist:
                    self._stop_draining(timed_out=False)
                elif (now_ms - self.drain_start_time_ms) > self.DRAIN_TIMEOUT_MS:
                    self._stop_draining(timed_out=True)
            elif self.active_scenario == "TANK_FILLING":
                self.raw_distance = max(self.TANK_FULL_DIST, self.raw_distance - (dt_sec * 1.5))

            # 3. Update EMA Filtered Distance
            raw_reading = -1.0 if self.sensor_fault else self.raw_distance
            if raw_reading < 0:
                # Retain filtered or default empty
                dist_filtered = self.filtered_distance if self.filtered_distance >= 0 else self.TANK_EMPTY_DIST
            else:
                dist_filtered = (self.EMA_ALPHA * raw_reading) + ((1.0 - self.EMA_ALPHA) * self.filtered_distance)
            self.filtered_distance = dist_filtered

            ballast_pct = self._distance_to_ballast_pct(self.filtered_distance)

            # 4. Check Risk & Warning Banners
            risk_str = self._get_risk(self.current_roll, self.current_pitch)
            max_tank_kg = (self.TANK_EMPTY_DIST - self.TANK_FULL_DIST) * self.TANK_AREA_CM2 / 1000.0 / self.BALLAST_RATIO_L_PER_KG
            weight_exceeded = (self.diagnostic_cargo_kg > max_tank_kg)
            self.warn_led = (risk_str == "CRITICAL" or weight_exceeded)

            # 5. Periodic Telemetry Emission (@ 500 ms / 2 Hz)
            if (now_ms - self.last_telemetry_time_ms) >= self.TELEMETRY_INTERVAL_MS:
                self.last_telemetry_time_ms = now_ms

                # Asynchronous alert lines (.ino lines 303-323)
                if ballast_pct >= 0 and ballast_pct < 20.0:
                    self.serial_output_queue.append("WARNING: LOW BALLAST LEVEL!\n")
                if weight_exceeded:
                    self.serial_output_queue.append("WARNING: Maximum Capacity attained!\n")
                if self.current_roll > self.LIST_LIMIT:
                    self.serial_output_queue.append("Tilt Right -> Pump PORT side\n")
                elif self.current_roll < -self.LIST_LIMIT:
                    self.serial_output_queue.append("Tilt Left -> Pump STARBOARD side\n")

                # Operation Status
                status_str = "IDLE"
                if self.diagnostic_cargo_kg >= 0.1 or self.is_draining:
                    status_str = "DRAINING" if self.is_draining else "READY"

                # 9-Line Multi-line JSON Packet matching .ino lines 350-360
                packet_str = (
                    "{\n"
                    f"  \"roll\": {self.current_roll:.2f},\n"
                    f"  \"pitch\": {self.current_pitch:.2f},\n"
                    f"  \"distance\": {self.filtered_distance:.2f},\n"
                    f"  \"ballast_pct\": {ballast_pct:.2f},\n"
                    f"  \"cargo_kg\": {self.diagnostic_cargo_kg:.2f},\n"
                    f"  \"status\": \"{status_str}\",\n"
                    f"  \"risk\": \"{risk_str}\"\n"
                    "}\n"
                    "---\n"
                )
                self.serial_output_queue.append(packet_str)

            # Drain queue to emitted text
            emitted = "".join(self.serial_output_queue)
            self.serial_output_queue.clear()
            return emitted

    # --- MATHEMATICAL CONVERSION HELPERS ---
    def _read_distance_filtered(self) -> float:
        return self.filtered_distance

    def _distance_to_depth(self, dist: float) -> float:
        depth = self.TANK_EMPTY_DIST - dist
        return max(0.0, min(self.TANK_EMPTY_DIST - self.TANK_FULL_DIST, depth))

    def _depth_to_volume_liters(self, depth_cm: float) -> float:
        return (depth_cm * self.TANK_AREA_CM2) / 1000.0

    def _distance_to_ballast_pct(self, dist: float) -> float:
        if dist < 0:
            return -1.0
        pct = (self.TANK_EMPTY_DIST - dist) / (self.TANK_EMPTY_DIST - self.TANK_FULL_DIST) * 100.0
        return max(0.0, min(100.0, pct))

    def _get_risk(self, roll: float, pitch: float) -> str:
        score = abs(roll) + abs(pitch)
        if score < 5.0:
            return "SAFE"
        if score < 12.0:
            return "WARNING"
        return "CRITICAL"

    def _predict_flow_rate_lps(self, depth_cm: float) -> float:
        h_m = depth_cm / 100.0
        if h_m <= 0:
            return 0.0
        a_m2 = self.GATE_OPEN_AREA_CM2 / 10000.0
        q_m3s = self.DISCHARGE_COEFFICIENT * a_m2 * math.sqrt(2.0 * 9.81 * h_m)
        return q_m3s * 1000.0

    def get_firmware_state(self) -> Dict[str, Any]:
        """Returns internal virtual hardware register values for diagnostics."""
        with self._lock:
            depth_cm = self._distance_to_depth(self.filtered_distance)
            flow_rate = round(self._predict_flow_rate_lps(depth_cm), 2) if self.is_draining else 0.0
            status_str = "SENSOR_ERROR" if self.sensor_fault else ("DRAINING" if self.is_draining else "IDLE")
            warnings_list = ["WARNING_ULTRASONIC_TIMEOUT"] if self.sensor_fault else []
            return {
                "active_scenario": self.active_scenario,
                "roll_deg": round(self.current_roll, 2),
                "pitch_deg": round(self.current_pitch, 2),
                "distance_cm": round(self.filtered_distance, 2),
                "ballast_pct": round(self._distance_to_ballast_pct(self.filtered_distance), 2),
                "diagnostic_cargo_kg": round(self.diagnostic_cargo_kg, 2),
                "gate_servo_angle": self.gate_servo_angle,
                "servo_gate_deg": self.gate_servo_angle,
                "pump_led": self.pump_led,
                "pump_active": self.pump_led,
                "warn_led": self.warn_led,
                "is_draining": self.is_draining,
                "flow_rate_l_s": flow_rate,
                "status": status_str,
                "warnings": warnings_list,
                "sensor_fault": self.sensor_fault,
                "baudrate": self.BAUDRATE,
                "provenance_tag": "[SIMULATED ESP32]"
            }
