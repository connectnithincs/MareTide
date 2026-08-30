import React from "react";
import { useSocket } from "../context/SocketContext";
import { SCADADigitalTwin } from "./SCADADigitalTwin";
import { Inclinometer } from "./Inclinometer";
import { RecommendationCard } from "./RecommendationCard";
import { Shield, Droplets, Activity, Scale, Compass } from "lucide-react";

export const DashboardOverview: React.FC = () => {
  const { connected, vesselState } = useSocket();

  if (!vesselState) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-brand-dark p-8">
        <Activity className="w-12 h-12 text-brand-accent animate-spin mb-4" />
        <p className="text-sm text-brand-muted font-bold animate-pulse">Synchronizing vessel telemetry state...</p>
      </div>
    );
  }

  // Pick color for stability score
  const score = vesselState.stability_score;
  let scoreCol = "text-brand-accent";
  let scoreBg = "bg-brand-accentBg";
  let borderCol = "border-brand-border";
  if (score < 50) {
    scoreCol = "text-brand-danger";
    scoreBg = "bg-brand-dangerBg";
    borderCol = "border-brand-danger/30";
  } else if (score < 85) {
    scoreCol = "text-amber-500";
    scoreBg = "bg-amber-500/12";
    borderCol = "border-amber-500/30";
  }

  // Total ballast displacement
  const totalBallastT = Object.values(vesselState.ballast_tanks || {}).reduce(
    (acc, t) => acc + (t.current_volume || 0), 
    0
  );

  const totalCargoT = (vesselState.containers || []).reduce(
    (acc, c) => acc + (c.weight || 0), 
    0
  );

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Top Telemetry Connection Status */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-brand-border pb-4 gap-3">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Vessel Telemetry Overview</h2>
            <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              Provenance: [DOCUMENT AI] + [CALCULATED]
            </span>
          </div>
          <p className="text-xs text-brand-muted font-semibold mt-1">Real-time stability monitoring, hydrostatics, and AI-guided stowage supervisory overview.</p>
        </div>

        <div className={`flex items-center gap-2 border px-3.5 py-1.5 rounded-xl shadow ${
          connected 
            ? "bg-brand-accentBg border-brand-accent/20 text-brand-accent" 
            : "bg-brand-dangerBg border-brand-danger/20 text-brand-danger"
        }`}>
          <div className={`w-2.5 h-2.5 rounded-full ${connected ? "bg-brand-accent animate-pulse" : "bg-brand-danger"}`} />
          <span className="text-[10px] font-black uppercase tracking-wider">
            {connected ? (vesselState.is_simulated ? "Simulated Telemetry Stream" : "Hardware IoT Telemetry") : "Telemetry Disconnected"}
          </span>
        </div>
      </div>

      {/* Primary KPIs grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* KPI 1: Stability Score */}
        <div className={`bg-brand-card border ${borderCol} p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel relative overflow-hidden`}>
          <div className={`p-3 ${scoreBg} rounded-xl`}>
            <Shield className={`w-6 h-6 ${scoreCol}`} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">Stability Index</span>
              <span className="text-[8px] font-extrabold text-blue-400 bg-blue-500/10 px-1 rounded">[CALC]</span>
            </div>
            <span className={`text-xl font-black ${scoreCol}`}>{score.toFixed(1)}%</span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">Risk: {vesselState.stability_risk}</span>
          </div>
        </div>

        {/* KPI 2: Roll Angle */}
        <div className="bg-brand-card border border-brand-border p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel relative overflow-hidden">
          <div className="p-3 bg-[#5483B3]/12 rounded-xl">
            <Compass className="w-6 h-6 text-[#5483B3]" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">List / Roll</span>
              <span className="text-[8px] font-extrabold text-amber-400 bg-amber-500/10 px-1 rounded">[TEL]</span>
            </div>
            <span className="text-xl font-black text-brand-text">{vesselState.roll.toFixed(2)}°</span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">
              {vesselState.roll > 0 ? "Starboard List" : vesselState.roll < 0 ? "Port List" : "Balanced"}
            </span>
          </div>
        </div>

        {/* KPI 3: Cargo Stowage Mass */}
        <div className="bg-brand-card border border-brand-border p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel relative overflow-hidden">
          <div className="p-3 bg-amber-500/12 rounded-xl">
            <Scale className="w-6 h-6 text-amber-500" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">Document Cargo</span>
              <span className="text-[8px] font-extrabold text-cyan-400 bg-cyan-500/10 px-1 rounded">[DOC AI]</span>
            </div>
            <span className="text-xl font-black text-brand-text">
              {totalCargoT.toFixed(1)} t
            </span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">
              {vesselState.containers.length} Containers Loaded
            </span>
          </div>
        </div>

        {/* KPI 4: Ballast Water Displacement */}
        <div className="bg-brand-card border border-brand-border p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel relative overflow-hidden">
          <div className="p-3 bg-cyan-500/12 rounded-xl">
            <Droplets className="w-6 h-6 text-cyan-400" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">Ballast Water</span>
              <span className="text-[8px] font-extrabold text-blue-400 bg-blue-500/10 px-1 rounded">[CALC]</span>
            </div>
            <span className="text-xl font-black text-brand-text">{totalBallastT.toFixed(1)} t</span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">
              {Object.keys(vesselState.ballast_tanks || {}).length} Active Tanks
            </span>
          </div>
        </div>
      </div>

      {/* Row 2: Digital Twin (Visualizer) */}
      <div className="w-full">
        <SCADADigitalTwin tanks={vesselState.ballast_tanks} />
      </div>

      {/* Row 3: Inclinometer & AI Recommendations Side by Side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Inclinometer roll={vesselState.roll} pitch={vesselState.pitch} />
        
        <RecommendationCard 
          bestBay={vesselState.active_rec_bay}
          bestSide={vesselState.active_rec_side}
          bestScore={vesselState.stability_score}
          recommendations={[]}
          stabilityScore={vesselState.stability_score}
        />
      </div>
    </div>
  );
};
