import React, { useState } from "react";
import { 
  Radio, 
  Anchor, 
  Boxes, 
  FileSpreadsheet, 
  SlidersHorizontal, 
  LogOut, 
  Sparkles, 
  ChevronLeft, 
  ChevronRight,
  ShieldCheck,
  Cpu
} from "lucide-react";
import { useSocket } from "../context/SocketContext";
import { useContainerOperation } from "../context/ContainerOperationContext";
import { Tooltip } from "./ui/Tooltip";

export interface NavItem {
  id: string;
  name: string;
  shortName: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  category: "OPERATIONS" | "ENGINEERING" | "AUDIT";
}

export const PRIMARY_NAV_ITEMS: NavItem[] = [
  { 
    id: "monitor", 
    name: "LINE MONITOR", 
    shortName: "Line Monitor",
    icon: Radio,
    description: "Primary operational workspace, 7-stage container pipeline, and 10Hz telemetry",
    category: "OPERATIONS"
  },
  { 
    id: "twin", 
    name: "VESSEL DIGITAL TWIN", 
    shortName: "Digital Twin",
    icon: Anchor,
    description: "Three.js 3D spatial hull, 4-bay cross-sections, and ballast manifold controls",
    category: "ENGINEERING"
  },
  { 
    id: "planner", 
    name: "MANIFEST PLANNER", 
    shortName: "Manifest",
    icon: Boxes,
    description: "Phase 4D batch manifest ingestion and multi-objective Pareto solver",
    category: "ENGINEERING"
  },
  { 
    id: "audit", 
    name: "OPERATIONS & AUDIT", 
    shortName: "Audit Logs",
    icon: FileSpreadsheet,
    description: "Cryptographic SHA-256 event ledger and SOLAS VGM compliance manifests",
    category: "AUDIT"
  }
];

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  user: string | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onOpenSettings: () => void;
  onOpenDemo: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  activeTab, 
  setActiveTab, 
  user,
  collapsed,
  onToggleCollapse,
  onOpenSettings,
  onOpenDemo
}) => {
  const { connected, vesselState } = useSocket();
  const { operationStatus, extractedData, loadedResult, ballastCompensation } = useContainerOperation();
  const isSimulated = vesselState?.is_simulated ?? true;

  const handleLogout = () => {
    window.location.href = "http://localhost:5000/logout";
  };

  const isWorkflowActive = Boolean(
    extractedData || 
    loadedResult || 
    ballastCompensation || 
    (operationStatus && operationStatus !== "IDLE" && operationStatus !== "COMPLETED")
  );

  return (
    <aside 
      className={`${
        collapsed ? "w-18" : "w-64"
      } bg-brand-dark/95 backdrop-blur-2xl border-r border-brand-border flex flex-col h-full select-none flex-shrink-0 z-30 shadow-elevation-2 transition-all duration-250 ease-out`}
    >
      {/* Brand Header */}
      <div className="h-16 px-4 border-b border-brand-border flex items-center justify-between bg-brand-surface/40">
        <div className={`flex items-center gap-3 min-w-0 ${collapsed ? "justify-center w-full" : ""}`}>
          <div className="p-2 rounded-xl bg-brand-cyanBg border border-brand-cyan/40 text-brand-cyan shadow-sm shadow-brand-cyan/20 flex-shrink-0">
            <Anchor className="w-4.5 h-4.5" />
          </div>
          {!collapsed && (
            <div className="flex flex-col leading-none min-w-0">
              <span className="font-mono font-black text-sm tracking-wider text-brand-text truncate">
                MARETIDE<span className="text-brand-cyan">.</span>
              </span>
              <span className="text-[8.5px] font-mono font-bold text-brand-muted uppercase tracking-widest mt-0.5 truncate">
                Maritime Control OS
              </span>
            </div>
          )}
        </div>

        {!collapsed && (
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg border border-brand-borderSubtle hover:bg-brand-surface text-brand-muted hover:text-brand-text transition-colors"
            title="Collapse Sidebar"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Primary Navigation Rail */}
      <nav className="flex-1 px-2.5 py-4 space-y-1.5 overflow-y-auto">
        {!collapsed && (
          <div className="px-2.5 pb-2 text-[9px] font-mono font-bold uppercase tracking-widest text-brand-muted flex items-center justify-between">
            <span>Stations</span>
            {isWorkflowActive && (
              <span className="flex items-center gap-1 text-brand-cyan font-mono text-[8px]">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan animate-pulse" />
                ACTIVE
              </span>
            )}
          </div>
        )}

        {PRIMARY_NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = 
            activeTab === item.id || 
            (item.id === "monitor" && (activeTab === "command" || activeTab === "cargo" || activeTab === "overview" || activeTab === "vision")) ||
            (item.id === "planner" && activeTab === "manifest") ||
            (item.id === "audit" && (activeTab === "reports" || activeTab === "history" || activeTab === "timeline"));

          const buttonContent = (
            <button
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center ${
                collapsed ? "justify-center px-2 py-3" : "justify-between px-3.5 py-2.5"
              } rounded-xl text-xs font-mono font-bold transition-all relative group text-left ${
                isActive 
                  ? "bg-brand-surface/90 text-brand-cyan border border-brand-cyan/40 shadow-sm shadow-brand-cyan/10" 
                  : "text-brand-muted hover:text-brand-text hover:bg-brand-surface/40 border border-transparent"
              }`}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-brand-cyan rounded-r-full shadow-sm shadow-brand-cyan/80" />
              )}
              <div className="flex items-center gap-3 min-w-0">
                <Icon className={`w-4 h-4 flex-shrink-0 transition-colors ${isActive ? 'text-brand-cyan' : 'text-brand-muted group-hover:text-brand-text'}`} />
                {!collapsed && <span className="truncate tracking-wide">{item.name}</span>}
              </div>

              {!collapsed && item.id === "monitor" && isWorkflowActive && (
                <span className="w-2 h-2 rounded-full bg-brand-cyan animate-ping flex-shrink-0" />
              )}
            </button>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.id} content={item.shortName} position="right">
                {buttonContent}
              </Tooltip>
            );
          }

          return <div key={item.id}>{buttonContent}</div>;
        })}

        {/* Demo Drawer Launcher */}
        <div className="pt-2">
          {collapsed ? (
            <Tooltip content="Demo Scenarios" position="right">
              <button
                onClick={onOpenDemo}
                className="w-full flex items-center justify-center p-3 rounded-xl border border-brand-borderSubtle bg-brand-card hover:bg-brand-elevated text-brand-muted hover:text-brand-text transition-all"
              >
                <Sparkles className="w-4 h-4 text-brand-cyan" />
              </button>
            </Tooltip>
          ) : (
            <button
              onClick={onOpenDemo}
              className="w-full flex items-center justify-between px-3.5 py-2 rounded-xl text-xs font-mono font-bold transition-all border border-brand-borderSubtle bg-brand-card hover:bg-brand-elevated text-brand-muted hover:text-brand-text group"
            >
              <div className="flex items-center gap-2.5">
                <Sparkles className="w-3.5 h-3.5 text-brand-cyan group-hover:animate-spin" />
                <span className="text-[10.5px] uppercase tracking-wider">Demo Scenarios</span>
              </div>
              <span className="text-[8px] font-mono font-bold px-1.5 py-0.5 rounded bg-brand-surface text-brand-cyan border border-brand-cyan/20">
                PHASE 6E
              </span>
            </button>
          )}
        </div>
      </nav>

      {/* Bottom Area */}
      <div className="p-3 border-t border-brand-border bg-brand-dark/50 space-y-2.5 flex-shrink-0 text-xs font-mono">
        {!collapsed && (
          <div className="p-2.5 rounded-xl bg-brand-surface/70 border border-brand-borderSubtle space-y-1">
            <div className="flex items-center justify-between text-[9.5px]">
              <span className="text-brand-muted uppercase font-bold">Telemetry Link</span>
              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-brand-safe animate-pulse' : 'bg-brand-danger'}`} />
            </div>
            <div className="text-[10.5px] font-bold text-brand-text truncate">
              {connected 
                ? (isSimulated ? "Simulated Stream (10Hz)" : "ESP32 Hardware (10Hz)") 
                : "Disconnected"}
            </div>
          </div>
        )}

        <div className={`grid ${collapsed ? "grid-cols-1" : "grid-cols-2"} gap-1.5`}>
          {collapsed ? (
            <>
              <Tooltip content="Settings" position="right">
                <button
                  onClick={onOpenSettings}
                  className="w-full p-2.5 rounded-lg bg-brand-surface hover:bg-brand-elevated text-brand-muted hover:text-brand-text border border-brand-borderSubtle flex items-center justify-center"
                >
                  <SlidersHorizontal className="w-4 h-4" />
                </button>
              </Tooltip>
              <Tooltip content="Expand Sidebar" position="right">
                <button
                  onClick={onToggleCollapse}
                  className="w-full p-2.5 rounded-lg bg-brand-surface hover:bg-brand-elevated text-brand-cyan border border-brand-borderSubtle flex items-center justify-center"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </Tooltip>
            </>
          ) : (
            <>
              <button
                onClick={onOpenSettings}
                className="flex items-center justify-center gap-1.5 px-2.5 py-2 rounded-lg bg-brand-surface hover:bg-brand-elevated text-brand-muted hover:text-brand-text border border-brand-borderSubtle text-[10px] font-bold uppercase transition-all shadow-sm active:scale-95"
              >
                <SlidersHorizontal className="w-3 h-3" />
                <span>Settings</span>
              </button>

              <button
                onClick={handleLogout}
                className="flex items-center justify-center gap-1.5 px-2.5 py-2 rounded-lg bg-brand-dangerBg hover:bg-brand-dangerBg/90 text-brand-danger border border-brand-danger/30 text-[10px] font-bold uppercase transition-all shadow-sm active:scale-95"
              >
                <LogOut className="w-3 h-3" />
                <span>Exit</span>
              </button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
};
