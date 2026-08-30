import React from "react";
import { 
  LayoutDashboard, 
  Radio, 
  Droplets, 
  Grid, 
  BrainCircuit, 
  FileSpreadsheet, 
  History, 
  Eye, 
  Compass, 
  Settings as SettingsIcon, 
  LogOut, 
  Anchor,
  Sparkles,
  Sun,
  Moon
} from "lucide-react";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  user: string | null;
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, user, theme, setTheme }) => {
  const menuItems = [
    { id: "overview", name: "Dashboard Overview", icon: LayoutDashboard },
    { id: "demo-mode", name: "Hackathon Demo Mode", icon: Sparkles, badge: "DEMO" },
    { id: "container-ai", name: "Container Slip AI", icon: FileSpreadsheet },
    { id: "monitor", name: "Live Monitor", icon: Radio },
    { id: "ballast", name: "Ballast Control", icon: Droplets },
    { id: "deck", name: "Deck View", icon: Grid },
    { id: "advisor", name: "AI Advisor", icon: BrainCircuit },
    { id: "reports", name: "Reports", icon: FileSpreadsheet },
    { id: "history", name: "History & Logs", icon: History },
    { id: "vision", name: "AI Vision Monitoring", icon: Eye },
    { id: "voyage", name: "Voyage Intelligence", icon: Compass },
    { id: "settings", name: "Settings", icon: SettingsIcon }
  ];


  const handleLogout = () => {
    window.location.href = "http://localhost:5000/logout";
  };

  return (
    <aside className="w-64 bg-sidebar-gradient flex flex-col h-screen select-none border-r border-[#7DA0CA]/20 shadow-[0_20px_40px_-14px_rgba(2,16,36,0.45)]">
      {/* Header / Brand */}
      <div className="p-6 border-b border-[#7DA0CA]/20 flex items-center gap-3">
        <Anchor className="text-[#5483B3] w-8 h-8 animate-pulse" />
        <div>
          <h1 className="font-extrabold text-lg leading-none tracking-wide text-[#C1E8FF]">
            MARETIDE<span className="text-[#5483B3]">.</span>
          </h1>
          <span className="text-[10px] text-[#7DA0CA] font-bold tracking-widest uppercase">Stability AI</span>
        </div>
      </div>

      {/* Menu List */}
      <nav className="flex-1 px-4 py-6 overflow-y-auto space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-150 relative ${
                isActive 
                  ? "bg-[#5483B3]/28 text-[#C1E8FF]" 
                  : "text-[#7DA0CA] hover:text-[#C1E8FF] hover:bg-[#5483B3]/18"
              }`}
            >
              {isActive && (
                <span className="absolute left-[-16px] top-1/2 -translate-y-1/2 w-1 h-5.5 bg-[#C1E8FF] rounded-r-md" />
              )}
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{item.name}</span>
            </button>
          );
        })}
      </nav>

      {/* Theme Toggler */}
      <div className="px-5 py-3 border-t border-[#7DA0CA]/20 flex items-center justify-between">
        <span className="text-[10px] text-[#7DA0CA] uppercase font-bold tracking-wider">Dashboard Theme</span>
        <button
          onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          className="p-1 px-2.5 rounded-lg border border-[#7DA0CA]/20 bg-slate-900/40 hover:bg-slate-900/60 transition-all text-[#C1E8FF] flex items-center gap-1.5 font-bold"
        >
          {theme === "light" ? (
            <>
              <Sun className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
              <span className="text-[10px] uppercase tracking-wide font-black text-amber-500">Light</span>
            </>
          ) : (
            <>
              <Moon className="w-3.5 h-3.5 text-indigo-400 fill-indigo-400" />
              <span className="text-[10px] uppercase tracking-wide font-black text-indigo-400">Dark</span>
            </>
          )}
        </button>
      </div>

      {/* User Status & Logout */}
      <div className="p-4 border-t border-[#7DA0CA]/20 bg-slate-950/20 flex flex-col gap-3">
        {user && (
          <div className="flex items-center gap-3 bg-[rgba(193,232,255,0.06)] border border-[rgba(125,160,202,0.25)] rounded-2xl p-2.5">
            <div className="w-8 h-8 rounded-full bg-[#5483B3] text-[#C1E8FF] flex items-center justify-center font-bold text-xs border border-[#C1E8FF]/30">
              {user.slice(0, 2).toUpperCase()}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-[10px] text-[#7DA0CA] uppercase font-bold tracking-wider">Logged In As</span>
              <span className="text-xs text-[#C1E8FF] font-bold truncate">{user}</span>
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-brand-dangerBg text-[#E7594B] hover:bg-brand-danger/20 rounded-xl text-sm font-bold border border-brand-danger/30 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Exit Dashboard</span>
        </button>
      </div>
    </aside>
  );
};
