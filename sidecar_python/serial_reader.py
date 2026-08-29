import threading
import time
import json
import random
import serial
import serial.tools.list_ports

class SerialTelemetryReader:
    """
    Reads JSON telemetry output from ESP32 over Serial, or generates
    simulated data if in simulation mode.
    """
    def __init__(self, port=None, baudrate=115200, is_simulated=False):
        self.port = port
        self.baudrate = baudrate
        self.is_simulated = is_simulated
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Default telemetry structure
        self.telemetry = {
            "roll": 0.0,
            "pitch": 0.0,
            "distance": 30.0,      # Empty tank distance (cm)
            "ballast_pct": 100.0,  # Ballast tank percentage
            "cargo_kg": 0.0,       # Cargo weight (kg)
            "status": "IDLE",      # IoT operation status
            "risk": "SAFE"
        }
        
        # Simulator internal state
        self._sim_target_cargo = 0.0
        self._sim_gate_open = False
        self._sim_tank_empty_dist = 30.0
        self._sim_tank_full_dist = 10.0
        self._sim_current_dist = 10.0  # Start fully ballasted (water level high)
        self._sim_current_cargo = 0.0
        self._sim_override_roll = None
        self._sim_override_pitch = None
        self.ser = None  # Reference to the open serial port

    def set_simulated_tilt(self, roll, pitch):
        """Sets simulated tilt overrides (use None to disable overrides)."""
        with self.lock:
            self._sim_override_roll = float(roll) if roll is not None else None
            self._sim_override_pitch = float(pitch) if pitch is not None else None

    @staticmethod
    def get_available_ports():
        """Scans the system for active serial COM ports."""
        try:
            ports = serial.tools.list_ports.comports()
            return [p.device for p in ports]
        except Exception:
            return []

    def start(self):
        """Starts the background reading/simulation thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the background thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def get_telemetry(self):
        """Returns a thread-safe copy of the latest telemetry."""
        with self.lock:
            return self.telemetry.copy()

    def set_simulated_cargo(self, weight_kg):
        """Sets target cargo weight for the simulator."""
        with self.lock:
            self._sim_target_cargo = float(weight_kg)

    def reset_simulated_cargo(self):
        """Resets simulated cargo weight to zero."""
        with self.lock:
            self._sim_target_cargo = 0.0
            self._sim_current_cargo = 0.0
            self._sim_gate_open = False

    def send_drain_command(self, weight_kg):
        """Sends the command to the ESP32 (or triggers simulated draining)."""
        with self.lock:
            self._sim_target_cargo = float(weight_kg)
            self._sim_gate_open = True
            
        if not self.is_simulated:
            with self.lock:
                ser_port = self.ser
            if ser_port and ser_port.is_open:
                try:
                    cmd = f"DRAIN:{weight_kg:.2f}\n"
                    ser_port.write(cmd.encode('utf-8'))
                    ser_port.flush()
                except Exception as e:
                    with self.lock:
                        self.telemetry["risk"] = f"ERROR SENDING CMD: {str(e)}"

    def _run_loop(self):
        if self.is_simulated:
            self._run_simulation()
        else:
            self._run_serial()

    def _run_serial(self):
        ser = None
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=1.0)
            with self.lock:
                self.ser = ser
            buffer = ""
            while self.running:
                if ser.in_waiting > 0:
                    # Read available data and append to buffer
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Split lines by newline and parse complete JSON blocks
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        # Match JSON bracket boundaries
                        if line.startswith("{") and line.endswith("}"):
                            try:
                                parsed = json.loads(line)
                                with self.lock:
                                    for key in self.telemetry:
                                        if key in parsed:
                                            self.telemetry[key] = parsed[key]
                            except json.JSONDecodeError:
                                pass # Partial or malformed JSON line
                time.sleep(0.05)
        except Exception as e:
            with self.lock:
                self.telemetry["risk"] = f"ERROR: {str(e)}"
        finally:
            with self.lock:
                self.ser = None
            if ser and ser.is_open:
                ser.close()

    def _run_simulation(self):
        while self.running:
            with self.lock:
                target_cargo = self._sim_target_cargo
                gate_open = self._sim_gate_open
                current_dist = self._sim_current_dist
                current_cargo = self._sim_current_cargo

            # Smoothly transition current simulated cargo weight to target
            if abs(current_cargo - target_cargo) > 0.05:
                if target_cargo > current_cargo:
                    current_cargo += min(1.0, target_cargo - current_cargo)
                else:
                    current_cargo -= min(1.0, current_cargo - target_cargo)

            target_dist = 10.0 + (current_cargo * 20.0 / 30.0)  # mock scaling
            target_dist = min(target_dist, self._sim_tank_empty_dist)

            if gate_open:
                if target_cargo > 0.1:
                    duration_sec = target_cargo / 0.85
                    total_dist_change = target_dist - 10.0
                    dist_step = (total_dist_change / duration_sec) * 0.1
                else:
                    dist_step = 0.04
                
                if current_dist < target_dist:
                    current_dist += dist_step
                    current_dist = min(current_dist, target_dist)
                else:
                    gate_open = False  # Target reached, close gate
            else:
                # If cargo is cleared, simulate pumps refilling the ballast tank (distance decreases)
                if current_cargo < 0.5 and current_dist > 10.0:
                    current_dist -= 0.08  # Pumping water in
                    current_dist = max(10.0, current_dist)

            # Calculate ballast percentage based on current distance
            ballast_pct = (self._sim_tank_empty_dist - current_dist) / \
                          (self._sim_tank_empty_dist - self._sim_tank_full_dist) * 100.0
            ballast_pct = max(0.0, min(100.0, ballast_pct))

            # Simulate wave action / jitter on roll and pitch
            wave_roll = random.uniform(-0.4, 0.4)
            wave_pitch = random.uniform(-0.2, 0.2)

            # If overrides are active, use them; otherwise, compute based on cargo + waves
            with self.lock:
                override_roll = self._sim_override_roll
                override_pitch = self._sim_override_pitch

            if override_roll is not None:
                sim_roll = override_roll
            else:
                sim_roll = (current_cargo * 0.04) + wave_roll

            if override_pitch is not None:
                sim_pitch = override_pitch
            else:
                sim_pitch = (current_cargo * 0.02) + wave_pitch

            # Standard risk assessment based on roll/pitch
            score = abs(sim_roll) + abs(sim_pitch)
            if score < 5.0:
                risk = "SAFE"
            elif score < 12.0:
                risk = "WARNING"
            else:
                risk = "CRITICAL"

            # Calculate status
            if current_cargo < 0.1:
                status = "IDLE"
            elif current_cargo >= 30.0:  # 30.0 kg is the physical scale limit (300 t virtual equivalent)
                status = "NO SPACE"
            elif gate_open:
                status = "DRAINING"
            elif current_dist >= target_dist - 0.2:
                status = "READY"
            else:
                status = "STANDBY"

            with self.lock:
                self._sim_current_cargo = current_cargo
                self._sim_current_dist = current_dist
                self._sim_gate_open = gate_open
                self.telemetry = {
                    "roll": sim_roll,
                    "pitch": sim_pitch,
                    "distance": current_dist,
                    "ballast_pct": ballast_pct,
                    "cargo_kg": current_cargo,
                    "status": status,
                    "risk": risk
                }

            time.sleep(0.1)  # 10 Hz refresh
