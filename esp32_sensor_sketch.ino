// ====================================================================
// NAVI-AI — ESP32 Sensor Code (Refactored, Non-Blocking, & Filtered)
// MPU-6050 (tilt) + HC-SR04 (ballast level) + HX711 (cargo weight) + Servo (ballast gate)
// ====================================================================

#include <Wire.h>
#include <MPU6050.h>
#include <HX711.h>
#include <ESP32Servo.h>

// --------------------------------
// PIN SETUP
// --------------------------------
#define PUMP_LED        23    // LED = ballast pump indicator
#define TRIG_PIN        5     // HC-SR04 trigger
#define ECHO_PIN        18    // HC-SR04 echo
#define WARN_LED        19    // Warning LED

#define LOADCELL_DOUT   32    // HX711 data pin
#define LOADCELL_SCK    33    // HX711 clock pin

#define GATE_SERVO_PIN  25    // Servo controlling the ballast drain gate

// --------------------------------
// THRESHOLDS
// --------------------------------
#define LIST_LIMIT      5.0   // degrees — roll alert
#define TRIM_LIMIT      5.0   // degrees — pitch alert
#define TANK_FULL_DIST  10.0  // cm — sensor distance when tank is full
#define TANK_EMPTY_DIST 30.0  // cm — sensor distance when tank is empty

// --------------------------------
// CALIBRATION
// --------------------------------
#define LOADCELL_CAL_FACTOR    1.0  // Tune using HX711 calibration sketch
#define TANK_AREA_CM2           150.0   // cross-sectional area of ballast tank
#define BALLAST_RATIO_L_PER_KG  1.0     // 1L of ballast drained per 1kg of cargo added

#define GATE_CLOSED_ANGLE       0
#define GATE_OPEN_ANGLE         80

#define DISCHARGE_COEFFICIENT   0.62    // orifice flow coefficient
#define GATE_OPEN_AREA_CM2      2.0     // gate open area

#define DRAIN_TIMEOUT_MS        30000   // safety cutoff

// --------------------------------
// OBJECTS & GLOBAL VARIABLES
// --------------------------------
MPU6050 mpu;
HX711   scale;
Servo   gateServo;

// Tracking state for stable weight trigger
float lastStableWeight = 0;

// EMA filter variables for distance sensor
float filteredDistance = -1.0;
const float EMA_ALPHA = 0.25;  // Smoothing factor (lower = smoother but slower)

// Non-blocking draining state machine variables
bool isDraining = false;
float drainTargetDist = 0.0;
unsigned long drainStartTime = 0;
float drainStartDist = 0.0;
float drainStartVol = 0.0;
float drainTargetVolClamped = 0.0;
float drainPredictedQ = 0.0;
float drainPredictedSec = 0.0;

// Telemetry interval tracking
unsigned long lastTelemetryTime = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 500; // Send telemetry every 500ms

// --------------------------------
// SETUP
// --------------------------------
void setup() {
  Serial.begin(115200);

  pinMode(PUMP_LED, OUTPUT);
  pinMode(WARN_LED, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Wire.begin(21, 22); // SDA=21, SCL=22
  mpu.initialize();
  Serial.println(mpu.testConnection() ? "MPU6050: OK" : "MPU6050: FAILED");

  scale.begin(LOADCELL_DOUT, LOADCELL_SCK);
  scale.set_scale(LOADCELL_CAL_FACTOR);
  scale.tare();
  Serial.println("HX711: Ready");

  gateServo.attach(GATE_SERVO_PIN);
  gateServo.write(GATE_CLOSED_ANGLE);
  Serial.println("Gate Servo: Closed");

  Serial.println("NAVI-AI ESP32 Ready");
  Serial.println("-------------------");
}

// --------------------------------
// READ HC-SR04 DISTANCE (cm)
// --------------------------------
float readDistanceRaw() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
  if (duration == 0) return -1; // sensor error

  return (duration * 0.034) / 2.0;
}

// --------------------------------
// SMOOTHED DISTANCE USING EMA FILTER
// --------------------------------
float readDistanceFiltered() {
  float raw = readDistanceRaw();
  if (raw < 0) {
    // If sensor errors out, return the last known good filtered reading
    return (filteredDistance >= 0) ? filteredDistance : TANK_EMPTY_DIST;
  }
  
  if (filteredDistance < 0) {
    // First reading initialization
    filteredDistance = raw;
  } else {
    // Apply EMA filter
    filteredDistance = (EMA_ALPHA * raw) + ((1.0 - EMA_ALPHA) * filteredDistance);
  }
  return filteredDistance;
}

// --------------------------------
// CONVERT DISTANCE <-> WATER DEPTH / VOLUME
// --------------------------------
float distanceToDepth(float dist) {
  float depth = TANK_EMPTY_DIST - dist;
  return constrain(depth, 0.0, TANK_EMPTY_DIST - TANK_FULL_DIST);
}

float depthToVolumeLiters(float depthCm) {
  return (depthCm * TANK_AREA_CM2) / 1000.0;   // cm^3 -> liters
}

float distanceToBallastPct(float dist) {
  if (dist < 0) return -1;
  float pct = (TANK_EMPTY_DIST - dist) / (TANK_EMPTY_DIST - TANK_FULL_DIST) * 100.0;
  return constrain(pct, 0.0, 100.0);
}

// --------------------------------
// READ CARGO WEIGHT (kg) FROM LOAD CELL
// --------------------------------
float readCargoWeight() {
  if (!scale.is_ready()) return 0;
  return scale.get_units(1);
}

// --------------------------------
// GET RISK LEVEL (tilt-based)
// --------------------------------
String getRisk(float roll, float pitch) {
  float score = abs(roll) + abs(pitch);
  if (score < 5.0)  return "SAFE";
  if (score < 12.0) return "WARNING";
  return "CRITICAL";
}

// --------------------------------
// PREDICT FLOW RATE (L/s)
// --------------------------------
float predictFlowRateLps(float depthCm) {
  float h_m = depthCm / 100.0;
  if (h_m <= 0) return 0;
  float A_m2 = GATE_OPEN_AREA_CM2 / 10000.0;
  float Q_m3s = DISCHARGE_COEFFICIENT * A_m2 * sqrt(2.0 * 9.81 * h_m);
  return Q_m3s * 1000.0;   // m^3/s -> L/s
}

// --------------------------------
// NON-BLOCKING DRAINING STATE MACHINE INITS
// --------------------------------
void startDraining(float cargoWeightKg) {
  float startDist  = readDistanceFiltered();
  float startDepth = distanceToDepth(startDist);
  float startVolL  = depthToVolumeLiters(startDepth);

  float targetVolL         = cargoWeightKg * BALLAST_RATIO_L_PER_KG;
  float targetVolL_clamped = min(targetVolL, startVolL);
  
  // Calculate target depth & ensure it stays within physical limits (>= 0)
  float targetDepth        = startDepth - (targetVolL_clamped * 1000.0) / TANK_AREA_CM2;
  if (targetDepth < 0) targetDepth = 0;

  float targetDist         = TANK_EMPTY_DIST - targetDepth;

  float predictedQ       = predictFlowRateLps(startDepth);
  float predictedSeconds = (predictedQ > 0) ? (targetVolL_clamped / predictedQ) : 0;

  // Initialize state variables for non-blocking loop checks
  isDraining = true;
  drainTargetDist = targetDist;
  drainStartTime = millis();
  drainStartDist = startDist;
  drainStartVol = startVolL;
  drainTargetVolClamped = targetVolL_clamped;
  drainPredictedQ = predictedQ;
  drainPredictedSec = predictedSeconds;

  Serial.println("=== BALLAST DRAIN STARTED ===");
  Serial.print("Cargo weight (kg): ");    Serial.println(cargoWeightKg, 2);
  Serial.print("Target volume (L): ");    Serial.println(targetVolL_clamped, 2);
  Serial.print("Target distance (cm): "); Serial.println(targetDist, 2);
  Serial.print("Predicted flow (L/s): "); Serial.println(predictedQ, 3);
  Serial.print("Predicted time (s): ");   Serial.println(predictedSeconds, 1);

  gateServo.write(GATE_OPEN_ANGLE);
  digitalWrite(PUMP_LED, HIGH);
}

// --------------------------------
// STATE MACHINE STEP FOR DRAINING
// --------------------------------
void updateDraining() {
  if (!isDraining) return;

  float currentDist = readDistanceFiltered();
  bool complete = false;
  bool timedOut = false;

  // Drain complete if we hit/exceed target distance or timed out
  if (currentDist >= drainTargetDist) {
    complete = true;
  } else if (millis() - drainStartTime > DRAIN_TIMEOUT_MS) {
    timedOut = true;
    complete = true;
  }

  if (complete) {
    gateServo.write(GATE_CLOSED_ANGLE);
    digitalWrite(PUMP_LED, LOW);
    isDraining = false;

    float elapsedSec    = (millis() - drainStartTime) / 1000.0;
    float endDepth      = distanceToDepth(currentDist);
    float endVolL       = depthToVolumeLiters(endDepth);
    float actualVolL    = drainStartVol - endVolL;
    float actualFlowLps = (elapsedSec > 0) ? (actualVolL / elapsedSec) : 0;

    Serial.println("=== BALLAST DRAIN COMPLETE ===");
    if (timedOut) {
      Serial.println("STATUS: WARNING - Drain timeout reached. Gate closed for safety.");
    } else {
      Serial.println("STATUS: SUCCESS - Target level achieved.");
    }
    Serial.print("Actual volume drained (L): "); Serial.println(actualVolL, 2);
    Serial.print("Time taken (s): ");            Serial.println(elapsedSec, 1);
    Serial.print("Actual flow rate (L/s): ");    Serial.println(actualFlowLps, 3);
    Serial.println("-------------------------------");
  }
}

// --------------------------------
// --------------------------------
// MAIN LOOP
// --------------------------------
void loop() {
  // --- Non-blocking Draining Controller ---
  updateDraining();

  // --- Cargo weight monitoring ---
  float weight = readCargoWeight();

  // Reset lastStableWeight when cargo is cleared, but do NOT automatically start draining
  if (weight < 1.0) {
    lastStableWeight = 0;
  } else {
    lastStableWeight = weight;
  }

  // --- Tilt Readings ---
  int16_t ax, ay, az, gx, gy, gz;
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

  float accX = ax / 16384.0;
  float accY = ay / 16384.0;
  float accZ = az / 16384.0;

  float roll  = atan2(accY, accZ) * 180.0 / PI;
  float pitch = atan2(-accX, sqrt(accY * accY + accZ * accZ)) * 180.0 / PI;

  // --- Ballast Level & Safety ---
  float distance   = readDistanceFiltered();
  float ballastPct = distanceToBallastPct(distance);

  // Live alert output if ballast level is critically low
  if (ballastPct >= 0 && ballastPct < 20) {
    Serial.println("WARNING: LOW BALLAST LEVEL!");
  }

  // Cargo weight capacity check
  float maxTankCapacityKg = (TANK_EMPTY_DIST - TANK_FULL_DIST) * TANK_AREA_CM2 / 1000.0 / BALLAST_RATIO_L_PER_KG;
  bool weightExceeded = (weight > maxTankCapacityKg);
  if (weightExceeded) {
    Serial.println("WARNING: Maximum Capacity attained!");
  }

  // Tilt & Weight Risk Alert & Output
  String risk = getRisk(roll, pitch);
  digitalWrite(WARN_LED, (risk == "CRITICAL" || weightExceeded) ? HIGH : LOW);

  if (roll > LIST_LIMIT) {
    Serial.println("Tilt Right -> Pump PORT side");
  } else if (roll < -LIST_LIMIT) {
    Serial.println("Tilt Left -> Pump STARBOARD side");
  }

  // --- Check for incoming serial commands ---
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("DRAIN:")) {
      float targetWeight = cmd.substring(6).toFloat();
      if (targetWeight > 0.0 && !isDraining) {
        startDraining(targetWeight);
      }
    }
  }

  // --- Throttled Serial Telemetry Output (JSON) ---
  unsigned long now = millis();
  if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = now;

    String status = "IDLE";
    if (weight >= 0.1) {
      if (isDraining) {
        status = "DRAINING";
      } else {
        status = "READY";
      }
    }

    Serial.println("{");
    Serial.print("  \"roll\": ");         Serial.print(roll, 2);       Serial.println(",");
    Serial.print("  \"pitch\": ");        Serial.print(pitch, 2);      Serial.println(",");
    Serial.print("  \"distance\": ");     Serial.print(distance, 2);   Serial.println(",");
    Serial.print("  \"ballast_pct\": ");  Serial.print(ballastPct, 2); Serial.println(",");
    Serial.print("  \"cargo_kg\": ");     Serial.print(weight, 2);     Serial.println(",");
    Serial.print("  \"status\": \"");     Serial.print(status);        Serial.println("\",");
    Serial.print("  \"risk\": \"");       Serial.print(risk);          Serial.println("\"");
    Serial.println("}");
    Serial.println("---");
  }

  delay(20); // Small delay to prevent CPU spinning (runs at 50Hz)
}
