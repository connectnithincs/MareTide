import React from "react";

export type StatusVariant = 
  | "safe" 
  | "warning" 
  | "danger" 
  | "cyan" 
  | "purple"
  | "neutral" 
  | "standby";

export interface StatusBadgeProps {
  status: string;
  variant?: StatusVariant;
  label?: string;
  showDot?: boolean;
  pulseDot?: boolean;
  size?: "sm" | "md";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  variant,
  label,
  showDot = true,
  pulseDot = false,
  size = "md",
  className = ""
}) => {
  const normalized = status.toUpperCase();
  let resolvedVariant: StatusVariant = variant || "neutral";

  if (!variant) {
    if (normalized.includes("SAFE") || normalized.includes("VALID") || normalized.includes("LOADED") || normalized.includes("ONLINE") || normalized.includes("SUCCESS") || normalized.includes("COMPLETED") || normalized.includes("CONFIRMED") || normalized.includes("EQUILIBRIUM")) {
      resolvedVariant = "safe";
    } else if (normalized.includes("WARN") || normalized.includes("REVIEW") || normalized.includes("HEELING") || normalized.includes("STALE") || normalized.includes("ADVISORY")) {
      resolvedVariant = "warning";
    } else if (normalized.includes("DANGER") || normalized.includes("CRITICAL") || normalized.includes("ALARM") || normalized.includes("FAILED") || normalized.includes("DISCONNECT") || normalized.includes("REJECT") || normalized.includes("BLOCKED")) {
      resolvedVariant = "danger";
    } else if (normalized.includes("TELEMETRY") || normalized.includes("DRAINING") || normalized.includes("PUMP") || normalized.includes("CALC") || normalized.includes("ACTIVE") || normalized.includes("PROGRESS")) {
      resolvedVariant = "cyan";
    }
  }

  const variantMap = {
    safe: "bg-brand-safeBg text-brand-safe border-brand-safe/30",
    warning: "bg-brand-warningBg text-brand-warning border-brand-warning/30",
    danger: "bg-brand-dangerBg text-brand-danger border-brand-danger/30",
    cyan: "bg-brand-cyanBg text-brand-cyan border-brand-cyan/30",
    purple: "bg-brand-purpleBg text-brand-purple border-brand-purple/30",
    neutral: "bg-brand-surface text-brand-muted border-brand-borderSubtle",
    standby: "bg-brand-card text-brand-muted/70 border-brand-borderSubtle"
  };

  const dotColorMap = {
    safe: "bg-brand-safe shadow-sm shadow-brand-safe/50",
    warning: "bg-brand-warning shadow-sm shadow-brand-warning/50",
    danger: "bg-brand-danger shadow-sm shadow-brand-danger/50",
    cyan: "bg-brand-cyan shadow-sm shadow-brand-cyan/50",
    purple: "bg-brand-purple shadow-sm shadow-brand-purple/50",
    neutral: "bg-brand-muted",
    standby: "bg-brand-muted/50"
  };

  const sizeClasses = size === "sm" 
    ? "text-[8.5px] px-2 py-0.5" 
    : "text-[9.5px] px-2.5 py-0.5";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-mono font-bold uppercase tracking-wider border backdrop-blur-md ${variantMap[resolvedVariant]} ${sizeClasses} ${className}`}>
      {showDot && (
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColorMap[resolvedVariant]} ${pulseDot ? 'animate-pulse' : ''}`} />
      )}
      <span className="truncate">{label || status}</span>
    </span>
  );
};
