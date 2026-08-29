import React, { createContext, useContext, useEffect, useState, useRef } from "react";

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
  }>;
  is_pumping?: boolean;
}

interface SocketContextProps {
  connected: boolean;
  vesselState: VesselState | null;
}

const SocketContext = createContext<SocketContextProps>({
  connected: false,
  vesselState: null
});

export const useSocket = () => useContext(SocketContext);

export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [connected, setConnected] = useState(false);
  const [vesselState, setVesselState] = useState<VesselState | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let connectTimeout: number;

    const connect = () => {
      console.log("Connecting to telemetry WebSocket...");
      const ws = new WebSocket("ws://localhost:8000/ws/telemetry");
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("Telemetry WebSocket connected.");
        setConnected(true);
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
        console.log("Telemetry WebSocket disconnected. Retrying in 3s...");
        setConnected(false);
        connectTimeout = window.setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(connectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return (
    <SocketContext.Provider value={{ connected, vesselState }}>
      {children}
    </SocketContext.Provider>
  );
};
