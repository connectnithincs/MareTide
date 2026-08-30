import React, { useEffect, useState } from "react";
import { 
  FileText, CheckCircle2, ShieldCheck, UserCheck, 
  ArrowDownCircle, Scale, Droplet, CheckCheck, 
  AlertTriangle, XCircle, RefreshCw, Clock, Database, ChevronRight, Layers
} from "lucide-react";
import { workflowAPI } from "../utils/api";

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

  const getProvenanceBadge = (source: string) => {
    const s = (source || "").toUpperCase();
    if (s.includes("DOCUMENT")) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">[DOCUMENT AI]</span>;
    } else if (s.includes("OPERATOR")) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-purple-500/15 text-purple-300 border border-purple-500/30">[OPERATOR]</span>;
    } else if (s.includes("HARDWARE")) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-blue-500/15 text-blue-300 border border-blue-500/30">[HARDWARE TELEMETRY — NON-AUTHORITATIVE]</span>;
    } else if (s.includes("SIMULAT")) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30">[SIMULATED TELEMETRY]</span>;
    } else {
      return <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">[CALCULATED]</span>;
    }
  };


  return (
    <div className="flex flex-col h-full space-y-6 bg-brand-dark p-6 overflow-y-auto">
      {/* Top Header & Operation Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-brand-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Operational Traceability & Timeline</h2>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-accentBg text-brand-accent border border-brand-border">
              Phase 5 SQLite Audit
            </span>
          </div>
          <p className="text-xs text-brand-muted font-medium mt-1">
            Chronological audit trail of all container decisions, physics simulations, operator authorizations, and ballast executions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Operation Selector Dropdown */}
          <div className="flex items-center gap-2 bg-slate-900/80 border border-brand-border px-3 py-1.5 rounded-lg">
            <Layers className="w-4 h-4 text-brand-accent" />
            <select
              value={selectedOpId}
              onChange={(e) => setSelectedOpId(e.target.value)}
              className="bg-transparent text-xs font-bold text-brand-text outline-none cursor-pointer"
            >
              {operations.length === 0 ? (
                <option value="">No active operations</option>
              ) : (
                operations.map(op => (
                  <option key={op.operation_id} value={op.operation_id} className="bg-slate-900 text-white">
                    {op.operation_id} ({op.container_id || "PENDING"}) - {op.event_count} events
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
            className="p-2 bg-slate-900 border border-brand-border text-brand-muted hover:text-brand-text rounded-lg transition-colors flex items-center gap-1.5 text-xs font-semibold"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-brand-accent" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 10-Stage Visual Lifecycle Stepper */}
      <div className="bg-slate-950/60 border border-brand-border rounded-xl p-5 shadow-lg glass-panel">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-black text-brand-muted uppercase tracking-wider flex items-center gap-2">
            <Clock className="w-4 h-4 text-brand-accent" />
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
                className={`flex flex-col items-center justify-center p-3 rounded-lg border text-center transition-all ${
                  isCompleted 
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" 
                    : isReached && isFailed
                    ? "bg-red-500/10 border-red-500/30 text-red-400"
                    : "bg-slate-900/40 border-brand-border/40 text-brand-muted"
                }`}
              >
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-slate-900 border border-brand-border mb-1.5">
                  <Icon className={`w-3.5 h-3.5 ${isCompleted ? "text-emerald-400" : isReached && isFailed ? "text-red-400" : "text-slate-500"}`} />
                </div>
                <span className="text-[10px] font-black uppercase tracking-tight line-clamp-1">{st.label}</span>
                <span className="text-[9px] font-mono opacity-60 mt-0.5">Stage {idx + 1}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Chronological Event Stream */}
      <div className="bg-slate-950/60 border border-brand-border rounded-xl p-5 shadow-lg glass-panel flex-1">
        <div className="flex items-center justify-between mb-4 border-b border-brand-border pb-3">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-black text-brand-text uppercase tracking-wider">
              Audit Event Stream ({events.length} Events)
            </h3>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-brand-muted">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400"></span> Valid Document AI</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-400"></span> Calculated Hydrostatics</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-400"></span> Human-In-The-Loop</span>
          </div>
        </div>

        {events.length === 0 ? (
          <div className="py-16 text-center text-brand-muted text-xs font-semibold">
            No audit events found for operation ID "{selectedOpId}".
          </div>
        ) : (
          <div className="space-y-3 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-brand-border/40 before:pointer-events-none">
            {events.map((ev, idx) => {
              const isError = !ev.success || ev.event_type === "FAILED";
              return (
                <div key={ev.id || idx} className="relative flex items-start gap-4 pl-8 group">
                  {/* Timeline Dot */}
                  <div className={`absolute left-2 top-3 w-3 h-3 rounded-full border-2 transform -translate-x-1/2 transition-transform group-hover:scale-125 ${
                    isError 
                      ? "bg-red-500 border-slate-900 ring-2 ring-red-500/30" 
                      : "bg-cyan-400 border-slate-900 ring-2 ring-cyan-400/30"
                  }`} />

                  {/* Card Container */}
                  <div className={`flex-1 p-4 rounded-xl border transition-all ${
                    isError 
                      ? "bg-red-950/20 border-red-500/30" 
                      : "bg-slate-900/60 border-brand-border hover:border-brand-accent/50"
                  }`}>
                    {/* Header Row */}
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-black text-brand-text uppercase font-mono">
                          #{idx + 1} {ev.event_type}
                        </span>
                        {getProvenanceBadge(ev.source)}
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                          Actor: {ev.actor}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] text-brand-muted font-mono">
                        <Clock className="w-3 h-3" />
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
                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-brand-border/40">
                        {Object.entries(ev.relevant_metrics).map(([k, v]) => (
                          <span 
                            key={k} 
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-950 border border-brand-border/60 text-[10px] font-mono text-cyan-300"
                          >
                            <strong className="text-slate-400 font-semibold">{k}:</strong> {typeof v === "number" ? v.toFixed(2) : String(v)}
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
