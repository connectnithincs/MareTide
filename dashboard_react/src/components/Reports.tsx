import React, { useEffect, useState } from "react";
import { reportsAPI } from "../utils/api";
import { FileSpreadsheet, Trash2, Download, Search, RefreshCw } from "lucide-react";

export const Reports: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"cargo" | "ballast" | "ops">("cargo");
  const [cargoLogs, setCargoLogs] = useState<any[]>([]);
  const [ballastLogs, setBallastLogs] = useState<any[]>([]);
  const [opsLogs, setOpsLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Filtering states
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSource, setFilterSource] = useState("all");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [cargo, ballast, ops] = await Promise.all([
        reportsAPI.getCargoManifest(),
        reportsAPI.getBallastLog(),
        reportsAPI.getOpsLog()
      ]);
      setCargoLogs(cargo);
      setBallastLogs(ballast);
      setOpsLogs(ops);
    } catch (err) {
      console.error("Failed to load reports logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const handleClearLogs = async () => {
    if (!window.confirm("Are you sure you want to clear all operation logs from the database?")) return;
    try {
      await reportsAPI.clearAll();
      fetchData();
    } catch (err) {
      console.error("Error clearing logs:", err);
    }
  };

  // Client-side CSV Exporter
  const handleExportCSV = () => {
    let headers: string[] = [];
    let rows: any[] = [];
    let filename = "";

    if (activeTab === "cargo") {
      headers = ["Timestamp", "Event", "Container ID", "Weight (t)", "Bay", "Side", "Tier", "Source"];
      rows = filteredCargoLogs.map(l => [l.time, l.event, l.container, l.weight, l.bay, l.side.toUpperCase(), l.tier, l.source]);
      filename = "cargo_manifest.csv";
    } else if (activeTab === "ballast") {
      headers = ["Timestamp", "Operation", "Pump Mode", "Source", "Dest", "Volume (t)", "Remaining Src", "Final Dest", "Score Before", "Score After", "Trigger"];
      rows = filteredBallastLogs.map(l => [l.timestamp, l.op_type, l.pump_mode, l.source, l.dest, l.qty, l.remaining_src, l.final_dest, l.score_before, l.score_after, l.trigger]);
      filename = "ballast_operation_log.csv";
    } else {
      headers = ["Timestamp", "Event", "Container ID", "Weight (t)", "Bay", "Side", "Tier", "Source"];
      rows = filteredOpsLogs.map(l => [l.time, l.event, l.container, l.weight, l.bay, l.side.toUpperCase(), l.tier, l.source]);
      filename = "operations_log.csv";
    }

    const csvContent = [
      headers.join(","),
      ...rows.map((e: any[]) => e.map((val: any) => `"${val}"`).join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Filter computations
  const filteredCargoLogs = cargoLogs.filter(l => {
    const matchesSearch = l.container.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSource = filterSource === "all" || l.source.toLowerCase() === filterSource.toLowerCase();
    return matchesSearch && matchesSource;
  });

  const filteredBallastLogs = ballastLogs.filter(l => {
    const matchesSearch = l.op_type.toLowerCase().includes(searchQuery.toLowerCase()) || l.source.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSource = filterSource === "all" || l.trigger.toLowerCase() === filterSource.toLowerCase();
    return matchesSearch && matchesSource;
  });

  const filteredOpsLogs = opsLogs.filter(l => {
    const matchesSearch = l.container.toLowerCase().includes(searchQuery.toLowerCase()) || l.event.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSource = filterSource === "all" || l.source.toLowerCase() === filterSource.toLowerCase();
    return matchesSearch && matchesSource;
  });

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-brand-dark">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-brand-border pb-4">
        <div>
          <h2 className="text-xl font-black text-brand-text tracking-wide uppercase">Stability Compliance Reports</h2>
          <p className="text-xs text-brand-muted font-semibold mt-1">Review, filter, and export historical vessel stowage logs.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchData}
            className="p-2 bg-brand-border/40 hover:bg-brand-border/80 text-brand-muted hover:text-brand-text rounded-lg border border-brand-border transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-3 py-2 bg-brand-accentBg hover:bg-brand-accent/20 text-brand-accent border border-brand-accent/30 rounded-lg text-xs font-bold transition-all"
          >
            <Download className="w-4 h-4" />
            <span>Export CSV</span>
          </button>
          <button
            onClick={handleClearLogs}
            className="flex items-center gap-2 px-3 py-2 bg-brand-dangerBg hover:bg-brand-danger/20 text-brand-danger border border-brand-danger/30 rounded-lg text-xs font-bold transition-all"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear Logs</span>
          </button>
        </div>
      </div>

      {/* Tabs Row */}
      <div className="flex gap-1 border-b border-brand-border">
        <button
          onClick={() => { setActiveTab("cargo"); setSearchQuery(""); }}
          className={`px-4 py-2 text-xs font-black uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "cargo" 
              ? "border-brand-accent text-brand-accent bg-brand-accentBg/10" 
              : "border-transparent text-brand-muted hover:text-brand-text"
          }`}
        >
          Cargo Manifest
        </button>
        <button
          onClick={() => { setActiveTab("ballast"); setSearchQuery(""); }}
          className={`px-4 py-2 text-xs font-black uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "ballast" 
              ? "border-brand-accent text-brand-accent bg-brand-accentBg/10" 
              : "border-transparent text-brand-muted hover:text-brand-text"
          }`}
        >
          Ballast Log
        </button>
        <button
          onClick={() => { setActiveTab("ops"); setSearchQuery(""); }}
          className={`px-4 py-2 text-xs font-black uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "ops" 
              ? "border-brand-accent text-brand-accent bg-brand-accentBg/10" 
              : "border-transparent text-brand-muted hover:text-brand-text"
          }`}
        >
          Operational Log
        </button>
      </div>

      {/* Filtering Widgets */}
      <div className="flex flex-col sm:flex-row gap-4 bg-brand-card p-4 border border-brand-border rounded-xl glass-panel">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 text-brand-muted absolute left-3 top-3" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-brand-app border border-brand-border rounded-lg pl-9 pr-4 py-2 text-xs text-brand-text font-semibold focus:outline-none focus:border-brand-accent"
            placeholder={activeTab === "ballast" ? "Filter by operation type..." : "Search by container ID..."}
          />
        </div>

        <div className="w-full sm:w-48">
          <select
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
            className="w-full bg-brand-app border border-brand-border rounded-lg px-3 py-2 text-xs text-brand-text font-semibold focus:outline-none focus:border-brand-accent"
          >
            <option value="all">All Sources / Triggers</option>
            {activeTab === "ballast" ? (
              <>
                <option value="ai">AI Triggered</option>
                <option value="user">User Triggered</option>
              </>
            ) : (
              <>
                <option value="esp32">ESP32 Hardware</option>
                <option value="simulation">Simulation Mode</option>
              </>
            )}
          </select>
        </div>
      </div>

      {/* Report Data Table */}
      <div className="border border-brand-border bg-brand-card rounded-xl overflow-hidden shadow-lg glass-panel">
        {loading ? (
          <div className="py-20 text-center flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-8 h-8 text-brand-accent animate-spin" />
            <span className="text-xs text-brand-muted font-semibold">Retrieving compliance data...</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            {activeTab === "cargo" && (
              <table className="w-full text-left text-xs font-semibold">
                <thead className="bg-brand-app text-brand-muted uppercase text-[10px] tracking-wider border-b border-brand-border">
                  <tr>
                    <th className="p-4">Timestamp</th>
                    <th className="p-4">Event</th>
                    <th className="p-4">Container ID</th>
                    <th className="p-4">Weight</th>
                    <th className="p-4">Location (Bay/Side/Tier)</th>
                    <th className="p-4">Stowage Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/60 text-brand-text">
                  {filteredCargoLogs.map((log, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/20">
                      <td className="p-4">{log.time}</td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                          log.event === "LOAD" ? "bg-emerald-500/10 text-emerald-400" : "bg-brand-dangerBg text-brand-danger"
                        }`}>
                          {log.event}
                        </span>
                      </td>
                      <td className="p-4 font-bold">{log.container}</td>
                      <td className="p-4">{log.weight.toFixed(1)} t</td>
                      <td className="p-4 uppercase">Bay {log.bay} / {log.side} / T{log.tier}</td>
                      <td className="p-4 text-brand-muted">{log.source}</td>
                    </tr>
                  ))}
                  {filteredCargoLogs.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-brand-muted italic">No cargo operations logged.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}

            {activeTab === "ballast" && (
              <table className="w-full text-left text-xs font-semibold">
                <thead className="bg-brand-app text-brand-muted uppercase text-[10px] tracking-wider border-b border-brand-border">
                  <tr>
                    <th className="p-4">Timestamp</th>
                    <th className="p-4">Operation</th>
                    <th className="p-4">Pump Mode</th>
                    <th className="p-4">Path (Src ➔ Dest)</th>
                    <th className="p-4">Volume</th>
                    <th className="p-4">Final Source</th>
                    <th className="p-4">Stability Index Δ</th>
                    <th className="p-4">Trigger</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/60 text-brand-text">
                  {filteredBallastLogs.map((log, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/20">
                      <td className="p-4">{log.timestamp}</td>
                      <td className="p-4 uppercase">{log.op_type}</td>
                      <td className="p-4 text-brand-muted">{log.pump_mode}</td>
                      <td className="p-4 font-bold">{log.source} ➔ {log.dest}</td>
                      <td className="p-4 text-brand-danger">-{log.qty.toFixed(1)} t</td>
                      <td className="p-4">{Math.round(log.remaining_src)} t</td>
                      <td className="p-4">
                        <span className="text-brand-muted">{log.score_before.toFixed(1)}% ➔ </span>
                        <span className="text-brand-accent">{log.score_after.toFixed(1)}%</span>
                      </td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                          log.trigger === "AI" ? "bg-brand-accentBg text-brand-accent" : "bg-brand-border text-brand-text"
                        }`}>
                          {log.trigger}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {filteredBallastLogs.length === 0 && (
                    <tr>
                      <td colSpan={8} className="p-8 text-center text-brand-muted italic">No ballast pump actions logged.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}

            {activeTab === "ops" && (
              <table className="w-full text-left text-xs font-semibold">
                <thead className="bg-brand-app text-brand-muted uppercase text-[10px] tracking-wider border-b border-brand-border">
                  <tr>
                    <th className="p-4">Timestamp</th>
                    <th className="p-4">Event</th>
                    <th className="p-4">Container ID</th>
                    <th className="p-4">Weight</th>
                    <th className="p-4">Placement (B/S/T)</th>
                    <th className="p-4">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/60 text-brand-text">
                  {filteredOpsLogs.map((log, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/20">
                      <td className="p-4">{log.time}</td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                          log.event === "LOAD" ? "bg-emerald-500/10 text-emerald-400" : "bg-brand-dangerBg text-brand-danger"
                        }`}>
                          {log.event}
                        </span>
                      </td>
                      <td className="p-4 font-bold">{log.container}</td>
                      <td className="p-4">{log.weight.toFixed(1)} t</td>
                      <td className="p-4 uppercase">Bay {log.bay} / {log.side} / T{log.tier}</td>
                      <td className="p-4 text-brand-muted">{log.source}</td>
                    </tr>
                  ))}
                  {filteredOpsLogs.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-brand-muted italic">No operations logged.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
