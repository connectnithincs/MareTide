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
  FileSpreadsheet,
  Boxes,
  Check
} from "lucide-react";
import { useContainerOperation } from "../context/ContainerOperationContext";
import { SectionHeader } from "./ui/SectionHeader";
import { StatusBadge } from "./ui/StatusBadge";
import { SafetyBadge } from "./ui/SafetyBadge";
import { AlertBanner } from "./ui/AlertBanner";
import { LoadingState } from "./ui/LoadingState";

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

  const totalMassT = manifestItems.reduce(
    (sum, item) => sum + (item.weights.gross_weight_kg / 1000), 
    0
  );

  return (
    <div className="space-y-5">
      {/* 1. Station Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-brand-borderSubtle">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-brand-cyanBg border border-brand-cyan/30 rounded-xl text-brand-cyan shadow-sm shadow-brand-cyan/20">
            <Boxes className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-sm font-mono font-black text-brand-text uppercase tracking-widest">
                BATCH MANIFEST STOWAGE PLANNER (PHASE 4D)
              </h1>
              <SafetyBadge type="CALCULATED" size="sm" />
            </div>
            <p className="text-[11px] text-brand-muted font-medium mt-0.5">
              Multi-objective combinatorial solver: simultaneous loading sequence optimization, transverse moment balancing, and stability maximization.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleLoadSample}
            className="px-3 py-1.5 surface-base hover:bg-brand-hover text-brand-cyan border border-brand-cyan/30 rounded-xl text-[11px] font-mono font-bold uppercase transition-all shadow-sm active:scale-95"
          >
            Load Sample Manifest
          </button>
        </div>
      </div>

      {errorMessage && (
        <AlertBanner
          variant="danger"
          title="Manifest Solver Error"
          message={errorMessage}
        />
      )}

      {/* 2. Top Summary & Action Bar */}
      <div className="surface-elevated border border-brand-borderSubtle rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-4 flex-wrap text-xs font-mono">
          <div className="p-3 surface-base rounded-xl border border-brand-borderSubtle">
            <span className="text-[9.5px] text-brand-muted uppercase font-bold block">Manifest Size</span>
            <span className="text-base font-black text-brand-text">{manifestItems.length} Containers</span>
          </div>
          <div className="p-3 surface-base rounded-xl border border-brand-borderSubtle">
            <span className="text-[9.5px] text-brand-muted uppercase font-bold block">Total Batch Mass</span>
            <span className="text-base font-black text-brand-cyan">{totalMassT.toFixed(1)} tonnes</span>
          </div>
          <div className="p-3 surface-base rounded-xl border border-brand-borderSubtle">
            <span className="text-[9.5px] text-brand-muted uppercase font-bold block">Dangerous Goods</span>
            <span className="text-base font-black text-brand-warning">
              {manifestItems.filter(i => i.cargo.hazardous).length} IMDG DG
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap w-full md:w-auto">
          <button
            onClick={handleAddContainer}
            className="px-3.5 py-2.5 surface-base hover:bg-brand-hover text-brand-text border border-brand-borderSubtle rounded-xl text-xs font-mono font-bold uppercase transition-all flex items-center gap-1.5 shadow-sm active:scale-95"
          >
            <Plus className="w-3.5 h-3.5 text-brand-cyan" />
            <span>Add Container</span>
          </button>

          <button
            onClick={handleOptimizePlan}
            disabled={manifestItems.length === 0 || isPlanningManifest}
            className="px-5 py-2.5 bg-brand-cyan hover:bg-brand-cyan/90 disabled:opacity-50 text-slate-950 rounded-xl text-xs font-mono font-black uppercase tracking-wider transition-all flex items-center gap-2 shadow-md shadow-brand-cyan/20 active:scale-95 cursor-pointer"
          >
            {isPlanningManifest ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>SOLVING OPTIMAL SEQUENCE...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-slate-950" />
                <span>OPTIMIZE STOWAGE SEQUENCE</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* 3. Manifest Ingestion Table & Optimization Plan Output */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: Input Manifest Table (6 cols on LG) */}
        <div className="lg:col-span-6 surface-elevated border border-brand-borderSubtle rounded-2xl p-5 space-y-4 font-mono text-xs shadow-sm">
          <SectionHeader
            title="Ingested Container Manifest Items"
            icon={FileSpreadsheet}
            badge={
              <span className="text-[9px] font-mono px-2 py-0.5 rounded-full surface-base text-brand-muted border border-brand-borderSubtle font-bold">
                {manifestItems.length} Entries
              </span>
            }
          />

          <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
            {manifestItems.map((item, idx) => (
              <div 
                key={idx} 
                className="p-3 surface-base rounded-xl border border-brand-borderSubtle flex items-center justify-between gap-3 hover:border-brand-border transition-colors shadow-sm"
              >
                <div className="min-w-0 flex-1 space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-black text-brand-text text-xs">{item.container_number}</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded surface-base text-brand-cyan border border-brand-borderSubtle">
                      {item.container_type}
                    </span>
                    {item.cargo.hazardous && (
                      <span className="text-[8.5px] px-1.5 py-0.2 rounded bg-brand-warningBg text-brand-warning border border-brand-warning/30 font-bold flex items-center gap-1">
                        <Flame className="w-2.5 h-2.5" /> IMDG
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-brand-muted flex items-center gap-3">
                    <span>Gross: <strong className="text-brand-text">{(item.weights.gross_weight_kg / 1000).toFixed(1)}t</strong></span>
                    <span>Dest: <strong className="text-brand-text truncate">{item.destination}</strong></span>
                  </div>
                </div>

                <button
                  onClick={() => handleRemoveContainer(idx)}
                  className="p-1.5 text-brand-muted hover:text-brand-danger hover:bg-brand-dangerBg rounded-lg transition-colors flex-shrink-0"
                  title="Remove from batch"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Optimized Sequence Plan & Batch Execution (6 cols on LG) */}
        <div className="lg:col-span-6 surface-elevated border border-brand-borderSubtle rounded-2xl p-5 space-y-4 font-mono text-xs shadow-sm">
          <SectionHeader
            title="Optimized Multi-Objective Loading Plan"
            icon={ListOrdered}
            badge={
              manifestPlan ? (
                <StatusBadge status="PLAN GENERATED" size="sm" />
              ) : (
                <span className="text-[9px] font-mono px-2 py-0.5 rounded surface-base text-brand-muted border border-brand-borderSubtle font-bold">
                  AWAITING SOLVER
                </span>
              )
            }
          />

          {!manifestPlan ? (
            <div className="py-16 text-center text-xs font-mono text-brand-muted space-y-2">
              <Boxes className="w-10 h-10 mx-auto text-brand-cyan/40" />
              <p className="font-bold text-brand-text">No batch plan generated yet</p>
              <p className="text-[11px] max-w-xs mx-auto">
                Click "Optimize Stowage Sequence" above to compute the multi-objective Pareto-optimal loading sequence.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Sequence Plan Steps List */}
              <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
                {(manifestPlan.loading_sequence || (manifestPlan as any).plan || []).map((step: any, idx: number) => (
                  <div 
                    key={idx} 
                    className="p-3 surface-base rounded-xl border border-brand-borderSubtle space-y-1.5 shadow-sm"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-brand-cyan text-slate-950 font-black text-[10px] flex items-center justify-center">
                          {idx + 1}
                        </span>
                        <span className="font-black text-brand-text">{step.container_number || step.container_id}</span>
                      </div>
                      <span className="text-[10px] font-bold text-brand-safe bg-brand-safeBg px-2 py-0.5 rounded-full border border-brand-safe/30">
                        Bay {step.bay} • {step.side} • T{step.tier}
                      </span>
                    </div>
                    <div className="text-[10px] text-brand-muted pl-7">
                      Mass: <strong className="text-brand-text">{(step.weight_t || (step.gross_weight_kg ? step.gross_weight_kg / 1000 : 25)).toFixed(1)}t</strong> • Post-Step List: <strong className="text-brand-safe">{step.projected_list_t?.toFixed(1) || "0.0"}t</strong>
                    </div>
                  </div>
                ))}
              </div>

              {/* Batch Sequence Execution Button */}
              <div className="pt-2">
                <button
                  onClick={handleExecuteSequence}
                  disabled={isExecutingManifest}
                  className="w-full py-3 bg-brand-safe hover:bg-brand-safe/90 disabled:opacity-50 text-slate-950 rounded-xl font-mono font-black text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 shadow-lg shadow-brand-safe/25 active:scale-95 cursor-pointer"
                >
                  {isExecutingManifest ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>EXECUTING BATCH MANIFEST SEQUENCE...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4 stroke-[3]" />
                      <span>EXECUTE FULL BATCH SEQUENCE</span>
                    </>
                  )}
                </button>
              </div>

              {executionSuccess && (
                <div className="p-3 bg-brand-safeBg border border-brand-safe/40 rounded-xl flex items-center gap-2 text-brand-safe text-xs font-bold font-mono">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>Batch manifest sequence successfully stowed into 3D vessel digital twin state!</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

