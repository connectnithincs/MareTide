import React from "react";

export interface DataRowProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  status?: "default" | "safe" | "warning" | "danger" | "cyan" | "purple";
  secondaryValue?: string;
  className?: string;
}

export const DataRow: React.FC<DataRowProps> = ({
  label,
  value,
  unit,
  status = "default",
  secondaryValue,
  className = ""
}) => {
  const statusColors = {
    default: "text-brand-text",
    safe: "text-brand-safe font-bold",
    warning: "text-brand-warning font-bold",
    danger: "text-brand-danger font-bold",
    cyan: "text-brand-cyan font-bold",
    purple: "text-brand-purple font-bold"
  };

  return (
    <div className={`flex items-center justify-between py-2 border-b border-brand-borderSubtle last:border-b-0 text-xs font-medium ${className}`}>
      <span className="text-[10px] font-mono text-brand-muted uppercase font-bold tracking-wider">
        {label}
      </span>
      <div className="flex items-baseline gap-1 text-right font-mono">
        <span className={`${statusColors[status]} tracking-tight text-xs`}>
          {value}
        </span>
        {unit && (
          <span className="text-[10px] text-brand-muted font-normal">
            {unit}
          </span>
        )}
        {secondaryValue && (
          <span className="text-[9.5px] text-brand-muted/80 ml-1.5 font-normal">
            ({secondaryValue})
          </span>
        )}
      </div>
    </div>
  );
};

