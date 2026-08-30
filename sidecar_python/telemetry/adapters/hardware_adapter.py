"""
Hardware Serial Telemetry Adapter for MareTide.
Communicates with physical ESP32 microcontrollers over UART / COM ports,
decodes incoming JSON telemetry packets, handles disconnections and auto-reconnection.
"""

import threading
import time
import json
import logging
from typing import Dict, Any, Optional, List
import serial
import serial.tools.list_ports

from telemetry.adapters.base import BaseTelemetryAdapter
from telemetry.models import TelemetrySource, ConnectionStatus

logger = logging.getLogger("telemetry.hardware")


class HardwareSerialAdapter(BaseTelemetryAdapter):
    """
    Hardware adapter connecting to ESP32 over serial UART.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        timeout: float = 1.0,
        reconnect_interval: float = 2.0
    ):
        super().__init__(adapter_id="hardware_serial_esp32", source_type=TelemetrySource.HARDWARE_SENSOR)
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reconnect_interval = reconnect_interval
        
        self.ser: Optional[serial.Serial] = None
        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        self._latest_raw: Dict[str, Any] = {}
        self._last_read_time = 0.0
        self._packet_count = 0
        self._error_count = 0
        self._last_error: Optional[str] = None

    @staticmethod
    def get_available_ports() -> List[str]:
        """Scans the host system for active serial COM ports."""
        try:
            ports = serial.tools.list_ports.comports()
            return [p.device for p in ports]
        except Exception as e:
            logger.warning(f"Error scanning serial ports: {e}")
            return []

    def connect(self) -> bool:
        if self._running:
            return self._connected

        self._running = True
        self._thread = threading.Thread(target=self._run_reader_loop, daemon=True)
        self._thread.start()
        return True

    def disconnect(self) -> None:
        self._running = False
        self._connected = False
        if self.ser:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except Exception as e:
                logger.warning(f"Error closing serial port: {e}")
            finally:
                self.ser = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected and (self.ser is not None) and self.ser.is_open

    def read_raw(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._latest_raw:
                return None
            return self._latest_raw.copy()

    def send_command(self, command: str, **kwargs) -> bool:
        """Dispatches an ASCII command to the ESP32 (e.g. 'DRAIN:24.0\n')."""
        with self._lock:
            if not self._connected or not self.ser or not self.ser.is_open:
                logger.warning("Cannot send command: hardware port not connected")
                return False
            try:
                cmd_str = command.strip()
                if not cmd_str.endswith("\n"):
                    cmd_str += "\n"
                self.ser.write(cmd_str.encode("utf-8"))
                self.ser.flush()
                return True
            except Exception as e:
                logger.error(f"Failed to write serial command '{command}': {e}")
                self._error_count += 1
                self._last_error = str(e)
                return False

    def get_adapter_info(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "adapter_id": self.adapter_id,
                "source_type": self.source_type.value,
                "port": self.port,
                "baudrate": self.baudrate,
                "connected": self._connected,
                "packet_count": self._packet_count,
                "error_count": self._error_count,
                "last_read_time": self._last_read_time,
                "last_error": self._last_error,
                "is_simulated": False
            }

    def _run_reader_loop(self):
        """Background thread that handles connection, reading, and auto-reconnect."""
        buffer = ""
        while self._running:
            # 1. Ensure serial port is connected
            if not self.ser or not self.ser.is_open:
                if not self.port:
                    # Auto-detect available COM port if none specified
                    available = self.get_available_ports()
                    target_port = available[0] if available else None
                else:
                    target_port = self.port

                if target_port:
                    try:
                        self.ser = serial.Serial(target_port, self.baudrate, timeout=self.timeout)
                        with self._lock:
                            self._connected = True
                            self.port = target_port
                            self._last_error = None
                        logger.info(f"Connected to ESP32 on port {target_port}")
                    except Exception as e:
                        with self._lock:
                            self._connected = False
                            self._last_error = str(e)
                        time.sleep(self.reconnect_interval)
                        continue
                else:
                    with self._lock:
                        self._connected = False
                        self._last_error = "No serial COM ports detected on host"
                    time.sleep(self.reconnect_interval)
                    continue

            # 2. Read incoming data stream
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                    raw_chunk = self.ser.read(self.ser.in_waiting).decode("utf-8", errors="ignore")
                    buffer += raw_chunk

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line.startswith("{") and line.endswith("}"):
                            try:
                                parsed = json.loads(line)
                                with self._lock:
                                    self._latest_raw = parsed
                                    self._last_read_time = time.time()
                                    self._packet_count += 1
                            except json.JSONDecodeError:
                                pass  # Incomplete JSON fragment
            except (serial.SerialException, OSError) as e:
                logger.warning(f"Serial connection lost on port {self.port}: {e}")
                with self._lock:
                    self._connected = False
                    self._last_error = str(e)
                    self._error_count += 1
                try:
                    if self.ser and self.ser.is_open:
                        self.ser.close()
                except Exception:
                    pass
                self.ser = None
                time.sleep(self.reconnect_interval)

            time.sleep(0.05)
