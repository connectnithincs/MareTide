import React, { useEffect, useState } from "react";
import { voyageAPI } from "../utils/api";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import { Compass, Ship, RefreshCw } from "lucide-react";

// Fix Leaflet marker icon configuration inside React SPA
import iconMarker from "leaflet/dist/images/marker-icon.png";
import iconRetina from "leaflet/dist/images/marker-icon-2x.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";

const DefaultIcon = L.icon({
  iconUrl: iconMarker,
  iconRetinaUrl: iconRetina,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

interface VoyageProfile {
  ship_name: string;
  imo: string;
  total_bays: number;
  tank_capacity: number;
  ship_configuration: string;
  cargo_data: any;
  ballast_configuration: any;
}

export const VoyageIntelligence: React.FC = () => {
  const [profile, setProfile] = useState<VoyageProfile | null>(null);
  const [track, setTrack] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Monitor DOM theme class changes dynamically for Leaflet styling
  const [isDarkTheme, setIsDarkTheme] = useState(() => document.documentElement.classList.contains("dark"));

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDarkTheme(document.documentElement.classList.contains("dark"));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  const fetchVoyageData = async () => {
    setLoading(true);
    try {
      const prof = await voyageAPI.getProfile();
      setProfile(prof);
      
      if (prof?.imo) {
        const trackData = await voyageAPI.getTrack(prof.imo);
        if (Array.isArray(trackData)) {
          setTrack(trackData);
        } else if (trackData?.track) {
          setTrack(trackData.track);
        }
      }
    } catch (err) {
      console.error("Error loading Voyage data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVoyageData();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center surface-base p-8">
        <RefreshCw className="w-12 h-12 text-brand-cyan animate-spin mb-4" />
        <p className="text-sm text-brand-muted font-bold animate-pulse font-mono">Loading voyage coordinates and AIS track...</p>
      </div>
    );
  }

  // Fallback coordinates if live AIS tracks are empty
  const defaultPosition: [number, number] = [36.75, -5.25]; // Algeciras Strait
  const polylineCoords: [number, number][] = track.length > 0 
    ? track.map(pt => [parseFloat(pt.lat || pt[0]), parseFloat(pt.lon || pt[1])]) 
    : [
        [36.80, -5.30],
        [36.75, -5.25],
        [36.70, -5.20],
        [36.65, -5.15]
      ];

  const currentPosition = polylineCoords[0] || defaultPosition;

  // Map API parameters
  const provider = localStorage.getItem("map_provider") || "osm";
  const apiKey = localStorage.getItem("map_api_key") || "";

  let tileUrl = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  let attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  let providerLabel = "OpenStreetMap API";

  if (apiKey) {
    if (provider === "mapbox") {
      const styleId = isDarkTheme ? "dark-v10" : "light-v10";
      tileUrl = `https://api.mapbox.com/styles/v1/mapbox/${styleId}/tiles/{z}/{x}/{y}?access_token=${apiKey}`;
      attribution = '&copy; <a href="https://www.mapbox.com/">Mapbox</a>';
      providerLabel = "Mapbox Satellite/Vector API";
    } else if (provider === "stadia") {
      const style = isDarkTheme ? "alidade_smooth_dark" : "alidade_smooth";
      tileUrl = `https://tiles.stadiamaps.com/tiles/${style}/{z}/{x}/{y}{r}.png?api_key=${apiKey}`;
      attribution = '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>';
      providerLabel = "Stadia Maps API";
    } else if (provider === "jawg") {
      const style = isDarkTheme ? "jawg-dark" : "jawg-light";
      tileUrl = `https://{s}.tile.jawg.io/${style}/{z}/{x}/{y}{r}.png?access-token=${apiKey}`;
      attribution = '&copy; <a href="https://www.jawg.io/">JawgMaps</a>';
      providerLabel = "JawgMaps Vector API";
    } else if (provider === "thunderforest") {
      const style = isDarkTheme ? "transport-dark" : "atlas";
      tileUrl = `https://{s}.tile.thunderforest.com/${style}/{z}/{x}/{y}.png?apikey=${apiKey}`;
      attribution = '&copy; <a href="https://www.thunderforest.com/">Thunderforest</a>';
      providerLabel = "Thunderforest API";
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 bg-brand-abyss">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-brand-borderSubtle pb-4">
        <div>
          <h2 className="text-sm font-black text-brand-text tracking-wide uppercase font-mono">
            Voyage Intelligence
          </h2>
          <p className="text-xs text-brand-muted font-medium mt-1">
            Vessel dimensions, cargo metrics, and live AIS tracking.
          </p>
        </div>
        <button 
          onClick={fetchVoyageData}
          className="p-2 surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text rounded-xl border border-brand-borderSubtle transition-all shadow-sm active:scale-95"
          title="Refresh Voyage Data"
        >
          <RefreshCw className="w-4 h-4 text-brand-cyan" />
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Vessel Specifications Panel */}
        <div className="surface-elevated border border-brand-borderSubtle rounded-2xl p-5 shadow-sm flex flex-col gap-4">
          <div className="flex items-center gap-2 pb-2 border-b border-brand-borderSubtle">
            <Ship className="text-brand-cyan w-5 h-5" />
            <h3 className="font-black text-xs text-brand-text uppercase tracking-wide font-mono">
              Vessel Profile Specifications
            </h3>
          </div>

          {profile ? (
            <div className="space-y-4 text-xs font-semibold font-mono">
              <div className="space-y-2 surface-base p-4 border border-brand-borderSubtle rounded-xl leading-relaxed shadow-sm">
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] tracking-wider">Vessel Name</span>
                  <span className="text-brand-text uppercase font-bold">{profile.ship_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] tracking-wider">IMO Number</span>
                  <span className="text-brand-text">{profile.imo}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] tracking-wider">Hull Design</span>
                  <span className="text-brand-text">{profile.ship_configuration}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] tracking-wider">Capacity Limit</span>
                  <span className="text-brand-text">{profile.tank_capacity.toFixed(0)} tonnes</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] tracking-wider">Configuration Bays</span>
                  <span className="text-brand-text">{profile.total_bays} Bays</span>
                </div>
              </div>

              {/* Cargo specs */}
              <div className="space-y-2 surface-base p-4 border border-brand-borderSubtle rounded-xl leading-relaxed shadow-sm">
                <span className="text-[10px] text-brand-muted uppercase font-bold tracking-wider block mb-1">
                  Cargo Loading Manifest
                </span>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] tracking-wider">Cargo Type</span>
                  <span className="text-brand-text">{profile.cargo_data.product}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted uppercase text-[10px] tracking-wider">Net Weight</span>
                  <span className="text-brand-text font-bold">{profile.cargo_data.quantity_mt?.toFixed(1)} t</span>
                </div>
              </div>
            </div>
          ) : (
            <span className="text-xs text-brand-muted italic font-mono">Profile details unavailable.</span>
          )}
        </div>

        {/* Live AIS Map container (Right 2 cols) */}
        <div className="lg:col-span-2 surface-elevated border border-brand-borderSubtle rounded-2xl p-4 shadow-sm flex flex-col gap-3 min-h-[400px]">
          <div className="flex items-center justify-between pb-2 border-b border-brand-borderSubtle">
            <div className="flex items-center gap-2">
              <Compass className="text-brand-cyan w-4 h-4" />
              <span className="text-xs font-black text-brand-text uppercase tracking-wide font-mono">
                Live AIS Tracking Map
              </span>
            </div>
            <span className="text-[10px] text-brand-cyan font-black uppercase tracking-wider font-mono">
              {providerLabel}
            </span>
          </div>

          {/* Leaflet Map rendering */}
          <div className="flex-1 rounded-xl overflow-hidden border border-brand-borderSubtle relative z-10">
            <MapContainer 
              center={currentPosition} 
              zoom={9} 
              style={{ height: "100%", width: "100%" }}
            >
              <TileLayer
                key={`${provider}-${isDarkTheme ? "dark" : "light"}`}
                attribution={attribution}
                url={tileUrl}
              />
              {track.length > 0 && <Polyline positions={polylineCoords} color="#00E5FF" weight={3} />}
              <Marker position={currentPosition}>
                <Popup>
                  <div className="text-xs font-semibold uppercase leading-tight text-slate-950 font-mono">
                    <strong>{profile?.ship_name || "ALGAMAR"}</strong><br/>
                    Status: Underway using engine<br/>
                    IMO: {profile?.imo || "8735106"}
                  </div>
                </Popup>
              </Marker>
            </MapContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

