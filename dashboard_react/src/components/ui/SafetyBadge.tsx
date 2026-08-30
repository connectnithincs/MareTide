import React from "react";
import { ShieldCheck, Compass, Radio, Zap, UserCheck, Scale, Cpu } from "lucide-react";

export type ProvenanceType = 
  | "DOCUMENT_AI" 
  | "CALCULATED" 
  | "HARDWARE_TELEMETRY" 
  | "SIMULATED_TELEMETRY" 
  | "OPERATOR"
  | "SOLAS_VGM"
  | "PREDICTED";

export interface SafetyBadgeProps {
  type: ProvenanceType | string;
  label?: string;
  size?: "sm" | "md";
  className?: string;
}

export const SafetyBadge: React.FC<SafetyBadgeProps> = ({
  type,
  label,
  size = "md",
  className = ""
}) => {
  const norm = type.toUpperCase().replace(/\s+/g, "_").replace(/\[|\]/g, "");

  let displayLabel = label;
  let Icon = ShieldCheck;
  let style = "bg-brand-safeBg text-brand-safe border-brand-safe/30 shadow-sm shadow-brand-safe/10";

  if (norm.includes("DOCUMENT") || norm.includes("DOC_AI")) {
    displayLabel = label || "DOCUMENT AI";
    Icon = ShieldCheck;
    style = "bg-brand-safeBg text-brand-safe border-brand-safe/40 shadow-sm shadow-brand-safe/10";
  } else if (norm.includes("CALCULAT") || norm.includes("CALC")) {
    displayLabel = label || "CALCULATED";
    Icon = Compass;
    style = "bg-brand-infoBg text-brand-info border-brand-info/40 shadow-sm shadow-brand-info/10";
  } else if (norm.includes("HARDWARE") || norm.includes("IOT") || norm.includes("SENSOR")) {
    displayLabel = label || "HARDWARE SENSOR";
    Icon = Radio;
    style = "bg-brand-cyanBg text-brand-cyan border-brand-cyan/40 shadow-sm shadow-brand-cyan/10";
  } else if (norm.includes("SIMULAT") || norm.includes("SIM")) {
    displayLabel = label || "SIMULATED TELEMETRY";
    Icon = Cpu;
    style = "bg-brand-warningBg text-brand-warning border-brand-warning/40 shadow-sm shadow-brand-warning/10";
  } else if (norm.includes("OPERATOR") || norm.includes("HUMAN")) {
    displayLabel = label || "OPERATOR AUTHORIZED";
    Icon = UserCheck;
    style = "bg-brand-purpleBg text-brand-purple border-brand-purple/40 shadow-sm shadow-brand-purple/10";
  } else if (norm.includes("SOLAS") || norm.includes("VGM")) {
    displayLabel = label || "SOLAS VGM VERIFIED";
    Icon = Scale;
    style = "bg-brand-safeBg text-brand-safe border-brand-safe/40 shadow-sm shadow-brand-safe/10";
  } else if (norm.includes("PREDICT")) {
    displayLabel = label || "PREDICTED";
    Icon = Zap;
    style = "bg-brand-purpleBg text-brand-purple border-brand-purple/40 shadow-sm shadow-brand-purple/10";
  }

  const sizeClasses = size === "sm"
    ? "text-[8px] px-2 py-0.5 gap-1"
    : "text-[9px] px-2.5 py-0.5 gap-1.5";

  return (
    <span
      className={`inline-flex items-center rounded-full font-mono font-bold uppercase tracking-wider border backdrop-blur-md ${style} ${sizeClasses} ${className}`}
    >
      <Icon className="w-2.5 h-2.5 flex-shrink-0" />
      <span>{displayLabel}</span>
    </span>
  );
};

