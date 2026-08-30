import React from "react";
import { BrainCircuit, AlertTriangle, CheckCircle } from "lucide-react";

interface RecommendationCardProps {
  bestBay: number;
  bestSide: string;
  bestScore: number;
  recommendations: string[];
  stabilityScore: number;
}

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  bestBay,
  bestSide,
  bestScore,
  recommendations,
  stabilityScore
}) => {
  const isSafe = stabilityScore <= 60;

  return (
    <div className="w-full border border-brand-border bg-brand-card rounded-xl p-5 flex flex-col gap-4 shadow-lg glass-panel">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-3">
        <div className="flex items-center gap-2">
          <BrainCircuit className="text-brand-accent w-5 h-5 animate-pulse" />
          <h3 className="font-extrabold text-sm text-brand-text tracking-wide uppercase">AI Advisor Advice</h3>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded font-black tracking-widest uppercase ${
          isSafe ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
        }`}>
          {isSafe ? "STATUS: STABLE" : "STATUS: HEAVING"}
        </span>
      </div>

      {/* Target Recommendation placement */}
      {bestBay !== undefined && bestBay > 0 ? (
        <div className="bg-brand-accentBg border border-brand-accent/20 rounded-lg p-3.5 flex items-start gap-3">
          <CheckCircle className="text-brand-accent w-5 h-5 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-xs font-bold text-brand-text">Optimal Placement Suggested</h4>
            <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
              Place the planned container cargo in <strong className="text-brand-accent uppercase">Bay {bestBay} ({bestSide})</strong>. 
              This coordinates with automated compensation, yielding a projected stability index of <strong>{bestScore.toFixed(1)}%</strong>.
            </p>

          </div>
        </div>
      ) : (
        <div className="bg-brand-dangerBg border border-brand-danger/20 rounded-lg p-3.5 flex items-start gap-3">
          <AlertTriangle className="text-brand-danger w-5 h-5 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-xs font-bold text-brand-text">No Space / Extreme Stability Risk</h4>
            <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
              Compensation tanks are at maximum capacity. Pumping additional ballast water is impossible. Please remove cargo weight or discharge active tanks.
            </p>
          </div>
        </div>
      )}

      {/* Recommendations List */}
      <div className="flex flex-col gap-2">
        <span className="text-[10px] text-brand-muted uppercase font-bold tracking-wider">Urgent Stability Actions</span>
        {recommendations && recommendations.length > 0 ? (
          <ul className="space-y-1.5 pl-4 list-disc text-[11px] text-brand-text leading-relaxed font-semibold">
            {recommendations.map((rec, idx) => (
              <li key={idx} className="marker:text-brand-accent">{rec}</li>
            ))}
          </ul>
        ) : (
          <span className="text-xs text-brand-muted italic">Vessel stability parameters fully optimized.</span>
        )}
      </div>
    </div>
  );
};
