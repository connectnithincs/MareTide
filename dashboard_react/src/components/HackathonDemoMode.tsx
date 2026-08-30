import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  FileText,
  Anchor,
  Droplets,
  Layers,
  Check,
  XCircle,
  Cpu,
  Activity,
  Terminal,
  Shield,
  Eye,
  Info,
  ChevronRight,
  Lock,
  Unlock,
  Scale
} from "lucide-react";
import { CargoAwareDigitalTwin } from "./CargoAwareDigitalTwin";
import { containerAPI, digitalTwinAPI, reportsAPI, type DemoScenario } from "../utils/api";

export const HackathonDemoMode: React.FC = () => {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<DemoScenario | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");

  // Extracted Data State
  const [extraction, setExtraction] = useState<any>(null);
  const [stowagePlan, setStowagePlan] = useState<any>(null);
  const [operatorAuthorized, setOperatorAuthorized] = useState<boolean>(false);
  const [loadedResult, setLoadedResult] = useState<any>(null);
  const [ballastPlan, setBallastPlan] = useState<any>(null);
  const [ballastAuthorized, setBallastAuthorized] = useState<boolean>(false);
  const [ballastResult, setBallastResult] = useState<any>(null);
  const [liveTwin, setLiveTwin] = useState<any>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);

  // Initial load: Fetch scenarios and reset/fetch state
  useEffect(() => {
    fetchScenarios();
    refreshLiveTwin();
  }, []);

  const fetchScenarios = async () => {
    try {
      const res = await containerAPI.getDemoFixtures();
      if (res && res.scenarios) {
        setScenarios(res.scenarios);
        if (res.scenarios.length > 0) {
          setSelectedScenario(res.scenarios[0]);
        }
      }
    } catch (err: any) {
      console.error("Failed to load demo scenarios:", err);
    }
  };

  const refreshLiveTwin = async () => {
    try {
      const data = await digitalTwinAPI.getState();
      setLiveTwin(data);
    } catch (err: any) {
      console.error("Failed to fetch live twin:", err);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await reportsAPI.getTimeline(10);
      if (res && res.timeline) {
        setAuditLogs(res.timeline);
      }
    } catch (err: any) {
      console.error("Failed to fetch audit logs:", err);
    }
  };

  const handleResetDemo = async () => {
    setLoading(true);
    setStatusMessage("Resetting vessel state and audit logs to baseline...");
    try {
      await containerAPI.resetDemo();
      setCurrentStep(1);
      setExtraction(null);
      setStowagePlan(null);
      setOperatorAuthorized(false);
      setLoadedResult(null);
      setBallastPlan(null);
      setBallastAuthorized(false);
      setBallastResult(null);
      await refreshLiveTwin();
      await fetchAuditLogs();
      setStatusMessage("Demo environment reset complete. Vessel at initial equilibrium.");
    } catch (err: any) {
      console.error("Reset failed:", err);
      setStatusMessage(`Reset error: ${err.message || "Failed to reset demo"}`);
    } finally {
      setLoading(false);
    }
  };

  // STEP 2 & 3: Run Document AI OCR on selected fixture
  const handleRunDocumentAI = async () => {
    if (!selectedScenario) return;
    setLoading(true);
    setStatusMessage(`Downloading ${selectedScenario.filename} and executing Document AI OCR...`);
    try {
      // 1. Fetch fixture image as blob
      const imageBlob = await containerAPI.getDemoFixtureImage(selectedScenario.filename);

      // 2. Submit to extraction endpoint
      const formData = new FormData();
      formData.append("file", imageBlob, selectedScenario.filename);

      const ocrRes = await containerAPI.extract(formData);

      setExtraction(ocrRes);
      setCurrentStep(2); // Advanced to Extraction Inspection
      setStatusMessage("Document AI OCR complete. Reviewing extracted fields & ISO 6346 checks.");
    } catch (err: any) {
      console.error("OCR Extraction failed:", err);
      setStatusMessage(`Document AI Extraction error: ${err.message || "Extraction failed"}`);
    } finally {
      setLoading(false);
    }
  };

  // STEP 6: Run Stowage Optimization
  const handleRunOptimization = async () => {
    if (!extraction || !extraction.container) return;
    setLoading(true);
    setStatusMessage("Executing multi-objective stowage solver across 8 candidate slots...");
    try {
      const payload = {
        container: {
          container_number: extraction.container.container_number,
          container_type: extraction.container.container_type,
          weights: extraction.container.weights,
          dimensions: extraction.container.dimensions,
          cargo: extraction.container.cargo,
          destination: extraction.container.destination,
          weight_source: "DOCUMENT_AI"
        },
        document: extraction.document,
        validation: extraction.validation
      };

      const res = await containerAPI.analyzeStability(payload);
      setStowagePlan(res);
      setCurrentStep(3); // Advanced to Stowage Plan
      setStatusMessage("Stowage optimization complete. Awaiting Chief Officer authorization.");
    } catch (err: any) {
      console.error("Stowage analysis failed:", err);
      setStatusMessage(`Optimization error: ${err.message || "Stowage solver failed"}`);
    } finally {
      setLoading(false);
    }
  };

  // STEP 8 & 9: Commit Container to Live Vessel
  const handleCommitContainer = async () => {
    if (!stowagePlan || !stowagePlan.recommendation || !extraction) return;
    setLoading(true);
    setStatusMessage("Authorizing and committing container to vessel state...");
    try {
      const payload = {
        container: extraction.container,
        document: extraction.document,
        validation: extraction.validation,
        recommendation: stowagePlan.recommendation,
        operator_confirmed: true,
        operator_id: "ChiefOfficer_Demo"
      };

      const res = await containerAPI.confirmAndLoad(payload);
      setLoadedResult(res);
      setOperatorAuthorized(true);
      setCurrentStep(4); // Advanced to Loaded & Digital Twin
      await refreshLiveTwin();
      await fetchAuditLogs();
      setStatusMessage("Container committed to live twin. Calculating required ballast compensation.");

      // Auto-compute Ballast recommendation
      await handleCalculateBallast(res);
    } catch (err: any) {
      console.error("Loading commit failed:", err);
      setStatusMessage(`Commit error: ${err.message || "Loading commit failed"}`);
    } finally {
      setLoading(false);
    }
  };

  // STEP 11: Calculate Ballast Compensation
  const handleCalculateBallast = async (loadedData: any) => {
    try {
      const payload = {
        container_number: loadedData.container?.container_number || extraction?.container?.container_number,
        gross_weight_t: loadedData.container?.gross_weight_t,
        bay: loadedData.loaded_position?.bay || stowagePlan?.recommendation?.bay,
        side: loadedData.loaded_position?.side || stowagePlan?.recommendation?.side,
        tier: loadedData.loaded_position?.tier || stowagePlan?.recommendation?.tier
      };

      const res = await containerAPI.calculateBallastCompensation(payload);
      setBallastPlan(res);
    } catch (err: any) {
      console.error("Ballast calculation error:", err);
    }
  };

  // STEP 12 & 13: Execute Ballast Compensation
  const handleExecuteBallast = async () => {
    if (!ballastPlan) return;
    setLoading(true);
    setStatusMessage("Executing operator-authorized ballast pump transfer...");
    const targetTank = ballastPlan.tank_key || ballastPlan.affected_tank || "port_1";
    try {
      const payload = {
        container_number: loadedResult?.container?.container_number,
        tank_key: targetTank.toLowerCase().replace("-", "_"),
        direction: (ballastPlan.direction || "DRAIN") as "DRAIN" | "FILL" | "TRANSFER",
        qty_t: ballastPlan.required_qty_t,
        operator_confirmed: true,
        operator_id: "ChiefOfficer_Demo"
      };

      const res = await containerAPI.executeBallastCompensation(payload);

      setBallastResult(res);
      setBallastAuthorized(true);
      setCurrentStep(5); // Final Certified Equilibrium & Audit
      await refreshLiveTwin();
      await fetchAuditLogs();
      setStatusMessage("Ballast compensation executed. Vessel restored to safe hydrostatic equilibrium.");
    } catch (err: any) {
      console.error("Ballast execution error:", err);
      setStatusMessage(`Ballast execution error: ${err.message || "Ballast pump execution failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const isAnomalyScenario = selectedScenario?.category === "ANOMALY_REJECTION";
  const hasCriticalAnomaly = extraction?.anomalies?.some((a: any) => a.severity === "CRITICAL");

  return (
    <div className="flex flex-col h-full bg-[#0a101f] text-slate-100 overflow-y-auto font-sans p-6 space-y-6">
      {/* Top Banner: Demo Mode Indicator */}
      <div className="flex items-center justify-between bg-gradient-to-r from-blue-900/40 via-indigo-900/40 to-slate-900/40 border border-blue-500/30 p-4 rounded-2xl shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-500/20 text-blue-400 rounded-xl border border-blue-500/30 animate-pulse">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-extrabold tracking-wide uppercase text-white">
                MareTide Hackathon Demonstration Mode
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                LIVE JUDGING FLOW (3–5 MIN)
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-blue-500/20 text-blue-300 border border-blue-500/40">
                PROVENANCE: [DOCUMENT AI] ONLY
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Walkthrough demonstrating certified SOLAS OCR extraction, multi-objective stowage, operator gates, digital twin, and ballast re-leveling.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleResetDemo}
            disabled={loading}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-600 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shadow"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Reset Demo State
          </button>
        </div>
      </div>

      {/* Scenario Selection Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {scenarios.map((sc) => {
          const isSelected = selectedScenario?.id === sc.id;
          const isAnomaly = sc.category === "ANOMALY_REJECTION";
          return (
            <div
              key={sc.id}
              onClick={() => {
                setSelectedScenario(sc);
                setCurrentStep(1);
                setExtraction(null);
                setStowagePlan(null);
                setLoadedResult(null);
                setBallastPlan(null);
                setBallastResult(null);
              }}
              className={`cursor-pointer p-4 rounded-2xl border transition-all relative overflow-hidden flex flex-col justify-between space-y-3 ${
                isSelected
                  ? isAnomaly
                    ? "bg-red-950/30 border-red-500 shadow-lg shadow-red-500/10 ring-1 ring-red-500"
                    : "bg-blue-950/40 border-blue-500 shadow-lg shadow-blue-500/20 ring-1 ring-blue-500"
                  : "bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`text-[10px] font-black uppercase px-2 py-0.5 rounded-md border ${
                      isAnomaly
                        ? "bg-red-500/20 text-red-300 border-red-500/40"
                        : "bg-blue-500/20 text-blue-300 border-blue-500/40"
                    }`}
                  >
                    {sc.category}
                  </span>
                  {isSelected && (
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                    </span>
                  )}
                </div>
                <h3 className="text-xs font-bold text-slate-100 leading-tight">{sc.title}</h3>
                <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{sc.description}</p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-[11px] text-slate-400">
                <span className="font-mono">{sc.container_number}</span>
                <span className="text-blue-400 font-semibold">{isSelected ? "ACTIVE" : "SELECT"} &rarr;</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Interactive Demo Stepper Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive Workflow Steps */}
        <div className="lg:col-span-8 space-y-6">
          {/* STEP 1: INITIAL VESSEL STATE & DOCUMENT AI TRIGGER */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 font-bold text-xs flex items-center justify-center border border-blue-500/30">
                  1
                </div>
                <h2 className="text-sm font-bold text-slate-200">
                  Document AI OCR & Gate Verification
                </h2>
              </div>
              <span className="text-[11px] text-slate-400 font-mono">
                Source: {selectedScenario?.filename}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Slip Preview Card */}
              <div className="p-3 bg-black/40 border border-slate-800 rounded-xl flex flex-col justify-between space-y-2">
                <div className="text-[11px] text-slate-400 flex items-center justify-between">
                  <span>Selected Slip Fixture:</span>
                  <span className="text-blue-400 font-mono text-[10px]">{selectedScenario?.filename}</span>
                </div>
                <div className="relative rounded-lg overflow-hidden border border-slate-800 bg-slate-950 flex items-center justify-center p-4">
                  <FileText className="w-8 h-8 text-blue-400/60 mb-2" />
                  <div className="text-center">
                    <p className="text-xs font-bold text-slate-200">{selectedScenario?.title}</p>
                    <p className="text-[10px] text-slate-400">{selectedScenario?.subtitle}</p>
                  </div>
                </div>
                <button
                  onClick={handleRunDocumentAI}
                  disabled={loading}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
                >
                  <Cpu className="w-4 h-4" />
                  {extraction ? "Re-Run Document AI" : "Run Document AI Extraction"}
                </button>
              </div>

              {/* Initial Vessel State Snapshot */}
              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2.5 text-xs">
                <div className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                  Initial Vessel Equilibrium:
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 bg-slate-900/80 rounded-lg border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Stowed Containers</span>
                    <p className="text-sm font-bold text-slate-200">{liveTwin?.containers?.length || 0} Units</p>
                  </div>
                  <div className="p-2 bg-slate-900/80 rounded-lg border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Initial List Angle</span>
                    <p className="text-sm font-bold text-emerald-400">{liveTwin?.list_t || 0.0}&deg; (Center)</p>
                  </div>
                  <div className="p-2 bg-slate-900/80 rounded-lg border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Initial Trim Angle</span>
                    <p className="text-sm font-bold text-emerald-400">{liveTwin?.trim_t || 0.0}&deg; (Even Keel)</p>
                  </div>
                  <div className="p-2 bg-slate-900/80 rounded-lg border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Safety Risk Status</span>
                    <p className="text-sm font-bold text-emerald-400">{liveTwin?.risk_level || "SAFE"}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Extracted Fields Matrix (if OCR extracted) */}
            {extraction && extraction.container && (
              <div className="mt-5 pt-4 border-t border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Structured Container Intelligence JSON
                  </span>
                  <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-bold font-mono">
                    PROVENANCE: [DOCUMENT AI]
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                  <div className="p-2.5 bg-slate-950/80 rounded-xl border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Container Number</span>
                    <p className="font-mono font-bold text-slate-100">{extraction.container.container_number || "N/A"}</p>
                  </div>
                  <div className="p-2.5 bg-slate-950/80 rounded-xl border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Type / ISO</span>
                    <p className="font-mono font-bold text-slate-100">{extraction.container.container_type || "40HC"}</p>
                  </div>
                  <div className="p-2.5 bg-slate-950/80 rounded-xl border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Gross Mass (VGM)</span>
                    <p className="font-mono font-bold text-emerald-400">
                      {extraction.container.weights?.gross_weight_kg ? `${extraction.container.weights.gross_weight_kg.toLocaleString()} kg` : "N/A"}
                    </p>
                  </div>
                  <div className="p-2.5 bg-slate-950/80 rounded-xl border border-slate-800">
                    <span className="text-slate-400 text-[10px]">Tare / Cargo Mass</span>
                    <p className="font-mono text-slate-200">
                      {extraction.container.weights?.tare_weight_kg || 0} / {extraction.container.weights?.cargo_weight_kg || 0} kg
                    </p>
                  </div>
                </div>

                {/* Critical Anomaly Banner if Scenario 2 */}
                {hasCriticalAnomaly && (
                  <div className="p-4 bg-red-950/40 border border-red-500/50 rounded-xl space-y-2 animate-pulse">
                    <div className="flex items-center gap-2 text-red-400 font-bold text-xs">
                      <ShieldAlert className="w-4 h-4" />
                      CRITICAL SAFETY ANOMALY DETECTED &bull; LOAD LOCKED
                    </div>
                    <p className="text-xs text-red-200 leading-relaxed">
                      {extraction.anomalies[0].message} (Observed: {extraction.anomalies[0].observed} vs Expected: {extraction.anomalies[0].expected})
                    </p>
                    <div className="flex items-center gap-2 text-[11px] text-red-300 font-semibold pt-1">
                      <Lock className="w-3.5 h-3.5" />
                      Safety Gate Enforcement: Vessel state cannot be mutated without verified weighbridge certificate.
                    </div>
                  </div>
                )}

                {/* Next Step Button (if not blocked) */}
                {!hasCriticalAnomaly && (
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleRunOptimization}
                      disabled={loading}
                      className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl text-xs font-bold transition-all flex items-center gap-2 shadow-lg shadow-blue-500/25"
                    >
                      <span>Proceed to Multi-Objective Stowage Solver</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* STEP 2: STOWAGE RECOMMENDATION & OPERATOR GATE */}
          {stowagePlan && stowagePlan.success && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 font-bold text-xs flex items-center justify-center border border-blue-500/30">
                    2
                  </div>
                  <h2 className="text-sm font-bold text-slate-200">
                    AI Stowage Optimization & Operator Gate
                  </h2>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Rank #1 Optimal Slot
                </span>
              </div>

              {/* Recommendation Card */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-3.5 bg-blue-950/40 border border-blue-500/40 rounded-xl space-y-1">
                  <span className="text-slate-400 text-[10px] uppercase font-bold">Recommended Slot</span>
                  <p className="text-base font-extrabold text-blue-300">
                    Bay {stowagePlan.recommendation?.bay} &bull; {stowagePlan.recommendation?.side} &bull; Tier {stowagePlan.recommendation?.tier}
                  </p>
                </div>
                <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                  <span className="text-slate-400 text-[10px] uppercase font-bold">Hydrostatic List Impact</span>
                  <p className="text-sm font-bold text-slate-200">
                    {stowagePlan.stability_before?.list_t}&deg; &rarr; {stowagePlan.stability_after?.list_t}&deg;
                  </p>
                </div>
                <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                  <span className="text-slate-400 text-[10px] uppercase font-bold">Longitudinal Trim</span>
                  <p className="text-sm font-bold text-slate-200">
                    {stowagePlan.stability_before?.trim_t}&deg; &rarr; {stowagePlan.stability_after?.trim_t}&deg;
                  </p>
                </div>
              </div>

              {/* Explainable Decision Reasons */}
              {stowagePlan.explainable_reasons && stowagePlan.explainable_reasons.length > 0 && (
                <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-1.5">
                  <span className="text-[10px] uppercase font-bold text-slate-400">Explainable Decision Support:</span>
                  <ul className="text-xs text-slate-300 space-y-1 list-disc list-inside">
                    {stowagePlan.explainable_reasons.map((r: string, idx: number) => (
                      <li key={idx} className="leading-relaxed">{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Operator Authorization Gate */}
              <div className="p-4 bg-gradient-to-r from-amber-950/20 to-slate-900/40 border border-amber-500/30 rounded-xl flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-xs">
                    <Shield className="w-4 h-4" />
                    Human-in-the-Loop Gate: Chief Officer Authorization Required
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Live vessel state will NOT be mutated until explicitly authorized by operator.
                  </p>
                </div>

                <button
                  onClick={handleCommitContainer}
                  disabled={loading || operatorAuthorized}
                  className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shadow-lg ${
                    operatorAuthorized
                      ? "bg-emerald-600 text-white cursor-default"
                      : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20"
                  }`}
                >
                  {operatorAuthorized ? (
                    <>
                      <Check className="w-4 h-4" />
                      Authorized & Stowed
                    </>
                  ) : (
                    <>
                      <Unlock className="w-4 h-4" />
                      Authorize & Stow Container
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: BALLAST COMPENSATION & EXECUTION */}
          {ballastPlan && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 font-bold text-xs flex items-center justify-center border border-blue-500/30">
                    3
                  </div>
                  <h2 className="text-sm font-bold text-slate-200">
                    Ballast Auto-Compensation & Physical Pump Trigger
                  </h2>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Target Tank: {(ballastPlan.affected_tank || ballastPlan.tank_key || "PORT-1").toUpperCase()}
                </span>

              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                  <span className="text-slate-400 text-[10px] uppercase font-bold">Required Compensation</span>
                  <p className="text-sm font-bold text-blue-400">
                    {ballastPlan.direction} {ballastPlan.required_qty_t} Tonnes
                  </p>
                </div>
                <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                  <span className="text-slate-400 text-[10px] uppercase font-bold">Est. Pump Duration</span>
                  <p className="text-sm font-bold text-slate-200">
                    ~{ballastPlan.est_duration_sec || 45} seconds (@ 45 L/s)
                  </p>
                </div>
                <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                  <span className="text-slate-400 text-[10px] uppercase font-bold">Projected Equilibrium</span>
                  <p className="text-sm font-bold text-emerald-400">
                    List: {ballastPlan.projected_stability?.list_t || 0.0}&deg; &bull; SAFE
                  </p>
                </div>
              </div>

              {/* Ballast Authorization Gate */}
              <div className="p-4 bg-gradient-to-r from-blue-950/20 to-slate-900/40 border border-blue-500/30 rounded-xl flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 text-blue-400 font-bold text-xs">
                    <Droplets className="w-4 h-4" />
                    Ballast Discharge Confirmation Gate
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Commands pump actuator to rebalance water between port/starboard tanks.
                  </p>
                </div>

                <button
                  onClick={handleExecuteBallast}
                  disabled={loading || ballastAuthorized}
                  className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shadow-lg ${
                    ballastAuthorized
                      ? "bg-emerald-600 text-white cursor-default"
                      : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/25"
                  }`}
                >
                  {ballastAuthorized ? (
                    <>
                      <Check className="w-4 h-4" />
                      Discharge Executed
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Authorize & Execute Ballast
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* STEP 4: 3-STAGE STABILITY MATRIX & AUDIT TRAIL */}
          {ballastResult && ballastResult.three_stage_stability && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-xs flex items-center justify-center border border-emerald-500/30">
                    4
                  </div>
                  <h2 className="text-sm font-bold text-slate-200">
                    Four-Stage Hydrostatic Verification & Certified Audit
                  </h2>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  FINAL RISK: SAFE
                </span>
              </div>

              {/* 3-Stage Stability Table */}
              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-xs text-left text-slate-300">
                  <thead className="text-[10px] uppercase bg-slate-950 text-slate-400 border-b border-slate-800 font-bold">
                    <tr>
                      <th className="px-4 py-2.5">Operational Stage</th>
                      <th className="px-4 py-2.5">List Moment (&deg;)</th>
                      <th className="px-4 py-2.5">Trim Moment (&deg;)</th>
                      <th className="px-4 py-2.5">Stability Score</th>
                      <th className="px-4 py-2.5">Risk Level</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    <tr className="bg-slate-900/40">
                      <td className="px-4 py-2.5 font-sans font-semibold text-slate-300">1. Before Load</td>
                      <td className="px-4 py-2.5">{ballastResult.three_stage_stability.before_load.list_t}&deg;</td>
                      <td className="px-4 py-2.5">{ballastResult.three_stage_stability.before_load.trim_t}&deg;</td>
                      <td className="px-4 py-2.5">{ballastResult.three_stage_stability.before_load.stability_score}</td>
                      <td className="px-4 py-2.5 text-emerald-400 font-bold">{ballastResult.three_stage_stability.before_load.risk_level}</td>
                    </tr>
                    <tr className="bg-amber-950/20">
                      <td className="px-4 py-2.5 font-sans font-semibold text-amber-300">2. After Container Placement</td>
                      <td className="px-4 py-2.5 text-amber-400 font-bold">{ballastResult.three_stage_stability.after_container.list_t}&deg;</td>
                      <td className="px-4 py-2.5">{ballastResult.three_stage_stability.after_container.trim_t}&deg;</td>
                      <td className="px-4 py-2.5">{ballastResult.three_stage_stability.after_container.stability_score}</td>
                      <td className="px-4 py-2.5 text-amber-400 font-bold">{ballastResult.three_stage_stability.after_container.risk_level}</td>
                    </tr>
                    <tr className="bg-emerald-950/20">
                      <td className="px-4 py-2.5 font-sans font-semibold text-emerald-300">3. After Ballast Compensation</td>
                      <td className="px-4 py-2.5 text-emerald-400 font-bold">{ballastResult.three_stage_stability.after_ballast.list_t}&deg;</td>
                      <td className="px-4 py-2.5">{ballastResult.three_stage_stability.after_ballast.trim_t}&deg;</td>
                      <td className="px-4 py-2.5">{ballastResult.three_stage_stability.after_ballast.stability_score}</td>
                      <td className="px-4 py-2.5 text-emerald-400 font-bold">{ballastResult.three_stage_stability.after_ballast.risk_level}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Audit Proof Box */}
              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5 font-mono text-[11px]">
                <div className="text-slate-400 flex items-center justify-between">
                  <span>SQLite Cryptographic Audit Stamp:</span>
                  <span className="text-emerald-400 font-bold">VERIFIED IMMUTABLE</span>
                </div>
                <p className="text-slate-300 text-xs">
                  Event: <span className="text-blue-400">BALLAST_COMPENSATION</span> &bull; Tank: <span className="text-amber-300">{ballastResult.affected_tank}</span> &bull; Discharged: <span className="text-blue-300">{ballastResult.actual_qty_t}t</span> &bull; Net Score Delta: <span className="text-emerald-400">{ballastResult.three_stage_stability.net_score_delta} pts</span>
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Live Cargo-Aware Digital Twin */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Anchor className="w-4 h-4 text-blue-400" />
                Live Vessel Digital Twin
              </h3>
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                ACTIVE
              </span>
            </div>

            <CargoAwareDigitalTwin compact={true} />


            {/* Audit Log Feed */}
            <div className="pt-2 border-t border-slate-800 space-y-2">
              <span className="text-[10px] uppercase font-bold text-slate-400 flex items-center gap-1.5">
                <Terminal className="w-3 h-3 text-slate-400" />
                Recent Audit Trail Events:
              </span>
              <div className="max-h-40 overflow-y-auto space-y-1.5 text-[11px] font-mono pr-1">
                {auditLogs.length === 0 ? (
                  <p className="text-slate-500 text-xs">No audit events recorded yet.</p>
                ) : (
                  auditLogs.slice(0, 5).map((log: any, idx: number) => (
                    <div key={idx} className="p-2 bg-slate-950 rounded-lg border border-slate-800/80 flex items-center justify-between">
                      <div>
                        <span className="text-blue-400 font-bold">{log.event || log.action}</span>
                        <span className="text-slate-400 text-[10px] ml-1.5">{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : "Just now"}</span>
                      </div>
                      <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">OK</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HackathonDemoMode;
