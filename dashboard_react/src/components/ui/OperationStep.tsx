import React from "react";
import { Check, AlertTriangle, XOctagon, Loader2 } from "lucide-react";

export type StepState = "pending" | "active" | "completed" | "warning" | "blocked";

export interface StepItem {
  num: number;
  label: string;
  desc: string;
  state?: StepState;
}

export interface OperationStepProps {
  steps?: StepItem[];
  currentStep: number;
  blocked?: boolean;
  warning?: boolean;
  className?: string;
  onStepClick?: (stepNum: number) => void;
}

export const CANONICAL_8_STEPS: StepItem[] = [
  { num: 1, label: "DOCUMENT", desc: "Gate Slip Ingestion" },
  { num: 2, label: "ANALYZE", desc: "OCR & VGM Modulo-11" },
  { num: 3, label: "OPTIMIZE", desc: "Physics Stowage Solver" },
  { num: 4, label: "AUTHORIZE", desc: "Officer Safety Gate" },
  { num: 5, label: "LOAD", desc: "Commit to 3D State" },
  { num: 6, label: "BALLAST", desc: "Anti-Heeling Discharge" },
  { num: 7, label: "VERIFY", desc: "4-Stage Comparison" },
  { num: 8, label: "COMPLETE", desc: "Signed to Ledger" }
];

export const OperationStep: React.FC<OperationStepProps> = ({
  steps = CANONICAL_8_STEPS,
  currentStep,
  blocked = false,
  warning = false,
  className = "",
  onStepClick
}) => {
  return (
    <div className={`grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 select-none ${className}`}>
      {steps.map((s) => {
        let stepState: StepState = "pending";
        if (s.state) {
          stepState = s.state;
        } else if (currentStep > s.num) {
          stepState = "completed";
        } else if (currentStep === s.num) {
          if (blocked) stepState = "blocked";
          else if (warning) stepState = "warning";
          else stepState = "active";
        }

        const stateStyles = {
          pending: "surface-base border-brand-borderSubtle text-brand-muted opacity-75",
          active: "bg-brand-cyanBg border-brand-cyan/70 text-brand-cyan shadow-sm shadow-brand-cyan/20 ring-1 ring-brand-cyan/40 scale-[1.02]",
          completed: "bg-brand-safeBg border-brand-safe/50 text-brand-safe",
          warning: "bg-brand-warningBg border-brand-warning/70 text-brand-warning ring-1 ring-brand-warning/30",
          blocked: "bg-brand-dangerBg border-brand-danger/70 text-brand-danger ring-1 ring-brand-danger/30"
        };

        const pillStyles = {
          pending: "surface-base text-brand-muted border border-brand-borderSubtle",
          active: "bg-brand-cyan text-slate-950 font-black shadow-sm",
          completed: "bg-brand-safe text-slate-950 font-black",
          warning: "bg-brand-warning text-slate-950 font-black",
          blocked: "bg-brand-danger text-white font-black"
        };

        return (
          <div
            key={s.num}
            onClick={() => onStepClick && onStepClick(s.num)}
            className={`p-2 rounded-xl border flex flex-col justify-between transition-all duration-200 backdrop-blur-md ${
              onStepClick ? "cursor-pointer" : ""
            } ${stateStyles[stepState]}`}
          >
            <div className="flex items-center justify-between">
              <span
                className={`text-[9px] font-mono font-black w-4.5 h-4.5 rounded-full flex items-center justify-center transition-transform ${pillStyles[stepState]}`}
              >
                {stepState === "completed" ? (
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                ) : stepState === "warning" ? (
                  <AlertTriangle className="w-2.5 h-2.5" />
                ) : stepState === "blocked" ? (
                  <XOctagon className="w-2.5 h-2.5" />
                ) : (
                  s.num
                )}
              </span>

              {stepState === "active" && (
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-cyan opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-cyan" />
                </span>
              )}
            </div>

            <div className="mt-2">
              <div className="text-[10px] font-mono font-black tracking-tight truncate uppercase">
                {s.num}. {s.label}
              </div>
              <div className="text-[8.5px] text-brand-muted font-medium truncate mt-0.5">
                {s.desc}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

