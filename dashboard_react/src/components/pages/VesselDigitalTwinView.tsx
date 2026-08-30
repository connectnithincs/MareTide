import React, { useState, useRef } from "react";
import { useSocket } from "../../context/SocketContext";
import { useContainerOperation } from "../../context/ContainerOperationContext";
import { BallastControlTable } from "../BallastControlTable";
import { 
  Anchor, 
  Layers, 
  Droplets, 
  Box, 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Flame, 
  Eye, 
  SlidersHorizontal,
  Compass,
  RefreshCw,
  Maximize2,
  X
} from "lucide-react";
import { StatusBadge } from "../ui/StatusBadge";
import { SafetyBadge } from "../ui/SafetyBadge";
import { SectionHeader } from "../ui/SectionHeader";
import { LoadingState } from "../ui/LoadingState";
import { Vessel3DCanvas } from "../vessel_3d/Vessel3DCanvas";

export type ViewMode = "ISOMETRIC" | "TOP" | "SIDE" | "FRONT";
export type OperationLifecycleState = 
  | "BEFORE_LOAD" 
  | "PROJECTED_LOAD" 
  | "CONTAINER_LOADED" 
  | "BALLAST_COMPENSATED" 
  | "CURRENT_STATE";

export interface DigitalTwinContainer {
  id: string;
  bay: number;
  side: string;
  tier: number;
  weight: number;
  container_type?: string;
  hazardous?: boolean;
  isProjected?: boolean;
  provenance?: string;
}

export interface SelectedContainerInfo {
  id: string;
  bay: number;
  side: "PORT" | "STARBOARD";
  tier: number;
  weight: number;
  container_type: string;
  hazardous?: boolean;
  un_number?: string;
  imdg_class?: string;
  destination?: string;
}

export interface SelectedTankInfo {
  id: string;
  name: string;
  side: "PORT" | "STARBOARD";
  bay: number;
  location: string;
  current_volume: number;
  capacity: number;
  percentage: number;
  status: "NORMAL" | "LOW" | "HIGH" | "DISCHARGING";
}

export const VesselDigitalTwinView: React.FC = () => {
  const { connected, vesselState } = useSocket();
  const { stabilityResult } = useContainerOperation();

  // Viewport and spatial camera controls state
  const [displayMode, setDisplayMode] = useState<"3D" | "2D">("3D");
  const [viewMode, setViewMode] = useState<ViewMode>("ISOMETRIC");
  const [lifecycleState, setLifecycleState] = useState<OperationLifecycleState>("CURRENT_STATE");
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [showBallastMatrix, setShowBallastMatrix] = useState<boolean>(false);

  // Selected object state
  const [selectedContainer, setSelectedContainer] = useState<SelectedContainerInfo | null>(null);
  const [selectedTank, setSelectedTank] = useState<SelectedTankInfo | null>(null);

  const vesselCanvasRef = useRef<HTMLDivElement>(null);

  if (!vesselState) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-maretide-app">
        <LoadingState message="Connecting to High-Precision Vessel Digital Twin Stream..." />
      </div>
    );
  }

  // Live telemetry
  const tanks = vesselState.ballast_tanks || {};
  const containers = vesselState.containers || [];
  const roll = vesselState.roll ?? 0;
  const pitch = vesselState.pitch ?? 0;
  const score = vesselState.stability_score ?? 100;
  const risk = vesselState.stability_risk ?? "SAFE";
  const isSimulated = vesselState.is_simulated ?? true;
  const totalCargoT = containers.reduce((acc, c) => acc + (c.weight || 0), 0);
  const totalBallastT = Object.values(tanks).reduce((acc, t) => acc + (t.current_volume || 0), 0);

  // Derive active containers based on selected lifecycle state
  const getLifecycleContainers = (): DigitalTwinContainer[] => {
    if (lifecycleState === "BEFORE_LOAD") return [];
    if (lifecycleState === "PROJECTED_LOAD" && stabilityResult?.recommendation) {
      const rec = stabilityResult.recommendation;
      return [
        ...containers,
        {
          id: stabilityResult.container?.container_number || "PREVIEW_LOAD",
          bay: rec.bay,
          side: rec.side.toUpperCase(),
          tier: rec.tier,
          weight: (stabilityResult.container?.gross_weight_kg || 26200) / 1000,
          container_type: stabilityResult.container?.container_type || "40HC",
          hazardous: stabilityResult.container?.hazardous || false,
          isProjected: true
        }
      ];
    }
    return containers.map(c => ({
      id: c.id,
      bay: c.bay,
      side: c.side,
      tier: c.tier,
      weight: c.weight,
      container_type: "40HC",
      hazardous: false,
      provenance: c.provenance
    }));
  };

  const activeContainers = getLifecycleContainers();

  const handleResetCamera = () => {
    setZoomLevel(100);
    setViewMode("ISOMETRIC");
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 bg-brand-abyss">
      {/* 1. Header with Maritime Subtitle & Provenance */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-brand-borderSubtle">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-brand-cyanBg border border-brand-cyan/30 rounded-xl text-brand-cyan shadow-sm shadow-brand-cyan/20">
            <Anchor className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-sm font-mono font-black text-brand-text uppercase tracking-widest">
                VESSEL 3D DIGITAL TWIN & HYDROSTATICS STATION
              </h1>
              <SafetyBadge type={isSimulated ? "SIMULATED_TELEMETRY" : "HARDWARE_TELEMETRY"} size="sm" />
            </div>
            <p className="text-[11px] text-brand-muted font-medium mt-0.5">
              Three.js WebGL spatial coordinate binding, 4-bay cellular stowage, double-bottom ballast tanks, and manifold pumps.
            </p>
          </div>
        </div>

        {/* Lifecycle State Selector */}
        <div className="flex items-center gap-1.5 surface-base p-1 rounded-xl border border-brand-borderSubtle text-xs font-mono font-bold flex-wrap">
          <span className="text-[10px] text-brand-muted uppercase px-2 hidden md:inline">State:</span>
          {(
            [
              { id: "CURRENT_STATE", label: "Live (10Hz)" },
              { id: "BEFORE_LOAD", label: "Before Load" },
              { id: "PROJECTED_LOAD", label: "Projected" },
              { id: "CONTAINER_LOADED", label: "Loaded" },
              { id: "BALLAST_COMPENSATED", label: "Compensated" }
            ] as const
          ).map((st) => (
            <button
              key={st.id}
              onClick={() => setLifecycleState(st.id)}
              className={`px-3 py-1 rounded-lg text-[10px] transition-all uppercase ${
                lifecycleState === st.id
                  ? "bg-brand-cyan text-slate-950 shadow-md shadow-brand-cyan/20 font-black"
                  : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Main 3D WebGL Digital Twin Viewport */}
      <div className="surface-elevated border border-brand-borderSubtle relative rounded-2xl overflow-hidden flex flex-col min-h-[600px] shadow-2xl">
        {/* Viewport Top Bar: Engine Switcher, Camera & View Mode Controls */}
        <div className="p-3.5 border-b border-brand-borderSubtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 surface-base/90 backdrop-blur-md z-20">
          {/* Left: Viewport Engine (3D WebGL vs 2D SCADA) + Camera Angles */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* 3D vs 2D Engine Switch */}
            <div className="flex items-center surface-base p-0.5 rounded-xl border border-brand-borderSubtle text-xs font-mono font-bold">
              <button
                onClick={() => setDisplayMode("3D")}
                className={`px-3 py-1.5 rounded-lg text-[10px] uppercase transition-all tracking-wider flex items-center gap-1.5 ${
                  displayMode === "3D"
                    ? "bg-brand-cyan text-slate-950 font-black shadow-sm"
                    : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
                }`}
              >
                <Box className="w-3.5 h-3.5" />
                <span>3D WebGL</span>
              </button>
              <button
                onClick={() => setDisplayMode("2D")}
                className={`px-3 py-1.5 rounded-lg text-[10px] uppercase transition-all tracking-wider flex items-center gap-1.5 ${
                  displayMode === "2D"
                    ? "bg-brand-cyan text-slate-950 font-black shadow-sm"
                    : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>2D Cross-Section</span>
              </button>
            </div>

            {/* View Mode Controls: ISOMETRIC, TOP, SIDE, FRONT */}
            <div className="flex items-center gap-1 surface-base p-0.5 rounded-xl border border-brand-borderSubtle text-xs font-mono font-bold">
              {(["ISOMETRIC", "TOP", "SIDE", "FRONT"] as ViewMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] uppercase transition-all tracking-wider ${
                    viewMode === mode
                      ? "bg-brand-cyan text-slate-950 font-black shadow-sm"
                      : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          {/* Camera Controls Area */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <button
              onClick={() => setZoomLevel(prev => Math.min(prev + 15, 180))}
              className="p-2 surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text border border-brand-borderSubtle rounded-xl transition-all shadow-sm active:scale-95"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel(prev => Math.max(prev - 15, 50))}
              className="p-2 surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text border border-brand-borderSubtle rounded-xl transition-all shadow-sm active:scale-95"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleResetCamera}
              className="px-3 py-1.5 surface-base hover:bg-brand-hover text-brand-cyan border border-brand-cyan/30 rounded-xl transition-all flex items-center gap-1.5 text-[10px] font-bold shadow-sm active:scale-95"
              title="Reset Camera View"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>RESET</span>
            </button>
            <button
              onClick={() => setShowBallastMatrix(!showBallastMatrix)}
              className={`px-3 py-1.5 border rounded-xl transition-all flex items-center gap-1.5 text-[10px] font-bold shadow-sm active:scale-95 ${
                showBallastMatrix 
                  ? "bg-brand-cyan text-slate-950 border-brand-cyan font-black" 
                  : "surface-base text-brand-textSecondary hover:text-brand-text border-brand-borderSubtle hover:bg-brand-hover"
              }`}
              title="Toggle Ballast Pump Matrix"
            >
              <Droplets className="w-3.5 h-3.5" />
              <span>PUMP MATRIX</span>
            </button>
          </div>
        </div>

        {/* Viewport Core Canvas Area */}
        <div 
          ref={vesselCanvasRef}
          className="flex-1 relative flex items-center justify-center select-none overflow-hidden min-h-[520px]"
        >
          {/* Top-Left: Stability Telemetry Overlay HUD */}
          <div className="absolute top-4 left-4 z-10 surface-elevated backdrop-blur-xl p-3.5 rounded-2xl border border-brand-borderSubtle text-xs font-mono space-y-1.5 shadow-2xl max-w-[210px] pointer-events-none">
            <div className="flex items-center justify-between pb-1.5 border-b border-brand-borderSubtle text-[10px]">
              <span className="text-brand-muted uppercase font-bold">Stability Index</span>
              <StatusBadge status={risk} size="sm" />
            </div>
            <div className="flex justify-between">
              <span className="text-brand-muted">Score:</span>
              <span className="text-brand-safe font-bold">{score.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-brand-muted">List (Roll):</span>
              <span className={`font-bold ${Math.abs(roll) > 2 ? 'text-brand-warning' : 'text-brand-text'}`}>
                {Math.abs(roll).toFixed(2)}° {roll > 0 ? 'STBD' : roll < 0 ? 'PORT' : 'BAL'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-brand-muted">Trim (Pitch):</span>
              <span className={`font-bold ${Math.abs(pitch) > 1.5 ? 'text-brand-warning' : 'text-brand-text'}`}>
                {Math.abs(pitch).toFixed(2)}° {pitch > 0 ? 'AFT' : pitch < 0 ? 'FWD' : 'EVEN'}
              </span>
            </div>
          </div>

          {/* Top-Right: Cargo & Ballast Summary Overlay HUD */}
          <div className="absolute top-4 right-4 z-10 surface-elevated backdrop-blur-xl p-3.5 rounded-2xl border border-brand-borderSubtle text-xs font-mono space-y-1.5 shadow-2xl max-w-[210px] pointer-events-none">
            <div className="flex items-center justify-between pb-1.5 border-b border-brand-borderSubtle text-[10px]">
              <span className="text-brand-muted uppercase font-bold">Vessel Loading</span>
              <span className="text-[8px] font-bold text-brand-cyan">[SOLAS VGM]</span>
            </div>
            <div className="flex justify-between">
              <span className="text-brand-muted">Stowed Cargo:</span>
              <span className="text-brand-text font-bold">{totalCargoT.toFixed(1)} t</span>
            </div>
            <div className="flex justify-between">
              <span className="text-brand-muted">Containers:</span>
              <span className="text-brand-cyan font-bold">{activeContainers.length} Stowed</span>
            </div>
            <div className="flex justify-between">
              <span className="text-brand-muted">Total Ballast:</span>
              <span className="text-brand-text font-bold">{totalBallastT.toFixed(1)} t</span>
            </div>
          </div>

          {/* MAIN VIEWPORT: 3D WebGL vs 2D SCADA */}
          {displayMode === "3D" ? (
            <div className="w-full h-full min-h-[520px] flex-1">
              <Vessel3DCanvas
                containers={activeContainers}
                ballastTanks={tanks}
                roll={roll}
                pitch={pitch}
                viewMode={viewMode}
                selectedContainerId={selectedContainer?.id}
                selectedTankId={selectedTank?.id}
                recommendedSlot={stabilityResult?.recommendation}
                alternativeSlots={stabilityResult?.candidate_evaluations || stabilityResult?.candidates || []}
                onSelectContainer={(c) => setSelectedContainer(c)}
                onSelectTank={(t) => setSelectedTank(t)}
              />
            </div>
          ) : (
            /* 2D 4-Bay Schematic Cross Section */
            <div 
              className="w-full max-w-4xl p-6 transition-transform duration-300 flex flex-col items-center space-y-4"
              style={{ transform: `scale(${zoomLevel / 100})` }}
            >
              <div className="w-full surface-elevated rounded-2xl border border-brand-borderSubtle p-5 shadow-2xl relative backdrop-blur-xl">
                <div className="flex items-center justify-between text-[10px] font-mono text-brand-muted uppercase font-bold pb-2.5 border-b border-brand-borderSubtle">
                  <span className="flex items-center gap-1.5 text-brand-cyan">
                    <Anchor className="w-3.5 h-3.5" /> BOW (FORWARD - BAY 1)
                  </span>
                  <span>4-BAY CELLULAR CARGO HOLD & BALLAST DOUBLE BOTTOM</span>
                  <span>STERN (AFT - BAY 4)</span>
                </div>

                <div className="grid grid-cols-4 gap-3 py-4">
                  {[1, 2, 3, 4].map(bayNum => {
                    const bayContainers = activeContainers.filter(c => c.bay === bayNum);

                    return (
                      <div key={bayNum} className="space-y-2">
                        <div className="text-center font-mono font-black text-xs text-brand-cyan uppercase tracking-wider pb-1 border-b border-brand-borderSubtle">
                          BAY 0{bayNum}
                        </div>

                        <div className="surface-base p-2.5 rounded-xl border border-brand-borderSubtle space-y-1.5">
                          {/* Tier 2 */}
                          <div className="grid grid-cols-2 gap-1.5">
                            {["PORT", "STARBOARD"].map(side => {
                              const c = bayContainers.find(item => item.side?.toUpperCase() === side && item.tier === 2);
                              const isSelected = selectedContainer?.id === c?.id;
                              return (
                                <button
                                  key={side}
                                  onClick={() => {
                                    if (c) {
                                      setSelectedContainer({
                                        id: c.id,
                                        bay: bayNum,
                                        side: side as "PORT" | "STARBOARD",
                                        tier: 2,
                                        weight: c.weight,
                                        container_type: c.container_type || "40HC",
                                        hazardous: c.hazardous
                                      });
                                      setSelectedTank(null);
                                    }
                                  }}
                                  className={`h-12 p-1.5 rounded-lg border text-[9px] font-mono font-bold flex flex-col justify-between transition-all ${
                                    c 
                                      ? isSelected
                                        ? "bg-brand-cyan text-slate-950 border-brand-cyan ring-2 ring-brand-cyan font-black"
                                        : c.isProjected
                                        ? "bg-brand-cyanBg border-brand-cyan text-brand-cyan animate-pulse"
                                        : "surface-elevated text-brand-text border-brand-borderSubtle hover:border-brand-cyan/50"
                                      : "surface-base/40 border-brand-borderSubtle/50 text-brand-muted/40 border-dashed"
                                  }`}
                                >
                                  <span>{side === "PORT" ? "T2-P" : "T2-S"}</span>
                                  {c && <span className="truncate">{c.weight.toFixed(1)}t</span>}
                                </button>
                              );
                            })}
                          </div>

                          {/* Tier 1 */}
                          <div className="grid grid-cols-2 gap-1.5">
                            {["PORT", "STARBOARD"].map(side => {
                              const c = bayContainers.find(item => item.side?.toUpperCase() === side && item.tier === 1);
                              const isSelected = selectedContainer?.id === c?.id;
                              return (
                                <button
                                  key={side}
                                  onClick={() => {
                                    if (c) {
                                      setSelectedContainer({
                                        id: c.id,
                                        bay: bayNum,
                                        side: side as "PORT" | "STARBOARD",
                                        tier: 1,
                                        weight: c.weight,
                                        container_type: c.container_type || "40HC",
                                        hazardous: c.hazardous
                                      });
                                      setSelectedTank(null);
                                    }
                                  }}
                                  className={`h-12 p-1.5 rounded-lg border text-[9px] font-mono font-bold flex flex-col justify-between transition-all ${
                                    c 
                                      ? isSelected
                                        ? "bg-brand-cyan text-slate-950 border-brand-cyan ring-2 ring-brand-cyan font-black"
                                        : c.isProjected
                                        ? "bg-brand-cyanBg border-brand-cyan text-brand-cyan animate-pulse"
                                        : "surface-elevated text-brand-text border-brand-borderSubtle hover:border-brand-cyan/50"
                                      : "surface-base/40 border-brand-borderSubtle/50 text-brand-muted/40 border-dashed"
                                  }`}
                                >
                                  <span>{side === "PORT" ? "T1-P" : "T1-S"}</span>
                                  {c && <span className="truncate">{c.weight.toFixed(1)}t</span>}
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* Double Bottom Ballast Tanks */}
                        <div className="grid grid-cols-2 gap-1.5 pt-1">
                          {["port", "starboard"].map(side => {
                            const tankKey = `${side}_${bayNum}`;
                            const t = tanks[tankKey] || { current_volume: 10.5, capacity: 15 };
                            const pct = t.capacity ? (t.current_volume / t.capacity) * 100 : 70;
                            const isTankSelected = selectedTank?.id === tankKey;

                            return (
                              <button
                                key={side}
                                onClick={() => {
                                  setSelectedTank({
                                    id: tankKey,
                                    name: `${side === "port" ? "Port" : "Starboard"} Tank ${bayNum}`,
                                    side: side.toUpperCase() as "PORT" | "STARBOARD",
                                    bay: bayNum,
                                    location: `Bay 0${bayNum} ${side === "port" ? "Port" : "Starboard"} Wing`,
                                    current_volume: t.current_volume || 0,
                                    capacity: t.capacity || 15,
                                    percentage: pct,
                                    status: "NORMAL"
                                  });
                                  setSelectedContainer(null);
                                }}
                                className={`p-2 rounded-lg border text-[8px] font-mono font-bold flex flex-col justify-between transition-all ${
                                  isTankSelected 
                                    ? "bg-brand-cyan text-slate-950 border-brand-cyan ring-2 ring-brand-cyan font-black"
                                    : "surface-base text-brand-cyan border-brand-cyan/30 hover:border-brand-cyan"
                                }`}
                              >
                                <span>{side === "port" ? `PT ${bayNum}` : `ST ${bayNum}`}</span>
                                <div className="w-full surface-base h-1.5 rounded-full overflow-hidden mt-1">
                                  <div 
                                    className="h-full bg-brand-cyan transition-all duration-300"
                                    style={{ width: `${Math.min(pct, 100)}%` }}
                                  />
                                </div>
                                <span className="mt-0.5">{(t.current_volume || 0).toFixed(1)}t</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Bottom-Left: Interactive Object Inspector Side-Sheet */}
          {(selectedContainer || selectedTank) && (
            <div className="absolute bottom-5 left-5 z-10 surface-elevated backdrop-blur-2xl p-4 rounded-2xl border border-brand-cyan/50 text-xs font-mono shadow-2xl space-y-2.5 max-w-xs animate-in slide-in-from-bottom duration-200">
              {selectedContainer ? (
                <>
                  <div className="flex items-center justify-between border-b border-brand-borderSubtle pb-1.5">
                    <span className="text-[10px] text-brand-cyan uppercase font-black flex items-center gap-1.5">
                      <Box className="w-3.5 h-3.5" /> Container Inspector
                    </span>
                    <button 
                      onClick={() => setSelectedContainer(null)}
                      className="text-brand-muted hover:text-brand-text p-1 rounded-md hover:surface-base transition-colors"
                      title="Close"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="space-y-1">
                    <div className="text-sm font-black text-brand-text">{selectedContainer.id}</div>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-brand-muted">Slot:</span>
                      <span className="text-brand-cyan font-bold">Bay {selectedContainer.bay} • {selectedContainer.side} • Tier {selectedContainer.tier}</span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-brand-muted">Mass:</span>
                      <span className="text-brand-safe font-bold">{selectedContainer.weight.toFixed(1)} t [SOLAS VGM]</span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-brand-muted">Type:</span>
                      <span className="text-brand-text">{selectedContainer.container_type}</span>
                    </div>
                    {selectedContainer.hazardous && (
                      <div className="text-[10px] text-brand-warning font-bold flex items-center gap-1 mt-1">
                        <Flame className="w-3 h-3" /> IMDG DG Dangerous Goods
                      </div>
                    )}
                  </div>
                </>
              ) : selectedTank ? (
                <>
                  <div className="flex items-center justify-between border-b border-brand-borderSubtle pb-1.5">
                    <span className="text-[10px] text-brand-cyan uppercase font-black flex items-center gap-1.5">
                      <Droplets className="w-3.5 h-3.5" /> Ballast Tank Inspector
                    </span>
                    <button 
                      onClick={() => setSelectedTank(null)}
                      className="text-brand-muted hover:text-brand-text p-1 rounded-md hover:surface-base transition-colors"
                      title="Close"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="space-y-1">
                    <div className="text-sm font-black text-brand-text">{selectedTank.name}</div>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-brand-muted">Location:</span>
                      <span className="text-brand-cyan font-bold">{selectedTank.location}</span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-brand-muted">Volume:</span>
                      <span className="text-brand-text font-bold">{selectedTank.current_volume.toFixed(1)} / {selectedTank.capacity.toFixed(1)} t</span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-brand-muted">Fill Level:</span>
                      <span className="text-brand-safe font-bold">{selectedTank.percentage.toFixed(0)}%</span>
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          )}
        </div>
      </div>

      {/* 3. Collapsible Ballast Pump Controls Matrix */}
      {showBallastMatrix && (
        <div className="surface-elevated border border-brand-borderSubtle rounded-2xl p-5 space-y-4 shadow-sm">
          <SectionHeader
            title="Manual Ballast Pump & Valve Manifold Matrix"
            icon={Droplets}
            actions={
              <button
                onClick={() => setShowBallastMatrix(false)}
                className="text-[10px] font-mono text-brand-muted hover:text-brand-text px-2 py-1 surface-base rounded-lg border border-brand-borderSubtle"
              >
                Close Matrix
              </button>
            }
          />
          <BallastControlTable tanks={tanks} onAdjustComplete={() => {}} />
        </div>
      )}
    </div>
  );
};

