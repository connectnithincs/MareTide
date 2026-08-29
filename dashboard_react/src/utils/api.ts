import axios from "axios";

const API_BASE = "http://localhost:8010";

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
