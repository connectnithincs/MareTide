import React from "react";
import { type LucideIcon, Radio } from "lucide-react";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = Radio,
  title,
  description,
  action,
  className = ""
}) => {
  return (
    <div className={`border border-dashed border-brand-borderSubtle surface-base/40 backdrop-blur-md rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-3 shadow-inner ${className}`}>
      <div className="p-4 surface-base rounded-2xl text-brand-muted border border-brand-borderSubtle shadow-inner">
        <Icon className="w-8 h-8 text-brand-cyan/80" />
      </div>
      <div className="space-y-1 max-w-md">
        <h3 className="text-xs font-mono font-black text-brand-text uppercase tracking-widest">
          {title}
        </h3>
        <p className="text-xs text-brand-muted leading-relaxed font-medium">
          {description}
        </p>
      </div>
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
};

