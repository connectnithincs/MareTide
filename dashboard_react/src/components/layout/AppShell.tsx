import React, { useState, useEffect } from "react";
import { Sidebar, PRIMARY_NAV_ITEMS } from "../Sidebar";
import { TopBar } from "./TopBar";
import { Drawer } from "../ui/Drawer";
import { HackathonDemoMode } from "../HackathonDemoMode";
import { Settings } from "../Settings";

export interface AppShellProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  user: string | null;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({
  activeTab,
  setActiveTab,
  user,
  children
}) => {
  const [isDemoOpen, setIsDemoOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== "undefined" && window.innerWidth < 1200) return true;
    const saved = localStorage.getItem("maretide_sidebar_collapsed");
    return saved === "true";
  });

  const handleToggleCollapse = () => {
    setIsSidebarCollapsed(prev => {
      const next = !prev;
      localStorage.setItem("maretide_sidebar_collapsed", String(next));
      return next;
    });
  };

  // Close mobile nav when tab changes
  useEffect(() => {
    setIsMobileNavOpen(false);
  }, [activeTab]);

  // Find active nav item for TopBar description
  const currentNav = 
    PRIMARY_NAV_ITEMS.find(n => n.id === activeTab) || 
    (activeTab === "command" || activeTab === "cargo" || activeTab === "overview" || activeTab === "vision" ? PRIMARY_NAV_ITEMS[0] : null) ||
    (activeTab === "manifest" ? PRIMARY_NAV_ITEMS[2] : null) ||
    (activeTab === "reports" || activeTab === "history" || activeTab === "timeline" ? PRIMARY_NAV_ITEMS[3] : null) ||
    PRIMARY_NAV_ITEMS[0];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-brand-abyss text-brand-text font-sans antialiased">
      {/* 1. Desktop & Tablet Sidebar */}
      <div className="hidden md:flex h-full flex-shrink-0">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          user={user}
          collapsed={isSidebarCollapsed}
          onToggleCollapse={handleToggleCollapse}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenDemo={() => setIsDemoOpen(true)}
        />
      </div>

      {/* 2. Mobile Navigation Drawer */}
      <Drawer
        isOpen={isMobileNavOpen}
        onClose={() => setIsMobileNavOpen(false)}
        title="Maritime Control Stations"
        subtitle="Select supervisory workstation"
        width="sm"
      >
        <div className="space-y-2 font-mono text-xs">
          {PRIMARY_NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setIsMobileNavOpen(false);
                }}
                className={`w-full p-3 rounded-xl border text-left flex items-center gap-3 transition-all ${
                  isActive
                    ? "bg-brand-cyan text-slate-950 border-brand-cyan font-black"
                    : "bg-brand-surface text-brand-text border-brand-borderSubtle"
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <div className="min-w-0">
                  <span className="block font-bold">{item.name}</span>
                  <span className={`text-[10px] block truncate ${isActive ? "text-slate-800" : "text-brand-muted"}`}>
                    {item.shortName}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </Drawer>

      {/* 3. Main Application Column */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Top Navigation Bar */}
        <TopBar
          activeTab={activeTab}
          activeTitle={currentNav.name}
          activeDescription={currentNav.description}
          user={user}
          onToggleSidebar={() => setIsMobileNavOpen(true)}
          onOpenDemoDrawer={() => setIsDemoOpen(true)}
          onOpenSettingsDrawer={() => setIsSettingsOpen(true)}
        />

        {/* Viewport Content with Smooth Page Transitions */}
        <main 
          key={activeTab} 
          className="flex-1 flex flex-col min-w-0 overflow-hidden bg-brand-abyss relative page-enter"
        >
          {children}
        </main>
      </div>

      {/* 4. Slide-Over Drawer: Demo Scenarios & Verification Engine */}
      <Drawer
        isOpen={isDemoOpen}
        onClose={() => setIsDemoOpen(false)}
        title="Demonstration Scenarios & Verification Fixtures"
        subtitle="Phase 6E Verification Engine, Golden Path Sequences & Scenario Injections"
        width="xl"
      >
        <HackathonDemoMode />
      </Drawer>

      {/* 5. Slide-Over Drawer: System Settings & Hardware Link */}
      <Drawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        title="Hardware Link & System Settings"
        subtitle="ESP32 COM Port Binding, AI Camera Feeds, Baud Rates, and Telemetry Source"
        width="lg"
      >
        <Settings />
      </Drawer>
    </div>
  );
};
