import React, { useState, useEffect } from "react";
import { 
  Sparkles, 
  Clock, 
  SlidersHorizontal,
  Anchor,
  Radio,
  Boxes,
  FileSpreadsheet,
  Sun,
  Moon,
  Menu
} from "lucide-react";
import { useSocket } from "../../context/SocketContext";
import { useTheme } from "../../context/ThemeContext";
import { VesselStatusIndicator } from "../ui/VesselStatusIndicator";
import { Tooltip } from "../ui/Tooltip";

export interface TopBarProps {
  activeTab: string;
  activeTitle: string;
  activeDescription: string;
  user: string | null;
  onToggleSidebar?: () => void;
  onOpenDemoDrawer: () => void;
  onOpenSettingsDrawer: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  activeTab,
  activeTitle,
  activeDescription,
  user,
  onToggleSidebar,
  onOpenDemoDrawer,
  onOpenSettingsDrawer
}) => {
  const { connected, vesselState } = useSocket();
  const { theme, toggleTheme } = useTheme();
  const [utcTime, setUtcTime] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toUTCString().slice(17, 25) + " UTC");
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const isSimulated = vesselState?.is_simulated ?? true;
  const score = vesselState?.stability_score ?? 100;
  const risk = vesselState?.stability_risk ?? "SAFE";

  const getStationIcon = () => {
    if (activeTab === "twin") return Anchor;
    if (activeTab === "planner" || activeTab === "manifest") return Boxes;
    if (activeTab === "audit" || activeTab === "reports" || activeTab === "history") return FileSpreadsheet;
    return Radio;
  };

  const StationIcon = getStationIcon();

  return (
    <header className="h-16 bg-brand-dark/90 backdrop-blur-2xl border-b border-brand-border px-4 sm:px-6 flex items-center justify-between flex-shrink-0 z-20 select-none shadow-elevation-1">
      {/* Left: Hamburger (Mobile) & Station Title */}
      <div className="flex items-center gap-3 min-w-0 pr-2">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="p-2 rounded-xl bg-brand-surface hover:bg-brand-elevated text-brand-muted hover:text-brand-text border border-brand-borderSubtle md:hidden flex-shrink-0"
            title="Toggle Navigation"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}

        <div className="p-2 bg-brand-surface border border-brand-border rounded-xl text-brand-cyan shadow-sm hidden sm:flex flex-shrink-0">
          <StationIcon className="w-4 h-4" />
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xs font-mono font-black text-brand-text uppercase tracking-widest truncate">
              {activeTitle}
            </h1>
            <span className="text-[9px] font-mono text-brand-muted uppercase hidden lg:inline">
              • IMO: <strong className="text-brand-text">8735106</strong>
            </span>
          </div>
          <p className="text-[10px] text-brand-muted font-medium hidden 2xl:block truncate">
            {activeDescription}
          </p>
        </div>
      </div>

      {/* Right: Global Telemetry Status, UTC Clock, Theme, Demo, & Settings */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* UTC Live Clock */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 bg-brand-surface/80 rounded-full border border-brand-borderSubtle text-[10.5px] font-mono font-bold text-brand-muted shadow-sm">
          <Clock className="w-3 h-3 text-brand-cyan" />
          <span>{utcTime}</span>
        </div>

        {/* Global Connection & Stability Status Indicator */}
        <VesselStatusIndicator
          connected={connected}
          isSimulated={isSimulated}
          stabilityScore={score}
          stabilityRisk={risk}
          staleSeconds={vesselState?.stale_seconds}
          telemetryTimestamp={vesselState?.telemetry_timestamp}
        />

        {/* Theme Switcher */}
        <Tooltip content={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}>
          <button
            onClick={toggleTheme}
            className="p-2 bg-brand-surface hover:bg-brand-elevated text-brand-muted hover:text-brand-text border border-brand-borderSubtle rounded-xl transition-all shadow-sm active:scale-95"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? (
              <Sun className="w-3.5 h-3.5 text-amber-400" />
            ) : (
              <Moon className="w-3.5 h-3.5 text-indigo-500" />
            )}
          </button>
        </Tooltip>

        {/* Demo Scenarios Quick Action Button */}
        <button
          onClick={onOpenDemoDrawer}
          className="px-2.5 py-1.5 bg-brand-surface hover:bg-brand-elevated text-brand-text hover:text-brand-cyan border border-brand-border hover:border-brand-cyan/40 rounded-xl text-[10px] font-mono font-black uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-sm active:scale-95"
          title="Open demonstration scenarios & verification fixtures"
        >
          <Sparkles className="w-3 h-3 text-brand-cyan animate-pulse" />
          <span className="hidden sm:inline">DEMO</span>
        </button>

        {/* Settings Launcher */}
        <Tooltip content="System Settings">
          <button
            onClick={onOpenSettingsDrawer}
            className="p-2 bg-brand-surface hover:bg-brand-elevated text-brand-muted hover:text-brand-text border border-brand-border rounded-xl transition-all shadow-sm active:scale-95"
            aria-label="Settings"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </Tooltip>

        {/* User Pill */}
        {user && (
          <div className="hidden xl:flex items-center gap-2 pl-2 border-l border-brand-borderSubtle">
            <div className="w-7 h-7 rounded-xl bg-brand-elevated border border-brand-border text-brand-cyan flex items-center justify-center font-mono font-black text-[10px] shadow-sm">
              {user.slice(0, 2).toUpperCase()}
            </div>
            <div className="flex flex-col text-[10px] leading-tight">
              <span className="font-mono text-brand-text font-bold truncate max-w-[100px]">{user.split("@")[0]}</span>
              <span className="text-[8px] font-mono text-brand-muted uppercase font-bold">Officer</span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
