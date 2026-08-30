import React from "react";
import { AlertOctagon, AlertTriangle, Info, CheckCircle2, X, ArrowRight } from "lucide-react";

export type AlertVariant = "info" | "warning" | "danger" | "safe";

export interface AlertBannerProps {
  title?: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  variant?: AlertVariant;
  onDismiss?: () => void;
  className?: string;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({
  title,
  message,
  actionLabel,
  onAction,
  variant = "warning",
  onDismiss,
  className = ""
}) => {
  const styles = {
    info: {
      border: "border-brand-info/40",
      bg: "bg-brand-infoBg",
      text: "text-brand-info",
      icon: Info
    },
    warning: {
      border: "border-brand-warning/40",
      bg: "bg-brand-warningBg",
      text: "text-brand-warning",
      icon: AlertTriangle
    },
    danger: {
      border: "border-brand-danger/40",
      bg: "bg-brand-dangerBg",
      text: "text-brand-danger",
      icon: AlertOctagon
    },
    safe: {
      border: "border-brand-safe/40",
      bg: "bg-brand-safeBg",
      text: "text-brand-safe",
      icon: CheckCircle2
    }
  };

  const style = styles[variant];
  const Icon = style.icon;

  return (
    <div className={`p-3.5 rounded-2xl border backdrop-blur-xl ${style.border} ${style.bg} flex items-start justify-between gap-3 text-xs shadow-sm ${className}`}>
      <div className="flex items-start gap-3 min-w-0">
        <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${style.text}`} />
        <div className="min-w-0">
          {title && (
            <div className={`font-mono font-black uppercase text-[10px] tracking-wider mb-0.5 ${style.text}`}>
              {title}
            </div>
          )}
          <p className="text-brand-text leading-relaxed font-medium">
            {message}
          </p>
          {actionLabel && onAction && (
            <button
              onClick={onAction}
              className={`mt-2 inline-flex items-center gap-1.5 font-mono text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded-lg border transition-all ${style.border} ${style.text} hover:bg-brand-hover active:scale-95`}
            >
              <span>{actionLabel}</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-brand-muted hover:text-brand-text p-1 rounded-lg hover:surface-base transition-colors flex-shrink-0"
          title="Dismiss notification"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};

