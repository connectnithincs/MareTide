import axios from "axios";

const API_BASE = "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true
});

export const authAPI = {
  exchangeToken: async (token: string) => {
    const res = await api.get(`/api/auth/exchange?token=${token}`);
    return res.data;
  },
  checkSession: async () => {
    const res = await api.get("/api/auth/session");
    return res.data;
  }
};

export const vesselAPI = {
  getState: async () => {
    const res = await api.get("/api/vessel-state");
    return res.data;
  },
  calculateCompensation: async (id: string, bay: number, side: string, tier: number) => {
    const res = await api.post("/api/ballast/calculate-compensation", { id, bay, side, tier });
    return res.data;
  },
  confirmDrain: async () => {
    const res = await api.post("/api/ballast/confirm-drain");
    return res.data;
  },
  clearScale: async () => {
    const res = await api.post("/api/ballast/clear-scale");
    return res.data;
  },
  adjustBallast: async (tank_key: string, action: "fill" | "drain", qty: number) => {
    const res = await api.post("/api/ballast/adjust", { tank_key, action, qty });
    return res.data;
  },
  pumpBallast: async (from_side: string, to_side: string, amount: number, from_bay: string, to_bay: string) => {
    const res = await api.post("/api/ballast/pump", { from_side, to_side, amount, from_bay, to_bay });
    return res.data;
  }
};

export const advisoryAPI = {
  getRecommendations: async () => {
    const res = await api.get("/api/recommendations");
    return res.data;
  }
};

export const reportsAPI = {
  getCargoManifest: async () => {
    const res = await api.get("/api/reports/cargo-manifest");
    return res.data;
  },
  getBallastLog: async () => {
    const res = await api.get("/api/reports/ballast-log");
    return res.data;
  },
  getOpsLog: async () => {
    const res = await api.get("/api/reports/ops-log");
    return res.data;
  },
  clearAll: async () => {
    const res = await api.post("/api/reports/clear");
    return res.data;
  }
};

export const telemetryAPI = {
  connect: async (port: string | null, is_simulated: boolean) => {
    const res = await api.post("/api/telemetry/connect", { port, is_simulated });
    return res.data;
  },
  disconnect: async () => {
    const res = await api.post("/api/telemetry/disconnect");
    return res.data;
  },
  getPorts: async () => {
    const res = await api.get("/api/telemetry/ports");
    return res.data;
  },
  simulateCargo: async (weight_t: number) => {
    const res = await api.post("/api/telemetry/simulate/cargo", { weight_t });
    return res.data;
  },
  simulateTilt: async (roll: number | null, pitch: number | null) => {
    const res = await api.post("/api/telemetry/simulate/tilt", { roll, pitch });
    return res.data;
  }
};

export const telemetryV2API = {
  getLive: async () => {
    const res = await api.get("/api/telemetry/live");
    return res.data;
  },
  getHealth: async () => {
    const res = await api.get("/api/telemetry/health");
    return res.data;
  },
  getSources: async () => {
    const res = await api.get("/api/telemetry/sources");
    return res.data;
  },
  selectSource: async (source: "HARDWARE_SENSOR" | "SIMULATED_TELEMETRY", port?: string) => {
    const res = await api.post("/api/telemetry/source/select", { source, port });
    return res.data;
  }
};

export const visionAPI = {
  getStatus: async () => {
    const res = await api.get("/api/vision/status");
    return res.data;
  },
  toggleCamera: async (camera_id: string, enabled: boolean) => {
    const res = await api.post(`/api/vision/camera/${camera_id}/toggle`, { enabled });
    return res.data;
  },
  toggleSourceMode: async (mode: "simulated" | "live", device_index: any = 0) => {
    const res = await api.post("/api/vision/source-mode", { mode, device_index });
    return res.data;
  },
  getAlerts: async () => {
    const res = await api.get("/api/vision/alerts");
    return res.data;
  },
  setScenario: async (scenario: string) => {
    const res = await api.post("/api/vision/scenario", { scenario });
    return res.data;
  },
  clearAlerts: async () => {
    const res = await api.post("/api/vision/alerts/clear");
    return res.data;
  }
};

export const voyageAPI = {
  getProfile: async () => {
    const res = await api.get("/api/voyage/profile");
    return res.data;
  },
  getTrack: async (imo: string) => {
    const res = await api.get(`/api/voyage/track?imo=${imo}`);
    return res.data;
  }
};

export const containerAPI = {
  extract: async (formData: FormData) => {
    const res = await api.post("/api/container/extract", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return res.data;
  },
  analyzeStability: async (payload: any) => {
    const res = await api.post("/api/container/stability/analyze", payload);
    return res.data;
  },
  confirmAndLoad: async (payload: any) => {
    const res = await api.post("/api/container/load/confirm", payload);
    return res.data;
  },
  getLoadingAudit: async (limit: number = 100) => {
    const res = await api.get(`/api/container/load/audit?limit=${limit}`);
    return res.data;
  },
  calculateBallastCompensation: async (payload: any) => {
    const res = await api.post("/api/container/ballast/calculate", payload);
    return res.data;
  },
  executeBallastCompensation: async (payload: any) => {
    const res = await api.post("/api/container/ballast/execute", payload);
    return res.data;
  },
  planManifest: async (payload: any) => {
    const res = await api.post("/api/container/stability/manifest-plan", payload);
    return res.data;
  },
  executeManifest: async (payload: any) => {
    const res = await api.post("/api/container/manifest/execute", payload);
    return res.data;
  }
};

export const digitalTwinAPI = {
  getState: async () => {
    const res = await api.get("/api/digital-twin/state");
    return res.data;
  },
  getLifecycle: async () => {
    const res = await api.get("/api/digital-twin/lifecycle");
    return res.data;
  },
  getPredictive: async (payload: { container_id: string; gross_weight_t: number; bay: number; side: string; tier?: number }) => {
    const res = await api.post("/api/digital-twin/predictive", payload);
    return res.data;
  }
};

export const operationsAPI = {
  getLiveStatus: async () => {
    const res = await api.get("/api/operations/live-status");
    return res.data;
  },
  resetFlow: async () => {
    const res = await api.post("/api/operations/reset");
    return res.data;
  },
  getPolicy: async () => {
    const res = await api.get("/api/operations/policy");
    return res.data;
  }
};

export const workflowAPI = {
  initiateFromImage: async (formData: FormData) => {
    const res = await api.post("/api/container/workflow/initiate", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return res.data;
  },
  confirmLoad: async (payload: { operation_id: string; operator_id?: string; operator_confirmed?: boolean; override_position?: any }) => {
    const res = await api.post("/api/container/workflow/confirm-load", payload);
    return res.data;
  },
  confirmBallast: async (payload: { operation_id: string; operator_id?: string; operator_confirmed?: boolean }) => {
    const res = await api.post("/api/container/workflow/confirm-ballast", payload);
    return res.data;
  },
  approveReview: async (payload: { operation_id: string; operator_id?: string; operator_notes?: string }) => {
    const res = await api.post("/api/container/workflow/approve-review", payload);
    return res.data;
  },
  reject: async (payload: { operation_id: string; reason: string; operator_id?: string }) => {
    const res = await api.post("/api/container/workflow/reject", payload);
    return res.data;
  },
  getActiveSession: async () => {
    const res = await api.get("/api/container/workflow/active");
    return res.data;
  },
  getSession: async (operationId: string) => {
    const res = await api.get(`/api/container/workflow/session/${operationId}`);
    return res.data;
  },
  getHistory: async (limit: number = 20) => {
    const res = await api.get(`/api/container/workflow/history?limit=${limit}`);
    return res.data;
  },
  getTimeline: async (operationId: string) => {
    const res = await api.get(`/api/container/workflow/timeline/${operationId}`);
    return res.data;
  },
  getRecentTimelines: async (limit: number = 20) => {
    const res = await api.get(`/api/container/workflow/timeline?limit=${limit}`);
    return res.data;
  },
  getAuditEvents: async (limit: number = 100, containerId?: string) => {
    const params = new URLSearchParams();
    params.append("limit", limit.toString());
    if (containerId) params.append("container_id", containerId);
    const res = await api.get(`/api/container/workflow/events?${params.toString()}`);
    return res.data;
  }
};



