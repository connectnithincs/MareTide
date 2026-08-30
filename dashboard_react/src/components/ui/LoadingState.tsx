import React from "react";
import { RefreshCw } from "lucide-react";

export interface LoadingStateProps {
  message?: string;
  subMessage?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = "Synchronizing vessel telemetry stream...",
  subMessage,
  size = "md",
  className = ""
}) => {
  const iconSizes = {
    sm: "w-5 h-5",
    md: "w-8 h-8",
    lg: "w-11 h-11"
  };

  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center space-y-3.5 surface-base/60 backdrop-blur-xl rounded-2xl border border-brand-borderSubtle shadow-xl ${className}`}>
      <div className="relative p-3.5 surface-base border border-brand-border rounded-2xl text-brand-cyan shadow-sm shadow-brand-cyan/20">
        <RefreshCw className={`${iconSizes[size]} animate-spin text-brand-cyan`} />
        <span className="absolute -top-1 -right-1 flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-cyan opacity-75" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-brand-cyan" />
        </span>
      </div>
      <div className="space-y-1">
        <p className="text-xs font-mono font-black text-brand-text uppercase tracking-widest animate-pulse">
          {message}
        </p>
        {subMessage && (
          <p className="text-[10px] text-brand-muted font-mono">
            {subMessage}
          </p>
        )}
      </div>
    </div>
  );
};

