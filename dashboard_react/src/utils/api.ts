import axios, { AxiosError } from "axios";

export const API_BASE = "http://localhost:8000";

// Central Axios API instance configured with timeouts and credentials
export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000, // 30s network timeout
  withCredentials: true,
  headers: {
    "Accept": "application/json"
  }
});

// Central error normalization interceptor
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<any>) => {
    let cleanMessage = "An unexpected error occurred. Please try again.";
    
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

      if (typeof data === "string") {
        cleanMessage = data.length > 200 ? `Error ${status}: Request failed.` : data;
      } else if (data && typeof data === "object") {
        if (data.detail) {
          cleanMessage = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        } else if (data.message) {
          cleanMessage = data.message;
        } else if (data.error) {
          cleanMessage = typeof data.error === "string" ? data.error : JSON.stringify(data.error);
        }
      }

      if (status === 400) {
        cleanMessage = cleanMessage || "Bad Request: Invalid operation parameters.";
      } else if (status === 401) {
        cleanMessage = cleanMessage || "Unauthorized: Session expired or invalid token.";
      } else if (status === 403) {
        cleanMessage = cleanMessage || "Forbidden: You do not have permission for this action.";
      } else if (status === 404) {
        cleanMessage = cleanMessage || "Resource not found on vessel sidecar server.";
      } else if (status === 409) {
        cleanMessage = cleanMessage || "Conflict: Slot occupied or concurrent operation in progress.";
      } else if (status === 422) {
        cleanMessage = cleanMessage || "Validation Error: Payload format does not match vessel criteria.";
      } else if (status >= 500) {
        cleanMessage = cleanMessage || "Vessel stability sidecar service encountered an internal error.";
      }
    } else if (error.code === "ECONNABORTED" || error.message.includes("timeout")) {
      cleanMessage = "Request timed out. Vessel telemetry sidecar may be busy.";
    } else if (error.request) {
      cleanMessage = "Network error: Unable to connect to MareTide API Gateway on port 8000.";
    }

    // Strip raw python tracebacks if present
    if (cleanMessage.includes("Traceback (most recent call last):")) {
      const lines = cleanMessage.split("\n");
      cleanMessage = lines[lines.length - 1] || "Internal server error occurred.";
    }

    const enhancedError = new Error(cleanMessage);
    (enhancedError as any).status = error.response?.status;
    (enhancedError as any).originalError = error;
    return Promise.reject(enhancedError);
  }
);

// ==========================================
// 1. DATA MODELS & TYPES
// ==========================================

export interface BallastTankState {
  name: string;
  current_volume: number;
  capacity: number;
  fill_ratio: number;
}

export interface ContainerItem {
  id: string;
  weight: number;
  bay: number;
  side: "port" | "starboard" | "center" | string;
  tier: number;
  provenance?: string;
}

export interface VesselState {
  ship_name: string;
  containers: ContainerItem[];
  ballast_tanks: Record<string, BallastTankState>;
  roll: number;
  pitch: number;
  list_t?: number;
  trim_t?: number;
  status: string;
  stability_score: number;
  risk_level: "SAFE" | "WARNING" | "CRITICAL";
  is_simulated?: boolean;
  telemetry_source?: string;
  connection_status?: string;
  telemetry_freshness?: "FRESH" | "STALE" | "DEGRADED" | "DISCONNECTED";
  stale_seconds?: number;
  telemetry_timestamp?: string;
  pump_state?: string;
  pump_flow_l_s?: number;
  pump_active?: boolean;
  is_pumping?: boolean;
  gm_m?: number;
  total_cargo_weight_t?: number;
  total_ballast_weight_t?: number;
}

export interface OperationalSafetyAlert {
  alert_type: string;
  severity: "WARNING" | "CRITICAL" | "INFO";
  threshold: string;
  observed_value: number;
  message: string;
  action: string;
}

export interface DigitalTwinVesselState {
  ship_name: string;
  containers: ContainerItem[];
  ballast_tanks: Record<string, BallastTankState>;
  roll_deg: number;
  pitch_deg: number;
  list_t: number;
  trim_t: number;
  stability_score: number;
  risk_level: "SAFE" | "WARNING" | "CRITICAL";
  is_simulated: boolean;
  telemetry_source: string;
  authoritative_weight_source: string;
  operation_status: string;
  alerts: OperationalSafetyAlert[];
  telemetry_timestamp?: string;
  telemetry_freshness?: string;
  stale_seconds?: number;
  connection_status?: string;
  pump_state?: string;
  pump_flow_l_s?: number;
  pump_active?: boolean;
  provenance_map?: Record<string, string>;
}

export interface FourStageLifecycle {
  vessel_before?: DigitalTwinVesselState | null;
  container_loaded?: DigitalTwinVesselState | null;
  ballast_compensated?: DigitalTwinVesselState | null;
  current_vessel_state: DigitalTwinVesselState;
  alerts: OperationalSafetyAlert[];
}

export interface PredictiveComparisonRequest {
  container_id: string;
  gross_weight_t: number;
  bay: number;
  side: string;
  tier?: number;
}

export interface PredictiveComparison {
  container_id: string;
  projected_list_t: number;
  projected_trim_t: number;
  projected_stability_score: number;
  projected_ballast_req_t: number;
  actual_list_t?: number | null;
  actual_trim_t?: number | null;
  actual_stability_score?: number | null;
  actual_ballast_state_t?: number | null;
  status: "PROJECTED" | "COMMITTED";
}

export interface CargoAnomaly {
  field: string;
  observed?: any;
  expected?: string | number | null;
  severity: "INFO" | "WARNING" | "CRITICAL" | string;
  message: string;
  action?: string;
  code?: string;
}

export interface CargoMassMetadata {
  gross_weight_kg: number;
  gross_weight_t: number;
  source: string;
  authoritative: boolean;
  provenance_label: string;
  load_cell_used: boolean;
}

export interface ContainerSlipResponse {
  success: boolean;
  container?: {
    container_number?: string | null;
    container_type?: string | null;
    iso_type?: string | null;
    weights?: {
      gross_weight_kg?: number | null;
      tare_weight_kg?: number | null;
      cargo_weight_kg?: number | null;
      net_weight_kg?: number | null;
    };
    dimensions?: {
      length_ft?: number | null;
      height_ft?: number | null;
      width_ft?: number | null;
    };
    cargo?: {
      hazardous?: boolean | null;
      un_number?: string | null;
      imdg_class?: string | null;
      description?: string | null;
      cargo_description?: string | null;
    };
    destination?: string | null;
    seal_number?: string | null;
    carrier?: string | null;
  };
  document?: {
    source?: string;
    document_type?: string;
    processing_status?: string;
    processing_time_ms?: number;
    ocr_confidence?: number;
    ocr_engine?: string;
  };
  confidence?: {
    overall?: number;
    container_number?: number;
    container_type?: number;
    dimensions?: number;
    weights?: number;
    cargo?: number;
    destination?: number;
  };
  validation?: {
    valid?: boolean;
    is_valid?: boolean;
    iso_6346_valid?: boolean;
    weight_balance_valid?: boolean;
    warnings?: string[];
    errors?: string[];
    anomalies?: CargoAnomaly[];
  };
  anomalies?: CargoAnomaly[];
  cargo_mass?: CargoMassMetadata;
  raw_text?: string;
  error_message?: string;
}

export interface SlotCandidateEvaluation {
  bay: number;
  side: string;
  tier: number;
  list_t: number;
  trim_t: number;
  score: number;
  stability_score?: number;
  risk: "SAFE" | "WARNING" | "CRITICAL" | string;
  eligible?: boolean;
  ranking_score?: number;
  penalties?: Record<string, number>;
  reasons?: string[];
  rank?: number;
  label?: "BEST" | "ALTERNATIVE" | "INELIGIBLE" | string;
  selected?: boolean;
}

export interface RecommendedPosition {
  bay: number;
  side: string;
  tier: number;
  label?: string;
  ranking_score?: number;
}

export interface StabilityComparison {
  before: {
    list_t: number;
    trim_t: number;
    stability_score: number;
    risk_level: "SAFE" | "WARNING" | "CRITICAL" | string;
    normalized_score?: number | null;
  };
  after: {
    list_t: number;
    trim_t: number;
    stability_score: number;
    risk_level: "SAFE" | "WARNING" | "CRITICAL" | string;
    normalized_score?: number | null;
  };
  delta_score: number;
}

export interface ContainerStabilityAnalysisRequest {
  container?: any;
  document?: any;
  validation?: any;
}

export interface ContainerStabilityAnalysisResponse {
  success: boolean;
  status: "success" | "review_required" | "error" | string;
  container?: any;
  recommendation?: RecommendedPosition;
  alternatives?: SlotCandidateEvaluation[];
  stability?: StabilityComparison;
  candidates?: SlotCandidateEvaluation[];
  candidate_evaluations?: SlotCandidateEvaluation[];
  explainable_reasons?: string[];
  reason?: string[];
  anomalies?: CargoAnomaly[];
  stability_before?: any;
  stability_after?: any;
  structured_explanations?: any[];
  provenance?: any;
  disclaimer?: string;
  error_message?: string;
}

export interface ContainerLoadConfirmRequest {
  container?: any;
  document?: any;
  validation?: any;
  recommendation?: RecommendedPosition;
  override_position?: {
    bay: number;
    side: string;
    tier: number;
  };
  operator_confirmed: boolean;
  operator_id?: string;
}

export interface ContainerLoadConfirmResponse {
  success: boolean;
  status: string;
  container?: any;
  loaded_position?: {
    bay: number;
    side: string;
    tier: number;
  };
  vessel_stability?: {
    list_t: number;
    trim_t: number;
    stability_score: number;
    risk_level: string;
  };
  ballast_recommendation_required?: boolean;
  audit_id?: number;
  timestamp?: string;
  error_message?: string;
}

export interface BallastCompensationRequest {
  container_number?: string;
  gross_weight_t?: number;
  bay?: number;
  side?: string;
  tier?: number;
  target_tank?: string;
}

export interface BallastCompensationResponse {
  success: boolean;
  container_number?: string;
  affected_tank: string;
  tank_key?: string;
  direction: "DRAIN" | "FILL" | "TRANSFER" | string;
  required_qty_t: number;
  required_qty_kg?: number;
  flow_rate_l_s?: number;
  est_duration_sec: number;
  compensation_required?: boolean;
  projected_stability: {
    list_t: number;
    trim_t: number;
    stability_score: number;
    risk_level: string;
  };
  status?: string;
  error_message?: string;
}

export interface BallastExecutionRequest {
  container_number?: string;
  tank_key: string;
  direction: "DRAIN" | "FILL" | "TRANSFER" | string;
  qty_t: number;
  operator_confirmed: boolean;
  operator_id?: string;
  stability_before_load?: any;
}

export interface BallastExecutionResponse {
  success: boolean;
  affected_tank: string;
  direction: string;
  actual_qty_t: number;
  remaining_tank_volume_t?: number;
  three_stage_stability?: {
    before_load: { list_t: number; trim_t: number; stability_score: number; risk_level: string };
    after_container: { list_t: number; trim_t: number; stability_score: number; risk_level: string };
    after_ballast: { list_t: number; trim_t: number; stability_score: number; risk_level: string };
    net_score_delta: number;
  };
  audit_logged?: boolean;
  status: string;
  error_message?: string;
}

export interface SafetyGateStatusResponse {
  safety_gate_active: boolean;
  enforce_strict_vgm: boolean;
  enforce_iso_check_digit: boolean;
  enforce_operator_human_gate: boolean;
  strict_zero_load_cell_check: boolean;
  authoritative_source: string;
}

export interface SafetyGateEvaluationResponse {
  passed: boolean;
  action: "ALLOW" | "REQUIRE_REVIEW" | "REJECT_AND_LOCK";
  blocking_reasons: string[];
  warnings: string[];
  anomalies: CargoAnomaly[];
}

export interface LiveOperationalStatusResponse {
  success: boolean;
  operational_stage: string;
  ship_name: string;
  total_containers: number;
  total_cargo_weight_t: number;
  total_ballast_weight_t: number;
  list_t: number;
  trim_t: number;
  stability_score: number;
  risk_level: string;
  telemetry: Record<string, any>;
  normalized_telemetry?: Record<string, any>;
  telemetry_source: string;
  connection_status: string;
  data_quality?: string;
  authoritative_weight_source: string;
  container_weight_source: string;
  load_cell_policy: string;
}

export interface OperationalResetResponse {
  success: boolean;
  stage: string;
  message: string;
}

export interface OperationalPolicyResponse {
  authoritative_source: string;
  container_weight_source: string;
  load_cell_cargo_mass: string;
  hardware_telemetry_label: string;
  load_cell_policy: string;
  solas_vgm_rule: string;
}

export interface VoyageProfileResponse {
  ship_name: string;
  imo: string;
  total_bays: number;
  tank_capacity: number;
  ship_configuration: string;
  cargo_data: any;
  ballast_configuration: any;
}

export interface VoyageTrackPoint {
  lat: number | string;
  lon: number | string;
  timestamp?: string;
  speed?: number;
  course?: number;
}

export interface VoyageTrackResponse {
  imo: string;
  track: VoyageTrackPoint[];
}

export interface OpsLogItem {
  time: string;
  event: string;
  container: string;
  weight: number;
  bay: number;
  side: string;
  tier: number;
  source: string;
}

export interface BallastLogItem {
  timestamp: string;
  op_type: string;
  pump_mode: string;
  source: string;
  dest: string;
  qty: number;
  remaining_src: number;
  final_dest: number;
  score_before: number;
  score_after: number;
  trigger: string;
}

export interface TimelineEvent {
  id: number;
  operation_id: string;
  timestamp: string;
  event_type: string;
  container_id: string;
  actor: string;
  source: string;
  previous_state?: string;
  new_state?: string;
  relevant_metrics?: Record<string, any>;
  reason?: string;
  success: boolean;
}

export interface ExplainableRecommendation {
  condition: string;
  cause: string;
  bays: string;
  tanks: string;
  action: string;
  water: number;
  pred_score: number;
  priority: string;
  confidence: number;
  engineering: string;
}

export interface AIRecommendationResponse {
  best_bay?: number;
  best_side?: string;
  best_score?: number;
  explainable_recs?: ExplainableRecommendation[];
}

export interface DeckPlanResponse {
  num_bays: number;
  containers: ContainerItem[];
}

export interface VisionAlertItem {
  category: string;
  message: string;
  camera: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  timestamp: string;
}

export interface DemoScenario {
  id: string;
  title: string;
  subtitle: string;
  filename: string;
  category: "GOLDEN_PATH" | "ANOMALY_REJECTION" | "VALIDATION_WARNING" | "HEAVY_CARGO";
  container_number: string;
  expected_result: string;
  description: string;
  tags: string[];
}

export interface DemoFixturesResponse {
  scenarios: DemoScenario[];
  total: number;
}

// ==========================================
// 2. CENTRALIZED API SERVICES
// ==========================================

export const authAPI = {
  exchangeToken: async (token: string): Promise<{ success?: boolean; valid?: boolean; user?: string }> => {
    const res = await api.get(`/api/auth/exchange?token=${encodeURIComponent(token)}`);
    return res.data;
  },
  checkSession: async (): Promise<{ authenticated: boolean; user?: string }> => {
    const res = await api.get("/api/auth/session");
    return res.data;
  }
};

export const vesselAPI = {
  getState: async (): Promise<VesselState> => {
    const res = await api.get<VesselState>("/api/vessel-state");
    return res.data;
  },
  calculateCompensation: async (id: string, bay: number, side: string, tier: number): Promise<{ success: boolean; stage: string }> => {
    const res = await api.post("/api/ballast/calculate-compensation", { id, bay, side, tier });
    return res.data;
  },
  confirmDrain: async (): Promise<{ success: boolean; stage: string }> => {
    const res = await api.post("/api/ballast/confirm-drain");
    return res.data;
  },
  adjustBallast: async (tank_key: string, action: "fill" | "drain", qty: number): Promise<{ success: boolean; message: string }> => {
    const res = await api.post("/api/ballast/adjust", { tank_key, action, qty });
    return res.data;
  },
  pumpBallast: async (
    from_side: string,
    to_side: string,
    amount: number,
    from_bay?: string | number | null,
    to_bay?: string | number | null
  ): Promise<{ success: boolean; message: string }> => {
    const payload = {
      from_side,
      to_side,
      amount,
      from_bay: (from_bay === "All" || from_bay === "" || from_bay === null) ? "All" : from_bay,
      to_bay: (to_bay === "All" || to_bay === "" || to_bay === null) ? "All" : to_bay
    };
    const res = await api.post("/api/ballast/pump", payload);
    return res.data;
  },
  setTank: async (tank: string, volume: number): Promise<{ success: boolean; message: string }> => {
    const res = await api.post("/api/ballast/tank", { tank, volume });
    return res.data;
  }
};

export const advisoryAPI = {
  getRecommendations: async (): Promise<AIRecommendationResponse> => {
    const res = await api.get<AIRecommendationResponse>("/api/recommendations");
    return res.data;
  },
  getDeckPlan: async (): Promise<DeckPlanResponse> => {
    const res = await api.get<DeckPlanResponse>("/api/deck-plan");
    return res.data;
  }
};

export const reportsAPI = {
  getCargoManifest: async (): Promise<OpsLogItem[]> => {
    const res = await api.get<OpsLogItem[]>("/api/reports/cargo-manifest");
    return res.data;
  },
  getBallastLog: async (): Promise<BallastLogItem[]> => {
    const res = await api.get<BallastLogItem[]>("/api/reports/ballast-log");
    return res.data;
  },
  getOpsLog: async (): Promise<OpsLogItem[]> => {
    const res = await api.get<OpsLogItem[]>("/api/reports/ops-log");
    return res.data;
  },
  getTimeline: async (limit: number = 20): Promise<{ timeline: TimelineEvent[] }> => {
    const res = await api.get(`/api/reports/timeline?limit=${limit}`);
    return res.data;
  },
  clearAll: async (): Promise<{ success: boolean; message: string }> => {
    const res = await api.post("/api/reports/clear");
    return res.data;
  }
};

export const telemetryAPI = {
  connect: async (port: string | null, is_simulated: boolean): Promise<{ success: boolean; message: string }> => {
    const res = await api.post("/api/telemetry/connect", { port, is_simulated });
    return res.data;
  },
  disconnect: async (): Promise<{ success: boolean; message: string }> => {
    const res = await api.post("/api/telemetry/disconnect");
    return res.data;
  },
  getPorts: async (): Promise<{ ports: string[] }> => {
    const res = await api.get<{ ports: string[] }>("/api/telemetry/ports");
    return res.data;
  },
  simulateCargo: async (weight_t: number): Promise<{ success: boolean }> => {
    const res = await api.post("/api/telemetry/simulate/cargo", { weight_t });
    return res.data;
  },
  simulateTilt: async (roll: number | null, pitch: number | null): Promise<{ success: boolean }> => {
    const res = await api.post("/api/telemetry/simulate/tilt", { roll, pitch });
    return res.data;
  },
  getLive: async (): Promise<any> => {
    const res = await api.get("/api/telemetry/live");
    return res.data;
  },
  getHealth: async (): Promise<any> => {
    const res = await api.get("/api/telemetry/health");
    return res.data;
  },
  getSources: async (): Promise<{ active_source: string; available_sources: string[] }> => {
    const res = await api.get("/api/telemetry/sources");
    return res.data;
  },
  selectSource: async (source: string, port?: string): Promise<{ success: boolean; active_source: string }> => {
    const res = await api.post("/api/telemetry/source/select", { source, port });
    return res.data;
  },
  getVirtualStatus: async (): Promise<any> => {
    const res = await api.get("/api/telemetry/virtual/status");
    return res.data;
  },
  setVirtualScenario: async (scenario: string): Promise<any> => {
    const res = await api.post("/api/telemetry/virtual/scenario", { scenario });
    return res.data;
  },
  sendVirtualCommand: async (command: string): Promise<any> => {
    const res = await api.post("/api/telemetry/virtual/command", { command });
    return res.data;
  }
};

export const telemetryV2API = {
  getLive: async (): Promise<any> => {
    const res = await api.get("/api/telemetry/live");
    return res.data;
  },
  getHealth: async (): Promise<any> => {
    const res = await api.get("/api/telemetry/health");
    return res.data;
  },
  getSources: async (): Promise<{ active_source: string; available_sources: string[] }> => {
    const res = await api.get("/api/telemetry/sources");
    return res.data;
  },
  selectSource: async (source: string, port?: string): Promise<{ success: boolean; source: string; active_source: string }> => {
    const res = await api.post("/api/telemetry/source/select", { source, port });
    return res.data;
  },
  overrideSimulation: async (overrides: { roll?: number; pitch?: number; weight?: number }): Promise<{ success: boolean }> => {
    const res = await api.post("/api/telemetry/simulate/override", overrides);
    return res.data;
  },
  getVirtualStatus: async (): Promise<any> => {
    const res = await api.get("/api/telemetry/virtual/status");
    return res.data;
  },
  setVirtualScenario: async (scenario: string): Promise<any> => {
    const res = await api.post("/api/telemetry/virtual/scenario", { scenario });
    return res.data;
  },
  sendVirtualCommand: async (command: string): Promise<any> => {
    const res = await api.post("/api/telemetry/virtual/command", { command });
    return res.data;
  }
};

export const visionAPI = {
  getStatus: async (): Promise<any> => {
    const res = await api.get("/api/vision/status");
    return res.data;
  },
  toggleCamera: async (camera_id: string, enabled: boolean): Promise<{ success: boolean }> => {
    const res = await api.post(`/api/vision/camera/${camera_id}/toggle`, { enabled });
    return res.data;
  },
  toggleSourceMode: async (mode: "simulated" | "live", device_index: any = 0): Promise<{ success: boolean }> => {
    const res = await api.post("/api/vision/source-mode", { mode, device_index });
    return res.data;
  },
  getAlerts: async (): Promise<VisionAlertItem[]> => {
    const res = await api.get<VisionAlertItem[]>("/api/vision/alerts");
    return res.data;
  },
  setScenario: async (scenario: string): Promise<{ success: boolean }> => {
    const res = await api.post("/api/vision/scenario", { scenario });
    return res.data;
  },
  clearAlerts: async (): Promise<{ success: boolean }> => {
    const res = await api.post("/api/vision/alerts/clear");
    return res.data;
  }
};

export const voyageAPI = {
  getProfile: async (): Promise<VoyageProfileResponse> => {
    const res = await api.get<VoyageProfileResponse>("/api/voyage/profile");
    return res.data;
  },
  getTrack: async (imo: string): Promise<VoyageTrackResponse | any> => {
    const res = await api.get(`/api/voyage/track?imo=${encodeURIComponent(imo)}`);
    return res.data;
  }
};

export const containerAPI = {
  extract: async (formData: FormData): Promise<ContainerSlipResponse | any> => {
    const res = await api.post<ContainerSlipResponse>("/api/container/extract", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return res.data;
  },
  extractSlip: async (formData: FormData): Promise<ContainerSlipResponse | any> => {
    const res = await api.post<ContainerSlipResponse>("/api/container/ocr/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return res.data;
  },
  analyzeStability: async (payload: any): Promise<ContainerStabilityAnalysisResponse | any> => {
    const res = await api.post<ContainerStabilityAnalysisResponse>("/api/container/stability/analyze", payload);
    return res.data;
  },
  confirmAndLoad: async (payload: any): Promise<ContainerLoadConfirmResponse | any> => {
    const res = await api.post<ContainerLoadConfirmResponse>("/api/container/load/confirm", payload);
    return res.data;
  },
  calculateBallastCompensation: async (payload: any): Promise<BallastCompensationResponse | any> => {
    const res = await api.post<BallastCompensationResponse>("/api/container/ballast/calculate", payload);
    return res.data;
  },
  executeBallastCompensation: async (payload: any): Promise<BallastExecutionResponse | any> => {
    const res = await api.post<BallastExecutionResponse>("/api/container/ballast/execute", payload);
    return res.data;
  },
  planManifest: async (payload: { containers: any[] }): Promise<any> => {
    const res = await api.post("/api/container/stability/manifest-plan", payload);
    return res.data;
  },
  executeManifest: async (payload: any): Promise<any> => {
    const res = await api.post("/api/container/manifest/execute", payload);
    return res.data;
  },
  getDemoFixtures: async (): Promise<DemoFixturesResponse> => {
    const res = await api.get<DemoFixturesResponse>("/api/container/demo/fixtures");
    return res.data;
  },
  getDemoFixtureImage: async (filename: string): Promise<Blob> => {
    const res = await api.get(`/api/container/demo/fixtures/${encodeURIComponent(filename)}/image`, {
      responseType: "blob"
    });
    return res.data;
  },
  resetDemo: async (): Promise<{ success: boolean; message: string }> => {
    const res = await api.post("/api/container/demo/reset");
    return res.data;
  }
};

export const digitalTwinAPI = {
  getState: async (): Promise<DigitalTwinVesselState> => {
    const res = await api.get<DigitalTwinVesselState>("/api/digital-twin/state");
    return res.data;
  },
  getLifecycle: async (): Promise<FourStageLifecycle> => {
    const res = await api.get<FourStageLifecycle>("/api/digital-twin/lifecycle");
    return res.data;
  },
  getPredictive: async (payload: PredictiveComparisonRequest): Promise<PredictiveComparison> => {
    const res = await api.post<PredictiveComparison>("/api/digital-twin/predictive", payload);
    return res.data;
  }
};

export const safetyGateAPI = {
  getStatus: async (): Promise<SafetyGateStatusResponse> => {
    const res = await api.get<SafetyGateStatusResponse>("/api/safety-gate/status");
    return res.data;
  },
  evaluate: async (payload: ContainerStabilityAnalysisRequest): Promise<SafetyGateEvaluationResponse> => {
    const res = await api.post<SafetyGateEvaluationResponse>("/api/safety-gate/evaluate", payload);
    return res.data;
  },
  evaluateLoading: async (payload: ContainerLoadConfirmRequest): Promise<SafetyGateEvaluationResponse> => {
    const res = await api.post<SafetyGateEvaluationResponse>("/api/safety-gate/evaluate-loading", payload);
    return res.data;
  },
  evaluateBallast: async (payload: BallastExecutionRequest): Promise<SafetyGateEvaluationResponse> => {
    const res = await api.post<SafetyGateEvaluationResponse>("/api/safety-gate/evaluate-ballast", payload);
    return res.data;
  }
};

export const operationsAPI = {
  getLiveStatus: async (): Promise<LiveOperationalStatusResponse> => {
    const res = await api.get<LiveOperationalStatusResponse>("/api/operations/live-status");
    return res.data;
  },
  resetFlow: async (): Promise<OperationalResetResponse> => {
    const res = await api.post<OperationalResetResponse>("/api/operations/reset");
    return res.data;
  },
  resetStage: async (): Promise<OperationalResetResponse> => {
    const res = await api.post<OperationalResetResponse>("/api/operations/reset");
    return res.data;
  },
  getPolicy: async (): Promise<OperationalPolicyResponse> => {
    const res = await api.get<OperationalPolicyResponse>("/api/operations/policy");
    return res.data;
  }
};

export const workflowAPI = {
  initiateFromImage: async (formData: FormData): Promise<any> => {
    const res = await api.post("/api/container/workflow/initiate", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return res.data;
  },
  confirmLoad: async (payload: { operation_id: string; operator_id?: string; operator_confirmed?: boolean; override_position?: any }): Promise<any> => {
    const res = await api.post("/api/container/workflow/confirm-load", payload);
    return res.data;
  },
  confirmBallast: async (payload: { operation_id: string; operator_id?: string; operator_confirmed?: boolean }): Promise<any> => {
    const res = await api.post("/api/container/workflow/confirm-ballast", payload);
    return res.data;
  },
  getActiveSession: async (): Promise<any> => {
    const res = await api.get("/api/container/workflow/active");
    return res.data;
  },
  getSession: async (operationId: string): Promise<any> => {
    const res = await api.get(`/api/container/workflow/session/${encodeURIComponent(operationId)}`);
    return res.data;
  },
  getTimeline: async (operationId?: string): Promise<any> => {
    const url = operationId ? `/api/container/workflow/timeline/${encodeURIComponent(operationId)}` : "/api/container/workflow/timeline";
    const res = await api.get(url);
    return res.data;
  },
  getRecentTimelines: async (limit: number = 20): Promise<any> => {
    const res = await api.get(`/api/container/workflow/timeline?limit=${limit}`);
    return res.data;
  },
  getHistory: async (limit: number = 20): Promise<any> => {
    const res = await api.get(`/api/container/workflow/history?limit=${limit}`);
    return res.data;
  },
  getAuditEvents: async (limit: number = 100, containerId?: string): Promise<TimelineEvent[]> => {
    const params = new URLSearchParams();
    params.append("limit", limit.toString());
    if (containerId) params.append("container_id", containerId);
    const res = await api.get(`/api/container/workflow/events?${params.toString()}`);
    return res.data;
  }
};

