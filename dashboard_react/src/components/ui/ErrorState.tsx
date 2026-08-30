import React from "react";
import { AlertOctagon, RefreshCw } from "lucide-react";
import { Button } from "./Button";

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = "Telemetry Stream Error",
  message,
  onRetry,
  className = ""
}) => {
  return (
    <div className={`p-8 rounded-2xl border border-brand-danger/30 bg-brand-dangerBg/40 backdrop-blur-xl text-center flex flex-col items-center justify-center space-y-3.5 shadow-sm ${className}`}>
      <div className="p-3.5 bg-brand-dangerBg border border-brand-danger/40 rounded-2xl text-brand-danger shadow-inner">
        <AlertOctagon className="w-8 h-8 text-brand-danger animate-pulse" />
      </div>
      <div className="space-y-1 max-w-md font-mono">
        <h3 className="text-xs font-black text-brand-danger uppercase tracking-widest">
          {title}
        </h3>
        <p className="text-xs text-brand-text/90 font-medium leading-relaxed">
          {message}
        </p>
      </div>
      {onRetry && (
        <div className="pt-2">
          <Button
            variant="danger"
            size="sm"
            icon={RefreshCw}
            onClick={onRetry}
          >
            Retry Connection
          </Button>
        </div>
      )}
    </div>
  );
};

