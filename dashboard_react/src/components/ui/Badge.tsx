import React from "react";
import { type LucideIcon } from "lucide-react";

export type BadgeVariant = 
  | "default" 
  | "cyan" 
  | "safe" 
  | "warning" 
  | "danger" 
  | "purple" 
  | "info" 
  | "outline";

export type BadgeSize = "sm" | "md" | "lg";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  icon?: LucideIcon;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "default",
  size = "md",
  icon: Icon,
  className = ""
}) => {
  const variantStyles: Record<BadgeVariant, string> = {
    default: "surface-base text-brand-textSecondary border-brand-borderSubtle",
    cyan: "bg-brand-cyanBg text-brand-cyan border-brand-cyan/30",
    safe: "bg-brand-safeBg text-brand-safe border-brand-safe/30",
    warning: "bg-brand-warningBg text-brand-warning border-brand-warning/30",
    danger: "bg-brand-dangerBg text-brand-danger border-brand-danger/30",
    purple: "bg-brand-purpleBg text-brand-purple border-brand-purple/30",
    info: "bg-brand-infoBg text-brand-info border-brand-info/30",
    outline: "bg-transparent text-brand-text border-brand-border"
  };

  const sizeStyles: Record<BadgeSize, string> = {
    sm: "text-[8.5px] px-2 py-0.5 gap-1",
    md: "text-[9.5px] px-2.5 py-0.5 gap-1.5",
    lg: "text-xs px-3 py-1 gap-2"
  };

  const iconSizes: Record<BadgeSize, string> = {
    sm: "w-2.5 h-2.5",
    md: "w-3 h-3",
    lg: "w-3.5 h-3.5"
  };

  return (
    <span
      className={`inline-flex items-center rounded-full font-mono font-bold uppercase tracking-wider border backdrop-blur-md ${
        variantStyles[variant]
      } ${sizeStyles[size]} ${className}`}
    >
      {Icon && <Icon className={`${iconSizes[size]} flex-shrink-0`} />}
      <span>{children}</span>
    </span>
  );
};

