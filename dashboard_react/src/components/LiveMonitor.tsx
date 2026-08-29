import React, { useState, useEffect } from "react";
import { useSocket } from "../context/SocketContext";
import { vesselAPI, advisoryAPI, telemetryAPI } from "../utils/api";
import { Radio, AlertTriangle, ArrowRight, Play, CheckCircle2, RefreshCw, Layers } from "lucide-react";

export const LiveMonitor: React.FC = () => {
  const { connected, vesselState } = useSocket();
  const [containerId, setContainerId] = useState("");
  const [targetBay, setTargetBay] = useState(1);
  const [targetSide, setTargetSide] = useState("port");
  const [targetTier, setTargetTier] = useState(1);
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<{ best_bay?: number; best_side?: string } | null>(null);

  // Simulation Overrides States
  const [simCargo, setSimCargo] = useState(0.0);
  const [rollVal, setRollVal] = useState(0.0);
  const [pitchVal, setPitchVal] = useState(0.0);
  const [manualOverride, setManualOverride] = useState(false);

  // Poll recommendations once when entering the placing cargo stage
  useEffect(() => {
    if (vesselState?.iot_flow_stage === "PLACING_CARGO") {
      // Pre-fill fields with AI recommendation
      if (vesselState.active_rec_bay) setTargetBay(vesselState.active_rec_bay);
      if (vesselState.active_rec_side) setTargetSide(vesselState.active_rec_side);
      setContainerId(`IOT-${Math.floor(Date.now() / 1000) % 1000}`);
    }
  }, [vesselState?.iot_flow_stage]);

  // Keep simulator values synchronized in real-time
  useEffect(() => {
    if (vesselState && !manualOverride) {
      setRollVal(vesselState.roll);
      setPitchVal(vesselState.pitch);
    }
    if (vesselState) {
      setSimCargo(vesselState.cargo_t);
    }
  }, [vesselState, manualOverride]);

  const handleTiltOverrideToggle = async (checked: boolean) => {
    setManualOverride(checked);
    try {
      if (!checked) {
        await telemetryAPI.simulateTilt(null, null);
      } else {
        await telemetryAPI.simulateTilt(rollVal, pitchVal);
      }
    } catch (err) {
      console.error("Error setting tilt override:", err);
    }
  };

  if (!vesselState) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-brand-dark p-8">
        <RefreshCw className="w-12 h-12 text-brand-accent animate-spin mb-4" />
        <p className="text-sm text-brand-muted font-bold animate-pulse">Initializing loading interface...</p>
      </div>
    );
  }

  const {
    roll,
    pitch,
    distance,
    ballast_pct,
    cargo_kg,
    cargo_t,
    status,
    is_simulated,
    iot_flow_stage,
    planned_container,
    stability_risk,
    containers,
    active_rec_bay,
    active_rec_side
  } = vesselState;

  const tankCapacity = 300.0;
  const alreadyLoadedWeight = (containers || [])
    .filter((c: any) => c.bay === targetBay && c.side.toLowerCase() === targetSide.toLowerCase())
    .reduce((sum: number, c: any) => sum + c.weight, 0);
  const remainingCapacity = tankCapacity - alreadyLoadedWeight;
  const isNoSpace = (status === "NO SPACE" || cargo_t > remainingCapacity || (active_rec_bay === null && cargo_t >= 0.1)) && 
                    (iot_flow_stage === "WAITING_FOR_CARGO" || iot_flow_stage === "PLACING_CARGO" || iot_flow_stage === "CONFIRM_COMPENSATION");

  const handleCalculateCompensation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!containerId.trim()) return alert("Container ID cannot be empty");
    setLoading(true);
    try {
      await vesselAPI.calculateCompensation(containerId.trim(), targetBay, targetSide, targetTier);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmDrain = async () => {
    setLoading(true);
    try {
      await vesselAPI.confirmDrain();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleClearScale = async () => {
    setLoading(true);
    try {
      await vesselAPI.clearScale();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Render Step 1 Form (Placing Cargo)
  const renderPlacingCargoForm = () => (
    <form onSubmit={handleCalculateCompensation} className="space-y-4">
      <h3 className="text-sm font-bold uppercase tracking-wider text-brand-text mb-2">Step 1: Enter Container Details</h3>
      
      <div>
        <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Container ID Name</label>
        <input 
          type="text" 
          value={containerId}
          onChange={(e) => setContainerId(e.target.value)}
          className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-sm text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
          placeholder="e.g. IOT-452"
        />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Target Bay</label>
          <input 
            type="number" 
            min={1} 
            max={4}
            value={targetBay}
            onChange={(e) => setTargetBay(parseInt(e.target.value))}
            className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-sm text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
          />
        </div>
        <div>
          <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Target Side</label>
          <select 
            value={targetSide}
            onChange={(e) => setTargetSide(e.target.value)}
            className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-sm text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
          >
            <option value="port">Port</option>
            <option value="starboard">Starboard</option>
          </select>
        </div>
        <div>
          <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Target Tier</label>
          <input 
            type="number" 
            min={1} 
            max={6}
            value={targetTier}
            onChange={(e) => setTargetTier(parseInt(e.target.value))}
            className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-sm text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2.5 bg-brand-accent hover:bg-brand-accent/90 disabled:opacity-50 text-slate-950 font-black text-sm uppercase rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <span>Calculate Ballast Compensation</span>
        <ArrowRight className="w-4 h-4" />
      </button>
    </form>
  );

  // Render Step 2 Confirmation (Confirm Compensation)
  const renderConfirmCompensation = () => {
    const planned = planned_container || {};
    const tankKey = `${planned.side}_${planned.bay}`;
    const targetVolume = planned.weight || 0.0;
    
    // Proportional calculation
    const flowRate = 0.85; // L/s model scale estimation
    const estDuration = cargo_kg / flowRate;

    return (
      <div className="space-y-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-brand-text mb-2">Step 2: Ballast Pumping Confirmation</h3>
        
        <div className="space-y-2 bg-slate-950/40 p-4 border border-brand-border rounded-lg text-xs leading-relaxed font-semibold">
          <div className="flex justify-between">
            <span className="text-brand-muted uppercase tracking-wider text-[10px]">Target Compensation Tank</span>
            <span className="text-brand-text uppercase">{planned.side}-Tank-{planned.bay}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-brand-muted uppercase tracking-wider text-[10px]">Water to Pump Out</span>
            <span className="text-brand-danger">-{targetVolume.toFixed(1)} t (proportional)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-brand-muted uppercase tracking-wider text-[10px]">Est. Discharge Rate</span>
            <span className="text-brand-text">{flowRate.toFixed(2)} L/s (scale)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-brand-muted uppercase tracking-wider text-[10px]">Est. Pump Out Duration</span>
            <span className="text-brand-text">{estDuration.toFixed(1)} seconds</span>
          </div>
        </div>

        <div className="flex gap-4">
          <button
            onClick={handleConfirmDrain}
            disabled={loading}
            className="flex-1 py-2.5 bg-brand-accent hover:bg-brand-accent/90 disabled:opacity-50 text-slate-950 font-black text-sm uppercase rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4 fill-slate-950" />
            <span>Confirm & Open Gate</span>
          </button>
          <button
            onClick={handleClearScale}
            disabled={loading}
            className="flex-1 py-2.5 bg-brand-dangerBg text-brand-danger hover:bg-brand-danger/20 disabled:opacity-50 font-black text-sm uppercase rounded-lg border border-brand-danger/30 transition-colors"
          >
            <span>Cancel</span>
          </button>
        </div>
      </div>
    );
  };

  // Render Step 3 (Draining)
  const renderDraining = () => (
    <div className="space-y-4">
      <div className="bg-brand-dangerBg border border-brand-danger/20 text-brand-danger p-4 rounded-lg flex items-start gap-3">
        <AlertTriangle className="w-6 h-6 flex-shrink-0 animate-bounce" />
        <div>
          <h4 className="font-bold text-xs">DANGER: BALLAST DRAIN VALVE OPEN</h4>
          <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
            Pumping out ballast water from <strong className="text-brand-text uppercase">{planned_container.side}-TANK-{planned_container.bay}</strong> to offset cargo load of <strong>{planned_container.weight?.toFixed(1)}t</strong>.
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-xs font-semibold">
          <span className="text-brand-muted">Pumping Progress</span>
          <span className="text-brand-text">{ballast_pct.toFixed(0)}% Left</span>
        </div>
        <div className="w-full bg-slate-950 rounded-full h-3.5 border border-brand-border p-[1px]">
          <div 
            style={{ width: `${ballast_pct}%` }}
            className="bg-brand-danger h-full rounded-full transition-all duration-300"
          />
        </div>
        <span className="block text-[10px] text-brand-muted italic font-bold">
          Sensor distance: {distance.toFixed(1)} cm
        </span>
      </div>
    </div>
  );

  // Render Step 4 (Completed)
  const renderCompleted = () => (
    <div className="space-y-4">
      <div className="bg-emerald-500/10 border border-emerald-500/20 text-brand-accent p-4 rounded-lg flex items-start gap-3">
        <CheckCircle2 className="w-6 h-6 flex-shrink-0 text-brand-accent" />
        <div>
          <h4 className="font-bold text-xs uppercase tracking-wide">Loading Completed Successfully!</h4>
          <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
            Container <strong className="text-brand-text">{planned_container.id}</strong> ({planned_container.weight?.toFixed(1)}t) has been stowed at <strong className="text-brand-text uppercase">Bay {planned_container.bay} / {planned_container.side} / Tier {planned_container.tier}</strong>. Ballast water successfully compensated.
          </p>
        </div>
      </div>

      <button
        onClick={handleClearScale}
        disabled={loading}
        className="w-full py-2.5 bg-brand-accent hover:bg-brand-accent/90 disabled:opacity-50 text-slate-950 font-black text-sm uppercase rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <RefreshCw className="w-4 h-4" />
        <span>Clear Scale to Load Next</span>
      </button>
    </div>
  );

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Live Telemetry Stowage Flow</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Stowage sequence automation controlled by scale sensor integration.</p>
        </div>
      </div>

      {/* Grid: Telemetry parameters on left, flow card on right */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Side: Telemetry status values */}
        <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
          <h3 className="text-xs text-brand-muted font-bold uppercase tracking-wider pb-2 border-b border-brand-border">Telemetry Sensors Readings</h3>
          
          <div className="grid grid-cols-2 gap-3 text-xs leading-none">
            <div className="bg-brand-app border border-brand-border p-3.5 rounded-xl flex flex-col gap-2 shadow-sm">
              <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider">Roll (Heel)</span>
              <span className="text-sm font-black tracking-tight text-brand-text">{roll.toFixed(2)}°</span>
            </div>
            <div className="bg-brand-app border border-brand-border p-3.5 rounded-xl flex flex-col gap-2 shadow-sm">
              <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider">Pitch (Trim)</span>
              <span className="text-sm font-black tracking-tight text-brand-text">{pitch.toFixed(2)}°</span>
            </div>
            <div className="bg-brand-app border border-brand-border p-3.5 rounded-xl flex flex-col gap-2 shadow-sm">
              <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider">Scale Weight</span>
              <span className="text-sm font-black tracking-tight text-brand-text">{cargo_t.toFixed(1)} t</span>
              <span className="text-[9px] text-brand-muted font-semibold">({cargo_kg.toFixed(2)} kg)</span>
            </div>
            <div className="bg-brand-app border border-brand-border p-3.5 rounded-xl flex flex-col gap-2 shadow-sm">
              <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider">Ballast Level</span>
              <span className="text-sm font-black tracking-tight text-brand-text">{ballast_pct.toFixed(1)}%</span>
              <span className="text-[9px] text-brand-muted font-semibold">({distance.toFixed(1)} cm)</span>
            </div>
          </div>

          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex justify-between items-center text-xs shadow-sm">
            <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Stability Risk Level</span>
            <span className={`font-black uppercase ${stability_risk === "SAFE" ? "text-brand-accent" : "text-brand-danger"}`}>{stability_risk}</span>
          </div>

          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex justify-between items-center text-xs shadow-sm">
            <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Scale Connection</span>
            <span className="font-black text-brand-accent uppercase">{status}</span>
          </div>
        </div>

        {/* Right Side: Flow card */}
        <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-brand-border pb-3">
            <div className="flex items-center gap-2">
              <Radio className="text-brand-accent w-4 h-4 animate-pulse" />
              <h3 className="font-extrabold text-xs text-brand-text tracking-wider uppercase">Loading state machine</h3>
            </div>
            <span className="text-[10px] bg-brand-accentBg text-brand-accent border border-brand-accent/20 px-2 py-0.5 rounded font-black tracking-wider uppercase">
              {iot_flow_stage}
            </span>
          </div>

          {/* Conditional rendering based on stage */}
          {isNoSpace && (
            <div className="bg-brand-dangerBg border border-brand-danger/20 text-brand-danger p-4 rounded-lg flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-brand-danger" />
              <div>
                <h4 className="font-bold text-xs uppercase tracking-wider">NO SPACE</h4>
                <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
                  Ballast compensation capacity is fully utilized (Maximum weight to handle is attained).
                  Target slot: <strong className="text-brand-text uppercase">{targetSide}-Tank-{targetBay}</strong>. 
                  Currently loaded in this bay: <strong>{alreadyLoadedWeight.toFixed(1)}t</strong>. 
                  Remaining capacity: <strong>{remainingCapacity.toFixed(1)}t</strong>.
                </p>
              </div>
            </div>
          )}

          {!isNoSpace && iot_flow_stage === "WAITING_FOR_CARGO" && (
            <div className="py-8 text-center flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-8 h-8 text-brand-muted animate-spin" />
              <p className="text-xs text-brand-muted font-bold leading-relaxed max-w-xs">
                📥 <strong>STATUS: WAITING FOR CARGO</strong> — Place a physical container on the sensor scale to begin loading sequence.
              </p>
            </div>
          )}

          {!isNoSpace && iot_flow_stage === "PLACING_CARGO" && renderPlacingCargoForm()}

          {!isNoSpace && iot_flow_stage === "CONFIRM_COMPENSATION" && renderConfirmCompensation()}

          {!isNoSpace && iot_flow_stage === "DRAINING" && renderDraining()}

          {iot_flow_stage === "COMPLETED" && renderCompleted()}
        </div>
      </div>

      {/* Simulator Override Controls */}
      {is_simulated && (
        <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4 mt-6">
          <div className="flex items-center justify-between border-b border-brand-border pb-3">
            <h3 className="font-extrabold text-xs text-brand-text tracking-wider uppercase">Simulator Control Dashboard (Manual Overrides)</h3>
            <span className="text-[10px] bg-brand-accentBg text-brand-accent border border-brand-accent/20 px-2 py-0.5 rounded font-black tracking-wider uppercase">SIMULATOR ACTIVE</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs font-semibold">
            {/* Cargo slider */}
            <div className="flex flex-col gap-2">
              <div className="flex justify-between">
                <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Simulated Cargo Weight</span>
                <span className="text-brand-accent">{simCargo.toFixed(1)} t</span>
              </div>
              <input 
                type="range"
                min="0.0"
                max="300.0"
                step="5.0"
                value={simCargo}
                onChange={async (e) => {
                  const val = parseFloat(e.target.value);
                  setSimCargo(val);
                  try {
                    await telemetryAPI.simulateCargo(val);
                  } catch (err) {}
                }}
                className="accent-brand-accent w-full cursor-pointer h-1 bg-slate-950 rounded-lg appearance-none"
              />
              <span className="text-[9px] text-brand-muted">Corresponds to physical scale weight of {(simCargo / 10.0).toFixed(2)} kg.</span>
            </div>

            {/* Checkbox override */}
            <div className="flex flex-col justify-center gap-2">
              <label className="flex items-center gap-2.5 cursor-pointer text-brand-text text-xs uppercase font-bold tracking-wider">
                <input 
                  type="checkbox"
                  checked={manualOverride}
                  onChange={(e) => handleTiltOverrideToggle(e.target.checked)}
                  className="accent-brand-accent w-4 h-4 rounded"
                />
                <span>Enable Manual Tilt Override</span>
              </label>
              <span className="text-[9px] text-brand-muted">Overrides live physics inclinometers to test extreme list and trim margins.</span>
            </div>

            {/* Roll & Pitch sliders */}
            <div className="flex flex-col gap-4">
              {/* Roll Slider */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Simulated Roll</span>
                  <span className="text-brand-text">{rollVal.toFixed(1)}°</span>
                </div>
                <input 
                  type="range"
                  min="-15.0"
                  max="15.0"
                  step="0.5"
                  disabled={!manualOverride}
                  value={rollVal}
                  onChange={async (e) => {
                    const val = parseFloat(e.target.value);
                    setRollVal(val);
                    try {
                      await telemetryAPI.simulateTilt(val, pitchVal);
                    } catch (err) {}
                  }}
                  className="accent-brand-accent w-full cursor-pointer h-1 bg-slate-950 rounded-lg appearance-none disabled:opacity-40"
                />
              </div>

              {/* Pitch Slider */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Simulated Pitch</span>
                  <span className="text-brand-text">{pitchVal.toFixed(1)}°</span>
                </div>
                <input 
                  type="range"
                  min="-10.0"
                  max="10.0"
                  step="0.5"
                  disabled={!manualOverride}
                  value={pitchVal}
                  onChange={async (e) => {
                    const val = parseFloat(e.target.value);
                    setPitchVal(val);
                    try {
                      await telemetryAPI.simulateTilt(rollVal, val);
                    } catch (err) {}
                  }}
                  className="accent-brand-accent w-full cursor-pointer h-1 bg-slate-950 rounded-lg appearance-none disabled:opacity-40"
                />
              </div>
            </div>
          </div>

          {manualOverride && stability_risk !== "SAFE" && (
            <div className="bg-brand-dangerBg border border-brand-danger/20 text-brand-danger p-3 rounded-lg text-xs leading-relaxed font-bold">
              ⚠️ <strong>MANUAL TILT RISK WARNING</strong> — simulated parameters exceed stability margins! Risk: {stability_risk}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
