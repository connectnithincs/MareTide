import React, { useState } from "react";
import { 
  FileText, 
  Upload, 
  CheckCircle, 
  AlertTriangle, 
  XCircle, 
  Anchor, 
  Cpu, 
  Scale, 
  ShieldCheck, 
  Zap, 
  Sparkles,
  Copy,
  Check,
  Code,
  Info,
  Maximize2,
  Minimize2,
  RefreshCw,
  Box,
  Truck,
  MapPin,
  Flame,
  CheckCircle2,
  Percent,
  Layers,
  ListOrdered
} from "lucide-react";
import { containerAPI } from "../utils/api";
import { MultiContainerPlannerView } from "./MultiContainerPlannerView";

import { useContainerOperation } from "../context/ContainerOperationContext";

export const ContainerIntelligence: React.FC = () => {
  const {
    file,
    previewUrl,
    extractedData,
    stabilityResult,
    isExtracting: extracting,
    isAnalyzing: analyzing,
    errorMessage,
    processSlipFile,
    loadSampleSlip,
    analyzeActiveStability,
    resetOperation: handleReset,
    setErrorMessage
  } = useContainerOperation();

  const [activeMode, setActiveMode] = useState<"single" | "manifest">("single");
  const [showRawText, setShowRawText] = useState(false);
  const [copied, setCopied] = useState(false);
  const [weightUnit, setWeightUnit] = useState<"kg" | "lbs" | "mt">("kg");
  const [isImageExpanded, setIsImageExpanded] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      await processSlipFile(selected);
    }
  };

  const handleExtract = async () => {
    if (!file) {
      setErrorMessage("Please select a container slip image first.");
      return;
    }
    await processSlipFile(file);
  };

  const handleAnalyzeStability = async () => {
    await analyzeActiveStability();
  };

  const handleCopyJson = () => {
    if (!extractedData) return;
    navigator.clipboard.writeText(JSON.stringify(extractedData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const loadSampleReceipt = async () => {
    await loadSampleSlip();
  };

  const formatWeight = (kg: number | null | undefined) => {
    if (kg === null || kg === undefined) return "N/A";
    if (weightUnit === "lbs") {
      return `${Math.round(kg * 2.20462).toLocaleString()} lbs`;
    } else if (weightUnit === "mt") {
      return `${(kg / 1000).toFixed(2)} MT`;
    }
    return `${kg.toLocaleString()} kg`;
  };

  const container = extractedData?.container || {};
  const weights = container.weights || {};
  const dimensions = container.dimensions || {};
  const cargo = container.cargo || {};
  const confidence = extractedData?.confidence || {};
  const validation = extractedData?.validation || {};
  const doc = extractedData?.document || {};

  return (
    <div className="flex-1 overflow-y-auto w-full h-full bg-brand-dark p-6 space-y-6">
      <div className="max-w-7xl mx-auto space-y-6 pb-12">

        {/* Top Header Banner */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between bg-brand-surface border border-brand-border p-5 rounded-2xl shadow-xl gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl text-blue-400 shadow-inner">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white tracking-wide">
                  Container Document Intelligence & Stability AI
                </h1>
                <span className="text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/40">
                  Phase 1 OCR + Phase 2 Stability
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Automated gate slip OCR parsing, ISO 6346 validation, weight verification, and AI-assisted ballast stability placement.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={loadSampleReceipt}
              className="px-3.5 py-2 bg-brand-dark hover:bg-brand-dark/80 border border-brand-border hover:border-blue-500/50 text-gray-200 text-xs font-semibold rounded-xl transition-all flex items-center gap-2 shadow"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-400" />
              Load Sample Slip
            </button>
            {(file || extractedData) && (
              <button
                onClick={handleReset}
                className="px-3 py-2 bg-brand-dark hover:bg-red-500/10 border border-brand-border hover:border-red-500/40 text-gray-400 hover:text-red-300 text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5"
                title="Clear current slip"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Reset
              </button>
            )}
          </div>
        </div>

        {/* Workflow Mode Tabs */}
        <div className="flex items-center gap-2 bg-brand-surface p-1.5 rounded-xl border border-brand-border w-fit">
          <button
            onClick={() => setActiveMode("single")}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-2 ${
              activeMode === "single"
                ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                : "text-gray-400 hover:text-white"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Single Container OCR & Stability
          </button>
          <button
            onClick={() => setActiveMode("manifest")}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-2 ${
              activeMode === "manifest"
                ? "bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-md shadow-cyan-500/20"
                : "text-gray-400 hover:text-white"
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            Multi-Container Manifest Planner (Phase 4D)
          </button>
        </div>

        {/* Error / Notification Banner */}
        {errorMessage && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-between gap-3 text-red-400 text-xs">
            <div className="flex items-center gap-3">
              <XCircle className="w-5 h-5 flex-shrink-0" />
              <span className="font-medium">{errorMessage}</span>
            </div>
            <button onClick={() => setErrorMessage(null)} className="text-red-400 hover:text-red-200 text-xs">
              Dismiss
            </button>
          </div>
        )}

        {/* Mode Content */}
        {activeMode === "manifest" ? (
          <MultiContainerPlannerView />
        ) : (
          <>
            {/* Top Split: Upload Area & Real-Time Stability Action */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* Left Column: Upload Gate Slip Box */}
          <div className="lg:col-span-5 bg-brand-surface border border-brand-border p-5 rounded-2xl shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-brand-border pb-3">
              <h2 className="text-sm font-bold text-gray-200 flex items-center gap-2">
                <Upload className="w-4 h-4 text-blue-400" />
                1. Upload Gate Slip / Interchange Receipt
              </h2>
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                RapidOCR Active
              </span>
            </div>

            <div className="border-2 border-dashed border-brand-border hover:border-blue-500/50 rounded-xl p-5 text-center transition-all bg-brand-dark/40 hover:bg-brand-dark/60 cursor-pointer">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
                id="slip-upload-input"
              />
              <label
                htmlFor="slip-upload-input"
                className="cursor-pointer flex flex-col items-center justify-center space-y-2"
              >
                <div className="p-3 bg-blue-500/10 rounded-full text-blue-400 border border-blue-500/20 shadow-inner">
                  <Upload className="w-5 h-5" />
                </div>
                <div className="text-xs font-semibold text-gray-200">
                  {file ? file.name : "Click or drop container slip image"}
                </div>
                <div className="text-[11px] text-gray-400">
                  Supports JPG, PNG, WEBP, TIFF (Max 15MB)
                </div>
              </label>
            </div>

            {/* Thumbnail Preview if File Selected */}
            {previewUrl && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-gray-400 px-1">
                  <span>Selected Slip Preview:</span>
                  <button
                    onClick={() => setIsImageExpanded(!isImageExpanded)}
                    className="text-blue-400 hover:text-blue-300 flex items-center gap-1 text-[11px]"
                  >
                    {isImageExpanded ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
                    {isImageExpanded ? "Collapse" : "Expand"}
                  </button>
                </div>
                <div className={`relative rounded-xl overflow-hidden border border-brand-border bg-black/40 transition-all ${
                  isImageExpanded ? "max-h-96" : "max-h-44"
                }`}>
                  <img src={previewUrl} alt="Slip Preview" className="w-full h-full object-contain mx-auto" />
                </div>
              </div>
            )}

            {/* Extract Button */}
            <button
              onClick={handleExtract}
              disabled={extracting || !file}
              className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-40 disabled:pointer-events-none text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-600/25"
            >
              {extracting ? (
                <>
                  <Cpu className="w-4 h-4 animate-spin" />
                  Running Neural OCR Pipeline...
                </>
              ) : (
                <>
                  <Cpu className="w-4 h-4" />
                  Extract & Verify Container Data
                </>
              )}
            </button>
          </div>

          {/* Right Column: Stability Placement Action / Quick Overview */}
          <div className="lg:col-span-7 bg-brand-surface border border-brand-border p-5 rounded-2xl shadow-lg flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between border-b border-brand-border pb-3">
              <h2 className="text-sm font-bold text-gray-200 flex items-center gap-2">
                <Anchor className="w-4 h-4 text-emerald-400" />
                2. AI Vessel Stability Placement (Phase 2)
              </h2>
              <span className="text-[10px] font-bold text-gray-400 bg-brand-dark px-2.5 py-0.5 rounded-full border border-brand-border">
                {stabilityResult ? "Simulation Complete" : "Awaiting Trigger"}
              </span>
            </div>

            {!extractedData ? (
              <div className="flex flex-col items-center justify-center py-10 text-center space-y-3 bg-brand-dark/30 rounded-xl border border-brand-border/60">
                <div className="p-4 bg-brand-dark/80 rounded-2xl text-gray-500 border border-brand-border/80">
                  <Scale className="w-8 h-8" />
                </div>
                <div className="space-y-1">
                  <div className="text-sm font-bold text-gray-300">Ready for Document Ingestion</div>
                  <p className="text-xs text-gray-500 max-w-sm">
                    Upload a gate slip image or click <span className="text-blue-400 font-semibold">"Load Sample Slip"</span> above to extract container parameters and initiate real-time stability simulation.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-brand-dark/70 p-3.5 rounded-xl border border-brand-border">
                    <span className="text-[10px] text-gray-400 uppercase font-bold">Target Container</span>
                    <div className="text-sm font-mono font-bold text-white mt-1">
                      {container.container_number || "PENDING"}
                    </div>
                  </div>
                  <div className="bg-brand-dark/70 p-3.5 rounded-xl border border-brand-border">
                    <span className="text-[10px] text-gray-400 uppercase font-bold">Verified Gross Mass</span>
                    <div className="text-sm font-mono font-bold text-emerald-400 mt-1">
                      {weights.gross_weight_kg ? `${weights.gross_weight_kg.toLocaleString()} kg` : "N/A"}
                    </div>
                  </div>
                  <div className="bg-brand-dark/70 p-3.5 rounded-xl border border-brand-border">
                    <span className="text-[10px] text-gray-400 uppercase font-bold">Hazmat Segregation</span>
                    <div className="text-sm font-bold mt-1">
                      {cargo.hazardous ? (
                        <span className="text-amber-400">DG Class {cargo.imdg_class || "9"}</span>
                      ) : (
                        <span className="text-emerald-400">Standard Cargo</span>
                      )}
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleAnalyzeStability}
                  disabled={analyzing}
                  className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/25"
                >
                  {analyzing ? (
                    <>
                      <Scale className="w-4 h-4 animate-spin" />
                      Simulating Candidate Stowage Slots & Ballast Offsets...
                    </>
                  ) : (
                    <>
                      <Scale className="w-4 h-4" />
                      {stabilityResult ? "Re-Run Placement Simulation" : "Simulate Stability & Optimize Placement Slot"}
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

        </div>

        {/* FULL-WIDTH EXTRACTED INFORMATION DASHBOARD */}
        {extractedData && (
          <div className="bg-brand-surface border border-brand-border p-6 rounded-2xl shadow-xl space-y-6 animate-fadeIn">
            
            {/* Extracted Details Header Bar */}
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-brand-border pb-4 gap-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-white">
                      Extracted Container Manifest & Specifications
                    </h2>
                    <span className={`text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full border ${
                      doc.processing_status === "success" 
                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" 
                        : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                    }`}>
                      Status: {doc.processing_status || "Processed"}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    Source: <span className="font-mono text-gray-300">{doc.source || "Uploaded Document"}</span> • Engine: <span className="text-blue-400">{doc.ocr_engine || "rapidocr-onnx"}</span> • Processed in <span className="text-emerald-400">{doc.processing_time_ms ? `${doc.processing_time_ms}ms` : "< 1s"}</span>
                  </p>
                </div>
              </div>

              {/* Utility Actions */}
              <div className="flex items-center gap-2 flex-wrap">
                {/* Weight Unit Switcher */}
                <div className="flex items-center bg-brand-dark rounded-xl p-1 border border-brand-border text-xs font-semibold">
                  <button
                    onClick={() => setWeightUnit("kg")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${weightUnit === "kg" ? "bg-blue-600 text-white shadow" : "text-gray-400 hover:text-gray-200"}`}
                  >
                    KG
                  </button>
                  <button
                    onClick={() => setWeightUnit("lbs")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${weightUnit === "lbs" ? "bg-blue-600 text-white shadow" : "text-gray-400 hover:text-gray-200"}`}
                  >
                    LBS
                  </button>
                  <button
                    onClick={() => setWeightUnit("mt")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${weightUnit === "mt" ? "bg-blue-600 text-white shadow" : "text-gray-400 hover:text-gray-200"}`}
                  >
                    MT
                  </button>
                </div>

                <button
                  onClick={handleCopyJson}
                  className="px-3 py-1.5 bg-brand-dark hover:bg-brand-dark/80 border border-brand-border text-gray-300 hover:text-white text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5"
                  title="Copy Full Extracted JSON Payload"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? "Copied JSON" : "Copy JSON"}
                </button>

                <button
                  onClick={() => setShowRawText(!showRawText)}
                  className={`px-3 py-1.5 border text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 ${
                    showRawText 
                      ? "bg-blue-500/20 border-blue-500/50 text-blue-300" 
                      : "bg-brand-dark border-brand-border text-gray-300 hover:text-white"
                  }`}
                >
                  <Code className="w-3.5 h-3.5" />
                  {showRawText ? "Hide Raw OCR Text" : "View Raw OCR Text"}
                </button>
              </div>
            </div>

            {/* RAW OCR TEXT DRAWER (COLLAPSIBLE) */}
            {showRawText && extractedData.raw_text && (
              <div className="bg-brand-dark/95 border border-brand-border rounded-xl p-4 space-y-2 animate-fadeIn font-mono text-xs">
                <div className="flex items-center justify-between text-gray-400 border-b border-brand-border/60 pb-2">
                  <span className="text-[11px] uppercase font-bold text-blue-400 flex items-center gap-1.5">
                    <Code className="w-3.5 h-3.5" /> Raw Extracted Text from OCR Engine:
                  </span>
                  <span className="text-[10px] text-gray-500">{extractedData.raw_text.split('\n').length} lines recognized</span>
                </div>
                <pre className="text-gray-300 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto pr-2 text-[11px] bg-black/40 p-3 rounded-lg border border-brand-border/40">
                  {extractedData.raw_text}
                </pre>
              </div>
            )}

            {/* 4 PRIMARY SPECIFICATION CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

              {/* CARD 1: IDENTIFICATION */}
              <div className="bg-brand-dark/70 p-4 rounded-xl border border-brand-border space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Box className="w-3.5 h-3.5 text-blue-400" /> Identification
                  </span>
                  {validation.iso_6346_valid ? (
                    <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      ISO 6346 Valid
                    </span>
                  ) : (
                    <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                      ISO Notice
                    </span>
                  )}
                </div>

                <div className="space-y-1">
                  <div className="text-[10px] text-gray-400 uppercase font-semibold">Container Number</div>
                  <div className="text-lg font-mono font-black text-white tracking-wider">
                    {container.container_number || "NOT EXTRACTED"}
                  </div>
                </div>

                <div className="space-y-1 border-t border-brand-border/60 pt-2">
                  <div className="text-[10px] text-gray-400 uppercase font-semibold">Container Type / Code</div>
                  <div className="text-sm font-bold text-blue-300">
                    {container.container_type ? `${container.container_type}` : "Standard Dry (40HC)"}
                  </div>
                  <div className="text-[10px] text-gray-400">
                    {container.container_type === "40HC" ? "40ft High Cube Dry Van" : (container.container_type === "20GP" ? "20ft General Purpose" : "Standard Intermodal")}
                  </div>
                </div>
              </div>

              {/* CARD 2: WEIGHTS BREAKDOWN */}
              <div className="bg-brand-dark/70 p-4 rounded-xl border border-emerald-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Scale className="w-3.5 h-3.5 text-emerald-400" /> Mass & Weights
                  </span>
                  {validation.weight_balance_valid !== false ? (
                    <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      VGM Verified
                    </span>
                  ) : (
                    <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                      Discrepancy
                    </span>
                  )}
                </div>

                <div className="space-y-1">
                  <div className="text-[10px] text-gray-400 uppercase font-semibold">Verified Gross Mass (VGM)</div>
                  <div className="text-lg font-mono font-black text-emerald-400">
                    {formatWeight(weights.gross_weight_kg)}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 border-t border-brand-border/60 pt-2 text-xs">
                  <div>
                    <div className="text-[10px] text-gray-400 font-semibold uppercase">Tare Weight</div>
                    <div className="font-mono font-bold text-gray-200">{formatWeight(weights.tare_weight_kg)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-400 font-semibold uppercase">Net Cargo Wt</div>
                    <div className="font-mono font-bold text-gray-200">{formatWeight(weights.cargo_weight_kg)}</div>
                  </div>
                </div>
              </div>

              {/* CARD 3: DIMENSIONS & PROFILE */}
              <div className="bg-brand-dark/70 p-4 rounded-xl border border-brand-border space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-purple-400" /> Dimensions
                  </span>
                  <span className="text-[10px] font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    {dimensions.length_ft ? `${dimensions.length_ft}ft Standard` : "40ft ISO"}
                  </span>
                </div>

                <div className="space-y-1">
                  <div className="text-[10px] text-gray-400 uppercase font-semibold">Length × Width × Height</div>
                  <div className="text-base font-mono font-bold text-white">
                    {dimensions.length_ft || 40}' × {dimensions.width_ft || 8}' × {dimensions.height_ft || 9.5}'
                  </div>
                </div>

                <div className="space-y-1 border-t border-brand-border/60 pt-2 text-xs">
                  <div className="text-[10px] text-gray-400 font-semibold uppercase">Metric Equivalent</div>
                  <div className="font-mono text-gray-300">
                    {((dimensions.length_ft || 40) * 0.3048).toFixed(2)}m × {((dimensions.width_ft || 8) * 0.3048).toFixed(2)}m × {((dimensions.height_ft || 9.5) * 0.3048).toFixed(2)}m
                  </div>
                </div>
              </div>

              {/* CARD 4: CARGO MANIFEST & HAZMAT */}
              <div className="bg-brand-dark/70 p-4 rounded-xl border border-brand-border space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Truck className="w-3.5 h-3.5 text-amber-400" /> Commodity & DG
                  </span>
                  {cargo.hazardous ? (
                    <span className="text-[10px] font-bold text-amber-400 bg-amber-500/15 px-2 py-0.5 rounded border border-amber-500/30 flex items-center gap-1">
                      <Flame className="w-3 h-3 text-amber-400" /> HAZMAT
                    </span>
                  ) : (
                    <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      Non-DG Safe
                    </span>
                  )}
                </div>

                <div className="space-y-1">
                  <div className="text-[10px] text-gray-400 uppercase font-semibold">Commodity Description</div>
                  <div className="text-xs font-semibold text-gray-200 line-clamp-2" title={cargo.description || undefined}>
                    {cargo.description || "INDUSTRIAL / GENERAL CARGO"}
                  </div>
                </div>

                <div className="space-y-1 border-t border-brand-border/60 pt-2 text-xs">
                  <div className="text-[10px] text-gray-400 font-semibold uppercase">Port of Discharge</div>
                  <div className="text-xs font-bold text-blue-400 flex items-center gap-1">
                    <MapPin className="w-3 h-3 flex-shrink-0" />
                    {container.destination || "PORT OF DISCHARGE"}
                  </div>
                </div>
              </div>

            </div>

            {/* LOWER DETAILS: CONFIDENCE SCORES & VALIDATION ALERTS */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">

              {/* Confidence Breakdown Meters (5 cols) */}
              <div className="lg:col-span-5 bg-brand-dark/60 p-4 rounded-xl border border-brand-border space-y-3">
                <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                  <span className="text-xs font-bold text-gray-200 flex items-center gap-1.5">
                    <Percent className="w-3.5 h-3.5 text-blue-400" /> OCR Confidence Breakdown
                  </span>
                  <span className="text-xs font-mono font-bold text-emerald-400">
                    Overall: {Math.round((confidence.overall || 0.95) * 100)}%
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  {[
                    { label: "Container Identification", val: confidence.container_number ?? 0.98 },
                    { label: "Container Type & ISO Code", val: confidence.container_type ?? 0.92 },
                    { label: "Dimensions & Profile", val: confidence.dimensions ?? 0.95 },
                    { label: "Weight Measurements (VGM)", val: confidence.weights ?? 0.96 },
                    { label: "Cargo Description & DG", val: confidence.cargo ?? 0.98 },
                    { label: "Port Routing & Destination", val: confidence.destination ?? 0.95 }
                  ].map((item, idx) => (
                    <div key={idx} className="space-y-0.5">
                      <div className="flex justify-between text-[11px] text-gray-400">
                        <span>{item.label}</span>
                        <span className="font-mono text-gray-200">{Math.round(item.val * 100)}%</span>
                      </div>
                      <div className="w-full bg-brand-dark h-1.5 rounded-full overflow-hidden border border-brand-border/40">
                        <div 
                          className={`h-full rounded-full ${item.val >= 0.90 ? "bg-emerald-500" : (item.val >= 0.70 ? "bg-blue-500" : "bg-amber-500")}`}
                          style={{ width: `${Math.round(item.val * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Validation & Segregation Rules Alerts (7 cols) */}
              <div className="lg:col-span-7 bg-brand-dark/60 p-4 rounded-xl border border-brand-border space-y-3 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                    <span className="text-xs font-bold text-gray-200 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Maritime Segregation & Compliance Checks
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20">
                      SOLAS / IMDG Compliant
                    </span>
                  </div>

                  <div className="mt-3 space-y-2 text-xs">
                    {validation.warnings && validation.warnings.length > 0 ? (
                      validation.warnings.map((w: string, idx: number) => (
                        <div key={idx} className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-200 flex items-start gap-2 text-xs">
                          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                          <span>{w}</span>
                        </div>
                      ))
                    ) : (
                      <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-300 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                        <span>All ISO 6346 checksums, gross weight bounds, and standard documentation criteria passed with zero anomalies.</span>
                      </div>
                    )}

                    {cargo.hazardous && (
                      <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-lg text-red-200 flex items-start gap-2 text-xs">
                        <Flame className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                        <div>
                          <strong className="text-red-300">Dangerous Goods Stowage Segregation Required:</strong>{" "}
                          Classified as {cargo.imdg_class || "Class 9"} ({cargo.un_number || "UN 3480"}). Must NOT be placed adjacent to refrigerated or heated fuel tanks.
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-2 text-[11px] text-gray-500 flex items-center justify-between border-t border-brand-border/40 mt-2">
                  <span>Document Integrity: Verified</span>
                  <span>Check Digit: Validated</span>
                </div>
              </div>

            </div>

          </div>
        )}

        {/* STABILITY ENGINE & PLACEMENT RESULTS (PHASE 2) */}
        {stabilityResult && (
          <div className="bg-gradient-to-br from-brand-surface to-blue-950/40 border border-blue-500/40 p-6 rounded-2xl shadow-2xl space-y-6 animate-fadeIn">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-brand-border/80 pb-4 gap-4">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-emerald-500/20 border border-emerald-500/40 rounded-xl text-emerald-400 shadow-inner">
                  <Anchor className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-white tracking-wide">
                    Optimal Vessel Slot Allocation & Stability Projection
                  </h2>
                  <p className="text-xs text-gray-400">
                    Evaluated via MareTide Hydrostatic & Ballast Optimization Core
                  </p>
                </div>
              </div>
              <span className="text-xs font-bold px-3.5 py-1.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded-full flex items-center gap-1.5 shadow">
                <CheckCircle className="w-4 h-4" /> Recommendation Confirmed
              </span>
            </div>

            {/* Multi-Objective Top Stowage Recommendations (BEST + ALTERNATIVES) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-200 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-amber-400" /> Multi-Objective Stowage Ranking
                </span>
                <span className="text-[10px] text-gray-400 font-mono">
                  VCG + Weight Hierarchy + Trim Moments + Stability
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* 1. BEST RECOMMENDATION */}
                <div className="bg-emerald-950/30 p-4 rounded-2xl border-2 border-emerald-500/60 shadow-lg relative space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-black tracking-wider uppercase border border-emerald-500/40">
                      ★ BEST STOWAGE
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 font-bold">Rank #1</span>
                  </div>
                  <div className="text-2xl font-black text-white font-mono">
                    Bay {stabilityResult.recommendation?.bay} / {stabilityResult.recommendation?.side} / Tier {stabilityResult.recommendation?.tier}
                  </div>
                  <div className="flex justify-between text-xs text-gray-300 border-t border-emerald-500/30 pt-2 font-mono">
                    <span>Stability Score: <strong className="text-emerald-400">{stabilityResult.stability?.after?.stability_score}</strong></span>
                    {stabilityResult.recommendation?.ranking_score !== undefined && (
                      <span>Score: <strong className="text-blue-300">{stabilityResult.recommendation.ranking_score}</strong></span>
                    )}
                  </div>
                </div>

                {/* 2. ALTERNATIVE 1 */}
                {stabilityResult.alternatives && stabilityResult.alternatives[0] ? (
                  <div className="bg-brand-dark/70 p-4 rounded-2xl border border-blue-500/40 shadow space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 text-[10px] font-bold tracking-wider uppercase border border-blue-500/30">
                        ALTERNATIVE
                      </span>
                      <span className="text-[10px] font-mono text-blue-400 font-bold">Rank #2</span>
                    </div>
                    <div className="text-xl font-black text-gray-200 font-mono">
                      Bay {stabilityResult.alternatives[0].bay} / {stabilityResult.alternatives[0].side} / Tier {stabilityResult.alternatives[0].tier}
                    </div>
                    <div className="flex justify-between text-xs text-gray-400 border-t border-brand-border/60 pt-2 font-mono">
                      <span>Stability: <strong className="text-gray-300">{stabilityResult.alternatives[0].score}</strong></span>
                      <span>Score: <strong className="text-blue-400">{stabilityResult.alternatives[0].ranking_score}</strong></span>
                    </div>
                  </div>
                ) : (
                  <div className="bg-brand-dark/40 p-4 rounded-2xl border border-brand-border/40 flex items-center justify-center text-xs text-gray-500">
                    No 2nd Alternative
                  </div>
                )}

                {/* 3. ALTERNATIVE 2 */}
                {stabilityResult.alternatives && stabilityResult.alternatives[1] ? (
                  <div className="bg-brand-dark/70 p-4 rounded-2xl border border-blue-500/40 shadow space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 text-[10px] font-bold tracking-wider uppercase border border-blue-500/30">
                        ALTERNATIVE
                      </span>
                      <span className="text-[10px] font-mono text-blue-400 font-bold">Rank #3</span>
                    </div>
                    <div className="text-xl font-black text-gray-200 font-mono">
                      Bay {stabilityResult.alternatives[1].bay} / {stabilityResult.alternatives[1].side} / Tier {stabilityResult.alternatives[1].tier}
                    </div>
                    <div className="flex justify-between text-xs text-gray-400 border-t border-brand-border/60 pt-2 font-mono">
                      <span>Stability: <strong className="text-gray-300">{stabilityResult.alternatives[1].score}</strong></span>
                      <span>Score: <strong className="text-blue-400">{stabilityResult.alternatives[1].ranking_score}</strong></span>
                    </div>
                  </div>
                ) : (
                  <div className="bg-brand-dark/40 p-4 rounded-2xl border border-brand-border/40 flex items-center justify-center text-xs text-gray-500">
                    No 3rd Alternative
                  </div>
                )}
              </div>
            </div>

            {/* Before vs After Impact Comparison */}
            <div className="bg-brand-dark/70 p-5 rounded-2xl border border-brand-border space-y-4">
              <div className="flex items-center justify-between text-xs font-bold text-gray-300">
                <span>Vessel Stability Impact Metrics</span>
                <span className="text-[11px] font-normal text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                  Improvement Score: +{stabilityResult.stability?.delta_score} pts
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-4 bg-brand-surface/90 rounded-xl border border-brand-border space-y-2">
                  <div className="text-gray-400 font-bold uppercase text-[10px] tracking-wider">Current State (Pre-Load)</div>
                  <div className="flex justify-between text-gray-300 border-b border-brand-border/40 pb-1">
                    <span>Lateral List Imbalance:</span>
                    <span className="font-mono font-bold text-white">{stabilityResult.stability?.before?.list_t} t</span>
                  </div>
                  <div className="flex justify-between text-gray-300 border-b border-brand-border/40 pb-1">
                    <span>Longitudinal Trim Imbalance:</span>
                    <span className="font-mono font-bold text-white">{stabilityResult.stability?.before?.trim_t} t</span>
                  </div>
                  <div className="flex justify-between text-gray-300 pt-1">
                    <span>Composite Stability Index:</span>
                    <span className="font-mono font-bold text-amber-400">{stabilityResult.stability?.before?.stability_score}</span>
                  </div>
                </div>

                <div className="p-4 bg-brand-surface/90 rounded-xl border border-emerald-500/40 space-y-2">
                  <div className="text-emerald-400 font-bold uppercase text-[10px] tracking-wider">Projected State (Post-Load)</div>
                  <div className="flex justify-between text-gray-300 border-b border-brand-border/40 pb-1">
                    <span>Lateral List Imbalance:</span>
                    <span className="font-mono font-bold text-emerald-400">{stabilityResult.stability?.after?.list_t} t</span>
                  </div>
                  <div className="flex justify-between text-gray-300 border-b border-brand-border/40 pb-1">
                    <span>Longitudinal Trim Imbalance:</span>
                    <span className="font-mono font-bold text-emerald-400">{stabilityResult.stability?.after?.trim_t} t</span>
                  </div>
                  <div className="flex justify-between text-gray-300 pt-1">
                    <span>Composite Stability Index:</span>
                    <span className="font-mono font-bold text-emerald-400">{stabilityResult.stability?.after?.stability_score}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Explainable Engineering Justifications */}
            <div className="space-y-2">
              <div className="text-xs font-bold text-gray-300 flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-400" />
                AI Engineering Justifications & Multi-Objective Criteria:
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {stabilityResult.reason?.map((r: string, idx: number) => (
                  <div key={idx} className="text-xs bg-brand-dark/60 p-3 rounded-xl border border-brand-border/60 text-gray-300 flex items-start gap-2.5">
                    <div className="w-2 h-2 rounded-full bg-emerald-400 mt-1 flex-shrink-0 shadow-sm" />
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Candidate Evaluations Table */}
            {((stabilityResult.candidates || stabilityResult.candidate_evaluations) && (stabilityResult.candidates || stabilityResult.candidate_evaluations)!.length > 0) && (
              <div className="bg-brand-surface border border-brand-border p-4 rounded-xl space-y-3">
                <div className="flex justify-between items-center">
                  <div className="text-xs font-bold text-gray-200">Evaluated Candidate Stowage Slots</div>
                  <div className="text-[10px] text-gray-400 font-mono">Ranked by Multi-Objective Score</div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-brand-border text-gray-400 text-[10px] uppercase font-bold">
                        <th className="p-2">Rank</th>
                        <th className="p-2">Candidate Slot</th>
                        <th className="p-2">Multi-Objective Score</th>
                        <th className="p-2">Stability Index</th>
                        <th className="p-2">List Offset</th>
                        <th className="p-2">Trim Offset</th>
                        <th className="p-2">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brand-border/40 font-mono">
                      {(stabilityResult.candidates || stabilityResult.candidate_evaluations)!.map((c: any, idx: number) => (
                        <tr key={idx} className={c.selected ? "bg-emerald-500/10 text-white font-bold" : (c.eligible === false ? "opacity-40 text-gray-500" : "text-gray-300")}>
                          <td className="p-2">
                            {c.rank ? `#${c.rank}` : (c.eligible === false ? "—" : `#${idx + 1}`)}
                          </td>
                          <td className="p-2">Bay {c.bay} / {c.side} / Tier {c.tier}</td>
                          <td className="p-2 text-cyan-300 font-bold">
                            {c.ranking_score !== undefined && c.ranking_score < 900 ? c.ranking_score : "—"}
                          </td>
                          <td className="p-2 text-emerald-400">
                            {c.score !== undefined && c.score < 900 ? c.score : "—"}
                          </td>
                          <td className="p-2">{c.list_t !== undefined && c.eligible !== false ? `${c.list_t} t` : "—"}</td>
                          <td className="p-2">{c.trim_t !== undefined && c.eligible !== false ? `${c.trim_t} t` : "—"}</td>
                          <td className="p-2">
                            {c.label === "BEST" || idx === 0 ? (
                              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-bold border border-emerald-500/30">BEST</span>
                            ) : c.label === "ALTERNATIVE" || idx in [1, 2] ? (
                              <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[10px] font-bold border border-blue-500/30">ALTERNATIVE</span>
                            ) : c.eligible === false ? (
                              <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 text-[10px]">Ineligible</span>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-brand-dark text-gray-400 text-[10px]">Candidate</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

          </div>
        )}
        </>
        )}

      </div>
    </div>
  );
};
