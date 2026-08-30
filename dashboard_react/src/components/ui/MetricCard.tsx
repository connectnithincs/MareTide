import React from "react";
import { type LucideIcon } from "lucide-react";

export interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  subValue?: string;
  icon?: LucideIcon;
  variant?: "default" | "safe" | "warning" | "danger" | "cyan" | "purple";
  provenance?: "DOC AI" | "CALC" | "TEL" | "SIM" | "OPERATOR" | "SOLAS VGM" | string;
  trend?: "up" | "down" | "neutral";
  className?: string;
  onClick?: () => void;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  subValue,
  icon: Icon,
  variant = "default",
  provenance,
  className = "",
  onClick
}) => {
  const variantStyles = {
    default: {
      border: "border-brand-borderSubtle hover:border-brand-border",
      bg: "bg-brand-card hover:bg-brand-surface",
      iconBg: "bg-brand-surface text-brand-muted",
      valCol: "text-brand-text",
      badge: "bg-brand-surface text-brand-muted border-brand-borderSubtle"
    },
    safe: {
      border: "border-brand-safe/30 hover:border-brand-safe/50",
      bg: "bg-brand-card hover:bg-brand-surface",
      iconBg: "bg-brand-safeBg text-brand-safe",
      valCol: "text-brand-safe",
      badge: "bg-brand-safeBg text-brand-safe border-brand-safe/30"
    },
    warning: {
      border: "border-brand-warning/30 hover:border-brand-warning/50",
      bg: "bg-brand-card hover:bg-brand-surface",
      iconBg: "bg-brand-warningBg text-brand-warning",
      valCol: "text-brand-warning",
      badge: "bg-brand-warningBg text-brand-warning border-brand-warning/30"
    },
    danger: {
      border: "border-brand-danger/30 hover:border-brand-danger/50",
      bg: "bg-brand-card hover:bg-brand-surface",
      iconBg: "bg-brand-dangerBg text-brand-danger",
      valCol: "text-brand-danger",
      badge: "bg-brand-dangerBg text-brand-danger border-brand-danger/30"
    },
    cyan: {
      border: "border-brand-cyan/30 hover:border-brand-cyan/50",
      bg: "bg-brand-card hover:bg-brand-surface",
      iconBg: "bg-brand-cyanBg text-brand-cyan",
      valCol: "text-brand-cyan",
      badge: "bg-brand-cyanBg text-brand-cyan border-brand-cyan/30"
    },
    purple: {
      border: "border-brand-purple/30 hover:border-brand-purple/50",
      bg: "bg-brand-card hover:bg-brand-surface",
      iconBg: "bg-brand-purpleBg text-brand-purple",
      valCol: "text-brand-purple",
      badge: "bg-brand-purpleBg text-brand-purple border-brand-purple/30"
    }
  };

  const style = variantStyles[variant];

  return (
    <div
      onClick={onClick}
      className={`glass-card ${style.border} ${style.bg} p-3.5 flex flex-col justify-between transition-all duration-200 relative overflow-hidden shadow-sm ${
        onClick ? "cursor-pointer active:scale-[0.99]" : ""
      } ${className}`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {Icon && (
            <div className={`p-1.5 rounded-lg ${style.iconBg} flex-shrink-0 shadow-inner`}>
              <Icon className="w-3.5 h-3.5" />
            </div>
          )}
          <span
            className="text-[10px] font-mono font-bold text-brand-muted uppercase tracking-wider truncate"
            title={label}
          >
            {label}
          </span>
        </div>
        {provenance && (
          <span className={`text-[8px] font-mono font-black uppercase px-1.5 py-0.5 rounded-full border tracking-wide ${style.badge}`}>
            {provenance}
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-1.5 mt-1">
        <span className={`text-xl font-mono font-black tracking-tight ${style.valCol}`}>
          {value}
        </span>
        {unit && (
          <span className="text-xs font-mono font-bold text-brand-muted">
            {unit}
          </span>
        )}
      </div>

      {subValue && (
        <div className="text-[10.5px] font-medium text-brand-muted/90 truncate mt-1">
          {subValue}
        </div>
      )}
    </div>
  );
};
