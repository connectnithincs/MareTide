import React, { useEffect, useState } from "react";
import { visionAPI } from "../utils/api";
import { Eye, ShieldAlert, Video, RefreshCw, ToggleLeft, ToggleRight, Camera } from "lucide-react";

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

const getAuthenticatedUrl = (url: string, user: string, pass: string) => {
  if (!url) return "";
  if (!user || !pass) return url;
  
  const cleanUrl = url.trim();
  const cleanUser = encodeURIComponent(user.trim());
  const cleanPass = encodeURIComponent(pass.trim());
  
  // Check if it already has credentials in the URL
  if (cleanUrl.includes("@") && (cleanUrl.startsWith("http") || cleanUrl.startsWith("rtsp"))) {
    return cleanUrl;
  }
  
  const protocolMatch = cleanUrl.match(/^(https?:\/\/|rtsp:\/\/)/i);
  if (protocolMatch) {
    const protocol = protocolMatch[0];
    const rest = cleanUrl.substring(protocol.length);
    return `${protocol}${cleanUser}:${cleanPass}@${rest}`;
  }
  
  return `http://${cleanUser}:${cleanPass}@${cleanUrl}`;
};

export const AIVision: React.FC = () => {
  const [cameras, setCameras] = useState<{ [key: string]: boolean }>({
    sea: true,
    cargo: true,
    ballast: true
  });
  const [sourceMode, setSourceMode] = useState<"simulated" | "live">("simulated");
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScenario, setSelectedScenario] = useState("Normal Voyage");

  const handleTriggerScenario = async () => {
    try {
      await visionAPI.setScenario(selectedScenario);
      alert(`Simulation scenario triggered: ${selectedScenario}`);
      await fetchStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const handleClearAlerts = async () => {
    try {
      await visionAPI.clearAlerts();
      setAlerts([]);
      alert("Alert history cleared!");
    } catch (err) {
      console.error(err);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await visionAPI.getStatus();
      setCameras(res.camera_states || {
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
    // Poll alerts every 3 seconds for active UI updates
    const interval = setInterval(async () => {
      try {
        const alertLogs = await visionAPI.getAlerts();
        setAlerts(alertLogs.slice(0, 15));
      } catch (err) {}
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const handleToggleCamera = async (camId: string) => {
    const nextState = !cameras[camId];
    // Update local state first for instant response
    setCameras(prev => ({ ...prev, [camId]: nextState }));
    try {
      await visionAPI.toggleCamera(camId, nextState);
    } catch (err) {
      console.error(err);
      // Revert state on error
      setCameras(prev => ({ ...prev, [camId]: !nextState }));
    }
  };

  const handleToggleSourceMode = async (mode: "simulated" | "live") => {
    setSourceMode(mode);
    try {
      let source: any = 0;
      if (mode === "live") {
        const rawUrl = localStorage.getItem("vision_cam_source") || "0";
        const user = localStorage.getItem("vision_cam_user") || "";
        const pass = localStorage.getItem("vision_cam_pass") || "";
        source = getAuthenticatedUrl(rawUrl, user, pass);
      }
      await visionAPI.toggleSourceMode(mode, source);
    } catch (err) {
      console.error(err);
    }
  };

  const cameraMetadata = [
    { id: "sea", label: "Sea State Monitoring", model: "YOLOv8 Live" },
    { id: "cargo", label: "Stowage Cargo Security", model: "Simulated overlays" },
    { id: "ballast", label: "Ballast Leak Monitor", model: "Motion analysis" }
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">AI Vision Systems</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Surveillance and automated computer vision alert pipelines.</p>
        </div>

        {/* Global Controls */}
        <div className="flex items-center gap-3 bg-brand-app border border-brand-border p-1.5 rounded-lg text-xs font-bold text-brand-text shadow-sm">
          <span className="text-[10px] text-brand-muted uppercase font-bold tracking-wider px-2">Webcam Source</span>
          <button
            onClick={() => handleToggleSourceMode("simulated")}
            className={`px-3 py-1.5 rounded transition-all ${
              sourceMode === "simulated" ? "bg-brand-accent text-slate-950" : "hover:text-brand-text text-brand-muted"
            }`}
          >
            Simulated Loops
          </button>
          <button
            onClick={() => handleToggleSourceMode("live")}
            className={`px-3 py-1.5 rounded transition-all ${
              sourceMode === "live" ? "bg-brand-accent text-slate-950" : "hover:text-brand-text text-brand-muted"
            }`}
          >
            Live Webcams
          </button>
        </div>
      </div>

      {/* Simulation Scenario Trigger Bar */}
      {sourceMode === "simulated" && (
        <div className="border border-brand-border bg-brand-card rounded-xl p-4 shadow-lg glass-panel flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs font-semibold">
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] text-brand-muted uppercase font-bold tracking-wider">Simulation Scenario Selection</span>
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              className="bg-brand-app border border-brand-border rounded px-3 py-2 text-brand-text font-bold focus:outline-none focus:border-brand-accent"
            >
              <option value="Normal Voyage">Normal Voyage</option>
              <option value="Cargo Misplacement">Cargo Misplacement</option>
              <option value="Ballast Leak">Ballast Leak</option>
              <option value="Sea Obstacle">Sea Obstacle</option>
            </select>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleTriggerScenario}
              className="px-4 py-2.5 bg-brand-accent hover:bg-brand-accent/90 text-slate-950 rounded-lg uppercase tracking-wider font-extrabold text-xs transition-all flex items-center gap-2 shadow-sm"
            >
              <ShieldAlert className="w-4 h-4" />
              <span>Trigger Scenario</span>
            </button>
            <button
              onClick={handleClearAlerts}
              className="px-4 py-2.5 bg-brand-app hover:bg-brand-border/40 text-brand-text rounded-lg border border-brand-border uppercase tracking-wider font-extrabold text-xs transition-all"
            >
              Clear Alerts
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center flex flex-col items-center justify-center gap-3">
          <RefreshCw className="w-8 h-8 text-brand-accent animate-spin" />
          <span className="text-xs text-brand-muted font-semibold">Warming up YOLOv8 vision pipeline...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Cameras Grid (Left 2 cols) */}
          <div className="xl:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            {cameraMetadata.map((cam) => {
              const enabled = cameras[cam.id];
              return (
                <div 
                  key={cam.id} 
                  className="bg-brand-card border border-brand-border rounded-xl overflow-hidden shadow-md flex flex-col glass-panel"
                >
                  {/* Header bar */}
                  <div className="px-4 py-3 border-b border-brand-border/60 bg-slate-950/40 flex justify-between items-center text-xs">
                    <div className="flex items-center gap-2">
                      <Video className="w-4 h-4 text-brand-accent" />
                      <div>
                        <span className="font-extrabold block text-brand-text">{cam.label}</span>
                        <span className="text-[9px] text-brand-muted uppercase font-black tracking-wide">{cam.model}</span>
                      </div>
                    </div>
                    {/* Toggle Button */}
                    <button
                      onClick={() => handleToggleCamera(cam.id)}
                      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border font-bold transition-all ${
                        enabled 
                          ? "bg-brand-accentBg border-brand-accent/20 text-brand-accent" 
                          : "bg-brand-dangerBg border-brand-danger/20 text-brand-danger"
                      }`}
                    >
                      {enabled ? <Camera className="w-3.5 h-3.5" /> : null}
                      <span>{enabled ? "ACTIVE" : "OFFLINE"}</span>
                    </button>
                  </div>

                  {/* Frame Container */}
                  <div className="aspect-video bg-slate-950 flex items-center justify-center relative overflow-hidden">
                    {enabled ? (
                      <img
                        src={`http://localhost:8001/api/video/${cam.id}?t=${Date.now()}`}
                        className="w-full h-full object-cover"
                        alt={cam.label}
                      />
                    ) : (
                      <div className="text-center p-6 flex flex-col items-center justify-center gap-2">
                        <Eye className="w-8 h-8 text-brand-danger opacity-40" />
                        <span className="text-xs text-brand-muted font-bold uppercase tracking-wider">
                          Feed Manually Disabled
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Active Alerts List (Right 1 col) */}
          <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
            <div className="flex items-center gap-2 pb-2 border-b border-brand-border">
              <ShieldAlert className="text-brand-danger w-5 h-5 animate-pulse" />
              <h3 className="font-black text-xs text-brand-text tracking-wide uppercase">Active Safety Alerts</h3>
            </div>

            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {alerts.map((alert, idx) => {
                const isCritical = alert.severity === "CRITICAL" || alert.severity === "WARNING";
                const borderCol = isCritical ? "border-brand-danger" : "border-brand-accent";
                
                return (
                  <div 
                    key={idx} 
                    className={`bg-brand-app border-l-4 ${borderCol} border border-brand-border/60 rounded p-3 text-[11px] font-semibold shadow-sm`}
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-extrabold uppercase text-brand-text">{alert.category}</span>
                      <span className="text-[9px] text-brand-muted">{formatTimestamp(alert.timestamp)}</span>
                    </div>
                    <p className="text-brand-muted leading-relaxed mb-1">{alert.message}</p>
                    <div className="flex justify-between text-[9px] text-brand-muted">
                      <span>Cam: {alert.camera}</span>
                      <span className={isCritical ? "text-brand-danger font-bold" : "text-brand-accent font-bold"}>
                        {alert.severity}
                      </span>
                    </div>
                  </div>
                );
              })}
              {alerts.length === 0 && (
                <span className="text-xs text-brand-muted italic font-semibold text-center block py-10">
                  No camera warnings detected.
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
