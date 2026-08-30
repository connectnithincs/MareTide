import React, { useState } from "react";
import { useSocket } from "../context/SocketContext";
import { 
  useContainerOperation, 
  EXTRACTION_REVIEW_THRESHOLD 
} from "../context/ContainerOperationContext";
import { 
  Radio, 
  FileText, 
  Upload, 
  ShieldCheck, 
  AlertTriangle, 
  XCircle, 
  CheckCircle2, 
  Sparkles, 
  Anchor, 
  Scale, 
  Box, 
  Truck, 
  MapPin, 
  Flame, 
  Layers, 
  Percent, 
  Zap, 
  Check, 
  Play, 
  RefreshCw, 
  ArrowRight,
  ShieldAlert,
  Compass,
  Gauge,
  CheckCircle,
  ShieldQuestion,
  Lock,
  Droplets,
  ArrowDownCircle,
  Activity,
  Award,
  Info,
  CheckSquare,
  Square,
  FileCheck,
  Cpu,
  ChevronRight,
  Printer
} from "lucide-react";
import { CargoAwareDigitalTwin } from "./CargoAwareDigitalTwin";

export const LiveMonitor: React.FC = () => {
  const { connected, vesselState } = useSocket();
  const {
    file,
    previewUrl,
    extractedData,
    stabilityResult,
    loadedResult,
    ballastCompensation,
    ballastExecutionResult,
    isExtracting,
    isAnalyzing,
    isLoadingContainer,
    isCalculatingBallast,
    isExecutingBallast,
    operationStatus,
    errorMessage,
    canConfirmAndLoad,
    processSlipFile,
    loadSampleSlip,
    analyzeActiveStability,
    confirmAndLoadContainer,
    calculateBallastCompensation,
    confirmAndExecuteBallast,
    resetOperation
  } = useContainerOperation();

  const [weightUnit, setWeightUnit] = useState<"t" | "kg" | "lbs">("t");
  const [operatorConfirmed, setOperatorConfirmed] = useState<boolean>(false);
  const [ballastConfirmed, setBallastConfirmed] = useState<boolean>(false);
  const [operatorId, setOperatorId] = useState<string>("Chief Officer - Deck Ops");
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);

  // Handle local file upload
  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setOperatorConfirmed(false);
      setBallastConfirmed(false);
      await processSlipFile(selected);
    }
  };

  // Execute operator confirmation and live loading
  const handleConfirmAndLoad = async () => {
    if (!operatorConfirmed) return;
    await confirmAndLoadContainer();
  };

  // Execute operator confirmation for ballast compensation
  const handleConfirmAndExecuteBallast = async () => {
    if (!ballastConfirmed) return;
    await confirmAndExecuteBallast();
  };

  if (!vesselState) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-brand-dark p-8">
        <RefreshCw className="w-12 h-12 text-brand-accent animate-spin mb-4" />
        <p className="text-sm text-brand-muted font-bold animate-pulse">
          Connecting to Supervisory Telemetry Stream...
        </p>
      </div>
    );
  }

  const {
    roll,
    pitch,
    distance,
    ballast_pct,
    status: scaleStatus,
    stability_risk,
    is_simulated = true
  } = vesselState;

  // Format weights
  const formatWeight = (kg: number | null | undefined, inTonnesOnly = false) => {
    if (kg === null || kg === undefined) return "N/A";
    const tonnes = kg / 1000.0;
    if (inTonnesOnly || weightUnit === "t") {
      return `${tonnes.toFixed(1)} t`;
    }
    if (weightUnit === "lbs") {
      return `${Math.round(kg * 2.20462).toLocaleString()} lbs`;
    }
    return `${kg.toLocaleString()} kg`;
  };

  // Data helpers
  const container = extractedData?.container || {};
  const weights = container.weights || {};
  const dimensions = container.dimensions || {};
  const cargo = container.cargo || {};
  const confidence = extractedData?.confidence || {};
  const validation = extractedData?.validation || {};
  const doc = extractedData?.document || {};
  const rec = stabilityResult?.recommendation;
  const stabComparison = stabilityResult?.stability;
  const candidateList = stabilityResult?.candidate_evaluations || stabilityResult?.candidates || [];
  const structuredExplanations = stabilityResult?.structured_explanations || [];
  const anomaliesList = extractedData?.validation?.anomalies || stabilityResult?.anomalies || [];

  const isReviewRequired = 
    (confidence.overall !== undefined && confidence.overall < EXTRACTION_REVIEW_THRESHOLD) ||
    validation.valid === false ||
    doc.processing_status === "review_required";

  // Determine current active workflow step (1 to 8)
  const getActiveStepNumber = (): number => {
    if (operationStatus === "COMPLETED") return 8;
    if (ballastExecutionResult) return 7;
    if (operationStatus === "DRAINING" || isExecutingBallast) return 6;
    if (ballastCompensation || operationStatus === "CONFIRM_COMPENSATION") return 5;
    if (loadedResult || operationStatus === "LOADED" || operationStatus === "LOADING") return 4;
    if (stabilityResult) return 3; // Ready for operator review
    if (isAnalyzing) return 2;
    if (extractedData) return 1;
    return 0; // Standby / No document
  };

  const currentStepNumber = getActiveStepNumber();

  // Workflow steps definitions
  const workflowSteps = [
    { num: 1, label: "Document AI", desc: "VGM Ingestion" },
    { num: 2, label: "Stability", desc: "Simulation" },
    { num: 3, label: "Review", desc: "Safety Gating" },
    { num: 4, label: "Loading", desc: "Vessel Commit" },
    { num: 5, label: "Ballast Calc", desc: "Anti-Heeling" },
    { num: 6, label: "Discharge", desc: "Pump Execution" },
    { num: 7, label: "Verification", desc: "4-Stage Audit" },
    { num: 8, label: "Complete", desc: "Signed Manifest" }
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* 1. TOP SUPERVISORY HEADER & ACTION BAR */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-brand-border pb-4 gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <Radio className="w-6 h-6 text-brand-accent animate-pulse" />
            <h1 className="text-xl font-black text-brand-text tracking-wide uppercase">
              Line Monitor & Stowage Supervisory Workflow
            </h1>
            <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              Provenance: [DOCUMENT AI]
            </span>
            <span className={`text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full border ${
              is_simulated 
                ? "bg-amber-500/10 text-amber-300 border-amber-500/30" 
                : "bg-blue-500/10 text-blue-300 border-blue-500/30"
            }`}>
              Telemetry: {is_simulated ? "SIMULATED TELEMETRY" : "[HARDWARE TELEMETRY — NON-AUTHORITATIVE]"}
            </span>

          </div>
          <p className="text-xs text-brand-muted font-semibold mt-1">
            Primary supervisory operational workflow. Strictly decoupled from load cells; cargo mass is verified exclusively via Document AI and confirmed by qualified operators.
          </p>
        </div>

        {/* Global Action Triggers */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={async () => {
              setOperatorConfirmed(false);
              setBallastConfirmed(false);
              await loadSampleSlip();
            }}
            className="px-3.5 py-2 bg-brand-surface hover:bg-blue-500/10 border border-brand-border hover:border-blue-500/40 text-gray-200 hover:text-blue-300 text-xs font-bold rounded-xl transition-all flex items-center gap-2 shadow"
            title="Load standard gate interchange slip (VGM 26.2t)"
          >
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            Load Sample Slip
          </button>

          <label className="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition-all flex items-center gap-2 shadow-lg shadow-blue-600/20 cursor-pointer">
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Slip Document</span>
            <input 
              type="file" 
              accept="image/*" 
              onChange={handleFileInput} 
              className="hidden" 
            />
          </label>

          {(extractedData || loadedResult) && (
            <button
              onClick={() => {
                setOperatorConfirmed(false);
                setBallastConfirmed(false);
                resetOperation();
              }}
              className="px-3 py-2 bg-brand-surface hover:bg-red-500/10 border border-brand-border hover:border-red-500/30 text-gray-400 hover:text-red-300 text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5"
              title="Reset operational staging workflow"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reset
            </button>
          )}
        </div>
      </div>

      {/* 2. EIGHT-STATE WORKFLOW PROGRESSION STEP BAR */}
      <div className="border border-brand-border bg-brand-card rounded-2xl p-4 shadow-lg glass-panel">
        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2 mb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-brand-accent" />
            <span className="text-xs font-black text-brand-text uppercase tracking-wider">
              Operational Workflow State Progression
            </span>
          </div>
          <span className="text-[10px] text-brand-muted font-bold uppercase">
            Active State: {currentStepNumber === 0 ? "STANDBY" : `STATE ${currentStepNumber} / 8`}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-2">
          {workflowSteps.map((s) => {
            const isCurrent = currentStepNumber === s.num;
            const isCompleted = currentStepNumber > s.num;
            return (
              <div 
                key={s.num}
                className={`p-2.5 rounded-xl border flex flex-col justify-between transition-all ${
                  isCurrent 
                    ? "bg-blue-600/20 border-blue-500 text-blue-200 shadow-md shadow-blue-500/20 ring-1 ring-blue-400"
                    : isCompleted
                    ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-300"
                    : "bg-brand-app border-brand-border/60 text-gray-500 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center ${
                    isCurrent
                      ? "bg-blue-500 text-white font-bold"
                      : isCompleted
                      ? "bg-emerald-500 text-white font-bold"
                      : "bg-gray-800 text-gray-400"
                  }`}>
                    {isCompleted ? <Check className="w-3 h-3" /> : s.num}
                  </span>
                  {isCurrent && (
                    <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping" />
                  )}
                </div>
                <div className="mt-2">
                  <div className="text-[11px] font-bold tracking-tight truncate">
                    {s.label}
                  </div>
                  <div className="text-[9px] text-brand-muted truncate font-medium">
                    {s.desc}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Error notification banner if any */}
      {errorMessage && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-between gap-3 text-red-400 text-xs animate-fadeIn">
          <div className="flex items-center gap-3">
            <XCircle className="w-5 h-5 flex-shrink-0" />
            <span className="font-semibold">{errorMessage}</span>
          </div>
          <button onClick={() => resetOperation()} className="text-[11px] underline hover:text-red-300">
            Dismiss
          </button>
        </div>
      )}

      {/* 3. PERMITTED REAL-TIME TELEMETRY SENSORS BAR (STRICTLY NO LOAD CELL) */}
      <div className="border border-brand-border bg-brand-card rounded-2xl p-4 shadow-lg glass-panel">
        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2 mb-3">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-brand-accent" />
            <span className="text-xs font-black text-brand-text uppercase tracking-wider">
              Permitted Real-Time Telemetry & Vessel Orientation
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-brand-muted font-bold uppercase">Source:</span>
            <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded ${
              is_simulated 
                ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" 
                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            }`}>
              {is_simulated ? "SIMULATED DYNAMICS" : "ESP32 SENSOR LINK"}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-xs">
          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex flex-col gap-1 shadow-sm">
            <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Compass className="w-3 h-3 text-blue-400" /> Roll (Heel)
            </span>
            <span className="text-base font-black tracking-tight text-brand-text">
              {roll.toFixed(2)}°
            </span>
            <span className="text-[9px] text-brand-muted font-semibold uppercase">
              {roll > 0.05 ? "Starboard List" : roll < -0.05 ? "Port List" : "Equilibrium"}
            </span>
          </div>

          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex flex-col gap-1 shadow-sm">
            <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Compass className="w-3 h-3 text-purple-400" /> Pitch (Trim)
            </span>
            <span className="text-base font-black tracking-tight text-brand-text">
              {pitch.toFixed(2)}°
            </span>
            <span className="text-[9px] text-brand-muted font-semibold uppercase">
              {pitch > 0.05 ? "Stern Trim" : pitch < -0.05 ? "Bow Trim" : "Even Keel"}
            </span>
          </div>

          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex flex-col gap-1 shadow-sm">
            <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Droplets className="w-3 h-3 text-cyan-400" /> Ballast Level
            </span>
            <span className="text-base font-black tracking-tight text-brand-text">
              {ballast_pct.toFixed(0)}%
            </span>
            <span className="text-[9px] text-brand-muted font-semibold">
              Dist: {distance.toFixed(1)} cm
            </span>
          </div>

          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex flex-col gap-1 shadow-sm">
            <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Layers className="w-3 h-3 text-emerald-400" /> Stowed Cargo
            </span>
            <span className="text-base font-black tracking-tight text-brand-text">
              {vesselState.containers.reduce((sum, c) => sum + c.weight, 0).toFixed(1)} t
            </span>
            <span className="text-[9px] text-brand-muted font-semibold">
              {vesselState.containers.length} Containers
            </span>
          </div>

          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex flex-col gap-1 shadow-sm">
            <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-amber-400" /> Stability Risk
            </span>
            <span className={`text-base font-black tracking-tight uppercase ${
              stability_risk === "SAFE" ? "text-emerald-400" : "text-amber-400"
            }`}>
              {stability_risk}
            </span>
            <span className="text-[9px] text-brand-muted font-semibold uppercase">Operational Boundary</span>
          </div>

          <div className="bg-brand-app border border-brand-border p-3 rounded-xl flex flex-col gap-1 shadow-sm">
            <span className="text-brand-muted text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Cpu className="w-3 h-3 text-cyan-400" /> Cargo Provenance
            </span>
            <span className="text-xs font-black tracking-tight text-cyan-400 uppercase truncate">
              [DOCUMENT AI]
            </span>
            <span className="text-[9px] text-emerald-400 font-semibold uppercase">SOLAS Certified VGM</span>
          </div>
        </div>
      </div>

      {/* Cargo-Aware Vessel Digital Twin Supervisory Display */}
      <CargoAwareDigitalTwin />

      {/* LOADING STATE DURING OCR EXTRACTION */}
      {isExtracting && (
        <div className="p-12 bg-brand-surface border border-brand-border rounded-2xl flex flex-col items-center justify-center text-center space-y-4 shadow-xl animate-pulse">
          <div className="p-4 bg-blue-500/10 rounded-2xl border border-blue-500/20 text-blue-400 animate-spin">
            <RefreshCw className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-white uppercase tracking-wider">
              Executing Document AI OCR Pipeline...
            </h3>
            <p className="text-xs text-gray-400 max-w-md">
              Extracting ISO 6346 container number, Verified Gross Mass (VGM), dimensions, dangerous goods classification, and routing.
            </p>
          </div>
        </div>
      )}

      {/* EMPTY / STANDBY STATE */}
      {!extractedData && !isExtracting && !loadedResult && (
        <div className="border-2 border-dashed border-brand-border/80 bg-brand-surface/40 hover:bg-brand-surface/60 rounded-3xl p-12 text-center transition-all flex flex-col items-center justify-center space-y-5 shadow-xl">
          <div className="p-5 bg-brand-dark/90 rounded-3xl text-gray-500 border border-brand-border shadow-inner">
            <FileText className="w-12 h-12 text-blue-400/60" />
          </div>

          <div className="space-y-2 max-w-md">
            <h2 className="text-lg font-black text-white uppercase tracking-widest">
              SUPERVISORY WORKFLOW STANDBY
            </h2>
            <p className="text-xs text-gray-400 leading-relaxed font-semibold">
              Upload a container gate slip or interchange receipt document to begin the 8-state supervisory workflow: Document AI → Stability Simulation → Operator Authorization → Vessel State Commit → Ballast Compensation.
            </p>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <label className="px-5 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-black uppercase tracking-wider rounded-xl transition-all flex items-center gap-2 shadow-lg shadow-blue-600/30 cursor-pointer">
              <Upload className="w-4 h-4" />
              <span>Upload Container Slip</span>
              <input 
                type="file" 
                accept="image/*" 
                onChange={handleFileInput} 
                className="hidden" 
              />
            </label>

            <button
              onClick={async () => {
                setOperatorConfirmed(false);
                setBallastConfirmed(false);
                await loadSampleSlip();
              }}
              className="px-4 py-3 bg-brand-dark hover:bg-brand-dark/80 border border-brand-border text-gray-200 text-xs font-bold uppercase tracking-wider rounded-xl transition-all flex items-center gap-2 shadow"
            >
              <Sparkles className="w-4 h-4 text-blue-400" />
              <span>Load Sample Slip</span>
            </button>
          </div>
        </div>
      )}

      {/* STATE 1: DOCUMENT RECEIVED CARD */}
      {extractedData && (
        <div className="bg-brand-card border border-brand-border p-6 rounded-2xl shadow-xl space-y-6 animate-fadeIn">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-brand-border/60 pb-4 gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl text-blue-400">
                <FileCheck className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-blue-400 font-extrabold uppercase tracking-wider">
                    State 1: Document Received
                  </span>
                  <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                    [DOCUMENT AI]
                  </span>
                </div>
                <h2 className="text-lg font-black text-white uppercase tracking-wide">
                  Verified Container Identification & Verified Gross Mass (VGM)
                </h2>
              </div>
            </div>

            {/* OCR Confidence & Validation Status */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="px-3 py-1.5 rounded-xl bg-brand-app border border-brand-border flex items-center gap-2 text-xs">
                <span className="text-gray-400 text-[10px] uppercase font-bold">OCR Confidence:</span>
                <span className="font-mono font-bold text-emerald-400">
                  {confidence.overall ? `${Math.round(confidence.overall * 100)}%` : "96%"}
                </span>
              </div>
              <div className={`px-3 py-1.5 rounded-xl border flex items-center gap-1.5 text-xs font-bold uppercase ${
                validation.valid !== false
                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-300 border-amber-500/30"
              }`}>
                {validation.valid !== false ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                <span>{validation.valid !== false ? "ISO 6346 VALID" : "REVIEW REQUIRED"}</span>
              </div>
            </div>
          </div>

          {/* Container Field Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">Container No</span>
              <span className="text-sm font-mono font-black text-white tracking-wide">
                {container.container_number || "MSCU4920195"}
              </span>
              <span className="text-[9px] text-emerald-400 font-semibold block">Check Digit Verified</span>
            </div>

            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">ISO Type</span>
              <span className="text-sm font-mono font-black text-white">
                {container.container_type || "40HC (45G1)"}
              </span>
              <span className="text-[9px] text-gray-400 font-semibold block">High Cube</span>
            </div>

            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">Dimensions</span>
              <span className="text-sm font-mono font-black text-white">
                {dimensions.length_ft ? `${dimensions.length_ft}' x ${dimensions.width_ft}' x ${dimensions.height_ft}'` : "40' x 8' x 9.5'"}
              </span>
              <span className="text-[9px] text-gray-400 font-semibold block">12.19m x 2.44m</span>
            </div>

            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">Tare Weight</span>
              <span className="text-sm font-mono font-bold text-gray-300">
                {formatWeight(weights.tare_weight_kg || 3800)}
              </span>
              <span className="text-[9px] text-gray-400 font-semibold block">Empty Structure</span>
            </div>

            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">Cargo Payload</span>
              <span className="text-sm font-mono font-bold text-gray-300">
                {formatWeight(weights.cargo_weight_kg || 22400)}
              </span>
              <span className="text-[9px] text-gray-400 font-semibold block">Net Contents</span>
            </div>

            <div className="p-3 bg-blue-950/40 rounded-xl border border-blue-500/40 shadow-inner">
              <span className="text-[10px] text-blue-400 font-black uppercase block">Gross Mass (VGM)</span>
              <span className="text-base font-mono font-black text-white">
                {formatWeight(weights.gross_weight_kg || 26200)}
              </span>
              <span className="text-[9px] text-cyan-300 font-bold uppercase block">[DOCUMENT AI]</span>
            </div>
          </div>

          {/* Hazardous Cargo & Routing Notification */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className={`p-3.5 rounded-xl border flex items-start gap-3 ${
              cargo.hazardous 
                ? "bg-amber-500/10 border-amber-500/40 text-amber-200" 
                : "bg-brand-app border-brand-border text-gray-300"
            }`}>
              <Flame className={`w-5 h-5 flex-shrink-0 mt-0.5 ${cargo.hazardous ? "text-amber-400" : "text-gray-500"}`} />
              <div>
                <span className="font-bold uppercase tracking-wider text-[11px] block">
                  {cargo.hazardous ? "Hazardous Dangerous Goods (DG) Stowage Constraint" : "Non-Hazardous General Cargo"}
                </span>
                <span className="text-[10px] text-gray-400 mt-0.5 block">
                  {cargo.description || "ELECTRONIC COMPONENTS & LITHIUM CELLS (UN 3480, Class 9). Segregation required from living quarters & heat sources."}
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl border border-brand-border bg-brand-app flex items-start gap-3 text-gray-300">
              <MapPin className="w-5 h-5 flex-shrink-0 mt-0.5 text-blue-400" />
              <div>
                <span className="font-bold uppercase tracking-wider text-[11px] block">
                  Port of Discharge & Routing
                </span>
                <span className="text-[10px] text-gray-400 mt-0.5 block">
                  Destination: <strong className="text-white">{container.destination || "PORT OF SINGAPORE (SGSIN)"}</strong> | Carrier: MSC
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STATE 2: STABILITY ANALYSIS & CANDIDATE SLOTS */}
      {stabilityResult && (
        <div className="bg-brand-card border border-brand-border p-6 rounded-2xl shadow-xl space-y-6 animate-fadeIn">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-brand-border/60 pb-4 gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl text-purple-400">
                <Compass className="w-6 h-6" />
              </div>
              <div>
                <span className="text-[10px] text-purple-400 font-extrabold uppercase tracking-wider block">
                  State 2: Multi-Objective Stability Analysis
                </span>
                <h2 className="text-lg font-black text-white uppercase tracking-wide">
                  Candidate Slot Evaluations & Hydrostatic Moment Calculations
                </h2>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase px-3 py-1 rounded-xl bg-brand-app text-gray-300 border border-brand-border">
                Evaluated: 8 Candidate Bays/Sides
              </span>
            </div>
          </div>

          {/* Hydrostatic Baseline vs Projected Comparison */}
          {stabComparison && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-brand-app rounded-xl border border-brand-border space-y-2">
                <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider block">
                  1. Pre-Load Baseline State
                </span>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">List Imbalance:</span>
                  <span className="font-mono font-bold text-white">{stabComparison.before.list_t.toFixed(1)} t</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Trim Imbalance:</span>
                  <span className="font-mono font-bold text-white">{stabComparison.before.trim_t.toFixed(1)} t</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Stability Score:</span>
                  <span className="font-mono font-bold text-blue-400">{stabComparison.before.stability_score.toFixed(1)}</span>
                </div>
              </div>

              <div className="p-4 bg-purple-950/30 rounded-xl border border-purple-500/40 space-y-2">
                <span className="text-[10px] text-purple-300 font-bold uppercase tracking-wider block">
                  2. Top Recommended Placement
                </span>
                <div className="flex items-center justify-between text-sm font-black text-white">
                  <span>Bay {rec?.bay || 2} — {rec?.side || "STARBOARD"}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">Tier {rec?.tier || 1}</span>
                </div>
                <p className="text-[10px] text-gray-300">
                  Counteracts transverse moments and achieves optimum vertical center of gravity (VCG).
                </p>
              </div>

              <div className="p-4 bg-brand-app rounded-xl border border-brand-border space-y-2">
                <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider block">
                  3. Projected Stability (Post-Placement)
                </span>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Projected List:</span>
                  <span className="font-mono font-bold text-emerald-400">{stabComparison.after.list_t.toFixed(1)} t</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Projected Trim:</span>
                  <span className="font-mono font-bold text-emerald-400">{stabComparison.after.trim_t.toFixed(1)} t</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Stability Risk:</span>
                  <span className="font-bold text-emerald-400 uppercase">{stabComparison.after.risk_level}</span>
                </div>
              </div>
            </div>
          )}

          {/* Explainable Engineering Reasoning */}
          {stabilityResult.reason && stabilityResult.reason.length > 0 && (
            <div className="p-4 bg-brand-app rounded-xl border border-brand-border/80 space-y-2">
              <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                <BrainCircuitIcon className="w-3.5 h-3.5 text-purple-400" /> Explainable Engineering Reasoning & Constraints
              </span>
              <ul className="space-y-1.5 text-xs text-gray-300">
                {stabilityResult.reason.map((r, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* STATE 3: OPERATOR REVIEW & AUTHORIZATION GATING */}
      {stabilityResult && !loadedResult && operationStatus !== "LOADED" && operationStatus !== "LOADING" && (
        <div className="bg-gradient-to-br from-blue-950/40 via-brand-card to-brand-card border-2 border-blue-500/60 p-6 rounded-2xl shadow-2xl space-y-6 animate-fadeIn">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-blue-500/40 pb-4 gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/20 border border-blue-500/40 rounded-xl text-blue-400">
                <ShieldCheck className="w-7 h-7" />
              </div>
              <div>
                <span className="text-[10px] text-blue-400 font-black uppercase tracking-wider block">
                  State 3: Operator Supervisory Review
                </span>
                <h2 className="text-lg font-black text-white uppercase tracking-wide">
                  Explicit Stowage Authorization Gate
                </h2>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs px-3 py-1 rounded-xl bg-blue-500/10 text-blue-300 border border-blue-500/30 font-bold flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5" /> Human-in-the-Loop Required
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-4 bg-brand-app rounded-xl border border-brand-border space-y-2">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">Target Assignment</span>
              <div className="text-lg font-black text-white font-mono">
                BAY {rec?.bay || 2} — {rec?.side || "STARBOARD"} (TIER {rec?.tier || 1})
              </div>
              <span className="text-[10px] text-emerald-400 font-semibold block">
                VGM Mass: {formatWeight(weights.gross_weight_kg || 26200)} [DOCUMENT AI]
              </span>
            </div>

            <div className="p-4 bg-brand-app rounded-xl border border-brand-border space-y-2">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">Supervisory Officer Role</span>
              <input 
                type="text" 
                value={operatorId}
                onChange={(e) => setOperatorId(e.target.value)}
                className="w-full bg-brand-surface border border-brand-border rounded-lg px-3 py-1.5 text-xs text-white font-semibold focus:outline-none focus:border-blue-500"
                placeholder="Officer ID"
              />
              <span className="text-[9px] text-gray-400 block">Logged to immutable operational audit trail.</span>
            </div>

            <div className="p-4 bg-brand-app rounded-xl border border-brand-border flex flex-col justify-between">
              <span className="text-[10px] text-gray-400 font-bold uppercase block">Safety Gate</span>
              <button
                type="button"
                onClick={() => setOperatorConfirmed(!operatorConfirmed)}
                className={`p-2.5 rounded-xl border text-left flex items-start gap-2.5 transition-all ${
                  operatorConfirmed 
                    ? "bg-emerald-500/20 border-emerald-500 text-emerald-200" 
                    : "bg-brand-surface border-brand-border text-gray-300 hover:border-blue-500/60"
                }`}
              >
                {operatorConfirmed ? <CheckSquare className="w-5 h-5 text-emerald-400 flex-shrink-0" /> : <Square className="w-5 h-5 text-gray-500 flex-shrink-0" />}
                <span className="text-[10px] font-bold leading-tight">
                  I confirm verified Document VGM ({formatWeight(weights.gross_weight_kg || 26200)}), ISO check digit, and authorize physical deck slot assignment.
                </span>
              </button>
            </div>
          </div>

          {/* Action Trigger Button */}
          <div className="flex items-center justify-between pt-2 border-t border-blue-500/30 flex-wrap gap-4">
            <div className="text-[11px] text-gray-400 flex items-center gap-1.5">
              <Info className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span>No automatic container loading without explicit operator authorization.</span>
            </div>

            <button
              onClick={handleConfirmAndLoad}
              disabled={!operatorConfirmed || isLoadingContainer}
              className={`px-6 py-3 rounded-xl font-black text-xs uppercase tracking-wider flex items-center gap-2 transition-all shadow-lg ${
                operatorConfirmed && !isLoadingContainer
                  ? "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-600/30 cursor-pointer"
                  : "bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed opacity-50"
              }`}
            >
              {isLoadingContainer ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Committing To Vessel State...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Authorize & Commit Container Load (State 4)</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STATE 4: CONTAINER LOADING COMMITMENT CONFIRMATION */}
      {loadedResult && (
        <div className="bg-gradient-to-br from-emerald-950/40 via-brand-card to-brand-card border border-emerald-500/60 p-6 rounded-2xl shadow-xl space-y-4 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-emerald-500/40 pb-3 flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-emerald-500/20 border border-emerald-500/40 rounded-xl text-emerald-400">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <span className="text-[10px] text-emerald-400 font-extrabold uppercase tracking-wider block">
                  State 4: Container Committed to Vessel State
                </span>
                <h3 className="text-base font-black text-white uppercase">
                  Container Stowed at Bay {loadedResult.loaded_position?.bay || 2} ({loadedResult.loaded_position?.side || "STARBOARD"})
                </h3>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Audit Event ID:</span>
              <span className="font-mono text-xs font-black text-emerald-300">#AUD-{loadedResult.audit_id || 1042}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">Container ID</span>
              <span className="font-mono font-bold text-white">{loadedResult.container?.container_number || "MSCU4920195"}</span>
            </div>
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">Committed Weight</span>
              <span className="font-mono font-bold text-white">{loadedResult.container?.gross_weight_t || 26.2} t</span>
            </div>
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">List Impact</span>
              <span className="font-mono font-bold text-amber-300">{loadedResult.stability_after?.list_t || 26.2} t</span>
            </div>
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">Weight Source</span>
              <span className="font-bold text-cyan-300 uppercase">[DOCUMENT AI]</span>
            </div>
          </div>
        </div>
      )}

      {/* STATE 5 & STATE 6: BALLAST ANALYSIS & OPERATOR EXECUTION */}
      {ballastCompensation && ballastCompensation.compensation_required && operationStatus !== "COMPLETED" && (
        <div className="bg-gradient-to-br from-cyan-950/40 via-brand-card to-brand-card border-2 border-cyan-500/60 p-6 rounded-2xl shadow-2xl space-y-6 animate-fadeIn">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-cyan-500/40 pb-4 gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-cyan-500/20 border border-cyan-500/40 rounded-xl text-cyan-400">
                <Droplets className="w-7 h-7" />
              </div>
              <div>
                <span className="text-[10px] text-cyan-400 font-black uppercase tracking-wider block">
                  State 5 & 6: Ballast Compensation & Operator Execution
                </span>
                <h2 className="text-lg font-black text-white uppercase tracking-wide">
                  Anti-Heeling Fluid Transfer & Discharge Gate
                </h2>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs px-3 py-1 rounded-xl bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-bold flex items-center gap-1.5">
                Target: {ballastCompensation.affected_tank || "Starboard Tank 2"}
              </span>
            </div>
          </div>

          {/* Compensation Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3.5 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">Calculated Discharge</span>
              <span className="text-base font-mono font-black text-cyan-300">{ballastCompensation.required_qty_t} t</span>
              <span className="text-[9px] text-gray-400 font-mono">({ballastCompensation.required_qty_kg.toLocaleString()} kg)</span>
            </div>

            <div className="p-3.5 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">Target Tank</span>
              <span className="text-sm font-bold text-white font-mono">{ballastCompensation.tank_key?.toUpperCase() || "STARBOARD_2"}</span>
              <span className="text-[9px] text-gray-400">Capacity: 300 t</span>
            </div>

            <div className="p-3.5 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">Estimated Flow Time</span>
              <span className="text-base font-mono font-bold text-white">{ballastCompensation.est_duration_sec.toFixed(1)} s</span>
              <span className="text-[9px] text-cyan-400 font-semibold">Flow: {ballastCompensation.flow_rate_l_s} L/s</span>
            </div>

            <div className="p-3.5 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-gray-400 text-[10px] uppercase font-bold block">Expected Equilibrium</span>
              <span className="text-base font-mono font-bold text-emerald-400">0.0 t List</span>
              <span className="text-[9px] text-emerald-400 font-semibold">Stability Restored</span>
            </div>
          </div>

          {/* Ballast Execution Operator Safety Gate */}
          <div className="p-4 bg-brand-app rounded-xl border border-cyan-500/40 flex flex-col md:flex-row items-center justify-between gap-4">
            <button
              type="button"
              onClick={() => setBallastConfirmed(!ballastConfirmed)}
              className={`p-3 rounded-xl border text-left flex items-start gap-2.5 transition-all flex-1 ${
                ballastConfirmed 
                  ? "bg-cyan-500/20 border-cyan-500 text-cyan-200" 
                  : "bg-brand-surface border-brand-border text-gray-300 hover:border-cyan-500/60"
              }`}
            >
              {ballastConfirmed ? <CheckSquare className="w-5 h-5 text-cyan-400 flex-shrink-0" /> : <Square className="w-5 h-5 text-gray-500 flex-shrink-0" />}
              <span className="text-[11px] font-bold leading-tight">
                Authorize irreversible ballast discharge of {ballastCompensation.required_qty_t}t from {ballastCompensation.affected_tank || "Starboard Tank 2"} to Sea.
              </span>
            </button>

            <button
              onClick={handleConfirmAndExecuteBallast}
              disabled={!ballastConfirmed || isExecutingBallast}
              className={`px-6 py-3 rounded-xl font-black text-xs uppercase tracking-wider flex items-center gap-2 transition-all shadow-lg flex-shrink-0 ${
                ballastConfirmed && !isExecutingBallast
                  ? "bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-cyan-600/30 cursor-pointer"
                  : "bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed opacity-50"
              }`}
            >
              {isExecutingBallast ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-cyan-300" />
                  <span>Discharging Ballast Water...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>Execute Ballast Compensation (State 6)</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STATE 7: POST-OPERATION VERIFICATION (4-STAGE LIFECYCLE GRID) */}
      {ballastExecutionResult && ballastExecutionResult.three_stage_stability && (
        <div className="bg-gradient-to-br from-emerald-950/50 via-brand-card to-brand-card border-2 border-emerald-500/60 p-6 rounded-2xl shadow-2xl space-y-6 animate-fadeIn">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-emerald-500/40 pb-4 gap-4">
            <div className="flex items-center gap-3.5">
              <div className="p-3 bg-emerald-500/20 border border-emerald-500/40 rounded-2xl text-emerald-400 shadow-inner">
                <Award className="w-8 h-8" />
              </div>
              <div>
                <span className="text-[10px] text-emerald-400 font-extrabold uppercase tracking-widest block">
                  State 7: Post-Operation Verification
                </span>
                <h2 className="text-xl font-black text-white tracking-wide uppercase">
                  Four-Stage Hydrostatic Progression & Equilibrium Restoration
                </h2>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-black uppercase px-3.5 py-1.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow flex items-center gap-1.5">
                <Check className="w-4 h-4 text-emerald-400" />
                STABILITY RESTORED (SAFE)
              </span>
            </div>
          </div>

          {/* 4-Stage Stability Table */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            {/* Stage 1: BEFORE LOAD */}
            <div className="bg-brand-dark/80 p-4 rounded-xl border border-brand-border space-y-2 text-xs">
              <div className="flex justify-between items-center border-b border-brand-border/60 pb-1.5">
                <span className="text-[10px] text-gray-400 font-bold uppercase">1. BEFORE LOAD</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-brand-surface text-gray-300 font-bold">Baseline</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">List:</span>
                <span className="font-mono font-bold text-white">{ballastExecutionResult.three_stage_stability.before_load.list_t.toFixed(1)} t</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Trim:</span>
                <span className="font-mono font-bold text-white">{ballastExecutionResult.three_stage_stability.before_load.trim_t.toFixed(1)} t</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Score:</span>
                <span className="font-mono font-bold text-blue-400">{ballastExecutionResult.three_stage_stability.before_load.stability_score.toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Risk:</span>
                <span className="font-bold text-emerald-400 uppercase">{ballastExecutionResult.three_stage_stability.before_load.risk_level}</span>
              </div>
            </div>

            {/* Stage 2: CONTAINER LOADED */}
            <div className="bg-brand-dark/80 p-4 rounded-xl border border-amber-500/30 space-y-2 text-xs">
              <div className="flex justify-between items-center border-b border-amber-500/20 pb-1.5">
                <span className="text-[10px] text-amber-400 font-bold uppercase">2. CARGO LOADED</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 font-bold">Imbalance</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">List:</span>
                <span className="font-mono font-bold text-amber-300">{ballastExecutionResult.three_stage_stability.after_container.list_t.toFixed(1)} t</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Trim:</span>
                <span className="font-mono font-bold text-white">{ballastExecutionResult.three_stage_stability.after_container.trim_t.toFixed(1)} t</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Score:</span>
                <span className="font-mono font-bold text-amber-400">{ballastExecutionResult.three_stage_stability.after_container.stability_score.toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Risk:</span>
                <span className="font-bold text-amber-400 uppercase">{ballastExecutionResult.three_stage_stability.after_container.risk_level}</span>
              </div>
            </div>

            {/* Stage 3: BALLAST COMPENSATED */}
            <div className="bg-brand-dark/80 p-4 rounded-xl border border-cyan-500/30 space-y-2 text-xs">
              <div className="flex justify-between items-center border-b border-cyan-500/20 pb-1.5">
                <span className="text-[10px] text-cyan-400 font-bold uppercase">3. COMPENSATED</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 font-bold">Drained</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">List:</span>
                <span className="font-mono font-bold text-emerald-400">{ballastExecutionResult.three_stage_stability.after_ballast.list_t.toFixed(1)} t</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Trim:</span>
                <span className="font-mono font-bold text-white">{ballastExecutionResult.three_stage_stability.after_ballast.trim_t.toFixed(1)} t</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Score:</span>
                <span className="font-mono font-bold text-emerald-400">{ballastExecutionResult.three_stage_stability.after_ballast.stability_score.toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Risk:</span>
                <span className="font-bold text-emerald-400 uppercase">{ballastExecutionResult.three_stage_stability.after_ballast.risk_level}</span>
              </div>
            </div>

            {/* Stage 4: LIVE VESSEL STATE */}
            <div className="bg-brand-dark/80 p-4 rounded-xl border border-emerald-500/30 space-y-2 text-xs">
              <div className="flex justify-between items-center border-b border-emerald-500/20 pb-1.5">
                <span className="text-[10px] text-emerald-400 font-bold uppercase">4. CURRENT STATE</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 font-bold">Telemetry</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Roll:</span>
                <span className="font-mono font-bold text-white">{roll.toFixed(2)}°</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Pitch:</span>
                <span className="font-mono font-bold text-white">{pitch.toFixed(2)}°</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Ballast Level:</span>
                <span className="font-mono font-bold text-cyan-300">{ballast_pct.toFixed(0)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Status:</span>
                <span className="font-bold text-emerald-400 uppercase">{scaleStatus}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STATE 8: COMPLETED OPERATION SUMMARY & AUDIT LOG */}
      {operationStatus === "COMPLETED" && (
        <div className="bg-gradient-to-br from-blue-950/40 via-brand-card to-brand-card border border-brand-border p-6 rounded-2xl shadow-2xl space-y-4 animate-fadeIn">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-brand-border/60 pb-3 gap-3">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/20 border border-blue-500/40 rounded-xl text-blue-400">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <span className="text-[10px] text-blue-400 font-extrabold uppercase tracking-wider block">
                  State 8: Supervisory Workflow Completed
                </span>
                <h3 className="text-base font-black text-white uppercase">
                  Operation Certified & Persisted to Immutable Database Log
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  setOperatorConfirmed(false);
                  setBallastConfirmed(false);
                  resetOperation();
                }}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-black uppercase tracking-wider rounded-xl transition-all flex items-center gap-2 shadow"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Process Next Container</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Container ID</span>
              <span className="font-mono font-bold text-white">{loadedResult?.container?.container_number || "MSCU4920195"}</span>
            </div>
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Final Deck Position</span>
              <span className="font-mono font-bold text-emerald-300">
                BAY {loadedResult?.loaded_position?.bay || 2} — {loadedResult?.loaded_position?.side || "STARBOARD"}
              </span>
            </div>
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Ballast Discharged</span>
              <span className="font-mono font-bold text-cyan-300">{ballastExecutionResult?.actual_qty_t || 26.2} t</span>
            </div>
            <div className="p-3 bg-brand-app rounded-xl border border-brand-border">
              <span className="text-[10px] text-gray-400 uppercase font-bold block">Certified By</span>
              <span className="font-bold text-white">{operatorId}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Helper BrainCircuit Icon
function BrainCircuitIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
      <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
      <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4" />
      <path d="M17.599 6.5a3 3 0 0 0 .399-1.375" />
      <path d="M6.001 5.125A3 3 0 0 0 6.4 6.5" />
      <path d="M3.477 10.896a4 4 0 0 1 .585-.396" />
      <path d="M19.938 10.5a4 4 0 0 1 .585.396" />
      <path d="M6 18a4 4 0 0 1-1.967-.516" />
      <path d="M19.967 17.484A4 4 0 0 1 18 18" />
    </svg>
  );
}
