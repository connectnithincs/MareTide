import React, { useEffect, useState } from "react";
import { useSocket } from "../context/SocketContext";
import { advisoryAPI } from "../utils/api";
import { BrainCircuit, AlertTriangle, ShieldAlert, CheckCircle, RefreshCw } from "lucide-react";

interface ExplainableRec {
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

export const AIAdvisor: React.FC = () => {
  const { vesselState } = useSocket();
  const [data, setData] = useState<{
    best_bay?: number;
    best_side?: string;
    best_score?: number;
    explainable_recs?: ExplainableRec[];
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchRecs = async () => {
    try {
      const res = await advisoryAPI.getRecommendations();
      setData(res);
    } catch (err) {
      console.error("Error fetching AI recommendations:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecs();
    // Re-fetch recommendations every 5 seconds to stay updated
    const interval = setInterval(fetchRecs, 5000);
    return () => clearInterval(interval);
  }, [vesselState?.containers.length]); // Refresh when container count changes

  if (loading || !vesselState) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-brand-dark p-8">
        <RefreshCw className="w-12 h-12 text-brand-accent animate-spin mb-4" />
        <p className="text-sm text-brand-muted font-bold animate-pulse">Calculating optimal stability recommendations...</p>
      </div>
    );
  }

  const recs = data?.explainable_recs || [];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">AI Loading Advisor</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Stowage recommendations and explainable physics solutions.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Explainable recommendations list (Left 2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="text-xs text-brand-muted font-bold uppercase tracking-wider pl-1">Explainable Stability Recommendations</h3>
          
          {recs.length > 0 ? (
            recs.map((rec, idx) => {
              const isHigh = rec.priority === "HIGH" || rec.priority === "CRITICAL";
              const borderCol = isHigh ? "border-brand-danger border-l-4" : "border-brand-accent border-l-4";
              const textCol = isHigh ? "text-brand-danger" : "text-brand-accent";
              const badgeBg = isHigh ? "bg-brand-dangerBg text-brand-danger border-brand-danger/20" : "bg-brand-accentBg text-brand-accent border-brand-accent/20";

              return (
                <div 
                  key={idx} 
                  className={`bg-brand-card border border-brand-border rounded-xl p-5 shadow-lg glass-panel ${borderCol}`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <h4 className="text-sm font-black text-brand-text uppercase tracking-wide">{rec.action}</h4>
                    <span className={`text-[9px] px-2 py-0.5 rounded font-black tracking-widest border ${badgeBg}`}>
                      {rec.priority}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs leading-relaxed font-semibold mt-4 text-brand-text">
                    <div>
                      <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider mb-0.5">Condition</span>
                      {rec.condition}
                    </div>
                    <div>
                      <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider mb-0.5">Cause</span>
                      {rec.cause}
                    </div>
                    <div>
                      <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider mb-0.5">Affected Bays</span>
                      {rec.bays}
                    </div>
                    <div>
                      <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider mb-0.5">Affected Tanks</span>
                      {rec.tanks}
                    </div>
                    <div>
                      <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider mb-0.5">Discharge Target</span>
                      {rec.water} tonnes
                    </div>
                    <div>
                      <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider mb-0.5">Projected Index</span>
                      <span className="text-brand-accent">{rec.pred_score.toFixed(1)}%</span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-brand-border text-xs text-brand-muted italic leading-relaxed">
                    <strong className="text-brand-text not-italic font-bold block text-[10px] uppercase tracking-wider mb-1">Engineering Explanation</strong>
                    {rec.engineering}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="bg-brand-card border border-brand-border rounded-xl p-8 text-center text-brand-muted italic font-bold glass-panel">
              No active warnings. System running within stable criteria.
            </div>
          )}
        </div>

        {/* Dynamic AI Placement suggestion (Right 1 col) */}
        <div className="space-y-4">
          <h3 className="text-xs text-brand-muted font-bold uppercase tracking-wider pl-1">Best Cargo Placement</h3>
          
          {data?.best_bay ? (
            <div className="bg-brand-card border border-brand-border rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
              <div className="flex items-center gap-2 pb-2 border-b border-brand-border">
                <BrainCircuit className="text-brand-accent w-5 h-5 animate-pulse" />
                <span className="text-xs font-black text-brand-text uppercase tracking-wide">Next Loading Target</span>
              </div>

              <div className="bg-slate-950/40 border border-brand-border p-4 rounded-lg flex flex-col gap-3 text-xs font-semibold">
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Suggested Bay</span>
                  <span className="text-brand-text">Bay {data.best_bay}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Suggested Side</span>
                  <span className="text-brand-text uppercase">{data.best_side}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] font-bold tracking-wider">Projected Score</span>
                  <span className="text-brand-accent">{data.best_score?.toFixed(1)}%</span>
                </div>
              </div>

              <p className="text-[11px] text-brand-muted leading-relaxed">
                Applying container weight to the suggested location balances transverse moments and maximizes the metacentric height (GM) buffer.
              </p>
            </div>
          ) : (
            <div className="bg-brand-card border border-brand-border rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-3">
              <div className="flex items-center gap-2 pb-2 border-b border-brand-border text-brand-danger">
                <ShieldAlert className="w-5 h-5" />
                <span className="text-xs font-black uppercase tracking-wide">Stowage Locked</span>
              </div>
              <p className="text-xs text-brand-muted leading-relaxed font-bold">
                ⚠️ No further cargo should be loaded. Ballast tanks have reached capacity limits.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
