import React, { useEffect, useState } from "react";
import { telemetryAPI, visionAPI } from "../utils/api";
import { useSocket } from "../context/SocketContext";
import { Settings as SettingsIcon, Cpu, RefreshCw, Radio, Shield, AlertTriangle, Compass, Camera } from "lucide-react";

export const Settings: React.FC = () => {
  const { vesselState } = useSocket();
  const [ports, setPorts] = useState<string[]>([]);
  const [selectedPort, setSelectedPort] = useState("");
  const [isSimulated, setIsSimulated] = useState(true);
  const [loading, setLoading] = useState(false);
  const [reloadingPorts, setReloadingPorts] = useState(false);

  // Map configuration states
  const [mapProvider, setMapProvider] = useState(() => localStorage.getItem("map_provider") || "osm");
  const [mapApiKey, setMapApiKey] = useState(() => localStorage.getItem("map_api_key") || "");

  const saveMapSettings = () => {
    localStorage.setItem("map_provider", mapProvider);
    localStorage.setItem("map_api_key", mapApiKey);
    alert("Map settings saved successfully! Load the Voyage Intelligence tab to view the styled high-fidelity map.");
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
    alert("AI Vision camera settings saved! Toggle to Live Webcams in the AI Vision tab to stream this source.");
  };

  // Simulation overrides states
  const [simWeight, setSimWeight] = useState(1.5);
  const [overrideRoll, setOverrideRoll] = useState("");
  const [overridePitch, setOverridePitch] = useState("");

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
      alert("Telemetry reader reconfigured successfully!");
    } catch (err) {
      alert("Failed to connect to specified telemetry parameters");
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await telemetryAPI.disconnect();
      alert("Hardware connection released. Reverted to Simulator.");
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">System Settings</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Configure hardware serial streams, simulation models, and testing overrides.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Telemetry Hardware Link Config */}
        <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
          <div className="flex items-center gap-2 pb-2 border-b border-brand-border">
            <Cpu className="text-brand-accent w-5 h-5" />
            <h3 className="font-black text-xs text-brand-text uppercase tracking-wide">IoT Telemetry Hardware Link</h3>
          </div>

          <div className="space-y-4 text-xs font-semibold">
            {/* Mode selection */}
            <div>
              <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-2">Operation Mode</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer text-brand-text">
                  <input
                    type="radio"
                    name="mode"
                    checked={isSimulated}
                    onChange={() => setIsSimulated(true)}
                    className="accent-brand-accent"
                  />
                  <span>Simulate IoT Telemetry</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-brand-text">
                  <input
                    type="radio"
                    name="mode"
                    checked={!isSimulated}
                    onChange={() => setIsSimulated(false)}
                    className="accent-brand-accent"
                  />
                  <span>ESP32 Physical Port Link</span>
                </label>
              </div>
            </div>

            {/* COM Port select */}
            {!isSimulated && (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider">Select Serial COM Port</label>
                  <button
                    onClick={loadPorts}
                    disabled={reloadingPorts}
                    className="text-brand-accent flex items-center gap-1 hover:underline"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${reloadingPorts ? "animate-spin" : ""}`} />
                    <span>Scan Ports</span>
                  </button>
                </div>
                
                {ports.length > 0 ? (
                  <select
                    value={selectedPort}
                    onChange={(e) => setSelectedPort(e.target.value)}
                    className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
                  >
                    {ports.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                ) : (
                  <div className="bg-brand-dangerBg border border-brand-danger/20 text-brand-danger p-3 rounded-lg text-[11px]">
                    ⚠️ No physical serial COM ports detected on this system. Make sure the ESP32 is connected via USB.
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-4 pt-2">
              <button
                onClick={handleConnect}
                disabled={loading || (!isSimulated && ports.length === 0)}
                className="flex-1 py-2 bg-brand-accent hover:bg-brand-accent/90 disabled:opacity-50 text-slate-950 font-black uppercase rounded-lg transition-colors"
              >
                {isSimulated ? "Initialize Simulator" : "Establish COM Connection"}
              </button>
              {!isSimulated && (
                <button
                  onClick={handleDisconnect}
                  disabled={loading}
                  className="px-4 py-2 bg-brand-dangerBg text-brand-danger hover:bg-brand-danger/20 border border-brand-danger/30 font-black uppercase rounded-lg transition-colors"
                >
                  Disconnect
                </button>
              )}
            </div>
          </div>
        </div>

        {/* AI Vision Settings Panel */}
        <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
          <div className="flex items-center gap-2 pb-2 border-b border-brand-border">
            <Camera className="text-brand-accent w-5 h-5" />
            <h3 className="font-black text-xs text-brand-text uppercase tracking-wide">AI Vision Camera Config</h3>
          </div>

          <div className="space-y-4 text-xs font-semibold">
            <div>
              <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-2">Webcam Source Type</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer text-brand-text">
                  <input
                    type="radio"
                    name="vision_cam_type"
                    checked={visionCamType === "usb"}
                    onChange={() => {
                      setVisionCamType("usb");
                      setVisionCamSource("0");
                    }}
                    className="accent-brand-accent"
                  />
                  <span>Local USB / Virtual Webcam</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-brand-text">
                  <input
                    type="radio"
                    name="vision_cam_type"
                    checked={visionCamType === "ip"}
                    onChange={() => {
                      setVisionCamType("ip");
                      setVisionCamSource("http://192.168.1.100:8080/video");
                    }}
                    className="accent-brand-accent"
                  />
                  <span>Mobile IP Camera (Wi-Fi)</span>
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider">
                {visionCamType === "usb" ? "Device Index (0, 1, 2...)" : "IP Camera Video Stream URL"}
              </label>
              <input
                type="text"
                value={visionCamSource}
                onChange={(e) => setVisionCamSource(e.target.value)}
                placeholder={visionCamType === "usb" ? "0" : "e.g., http://192.168.1.50:8080/video"}
                className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
              />
              <p className="text-[10px] text-brand-muted mt-1 leading-normal">
                {visionCamType === "usb" 
                  ? "Standard USB ports or DroidCam/iVCam virtual drivers usually register as index 0 or 1." 
                  : "Enter the MJPEG/RTSP stream link exposed by IP webcam mobile apps (e.g., IP Webcam on Android)."}
              </p>
            </div>

            {visionCamType === "ip" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider">Stream Username (Optional)</label>
                  <input
                    type="text"
                    value={visionCamUser}
                    onChange={(e) => setVisionCamUser(e.target.value)}
                    placeholder="e.g., admin"
                    className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider">Stream Password (Optional)</label>
                  <input
                    type="password"
                    value={visionCamPass}
                    onChange={(e) => setVisionCamPass(e.target.value)}
                    placeholder="password"
                    className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
                  />
                </div>
              </div>
            )}

            <button
              onClick={saveVisionSettings}
              className="w-full py-2 bg-brand-accent hover:bg-brand-accent/90 text-slate-950 font-black uppercase rounded-lg transition-colors"
            >
              Save Camera Settings
            </button>
          </div>
        </div>

        {/* General Ship Details Panel */}
        <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
          <div className="flex items-center gap-2 pb-2 border-b border-brand-border">
            <Radio className="text-brand-accent w-5 h-5" />
            <h3 className="font-black text-xs text-brand-text uppercase tracking-wide">General Ship Details</h3>
          </div>

          <div className="space-y-4 text-xs font-semibold leading-relaxed">
            <div className="space-y-3">
              <div className="bg-brand-app border border-brand-border p-3.5 rounded-lg flex justify-between items-center shadow-sm">
                <span className="text-brand-muted uppercase text-[10px] tracking-wider">Ship Model Name</span>
                <span className="font-black text-brand-text">MareTide Twin</span>
              </div>
              <div className="bg-brand-app border border-brand-border p-3.5 rounded-lg flex justify-between items-center shadow-sm">
                <span className="text-brand-muted uppercase text-[10px] tracking-wider">Bays Configured</span>
                <span className="font-black text-brand-text">4 Bays</span>
              </div>
              <div className="bg-brand-app border border-brand-border p-3.5 rounded-lg flex justify-between items-center shadow-sm">
                <span className="text-brand-muted uppercase text-[10px] tracking-wider">Compartment Volume</span>
                <span className="font-black text-brand-text">300 t (virtual scale)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Map Configuration Panel */}
        <div className="border border-brand-border bg-brand-card rounded-xl p-5 shadow-lg glass-panel flex flex-col gap-4">
          <div className="flex items-center gap-2 pb-2 border-b border-brand-border">
            <Compass className="text-brand-accent w-5 h-5" />
            <h3 className="font-black text-xs text-brand-text uppercase tracking-wide">AIS Tracking Map Config</h3>
          </div>

          <div className="space-y-4 text-xs font-semibold">
            <div>
              <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-2">Map Provider</label>
              <select
                value={mapProvider}
                onChange={(e) => setMapProvider(e.target.value)}
                className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
              >
                <option value="osm">OpenStreetMap (Default, Free)</option>
                <option value="mapbox">Mapbox (Dynamic Dark/Light Styles)</option>
                <option value="stadia">Stadia Maps (Alidade Smooth)</option>
                <option value="jawg">JawgMaps (Light/Dark Themes)</option>
                <option value="thunderforest">Thunderforest (Atlas/Transport)</option>
              </select>
            </div>

            {mapProvider !== "osm" && (
              <div className="space-y-2">
                <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider">Map API Access Token / Key</label>
                <input
                  type="password"
                  value={mapApiKey}
                  onChange={(e) => setMapApiKey(e.target.value)}
                  placeholder="Paste your map service API key here..."
                  className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold"
                />
                <p className="text-[10px] text-brand-muted mt-1 leading-normal">
                  The API key is securely saved locally in your browser's configuration cache.
                </p>
              </div>
            )}

            <button
              onClick={saveMapSettings}
              className="w-full py-2.5 bg-brand-accent hover:bg-brand-accent/90 text-slate-950 font-black uppercase rounded-lg transition-colors flex items-center justify-center gap-1.5"
            >
              <span>Save Map Settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
