import React from "react";
import { useSocket } from "../context/SocketContext";
import { Grid, Anchor, RefreshCw } from "lucide-react";

export const DeckView: React.FC = () => {
  const { vesselState } = useSocket();

  if (!vesselState) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-brand-dark p-8">
        <RefreshCw className="w-12 h-12 text-brand-accent animate-spin mb-4" />
        <p className="text-sm text-brand-muted font-bold animate-pulse">Loading stowage grid...</p>
      </div>
    );
  }

  const { containers } = vesselState;
  const totalBays = 4;

  const getContainersForBay = (bayNum: number, side: "port" | "starboard") => {
    return containers.filter((c) => c.bay === bayNum && c.side === side);
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Ship Deck Plan Grid</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Stowage bay configuration and container placements.</p>
        </div>
      </div>

      {/* Grid Bays List */}
      <div className="space-y-6">
        {Array.from({ length: totalBays }).map((_, idx) => {
          const bayNum = idx + 1;
          const portContainers = getContainersForBay(bayNum, "port");
          const starboardContainers = getContainersForBay(bayNum, "starboard");

          return (
            <div key={bayNum} className="grid grid-cols-1 md:grid-cols-9 gap-4 items-center">
              {/* Port Side Card */}
              <div className="md:col-span-4 border border-brand-border bg-brand-card rounded-xl p-4 shadow-md glass-panel min-h-[110px]">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-xs font-black uppercase text-brand-text">Port Bay {bayNum}</span>
                  <span className="text-[9px] px-2 py-0.5 rounded-full font-black tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">PORT</span>
                </div>
                
                {portContainers.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {portContainers.map((c) => {
                      const badgeCol = c.tier % 2 === 1 ? "bg-emerald-600 hover:bg-emerald-500" : "bg-amber-600 hover:bg-amber-500";
                      return (
                        <span 
                          key={c.id} 
                          className={`${badgeCol} text-white px-2.5 py-1 rounded text-xs font-bold transition-colors cursor-default`}
                        >
                          {c.id} ({c.weight.toFixed(0)}t) T{c.tier}
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <span className="text-xs text-brand-muted italic font-bold">No containers stowed</span>
                )}
              </div>

              {/* Center Divider label */}
              <div className="md:col-span-1 text-center py-2 md:py-0">
                <span className="text-sm font-black text-brand-text tracking-wide uppercase px-3 py-1 bg-slate-900 border border-brand-border rounded-lg shadow-sm">
                  BAY {bayNum}
                </span>
              </div>

              {/* Starboard Side Card */}
              <div className="md:col-span-4 border border-brand-border bg-brand-card rounded-xl p-4 shadow-md glass-panel min-h-[110px]">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-xs font-black uppercase text-brand-text">Starboard Bay {bayNum}</span>
                  <span className="text-[9px] px-2 py-0.5 rounded-full font-black tracking-wider bg-blue-500/10 text-blue-400 border border-blue-500/20">STARBOARD</span>
                </div>
                
                {starboardContainers.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {starboardContainers.map((c) => {
                      const badgeCol = c.tier % 2 === 1 ? "bg-blue-600 hover:bg-blue-500" : "bg-orange-600 hover:bg-orange-500";
                      return (
                        <span 
                          key={c.id} 
                          className={`${badgeCol} text-white px-2.5 py-1 rounded text-xs font-bold transition-colors cursor-default`}
                        >
                          {c.id} ({c.weight.toFixed(0)}t) T{c.tier}
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <span className="text-xs text-brand-muted italic font-bold">No containers stowed</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
