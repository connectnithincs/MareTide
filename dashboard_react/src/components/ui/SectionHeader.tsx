import React from "react";
import { type LucideIcon } from "lucide-react";

export interface SectionHeaderProps {
  title: string;
  icon?: LucideIcon;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  icon: Icon,
  badge,
  actions,
  className = ""
}) => {
  return (
    <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2.5 mb-3 border-b border-brand-borderSubtle ${className}`}>
      <div className="flex items-center gap-2 min-w-0 flex-wrap">
        {Icon && <Icon className="w-4 h-4 text-brand-cyan flex-shrink-0" />}
        <h2 className="text-xs font-mono font-black text-brand-text uppercase tracking-wider">
          {title}
        </h2>
        {badge}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-auto">
          {actions}
        </div>
      )}
    </div>
  );
};

