import React from "react";
import { type LucideIcon } from "lucide-react";

export interface TabItem<T extends string = string> {
  id: T;
  label: string;
  icon?: LucideIcon;
  badge?: string | number;
}

export interface TabsProps<T extends string = string> {
  tabs: TabItem<T>[];
  activeTab: T;
  onChange: (tabId: T) => void;
  size?: "sm" | "md";
  className?: string;
}

export const Tabs = <T extends string = string>({
  tabs,
  activeTab,
  onChange,
  size = "md",
  className = ""
}: TabsProps<T>) => {
  const sizeStyles = {
    sm: "p-0.5 text-[10px] gap-1",
    md: "p-1 text-xs gap-1.5"
  };

  const buttonPadding = {
    sm: "px-2.5 py-1",
    md: "px-3.5 py-1.5"
  };

  return (
    <div className={`inline-flex items-center surface-base rounded-xl border border-brand-borderSubtle select-none ${sizeStyles[size]} ${className}`}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;

        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`inline-flex items-center gap-2 rounded-lg font-mono font-bold uppercase tracking-wider transition-all duration-150 relative ${
              buttonPadding[size]
            } ${
              isActive
                ? "bg-brand-cyan text-slate-950 shadow-sm shadow-brand-cyan/20 font-black"
                : "text-brand-textSecondary hover:text-brand-text hover:bg-brand-hover"
            }`}
          >
            {Icon && <Icon className="w-3.5 h-3.5 flex-shrink-0" />}
            <span className="truncate">{tab.label}</span>
            {tab.badge !== undefined && (
              <span className={`text-[8.5px] px-1.5 py-0.2 rounded-full font-mono font-black ${
                isActive ? "bg-slate-950 text-brand-cyan" : "surface-base text-brand-muted"
              }`}>
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

