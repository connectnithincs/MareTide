import React, { useEffect, useState } from "react";
import { reportsAPI, visionAPI } from "../utils/api";
import { History, Eye, ShieldAlert, Clock, RefreshCw } from "lucide-react";

export const HistoryLogs: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"operations" | "vision">("operations");
  const [opsLogs, setOpsLogs] = useState<any[]>([]);
  const [visionAlerts, setVisionAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      if (activeTab === "operations") {
        const ops = await reportsAPI.getOpsLog();
        setOpsLogs(ops);
      } else {
        const alerts = await visionAPI.getAlerts();
        setVisionAlerts(alerts);
      }
    } catch (err) {
      console.error("Failed to load logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Historical Logs</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Review chronological operations history and vision safety alerts.</p>
        </div>
        <button 
          onClick={fetchData}
          className="p-2 bg-slate-900 border border-brand-border text-brand-muted hover:text-brand-text rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs Row */}
      <div className="flex gap-1 border-b border-brand-border">
        <button
          onClick={() => setActiveTab("operations")}
          className={`px-4 py-2 text-xs font-black uppercase tracking-wider border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "operations" 
              ? "border-brand-accent text-brand-accent bg-brand-accentBg/10" 
              : "border-transparent text-brand-muted hover:text-brand-text"
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Vessel Operations Log</span>
        </button>
        <button
          onClick={() => setActiveTab("vision")}
          className={`px-4 py-2 text-xs font-black uppercase tracking-wider border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "vision" 
              ? "border-brand-accent text-brand-accent bg-brand-accentBg/10" 
              : "border-transparent text-brand-muted hover:text-brand-text"
          }`}
        >
          <Eye className="w-4 h-4" />
          <span>AI Vision Alarms Log</span>
        </button>
      </div>

      {/* Content */}
      <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel">
        {loading ? (
          <div className="py-20 text-center flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-8 h-8 text-brand-accent animate-spin" />
            <span className="text-xs text-brand-muted font-semibold">Retrieving operations logs...</span>
          </div>
        ) : activeTab === "operations" ? (
          <div className="space-y-4">
            <h3 className="text-xs text-brand-muted font-bold uppercase tracking-wider pb-2 border-b border-brand-border">Telemetry Operations Feed</h3>
            
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {opsLogs.map((log, idx) => (
                <div key={idx} className="bg-slate-950/40 border border-brand-border/60 rounded-lg p-3 flex justify-between items-center text-xs font-semibold">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                      log.event === "LOAD" ? "bg-emerald-500/10 text-emerald-400" : "bg-brand-dangerBg text-brand-danger"
                    }`}>
                      {log.event}
                    </span>
                    <span className="text-brand-text">
                      Container <strong className="text-brand-accent">{log.container}</strong> ({log.weight.toFixed(1)}t) stowed at <strong className="uppercase">Bay {log.bay}/{log.side}/T{log.tier}</strong>
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="block text-brand-muted text-[10px]">{log.time}</span>
                    <span className="text-[9px] text-brand-muted">Source: {log.source}</span>
                  </div>
                </div>
              ))}
              {opsLogs.length === 0 && (
                <p className="text-xs text-brand-muted italic text-center py-10 font-bold">No historical operations found.</p>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <h3 className="text-xs text-brand-muted font-bold uppercase tracking-wider pb-2 border-b border-brand-border">Webcam Alarm History (SQLite)</h3>
            
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {visionAlerts.map((alert, idx) => {
                const isCritical = alert.severity === "CRITICAL" || alert.severity === "WARNING";
                const borderCol = isCritical ? "border-brand-danger" : "border-brand-accent";
                const badgeCol = isCritical ? "bg-brand-dangerBg text-brand-danger border-brand-danger/20" : "bg-brand-accentBg text-brand-accent border-brand-accent/20";
                
                return (
                  <div 
                    key={idx} 
                    className={`bg-slate-950/40 border-l-4 ${borderCol} border border-brand-border/60 rounded-lg p-4 flex gap-4 items-start`}
                  >
                    <ShieldAlert className={`w-5 h-5 mt-0.5 flex-shrink-0 ${isCritical ? "text-brand-danger" : "text-brand-accent"}`} />
                    
                    <div className="flex-1 text-xs font-semibold">
                      <div className="flex justify-between items-center mb-1">
                        <h4 className="font-extrabold text-brand-text text-sm uppercase tracking-wide">{alert.category}</h4>
                        <span className="text-[10px] text-brand-muted">{alert.timestamp}</span>
                      </div>
                      
                      <p className="text-brand-text mb-2 leading-relaxed">{alert.message}</p>
                      
                      <div className="flex gap-4 text-[10px] text-brand-muted uppercase font-bold tracking-wider">
                        <span>Camera: <strong className="text-brand-text">{alert.camera}</strong></span>
                        <span>Severity: <span className={`px-1.5 py-0.5 rounded border ${badgeCol}`}>{alert.severity}</span></span>
                      </div>
                    </div>
                  </div>
                );
              })}
              {visionAlerts.length === 0 && (
                <p className="text-xs text-brand-muted italic text-center py-10 font-bold">No vision alarms logged.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
