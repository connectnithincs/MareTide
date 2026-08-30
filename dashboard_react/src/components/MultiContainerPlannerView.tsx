import React, { useState } from "react";
import { 
  Layers, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  ShieldCheck, 
  ArrowRight, 
  Anchor, 
  Droplets, 
  RefreshCw, 
  Flame, 
  Box, 
  Scale, 
  ListOrdered,
  Plus,
  Trash2,
  FileSpreadsheet
} from "lucide-react";
import { useContainerOperation, type PlannedContainerStep } from "../context/ContainerOperationContext";

const SAMPLE_MANIFEST = [
  {
    container_number: "MSCU8877112",
    container_type: "40HC",
    weights: { gross_weight_kg: 28000.0, tare_weight_kg: 3800.0, net_weight_kg: 24200.0 },
    cargo: { hazardous: false, cargo_description: "Heavy Industrial Machinery" },
    destination: "ROTTERDAM"
  },
  {
    container_number: "CMAU9922334",
    container_type: "40HC",
    weights: { gross_weight_kg: 24000.0, tare_weight_kg: 3900.0, net_weight_kg: 20100.0 },
    cargo: { hazardous: false, cargo_description: "Automotive Parts" },
    destination: "HAMBURG"
  },
  {
    container_number: "HAZU1122334",
    container_type: "20GP",
    weights: { gross_weight_kg: 18000.0, tare_weight_kg: 2200.0, net_weight_kg: 15800.0 },
    cargo: { hazardous: true, un_number: "UN 1203", imdg_class: "Class 3", cargo_description: "Flammable Liquids" },
    destination: "ANTWERP"
  },
  {
    container_number: "TGHU4455667",
    container_type: "40GP",
    weights: { gross_weight_kg: 15000.0, tare_weight_kg: 3700.0, net_weight_kg: 11300.0 },
    cargo: { hazardous: false, cargo_description: "Consumer Electronics" },
    destination: "SINGAPORE"
  }
];

export const MultiContainerPlannerView: React.FC = () => {
  const {
    manifestPlan,
    isPlanningManifest,
    isExecutingManifest,
    generateManifestPlan,
    executeManifestSequence,
    setManifestPlan,
    errorMessage
  } = useContainerOperation();

  const [manifestItems, setManifestItems] = useState(SAMPLE_MANIFEST);
  const [executionSuccess, setExecutionSuccess] = useState(false);

  const handleLoadSample = () => {
    setManifestItems(SAMPLE_MANIFEST);
    setExecutionSuccess(false);
  };

  const handleAddContainer = () => {
    const newIdx = manifestItems.length + 1;
    const newContainer = {
      container_number: `CONT${String(newIdx).padStart(3, "0")}998`,
      container_type: "40HC",
      weights: { gross_weight_kg: 20000.0, tare_weight_kg: 3800.0, net_weight_kg: 16200.0 },
      cargo: { hazardous: false, cargo_description: "General Cargo" },
      destination: "LE HAVRE"
    };
    setManifestItems([...manifestItems, newContainer]);
  };

  const handleRemoveContainer = (index: number) => {
    setManifestItems(manifestItems.filter((_, i) => i !== index));
  };

  const handleOptimizePlan = async () => {
    setExecutionSuccess(false);
    await generateManifestPlan(manifestItems);
  };

  const handleExecuteSequence = async () => {
    const ok = await executeManifestSequence();
    if (ok) {
      setExecutionSuccess(true);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="bg-brand-card p-5 rounded-2xl border border-brand-border shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20 text-blue-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-wide">Multi-Container Stowage Manifest Planner</h2>
              <p className="text-xs text-gray-400">
                Batch manifest optimization: determines loading sequence, per-step stability progression, and deck allocations.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleLoadSample}
            className="px-3.5 py-2 bg-brand-app/80 hover:bg-brand-app text-gray-300 hover:text-white rounded-xl border border-brand-border text-xs font-semibold flex items-center gap-1.5 transition-all"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400" />
            Sample Manifest (4x)
          </button>
          <button
            onClick={handleAddContainer}
            className="px-3.5 py-2 bg-brand-app/80 hover:bg-brand-app text-gray-300 hover:text-white rounded-xl border border-brand-border text-xs font-semibold flex items-center gap-1.5 transition-all"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            Add Container
          </button>
          <button
            onClick={handleOptimizePlan}
            disabled={isPlanningManifest || manifestItems.length === 0}
            className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white rounded-xl text-xs font-bold uppercase tracking-wider flex items-center gap-2 shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 cursor-pointer"
          >
            {isPlanningManifest ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Optimizing Sequence...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                Optimize Loading Plan
              </>
            )}
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="bg-red-500/10 border border-red-500/30 p-3 rounded-xl text-xs text-red-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Manifest Queue */}
      <div className="bg-brand-card p-5 rounded-2xl border border-brand-border space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListOrdered className="w-4 h-4 text-brand-accent" />
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
              Container Manifest Queue ({manifestItems.length} items)
            </h3>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            Total Mass: {(manifestItems.reduce((acc, c) => acc + (c.weights?.gross_weight_kg || 0), 0) / 1000).toFixed(1)} MT
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {manifestItems.map((item, idx) => (
            <div key={idx} className="bg-brand-app/80 p-3 rounded-xl border border-brand-border space-y-2 relative group">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-black text-white">{item.container_number}</span>
                <button
                  onClick={() => handleRemoveContainer(idx)}
                  className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity p-1"
                  title="Remove container"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-1 text-[11px] font-mono">
                <div className="text-gray-400">Mass: <span className="text-emerald-400 font-bold">{(item.weights.gross_weight_kg / 1000).toFixed(1)}t</span></div>
                <div className="text-gray-400">Type: <span className="text-blue-300">{item.container_type}</span></div>
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-white/5 text-[10px]">
                <span className="text-gray-400 truncate">{item.destination}</span>
                {item.cargo.hazardous ? (
                  <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 font-bold border border-red-500/30 flex items-center gap-1">
                    <Flame className="w-3 h-3 text-red-400" />
                    HAZMAT
                  </span>
                ) : (
                  <span className="px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400 font-bold">
                    STANDARD
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Optimized Loading Plan Section */}
      {manifestPlan && (
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-blue-950/40 via-brand-card to-cyan-950/40 p-6 rounded-2xl border border-cyan-500/30 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-brand-border/60">
              <div>
                <span className="px-2.5 py-1 rounded bg-cyan-500/20 text-cyan-300 font-black text-[10px] uppercase tracking-wider border border-cyan-500/30">
                  OPTIMIZED LOADING PLAN GENERATED
                </span>
                <h3 className="text-lg font-bold text-white mt-1.5">
                  Sequential Stowage Execution Plan ({manifestPlan.valid_count} Valid / {manifestPlan.total_containers} Total)
                </h3>
              </div>

              <div className="flex items-center gap-4 text-xs font-mono">
                <div className="bg-brand-app/80 p-2.5 rounded-xl border border-brand-border">
                  <span className="text-gray-400 block text-[10px]">Initial Stability:</span>
                  <span className="text-white font-bold">{manifestPlan.initial_stability?.stability_score.toFixed(1)} pts</span>
                </div>
                <div className="bg-brand-app/80 p-2.5 rounded-xl border border-brand-border">
                  <span className="text-gray-400 block text-[10px]">Final Projected:</span>
                  <span className="text-emerald-400 font-bold">{manifestPlan.final_stability?.stability_score.toFixed(1)} pts</span>
                </div>
              </div>
            </div>

            {/* Stability Progression Stepper */}
            <div className="space-y-2">
              <span className="text-xs font-bold text-gray-300 uppercase tracking-wider block">
                Hydrostatic Stability Progression Timeline
              </span>
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {manifestPlan.stability_progression.map((stage, idx) => (
                  <React.Fragment key={idx}>
                    <div className={`p-3 rounded-xl border shrink-0 min-w-[130px] ${
                      idx === 0 
                        ? "bg-gray-800/60 border-gray-700" 
                        : "bg-brand-app/90 border-brand-border"
                    }`}>
                      <span className="text-[10px] text-gray-400 font-bold block uppercase">{stage.label}</span>
                      <div className="font-mono text-sm font-black text-white mt-0.5">
                        {stage.metrics.stability_score.toFixed(1)} <span className="text-[10px] text-gray-400">pts</span>
                      </div>
                      <div className="text-[10px] text-gray-400 font-mono mt-1">
                        List: {stage.metrics.list_t.toFixed(1)}t | Trim: {stage.metrics.trim_t.toFixed(1)}t
                      </div>
                    </div>
                    {idx < manifestPlan.stability_progression.length - 1 && (
                      <ArrowRight className="w-4 h-4 text-cyan-400 shrink-0" />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* Step-by-Step Loading Sequence */}
            <div className="space-y-3">
              <span className="text-xs font-bold text-gray-300 uppercase tracking-wider block">
                Stowage Sequence Steps
              </span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {manifestPlan.loading_sequence.map((step) => (
                  <div key={step.step_number} className="bg-brand-app/90 p-4 rounded-xl border border-brand-border/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-cyan-500/20 text-cyan-300 flex items-center justify-center text-xs font-black border border-cyan-500/30">
                          {step.step_number}
                        </span>
                        <span className="font-mono font-bold text-white text-sm">
                          {step.container.container_number}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-[10px] border border-emerald-500/30">
                        {step.status}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 bg-black/30 p-2.5 rounded-lg text-xs font-mono border border-white/5">
                      <div>
                        <span className="text-gray-400 text-[10px] block">Position:</span>
                        <span className="text-cyan-300 font-bold">
                          Bay {step.recommended_position?.bay} / {step.recommended_position?.side} / T{step.recommended_position?.tier}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-400 text-[10px] block">Gross Weight:</span>
                        <span className="text-emerald-400 font-bold">{step.container.gross_weight_t}t</span>
                      </div>
                      <div>
                        <span className="text-gray-400 text-[10px] block">Post Stability:</span>
                        <span className="text-white font-bold">{step.stability_after?.stability_score.toFixed(1)} pts</span>
                      </div>
                    </div>

                    {step.ballast_required && (
                      <div className="bg-amber-500/10 p-2 rounded text-[11px] text-amber-300 border border-amber-500/20 flex items-center gap-1.5">
                        <Droplets className="w-3.5 h-3.5 text-amber-400" />
                        <span>Ballast compensation recommended after this placement.</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Rejected / Review Required Items */}
            {manifestPlan.rejected_containers.length > 0 && (
              <div className="bg-red-500/10 p-4 rounded-xl border border-red-500/30 space-y-2">
                <div className="flex items-center gap-2 text-red-300 text-xs font-bold uppercase">
                  <XCircle className="w-4 h-4 text-red-400" />
                  <span>Isolated Manifest Items ({manifestPlan.rejected_containers.length})</span>
                </div>
                <div className="space-y-1.5">
                  {manifestPlan.rejected_containers.map((rej, idx) => (
                    <div key={idx} className="bg-black/30 p-2.5 rounded-lg text-xs font-mono flex items-center justify-between">
                      <span className="text-white font-bold">{rej.container_number}</span>
                      <span className="text-red-300">{rej.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action Bar */}
            <div className="pt-4 border-t border-brand-border/60 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="text-xs text-gray-400 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-brand-accent" />
                <span>
                  {executionSuccess 
                    ? "Sequence successfully executed and committed to live vessel state." 
                    : "Plan validated. Operator authorization required to commit sequence to live vessel."}
                </span>
              </div>

              <button
                onClick={handleExecuteSequence}
                disabled={isExecutingManifest || executionSuccess || manifestPlan.loading_sequence.length === 0}
                className={`px-6 py-3 text-white font-black text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg flex items-center justify-center gap-2 ${
                  executionSuccess
                    ? "bg-emerald-700/60 opacity-80 cursor-not-allowed border border-emerald-500/40 text-emerald-200"
                    : "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-600/30 cursor-pointer"
                }`}
              >
                {isExecutingManifest ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Executing Sequence...
                  </>
                ) : executionSuccess ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-300" />
                    Sequence Committed to Live State
                  </>
                ) : (
                  <>
                    <Anchor className="w-4 h-4" />
                    Confirm & Execute Loading Sequence
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
