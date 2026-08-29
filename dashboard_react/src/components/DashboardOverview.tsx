import React from "react";
import { useSocket } from "../context/SocketContext";
import { SCADADigitalTwin } from "./SCADADigitalTwin";
import { Inclinometer } from "./Inclinometer";
import { RecommendationCard } from "./RecommendationCard";
import { Shield, Anchor, Activity, Scale, Compass } from "lucide-react";

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

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Top Telemetry Connection Status */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Vessel Telemetry Overview</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Real-time stability monitoring and AI-guided stowage compensation.</p>
        </div>
        <div className={`flex items-center gap-2 border px-3 py-1.5 rounded-lg ${
          connected 
            ? "bg-brand-accentBg border-brand-accent/20 text-brand-accent" 
            : "bg-brand-dangerBg border-brand-danger/20 text-brand-danger"
        }`}>
          <div className={`w-2 h-2 rounded-full ${connected ? "bg-brand-accent animate-pulse" : "bg-brand-danger"}`} />
          <span className="text-[10px] font-black uppercase tracking-wider">
            {connected ? "IoT Stream Connected" : "Connection Lost"}
          </span>
        </div>
      </div>

      {/* Primary KPIs grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* KPI 1: Stability Score */}
        <div className={`bg-brand-card border ${borderCol} p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel`}>
          <div className={`p-3 ${scoreBg} rounded-xl`}>
            <Shield className={`w-6 h-6 ${scoreCol}`} />
          </div>
          <div>
            <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">Stability Index</span>
            <span className={`text-xl font-black ${scoreCol}`}>{score.toFixed(1)}%</span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">Risk: {vesselState.stability_risk}</span>
          </div>
        </div>

        {/* KPI 2: Roll Angle */}
        <div className="bg-brand-card border border-brand-border p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel">
          <div className="p-3 bg-[#5483B3]/12 rounded-xl">
            <Compass className="w-6 h-6 text-[#5483B3]" />
          </div>
          <div>
            <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">List / Roll</span>
            <span className="text-xl font-black text-brand-text">{vesselState.roll.toFixed(2)}°</span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">
              {vesselState.roll > 0 ? "Starboard List" : vesselState.roll < 0 ? "Port List" : "Balanced"}
            </span>
          </div>
        </div>

        {/* KPI 3: Cargo Weight */}
        <div className="bg-brand-card border border-brand-border p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel">
          <div className="p-3 bg-amber-500/12 rounded-xl">
            <Scale className="w-6 h-6 text-amber-500" />
          </div>
          <div>
            <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">Total Stowage Weight</span>
            <span className="text-xl font-black text-brand-text">
              {vesselState.containers.reduce((acc, c) => acc + c.weight, 0).toFixed(1)} t
            </span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">
              {vesselState.containers.length} Containers Loaded
            </span>
          </div>
        </div>

        {/* KPI 4: Active Scale Weight */}
        <div className="bg-brand-card border border-brand-border p-4 rounded-xl flex items-center gap-4 shadow-md glass-panel">
          <div className="p-3 bg-brand-accentBg rounded-xl">
            <Anchor className="w-6 h-6 text-brand-accent" />
          </div>
          <div>
            <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">Active Scale Cargo</span>
            <span className="text-xl font-black text-brand-text">{vesselState.cargo_t.toFixed(1)} t</span>
            <span className="text-[9px] text-brand-muted font-semibold block mt-0.5 uppercase">
              Scale Model: {vesselState.cargo_kg.toFixed(2)} kg
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
        
        {/* We can fetch recommendations from the state endpoints directly, but passing down basic values is also great */}
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
