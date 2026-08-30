import React, { useEffect, useState } from "react";
import { telemetryAPI, visionAPI } from "../utils/api";
import { useSocket } from "../context/SocketContext";
import { useTheme, type ThemeMode } from "../context/ThemeContext";
import { 
  SlidersHorizontal, 
  Cpu, 
  RefreshCw, 
  Radio, 
  Shield, 
  AlertTriangle, 
  Compass, 
  Camera,
  CheckCircle2,
  MapPin,
  Save,
  Check,
  Sun,
  Moon,
  Monitor
} from "lucide-react";
import { VirtualESP32ScenarioControl } from "./VirtualESP32ScenarioControl";
import { SectionHeader } from "./ui/SectionHeader";
import { StatusBadge } from "./ui/StatusBadge";

export const Settings: React.FC = () => {
  const { vesselState } = useSocket();
  const { theme, themeMode, setThemeMode } = useTheme();

  const [ports, setPorts] = useState<string[]>([]);
  const [selectedPort, setSelectedPort] = useState("");
  const [isSimulated, setIsSimulated] = useState(true);
  const [loading, setLoading] = useState(false);
  const [reloadingPorts, setReloadingPorts] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Map configuration states
  const [mapProvider, setMapProvider] = useState(() => localStorage.getItem("map_provider") || "osm");
  const [mapApiKey, setMapApiKey] = useState(() => localStorage.getItem("map_api_key") || "");

  const showToast = (text: string, type: "success" | "error" = "success") => {
    setFeedbackMsg({ text, type });
    setTimeout(() => setFeedbackMsg(null), 4000);
  };

  const saveMapSettings = () => {
    localStorage.setItem("map_provider", mapProvider);
    localStorage.setItem("map_api_key", mapApiKey);
    showToast("Map provider settings saved successfully!");
  };

  // AI Vision camera configurations
  const [visionCamType, setVisionCamType] = useState(() => localStorage.getItem("vision_cam_type") || "usb");
  const [visionCamSource, setVisionCamSource] = useState(() => localStorage.getItem("vision_cam_source") || "0");
  const [visionCamUser, setVisionCamUser] = useState(() => localStorage.getItem("vision_cam_user") || "");
  const [visionCamPass, setVisionCamPass] = useState(() => localStorage.getItem("vision_cam_pass") || "");

  const saveVisionSettings = () => {
    localStorage.setItem("vision_cam_type", visionCamType);
    localStorage.setItem("vision_cam_source", visionCamSource);
    localStorage.setItem("vision_cam_user", visionCamUser);
    localStorage.setItem("vision_cam_pass", visionCamPass);
    showToast("AI Vision camera settings updated!");
  };

  const loadPorts = async () => {
    setReloadingPorts(true);
    try {
      const res = await telemetryAPI.getPorts();
      setPorts(res.ports || []);
      if (res.ports && res.ports.length > 0) {
        setSelectedPort(res.ports[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setReloadingPorts(false);
    }
  };

  useEffect(() => {
    loadPorts();
    if (vesselState) {
      setIsSimulated(vesselState.status === "SIMULATOR" || vesselState.status === "IDLE" || !vesselState.status.includes("COM"));
    }
  }, []);

  const handleConnect = async () => {
    setLoading(true);
    try {
      await telemetryAPI.connect(isSimulated ? null : selectedPort, isSimulated);
      showToast(isSimulated ? "Switched to Simulated Telemetry Stream" : `Bound to serial port ${selectedPort}`);
    } catch (err: any) {
      showToast("Failed to connect to specified telemetry parameters", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await telemetryAPI.disconnect();
      showToast("Hardware serial link released. Reverted to Simulator.");
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Toast feedback banner */}
      {feedbackMsg && (
        <div className={`p-3.5 rounded-xl border backdrop-blur-xl flex items-center gap-2.5 transition-all animate-in fade-in duration-200 ${
          feedbackMsg.type === "success" 
            ? "bg-brand-safeBg text-brand-safe border-brand-safe/40 shadow-sm shadow-brand-safe/10" 
            : "bg-brand-dangerBg text-brand-danger border-brand-danger/40 shadow-sm shadow-brand-danger/10"
        }`}>
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span className="font-bold">{feedbackMsg.text}</span>
        </div>
      )}

      {/* 1. Visual Theme Preferences */}
      <div className="p-4 surface-elevated rounded-2xl border border-brand-borderSubtle space-y-3 shadow-sm">
        <SectionHeader title="Visual Theme & Interface Appearance" icon={Sun} />

        <div className="space-y-2">
          <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block">
            Interface Theme Mode
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: "dark" as ThemeMode, label: "Dark (SCADA)", icon: Moon },
              { id: "light" as ThemeMode, label: "Light (Pearl)", icon: Sun },
              { id: "system" as ThemeMode, label: "Auto (System)", icon: Monitor }
            ].map((item) => {
              const Icon = item.icon;
              const isSelected = themeMode === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setThemeMode(item.id);
                    showToast(`Theme switched to ${item.label}`);
                  }}
                  className={`py-2.5 px-3 rounded-xl border text-center font-bold text-[11px] uppercase transition-all flex items-center justify-center gap-1.5 shadow-sm ${
                    isSelected
                      ? "bg-brand-cyan text-slate-950 border-brand-cyan shadow-sm font-black"
                      : "surface-base text-brand-textSecondary border-brand-borderSubtle hover:text-brand-text hover:bg-brand-hover"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </div>
          <span className="text-[9.5px] text-brand-muted block mt-1">
            Active visual mode: <strong className="text-brand-text uppercase">{theme}</strong>. Changes take effect instantly across all stations.
          </span>
        </div>
      </div>

      {/* 2. Telemetry Hardware Link Config */}
      <div className="p-4 surface-elevated rounded-2xl border border-brand-borderSubtle space-y-3 shadow-sm">
        <SectionHeader title="Serial Port Telemetry Binding" icon={Radio} />

        <div className="space-y-3">
          <div>
            <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
              Telemetry Reader Source
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setIsSimulated(true)}
                className={`py-2 px-3 rounded-xl border text-center font-bold text-xs uppercase transition-all shadow-sm ${
                  isSimulated
                    ? "bg-brand-cyan text-slate-950 border-brand-cyan font-black"
                    : "surface-base text-brand-textSecondary border-brand-borderSubtle hover:text-brand-text hover:bg-brand-hover"
                }`}
              >
                Simulator Stream
              </button>
              <button
                type="button"
                onClick={() => setIsSimulated(false)}
                className={`py-2 px-3 rounded-xl border text-center font-bold text-xs uppercase transition-all shadow-sm ${
                  !isSimulated
                    ? "bg-brand-cyan text-slate-950 border-brand-cyan font-black"
                    : "surface-base text-brand-textSecondary border-brand-borderSubtle hover:text-brand-text hover:bg-brand-hover"
                }`}
              >
                Physical Hardware COM
              </button>
            </div>
          </div>

          {!isSimulated && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider">
                  Available COM Ports
                </label>
                <button
                  onClick={loadPorts}
                  disabled={reloadingPorts}
                  className="text-brand-cyan hover:underline flex items-center gap-1 text-[10px] font-bold"
                >
                  <RefreshCw className={`w-3 h-3 ${reloadingPorts ? "animate-spin" : ""}`} />
                  <span>Scan Ports</span>
                </button>
              </div>

              <select
                value={selectedPort}
                onChange={(e) => setSelectedPort(e.target.value)}
                className="w-full surface-base border border-brand-border rounded-xl px-3 py-2 text-brand-text text-xs focus-ring"
              >
                {ports.map((p) => (
                  <option key={p} value={p} className="bg-brand-elevated text-brand-text">{p}</option>
                ))}
                {ports.length === 0 && (
                  <option value="" className="bg-brand-elevated text-brand-muted">No COM ports detected (Plug in ESP32 via USB)</option>
                )}
              </select>
            </div>
          )}

          <div className="pt-2 flex items-center gap-2">
            <button
              onClick={handleConnect}
              disabled={loading || (!isSimulated && !selectedPort)}
              className="flex-1 py-2.5 bg-brand-cyan hover:bg-brand-cyan/90 disabled:opacity-50 text-slate-950 rounded-xl font-black text-xs uppercase transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              <span>Apply Connection</span>
            </button>
            <button
              onClick={handleDisconnect}
              disabled={loading}
              className="py-2.5 px-3 surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text border border-brand-borderSubtle rounded-xl font-bold text-xs uppercase transition-all shadow-sm"
            >
              Disconnect
            </button>
          </div>
        </div>
      </div>

      {/* 3. Virtual ESP32 Hardware Scenario Controls */}
      <VirtualESP32ScenarioControl />

      {/* 4. Live Map Intelligence API Settings */}
      <div className="p-4 surface-elevated rounded-2xl border border-brand-borderSubtle space-y-3 shadow-sm">
        <SectionHeader title="Voyage Tracking Map Provider" icon={MapPin} />

        <div className="space-y-3">
          <div>
            <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
              Tile Provider Engine
            </label>
            <select
              value={mapProvider}
              onChange={(e) => setMapProvider(e.target.value)}
              className="w-full surface-base border border-brand-border rounded-xl px-3 py-2 text-brand-text text-xs focus-ring"
            >
              <option value="osm" className="bg-brand-elevated text-brand-text">OpenStreetMap (Standard Free - No Token)</option>
              <option value="mapbox" className="bg-brand-elevated text-brand-text">Mapbox Vector (Requires API Key)</option>
              <option value="stadia" className="bg-brand-elevated text-brand-text">Stadia Maps (Alidade Dark/Light)</option>
              <option value="jawg" className="bg-brand-elevated text-brand-text">JawgMaps Nautical Style</option>
              <option value="thunderforest" className="bg-brand-elevated text-brand-text">Thunderforest Transport</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
              Provider API Token / Secret
            </label>
            <input
              type="text"
              placeholder="Paste public access token..."
              value={mapApiKey}
              onChange={(e) => setMapApiKey(e.target.value)}
              className="w-full surface-base border border-brand-border rounded-xl px-3 py-2 text-brand-text text-xs placeholder-brand-muted/60 focus-ring"
            />
          </div>

          <div className="pt-1">
            <button
              onClick={saveMapSettings}
              className="w-full py-2 surface-base hover:bg-brand-hover text-brand-cyan border border-brand-cyan/30 rounded-xl font-bold text-xs uppercase transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Save Map Configuration</span>
            </button>
          </div>
        </div>
      </div>

      {/* 5. AI Vision Camera Stream Settings */}
      <div className="p-4 surface-elevated rounded-2xl border border-brand-borderSubtle space-y-3 shadow-sm">
        <SectionHeader title="CCTV Camera Stream Sources" icon={Camera} />

        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
                Hardware Camera Type
              </label>
              <select
                value={visionCamType}
                onChange={(e) => setVisionCamType(e.target.value)}
                className="w-full surface-base border border-brand-border rounded-xl px-3 py-2 text-brand-text text-xs focus-ring"
              >
                <option value="usb" className="bg-brand-elevated text-brand-text">Local USB / UVC Video Device</option>
                <option value="rtsp" className="bg-brand-elevated text-brand-text">IP Camera RTSP Stream</option>
                <option value="http" className="bg-brand-elevated text-brand-text">HTTP / MJPEG Endpoint</option>
              </select>
            </div>

            <div>
              <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
                Device Index or Stream URI
              </label>
              <input
                type="text"
                placeholder="0 or rtsp://192.168.1.100:554/h264"
                value={visionCamSource}
                onChange={(e) => setVisionCamSource(e.target.value)}
                className="w-full surface-base border border-brand-border rounded-xl px-3 py-2 text-brand-text text-xs placeholder-brand-muted/60 focus-ring"
              />
            </div>
          </div>

          {visionCamType === "rtsp" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
                  RTSP Username
                </label>
                <input
                  type="text"
                  placeholder="admin"
                  value={visionCamUser}
                  onChange={(e) => setVisionCamUser(e.target.value)}
                  className="w-full surface-base border border-brand-border rounded-xl px-3 py-2 text-brand-text text-xs focus-ring"
                />
              </div>

              <div>
                <label className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
                  RTSP Password
                </label>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={visionCamPass}
                  onChange={(e) => setVisionCamPass(e.target.value)}
                  className="w-full surface-base border border-brand-border rounded-xl px-3 py-2 text-brand-text text-xs focus-ring"
                />
              </div>
            </div>
          )}

          <div className="pt-1">
            <button
              onClick={saveVisionSettings}
              className="w-full py-2 surface-base hover:bg-brand-hover text-brand-cyan border border-brand-cyan/30 rounded-xl font-bold text-xs uppercase transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Save Camera Stream Configuration</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
