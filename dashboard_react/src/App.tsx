import React, { useEffect, useState } from "react";
import { authAPI } from "./utils/api";
import { SocketProvider } from "./context/SocketContext";
import { Sidebar } from "./components/Sidebar";
import { DashboardOverview } from "./components/DashboardOverview";
import { LiveMonitor } from "./components/LiveMonitor";
import { BallastControl } from "./components/BallastControl";
import { DeckView } from "./components/DeckView";
import { AIAdvisor } from "./components/AIAdvisor";
import { Reports } from "./components/Reports";
import { HistoryLogs } from "./components/HistoryLogs";
import { AIVision } from "./components/AIVision";
import { VoyageIntelligence } from "./components/VoyageIntelligence";
import { Settings } from "./components/Settings";
import { Activity } from "lucide-react";

export const App: React.FC = () => {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  useEffect(() => {
    const authenticate = async () => {
      // 1. Check for token in URL parameters (from Flask redirect)
      const urlParams = new URLSearchParams(window.location.search);
      const token = urlParams.get("token");

      try {
        if (token) {
          console.log("Token detected in URL. Initiating exchange handshake...");
          const res = await authAPI.exchangeToken(token);
          if (res.valid) {
            setAuthenticated(true);
            setUser(res.user);
            // Clear URL query parameters cleanly
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
          setUser(res.user);
          setLoading(false);
        } else {
          // Bypass redirect and log in as default local user
          console.log("Session not found. Activating local mock login...");
          setAuthenticated(true);
          setUser("admin@maretide.com");
          setLoading(false);
        }
      } catch (err) {
        // Fallback mock login on backend service connection errors
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
      <div className="flex flex-col items-center justify-center min-h-screen bg-brand-dark text-brand-text">
        <Activity className="w-12 h-12 text-brand-accent animate-spin mb-4" />
        <h2 className="font-bold text-sm uppercase tracking-widest animate-pulse">Establishing Secure Session Handshake...</h2>
      </div>
    );
  }

  // Active view switcher
  const renderTabContent = () => {
    switch (activeTab) {
      case "overview":
        return <DashboardOverview />;
      case "monitor":
        return <LiveMonitor />;
      case "ballast":
        return <BallastControl />;
      case "deck":
        return <DeckView />;
      case "advisor":
        return <AIAdvisor />;
      case "reports":
        return <Reports />;
      case "history":
        return <HistoryLogs />;
      case "vision":
        return <AIVision />;
      case "voyage":
        return <VoyageIntelligence />;
      case "settings":
        return <Settings />;
      default:
        return <DashboardOverview />;
    }
  };

  return (
    <SocketProvider>
      <div className="flex h-screen w-screen overflow-hidden bg-brand-dark text-brand-text">
        {/* Left Sidebar Navigation */}
        <Sidebar 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          user={user} 
          theme={theme}
          setTheme={setTheme}
        />

        {/* Right Tab panel */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {renderTabContent()}
        </main>
      </div>
    </SocketProvider>
  );
};

export default App;
