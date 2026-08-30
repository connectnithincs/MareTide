import React, { createContext, useContext, useState } from "react";
import { containerAPI, operationsAPI } from "../utils/api";
import { useSocket } from "./SocketContext";

export interface Dimensions {
  length_ft?: number | null;
  width_ft?: number | null;
  height_ft?: number | null;
}

export interface Weights {
  tare_weight_kg?: number | null;
  cargo_weight_kg?: number | null;
  gross_weight_kg?: number | null;
}

export interface Cargo {
  description?: string | null;
  hazardous?: boolean | null;
  un_number?: string | null;
  imdg_class?: string | null;
}

export interface ContainerDetails {
  container_number?: string | null;
  container_type?: string | null;
  dimensions?: Dimensions;
  weights?: Weights;
  cargo?: Cargo;
  destination?: string | null;
}

export interface DocumentMetadata {
  source?: string;
  processing_status?: string;
  processing_time_ms?: number;
  ocr_engine?: string;
}

export interface ConfidenceScores {
  overall?: number;
  container_number?: number;
  container_type?: number;
  dimensions?: number;
  weights?: number;
  cargo?: number;
  destination?: number;
}

export interface CargoAnomaly {
  field: string;
  observed: any;
  expected: string;
  severity: "INFO" | "WARNING" | "CRITICAL" | string;
  message: string;
  action: string;
}

export interface ValidationResult {
  valid?: boolean;
  iso_6346_valid?: boolean;
  weight_balance_valid?: boolean;
  warnings?: string[];
  errors?: string[];
  anomalies?: CargoAnomaly[];
}

export interface ExtractedData {
  success: boolean;
  document?: DocumentMetadata;
  container?: ContainerDetails;
  confidence?: ConfidenceScores;
  validation?: ValidationResult;
  anomalies?: CargoAnomaly[];
  raw_text?: string;
}

export interface StabilityMetrics {
  list_t: number;
  trim_t: number;
  stability_score: number;
  risk_level: string;
  normalized_score?: number | null;
}

export interface RecommendedPosition {
  bay: number;
  side: string;
  tier: number;
  label?: string;
  ranking_score?: number;
}

export interface SlotCandidateEvaluation {
  bay: number;
  side: string;
  tier: number;
  list_t: number;
  trim_t: number;
  score: number;
  stability_score?: number;
  risk: string;
  eligible?: boolean;
  ranking_score?: number;
  penalties?: Record<string, number>;
  reasons?: string[];
  rank?: number;
  label?: string;
  selected?: boolean;
}

export interface ExplanationItem {
  category: "DOCUMENT" | "VALIDATION" | "STABILITY" | "PLACEMENT" | "HAZARDOUS_CARGO" | "BALLAST" | "SAFETY" | string;
  message: string;
  evidence?: Record<string, any>;
}

export interface DataProvenanceReport {
  ocr_derived?: Record<string, any>;
  calculated?: Record<string, any>;
  operator_provided?: Record<string, any>;
}

export interface StabilityResult {
  success: boolean;
  status: string;
  container?: {
    container_number: string;
    container_type?: string;
    gross_weight_kg: number;
    gross_weight_t: number;
    hazardous?: boolean;
    destination?: string;
  };
  recommendation?: RecommendedPosition;
  alternatives?: SlotCandidateEvaluation[];
  stability?: {
    before: StabilityMetrics;
    after: StabilityMetrics;
    delta_score: number;
  };
  candidates?: SlotCandidateEvaluation[];
  candidate_evaluations?: SlotCandidateEvaluation[];
  reason?: string[];
  structured_explanations?: ExplanationItem[];
  provenance?: DataProvenanceReport;
  anomalies?: CargoAnomaly[];
  disclaimer?: string;
  error_message?: string;
}

export interface LoadedContainerResult {
  success: boolean;
  status: string;
  container?: {
    container_number: string;
    container_type?: string;
    gross_weight_kg: number;
    gross_weight_t: number;
    hazardous?: boolean;
    destination?: string;
  };
  loaded_position?: RecommendedPosition;
  stability_before?: StabilityMetrics;
  stability_after?: StabilityMetrics;
  stability_delta?: number;
  audit_id?: number;
  anomalies?: CargoAnomaly[];
  message?: string;
  error_message?: string;
}

export interface BallastCompensation {
  success: boolean;
  status: string;
  compensation_required: boolean;
  affected_tank?: string;
  tank_key?: string;
  direction?: string;
  required_qty_t: number;
  required_qty_kg: number;
  current_stability?: StabilityMetrics;
  target_stability?: StabilityMetrics;
  projected_stability?: StabilityMetrics;
  flow_rate_l_s: number;
  est_duration_sec: number;
  message?: string;
  error_message?: string;
}

export interface ThreeStageStabilityReport {
  before_load: StabilityMetrics;
  after_container: StabilityMetrics;
  after_ballast: StabilityMetrics;
  net_score_delta: number;
}

export interface BallastExecutionResult {
  success: boolean;
  status: string;
  actual_qty_t: number;
  affected_tank?: string;
  tank_key?: string;
  three_stage_stability?: ThreeStageStabilityReport;
  audit_id?: number;
  message?: string;
  error_message?: string;
}

export interface PlannedContainerStep {
  step_number: number;
  container: {
    container_number: string;
    container_type?: string;
    gross_weight_kg: number;
    gross_weight_t: number;
    hazardous?: boolean;
    destination?: string;
  };
  status: "VALID" | "REVIEW_REQUIRED" | "REJECTED" | string;
  recommended_position?: RecommendedPosition;
  ranking_score?: number;
  stability_after?: StabilityMetrics;
  delta_score?: number;
  ballast_required: boolean;
  ballast_recommendation?: Record<string, any>;
  reasons: string[];
}

export interface StageStability {
  stage_index: number;
  label: string;
  container_id?: string;
  metrics: StabilityMetrics;
}

export interface RejectedContainerItem {
  container_number: string;
  reason: string;
  status: string;
}

export interface MultiContainerPlanResponse {
  success: boolean;
  total_containers: number;
  valid_count: number;
  rejected_count: number;
  initial_stability?: StabilityMetrics;
  final_stability?: StabilityMetrics;
  stability_progression: StageStability[];
  loading_sequence: PlannedContainerStep[];
  rejected_containers: RejectedContainerItem[];
  cumulative_imbalance: number;
  warnings: string[];
  disclaimer: string;
  error_message?: string;
}

export type OperationStatus = 
  | "IDLE" 
  | "EXTRACTING" 
  | "EXTRACTED" 
  | "REVIEW_REQUIRED" 
  | "ANALYZED" 
  | "CONFIRMED" 
  | "LOADING" 
  | "LOADED"
  | "CONFIRM_COMPENSATION"
  | "DRAINING"
  | "COMPLETED";

interface ContainerOperationContextType {
  file: File | null;
  previewUrl: string | null;
  extractedData: ExtractedData | null;
  stabilityResult: StabilityResult | null;
  loadedResult: LoadedContainerResult | null;
  ballastCompensation: BallastCompensation | null;
  ballastExecutionResult: BallastExecutionResult | null;
  manifestPlan: MultiContainerPlanResponse | null;
  isExtracting: boolean;
  isAnalyzing: boolean;
  isLoadingContainer: boolean;
  isCalculatingBallast: boolean;
  isExecutingBallast: boolean;
  isPlanningManifest: boolean;
  isExecutingManifest: boolean;
  operationStatus: OperationStatus;
  errorMessage: string | null;
  canConfirmAndLoad: boolean;
  processSlipFile: (file: File) => Promise<boolean>;
  loadSampleSlip: () => Promise<void>;
  analyzeActiveStability: () => Promise<boolean>;
  confirmAndLoadContainer: () => Promise<boolean>;
  calculateBallastCompensation: (loadedInfo?: LoadedContainerResult) => Promise<boolean>;
  confirmAndExecuteBallast: () => Promise<boolean>;
  generateManifestPlan: (containers: any[], documents?: any[], validations?: any[]) => Promise<MultiContainerPlanResponse | null>;
  executeManifestSequence: () => Promise<boolean>;
  setManifestPlan: (plan: MultiContainerPlanResponse | null) => void;
  confirmOperation: () => void;
  resetOperation: () => void;
  setExtractedData: (data: ExtractedData | null) => void;
  setStabilityResult: (result: StabilityResult | null) => void;
  setErrorMessage: (msg: string | null) => void;
}

const ContainerOperationContext = createContext<ContainerOperationContextType | undefined>(undefined);

export const EXTRACTION_REVIEW_THRESHOLD = 0.85;

export const ContainerOperationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { refetchVesselState } = useSocket();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [extractedData, setExtractedData] = useState<ExtractedData | null>(null);
  const [stabilityResult, setStabilityResult] = useState<StabilityResult | null>(null);
  const [loadedResult, setLoadedResult] = useState<LoadedContainerResult | null>(null);
  const [ballastCompensation, setBallastCompensation] = useState<BallastCompensation | null>(null);
  const [ballastExecutionResult, setBallastExecutionResult] = useState<BallastExecutionResult | null>(null);
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [isLoadingContainer, setIsLoadingContainer] = useState<boolean>(false);
  const [isCalculatingBallast, setIsCalculatingBallast] = useState<boolean>(false);
  const [isExecutingBallast, setIsExecutingBallast] = useState<boolean>(false);
  const [operationStatus, setOperationStatus] = useState<OperationStatus>("IDLE");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);


  const hasCriticalAnomaly = Boolean(
    extractedData?.validation?.anomalies?.some(a => a.severity === "CRITICAL") ||
    stabilityResult?.anomalies?.some(a => a.severity === "CRITICAL")
  );

  // Evaluate safety rules for enabling Confirm & Load action
  const canConfirmAndLoad = Boolean(
    extractedData &&
    stabilityResult &&
    stabilityResult.recommendation &&
    extractedData.document?.processing_status !== "review_required" &&
    extractedData.validation?.valid !== false &&
    !hasCriticalAnomaly &&
    extractedData.container?.weights?.gross_weight_kg &&
    extractedData.container.weights.gross_weight_kg > 0 &&
    (extractedData.confidence?.overall === undefined || extractedData.confidence.overall >= EXTRACTION_REVIEW_THRESHOLD) &&
    operationStatus !== "LOADED" &&
    operationStatus !== "LOADING"
  );

  const resetOperation = async () => {
    setFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setExtractedData(null);
    setStabilityResult(null);
    setLoadedResult(null);
    setBallastCompensation(null);
    setBallastExecutionResult(null);
    setIsExtracting(false);
    setIsAnalyzing(false);
    setIsLoadingContainer(false);
    setIsCalculatingBallast(false);
    setIsExecutingBallast(false);
    setOperationStatus("IDLE");
    setErrorMessage(null);
    try {
      await operationsAPI.resetFlow();
    } catch {
      // Non-blocking sync
    }
    await refetchVesselState();
  };

  const executeStabilityAnalysis = async (data: ExtractedData): Promise<boolean> => {
    if (isAnalyzing) return false;
    setIsAnalyzing(true);
    try {
      const payload = {
        container: data.container,
        document: data.document,
        validation: data.validation
      };
      const res = await containerAPI.analyzeStability(payload);
      if (res.success) {
        setStabilityResult(res);
        const isReviewReq = 
          (data.confidence?.overall !== undefined && data.confidence.overall < EXTRACTION_REVIEW_THRESHOLD) ||
          data.validation?.valid === false ||
          data.document?.processing_status === "review_required";

        setOperationStatus(isReviewReq ? "REVIEW_REQUIRED" : "ANALYZED");
        return true;
      } else {
        setStabilityResult(null);
        setErrorMessage(res.error_message ? `STABILITY ANALYSIS UNAVAILABLE: ${res.error_message}` : "STABILITY ANALYSIS UNAVAILABLE");
        return false;
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || "STABILITY ANALYSIS UNAVAILABLE: Stability solver offline.";
      setStabilityResult(null);
      setErrorMessage(msg.startsWith("STABILITY ANALYSIS UNAVAILABLE") ? msg : `STABILITY ANALYSIS UNAVAILABLE: ${msg}`);
      return false;
    } finally {
      setIsAnalyzing(false);
    }
  };

  const optimizeImageForUpload = async (file: File): Promise<File | Blob> => {

    return new Promise((resolve) => {
      // If already small (< 500KB) and not huge dimensions, return as is
      if (file.size < 500 * 1024) {
        resolve(file);
        return;
      }
      const img = new Image();
      const reader = new FileReader();
      reader.onload = (e) => {
        img.src = e.target?.result as string;
      };
      img.onload = () => {
        const maxDim = 1400;
        let width = img.width;
        let height = img.height;
        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(file);
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob(
          (blob) => {
            if (blob) {
              const optimizedFile = new File([blob], file.name.replace(/\.[^/.]+$/, ".jpg"), {
                type: "image/jpeg",
                lastModified: Date.now()
              });
              resolve(optimizedFile);
            } else {
              resolve(file);
            }
          },
          "image/jpeg",
          0.92
        );
      };
      img.onerror = () => resolve(file);
      reader.readAsDataURL(file);
    });
  };

  const processSlipFile = async (selectedFile: File): Promise<boolean> => {
    if (isExtracting) return false;
    setFile(selectedFile);
    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);
    setExtractedData(null);
    setStabilityResult(null);
    setLoadedResult(null);
    setBallastCompensation(null);
    setBallastExecutionResult(null);
    setErrorMessage(null);
    setIsExtracting(true);
    setOperationStatus("EXTRACTING");

    try {
      const uploadPayload = await optimizeImageForUpload(selectedFile);
      const formData = new FormData();
      formData.append("image", uploadPayload as File);
      const res = await containerAPI.extract(formData);

      if (res.success) {
        setExtractedData(res);
        const isReviewReq = 
          (res.confidence?.overall !== undefined && res.confidence.overall < EXTRACTION_REVIEW_THRESHOLD) ||
          res.validation?.valid === false ||
          res.document?.processing_status === "review_required";

        if (isReviewReq) {
          const reason = res.validation?.anomalies?.[0]?.message || res.validation?.warnings?.[0] || "Confidence or check-digit review required.";
          setErrorMessage(`REVIEW REQUIRED: ${reason}`);
          setOperationStatus("REVIEW_REQUIRED");
        } else {
          setOperationStatus("EXTRACTED");
        }

        // Automatically trigger Phase 2 Stability analysis upon valid extraction
        await executeStabilityAnalysis(res);
        return true;
      } else {
        const warningMsg = res.validation?.errors?.[0] || res.validation?.warnings?.[0] || "DOCUMENT PROCESSING FAILED: Review notices triggered.";
        setErrorMessage(warningMsg.startsWith("DOCUMENT PROCESSING FAILED") ? warningMsg : `DOCUMENT PROCESSING FAILED: ${warningMsg}`);
        if (res.container) {
          setExtractedData(res);
          setOperationStatus("REVIEW_REQUIRED");
          await executeStabilityAnalysis(res);
        }
        return false;
      }
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || err.message || "Please check image resolution/format and retry.";
      setErrorMessage(`DOCUMENT PROCESSING FAILED: ${errorDetail}`);
      setOperationStatus("IDLE");
      return false;
    } finally {
      setIsExtracting(false);
    }
  };

  const loadSampleSlip = async () => {
    if (isExtracting) return;
    resetOperation();
    setIsExtracting(true);
    setOperationStatus("EXTRACTING");
    setErrorMessage(null);
    try {
      // 1. Fetch real sample_container_slip.jpg fixture binary from backend
      const imageBlob = await containerAPI.getDemoFixtureImage("sample_container_slip.jpg");
      const sampleFile = new File([imageBlob], "sample_container_slip.jpg", { type: "image/jpeg" });
      setFile(sampleFile);
      const url = URL.createObjectURL(sampleFile);
      setPreviewUrl(url);

      // 2. Submit real multipart/form-data to RapidOCR Document AI extraction
      const formData = new FormData();
      formData.append("file", sampleFile);
      formData.append("image", sampleFile);

      const res = await containerAPI.extract(formData);
      if (res.success) {
        setExtractedData(res);
        const isReviewReq = 
          (res.confidence?.overall !== undefined && res.confidence.overall < EXTRACTION_REVIEW_THRESHOLD) ||
          res.validation?.valid === false ||
          res.document?.processing_status === "review_required";

        if (isReviewReq) {
          const reason = res.validation?.anomalies?.[0]?.message || res.validation?.warnings?.[0] || "Confidence or check-digit review required.";
          setErrorMessage(`REVIEW REQUIRED: ${reason}`);
          setOperationStatus("REVIEW_REQUIRED");
        } else {
          setOperationStatus("EXTRACTED");
        }
        await executeStabilityAnalysis(res);
      } else {
        const warningMsg = res.validation?.errors?.[0] || res.validation?.warnings?.[0] || "DOCUMENT PROCESSING FAILED";
        setErrorMessage(warningMsg.startsWith("DOCUMENT PROCESSING FAILED") ? warningMsg : `DOCUMENT PROCESSING FAILED: ${warningMsg}`);
        if (res.container) {
          setExtractedData(res);
          setOperationStatus("REVIEW_REQUIRED");
          await executeStabilityAnalysis(res);
        }
      }
    } catch (err: any) {
      console.error("Failed loading sample slip:", err);
      const msg = err.response?.data?.detail || err.message || "Failed to extract sample container slip.";
      setErrorMessage(`DOCUMENT PROCESSING FAILED: ${msg}`);
      setOperationStatus("IDLE");
    } finally {
      setIsExtracting(false);
    }
  };

  const analyzeActiveStability = async (): Promise<boolean> => {
    if (!extractedData) return false;
    return await executeStabilityAnalysis(extractedData);
  };

  const calculateBallastCompensation = async (loadedInfo?: LoadedContainerResult): Promise<boolean> => {
    const target = loadedInfo || loadedResult;
    if (!target) {
      return false;
    }

    setIsCalculatingBallast(true);
    try {
      const payload = {
        container_number: target.container?.container_number,
        gross_weight_t: target.container?.gross_weight_t,
        bay: target.loaded_position?.bay,
        side: target.loaded_position?.side,
        tier: target.loaded_position?.tier
      };

      const res = await containerAPI.calculateBallastCompensation(payload);
      if (res.success) {
        setBallastCompensation(res);
        if (res.compensation_required) {
          setOperationStatus("CONFIRM_COMPENSATION");
        } else {
          setOperationStatus("LOADED");
        }
        return true;
      } else {
        setErrorMessage(res.error_message || "Ballast compensation calculation failed.");
        return false;
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to calculate ballast compensation.";
      setErrorMessage(msg);
      return false;
    } finally {
      setIsCalculatingBallast(false);
    }
  };

  const confirmAndLoadContainer = async (): Promise<boolean> => {
    if (isLoadingContainer) return false;
    if (!extractedData || !stabilityResult || !stabilityResult.recommendation) {
      setErrorMessage("Cannot confirm load: Extracted container or stability recommendation is missing.");
      return false;
    }

    setIsLoadingContainer(true);
    setOperationStatus("LOADING");
    setErrorMessage(null);

    try {
      const payload = {
        container: extractedData.container,
        document: extractedData.document,
        validation: extractedData.validation,
        recommendation: {
          bay: stabilityResult.recommendation.bay,
          side: stabilityResult.recommendation.side,
          tier: stabilityResult.recommendation.tier
        },
        operator_confirmed: true,
        operator_id: "operator"
      };

      const res = await containerAPI.confirmAndLoad(payload);
      if (res.success) {
        setLoadedResult(res);
        setOperationStatus("LOADED");
        await refetchVesselState();
        
        // Phase 3C: Automatically calculate ballast compensation for post-load vessel state
        await calculateBallastCompensation(res);
        return true;
      } else {
        setErrorMessage(res.error_message || "Loading rejected or failed.");
        setOperationStatus("ANALYZED");
        return false;
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to commit container load to vessel state.";
      setErrorMessage(msg);
      setOperationStatus("ANALYZED");
      return false;
    } finally {
      setIsLoadingContainer(false);
    }
  };

  const confirmAndExecuteBallast = async (): Promise<boolean> => {
    if (isExecutingBallast) return false;
    if (!ballastCompensation || !ballastCompensation.tank_key) {
      setErrorMessage("No active ballast compensation calculation available to execute.");
      return false;
    }

    setIsExecutingBallast(true);
    setOperationStatus("DRAINING");
    setErrorMessage(null);

    try {
      const payload = {
        container_number: loadedResult?.container?.container_number,
        tank_key: ballastCompensation.tank_key,
        direction: ballastCompensation.direction || "DRAIN",
        qty_t: ballastCompensation.required_qty_t,
        operator_confirmed: true,
        operator_id: "ChiefOfficer",
        stability_before_load: loadedResult?.stability_before
      };

      const res = await containerAPI.executeBallastCompensation(payload);
      if (res.success) {
        setBallastExecutionResult(res);
        setOperationStatus("COMPLETED");
        await refetchVesselState();
        return true;
      } else {
        setErrorMessage(res.error_message || "Ballast operation failed.");
        setOperationStatus("CONFIRM_COMPENSATION");
        return false;
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to execute ballast water compensation.";
      setErrorMessage(msg);
      setOperationStatus("CONFIRM_COMPENSATION");
      return false;
    } finally {
      setIsExecutingBallast(false);
    }
  };

  const [manifestPlan, setManifestPlan] = useState<MultiContainerPlanResponse | null>(null);
  const [isPlanningManifest, setIsPlanningManifest] = useState<boolean>(false);
  const [isExecutingManifest, setIsExecutingManifest] = useState<boolean>(false);

  const generateManifestPlan = async (containers: any[], documents?: any[], validations?: any[]): Promise<MultiContainerPlanResponse | null> => {
    if (isPlanningManifest) return null;
    setIsPlanningManifest(true);
    setErrorMessage(null);
    try {
      const payload = {
        containers,
        documents,
        validations
      };
      const res = await containerAPI.planManifest(payload);
      if (res.success) {
        setManifestPlan(res);
        return res;
      } else {
        setErrorMessage(res.error_message || "Failed to generate multi-container manifest plan.");
        return null;
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Multi-container planning service error.";
      setErrorMessage(msg);
      return null;
    } finally {
      setIsPlanningManifest(false);
    }
  };

  const executeManifestSequence = async (): Promise<boolean> => {
    if (isExecutingManifest) return false;
    if (!manifestPlan || !manifestPlan.loading_sequence || manifestPlan.loading_sequence.length === 0) {
      setErrorMessage("No approved loading sequence to execute.");
      return false;
    }
    setIsExecutingManifest(true);
    try {
      const payload = {
        loading_sequence: manifestPlan.loading_sequence,
        operator_confirmed: true,
        operator_id: "ChiefOfficer"
      };
      const res = await containerAPI.executeManifest(payload);
      if (res.success) {
        await refetchVesselState();
        return true;
      } else {
        setErrorMessage(res.error_message || "Failed to execute manifest sequence.");
        return false;
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Execution failed on live vessel.";
      setErrorMessage(msg);
      return false;
    } finally {
      setIsExecutingManifest(false);
    }
  };

  const confirmOperation = () => {
    setOperationStatus("CONFIRMED");
  };

  return (
    <ContainerOperationContext.Provider
      value={{
        file,
        previewUrl,
        extractedData,
        stabilityResult,
        loadedResult,
        ballastCompensation,
        ballastExecutionResult,
        manifestPlan,
        isExtracting,
        isAnalyzing,
        isLoadingContainer,
        isCalculatingBallast,
        isExecutingBallast,
        isPlanningManifest,
        isExecutingManifest,
        operationStatus,
        errorMessage,
        canConfirmAndLoad,
        processSlipFile,
        loadSampleSlip,
        analyzeActiveStability,
        confirmAndLoadContainer,
        calculateBallastCompensation,
        confirmAndExecuteBallast,
        generateManifestPlan,
        executeManifestSequence,
        setManifestPlan,
        confirmOperation,
        resetOperation,
        setExtractedData,
        setStabilityResult,
        setErrorMessage
      }}
    >
      {children}
    </ContainerOperationContext.Provider>
  );
};

export const useContainerOperation = () => {
  const context = useContext(ContainerOperationContext);
  if (!context) {
    throw new Error("useContainerOperation must be used within a ContainerOperationProvider");
  }
  return context;
};

