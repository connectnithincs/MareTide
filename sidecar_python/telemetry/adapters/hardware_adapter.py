"""
Hardware Serial Telemetry Adapter for MareTide.
Communicates with physical ESP32 microcontrollers over UART / COM ports,
decodes incoming JSON telemetry packets (including multi-line blocks, --- delimiters, and boot messages),
handles disconnections and auto-reconnection.

CRITICAL INVARIANT:
The ESP32 sketch (esp32_sensor_sketch.ino) includes an HX711 load-cell interface (cargo_kg).
In accordance with MareTide maritime safety architecture, load-cell data is quarantined
and NEVER used as container cargo weight, gross mass, or input into stability calculations
or stowage optimization. Container cargo weight originates exclusively from SOLAS Document AI.
"""

import threading
import time
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
import serial
import serial.tools.list_ports

from telemetry.adapters.base import BaseTelemetryAdapter
from telemetry.models import TelemetrySource, ConnectionStatus

logger = logging.getLogger("telemetry.hardware")


def extract_json_from_buffer(buffer: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Extracts all complete JSON dictionaries from a continuous serial stream buffer.
    Handles:
      1. Single-line JSON Lines (e.g. {"roll": 1.0, "pitch": 0.5}\\n)
      2. Multi-line JSON blocks bounded by '{' and '}' spanning newlines as output by esp32_sensor_sketch.ino
      3. Delimiters such as '---'
      4. Boot banners ('MPU6050: OK', 'NAVI-AI ESP32 Ready') and warning/status text
    Returns:
      (extracted_json_list, remaining_buffer)
    """
    packets: List[Dict[str, Any]] = []
    
    while "{" in buffer:
        start_idx = buffer.find("{")
        # Discard non-JSON leading text/banners
        if start_idx > 0:
            buffer = buffer[start_idx:]
            start_idx = 0
            
        depth = 0
        in_string = False
        escape = False
        end_idx = -1
        
        for i, char in enumerate(buffer):
            if char == '"' and not escape:
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
            
            if char == '\\' and not escape:
                escape = True
            else:
                escape = False
                
        if end_idx != -1:
            json_str = buffer[:end_idx + 1]
            buffer = buffer[end_idx + 1:]
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict):
                    packets.append(parsed)
            except json.JSONDecodeError:
                # Corrupted block or partial slice, discard leading '{' to proceed
                buffer = buffer[1:] if len(buffer) > 0 else ""
        else:
            # Incomplete JSON block still accumulating in serial buffer
            if len(buffer) > 8192:
                # Prevent buffer overflow from malformed open brace
                buffer = buffer[1:]
            break
            
    return packets, buffer


class HardwareSerialAdapter(BaseTelemetryAdapter):
    """
    Hardware adapter connecting to ESP32 over serial UART.
    Supports auto-discovery, multi-line JSON stream extraction,
    and automatic reconnection.
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
        """Dispatches an ASCII command to the ESP32 (e.g. 'DRAIN:24.0\\n')."""
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

                    # Extract complete JSON dictionaries (handling multi-line blocks & banners)
                    packets, buffer = extract_json_from_buffer(buffer)
                    for parsed in packets:
                        with self._lock:
                            self._latest_raw = parsed
                            self._last_read_time = time.time()
                            self._packet_count += 1
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
