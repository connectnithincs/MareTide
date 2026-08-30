import React from "react";
import { type LucideIcon } from "lucide-react";

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  category?: string;
  icon?: LucideIcon;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  category,
  icon: Icon,
  badge,
  actions,
  className = ""
}) => {
  return (
    <div className={`flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 mb-4 border-b border-brand-borderSubtle ${className}`}>
      <div className="flex items-start gap-3.5 min-w-0">
        {Icon && (
          <div className="p-2.5 bg-brand-cyanBg border border-brand-cyan/30 rounded-xl text-brand-cyan shadow-sm shadow-brand-cyan/10 flex-shrink-0 mt-0.5">
            <Icon className="w-5 h-5" />
          </div>
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            {category && (
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-brand-muted">
                {category} /
              </span>
            )}
            <h1 className="text-sm font-black text-brand-text font-mono uppercase tracking-widest truncate">
              {title}
            </h1>
            {badge && (
              <div className="flex-shrink-0">
                {badge}
              </div>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-brand-muted font-medium mt-0.5 leading-relaxed">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      {actions && (
        <div className="flex items-center gap-2 flex-wrap flex-shrink-0">
          {actions}
        </div>
      )}
    </div>
  );
};

