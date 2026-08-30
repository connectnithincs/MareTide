import React, { useState, useEffect } from "react";
import { 
  Cpu, 
  Radio, 
  Activity, 
  RefreshCw, 
  CheckCircle2, 
  AlertTriangle, 
  Sliders, 
  Zap, 
  Droplets, 
  Compass, 
  ShieldCheck, 
  WifiOff, 
  Wifi,
  ArrowDownCircle,
  Clock,
  Layers,
  Scale,
  ArrowLeft,
  ArrowRight,
  ArrowDown,
  ArrowUp,
  Waves,
  Unplug
} from "lucide-react";
import { telemetryAPI } from "../utils/api";
import { useSocket } from "../context/SocketContext";

export interface VirtualESP32ScenarioControlProps {
  className?: string;
  compact?: boolean;
}

export type ESP32Scenario = 
  | "STABLE"
  | "PORT_LIST"
  | "STARBOARD_LIST"
  | "FORWARD_PITCH"
  | "AFT_PITCH"
  | "TANK_FILLING"
  | "TANK_DRAINING"
  | "SENSOR_FAULT"
  | "DISCONNECTED";

const SCENARIOS: Array<{
  id: ESP32Scenario;
  label: string;
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}> = [
  { id: "STABLE", label: "STABLE", desc: "Level vessel (Roll 0.0°, Pitch 0.0°, 100% Ballast)", icon: Scale, color: "border-brand-safe/40 text-brand-safe bg-brand-safeBg" },
  { id: "PORT_LIST", label: "PORT LIST", desc: "Tilt vessel to port (-7.50° roll)", icon: ArrowLeft, color: "border-brand-info/40 text-brand-info bg-brand-infoBg" },
  { id: "STARBOARD_LIST", label: "STARBOARD LIST", desc: "Tilt vessel to starboard (+8.20° roll)", icon: ArrowRight, color: "border-brand-cyan/40 text-brand-cyan bg-brand-cyanBg" },
  { id: "FORWARD_PITCH", label: "FORWARD PITCH", desc: "Pitch vessel forward/bow-down (-6.50° pitch)", icon: ArrowDown, color: "border-brand-purple/40 text-brand-purple bg-brand-purpleBg" },
  { id: "AFT_PITCH", label: "AFT PITCH", desc: "Pitch vessel aft/stern-down (+5.80° pitch)", icon: ArrowUp, color: "border-brand-purple/40 text-brand-purple bg-brand-purpleBg" },
  { id: "TANK_FILLING", label: "TANK FILL", desc: "Ballast tank level rising (0% → 100%)", icon: Waves, color: "border-brand-cyan/40 text-brand-cyan bg-brand-cyanBg" },
  { id: "TANK_DRAINING", label: "TANK DRAIN", desc: "Servo gate opens 80°, Torricelli discharge", icon: Droplets, color: "border-brand-warning/40 text-brand-warning bg-brand-warningBg" },
  { id: "SENSOR_FAULT", label: "SENSOR FAULT", desc: "Ultrasonic sensor timeout/degradation error", icon: AlertTriangle, color: "border-brand-danger/40 text-brand-danger bg-brand-dangerBg" },
  { id: "DISCONNECTED", label: "DISCONNECT", desc: "Simulate physical UART link disconnection", icon: Unplug, color: "border-brand-borderSubtle text-brand-muted surface-base" }
];


export const VirtualESP32ScenarioControl: React.FC<VirtualESP32ScenarioControlProps> = ({
  className = "",
  compact = false
}) => {
  const { vesselState } = useSocket();
  const [activeScenario, setActiveScenario] = useState<ESP32Scenario>("STABLE");
  const [activeSource, setActiveSource] = useState<string>("SIMULATED_ESP32");
  const [virtualStatus, setVirtualStatus] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Poll virtual firmware diagnostic status every 2 seconds
  const fetchStatus = async () => {
    try {
      const status = await telemetryAPI.getVirtualStatus();
      setVirtualStatus(status);
      if (status.active_scenario) {
        setActiveScenario(status.active_scenario as ESP32Scenario);
      }
      const sources = await telemetryAPI.getSources();
      if (sources.active_source) {
        setActiveSource(sources.active_source);
      }
    } catch (e) {
      // Backend may be running without virtual status or restarting
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleScenarioChange = async (scenario: ESP32Scenario) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // Auto-switch telemetry source to virtual_esp32 if needed
      if (activeSource !== "SIMULATED_ESP32") {
        await telemetryAPI.selectSource("virtual_esp32");
        setActiveSource("SIMULATED_ESP32");
      }
      const res = await telemetryAPI.setVirtualScenario(scenario);
      setActiveScenario(scenario);
      setActionSuccess(`Scenario activated: ${scenario}`);
      setTimeout(() => setActionSuccess(null), 3000);
      await fetchStatus();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to switch virtual ESP32 scenario");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectVirtualMode = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await telemetryAPI.selectSource("virtual_esp32");
      setActiveSource("SIMULATED_ESP32");
      setActionSuccess("Switched authoritative telemetry engine to VIRTUAL ESP32");
      setTimeout(() => setActionSuccess(null), 3000);
      await fetchStatus();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to activate Virtual ESP32 mode");
    } finally {
      setLoading(false);
    }
  };

  const isVirtualActive = activeSource === "SIMULATED_ESP32";
  const rollVal = vesselState?.roll ?? virtualStatus?.firmware_state?.roll ?? 0.0;
  const pitchVal = vesselState?.pitch ?? virtualStatus?.firmware_state?.pitch ?? 0.0;
  const servoAngle = virtualStatus?.firmware_state?.servo_gate_deg ?? (activeScenario === "TANK_DRAINING" ? 80 : 0);
  const pumpActive = virtualStatus?.firmware_state?.pump_active ?? (activeScenario === "TANK_FILLING" || activeScenario === "TANK_DRAINING");
  const ballastPct = virtualStatus?.firmware_state?.ballast_pct ?? 100.0;

  return (
    <div className={`surface-elevated border border-brand-borderSubtle rounded-2xl p-4 shadow-sm space-y-4 font-mono text-xs ${className}`}>
      {/* Header: Title, Demonstration Badge, Source Selection */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-brand-borderSubtle pb-3 gap-2">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-brand-purpleBg border border-brand-purple/30 rounded-xl text-brand-purple">
            <Cpu className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-black text-brand-text uppercase tracking-wider">
                VIRTUAL ESP32 — DEMONSTRATION MODE
              </h3>
              <span className="px-2 py-0.5 rounded text-[8.5px] font-mono font-bold uppercase bg-brand-purpleBg text-brand-purple border border-brand-purple/30">
                [SIMULATED ESP32]
              </span>
            </div>
            <p className="text-[10.5px] text-brand-muted">
              Firmware emulator for <span className="font-mono text-brand-cyan">esp32_sensor_sketch.ino</span> (MPU6050 + HC-SR04 + SG90 Servo)
            </p>
          </div>
        </div>

        {/* Active Source Toggle / Indicator */}
        <div className="flex items-center gap-2">
          {isVirtualActive ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-brand-safeBg border border-brand-safe/40 text-brand-safe text-[11px] font-mono font-bold">
              <span className="w-2 h-2 rounded-full bg-brand-safe animate-pulse" />
              <span>VIRTUAL ESP32 CONNECTED</span>
            </div>
          ) : (
            <button
              onClick={handleSelectVirtualMode}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-brand-purple hover:bg-brand-purple/90 text-white text-[11px] font-mono font-bold shadow-md transition-all active:scale-95 cursor-pointer"
            >
              <Radio className="w-3.5 h-3.5" />
              <span>ACTIVATE VIRTUAL ESP32</span>
            </button>
          )}
        </div>
      </div>

      {/* Real-Time Live Reaction Telemetry Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2 text-xs">
        {/* Roll */}
        <div className="surface-base p-2.5 rounded-xl border border-brand-borderSubtle space-y-0.5">
          <div className="text-[9px] text-brand-muted uppercase font-bold flex items-center justify-between">
            <span>Roll [ESP32]</span>
            <span className="text-brand-purple font-mono text-[8px]">[SIMULATED]</span>
          </div>
          <div className={`font-mono font-black text-sm ${Math.abs(rollVal) > 5 ? "text-brand-warning" : "text-brand-text"}`}>
            {rollVal > 0 ? `+${rollVal.toFixed(2)}°` : `${rollVal.toFixed(2)}°`}
          </div>
        </div>

        {/* Pitch */}
        <div className="surface-base p-2.5 rounded-xl border border-brand-borderSubtle space-y-0.5">
          <div className="text-[9px] text-brand-muted uppercase font-bold flex items-center justify-between">
            <span>Pitch [ESP32]</span>
            <span className="text-brand-purple font-mono text-[8px]">[SIMULATED]</span>
          </div>
          <div className={`font-mono font-black text-sm ${Math.abs(pitchVal) > 4 ? "text-brand-warning" : "text-brand-text"}`}>
            {pitchVal > 0 ? `+${pitchVal.toFixed(2)}°` : `${pitchVal.toFixed(2)}°`}
          </div>
        </div>

        {/* Ballast Level */}
        <div className="surface-base p-2.5 rounded-xl border border-brand-borderSubtle space-y-0.5">
          <div className="text-[9px] text-brand-muted uppercase font-bold flex items-center justify-between">
            <span>Ballast Level</span>
            <span className="text-brand-cyan font-mono text-[8px]">HC-SR04</span>
          </div>
          <div className="font-mono font-black text-sm text-brand-cyan">
            {ballastPct.toFixed(0)}%
          </div>
        </div>

        {/* Servo Gate */}
        <div className="surface-base p-2.5 rounded-xl border border-brand-borderSubtle space-y-0.5">
          <div className="text-[9px] text-brand-muted uppercase font-bold flex items-center justify-between">
            <span>Gate Servo</span>
            <span className="text-brand-warning font-mono text-[8px]">SG90</span>
          </div>
          <div className="font-mono font-black text-sm text-brand-warning flex items-center gap-1">
            <span>{servoAngle}°</span>
            <span className="text-[10px] text-brand-muted font-normal">({servoAngle > 0 ? "OPEN" : "CLOSED"})</span>
          </div>
        </div>

        {/* Pump / Flow Rate */}
        <div className="surface-base p-2.5 rounded-xl border border-brand-borderSubtle space-y-0.5">
          <div className="text-[9px] text-brand-muted uppercase font-bold flex items-center justify-between">
            <span>Torricelli Pump</span>
            <span className="text-brand-safe font-mono text-[8px]">GPIO 23</span>
          </div>
          <div className="font-mono font-black text-sm text-brand-safe flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${pumpActive ? "bg-brand-safe animate-ping" : "bg-brand-muted/40"}`} />
            <span>{pumpActive ? "DRAINING (2.4 L/s)" : "IDLE"}</span>
          </div>
        </div>

        {/* Load-Cell Quarantine Diagnostic */}
        <div className="surface-base p-2.5 rounded-xl border border-brand-borderSubtle space-y-0.5">
          <div className="text-[9px] text-brand-muted uppercase font-bold flex items-center justify-between">
            <span>Diagnostic Scale</span>
            <span className="text-brand-muted font-mono text-[8px]">[ISOLATED]</span>
          </div>
          <div className="font-mono font-bold text-xs text-brand-text truncate" title="Load cell does not influence cargo weight or stability calculations">
            0.00 kg <span className="text-[8px] text-brand-warning font-normal">[DIAG ONLY]</span>
          </div>
        </div>
      </div>

      {/* Scenario Control Grid */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-brand-text uppercase tracking-wider flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-brand-purple" />
            Select Telemetry Reaction Scenario
          </span>
          <span className="text-[10px] font-mono text-brand-purple">
            Active: <strong className="text-brand-text uppercase">{activeScenario.replace("_", " ")}</strong>
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {SCENARIOS.map((sc) => {
            const isCurrent = activeScenario === sc.id;
            const Icon = sc.icon;
            return (
              <button
                key={sc.id}
                onClick={() => handleScenarioChange(sc.id)}
                disabled={loading}
                className={`p-2.5 rounded-xl border text-left transition-all relative overflow-hidden group ${
                  isCurrent
                    ? `${sc.color} ring-1 ring-brand-purple/40 shadow-md scale-[1.02]`
                    : "surface-base border-brand-borderSubtle hover:border-brand-border text-brand-text hover:bg-brand-hover"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="p-1 rounded-md surface-base border border-brand-borderSubtle">
                    <Icon className="w-3.5 h-3.5 text-brand-cyan" />
                  </div>
                  {isCurrent && (
                    <span className="w-2 h-2 rounded-full bg-brand-cyan animate-pulse" />
                  )}
                </div>
                <div className="font-mono font-black text-[10.5px] uppercase tracking-wider truncate">
                  {sc.label}
                </div>
                <p className="text-[9px] text-brand-muted line-clamp-2 mt-0.5 leading-tight">
                  {sc.desc}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Action Notification */}
      {actionSuccess && (
        <div className="p-2.5 bg-brand-safeBg border border-brand-safe/40 rounded-xl flex items-center gap-2 text-xs text-brand-safe animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-brand-safe shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-2.5 bg-brand-dangerBg border border-brand-danger/40 rounded-xl flex items-center gap-2 text-xs text-brand-danger">
          <AlertTriangle className="w-4 h-4 text-brand-danger shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
    </div>
  );

};
