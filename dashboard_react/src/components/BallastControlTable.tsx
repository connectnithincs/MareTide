import React, { useState, useEffect } from "react";
import { RefreshCw, Play, AlertTriangle } from "lucide-react";
import { vesselAPI } from "../utils/api";
import { useSocket } from "../context/SocketContext";

interface BallastControlTableProps {
  tanks: any;
  onAdjustComplete: () => void;
}

export const BallastControlTable: React.FC<BallastControlTableProps> = ({ tanks, onAdjustComplete }) => {
  const { vesselState } = useSocket();
  const [fromSide, setFromSide] = useState("port");
  const [toSide, setToSide] = useState("starboard");
  const [fromBay, setFromBay] = useState("All");
  const [toBay, setToBay] = useState("All");
  const [amount, setAmount] = useState(50);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activePumping = !!vesselState?.is_pumping || loading;

  // Clear success message when pumping stops
  useEffect(() => {
    if (!vesselState?.is_pumping && !loading) {
      // Pumping completed
    } else {
      setMessage(null);
      setError(null);
    }
  }, [vesselState?.is_pumping, loading]);

  const handleExecutePumping = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      const res = await vesselAPI.pumpBallast(fromSide, toSide, amount, fromBay, toBay);
      if (res.success) {
        setMessage(res.message);
        onAdjustComplete();
      }
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "Pumping operation failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full flex flex-col gap-4 border border-brand-border bg-brand-card p-5 rounded-xl shadow-lg glass-panel text-xs font-semibold text-brand-text">
      <div className="flex items-center gap-2 pb-3 border-b border-brand-border">
        <RefreshCw className={`w-4 h-4 text-brand-accent ${activePumping ? 'animate-spin' : 'animate-pulse'}`} />
        <h3 className="text-xs text-brand-muted font-bold uppercase tracking-wider">Manual Ballast Pumping</h3>
      </div>

      <form onSubmit={handleExecutePumping} className="space-y-4">
        {/* Source Side & Bay */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Pump From Side</label>
            <select 
              value={fromSide} 
              disabled={activePumping}
              onChange={(e) => setFromSide(e.target.value)}
              className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold disabled:opacity-50"
            >
              <option value="port">Port</option>
              <option value="starboard">Starboard</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Source Bay</label>
            <select 
              value={fromBay} 
              disabled={activePumping}
              onChange={(e) => setFromBay(e.target.value)}
              className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold disabled:opacity-50"
            >
              <option value="All">All Bays</option>
              <option value="1">Bay 1</option>
              <option value="2">Bay 2</option>
              <option value="3">Bay 3</option>
              <option value="4">Bay 4</option>
            </select>
          </div>
        </div>

        {/* Dest Side & Bay */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Pump Destination</label>
            <select 
              value={toSide} 
              disabled={activePumping}
              onChange={(e) => {
                setToSide(e.target.value);
                if (e.target.value === "Drain (Sea)") {
                  setToBay("All");
                }
              }}
              className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold disabled:opacity-50"
            >
              <option value="starboard">Starboard</option>
              <option value="port">Port</option>
              <option value="Drain (Sea)">Drain (Sea)</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Destination Bay</label>
            <select 
              value={toBay} 
              disabled={activePumping || toSide === "Drain (Sea)"}
              onChange={(e) => setToBay(e.target.value)}
              className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold disabled:opacity-50"
            >
              <option value="All">All Bays</option>
              <option value="1">Bay 1</option>
              <option value="2">Bay 2</option>
              <option value="3">Bay 3</option>
              <option value="4">Bay 4</option>
            </select>
          </div>
        </div>

        {/* Water Volume */}
        <div>
          <label className="block text-[10px] text-brand-muted uppercase font-bold tracking-wider mb-1">Water volume (t)</label>
          <input 
            type="number" 
            min={1} 
            max={300}
            value={amount}
            disabled={activePumping}
            onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
            className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-brand-text focus:outline-none focus:border-brand-accent font-semibold disabled:opacity-50"
          />
        </div>

        {/* Action Button */}
        <button
          type="submit"
          disabled={activePumping}
          className="w-full py-2.5 bg-brand-accent hover:bg-brand-accent/90 disabled:opacity-50 disabled:bg-brand-accent/30 text-slate-950 font-black text-xs uppercase rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {activePumping ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-slate-950" />}
          <span>{activePumping ? "Pumping Water..." : "Execute Pumping"}</span>
        </button>
      </form>

      {/* Active Pumping Alert */}
      {activePumping && (
        <div className="bg-brand-dangerBg border border-brand-danger/20 text-brand-danger p-4 rounded-lg flex items-start gap-3 animate-pulse">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 animate-bounce mt-0.5" />
          <div>
            <h4 className="font-bold text-[10px] uppercase tracking-wider">VALVE OPEN & PUMPING ACTIVE</h4>
            <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
              Discharging/transferring ballast water at <strong className="text-brand-text">8.5 t/s</strong>. SCADA Digital Twin valves are open. Please wait...
            </p>
          </div>
        </div>
      )}

      {/* Success / Error Messages */}
      {message && !activePumping && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 text-brand-accent p-3 rounded-lg text-[11px] leading-relaxed font-bold">
          ✅ {message}
        </div>
      )}
      {error && !activePumping && (
        <div className="bg-brand-dangerBg border border-brand-danger/20 text-brand-danger p-3 rounded-lg text-[11px] leading-relaxed font-bold">
          ❌ {error}
        </div>
      )}
    </div>
  );
};
