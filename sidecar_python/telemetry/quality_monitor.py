"""
Telemetry Quality & Freshness Monitor for MareTide.
Monitors packet rates, detects stale data, sensor freezes, and hardware disconnections,
and manages safe degradation fallbacks.
"""

import time
import collections
import logging
from typing import Optional, Dict, Any, Deque

from telemetry.models import (
    NormalizedTelemetry,
    ConnectionStatus,
    DataQuality,
    TelemetryHealthMetrics,
    TelemetrySource
)

logger = logging.getLogger("telemetry.quality")


class TelemetryQualityMonitor:
    """
    Evaluates packet freshness, connection continuity, and data fidelity.
    """

    def __init__(
        self,
        stale_threshold_sec: float = 2.0,
        disconnect_threshold_sec: float = 5.0,
        frozen_window_size: int = 25
    ):
        self.stale_threshold_sec = stale_threshold_sec
        self.disconnect_threshold_sec = disconnect_threshold_sec
        self.frozen_window_size = frozen_window_size

        self.last_packet_epoch: float = time.time()
        self.last_valid_telemetry: Optional[NormalizedTelemetry] = None
        self.start_time: float = time.time()

        self.packet_count: int = 0
        self.stale_count: int = 0
        self.disconnect_count: int = 0
        self.malformed_count: int = 0
        self.prohibited_load_cell_attempts: int = 0

        # Rolling history for freeze detection
        self._roll_history: Deque[float] = collections.deque(maxlen=frozen_window_size)
        self._pitch_history: Deque[float] = collections.deque(maxlen=frozen_window_size)

    def record_packet(self, telemetry: NormalizedTelemetry, is_malformed: bool = False, has_prohibited: bool = False):
        """Updates health statistics on incoming packet."""
        now = time.time()
        self.packet_count += 1
        self.last_packet_epoch = now
        
        if is_malformed:
            self.malformed_count += 1
        if has_prohibited:
            self.prohibited_load_cell_attempts += 1

        if not is_malformed:
            self.last_valid_telemetry = telemetry
            self._roll_history.append(telemetry.vessel_state.roll_deg)
            self._pitch_history.append(telemetry.vessel_state.pitch_deg)

    def evaluate_quality(
        self,
        current_telemetry: NormalizedTelemetry,
        is_adapter_connected: bool = True
    ) -> NormalizedTelemetry:
        """
        Assesses freshness, stale status, disconnect status, and applies safe fallbacks if necessary.
        """
        now = time.time()
        age = max(0.0, now - self.last_packet_epoch)

        # 1. Disconnect Detection
        if not is_adapter_connected or age > self.disconnect_threshold_sec:
            if current_telemetry.connection_status != ConnectionStatus.DISCONNECTED:
                self.disconnect_count += 1
            current_telemetry.connection_status = ConnectionStatus.DISCONNECTED
            current_telemetry.metadata.data_quality = DataQuality.DEGRADED
            current_telemetry.metadata.stale_seconds = round(age, 2)
            warning_msg = f"Connection lost: Telemetry source is disconnected (no updates received for {age:.1f}s)."
            if not any("disconnected" in w.lower() for w in current_telemetry.metadata.warnings):
                current_telemetry.metadata.warnings.append(warning_msg)
            return current_telemetry

        # 2. Invalid Data Detection
        if current_telemetry.metadata.validation_status == "INVALID":
            current_telemetry.connection_status = ConnectionStatus.INVALID_DATA
            current_telemetry.metadata.data_quality = DataQuality.INVALID
            current_telemetry.metadata.stale_seconds = round(age, 2)
            return current_telemetry

        # 3. Stale Detection
        if age > self.stale_threshold_sec:
            if current_telemetry.connection_status != ConnectionStatus.STALE:
                self.stale_count += 1
            current_telemetry.connection_status = ConnectionStatus.STALE
            current_telemetry.metadata.data_quality = DataQuality.STALE
            current_telemetry.metadata.stale_seconds = round(age, 2)
            warning_msg = f"Stale telemetry warning: Data age ({age:.1f}s) exceeds freshness threshold ({self.stale_threshold_sec:.1f}s)."
            if warning_msg not in current_telemetry.metadata.warnings:
                current_telemetry.metadata.warnings.append(warning_msg)
            return current_telemetry

        # 4. Hardware Connection Status
        if current_telemetry.source == TelemetrySource.HARDWARE_SENSOR:
            current_telemetry.connection_status = ConnectionStatus.CONNECTED
        elif current_telemetry.source == TelemetrySource.SIMULATED_ESP32:
            current_telemetry.connection_status = ConnectionStatus.CONNECTED
        else:
            current_telemetry.connection_status = ConnectionStatus.SIMULATED

        # 5. Frozen Sensor Check (only on live hardware feeds)
        if current_telemetry.source == TelemetrySource.HARDWARE_SENSOR and len(self._roll_history) == self.frozen_window_size:
            roll_variance = max(self._roll_history) - min(self._roll_history)
            pitch_variance = max(self._pitch_history) - min(self._pitch_history)
            if roll_variance == 0.0 and pitch_variance == 0.0:
                current_telemetry.metadata.data_quality = DataQuality.DEGRADED
                freeze_msg = f"Sensor freeze detected: {self.frozen_window_size} identical readings received without fluctuation."
                if freeze_msg not in current_telemetry.metadata.warnings:
                    current_telemetry.metadata.warnings.append(freeze_msg)

        current_telemetry.metadata.stale_seconds = round(age, 2)
        return current_telemetry

    def get_health_metrics(
        self,
        active_source: TelemetrySource,
        active_adapter: str,
        current_status: ConnectionStatus,
        current_quality: DataQuality,
        is_simulated: bool
    ) -> TelemetryHealthMetrics:
        now = time.time()
        uptime = max(0.0, now - self.start_time)
        pps = round(self.packet_count / uptime, 2) if uptime > 0 else 0.0
        age = max(0.0, round(now - self.last_packet_epoch, 2))

        return TelemetryHealthMetrics(
            active_source=active_source,
            active_adapter=active_adapter,
            connection_status=current_status,
            data_quality=current_quality,
            packet_count=self.packet_count,
            packets_per_second=pps,
            stale_count=self.stale_count,
            disconnect_count=self.disconnect_count,
            malformed_count=self.malformed_count,
            prohibited_load_cell_attempts=self.prohibited_load_cell_attempts,
            uptime_seconds=round(uptime, 1),
            last_packet_age_seconds=age,
            is_simulated=is_simulated
        )
