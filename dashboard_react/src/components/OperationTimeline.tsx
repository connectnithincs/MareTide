import React, { useEffect, useState } from "react";
import { 
  FileText, CheckCircle2, ShieldCheck, UserCheck, 
  ArrowDownCircle, Scale, Droplet, CheckCheck, 
  RefreshCw, Clock, Database, Layers
} from "lucide-react";
import { workflowAPI } from "../utils/api";
import { SafetyBadge } from "./ui/SafetyBadge";
import { SectionHeader } from "./ui/SectionHeader";
import { StatusBadge } from "./ui/StatusBadge";

interface AuditEvent {
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
  reason: string;
  success: boolean;
}

interface OperationSummary {
  operation_id: string;
  container_id: string;
  event_count: number;
  started_at: string;
  updated_at: string;
}

const STAGES = [
  { key: "DOCUMENT_RECEIVED", label: "Document", icon: FileText },
  { key: "VALIDATING", label: "Validated", icon: CheckCircle2 },
  { key: "ANALYZING_STABILITY", label: "Stability Analyzed", icon: Scale },
  { key: "AWAITING_OPERATOR_CONFIRMATION", label: "Approved", icon: UserCheck },
  { key: "LOADED", label: "Loaded", icon: ArrowDownCircle },
  { key: "BALLAST_CALCULATED", label: "Ballast Calculated", icon: Droplet },
  { key: "AWAITING_BALLAST_CONFIRMATION", label: "Ballast Approved", icon: ShieldCheck },
  { key: "BALLAST_EXECUTING", label: "Ballast Executed", icon: Droplet },
  { key: "VERIFYING", label: "Verified", icon: CheckCheck },
  { key: "COMPLETED", label: "Completed", icon: CheckCircle2 }
];

export const OperationTimeline: React.FC<{ initialOperationId?: string }> = ({ initialOperationId }) => {
  const [operations, setOperations] = useState<OperationSummary[]>([]);
  const [selectedOpId, setSelectedOpId] = useState<string>(initialOperationId || "");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // 1. Fetch recent operations
  const fetchOperations = async () => {
    try {
      const res = await workflowAPI.getRecentTimelines(20);
      if (res && res.operations) {
        setOperations(res.operations);
        if (!selectedOpId && res.operations.length > 0) {
          setSelectedOpId(res.operations[0].operation_id);
        }
      }
    } catch (err) {
      console.error("Failed to load operations summary:", err);
    }
  };

  // 2. Fetch timeline for selected operation
  const fetchTimeline = async (opId: string) => {
    if (!opId) return;
    setLoading(true);
    try {
      const res = await workflowAPI.getTimeline(opId);
      if (res && res.timeline) {
        setEvents(res.timeline);
      }
    } catch (err) {
      console.error(`Failed to load timeline for ${opId}:`, err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOperations();
  }, []);

  useEffect(() => {
    if (selectedOpId) {
      fetchTimeline(selectedOpId);
    }
  }, [selectedOpId]);

  useEffect(() => {
    if (!autoRefresh || !selectedOpId) return;
    const interval = setInterval(() => {
      fetchTimeline(selectedOpId);
      fetchOperations();
    }, 4000);
    return () => clearInterval(interval);
  }, [autoRefresh, selectedOpId]);

  // Compute stage statuses
  const currentEventTypes = new Set(events.map(e => e.event_type));
  const isFailed = events.some(e => e.event_type === "FAILED" || !e.success);

  return (
    <div className="flex flex-col space-y-5 font-mono text-xs">
      {/* Top Header & Operation Selector */}
      <div className="surface-elevated border border-brand-borderSubtle p-5 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-black text-brand-text tracking-wide uppercase font-mono">
              Operational Traceability & Timeline
            </h2>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-cyanBg text-brand-cyan border border-brand-cyan/30">
              Phase 5 SQLite Audit
            </span>
          </div>
          <p className="text-xs text-brand-muted font-medium mt-1">
            Chronological audit trail of all container decisions, physics simulations, operator authorizations, and ballast executions.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Operation Selector Dropdown */}
          <div className="flex items-center gap-2 surface-base border border-brand-border rounded-xl px-3 py-1.5 shadow-sm">
            <Layers className="w-4 h-4 text-brand-cyan flex-shrink-0" />
            <select
              value={selectedOpId}
              onChange={(e) => setSelectedOpId(e.target.value)}
              className="bg-transparent text-xs font-bold text-brand-text outline-none cursor-pointer focus-ring"
            >
              {operations.length === 0 ? (
                <option value="">No active operations</option>
              ) : (
                operations.map(op => (
                  <option key={op.operation_id} value={op.operation_id} className="bg-brand-elevated text-brand-text">
                    {op.operation_id} ({op.container_id || "PENDING"}) — {op.event_count} events
                  </option>
                ))
              )}
            </select>
          </div>

          <button
            onClick={() => {
              if (selectedOpId) fetchTimeline(selectedOpId);
              fetchOperations();
            }}
            disabled={loading}
            className="p-2 surface-base hover:bg-brand-hover border border-brand-borderSubtle text-brand-muted hover:text-brand-text rounded-xl transition-all flex items-center gap-1.5 text-xs font-bold shadow-sm active:scale-95"
            title="Refresh Timeline"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-brand-cyan" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 10-Stage Visual Lifecycle Stepper */}
      <div className="surface-elevated border border-brand-borderSubtle rounded-2xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-brand-borderSubtle">
          <h3 className="text-xs font-black text-brand-text uppercase tracking-wider flex items-center gap-2 font-mono">
            <Clock className="w-4 h-4 text-brand-cyan" />
            <span>Operational Stage Progression (10 Stages)</span>
          </h3>
          <span className="text-[11px] text-brand-muted font-mono">
            Operation: <strong className="text-brand-text">{selectedOpId || "NONE"}</strong>
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
          {STAGES.map((st, idx) => {
            const Icon = st.icon;
            const isReached = currentEventTypes.has(st.key) || (st.key === "DOCUMENT_RECEIVED" && events.length > 0);
            const isCompleted = isReached && !isFailed;
            
            return (
              <div 
                key={st.key}
                className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                  isCompleted 
                    ? "bg-brand-safeBg border-brand-safe/40 text-brand-safe shadow-sm" 
                    : isReached && isFailed
                    ? "bg-brand-dangerBg border-brand-danger/40 text-brand-danger"
                    : "surface-base border-brand-borderSubtle/60 text-brand-muted opacity-75"
                }`}
              >
                <div className={`flex items-center justify-center w-7 h-7 rounded-full border mb-1.5 ${
                  isCompleted 
                    ? "bg-brand-safe text-slate-950 border-brand-safe" 
                    : isReached && isFailed
                    ? "bg-brand-danger text-white border-brand-danger"
                    : "surface-base border-brand-borderSubtle text-brand-muted"
                }`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <span className="text-[10px] font-black uppercase tracking-tight line-clamp-1">{st.label}</span>
                <span className="text-[9px] font-mono opacity-70 mt-0.5">Stage {idx + 1}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Chronological Event Stream */}
      <div className="surface-elevated border border-brand-borderSubtle rounded-2xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 border-b border-brand-borderSubtle pb-3 gap-2">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-brand-cyan" />
            <h3 className="text-xs font-black text-brand-text uppercase tracking-wider font-mono">
              Audit Event Stream ({events.length} Events)
            </h3>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-brand-muted flex-wrap">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-brand-safe"></span> Document AI</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-brand-cyan"></span> Hydrostatics</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-brand-purple"></span> Officer Gate</span>
          </div>
        </div>

        {events.length === 0 ? (
          <div className="py-16 text-center text-brand-muted text-xs font-semibold">
            No audit events found for operation ID "{selectedOpId}".
          </div>
        ) : (
          <div className="space-y-3 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-brand-borderSubtle before:pointer-events-none">
            {events.map((ev, idx) => {
              const isError = !ev.success || ev.event_type === "FAILED";
              return (
                <div key={ev.id || idx} className="relative flex items-start gap-4 pl-8 group">
                  {/* Timeline Dot */}
                  <div className={`absolute left-2 top-3 w-3 h-3 rounded-full border-2 transform -translate-x-1/2 transition-transform group-hover:scale-125 ${
                    isError 
                      ? "bg-brand-danger border-brand-abyss ring-2 ring-brand-danger/30" 
                      : "bg-brand-cyan border-brand-abyss ring-2 ring-brand-cyan/30"
                  }`} />

                  {/* Card Container */}
                  <div className={`flex-1 p-4 rounded-xl border transition-all ${
                    isError 
                      ? "bg-brand-dangerBg/30 border-brand-danger/40 text-brand-danger" 
                      : "surface-base border-brand-borderSubtle hover:border-brand-cyan/40 hover:bg-brand-hover shadow-sm"
                  }`}>
                    {/* Header Row */}
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-black text-brand-text uppercase font-mono">
                          #{idx + 1} {ev.event_type}
                        </span>
                        <SafetyBadge type={ev.source} size="sm" />
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold surface-base text-brand-muted border border-brand-borderSubtle">
                          Actor: {ev.actor}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] text-brand-muted font-mono">
                        <Clock className="w-3 h-3 text-brand-cyan" />
                        <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                        <span className="text-[9px] opacity-60">({ev.timestamp.split("T")[0]})</span>
                      </div>
                    </div>

                    {/* Reason Narrative */}
                    <p className="text-xs text-brand-text font-medium leading-relaxed mb-3">
                      {ev.reason}
                    </p>

                    {/* Relevant Metrics Pill-Grid */}
                    {ev.relevant_metrics && Object.keys(ev.relevant_metrics).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-brand-borderSubtle">
                        {Object.entries(ev.relevant_metrics).map(([k, v]) => (
                          <span 
                            key={k} 
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded surface-base border border-brand-borderSubtle text-[10px] font-mono text-brand-cyan"
                          >
                            <strong className="text-brand-muted font-semibold">{k}:</strong> {typeof v === "number" ? v.toFixed(2) : String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

