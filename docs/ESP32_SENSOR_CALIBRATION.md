# MARETIDE — ESP32 SENSOR CALIBRATION GUIDE

This document defines the calibration constants, engineering conversions, and physical calibration procedures for the MareTide ESP32 hardware testbench.

---

## 1. MPU-6050 Accelerometer & Inclinometer Calibration

### Sensor Characteristics
* **Interface:** I2C (SDA = GPIO 21, SCL = GPIO 22)
* **Default Range:** $\pm 2g$ ($16384 \text{ LSB}/g$)
* **Zero Offset:** Measured at rest on a level reference plane

### Conversion Equations
$$\text{accX} = \frac{ax - \text{offset}_X}{16384.0}, \quad \text{accY} = \frac{ay - \text{offset}_Y}{16384.0}, \quad \text{accZ} = \frac{az - \text{offset}_Z}{16384.0}$$

$$\text{roll} = \operatorname{atan2}(\text{accY}, \text{accZ}) \times \frac{180.0}{\pi} \quad (\text{deg})$$
$$\text{pitch} = \operatorname{atan2}(-\text{accX}, \sqrt{\text{accY}^2 + \text{accZ}^2}) \times \frac{180.0}{\pi} \quad (\text{deg})$$

### Calibration Procedure
1. Place the ESP32 breadboard on a verified horizontal level surface.
2. Record average raw accelerometer values over 100 samples.
3. Compute offsets such that $\text{roll} = 0.00^\circ$ and $\text{pitch} = 0.00^\circ$.

---

## 2. HC-SR04 Ultrasonic Distance Sensor Calibration

### Sensor Characteristics
* **Interface:** Trig = GPIO 5, Echo = GPIO 18
* **Speed of Sound:** $0.034\text{ cm}/\mu\text{s}$ at $20^\circ\text{C}$
* **Exponential Moving Average Filter:** $\alpha = 0.25$

### Physical Tank Limits
* `TANK_FULL_DIST = 10.0` cm (Water level highest / sensor closest to water)
* `TANK_EMPTY_DIST = 30.0` cm (Water level lowest / empty tank)
* `TANK_AREA_CM2 = 150.0` $\text{cm}^2$

### Ballast Percentage Mapping
$$\text{depth} = \operatorname{clamp}(30.0 - \text{distance}, 0.0, 20.0) \quad (\text{cm})$$
$$\text{ballast\_pct} = \frac{30.0 - \text{distance}}{20.0} \times 100.0 \quad (\%)$$

---

## 3. HX711 Load Cell Calibration

### Sensor Characteristics
* **Interface:** DOUT = GPIO 32, SCK = GPIO 33
* **ADC Resolution:** 24-bit Sigma-Delta ADC

### Calibration Procedure
1. Call `scale.tare()` with no weight on the load-cell platform.
2. Place a known reference calibration mass $M_{\text{cal}}$ (e.g. 1.000 kg).
3. Read raw units: `raw_val = scale.get_value(10)`.
4. Calculate calibration factor:
   $$\text{LOADCELL\_CAL\_FACTOR} = \frac{\text{raw\_val}}{M_{\text{cal}}}$$
5. Set factor: `scale.set_scale(LOADCELL_CAL_FACTOR);`.

> [!NOTE]
> Even after calibration, the HX711 load cell is isolated strictly for experimental bench monitoring and is NEVER used for container cargo weight or stability calculations.

---

## 4. Servo Actuator Calibration

* `GATE_CLOSED_ANGLE = 0` ($0^\circ$ PWM)
* `GATE_OPEN_ANGLE = 80` ($80^\circ$ PWM)
* `DISCHARGE_COEFFICIENT = 0.62`
* `GATE_OPEN_AREA_CM2 = 2.0` $\text{cm}^2$
