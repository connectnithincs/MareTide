import React from "react";
import { WifiOff, Cpu, Radio, ShieldCheck, Clock, AlertTriangle } from "lucide-react";

export interface VesselStatusIndicatorProps {
  connected: boolean;
  isSimulated: boolean;
  telemetrySource?: string;
  stabilityScore?: number;
  stabilityRisk?: string;
  staleSeconds?: number;
  telemetryTimestamp?: string;
  className?: string;
}

export const VesselStatusIndicator: React.FC<VesselStatusIndicatorProps> = ({
  connected,
  isSimulated,
  telemetrySource,
  stabilityScore,
  stabilityRisk = "SAFE",
  staleSeconds = 0,
  telemetryTimestamp,
  className = ""
}) => {
  const isStale = staleSeconds >= 3.0;
  const isDisconnected = !connected;
  const isVirtualESP32 = telemetrySource === "SIMULATED_ESP32" || telemetrySource === "virtual_esp32";
  const isRealHardware = telemetrySource === "HARDWARE_SENSOR" || (!isSimulated && !isVirtualESP32);

  const timeFormatted = telemetryTimestamp 
    ? new Date(telemetryTimestamp).toLocaleTimeString() 
    : new Date().toLocaleTimeString();

  return (
    <div className={`inline-flex items-center gap-2 text-xs font-mono select-none ${className}`}>
      {/* Telemetry Link Provenance Capsule */}
      <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[10px] font-mono font-bold uppercase tracking-wider backdrop-blur-md shadow-sm transition-all ${
        isDisconnected
          ? "bg-red-500/10 border-red-500/30 text-red-400"
          : isVirtualESP32
          ? isStale
            ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
            : "bg-purple-500/10 border-purple-500/30 text-purple-300 shadow-purple-500/10"
          : isRealHardware
          ? isStale
            ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
            : "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-emerald-500/10"
          : "bg-cyan-500/10 border-cyan-500/30 text-cyan-300"
      }`}>
        {isDisconnected ? (
          <>
            <span className="w-2 h-2 rounded-full bg-red-500 shadow-sm shadow-red-500/60" />
            <WifiOff className="w-3 h-3 text-red-400" />
            <span>DISCONNECTED</span>
          </>
        ) : isVirtualESP32 ? (
          <>
            <span className={`w-2 h-2 rounded-full ${isStale ? 'bg-amber-400 animate-ping' : 'bg-purple-400 animate-pulse shadow-sm shadow-purple-400/60'}`} />
            <Cpu className="w-3 h-3 text-purple-300" />
            <span>{isStale ? "VIRTUAL LINK STALE" : "VIRTUAL ESP32"}</span>
          </>
        ) : isRealHardware ? (
          <>
            <span className={`w-2 h-2 rounded-full ${isStale ? 'bg-amber-400 animate-ping' : 'bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400/60'}`} />
            <Radio className="w-3 h-3 text-emerald-400" />
            <span>{isStale ? "HARDWARE LINK STALE" : "ESP32 HARDWARE"}</span>
          </>
        ) : (
          <>
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-sm shadow-cyan-400/60" />
            <Cpu className="w-3 h-3 text-cyan-300" />
            <span>SIMULATED TELEMETRY</span>
          </>
        )}
      </div>

      {/* Stability Score Capsule */}
      {stabilityScore !== undefined && (
        <div className={`hidden md:inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[10px] font-mono font-bold uppercase backdrop-blur-md shadow-sm ${
          stabilityRisk === "SAFE"
            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
            : stabilityRisk === "ADVISORY"
            ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
            : "bg-red-500/10 border-red-500/30 text-red-400"
        }`}>
          <ShieldCheck className="w-3 h-3" />
          <span>STABILITY: {stabilityScore.toFixed(0)}% ({stabilityRisk})</span>
        </div>
      )}
    </div>
  );
};
