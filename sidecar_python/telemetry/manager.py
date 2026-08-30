"""
Telemetry Manager Singleton Orchestrator for MareTide.
Coordinates active telemetry adapters, normalization, validation, quality monitoring,
and broadcasts normalized vessel states to downstream consumers (Digital Twin, Stability Engine).
"""

import threading
import time
import logging
from typing import Dict, Any, Optional, List, Callable

from telemetry.models import (
    NormalizedTelemetry,
    TelemetrySource,
    ConnectionStatus,
    DataQuality,
    TelemetryHealthMetrics
)
from telemetry.adapters.base import BaseTelemetryAdapter
from telemetry.adapters.simulator_adapter import SimulatorTelemetryAdapter
from telemetry.adapters.hardware_adapter import HardwareSerialAdapter
from telemetry.adapters.virtual_esp32_adapter import VirtualESP32Adapter
from telemetry.normalizer import TelemetryNormalizer
from telemetry.validator import TelemetryValidator
from telemetry.quality_monitor import TelemetryQualityMonitor

logger = logging.getLogger("telemetry.manager")


class TelemetryManager:
    """
    Central, thread-safe Telemetry Management Subsystem.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        import os
        self._mutex = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Quality monitor
        self.quality_monitor = TelemetryQualityMonitor()
        
        # Adapters
        self._sim_adapter = SimulatorTelemetryAdapter()
        self._hw_adapter = HardwareSerialAdapter()
        self._virtual_esp32_adapter = VirtualESP32Adapter()
        
        # Mode from environment (MARETIDE_TELEMETRY_MODE or EV_TELEMETRY_MODE)
        env_mode = (
            os.environ.get("MARETIDE_TELEMETRY_MODE")
            or os.environ.get("EV_TELEMETRY_MODE")
            or os.environ.get("TELEMETRY_MODE")
            or ""
        ).strip().lower()

        serial_port = (
            os.environ.get("MARETIDE_SERIAL_PORT")
            or os.environ.get("EV_SERIAL_PORT")
            or os.environ.get("SERIAL_PORT")
        )

        if env_mode in ["virtual_esp32", "virtual", "simulated_esp32"]:
            self._active_adapter = self._virtual_esp32_adapter
            initial_source = TelemetrySource.SIMULATED_ESP32
            initial_status = ConnectionStatus.CONNECTED
        elif env_mode in ["real_esp32", "hardware", "hardware_sensor", "real"]:
            if serial_port:
                self._hw_adapter.port = serial_port
            self._active_adapter = self._hw_adapter
            initial_source = TelemetrySource.HARDWARE_SENSOR
            initial_status = ConnectionStatus.DISCONNECTED
        else:
            self._active_adapter = self._sim_adapter
            initial_source = TelemetrySource.SIMULATED_TELEMETRY
            initial_status = ConnectionStatus.SIMULATED

        # State caches
        self._latest_normalized: NormalizedTelemetry = TelemetryNormalizer.get_safe_fallback_telemetry(
            source=initial_source,
            connection_status=initial_status
        )
        self._listeners: List[Callable[[NormalizedTelemetry], None]] = []
        self._sequence_counter = 0

    @classmethod
    def get_instance(cls) -> "TelemetryManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.start()
            return cls._instance

    def start(self):
        """Starts the active adapter and background telemetry processing thread."""
        with self._mutex:
            if self._running:
                return
            self._running = True
            self._active_adapter.connect()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info(f"TelemetryManager initialized with active adapter: {self._active_adapter.adapter_id}")

    def stop(self):
        """Stops telemetry collection and shuts down adapters."""
        with self._mutex:
            self._running = False
            if self._active_adapter:
                self._active_adapter.disconnect()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
                self._thread = None

    def select_source(self, source: Any, port: Optional[str] = None) -> bool:
        """Switches the active telemetry source between Simulator, Virtual ESP32, and Hardware Serial."""
        if isinstance(source, str):
            source_lower = source.strip().lower()
            if source_lower in ["hardware_sensor", "real_esp32", "real", "hardware"]:
                source_enum = TelemetrySource.HARDWARE_SENSOR
            elif source_lower in ["simulated_esp32", "virtual_esp32", "virtual"]:
                source_enum = TelemetrySource.SIMULATED_ESP32
            else:
                source_enum = TelemetrySource.SIMULATED_TELEMETRY
        else:
            source_enum = source

        with self._mutex:
            if self._active_adapter:
                self._active_adapter.disconnect()

            if source_enum == TelemetrySource.HARDWARE_SENSOR:
                if port:
                    self._hw_adapter.port = port
                self._active_adapter = self._hw_adapter
                init_status = ConnectionStatus.CONNECTED if self._hw_adapter.is_connected() else ConnectionStatus.DISCONNECTED
            elif source_enum == TelemetrySource.SIMULATED_ESP32:
                self._active_adapter = self._virtual_esp32_adapter
                init_status = ConnectionStatus.CONNECTED
            else:
                self._active_adapter = self._sim_adapter
                init_status = ConnectionStatus.SIMULATED

            if self._running:
                self._active_adapter.connect()

            self._latest_normalized = TelemetryNormalizer.get_safe_fallback_telemetry(
                source=self._active_adapter.source_type,
                connection_status=init_status
            )
            logger.info(f"Switched telemetry source to {source_enum.value} (Adapter: {self._active_adapter.adapter_id})")
            return True

    def set_virtual_scenario(self, scenario: str) -> bool:
        """Configures scenario for Virtual ESP32 adapter."""
        return self._virtual_esp32_adapter.set_scenario(scenario)

    def send_virtual_command(self, cmd: str) -> None:
        """Sends command to Virtual ESP32 microcontroller."""
        self._virtual_esp32_adapter.send_command(cmd)

    def get_virtual_firmware_state(self) -> Dict[str, Any]:
        """Returns internal registers of Virtual ESP32."""
        return self._virtual_esp32_adapter.get_firmware_state()

    def get_active_adapter(self) -> BaseTelemetryAdapter:
        with self._mutex:
            return self._active_adapter

    def get_latest_telemetry(self) -> NormalizedTelemetry:
        """Returns a thread-safe copy of the latest normalized telemetry model."""
        with self._mutex:
            # Re-evaluate quality on read to ensure fresh stale/disconnect flags
            evaluated = self.quality_monitor.evaluate_quality(
                self._latest_normalized,
                is_adapter_connected=self._active_adapter.is_connected()
            )
            return evaluated

    def get_legacy_telemetry_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary compatible with legacy endpoints, strictly
        containing NO sensor cargo weight (cargo_kg is set to 0.0 or from active manifest).
        """
        telemetry = self.get_latest_telemetry()
        # Find first tank distance and ballast level
        first_tank = next(iter(telemetry.ballast_tanks.values()), None)
        dist = first_tank.distance_cm if first_tank else 10.0
        ballast_pct = first_tank.level_pct if first_tank else 100.0

        return {
            "roll": telemetry.vessel_state.roll_deg,
            "pitch": telemetry.vessel_state.pitch_deg,
            "distance": dist,
            "ballast_pct": ballast_pct,
            "cargo_kg": 0.0,  # Strict Phase 5 Load Cell Exclusion: Sensor cargo is always 0
            "status": telemetry.operational_telemetry.status,
            "risk": telemetry.operational_telemetry.risk_level,
            "is_simulated": (telemetry.source == TelemetrySource.SIMULATED_TELEMETRY),
            "telemetry_source": telemetry.source.value,
            "connection_status": telemetry.connection_status.value,
            "data_quality": telemetry.metadata.data_quality.value
        }

    def send_command(self, command: str, **kwargs) -> bool:
        """Sends an operational command through the active telemetry adapter."""
        with self._mutex:
            return self._active_adapter.send_command(command, **kwargs)

    def set_simulator_overrides(self, roll: Optional[float] = None, pitch: Optional[float] = None, ballast_pct: Optional[float] = None):
        """Applies manual simulation overrides."""
        with self._mutex:
            if isinstance(self._active_adapter, SimulatorTelemetryAdapter):
                if roll is not None or pitch is not None:
                    self._active_adapter.set_override_tilt(roll, pitch)
                if ballast_pct is not None:
                    self._active_adapter.set_override_ballast(ballast_pct)
                if roll is not None:
                    self._latest_normalized.vessel_state.roll_deg = float(roll)
                if pitch is not None:
                    self._latest_normalized.vessel_state.pitch_deg = float(pitch)
                if ballast_pct is not None:
                    for t in self._latest_normalized.ballast_tanks.values():
                        t.level_pct = float(ballast_pct)

    def clear_simulator_overrides(self):
        """Clears all simulator manual overrides."""
        with self._mutex:
            if isinstance(self._active_adapter, SimulatorTelemetryAdapter):
                self._active_adapter.clear_overrides()

    def register_listener(self, callback: Callable[[NormalizedTelemetry], None]):
        """Registers a callback to receive normalized telemetry on every tick."""
        with self._mutex:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def get_health_metrics(self) -> TelemetryHealthMetrics:
        with self._mutex:
            telemetry = self._latest_normalized
            return self.quality_monitor.get_health_metrics(
                active_source=telemetry.source,
                active_adapter=self._active_adapter.adapter_id,
                current_status=telemetry.connection_status,
                current_quality=telemetry.metadata.data_quality,
                is_simulated=self._active_adapter.is_simulated
            )

    def _run_loop(self):
        """Continuous collection, validation, normalization, and broadcast loop."""
        while self._running:
            try:
                adapter = self._active_adapter
                is_conn = adapter.is_connected()
                raw_packet = adapter.read_raw() if is_conn else None

                self._sequence_counter += 1
                
                # 1. Validation & Normalization
                if raw_packet is not None:
                    validation_res = TelemetryValidator.validate_raw_packet(
                        raw_data=raw_packet,
                        source=adapter.source_type,
                        strict_load_cell_check=False
                    )
                    
                    # Normalize raw packet into clean contract
                    normalized = TelemetryNormalizer.normalize_raw_packet(
                        raw_data=raw_packet,
                        source=adapter.source_type,
                        connection_status=ConnectionStatus.CONNECTED if not adapter.is_simulated else ConnectionStatus.SIMULATED,
                        adapter_id=adapter.adapter_id,
                        sequence_num=self._sequence_counter
                    )

                    # Update quality tracking
                    self.quality_monitor.record_packet(
                        normalized,
                        is_malformed=not validation_res.is_valid,
                        has_prohibited=len(validation_res.prohibited_fields_detected) > 0
                    )
                else:
                    # No raw packet available -> evaluate fallback
                    status = ConnectionStatus.DISCONNECTED if not is_conn else ConnectionStatus.STALE
                    normalized = TelemetryNormalizer.get_safe_fallback_telemetry(
                        source=adapter.source_type,
                        connection_status=status,
                        reason="No raw packet available from adapter"
                    )

                # 2. Evaluate Quality & Freshness
                evaluated_telemetry = self.quality_monitor.evaluate_quality(
                    normalized,
                    is_adapter_connected=is_conn
                )

                # 3. Store Latest State
                with self._mutex:
                    self._latest_normalized = evaluated_telemetry
                    listeners = list(self._listeners)

                # 4. Dispatch to Listeners
                for cb in listeners:
                    try:
                        cb(evaluated_telemetry)
                    except Exception as e:
                        logger.error(f"Error invoking telemetry callback: {e}")

            except Exception as ex:
                logger.error(f"Error in telemetry manager loop: {ex}")

            time.sleep(0.05)  # 20 Hz loop with proper CPU relaxation
