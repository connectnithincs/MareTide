import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

export type ThemeMode = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

interface ThemeContextType {
  theme: ResolvedTheme;
  themeMode: ThemeMode;
  toggleTheme: () => void;
  setThemeMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "dark",
  themeMode: "system",
  toggleTheme: () => {},
  setThemeMode: () => {}
});

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Read stored preference ('dark', 'light', or 'system')
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem("maretide_theme_mode") as ThemeMode;
    if (saved && (saved === "dark" || saved === "light" || saved === "system")) {
      return saved;
    }
    // Fallback: check old key or default to system
    const oldSaved = localStorage.getItem("maretide_theme") as ResolvedTheme;
    if (oldSaved && (oldSaved === "dark" || oldSaved === "light")) {
      return oldSaved;
    }
    return "dark"; // Default to dark for maritime SCADA
  });

  const getSystemTheme = (): ResolvedTheme => {
    if (typeof window === "undefined" || !window.matchMedia) return "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => {
    if (themeMode === "system") {
      return getSystemTheme();
    }
    return themeMode;
  });

  // Apply class and style attributes to root <html>
  const applyThemeToDOM = useCallback((newTheme: ResolvedTheme) => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(newTheme);
    root.style.colorScheme = newTheme;
  }, []);

  // Update resolved theme whenever themeMode changes
  useEffect(() => {
    let activeTheme: ResolvedTheme = "dark";
    if (themeMode === "system") {
      activeTheme = getSystemTheme();
    } else {
      activeTheme = themeMode;
    }

    setResolvedTheme(activeTheme);
    applyThemeToDOM(activeTheme);
    localStorage.setItem("maretide_theme_mode", themeMode);
    localStorage.setItem("maretide_theme", activeTheme);
  }, [themeMode, applyThemeToDOM]);

  // Listen to OS system theme changes if themeMode is 'system'
  useEffect(() => {
    if (themeMode !== "system" || !window.matchMedia) return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e: MediaQueryListEvent) => {
      const newTheme: ResolvedTheme = e.matches ? "dark" : "light";
      setResolvedTheme(newTheme);
      applyThemeToDOM(newTheme);
      localStorage.setItem("maretide_theme", newTheme);
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [themeMode, applyThemeToDOM]);

  const toggleTheme = useCallback(() => {
    setThemeModeState(prev => {
      const next: ThemeMode = prev === "dark" ? "light" : "dark";
      return next;
    });
  }, []);

  const setThemeMode = useCallback((mode: ThemeMode) => {
    setThemeModeState(mode);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme: resolvedTheme, themeMode, toggleTheme, setThemeMode }}>
      {children}
    </ThemeContext.Provider>
  );
};
