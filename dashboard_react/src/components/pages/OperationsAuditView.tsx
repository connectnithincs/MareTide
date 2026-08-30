import React, { useState } from "react";
import { OperationTimeline } from "../OperationTimeline";
import { Reports } from "../Reports";
import { 
  FileSpreadsheet, 
  GitCommit, 
  Database
} from "lucide-react";
import { SafetyBadge } from "../ui/SafetyBadge";

export const OperationsAuditView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"timeline" | "reports">("timeline");

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 bg-brand-abyss">
      {/* 1. Station Header & Sub-Tab Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-brand-borderSubtle">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-brand-cyanBg border border-brand-cyan/30 rounded-xl text-brand-cyan shadow-sm shadow-brand-cyan/20">
            <FileSpreadsheet className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-sm font-mono font-black text-brand-text uppercase tracking-widest">
                OPERATIONS TRACEABILITY & COMPLIANCE AUDIT
              </h1>
              <SafetyBadge type="SOLAS_VGM" size="sm" />
            </div>
            <p className="text-[11px] text-brand-muted font-medium mt-0.5">
              Immutable SHA-256 state transition provenance, 10-stage container lifecycles, and exportable SOLAS VGM manifests.
            </p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center surface-base p-1 rounded-xl border border-brand-borderSubtle text-xs font-mono font-bold">
          <button
            onClick={() => setActiveTab("timeline")}
            className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-2 ${
              activeTab === "timeline"
                ? "bg-brand-cyan text-slate-950 shadow-md shadow-brand-cyan/20 font-black"
                : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
            }`}
          >
            <GitCommit className="w-3.5 h-3.5" />
            <span>10-Stage Lifecycle Timeline</span>
          </button>

          <button
            onClick={() => setActiveTab("reports")}
            className={`px-3.5 py-1.5 rounded-lg transition-all flex items-center gap-2 ${
              activeTab === "reports"
                ? "bg-brand-cyan text-slate-950 shadow-md shadow-brand-cyan/20 font-black"
                : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>Compliance Manifests & CSV</span>
          </button>
        </div>
      </div>

      {/* 2. Active Tab Content */}
      {activeTab === "timeline" ? (
        <div className="space-y-5">
          <OperationTimeline />
        </div>
      ) : (
        <div className="space-y-4">
          <Reports />
        </div>
      )}
    </div>
  );
};
