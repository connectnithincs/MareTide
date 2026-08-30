import React, { useState } from "react";
import { 
  Box, 
  Droplets, 
  ShieldCheck, 
  AlertTriangle, 
  Activity, 
  Layers, 
  Compass, 
  RefreshCw, 
  Radio, 
  CheckCircle2, 
  AlertOctagon, 
  Clock, 
  Gauge, 
  Zap, 
  Sliders, 
  AlertCircle,
  Wifi,
  WifiOff
} from "lucide-react";
import { useSocket, type VesselState } from "../context/SocketContext";
import { useContainerOperation } from "../context/ContainerOperationContext";

interface CargoAwareDigitalTwinProps {
  customVesselState?: VesselState | null;
  compact?: boolean;
}

export const CargoAwareDigitalTwin: React.FC<CargoAwareDigitalTwinProps> = ({ 
  customVesselState,
  compact = false 
}) => {
  const { vesselState: socketState, connected: socketConnected } = useSocket();
  const { stabilityResult, extractedData, loadedResult, ballastCompensation, operationStatus } = useContainerOperation();
  
  const vessel = customVesselState || socketState;
  const [selectedStage, setSelectedStage] = useState<"BEFORE" | "LOADED" | "BALLASTED" | "CURRENT">("CURRENT");

  if (!vessel) {
    return (
      <div className="bg-brand-surface border border-brand-border p-6 rounded-2xl flex items-center justify-center text-gray-400 space-x-3">
        <RefreshCw className="w-5 h-5 animate-spin text-blue-400" />
        <span className="text-xs font-bold uppercase tracking-wider">Connecting to Vessel Digital Twin Telemetry...</span>
      </div>
    );
  }

  // Extract vessel parameters
  const tanks = vessel.ballast_tanks || {};
  const containers = vessel.containers || [];
  const rec = stabilityResult?.recommendation;
  const isSimulated = vessel.is_simulated ?? true;
  
  // Phase 5/6A Telemetry Quality & Provenance
  const telemetrySource = isSimulated ? "SIMULATED TELEMETRY" : "HARDWARE TELEMETRY — NON-AUTHORITATIVE";
  const telemetrySourceLabel = isSimulated ? "[SIMULATED TELEMETRY]" : "[HARDWARE TELEMETRY — NON-AUTHORITATIVE]";
  const connectionStatus = vessel.connection_status || (isSimulated ? "SIMULATED" : (socketConnected ? "CONNECTED" : "DISCONNECTED"));

  const isStale = (vessel.stale_seconds && vessel.stale_seconds >= 5.0) || vessel.telemetry_freshness === "STALE";
  const isDisconnected = connectionStatus === "DISCONNECTED";
  const staleSeconds = vessel.stale_seconds || 0.0;
  const timestampStr = vessel.telemetry_timestamp 
    ? new Date(vessel.telemetry_timestamp).toLocaleTimeString() 
    : new Date().toLocaleTimeString();

  const pumpState = vessel.pump_state || "IDLE";
  const pumpFlow = vessel.pump_flow_l_s || 0.0;
  const pumpActive = vessel.pump_active || vessel.is_pumping || (pumpState !== "IDLE" && pumpState !== "OFF");

  // Compute operational safety alerts based on live vessel state
  const liveList = Math.abs(vessel.roll || 0);
  const liveTrim = Math.abs(vessel.pitch || 0);
  const portVol = Object.entries(tanks)
    .filter(([k]) => k.toLowerCase().includes("port"))
    .reduce((sum, [, t]) => sum + (t.current_volume || 0), 0);
  const stbdVol = Object.entries(tanks)
    .filter(([k]) => k.toLowerCase().includes("starboard"))
    .reduce((sum, [, t]) => sum + (t.current_volume || 0), 0);
  const ballastImbalance = Math.abs(portVol - stbdVol);

  const activeAlerts: Array<{ type: string; severity: "WARNING" | "CRITICAL"; msg: string; action: string }> = [];
  
  if (isDisconnected) {
    activeAlerts.push({
      type: "TELEMETRY_DISCONNECTED",
      severity: "CRITICAL",
      msg: "Physical telemetry stream is offline. Preserving last verified state without synthesizing synthetic sensor data.",
      action: "Check serial COM / ESP32 link or switch to Simulation mode."
    });
  } else if (isStale) {
    activeAlerts.push({
      type: "STALE_TELEMETRY",
      severity: "WARNING",
      msg: `Telemetry stream delay is ${staleSeconds.toFixed(1)}s (exceeds 5.0s threshold). Displaying preserved values.`,
      action: "Verify sensor polling rate and telemetry adapter health."
    });
  }

  if (liveList >= 5.0) {
    activeAlerts.push({
      type: "EXCESSIVE_LIST",
      severity: "CRITICAL",
      msg: `Severe vessel list detected (${liveList.toFixed(2)}°). Extreme capsizing/heeling risk.`,
      action: "Halt cargo operations. Initiate emergency anti-heeling counter-flooding."
    });
  } else if (liveList >= 2.5) {
    activeAlerts.push({
      type: "EXCESSIVE_LIST",
      severity: "WARNING",
      msg: `Excessive vessel list (${liveList.toFixed(2)}°) exceeds standard operating threshold.`,
      action: "Review container weight distribution and execute ballast compensation."
    });
  }

  if (liveTrim >= 3.0) {
    activeAlerts.push({
      type: "EXCESSIVE_TRIM",
      severity: "CRITICAL",
      msg: `Critical longitudinal trim deviation (${liveTrim.toFixed(2)}°).`,
      action: "Execute longitudinal ballast transfer forward/aft to level keel."
    });
  } else if (liveTrim >= 1.5) {
    activeAlerts.push({
      type: "EXCESSIVE_TRIM",
      severity: "WARNING",
      msg: `Elevated longitudinal trim angle (${liveTrim.toFixed(2)}°).`,
      action: "Adjust container bay distribution forward/aft."
    });
  }

  if (ballastImbalance >= 150.0) {
    activeAlerts.push({
      type: "BALLAST_IMBALANCE",
      severity: "WARNING",
      msg: `Transverse ballast asymmetry: ${ballastImbalance.toFixed(1)}t difference (Port: ${portVol.toFixed(0)}t, Starboard: ${stbdVol.toFixed(0)}t).`,
      action: "Re-level ballast tanks across port and starboard manifolds."
    });
  }

  // 4-Stage Lifecycle Data Construction
  const stageData = {
    BEFORE: {
      label: "1. Vessel Before Container",
      provenance: "[CALCULATED]",
      list: stabilityResult?.stability?.before.list_t ?? vessel.roll,
      trim: stabilityResult?.stability?.before.trim_t ?? vessel.pitch,
      score: stabilityResult?.stability?.before.stability_score ?? vessel.stability_score,
      status: "INITIAL EQUILIBRIUM"
    },
    LOADED: {
      label: "2. Container Loaded",
      provenance: loadedResult ? "[CALCULATED]" : "[PREDICTED]",
      list: stabilityResult?.stability?.after.list_t ?? vessel.roll,
      trim: stabilityResult?.stability?.after.trim_t ?? vessel.pitch,
      score: stabilityResult?.stability?.after.stability_score ?? vessel.stability_score,
      status: loadedResult ? "COMMITTED" : "PREDICTED SIMULATION"
    },
    BALLASTED: {
      label: "3. Ballast Compensated",
      provenance: operationStatus === "COMPLETED" ? "[CALCULATED]" : "[PREDICTED]",
      list: ballastCompensation?.projected_stability?.list_t ?? 0.0,
      trim: ballastCompensation?.projected_stability?.trim_t ?? 0.0,
      score: ballastCompensation?.projected_stability?.stability_score ?? 96.0,
      status: operationStatus === "COMPLETED" ? "CONFIRMED" : "PREDICTED COMPENSATION"
    },
    CURRENT: {
      label: "4. Current Live Vessel State",
      provenance: telemetrySourceLabel,
      list: vessel.roll,
      trim: vessel.pitch,
      score: vessel.stability_score,
      status: isDisconnected ? "OFFLINE (PRESERVED)" : (isStale ? "STALE TELEMETRY" : "LIVE SENSOR TELEMETRY")
    }
  };

  const activeStage = stageData[selectedStage];

  // Helper to find container in a slot
  const findContainer = (bay: number, side: string, tier: number) => {
    return containers.find(
      c => c.bay === bay && c.side.toLowerCase() === side.toLowerCase() && c.tier === tier
    );
  };

  const isProjectedSlot = (bay: number, side: string, tier: number) => {
    if (!rec) return false;
    return rec.bay === bay && rec.side.toLowerCase() === side.toLowerCase() && rec.tier === tier;
  };

  return (
    <div className="bg-brand-surface border border-brand-border rounded-2xl p-5 shadow-2xl space-y-5">
      {/* 1. Header with Title, Ship Info, and Multi-Layer Provenance Badges */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between border-b border-brand-border/60 pb-3 gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-black text-white uppercase tracking-wide">
                Cargo-Aware Vessel Digital Twin
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/40 uppercase">
                {vessel.ship_name}
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Live bay cross-section, ballast compartments, pump telemetry, and predictive hydrostatic monitoring.
            </p>
          </div>
        </div>

        {/* 5-Tier Data Provenance Badges */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider border flex items-center gap-1 bg-emerald-950/40 text-emerald-300 border-emerald-500/40" title="Cargo weight & dimensions authoritative source">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            <span>[DOCUMENT AI]</span>
          </span>
          <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider border flex items-center gap-1 bg-blue-950/40 text-blue-300 border-blue-500/40" title="Hydrostatic physics stability engine">
            <Compass className="w-3 h-3 text-blue-400" />
            <span>[CALCULATED]</span>
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider border flex items-center gap-1 ${
            isDisconnected
              ? "bg-red-950/40 text-red-300 border-red-500/40"
              : isSimulated 
                ? "bg-purple-950/40 text-purple-300 border-purple-500/40" 
                : "bg-emerald-950/40 text-emerald-300 border-emerald-500/40"
          }`} title="Physical motion inclinometer & telemetry source">
            <Radio className="w-3 h-3 animate-pulse" />
            <span>{telemetrySourceLabel}</span>
          </span>
          <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider border flex items-center gap-1 bg-amber-950/40 text-amber-300 border-amber-500/40" title="Candidate pre-load simulation engine">
            <Zap className="w-3 h-3 text-amber-400" />
            <span>[PREDICTED]</span>
          </span>
        </div>
      </div>

      {/* 2. Real-Time Telemetry Quality, Freshness, & Pump Status Bar */}
      <div className="bg-brand-app/80 border border-brand-border/80 rounded-xl p-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        {/* Connection Status */}
        <div className="flex items-center gap-2">
          {isDisconnected ? (
            <WifiOff className="w-4 h-4 text-red-400 shrink-0" />
          ) : (
            <Wifi className="w-4 h-4 text-emerald-400 shrink-0" />
          )}
          <div>
            <div className="text-[9px] text-gray-400 uppercase font-bold">Link Status</div>
            <div className={`font-mono font-bold text-[11px] uppercase ${
              isDisconnected ? "text-red-400" : (isSimulated ? "text-purple-300" : "text-emerald-400")
            }`}>
              {connectionStatus}
            </div>
          </div>
        </div>

        {/* Telemetry Freshness & Timestamp */}
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-cyan-400 shrink-0" />
          <div>
            <div className="text-[9px] text-gray-400 uppercase font-bold">Freshness & Time</div>
            <div className="flex items-center gap-1 font-mono text-[11px]">
              <span className={`px-1.5 py-0.2 rounded text-[9px] font-black uppercase ${
                isStale ? "bg-amber-500/20 text-amber-300" : "bg-emerald-500/20 text-emerald-300"
              }`}>
                {isStale ? `STALE (+${staleSeconds.toFixed(0)}s)` : "FRESH"}
              </span>
              <span className="text-gray-300 text-[10px]">{timestampStr}</span>
            </div>
          </div>
        </div>

        {/* Pump Operational State */}
        <div className="flex items-center gap-2">
          <Droplets className={`w-4 h-4 shrink-0 ${pumpActive ? "text-cyan-400 animate-bounce" : "text-gray-400"}`} />
          <div>
            <div className="text-[9px] text-gray-400 uppercase font-bold">Ballast Pump</div>
            <div className="flex items-center gap-1 font-mono font-bold text-[11px]">
              <span className={pumpActive ? "text-cyan-300" : "text-gray-300"}>{pumpState}</span>
              {pumpActive && pumpFlow > 0 && (
                <span className="text-[9px] text-cyan-400">({pumpFlow.toFixed(1)} L/s)</span>
              )}
            </div>
          </div>
        </div>

        {/* Cargo Weight Provenance Verification */}
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <div>
            <div className="text-[9px] text-gray-400 uppercase font-bold">Cargo Mass Source</div>
            <div className="font-mono font-bold text-[11px] text-emerald-300">
              DOCUMENT AI <span className="text-[9px] text-gray-400 font-normal">(Zero Load-Cell)</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Stale Telemetry Warning Banner (if applicable) */}
      {(isStale || isDisconnected) && (
        <div className="p-3 bg-amber-950/40 border border-amber-500/50 rounded-xl flex items-start gap-2.5 text-xs text-amber-200">
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <strong className="font-bold uppercase tracking-wide">
              {isDisconnected ? "Physical Telemetry Disconnected" : "Telemetry Stream Stale"}
            </strong>
            <p className="text-[11px] text-amber-300/90 mt-0.5">
              {isDisconnected 
                ? "Physical sensor connection is currently offline. Preserving the last verified vessel state without synthesizing fake hardware data."
                : `No fresh telemetry received in the last ${staleSeconds.toFixed(1)} seconds. Retaining last known physical inclinometer values.`}
            </p>
          </div>
        </div>
      )}

      {/* 4. Operational Safety Alerts (if any) */}
      {activeAlerts.length > 0 && (
        <div className="space-y-2">
          {activeAlerts.map((alert, idx) => (
            <div 
              key={idx} 
              className={`p-3 rounded-xl border flex items-start justify-between gap-3 text-xs ${
                alert.severity === "CRITICAL" 
                  ? "bg-red-950/40 border-red-500/60 text-red-200" 
                  : "bg-amber-950/30 border-amber-500/50 text-amber-200"
              }`}
            >
              <div className="flex items-start gap-2.5">
                {alert.severity === "CRITICAL" ? (
                  <AlertOctagon className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold uppercase text-[10px] tracking-wider">
                      {alert.type}
                    </span>
                    <span className={`px-1.5 py-0.2 rounded text-[9px] font-black uppercase ${
                      alert.severity === "CRITICAL" ? "bg-red-500/20 text-red-300" : "bg-amber-500/20 text-amber-300"
                    }`}>
                      {alert.severity}
                    </span>
                  </div>
                  <p className="text-gray-300 mt-0.5">{alert.msg}</p>
                  <p className="text-[11px] font-semibold text-amber-300 mt-1">
                    <strong>Action:</strong> {alert.action}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 5. 4-Stage Lifecycle Stepper with Explicit Provenance Tags */}
      <div className="bg-brand-app/60 border border-brand-border/80 rounded-xl p-3 space-y-2">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-gray-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            4-Stage Operation Lifecycle
          </span>
          <span className="text-cyan-300 font-mono text-[10px] uppercase">
            Viewing: {activeStage.label} <span className="text-gray-400 font-normal">({activeStage.provenance})</span>
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {(["BEFORE", "LOADED", "BALLASTED", "CURRENT"] as const).map((stage) => {
            const data = stageData[stage];
            const isSelected = selectedStage === stage;
            return (
              <button
                key={stage}
                onClick={() => setSelectedStage(stage)}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  isSelected
                    ? "bg-blue-600/20 border-blue-500 text-white shadow-md shadow-blue-500/10"
                    : "bg-brand-dark/60 border-brand-border/60 text-gray-400 hover:text-gray-200 hover:border-gray-500"
                }`}
              >
                <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-wider truncate mb-1">
                  <span className="truncate">{data.label}</span>
                  <span className="text-[8px] font-mono text-cyan-300 px-1 py-0.2 rounded bg-cyan-950/60 border border-cyan-800/40">
                    {data.provenance}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span>List: <strong className="text-white">{data.list.toFixed(1)}°</strong></span>
                  <span>Trim: <strong className="text-white">{data.trim.toFixed(1)}°</strong></span>
                </div>
                <div className="text-[9px] text-gray-400 mt-1 truncate">
                  Score: <strong className="text-cyan-300">{data.score.toFixed(0)}/100</strong>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 6. 4-Bay Vessel Cross-Section & SCADA Ballast Twin */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
            <Box className="w-4 h-4 text-brand-accent" />
            Vessel Cargo Bay & Ballast Cross-Section (Bays 1 – 4)
          </span>
          <span className="text-[10px] text-gray-400 font-mono flex items-center gap-1">
            <span>{containers.length} Containers ({Math.round(containers.reduce((s, c) => s + c.weight, 0))}t)</span>
            <span className="text-emerald-400 font-bold">[DOCUMENT AI]</span>
          </span>
        </div>

        {/* 4 Bay Rows */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((bayNum) => {
            const portTank = tanks[`port_${bayNum}`] || { name: `PT-${bayNum}`, current_volume: 300, capacity: 300, fill_ratio: 1.0 };
            const stbdTank = tanks[`starboard_${bayNum}`] || { name: `ST-${bayNum}`, current_volume: 300, capacity: 300, fill_ratio: 1.0 };

            return (
              <div key={bayNum} className="bg-brand-dark/90 border border-brand-border rounded-xl p-3 space-y-2 shadow-sm">
                {/* Bay Header */}
                <div className="flex items-center justify-between border-b border-brand-border/50 pb-1.5 text-xs">
                  <span className="font-black text-white uppercase tracking-wider">
                    Bay {bayNum.toString().padStart(2, '0')}
                  </span>
                  <span className="text-[10px] text-gray-400 font-mono">
                    {containers.filter(c => c.bay === bayNum).length} Containers
                  </span>
                </div>

                {/* Cargo Slots Grid (Tier 2 on top, Tier 1 on base) */}
                <div className="space-y-1.5">
                  {/* Tier 2 */}
                  <div className="grid grid-cols-2 gap-1.5">
                    {/* Port Tier 2 */}
                    {renderSlot(bayNum, "PORT", 2, findContainer(bayNum, "port", 2), isProjectedSlot(bayNum, "port", 2))}
                    {/* Starboard Tier 2 */}
                    {renderSlot(bayNum, "STARBOARD", 2, findContainer(bayNum, "starboard", 2), isProjectedSlot(bayNum, "starboard", 2))}
                  </div>

                  {/* Tier 1 (Base) */}
                  <div className="grid grid-cols-2 gap-1.5">
                    {/* Port Tier 1 */}
                    {renderSlot(bayNum, "PORT", 1, findContainer(bayNum, "port", 1), isProjectedSlot(bayNum, "port", 1))}
                    {/* Starboard Tier 1 */}
                    {renderSlot(bayNum, "STARBOARD", 1, findContainer(bayNum, "starboard", 1), isProjectedSlot(bayNum, "starboard", 1))}
                  </div>
                </div>

                {/* Ballast Tanks at Keel Level */}
                <div className="pt-2 border-t border-brand-border/40 grid grid-cols-2 gap-1.5 text-[10px]">
                  {/* Port Tank */}
                  <div className="bg-blue-950/30 border border-blue-500/30 rounded p-1.5 space-y-1">
                    <div className="flex items-center justify-between text-blue-300 font-bold">
                      <span>PT-{bayNum}</span>
                      <span>{Math.round(portTank.fill_ratio * 100)}%</span>
                    </div>
                    {/* Tank Fill Bar */}
                    <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-cyan-400 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(0, portTank.fill_ratio * 100))}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[9px] text-gray-400 font-mono">
                      <span>{Math.round(portTank.current_volume)}t</span>
                      <span className="text-[8px] text-cyan-400 font-bold">[CALCULATED]</span>
                    </div>
                  </div>

                  {/* Starboard Tank */}
                  <div className="bg-blue-950/30 border border-blue-500/30 rounded p-1.5 space-y-1">
                    <div className="flex items-center justify-between text-blue-300 font-bold">
                      <span>ST-{bayNum}</span>
                      <span>{Math.round(stbdTank.fill_ratio * 100)}%</span>
                    </div>
                    {/* Tank Fill Bar */}
                    <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-cyan-400 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(0, stbdTank.fill_ratio * 100))}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[9px] text-gray-400 font-mono">
                      <span>{Math.round(stbdTank.current_volume)}t</span>
                      <span className="text-[8px] text-cyan-400 font-bold">[CALCULATED]</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 7. PROJECTED vs ACTUAL Predictive Monitoring Matrix */}
      {stabilityResult && (
        <div className="bg-brand-app/70 border border-brand-border rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                Predictive Hydrostatic Matrix: Projected vs Actual
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/30 uppercase">
                Container: {stabilityResult.container?.container_number || "Active Operation"}
              </span>
              <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 uppercase">
                [DOCUMENT AI]
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            {/* List Comparison */}
            <div className="bg-black/30 p-3 rounded-lg border border-brand-border/60 space-y-1">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Transverse List</span>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-amber-400 text-[10px]">[PREDICTED]:</span>
                <span className="text-amber-300 font-bold">{stabilityResult.stability?.after.list_t.toFixed(2)}°</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-cyan-400 text-[10px]">[CALCULATED]:</span>
                <span className="text-cyan-300 font-bold">{vessel.roll.toFixed(2)}°</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-purple-400 text-[10px]">{telemetrySourceLabel}:</span>
                <span className="text-white font-bold">{vessel.roll.toFixed(2)}°</span>
              </div>
            </div>

            {/* Trim Comparison */}
            <div className="bg-black/30 p-3 rounded-lg border border-brand-border/60 space-y-1">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Longitudinal Trim</span>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-amber-400 text-[10px]">[PREDICTED]:</span>
                <span className="text-amber-300 font-bold">{stabilityResult.stability?.after.trim_t.toFixed(2)}°</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-cyan-400 text-[10px]">[CALCULATED]:</span>
                <span className="text-cyan-300 font-bold">{vessel.pitch.toFixed(2)}°</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-purple-400 text-[10px]">{telemetrySourceLabel}:</span>
                <span className="text-white font-bold">{vessel.pitch.toFixed(2)}°</span>
              </div>
            </div>

            {/* Stability Score Comparison */}
            <div className="bg-black/30 p-3 rounded-lg border border-brand-border/60 space-y-1">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Stability Score</span>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-amber-400 text-[10px]">[PREDICTED]:</span>
                <span className="text-amber-300 font-bold">{stabilityResult.stability?.after.stability_score.toFixed(1)}/100</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-cyan-400 text-[10px]">[CALCULATED]:</span>
                <span className="text-cyan-300 font-bold">{vessel.stability_score.toFixed(1)}/100</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-purple-400 text-[10px]">{telemetrySourceLabel}:</span>
                <span className="text-white font-bold">{vessel.stability_score.toFixed(1)}/100</span>
              </div>
            </div>

            {/* Ballast Requirement */}
            <div className="bg-black/30 p-3 rounded-lg border border-brand-border/60 space-y-1">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Ballast Compensation</span>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-amber-400 text-[10px]">[PREDICTED]:</span>
                <span className="text-amber-300 font-bold">~{Math.round(Math.abs(stabilityResult.stability?.after.list_t || 0) * 20)}t</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-gray-400 text-[10px]">[STATUS]:</span>
                <span className="text-amber-300 font-bold">{ballastCompensation ? "CALCULATED" : "PENDING LOAD"}</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-cyan-400 text-[10px]">[PUMP]:</span>
                <span className={pumpActive ? "text-cyan-300 font-bold" : "text-gray-400"}>{pumpState}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  // Helper render for individual cell slot
  function renderSlot(bay: number, side: "PORT" | "STARBOARD", tier: number, container?: any, isProjected?: boolean) {
    if (container) {
      return (
        <div className="bg-brand-surface border border-brand-border p-2 rounded text-center space-y-0.5 shadow-inner">
          <div className="flex items-center justify-between text-[9px] text-gray-400">
            <span>{side[0]}T{tier}</span>
            <span className="text-emerald-400 font-bold font-mono">{container.weight}t</span>
          </div>
          <div className="font-mono font-bold text-[10px] text-white truncate">
            {container.id}
          </div>
          <div className="text-[8px] text-emerald-400 font-mono font-bold">
            [DOCUMENT AI]
          </div>
        </div>
      );
    }

    if (isProjected) {
      return (
        <div className="bg-blue-950/40 border-2 border-dashed border-cyan-400 p-2 rounded text-center space-y-0.5 animate-pulse shadow-md shadow-cyan-500/20">
          <div className="flex items-center justify-between text-[9px] text-cyan-300 font-bold">
            <span>{side[0]}T{tier}</span>
            <span>[PREDICTED]</span>
          </div>
          <div className="font-mono font-black text-[10px] text-cyan-200 truncate">
            {extractedData?.container?.container_number || "ASSIGNED"}
          </div>
          <div className="text-[8px] text-cyan-300 font-mono font-bold">
            [DOCUMENT AI]
          </div>
        </div>
      );
    }

    return (
      <div className="bg-brand-dark/40 border border-brand-border/40 p-2 rounded text-center text-gray-600 text-[9px] font-mono">
        {side[0]}T{tier} (Empty)
      </div>
    );
  }
};
