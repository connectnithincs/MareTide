import React from "react";
import { useSocket } from "../context/SocketContext";
import { BallastControlTable } from "./BallastControlTable";
import { SCADADigitalTwin } from "./SCADADigitalTwin";
import { Activity } from "lucide-react";

export const BallastControl: React.FC = () => {
  const { vesselState } = useSocket();

  if (!vesselState) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-brand-dark p-8">
        <Activity className="w-12 h-12 text-brand-accent animate-spin mb-4" />
        <p className="text-sm text-brand-muted font-bold animate-pulse">Initializing ballast controls...</p>
      </div>
    );
  }

  const handleAdjustComplete = () => {
    // WebSockets will automatically push updates down, so no manual refresh is needed!
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Ballast Control Systems</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Manual ballast tank valve manipulation and flow calculations.</p>
        </div>
      </div>

      {/* Grid: Twin on top/left, Control Table on bottom/right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SCADADigitalTwin tanks={vesselState.ballast_tanks} />
        </div>
        <div>
          <BallastControlTable 
            tanks={vesselState.ballast_tanks} 
            onAdjustComplete={handleAdjustComplete} 
          />
        </div>
      </div>
    </div>
  );
};
