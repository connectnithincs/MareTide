import React from "react";
import { type LucideIcon, RefreshCw } from "lucide-react";

export type IconButtonVariant = 
  | "default" 
  | "primary" 
  | "ghost" 
  | "danger" 
  | "safe";

export type IconButtonSize = "xs" | "sm" | "md" | "lg";

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  loading?: boolean;
  tooltip?: string;
}

export const IconButton: React.FC<IconButtonProps> = ({
  icon: Icon,
  variant = "default",
  size = "md",
  loading = false,
  disabled,
  className = "",
  title,
  tooltip,
  ...props
}) => {
  const variantStyles: Record<IconButtonVariant, string> = {
    default: "surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text border border-brand-borderSubtle",
    primary: "bg-brand-cyan hover:bg-brand-cyan/90 text-slate-950 border border-brand-cyan shadow-sm shadow-brand-cyan/20",
    ghost: "bg-transparent hover:bg-brand-surface text-brand-muted hover:text-brand-text border border-transparent",
    danger: "bg-brand-dangerBg hover:bg-brand-danger text-brand-danger hover:text-white border border-brand-danger/30",
    safe: "bg-brand-safeBg hover:bg-brand-safe text-brand-safe hover:text-slate-950 border border-brand-safe/30"
  };

  const sizeStyles: Record<IconButtonSize, string> = {
    xs: "p-1 rounded-md",
    sm: "p-1.5 rounded-lg",
    md: "p-2 rounded-xl",
    lg: "p-2.5 rounded-xl"
  };

  const iconSizes: Record<IconButtonSize, string> = {
    xs: "w-3 h-3",
    sm: "w-3.5 h-3.5",
    md: "w-4 h-4",
    lg: "w-5 h-5"
  };

  return (
    <button
      disabled={disabled || loading}
      title={title || tooltip}
      className={`inline-flex items-center justify-center transition-all duration-150 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 shadow-sm ${
        variantStyles[variant]
      } ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {loading ? (
        <RefreshCw className={`${iconSizes[size]} animate-spin flex-shrink-0`} />
      ) : (
        <Icon className={`${iconSizes[size]} flex-shrink-0`} />
      )}
    </button>
  );
};
