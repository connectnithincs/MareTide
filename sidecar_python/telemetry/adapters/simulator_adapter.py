"""
Simulator Telemetry Adapter for MareTide.
Generates dynamic, realistic maritime vessel telemetry (wave roll/pitch,
ultrasonic distance, ballast percentages, pump operations, and fluid flow rates).
"""

import threading
import time
import math
import random
import logging
from typing import Dict, Any, Optional

from telemetry.adapters.base import BaseTelemetryAdapter
from telemetry.models import TelemetrySource, PumpState

logger = logging.getLogger("telemetry.simulator")


class SimulatorTelemetryAdapter(BaseTelemetryAdapter):
    """
    Simulated telemetry source for testing, demonstration, and offline operation.
    """

    def __init__(self, tick_interval: float = 0.1):
        super().__init__(adapter_id="simulator_vessel_engine", source_type=TelemetrySource.SIMULATED_TELEMETRY)
        self.tick_interval = tick_interval
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Internal simulator states
        self._sim_tank_empty_dist = 30.0  # cm
        self._sim_tank_full_dist = 10.0   # cm
        self._current_dist = 10.0         # Start with full ballast
        self._target_dist = 10.0
        self._is_draining = False
        self._is_filling = False
        self._flow_rate_l_s = 0.0
        self._cumulative_flow_m3 = 0.0
        self._status = "IDLE"
        
        # Overrides
        self._override_roll: Optional[float] = None
        self._override_pitch: Optional[float] = None
        self._override_ballast_pct: Optional[float] = None
        
        # Wave simulation params
        self._wave_phase = 0.0
        self._wave_freq = 0.2  # Hz
        self._wave_amplitude_roll = 0.6  # deg
        self._wave_amplitude_pitch = 0.3  # deg
        
        self._latest_raw: Dict[str, Any] = {}
        self._packet_count = 0
        self._start_time = time.time()

    def connect(self) -> bool:
        if self._running:
            return True
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._thread.start()
        return True

    def disconnect(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def is_connected(self) -> bool:
        return self._running

    def read_raw(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._latest_raw:
                return None
            return self._latest_raw.copy()

    def set_override_tilt(self, roll: Optional[float], pitch: Optional[float]):
        """Sets manual roll/pitch tilt overrides (pass None to clear)."""
        with self._lock:
            self._override_roll = float(roll) if roll is not None else None
            self._override_pitch = float(pitch) if pitch is not None else None
            if self._override_roll is not None and "roll" in self._latest_raw:
                self._latest_raw["roll"] = self._override_roll
            if self._override_pitch is not None and "pitch" in self._latest_raw:
                self._latest_raw["pitch"] = self._override_pitch

    def set_override_ballast(self, ballast_pct: Optional[float]):
        """Sets manual ballast percentage override (pass None to clear)."""
        with self._lock:
            self._override_ballast_pct = float(ballast_pct) if ballast_pct is not None else None
            if self._override_ballast_pct is not None:
                pct = max(0.0, min(100.0, self._override_ballast_pct))
                self._current_dist = self._sim_tank_empty_dist - (pct / 100.0) * (self._sim_tank_empty_dist - self._sim_tank_full_dist)
                self._target_dist = self._current_dist
                if "ballast_pct" in self._latest_raw:
                    self._latest_raw["ballast_pct"] = pct
                if "distance" in self._latest_raw:
                    self._latest_raw["distance"] = round(self._current_dist, 2)

    def clear_overrides(self):
        """Clears all manual overrides."""
        with self._lock:
            self._override_roll = None
            self._override_pitch = None
            self._override_ballast_pct = None

    def trigger_drain(self, target_qty_t: float = 20.0):
        """Simulates initiating a ballast drain cycle."""
        with self._lock:
            self._is_draining = True
            self._is_filling = False
            # Calculate target distance from drain quantity (300t capacity = 20cm range)
            dist_delta = (target_qty_t / 300.0) * (self._sim_tank_empty_dist - self._sim_tank_full_dist)
            self._target_dist = min(self._sim_tank_empty_dist, self._current_dist + dist_delta)
            self._flow_rate_l_s = 0.85
            self._status = "DRAINING"

    def trigger_fill(self, target_qty_t: float = 20.0):
        """Simulates initiating a ballast fill cycle."""
        with self._lock:
            self._is_filling = True
            self._is_draining = False
            dist_delta = (target_qty_t / 300.0) * (self._sim_tank_empty_dist - self._sim_tank_full_dist)
            self._target_dist = max(self._sim_tank_full_dist, self._current_dist - dist_delta)
            self._flow_rate_l_s = 0.85
            self._status = "FILLING"

    def send_command(self, command: str, **kwargs) -> bool:
        cmd = command.strip().upper()
        if "DRAIN" in cmd:
            qty = kwargs.get("qty", 20.0)
            self.trigger_drain(qty)
            return True
        elif "FILL" in cmd:
            qty = kwargs.get("qty", 20.0)
            self.trigger_fill(qty)
            return True
        elif "SET_TILT" in cmd:
            self.set_override_tilt(kwargs.get("roll"), kwargs.get("pitch"))
            return True
        elif "RESET" in cmd or "IDLE" in cmd:
            with self._lock:
                self._is_draining = False
                self._is_filling = False
                self._flow_rate_l_s = 0.0
                self._status = "IDLE"
            return True
        return False

    def get_adapter_info(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "adapter_id": self.adapter_id,
                "source_type": self.source_type.value,
                "connected": self._running,
                "packet_count": self._packet_count,
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "is_simulated": True,
                "active_overrides": {
                    "roll": self._override_roll,
                    "pitch": self._override_pitch,
                    "ballast_pct": self._override_ballast_pct
                }
            }

    def _simulation_loop(self):
        """Generates continuous 10Hz simulated vessel dynamics."""
        while self._running:
            now = time.time()
            self._wave_phase += (2.0 * math.pi * self._wave_freq * self.tick_interval)

            with self._lock:
                # 1. Simulate Ballast Fluid Movement & Flow Rates
                if self._is_draining:
                    if self._current_dist < self._target_dist:
                        step = 0.12 * self.tick_interval
                        self._current_dist = min(self._target_dist, self._current_dist + step)
                        self._flow_rate_l_s = 0.85 + random.uniform(-0.03, 0.03)
                        self._cumulative_flow_m3 += (self._flow_rate_l_s * self.tick_interval / 1000.0)
                        self._status = "DRAINING"
                    else:
                        self._is_draining = False
                        self._flow_rate_l_s = 0.0
                        self._status = "READY"
                elif self._is_filling:
                    if self._current_dist > self._target_dist:
                        step = 0.12 * self.tick_interval
                        self._current_dist = max(self._target_dist, self._current_dist - step)
                        self._flow_rate_l_s = 0.85 + random.uniform(-0.03, 0.03)
                        self._cumulative_flow_m3 += (self._flow_rate_l_s * self.tick_interval / 1000.0)
                        self._status = "FILLING"
                    else:
                        self._is_filling = False
                        self._flow_rate_l_s = 0.0
                        self._status = "READY"
                else:
                    self._flow_rate_l_s = 0.0
                    if self._status not in ["READY", "STANDBY", "ALARM"]:
                        self._status = "IDLE"

                # 2. Compute Ballast Fill Percentage
                ballast_pct = (self._sim_tank_empty_dist - self._current_dist) / \
                              (self._sim_tank_empty_dist - self._sim_tank_full_dist) * 100.0
                ballast_pct = max(0.0, min(100.0, ballast_pct))

                if self._override_ballast_pct is not None:
                    ballast_pct = self._override_ballast_pct

                # 3. Compute Roll and Pitch Dynamics
                wave_roll = math.sin(self._wave_phase) * self._wave_amplitude_roll + random.uniform(-0.05, 0.05)
                wave_pitch = math.cos(self._wave_phase * 0.8) * self._wave_amplitude_pitch + random.uniform(-0.03, 0.03)

                roll = self._override_roll if self._override_roll is not None else wave_roll
                pitch = self._override_pitch if self._override_pitch is not None else wave_pitch

                # 4. Construct Raw Simulation Payload
                self._packet_count += 1
                datetime_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
                self._latest_raw = {
                    "timestamp": datetime_iso,
                    "timestamp_epoch": now,
                    "roll": round(roll, 2),
                    "pitch": round(pitch, 2),
                    "heave": round(math.sin(self._wave_phase * 0.5) * 0.1, 2),
                    "distance": round(self._current_dist, 2),
                    "ballast_pct": round(ballast_pct, 1),
                    "flow_rate_l_s": round(self._flow_rate_l_s, 2),
                    "cumulative_flow_m3": round(self._cumulative_flow_m3, 3),
                    "status": self._status,
                    "risk": "SAFE" if abs(roll) < 5.0 and abs(pitch) < 3.0 else ("WARNING" if abs(roll) < 12.0 else "CRITICAL")
                }

            time.sleep(self.tick_interval)
