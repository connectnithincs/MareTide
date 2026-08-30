import React from "react";
import { ShieldCheck, Lock, CheckSquare, Square, RefreshCw, Check } from "lucide-react";

export interface ConfirmationPanelProps {
  title?: string;
  subtitle?: string;
  targetAssignmentText: string;
  massText: string;
  operatorId: string;
  onOperatorIdChange: (id: string) => void;
  isConfirmed: boolean;
  onConfirmedToggle: () => void;
  disclaimerText: string;
  onAuthorize: () => void;
  isSubmitting?: boolean;
  submitButtonText?: string;
  submittingText?: string;
  className?: string;
}

export const ConfirmationPanel: React.FC<ConfirmationPanelProps> = ({
  title = "Explicit Stowage Authorization Gate",
  subtitle = "State 3: Operator Supervisory Review (Human-in-the-Loop Required)",
  targetAssignmentText,
  massText,
  operatorId,
  onOperatorIdChange,
  isConfirmed,
  onConfirmedToggle,
  disclaimerText,
  onAuthorize,
  isSubmitting = false,
  submitButtonText = "Authorize & Commit Container Load",
  submittingText = "Committing to Vessel State...",
  className = ""
}) => {
  return (
    <div className={`surface-elevated border-2 border-brand-cyan/40 p-5 rounded-2xl shadow-xl space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-brand-borderSubtle pb-3 gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-brand-cyanBg border border-brand-cyan/30 rounded-xl text-brand-cyan">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-brand-cyan font-black uppercase tracking-wider block">
              {subtitle}
            </span>
            <h3 className="text-sm font-black text-brand-text uppercase tracking-wide">
              {title}
            </h3>
          </div>
        </div>

        <span className="text-[10px] font-mono font-bold uppercase px-2.5 py-1 rounded-full surface-base text-brand-cyan border border-brand-cyan/30 flex items-center gap-1.5 shadow-sm">
          <Lock className="w-3 h-3" /> Human Authorization Enforced
        </span>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        <div className="p-3 surface-base rounded-xl border border-brand-borderSubtle space-y-1">
          <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">
            Target Assignment
          </span>
          <div className="text-sm font-mono font-black text-brand-text">
            {targetAssignmentText}
          </div>
          <span className="text-[10px] text-brand-safe font-mono font-semibold block">
            {massText}
          </span>
        </div>

        <div className="p-3 surface-base rounded-xl border border-brand-borderSubtle space-y-1.5">
          <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">
            Supervisory Officer ID
          </span>
          <input 
            type="text" 
            value={operatorId}
            onChange={(e) => onOperatorIdChange(e.target.value)}
            className="w-full surface-base border border-brand-border rounded-lg px-2.5 py-1.5 text-xs text-brand-text font-mono font-bold focus-ring"
            placeholder="Officer ID"
          />
          <span className="text-[9px] text-brand-muted block">
            Logged with cryptographic SHA-256 hash.
          </span>
        </div>

        <div className="p-3 surface-base rounded-xl border border-brand-borderSubtle flex flex-col justify-between">
          <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block mb-1">
            Safety Gate Verification
          </span>
          <button
            type="button"
            onClick={onConfirmedToggle}
            className={`p-2 rounded-xl border text-left flex items-start gap-2 transition-all ${
              isConfirmed 
                ? "bg-brand-safeBg border-brand-safe/50 text-brand-safe" 
                : "surface-base border-brand-borderSubtle text-brand-muted hover:border-brand-accent/50"
            }`}
          >
            {isConfirmed ? (
              <CheckSquare className="w-4 h-4 text-brand-safe flex-shrink-0 mt-0.5" />
            ) : (
              <Square className="w-4 h-4 text-brand-muted flex-shrink-0 mt-0.5" />
            )}
            <span className="text-[10px] font-bold leading-tight">
              {disclaimerText}
            </span>
          </button>
        </div>
      </div>

      {/* Action footer */}
      <div className="flex items-center justify-between pt-3 border-t border-brand-borderSubtle flex-wrap gap-3">
        <span className="text-[10px] text-brand-muted font-mono">
          Zero auto-commit: changes apply only upon explicit sign-off.
        </span>

        <button
          onClick={onAuthorize}
          disabled={!isConfirmed || isSubmitting}
          className={`px-5 py-2.5 rounded-xl font-black text-xs uppercase tracking-wider flex items-center gap-2 transition-all shadow-md ${
            isConfirmed && !isSubmitting
              ? "bg-brand-cyan hover:bg-brand-cyan/90 text-slate-950 shadow-brand-cyan/20 cursor-pointer active:scale-95"
              : "surface-base text-brand-muted border border-brand-borderSubtle cursor-not-allowed opacity-50"
          }`}
        >
          {isSubmitting ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>{submittingText}</span>
            </>
          ) : (
            <>
              <Check className="w-3.5 h-3.5 stroke-[3]" />
              <span>{submitButtonText}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

