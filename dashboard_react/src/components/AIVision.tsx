import React, { useEffect, useState } from "react";
import { visionAPI, API_BASE } from "../utils/api";
import { Eye, ShieldAlert, Video, RefreshCw, Camera, CheckCircle2 } from "lucide-react";
import { SectionHeader } from "./ui/SectionHeader";
import { StatusBadge } from "./ui/StatusBadge";

const formatTimestamp = (ts: any) => {
  if (!ts) return "";
  let date: Date;
  if (typeof ts === "number") {
    date = new Date(ts * 1000);
  } else if (typeof ts === "string") {
    const num = parseFloat(ts);
    if (!isNaN(num) && num > 1000000000 && num < 9999999999) {
      date = new Date(num * 1000);
    } else {
      date = new Date(ts);
    }
  } else {
    return "";
  }
  
  if (isNaN(date.getTime())) return String(ts);
  return date.toTimeString().split(" ")[0];
};

export const AIVision: React.FC = () => {
  const [cameras, setCameras] = useState<{ [key: string]: boolean }>({
    crew_safety: true,
    sea: true,
    cargo: true,
    ballast: true
  });
  const [sourceMode, setSourceMode] = useState<"simulated" | "live">("simulated");
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScenario, setSelectedScenario] = useState("Normal Voyage");
  const [feedback, setFeedback] = useState<string | null>(null);

  const showFeedback = (msg: string) => {
    setFeedback(msg);
    setTimeout(() => setFeedback(null), 3000);
  };

  const handleTriggerScenario = async () => {
    try {
      await visionAPI.setScenario(selectedScenario);
      showFeedback(`Simulation scenario triggered: ${selectedScenario}`);
      await fetchStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const handleClearAlerts = async () => {
    try {
      await visionAPI.clearAlerts();
      setAlerts([]);
      showFeedback("Alert history cleared!");
    } catch (err) {
      console.error(err);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await visionAPI.getStatus();
      setCameras(res.camera_states || {
        crew_safety: true,
        sea: true,
        cargo: true,
        ballast: true
      });
      setSourceMode(res.source_mode || "simulated");
      
      const alertLogs = await visionAPI.getAlerts();
      setAlerts(alertLogs.slice(0, 15));
    } catch (err) {
      console.error("Error loading CV status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const cameraNames: { [key: string]: string } = {
    crew_safety: "CAM 01: CREW SAFETY & PPE",
    sea: "CAM 02: SEA STATE & HORIZON",
    cargo: "CAM 03: STOWAGE BAY & CRANE",
    ballast: "CAM 04: DOUBLE-BOTTOM PUMPS"
  };

  return (
    <div className="space-y-4 font-mono text-xs">
      {/* Action feedback message */}
      {feedback && (
        <div className="p-2.5 rounded-xl bg-brand-safeBg border border-brand-safe/40 text-brand-safe font-bold flex items-center gap-2 animate-in fade-in duration-150">
          <CheckCircle2 className="w-4 h-4" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Camera Grid Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-2 border-b border-brand-borderSubtle gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-brand-muted uppercase font-bold">Scenario:</span>
          <select
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            className="surface-base border border-brand-border rounded-xl px-2.5 py-1 text-xs text-brand-text focus-ring"
          >
            <option value="Normal Voyage" className="bg-brand-elevated text-brand-text">Normal Voyage</option>
            <option value="Rough Sea" className="bg-brand-elevated text-brand-text">Rough Sea State</option>
            <option value="Cargo Shift Hazard" className="bg-brand-elevated text-brand-text">Cargo Shift Hazard</option>
            <option value="Man Overboard" className="bg-brand-elevated text-brand-text">Man Overboard (Safety)</option>
          </select>
          <button
            onClick={handleTriggerScenario}
            className="px-2.5 py-1 surface-base hover:bg-brand-hover text-brand-cyan border border-brand-cyan/30 rounded-xl text-[10px] font-bold uppercase transition-all shadow-sm"
          >
            Trigger
          </button>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[9px] font-bold px-2.5 py-0.5 rounded-full surface-base text-brand-safe border border-brand-safe/30">
            YOLOv8 Edge Engine Active
          </span>
          <button
            onClick={handleClearAlerts}
            className="text-[10px] text-brand-muted hover:text-brand-danger transition-colors underline"
          >
            Clear Log
          </button>
        </div>
      </div>

      {/* 4 HD Camera Video Matrix */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {Object.entries(cameras).map(([camId, isActive]) => {
          const streamUrl = `${API_BASE}/video_feed/${camId}?mode=${sourceMode}&t=${Date.now()}`;

          return (
            <div 
              key={camId}
              className="surface-elevated rounded-2xl border border-brand-borderSubtle overflow-hidden flex flex-col shadow-md group"
            >
              <div className="p-2.5 surface-base border-b border-brand-borderSubtle flex items-center justify-between text-[9.5px] font-bold">
                <span className="text-brand-text truncate">{cameraNames[camId] || camId}</span>
                <span className="w-2 h-2 rounded-full bg-brand-safe animate-pulse flex-shrink-0" />
              </div>

              <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden">
                {isActive ? (
                  <img
                    src={streamUrl}
                    alt={cameraNames[camId]}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = "none";
                    }}
                  />
                ) : (
                  <div className="text-center text-brand-muted text-[10px]">Camera Offline</div>
                )}
                {/* HUD Camera Crosshair Overlay */}
                <div className="absolute inset-0 border border-brand-cyan/10 pointer-events-none" />
                <div className="absolute top-1.5 left-1.5 text-[8px] font-mono text-brand-cyan font-bold bg-black/60 px-1.5 py-0.5 rounded-md border border-brand-cyan/20 backdrop-blur-sm">
                  REC • 1080p
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live AI Vision Threat Alerts Stream */}
      <div className="p-3.5 surface-elevated rounded-2xl border border-brand-borderSubtle space-y-2">
        <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block font-mono">
          Recent Edge Detection Events ({alerts.length})
        </span>

        <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
          {alerts.map((al, idx) => (
            <div 
              key={idx} 
              className="p-2 surface-base rounded-xl border border-brand-borderSubtle flex items-center justify-between text-[10.5px]"
            >
              <div className="flex items-center gap-2 min-w-0">
                <ShieldAlert className="w-3.5 h-3.5 text-brand-warning flex-shrink-0" />
                <span className="font-bold text-brand-text truncate">{al.message || al.category}</span>
              </div>
              <div className="flex items-center gap-2 text-[9px] text-brand-muted flex-shrink-0 font-mono">
                <span>{al.camera}</span>
                <span>{formatTimestamp(al.timestamp)}</span>
              </div>
            </div>
          ))}
          {alerts.length === 0 && (
            <div className="text-center py-3 text-[10px] text-brand-muted italic font-mono">
              All sectors clear. No safety or stowage anomalies detected.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

