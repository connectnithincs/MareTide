import React, { useEffect, useState } from "react";
import { reportsAPI } from "../utils/api";
import { FileSpreadsheet, Trash2, Download, Search, RefreshCw, CheckCircle2, AlertTriangle } from "lucide-react";
import { SectionHeader } from "./ui/SectionHeader";
import { StatusBadge } from "./ui/StatusBadge";
import { SafetyBadge } from "./ui/SafetyBadge";

export const Reports: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"cargo" | "ballast" | "ops">("cargo");
  const [cargoLogs, setCargoLogs] = useState<any[]>([]);
  const [ballastLogs, setBallastLogs] = useState<any[]>([]);
  const [opsLogs, setOpsLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirmClear, setConfirmClear] = useState(false);
  
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
    try {
      await reportsAPI.clearAll();
      setConfirmClear(false);
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
    <div className="surface-elevated border border-brand-borderSubtle p-5 rounded-2xl space-y-4 font-mono text-xs shadow-sm">
      {/* Sub-Header & Actions */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between pb-3 border-b border-brand-borderSubtle gap-3">
        {/* Category switcher */}
        <div className="flex items-center gap-1.5 surface-base p-1 rounded-xl border border-brand-borderSubtle">
          <button
            onClick={() => setActiveTab("cargo")}
            className={`px-3 py-1.5 rounded-lg font-bold text-xs uppercase transition-all ${
              activeTab === "cargo"
                ? "bg-brand-cyan text-slate-950 font-black shadow-sm"
                : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
            }`}
          >
            Cargo Manifest ({cargoLogs.length})
          </button>
          <button
            onClick={() => setActiveTab("ballast")}
            className={`px-3 py-1.5 rounded-lg font-bold text-xs uppercase transition-all ${
              activeTab === "ballast"
                ? "bg-brand-cyan text-slate-950 font-black shadow-sm"
                : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
            }`}
          >
            Ballast Log ({ballastLogs.length})
          </button>
          <button
            onClick={() => setActiveTab("ops")}
            className={`px-3 py-1.5 rounded-lg font-bold text-xs uppercase transition-all ${
              activeTab === "ops"
                ? "bg-brand-cyan text-slate-950 font-black shadow-sm"
                : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
            }`}
          >
            Operations Ledger ({opsLogs.length})
          </button>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={fetchData}
            className="p-2 surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text border border-brand-borderSubtle rounded-xl transition-all shadow-sm active:scale-95"
            title="Refresh logs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={handleExportCSV}
            className="px-3 py-2 surface-base hover:bg-brand-hover text-brand-cyan border border-brand-cyan/30 rounded-xl text-xs font-bold uppercase transition-all flex items-center gap-1.5 shadow-sm active:scale-95"
            title="Export CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          {!confirmClear ? (
            <button
              onClick={() => setConfirmClear(true)}
              className="p-2 surface-base hover:bg-brand-dangerBg text-brand-muted hover:text-brand-danger border border-brand-borderSubtle rounded-xl transition-all"
              title="Clear all records"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          ) : (
            <div className="flex items-center gap-1.5 animate-in fade-in duration-150">
              <button
                onClick={handleClearLogs}
                className="px-2.5 py-1.5 bg-brand-danger hover:bg-brand-danger/90 text-white rounded-xl text-[10px] font-black uppercase transition-all shadow-sm"
              >
                Confirm Clear
              </button>
              <button
                onClick={() => setConfirmClear(false)}
                className="px-2 py-1.5 surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text rounded-xl text-[10px]"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Filter controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-1">
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-brand-muted" />
          <input
            type="text"
            placeholder="Search by container ID or event..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full surface-base border border-brand-border rounded-xl pl-9 pr-3 py-2 text-xs text-brand-text placeholder-brand-muted/60 focus-ring"
          />
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto text-xs">
          <span className="text-[10px] text-brand-muted uppercase font-bold">Source Filter:</span>
          <select
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
            className="surface-base border border-brand-border rounded-xl px-2.5 py-1.5 text-xs text-brand-text focus-ring"
          >
            <option value="all" className="bg-brand-elevated text-brand-text">All Sources</option>
            <option value="rapidocr" className="bg-brand-elevated text-brand-text">RapidOCR</option>
            <option value="solver" className="bg-brand-elevated text-brand-text">Stowage Solver</option>
            <option value="anti_heeling" className="bg-brand-elevated text-brand-text">Anti-Heeling Pump</option>
            <option value="operator" className="bg-brand-elevated text-brand-text">Operator Sign-Off</option>
          </select>
        </div>
      </div>

      {/* Table Data View */}
      <div className="border border-brand-borderSubtle rounded-2xl overflow-hidden surface-base/30">
        {loading ? (
          <div className="py-16 text-center text-xs text-brand-muted flex flex-col items-center gap-2">
            <RefreshCw className="w-6 h-6 text-brand-cyan animate-spin" />
            <span>Loading compliance records...</span>
          </div>
        ) : activeTab === "cargo" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="surface-base border-b border-brand-borderSubtle text-[9.5px] uppercase text-brand-muted font-bold tracking-wider">
                <tr>
                  <th className="py-2.5 px-3.5">Timestamp</th>
                  <th className="py-2.5 px-3.5">Event</th>
                  <th className="py-2.5 px-3.5">Container ID</th>
                  <th className="py-2.5 px-3.5">Mass (t)</th>
                  <th className="py-2.5 px-3.5">Assigned Slot</th>
                  <th className="py-2.5 px-3.5">Provenance Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-borderSubtle/60">
                {filteredCargoLogs.map((row, i) => (
                  <tr key={i} className="hover:bg-brand-hover transition-colors">
                    <td className="py-2 px-3.5 text-[10.5px] text-brand-muted">{row.time}</td>
                    <td className="py-2 px-3.5">
                      <span className="px-2 py-0.5 rounded text-[9.5px] font-bold bg-brand-safeBg text-brand-safe border border-brand-safe/30">
                        {row.event}
                      </span>
                    </td>
                    <td className="py-2 px-3.5 font-bold text-brand-text">{row.container}</td>
                    <td className="py-2 px-3.5 text-brand-cyan font-bold">{row.weight.toFixed(1)}t</td>
                    <td className="py-2 px-3.5 font-bold text-brand-text">Bay {row.bay} • {row.side?.toUpperCase()} • T{row.tier}</td>
                    <td className="py-2 px-3.5">
                      <SafetyBadge type={row.source || "DOCUMENT_AI"} size="sm" />
                    </td>
                  </tr>
                ))}
                {filteredCargoLogs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-xs text-brand-muted italic font-medium">
                      No cargo manifest entries matching search filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : activeTab === "ballast" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="surface-base border-b border-brand-borderSubtle text-[9.5px] uppercase text-brand-muted font-bold tracking-wider">
                <tr>
                  <th className="py-2.5 px-3.5">Timestamp</th>
                  <th className="py-2.5 px-3.5">Operation</th>
                  <th className="py-2.5 px-3.5">Source Tank</th>
                  <th className="py-2.5 px-3.5">Destination</th>
                  <th className="py-2.5 px-3.5">Discharge (t)</th>
                  <th className="py-2.5 px-3.5">Restored Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-borderSubtle/60">
                {filteredBallastLogs.map((row, i) => (
                  <tr key={i} className="hover:bg-brand-hover transition-colors">
                    <td className="py-2 px-3.5 text-[10.5px] text-brand-muted">{row.timestamp}</td>
                    <td className="py-2 px-3.5 font-bold text-brand-text">{row.op_type}</td>
                    <td className="py-2 px-3.5 text-brand-cyan font-bold">{row.source}</td>
                    <td className="py-2 px-3.5 text-brand-text">{row.dest}</td>
                    <td className="py-2 px-3.5 font-bold text-brand-warning">{row.qty}t</td>
                    <td className="py-2 px-3.5 font-bold text-brand-safe">{row.score_after ? `${row.score_after.toFixed(1)}%` : "100.0%"}</td>
                  </tr>
                ))}
                {filteredBallastLogs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-xs text-brand-muted italic font-medium">
                      No ballast operations logged.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="surface-base border-b border-brand-borderSubtle text-[9.5px] uppercase text-brand-muted font-bold tracking-wider">
                <tr>
                  <th className="py-2.5 px-3.5">Timestamp</th>
                  <th className="py-2.5 px-3.5">Event Action</th>
                  <th className="py-2.5 px-3.5">Container</th>
                  <th className="py-2.5 px-3.5">Assigned Bay</th>
                  <th className="py-2.5 px-3.5">Provenance Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-borderSubtle/60">
                {filteredOpsLogs.map((row, i) => (
                  <tr key={i} className="hover:bg-brand-hover transition-colors">
                    <td className="py-2 px-3.5 text-[10.5px] text-brand-muted">{row.time}</td>
                    <td className="py-2 px-3.5 font-bold text-brand-safe">{row.event}</td>
                    <td className="py-2 px-3.5 font-bold text-brand-text">{row.container}</td>
                    <td className="py-2 px-3.5 text-brand-text">Bay {row.bay} ({row.side})</td>
                    <td className="py-2 px-3.5">
                      <SafetyBadge type={row.source || "OPERATOR"} size="sm" />
                    </td>
                  </tr>
                ))}
                {filteredOpsLogs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-10 text-center text-brand-muted italic font-medium">
                      No operational events recorded.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>

  );
};
