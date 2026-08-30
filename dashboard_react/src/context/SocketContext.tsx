import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from "react";
import { vesselAPI } from "../utils/api";

export interface VesselState {
  ship_name: string;
  roll: number;
  pitch: number;
  distance: number;
  ballast_pct: number;
  cargo_kg: number;
  cargo_t: number;
  status: string;
  stability_score: number;
  stability_label: string;
  stability_risk: string;
  is_simulated: boolean;
  iot_flow_stage: string;
  planned_container: {
    id?: string;
    bay?: number;
    side?: string;
    tier?: number;
    weight?: number;
  };
  active_rec_bay: number;
  active_rec_side: string;
  ballast_tanks: {
    [key: string]: {
      name: string;
      current_volume: number;
      capacity: number;
      fill_ratio: number;
    };
  };
  containers: Array<{
    id: string;
    weight: number;
    bay: number;
    side: string;
    tier: number;
    provenance?: string;
  }>;
  is_pumping?: boolean;
  telemetry_timestamp?: string;
  telemetry_freshness?: "FRESH" | "STALE" | "DEGRADED" | "DISCONNECTED" | string;
  stale_seconds?: number;
  connection_status?: "CONNECTED" | "DISCONNECTED" | "STALE" | "DEGRADED" | "SIMULATED" | string;
  pump_state?: string;
  pump_flow_l_s?: number;
  pump_active?: boolean;
  provenance_map?: Record<string, string>;
  telemetry_source?: string;
  authoritative_weight_source?: string;
  alerts?: Array<{
    alert_type: string;
    severity: "INFO" | "WARNING" | "CRITICAL";
    threshold: string;
    observed_value: number;
    message: string;
    action: string;
  }>;
}

interface SocketContextProps {
  connected: boolean;
  vesselState: VesselState | null;
  refetchVesselState: () => Promise<VesselState | null>;
}

const SocketContext = createContext<SocketContextProps>({
  connected: false,
  vesselState: null,
  refetchVesselState: async () => null
});

export const useSocket = () => useContext(SocketContext);

export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [connected, setConnected] = useState(false);
  const [vesselState, setVesselState] = useState<VesselState | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const refetchVesselState = useCallback(async (): Promise<VesselState | null> => {
    try {
      const state = await vesselAPI.getState();
      if (state) {
        setVesselState(state as unknown as VesselState);
        return state as unknown as VesselState;
      }
    } catch (err) {
      console.warn("Failed direct vessel state fetch:", err);
    }
    return null;
  }, []);

  // Initial HTTP fetch on mount so UI renders immediately without waiting for WS message
  useEffect(() => {
    refetchVesselState();
  }, [refetchVesselState]);

  // WebSocket connection management with automatic reconnection
  useEffect(() => {
    let connectTimeout: number;
    let fallbackPollInterval: number;

    const connect = () => {
      const ws = new WebSocket("ws://localhost:8000/ws/telemetry");
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        window.clearInterval(fallbackPollInterval);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as VesselState;
          setVesselState(data);
        } catch (err) {
          console.error("Failed parsing telemetry WS message:", err);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Start conservative fallback polling (every 2.5s) while WS is offline
        window.clearInterval(fallbackPollInterval);
        fallbackPollInterval = window.setInterval(() => {
          refetchVesselState();
        }, 2500);

        connectTimeout = window.setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        ws.close();
      };
    };

    connect();

    return () => {
      window.clearTimeout(connectTimeout);
      window.clearInterval(fallbackPollInterval);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [refetchVesselState]);

  return (
    <SocketContext.Provider value={{ connected, vesselState, refetchVesselState }}>
      {children}
    </SocketContext.Provider>
  );
};
