"""
Virtual ESP32 Adapter for MareTide Telemetry Subsystem.

Provides an in-memory serial UART stream from VirtualESP32Firmware, passing raw
multi-line string chunks through extract_json_from_buffer identically to physical hardware.
"""

import threading
import time
import logging
from typing import Dict, Any, Optional, List

from telemetry.models import TelemetrySource, ConnectionStatus
from telemetry.adapters.base import BaseTelemetryAdapter
from telemetry.adapters.hardware_adapter import extract_json_from_buffer
from telemetry.simulators.virtual_esp32_firmware import VirtualESP32Firmware

logger = logging.getLogger("telemetry.virtual_esp32_adapter")


class VirtualESP32Adapter(BaseTelemetryAdapter):
    """
    Adapter interfacing with the Virtual ESP32 firmware emulator over simulated UART stream.
    """

    def __init__(self):
        super().__init__(adapter_id="virtual_esp32_simulator", source_type=TelemetrySource.SIMULATED_ESP32)
        self.firmware = VirtualESP32Firmware()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._buffer = ""
        self._connected = False
        self._last_packet_time = 0.0
        self._latest_raw: Optional[Dict[str, Any]] = None

    def connect(self) -> bool:
        """Starts the virtual firmware clock and streaming thread."""
        with self._lock:
            if self._running:
                return True
            self._running = True
            self.firmware.boot()
            self._connected = True
            self._buffer = ""
            self._last_packet_time = time.time()
            self._thread = threading.Thread(target=self._run_virtual_uart_loop, daemon=True)
            self._thread.start()
            logger.info("VirtualESP32Adapter connected and streaming.")
            return True

    def disconnect(self) -> None:
        """Stops the virtual UART streaming thread."""
        with self._lock:
            self._running = False
            self._connected = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
                self._thread = None
            logger.info("VirtualESP32Adapter disconnected.")

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected and self.firmware.active_scenario != "DISCONNECTED"

    def read_raw(self) -> Optional[Dict[str, Any]]:
        """Reads latest raw telemetry packet."""
        with self._lock:
            return self._latest_raw

    def send_command(self, command: str, **kwargs) -> bool:
        """Sends command string to virtual microcontroller (e.g. DRAIN:<target>)."""
        self.firmware.send_command(command)
        return True

    def set_scenario(self, scenario: str) -> bool:
        """Switches the active scenario on the virtual firmware."""
        return self.firmware.set_scenario(scenario)

    def get_adapter_info(self) -> Dict[str, Any]:
        """Returns status, configuration, and health details about the adapter."""
        return {
            "adapter_id": self.adapter_id,
            "source_type": self.source_type.value,
            "is_simulated": True,
            "connected": self.is_connected(),
            "firmware_state": self.firmware.get_firmware_state()
        }

    def get_firmware_state(self) -> Dict[str, Any]:
        """Returns diagnostic virtual hardware registers."""
        return self.firmware.get_firmware_state()

    def _run_virtual_uart_loop(self):
        """Simulates 50Hz microcontroller loop ticks and 115200 baud streaming chunks."""
        while self._running:
            dt = 0.02 # 20 ms tick (50 Hz)
            raw_text = self.firmware.step(dt_sec=dt)

            if raw_text:
                self._buffer += raw_text

                # Parse multi-line JSON blocks using the exact hardware parser
                packets, self._buffer = extract_json_from_buffer(self._buffer)
                for pkt in packets:
                    with self._lock:
                        self._last_read_time = time.time()
                        pkt["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        pkt["timestamp_epoch"] = self._last_read_time
                        self._latest_raw = pkt

            time.sleep(dt)
