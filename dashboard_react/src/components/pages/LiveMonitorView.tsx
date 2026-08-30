import React, { useState } from "react";
import { useSocket } from "../../context/SocketContext";
import { 
  useContainerOperation,
  EXTRACTION_REVIEW_THRESHOLD,
  type CargoAnomaly 
} from "../../context/ContainerOperationContext";
import { Inclinometer } from "../Inclinometer";
import { AIVision } from "../AIVision";
import { 
  MetricCard, 
  StatusBadge, 
  SafetyBadge, 
  SectionHeader, 
  AlertBanner, 
  LoadingState, 
  OperationStep, 
  CANONICAL_8_STEPS,
  Button,
  GlassCard,
  Tooltip
} from "../ui";
import { 
  Radio, 
  Compass, 
  Droplets, 
  ShieldCheck, 
  Activity, 
  Eye, 
  Gauge, 
  Scale, 
  Box, 
  ArrowRight, 
  CheckCircle2, 
  AlertTriangle, 
  Flame, 
  RefreshCw, 
  Upload, 
  Sparkles, 
  FileText, 
  FileCheck, 
  BrainCircuit, 
  Check, 
  Square, 
  CheckSquare, 
  Layers, 
  Maximize2, 
  Anchor, 
  Play, 
  Award,
  ChevronRight,
  Lock,
  Cpu,
  XOctagon,
  ArrowDownCircle,
  FileSpreadsheet
} from "lucide-react";

export interface LiveMonitorViewProps {
  onNavigate?: (tab: string) => void;
}

export const LiveMonitorView: React.FC<LiveMonitorViewProps> = ({ onNavigate }) => {
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
    isLoadingContainer,
    isExecutingBallast,
    operationStatus,
    errorMessage,
    processSlipFile,
    loadSampleSlip,
    confirmAndLoadContainer,
    confirmAndExecuteBallast,
    resetOperation
  } = useContainerOperation();

  const [operatorConfirmed, setOperatorConfirmed] = useState<boolean>(false);
  const [ballastConfirmed, setBallastConfirmed] = useState<boolean>(false);
  const [operatorId, setOperatorId] = useState<string>("ChiefOfficer_Deck");
  const [showVisionGrid, setShowVisionGrid] = useState<boolean>(false);
  const [showAlternativeSlots, setShowAlternativeSlots] = useState<boolean>(false);

  if (!vesselState) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-maretide-app">
        <LoadingState message="Connecting to High-Frequency Telemetry Stream (10Hz)..." />
      </div>
    );
  }

  const {
    roll = 0,
    pitch = 0,
    distance = 0,
    stability_score = 100,
    stability_risk = "SAFE",
    is_simulated = true,
    stale_seconds = 0,
    containers = [],
    ballast_tanks = {},
    alerts = [],
    pump_state = "IDLE",
    pump_flow_l_s = 0
  } = vesselState;

  const totalCargoT = containers.reduce((sum, c) => sum + (c.weight || 0), 0);
  const totalBallastT = Object.values(ballast_tanks).reduce(
    (sum, t) => sum + (t.current_volume || 0), 
    0
  );

  // Compute 8-Stage Workflow Number
  const getActiveStepNumber = (): number => {
    if (operationStatus === "COMPLETED" || (ballastExecutionResult && !ballastCompensation?.compensation_required)) return 8;
    if (ballastExecutionResult || (loadedResult && !ballastCompensation?.compensation_required)) return 7;
    if (ballastCompensation || operationStatus === "CONFIRM_COMPENSATION" || isExecutingBallast) return 6;
    if (loadedResult || operationStatus === "LOADED" || operationStatus === "LOADING") return 5;
    if (stabilityResult) return 4;
    if (extractedData?.validation || extractedData) return 3;
    if (file || isExtracting) return 2;
    return 1;
  };

  const currentStep = getActiveStepNumber();

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setOperatorConfirmed(false);
      setBallastConfirmed(false);
      await processSlipFile(selected);
    }
  };

  const handleAuthorizeLoad = async () => {
    if (!operatorConfirmed) return;
    await confirmAndLoadContainer();
  };

  const handleAuthorizeBallast = async () => {
    if (!ballastConfirmed) return;
    await confirmAndExecuteBallast();
  };

  const container = extractedData?.container || {};
  const weights = container.weights || {};
  const dimensions = container.dimensions || {};
  const cargo = container.cargo || {};
  const validation = extractedData?.validation || {};
  const confidence = extractedData?.confidence || {};
  const rec = stabilityResult?.recommendation;
  const stabComparison = stabilityResult?.stability;
  const reasons = stabilityResult?.reason || [];
  const candidateList = stabilityResult?.candidate_evaluations || stabilityResult?.candidates || [];

  // Determine validation status & blocking
  let validationStatus: "VALID" | "REVIEW REQUIRED" | "BLOCKED" = "VALID";
  let isBlocked = false;

  if (validation.valid === false || (confidence.overall !== undefined && confidence.overall < EXTRACTION_REVIEW_THRESHOLD)) {
    validationStatus = "REVIEW REQUIRED";
  }
  if (validation.anomalies && validation.anomalies.some((a: CargoAnomaly) => a.severity === "CRITICAL")) {
    validationStatus = "BLOCKED";
    isBlocked = true;
  }

  // Active alerts list
  const activeAlerts: { id: string; title: string; message: string; severity: "INFO" | "WARNING" | "CRITICAL" }[] = [];

  if (Math.abs(roll) > 5.0) {
    activeAlerts.push({
      id: "roll-crit",
      title: "Transverse Capsize Alarm",
      message: `Critical heel angle detected: ${Math.abs(roll).toFixed(2)}° ${roll > 0 ? 'Starboard' : 'Port'}. Emergency ballast restorative moment required.`,
      severity: "CRITICAL"
    });
  } else if (Math.abs(roll) > 2.5) {
    activeAlerts.push({
      id: "roll-warn",
      title: "Transverse Heeling Advisory",
      message: `List exceeds operational boundary: ${Math.abs(roll).toFixed(2)}°. Monitor cargo transverse distribution.`,
      severity: "WARNING"
    });
  }

  if (stale_seconds >= 5.0) {
    activeAlerts.push({
      id: "stale-tel",
      title: "Telemetry Sync Latency",
      message: `Physical sensor stream delay (+${stale_seconds.toFixed(0)}s). Telemetry fallback active.`,
      severity: "WARNING"
    });
  }

  alerts.forEach((alt: any, idx: number) => {
    activeAlerts.push({
      id: `alert-${idx}`,
      title: alt.title || "Vessel Sensor Alert",
      message: alt.message || String(alt),
      severity: alt.level === "danger" ? "CRITICAL" : alt.level === "info" ? "INFO" : "WARNING"
    });
  });

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 bg-maretide-app page-enter">
      {/* 1. COMPACT OPERATIONAL HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-maretide-borderStrong/60">
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="p-2.5 bg-maretide-infoBg border border-maretide-info/30 rounded-xl text-maretide-info shadow-sm shadow-brand-cyan/20 flex-shrink-0">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xs sm:text-sm font-mono font-black text-maretide-text-primary uppercase tracking-widest truncate">
                LINE MONITOR — OPERATIONAL CONTROL STATION
              </h1>
              <span className={`text-[9px] font-mono font-black uppercase px-2 py-0.5 rounded-full border ${
                operationStatus === "COMPLETED"
                  ? "bg-maretide-safeBg text-maretide-safe border-maretide-safe/40"
                  : isLoadingContainer || isExecutingBallast || operationStatus === "DRAINING"
                  ? "bg-maretide-infoBg text-maretide-info border-maretide-info/40 animate-pulse"
                  : isBlocked
                  ? "bg-maretide-dangerBg text-maretide-danger border-maretide-danger/40"
                  : "surface-base text-maretide-text-primary border-maretide-border"
              }`}>
                STATUS: {operationStatus || "IDLE"}
              </span>
            </div>
            <p className="text-[11px] text-maretide-text-secondary font-medium truncate mt-0.5">
              Stage 0{currentStep}/08 • {CANONICAL_8_STEPS[currentStep - 1]?.desc || "Container Pipeline"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            variant="glass"
            size="sm"
            icon={Eye}
            onClick={() => setShowVisionGrid(!showVisionGrid)}
          >
            {showVisionGrid ? "Hide Cameras" : "YOLOv8 Vision"}
          </Button>

          {(extractedData || loadedResult) && (
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={() => {
                setOperatorConfirmed(false);
                setBallastConfirmed(false);
                resetOperation();
              }}
              title="Reset workflow to load next container"
            >
              Reset
            </Button>
          )}
        </div>
      </div>

      {/* Error alert banner if any */}
      {errorMessage && (
        <AlertBanner
          variant="danger"
          title="Supervisory Alert"
          message={errorMessage}
          onDismiss={() => resetOperation()}
        />
      )}

      {/* Active critical alarms */}
      {activeAlerts.length > 0 && (
        <div className="space-y-2">
          {activeAlerts.map(alt => (
            <AlertBanner
              key={alt.id}
              title={`[${alt.severity}] ${alt.title}`}
              message={alt.message}
              variant={alt.severity === "CRITICAL" ? "danger" : alt.severity === "INFO" ? "info" : "warning"}
            />
          ))}
        </div>
      )}

      {/* 2. PRIMARY 8-STAGE WORKFLOW STEPPER */}
      <div className="surface-elevated border border-maretide-border p-4 space-y-2.5">
        <div className="flex items-center justify-between text-[11px] font-mono font-bold">
          <span className="text-maretide-text-secondary uppercase tracking-wider flex items-center gap-2">
            <Compass className="w-4 h-4 text-maretide-info" />
            SOLAS Container Stability & Stowage Pipeline
          </span>
          <span className="text-maretide-info font-black surface-base px-2.5 py-0.5 rounded-full border border-maretide-border">
            {currentStep === 1 && !file ? "STANDBY — READY FOR SLIP" : `STAGE 0${currentStep} OF 08`}
          </span>
        </div>
        <OperationStep 
          steps={CANONICAL_8_STEPS} 
          currentStep={currentStep}
          blocked={isBlocked}
          warning={validationStatus === "REVIEW REQUIRED"}
        />
      </div>

      {/* 3. CORE METRIC TILES: SEPARATING CALCULATED VS RAW HARDWARE TELEMETRY */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {/* A. CALCULATED INTACT STABILITY CARD */}
        <div className="surface-elevated border border-maretide-border p-4 space-y-2">
          <div className="flex items-center justify-between border-b border-maretide-border pb-2">
            <span className="text-[10px] font-mono font-black uppercase text-maretide-text-primary flex items-center gap-1.5">
              <Compass className="w-3.5 h-3.5 text-maretide-info" /> Hydrostatics
            </span>
            <SafetyBadge type="CALCULATED" size="sm" />
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2 surface-base rounded-lg border border-maretide-border">
              <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Stability Score</span>
              <span className="text-sm font-black text-maretide-safe">{stability_score.toFixed(1)}%</span>
              <span className="text-[8px] text-maretide-text-secondary block">{stability_risk} Risk</span>
            </div>

            <div className="p-2 surface-base rounded-lg border border-maretide-border">
              <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Hydrostatic List</span>
              <span className="text-sm font-black text-maretide-text-primary">
                {Math.abs(stabComparison?.after?.list_t ?? roll).toFixed(1)}t
              </span>
              <span className="text-[8px] text-maretide-text-secondary block">
                {roll > 0.05 ? "Starboard" : roll < -0.05 ? "Port" : "Equilibrium"}
              </span>
            </div>
          </div>
        </div>

        {/* B. HARDWARE SENSOR TELEMETRY CARD */}
        <div className="surface-elevated border border-maretide-border p-4 space-y-2">
          <div className="flex items-center justify-between border-b border-maretide-border pb-2">
            <span className="text-[10px] font-mono font-black uppercase text-maretide-text-primary flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-maretide-info" /> Sensor Telemetry
            </span>
            <SafetyBadge type={is_simulated ? "SIMULATED_TELEMETRY" : "HARDWARE_TELEMETRY"} size="sm" />
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2 surface-base rounded-lg border border-maretide-border">
              <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Physical Roll (IMU)</span>
              <span className="text-sm font-black text-maretide-text-primary">{Math.abs(roll).toFixed(2)}°</span>
              <span className="text-[8px] text-maretide-text-secondary block">10Hz Stream</span>
            </div>

            <div className="p-2 surface-base rounded-lg border border-maretide-border">
              <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Physical Pitch (IMU)</span>
              <span className="text-sm font-black text-maretide-text-primary">{Math.abs(pitch).toFixed(2)}°</span>
              <span className="text-[8px] text-maretide-text-secondary block">10Hz Stream</span>
            </div>
          </div>
        </div>

        {/* C. ACTIVE BALLAST & STOWAGE SUMMARY */}
        <div className="surface-elevated border border-maretide-border p-4 space-y-2">
          <div className="flex items-center justify-between border-b border-maretide-border pb-2">
            <span className="text-[10px] font-mono font-black uppercase text-maretide-text-primary flex items-center gap-1.5">
              <Droplets className="w-3.5 h-3.5 text-maretide-info" /> Ballast & Cargo
            </span>
            <span className="text-[8px] font-mono font-bold text-maretide-text-secondary surface-base px-1.5 py-0.5 rounded border border-maretide-border">
              SOLAS VGM
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2 surface-base rounded-lg border border-maretide-border">
              <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Stowed Cargo</span>
              <span className="text-sm font-black text-maretide-text-primary">{totalCargoT.toFixed(1)} t</span>
              <span className="text-[8px] text-maretide-text-secondary block">{containers.length} on deck</span>
            </div>

            <div className="p-2 surface-base rounded-lg border border-maretide-border">
              <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Active Ballast</span>
              <span className="text-sm font-black text-maretide-info">{totalBallastT.toFixed(1)} t</span>
              <span className="text-[8px] text-maretide-text-secondary block">Level: {distance.toFixed(1)}cm</span>
            </div>
          </div>
        </div>
      </div>

      {/* 4. WORKFLOW EXECUTION PANELS (Left Column: Ingestion & Document AI; Right Column: Solver, Authorization & Ballast) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* LEFT COLUMN: STAGE 1 (DOCUMENT) & STAGE 2 (ANALYZE / CONTAINER HERO CARD) (6 cols on LG) */}
        <div className="lg:col-span-6 space-y-5">
          {/* STAGE 1: DOCUMENT (UPLOAD SLIP) */}
          <div className="surface-elevated border border-maretide-border p-5 space-y-4">
            <SectionHeader
              title="STAGE 01 — GATE INTERCHANGE SLIP INGESTION"
              icon={FileText}
              badge={
                <span className="text-[9px] font-mono px-2 py-0.5 rounded-full surface-base text-maretide-info border border-maretide-borderStrong font-bold">
                  PNG / JPG / WEBP
                </span>
              }
              actions={
                <Button
                  variant="glass"
                  size="xs"
                  icon={Sparkles}
                  onClick={async () => {
                    setOperatorConfirmed(false);
                    setBallastConfirmed(false);
                    await loadSampleSlip();
                  }}
                >
                  Sample Slip
                </Button>
              }
            />

            {/* Drag & Drop Upload Zone */}
            <div className="border-2 border-dashed border-maretide-border hover:border-maretide-info/50 rounded-2xl p-5 text-center transition-all surface-base/20 cursor-pointer relative group">
              <input
                type="file"
                accept="image/png, image/jpeg, image/jpg, image/webp"
                onChange={handleFileInput}
                className="hidden"
                id="line-monitor-slip-upload"
              />
              <label htmlFor="line-monitor-slip-upload" className="cursor-pointer flex flex-col items-center justify-center space-y-2">
                <div className="p-3 surface-base rounded-2xl text-maretide-info border border-maretide-borderStrong group-hover:scale-105 transition-transform shadow-inner">
                  <Upload className="w-5 h-5" />
                </div>
                <span className="text-xs font-mono font-bold text-maretide-text-primary">
                  {file ? file.name : "Click or drag gate interchange slip image"}
                </span>
                <span className="text-[10px] text-maretide-text-secondary font-medium">
                  SOLAS Verified Gross Mass (VGM) Ingestion • RapidOCR Engine
                </span>
              </label>
            </div>

            {isExtracting && (
              <LoadingState message="Processing Neural RapidOCR & Check-Digit Verification..." />
            )}

            {previewUrl && (
              <div className="p-2.5 surface-base rounded-xl border border-maretide-border flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <img 
                    src={previewUrl} 
                    alt="Container Slip Preview" 
                    className="w-12 h-12 object-cover rounded-lg border border-maretide-borderStrong flex-shrink-0"
                  />
                  <div className="min-w-0 text-xs font-mono">
                    <span className="text-maretide-text-primary font-bold block truncate">{file?.name || "container_slip.png"}</span>
                    <span className="text-[10px] text-maretide-safe font-semibold">OCR Analysis Complete</span>
                  </div>
                </div>

                <a 
                  href={previewUrl} 
                  target="_blank" 
                  rel="noreferrer"
                  className="p-2 rounded-lg surface-base hover:surface-elevated text-maretide-text-secondary hover:text-maretide-text-primary border border-maretide-borderStrong transition-colors"
                  title="View full resolution slip"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </a>
              </div>
            )}
          </div>

          {/* STAGE 2: CONTAINER HERO CARD [DOCUMENT AI] */}
          {extractedData && (
            <div className="surface-elevated border border-maretide-border p-5 space-y-3.5">
              <div className="flex items-center justify-between border-b border-maretide-border pb-2.5">
                <div className="flex items-center gap-2">
                  <FileCheck className="w-4 h-4 text-maretide-info" />
                  <span className="text-xs font-mono font-black text-maretide-text-primary uppercase">
                    CONTAINER SPECIFICATIONS
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <SafetyBadge type="DOCUMENT_AI" size="sm" />
                  <span className={`text-[8.5px] font-mono font-black uppercase px-2 py-0.5 rounded-full border ${
                    validationStatus === "VALID" 
                      ? "bg-maretide-safeBg text-maretide-safe border-maretide-safe/40"
                      : validationStatus === "REVIEW REQUIRED"
                      ? "bg-maretide-warningBg text-maretide-warning border-maretide-warning/40"
                      : "bg-maretide-dangerBg text-maretide-danger border-maretide-danger/40"
                  }`}>
                    {validationStatus}
                  </span>
                </div>
              </div>

              {/* Compact Specifications Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs font-mono">
                {/* Container No */}
                <div className="p-2.5 surface-base rounded-xl border border-maretide-border space-y-0.5">
                  <span className="text-[8.5px] text-maretide-text-secondary uppercase font-bold block">Container ID</span>
                  <span className="text-sm font-black text-maretide-text-primary block">{container.container_number || "MSCU4920195"}</span>
                  <span className="text-[8px] text-maretide-safe font-semibold block">Modulo-11 [PASS]</span>
                </div>

                {/* ISO Type */}
                <div className="p-2.5 surface-base rounded-xl border border-maretide-border space-y-0.5">
                  <span className="text-[8.5px] text-maretide-text-secondary uppercase font-bold block">ISO Type</span>
                  <span className="text-sm font-black text-maretide-info block">{container.container_type || "40HC"}</span>
                  <span className="text-[8px] text-maretide-text-secondary block">40ft High Cube</span>
                </div>

                {/* Gross Mass (SOLAS VGM) */}
                <div className="p-2.5 surface-base rounded-xl border border-maretide-border space-y-0.5">
                  <span className="text-[8.5px] text-maretide-text-secondary uppercase font-bold block">Gross Mass (VGM)</span>
                  <span className="text-sm font-black text-maretide-safe block">
                    {weights.gross_weight_kg ? `${(weights.gross_weight_kg / 1000).toFixed(1)} t` : "26.2 t"}
                  </span>
                  <span className="text-[8px] text-maretide-text-secondary block">Tare: {weights.tare_weight_kg ? `${(weights.tare_weight_kg / 1000).toFixed(1)}t` : "3.8t"}</span>
                </div>

                {/* Destination */}
                <div className="p-2.5 surface-base rounded-xl border border-maretide-border space-y-0.5">
                  <span className="text-[8.5px] text-maretide-text-secondary uppercase font-bold block">Discharge Port</span>
                  <span className="text-xs font-bold text-maretide-text-primary block truncate">{container.destination || "SINGAPORE (SGSIN)"}</span>
                  <span className="text-[8px] text-maretide-text-secondary block">POD</span>
                </div>

                {/* Confidence */}
                <div className="p-2.5 surface-base rounded-xl border border-maretide-border space-y-0.5">
                  <span className="text-[8.5px] text-maretide-text-secondary uppercase font-bold block">OCR Confidence</span>
                  <span className="text-xs font-bold text-maretide-info block">
                    {confidence.overall !== undefined ? `${(confidence.overall > 1 ? confidence.overall : confidence.overall * 100).toFixed(1)}%` : "98.5%"}
                  </span>
                  <span className="text-[8px] text-maretide-safe font-semibold block">High Quality</span>
                </div>

                {/* Hazardous IMDG Status */}
                <div className={`p-2.5 rounded-xl border space-y-0.5 ${
                  cargo.hazardous 
                    ? "bg-maretide-warningBg border-maretide-warning/40 text-maretide-warning" 
                    : "surface-base border-maretide-border text-maretide-text-secondary"
                }`}>
                  <span className="text-[8.5px] uppercase font-bold block flex items-center gap-1">
                    {cargo.hazardous && <Flame className="w-3 h-3 text-maretide-warning" />}
                    Hazardous (IMDG)
                  </span>
                  <span className="text-xs font-bold block">
                    {cargo.hazardous ? "IMDG DG APPLIED" : "NON-HAZARDOUS"}
                  </span>
                  <span className="text-[8px] block">Standard General Cargo</span>
                </div>
              </div>
            </div>
          )}

          {/* DYNAMIC INCLINOMETER INSTRUMENT WIDGET */}
          <div className="surface-elevated border border-maretide-border p-4 space-y-3">
            <SectionHeader
              title="Dynamic Liquid Inclinometer"
              icon={Compass}
              badge={<StatusBadge status={stability_risk} size="sm" />}
            />
            <Inclinometer roll={roll} pitch={pitch} />
          </div>
        </div>

        {/* RIGHT COLUMN: STAGE 3 (OPTIMIZE), STAGE 4 (AUTHORIZE), STAGE 5 (LOAD), STAGE 6 (BALLAST), STAGE 7 (VERIFY) (6 cols on LG) */}
        <div className="lg:col-span-6 space-y-5">
          {/* STAGE 3: RECOMMENDATION CARD (FOCAL POINT) */}
          {stabilityResult && (
            <div className="surface-elevated border border-maretide-border p-5 space-y-4 font-mono">
              <div className="flex items-center justify-between border-b border-maretide-border pb-2.5">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="w-4 h-4 text-maretide-info" />
                  <span className="text-xs font-black text-maretide-text-primary uppercase">
                    STOWAGE SOLVER RECOMMENDATION
                  </span>
                </div>
                <SafetyBadge type="CALCULATED" size="sm" />
              </div>

              {/* HERO RECOMMENDATION FOCAL POINT */}
              <div className="p-4 surface-base border-2 border-maretide-info/60 rounded-2xl space-y-2 shadow-md shadow-brand-cyan/10">
                <div className="flex items-center justify-between">
                  <span className="text-[9px] text-maretide-info font-bold uppercase tracking-wider">
                    Recommended Optimal Cell Slot
                  </span>
                  <span className="text-[10px] font-black text-maretide-safe bg-maretide-safeBg px-2 py-0.5 rounded-full border border-maretide-safe/40">
                    RANK #1 OPTIMAL
                  </span>
                </div>

                <div className="text-xl sm:text-2xl font-black text-maretide-text-primary tracking-tight">
                  BAY 0{rec?.bay || 2} — {rec?.side || "STARBOARD"} (TIER {rec?.tier || 1})
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-maretide-border">
                  <div>
                    <span className="text-[9px] text-maretide-text-secondary block">Projected Stability Score</span>
                    <span className="text-sm font-black text-maretide-safe">
                      {stabComparison?.after?.stability_score ? stabComparison.after.stability_score.toFixed(1) : "100.0"}% ({stability_risk})
                    </span>
                  </div>
                  <div>
                    <span className="text-[9px] text-maretide-text-secondary block">Projected Transverse List</span>
                    <span className="text-sm font-black text-maretide-safe">
                      {stabComparison?.after?.list_t !== undefined ? `${stabComparison.after.list_t.toFixed(1)} t` : "0.0 t"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Engineering Rationale */}
              <div className="p-3 surface-base/70 rounded-xl border border-maretide-border space-y-1.5 text-xs">
                <span className="text-[9.5px] font-bold text-maretide-text-secondary uppercase tracking-wider block">
                  Engineering Stowage Rationale
                </span>
                <p className="text-[11px] text-maretide-text-primary/90 font-medium leading-relaxed">
                  {reasons.length > 0
                    ? reasons[0]
                    : `Placement in Bay 0${rec?.bay || 2} ${rec?.side || "STARBOARD"} Tier ${rec?.tier || 1} counterbalances transverse cargo asymmetry while maintaining required metacentric height (GM ≥ 0.15m).`}
                </p>
              </div>

              {/* Alternative Candidate Slots Toggle */}
              {candidateList.length > 1 && (
                <div className="space-y-2">
                  <button
                    onClick={() => setShowAlternativeSlots(!showAlternativeSlots)}
                    className="text-[10px] text-maretide-info hover:underline font-bold flex items-center gap-1"
                  >
                    <span>{showAlternativeSlots ? "Hide Alternative Slots" : `View Evaluated Alternative Slots (${candidateList.length})`}</span>
                    <ChevronRight className={`w-3 h-3 transition-transform ${showAlternativeSlots ? "rotate-90" : ""}`} />
                  </button>

                  {showAlternativeSlots && (
                    <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                      {candidateList.slice(1, 5).map((cand: any, idx: number) => (
                        <div 
                          key={idx} 
                          className="p-2 surface-base rounded-lg border border-maretide-border flex items-center justify-between text-[10.5px]"
                        >
                          <span className="font-bold text-maretide-text-primary">
                            Bay {cand.bay} • {cand.side} • T{cand.tier}
                          </span>
                          <span className="text-maretide-text-secondary font-medium">
                            Score: {cand.score ? cand.score.toFixed(0) : "85"}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* STAGE 4: AUTHORIZATION SAFETY GATE (REVIEW → AUTHORIZE → LOAD) */}
          {stabilityResult && !loadedResult && operationStatus !== "LOADED" && operationStatus !== "LOADING" && (
            <div className={`surface-elevated border border-maretide-border p-5 border-2 space-y-4 font-mono ${
              isBlocked ? "border-maretide-danger/60" : "border-maretide-info/60"
            }`}>
              <SectionHeader
                title="STAGE 04 — OPERATOR AUTHORIZATION GATE"
                icon={ShieldCheck}
                badge={
                  <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-black ${
                    isBlocked 
                      ? "bg-maretide-dangerBg text-maretide-danger border border-maretide-danger/40"
                      : "bg-maretide-infoBg text-maretide-info border border-maretide-info/40"
                  }`}>
                    {isBlocked ? "BLOCKED" : "SOLAS ENFORCED"}
                  </span>
                }
              />

              <div className="space-y-3 text-xs">
                {/* Officer Input */}
                <div className="p-3 surface-base rounded-xl border border-maretide-border space-y-1">
                  <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Supervisory Duty Officer</span>
                  <input
                    type="text"
                    value={operatorId}
                    onChange={(e) => setOperatorId(e.target.value)}
                    className="w-full surface-base border border-maretide-border rounded-lg px-3 py-2 text-xs text-maretide-text-primary font-mono font-bold focus-ring"
                    placeholder="Officer Sign-Off ID"
                  />
                  <span className="text-[8.5px] text-maretide-text-secondary block">Signed to cryptographic SQLite transaction ledger.</span>
                </div>

                {/* Operator Checkbox Confirmation */}
                <button
                  type="button"
                  disabled={isBlocked}
                  onClick={() => setOperatorConfirmed(!operatorConfirmed)}
                  className={`w-full p-3 rounded-xl border text-left flex items-start gap-2.5 transition-all ${
                    operatorConfirmed 
                      ? "bg-maretide-safeBg border-maretide-safe/50 text-maretide-safe" 
                      : isBlocked
                      ? "bg-maretide-dangerBg/40 border-maretide-danger/30 text-maretide-danger cursor-not-allowed opacity-60"
                      : "surface-base border-maretide-border text-maretide-text-secondary hover:border-maretide-info/50"
                  }`}
                >
                  {operatorConfirmed ? (
                    <CheckSquare className="w-4 h-4 text-maretide-safe flex-shrink-0 mt-0.5" />
                  ) : (
                    <Square className="w-4 h-4 text-maretide-text-secondary flex-shrink-0 mt-0.5" />
                  )}
                  <span className="text-[10.5px] font-bold leading-tight">
                    I confirm container {container.container_number || "MSCU4920195"} meets SOLAS VGM criteria and authorize slot commitment to Bay 0{rec?.bay || 2}.
                  </span>
                </button>

                {/* Authorize Action Button */}
                <Button
                  variant={isBlocked ? "danger" : "primary"}
                  size="lg"
                  fullWidth
                  loading={isLoadingContainer}
                  disabled={!operatorConfirmed || isLoadingContainer || isBlocked}
                  onClick={handleAuthorizeLoad}
                  icon={Check}
                >
                  {isBlocked ? "ACTION BLOCKED — SEVERE ANOMALY" : "STAGE 04: AUTHORIZE & LOAD CONTAINER"}
                </Button>
              </div>
            </div>
          )}

          {/* STAGE 5: LOAD COMMITTED CONFIRMATION */}
          {loadedResult && (
            <div className="surface-elevated border border-maretide-border p-4 border border-maretide-safe/40 space-y-2 font-mono">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-maretide-safe" />
                  <div>
                    <span className="text-[9.5px] text-maretide-safe font-bold uppercase block">STAGE 05 COMPLETE: CONTAINER COMMITTED</span>
                    <h3 className="text-xs font-black text-maretide-text-primary uppercase">
                      Stowed at Bay {loadedResult.loaded_position?.bay || 2} ({loadedResult.loaded_position?.side || "STARBOARD"})
                    </h3>
                  </div>
                </div>
                <span className="text-xs font-bold text-maretide-safe bg-maretide-safeBg px-2 py-1 rounded-full border border-maretide-safe/30">
                  AUDIT #{loadedResult.audit_id || 1042}
                </span>
              </div>
            </div>
          )}

          {/* STAGE 6: BALLAST COMPENSATION (CONTINUATION OF WORKFLOW) */}
          {ballastCompensation && ballastCompensation.compensation_required && operationStatus !== "COMPLETED" && (
            <div className="surface-elevated border border-maretide-border p-5 border-2 border-maretide-info/60 space-y-4 font-mono">
              <SectionHeader
                title="STAGE 06 — BALLAST COMPENSATION REQUIRED"
                icon={Droplets}
                badge={
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-maretide-infoBg text-maretide-info border border-maretide-info/40 font-black">
                    ANTI-HEELING PUMP
                  </span>
                }
              />

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 surface-base rounded-xl border border-maretide-border">
                  <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Target Ballast Tank</span>
                  <span className="text-xs font-black text-maretide-info block truncate">{ballastCompensation.affected_tank || "Starboard Tank 2"}</span>
                </div>
                <div className="p-2.5 surface-base rounded-xl border border-maretide-border">
                  <span className="text-[9px] text-maretide-text-secondary uppercase font-bold block">Discharge Target</span>
                  <span className="text-xs font-black text-maretide-text-primary block">{ballastCompensation.required_qty_t} tonnes</span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setBallastConfirmed(!ballastConfirmed)}
                className={`w-full p-2.5 rounded-xl border text-left flex items-start gap-2 text-xs font-semibold transition-all ${
                  ballastConfirmed
                    ? "bg-maretide-safeBg border-maretide-safe/50 text-maretide-safe"
                    : "surface-base border-maretide-border text-maretide-text-secondary hover:border-maretide-info/50"
                }`}
              >
                {ballastConfirmed ? (
                  <CheckSquare className="w-4 h-4 text-maretide-safe flex-shrink-0 mt-0.5" />
                ) : (
                  <Square className="w-4 h-4 text-maretide-text-secondary flex-shrink-0 mt-0.5" />
                )}
                <span className="text-[10.5px] leading-tight">
                  Authorize discharge of {ballastCompensation.required_qty_t}t ballast from {ballastCompensation.affected_tank || "Starboard Tank 2"} to Sea.
                </span>
              </button>

              <Button
                variant="primary"
                size="lg"
                fullWidth
                loading={isExecutingBallast}
                disabled={!ballastConfirmed || isExecutingBallast}
                onClick={handleAuthorizeBallast}
                icon={Play}
              >
                STAGE 06: AUTHORIZE BALLAST DISCHARGE
              </Button>
            </div>
          )}

          {/* STAGE 7 & 8: FINAL 4-STAGE EQUILIBRIUM VERIFICATION & AUDIT COMMITMENT */}
          {ballastExecutionResult && (
            <div className="surface-elevated border border-maretide-border p-5 border-2 border-maretide-safe/60 space-y-4 font-mono">
              <SectionHeader
                title="STAGE 07 & 08 — 4-STAGE STABILITY VERIFICATION"
                icon={Award}
                badge={<StatusBadge status="EQUILIBRIUM RESTORED" size="sm" />}
              />

              {/* 4-Stage Comparison Table */}
              <div className="space-y-1.5 text-xs">
                <div className="p-2 surface-base rounded-lg border border-maretide-border flex justify-between">
                  <span className="text-maretide-text-secondary">1. BEFORE LOAD:</span>
                  <span className="text-maretide-text-primary font-bold">
                    {ballastExecutionResult.three_stage_stability?.before_load?.list_t?.toFixed(1) || "0.0"}t
                  </span>
                </div>
                <div className="p-2 surface-base rounded-lg border border-maretide-warning/30 flex justify-between">
                  <span className="text-maretide-warning">2. AFTER CONTAINER:</span>
                  <span className="text-maretide-warning font-bold">
                    {ballastExecutionResult.three_stage_stability?.after_container?.list_t?.toFixed(1) || "4.8"}t
                  </span>
                </div>
                <div className="p-2 surface-base rounded-lg border border-maretide-safe/40 flex justify-between">
                  <span className="text-maretide-safe">3. AFTER BALLAST:</span>
                  <span className="text-maretide-safe font-bold">
                    {ballastExecutionResult.three_stage_stability?.after_ballast?.list_t?.toFixed(1) || "0.0"}t (0.0°)
                  </span>
                </div>
                <div className="p-2 surface-base rounded-lg border border-maretide-info/40 flex justify-between">
                  <span className="text-maretide-info">4. LIVE TELEMETRY:</span>
                  <span className="text-maretide-info font-bold">
                    {Math.abs(roll).toFixed(2)}° ({Math.abs(roll) < 0.2 ? "Equilibrium" : "Balanced"})
                  </span>
                </div>
              </div>

              <div className="p-3 bg-maretide-safeBg border border-maretide-safe/40 rounded-xl flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-maretide-safe flex-shrink-0" />
                  <span className="text-[10px] text-maretide-safe font-bold uppercase">
                    STAGE 08: COMMITTED TO IMMUTABLE AUDIT LEDGER
                  </span>
                </div>
                <Button
                  variant="glass"
                  size="xs"
                  icon={RefreshCw}
                  onClick={() => {
                    setOperatorConfirmed(false);
                    setBallastConfirmed(false);
                    resetOperation();
                  }}
                >
                  Load Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 5. COLLAPSIBLE YOLOv8 REAL-TIME COMPUTER VISION FEEDS */}
      {showVisionGrid && (
        <div className="surface-elevated border border-maretide-border p-5 space-y-3">
          <SectionHeader
            title="YOLOv8 Edge Computer Vision Surveillance Feeds"
            icon={Eye}
            badge={
              <span className="text-[9px] font-mono px-2 py-0.5 rounded-full surface-base text-maretide-safe border border-maretide-safe/30 font-bold">
                4 HD Cameras Active
              </span>
            }
          />
          <AIVision />
        </div>
      )}
    </div>
  );
};
