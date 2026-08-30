import React, { useEffect, useState } from "react";
import { authAPI } from "./utils/api";
import { SocketProvider } from "./context/SocketContext";
import { ContainerOperationProvider } from "./context/ContainerOperationContext";
import { ThemeProvider } from "./context/ThemeContext";
import { AppShell } from "./components/layout/AppShell";
import { LiveMonitorView } from "./components/pages/LiveMonitorView";
import { VesselDigitalTwinView } from "./components/pages/VesselDigitalTwinView";
import { MultiContainerPlannerView } from "./components/MultiContainerPlannerView";
import { OperationsAuditView } from "./components/pages/OperationsAuditView";
import { Activity } from "lucide-react";

export const App: React.FC = () => {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("monitor");

  useEffect(() => {
    const authenticate = async () => {
      // 1. Check for token in URL parameters (from Flask redirect)
      const urlParams = new URLSearchParams(window.location.search);
      const token = urlParams.get("token");

      try {
        if (token) {
          console.log("Token detected in URL. Initiating exchange handshake...");
          const res = await authAPI.exchangeToken(token);
          if (res.valid || res.success) {
            setAuthenticated(true);
            setUser(res.user || "admin@maretide.com");
            window.history.replaceState({}, document.title, window.location.pathname);
            setLoading(false);
            return;
          }
        }
      } catch (err) {
        console.error("Token exchange failed:", err);
      }

      // 2. Fallback: Check for existing Flask session cookie
      try {
        const res = await authAPI.checkSession();
        if (res.authenticated) {
          setAuthenticated(true);
          setUser(res.user || "admin@maretide.com");
          setLoading(false);
        } else {
          // Bypass redirect and log in as default local user
          console.log("Session not found. Activating local mock login...");
          setAuthenticated(true);
          setUser("admin@maretide.com");
          setLoading(false);
        }
      } catch (err) {
        console.log("Auth connection failed. Activating offline local mock login...");
        setAuthenticated(true);
        setUser("admin@maretide.com");
        setLoading(false);
      }
    };

    authenticate();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-brand-abyss text-brand-text">
        <Activity className="w-10 h-10 text-brand-cyan animate-spin mb-3" />
        <h2 className="font-mono font-bold text-xs uppercase tracking-widest text-brand-muted animate-pulse">
          Establishing Secure Session Handshake...
        </h2>
      </div>
    );
  }

  // Active view switcher (4 Core Supervisory Stations with legacy fallback mappings)
  const renderTabContent = () => {
    switch (activeTab) {
      case "monitor":
      case "command":
      case "cargo":
      case "overview":
      case "advisor":
      case "vision":
        return <LiveMonitorView onNavigate={(tab) => setActiveTab(tab)} />;

      case "twin":
      case "ballast":
      case "deck":
        return <VesselDigitalTwinView />;

      case "planner":
      case "manifest":
        return (
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 bg-brand-abyss">
            <MultiContainerPlannerView />
          </div>
        );

      case "audit":
      case "reports":
      case "history":
      case "timeline":
        return <OperationsAuditView />;

      default:
        return <LiveMonitorView onNavigate={(tab) => setActiveTab(tab)} />;
    }
  };

  return (
    <ThemeProvider>
      <SocketProvider>
        <ContainerOperationProvider>
          <AppShell
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            user={user}
          >
            {renderTabContent()}
          </AppShell>
        </ContainerOperationProvider>
      </SocketProvider>
    </ThemeProvider>
  );
};

export default App;
