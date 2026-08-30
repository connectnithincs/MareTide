import React from "react";
import { type LucideIcon, RefreshCw } from "lucide-react";

export type ButtonVariant = 
  | "primary" 
  | "secondary" 
  | "outline" 
  | "ghost" 
  | "danger" 
  | "safe" 
  | "glass";

export type ButtonSize = "xs" | "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
  iconRight?: LucideIcon;
  loading?: boolean;
  fullWidth?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "primary",
  size = "md",
  icon: Icon,
  iconRight: IconRight,
  loading = false,
  fullWidth = false,
  disabled,
  className = "",
  ...props
}) => {
  const variantStyles: Record<ButtonVariant, string> = {
    primary: "bg-brand-cyan hover:bg-brand-cyan/90 text-slate-950 font-black shadow-md shadow-brand-cyan/20 border border-brand-cyan",
    secondary: "bg-brand-surface hover:bg-brand-elevated text-brand-text border border-brand-borderSubtle hover:border-brand-border",
    outline: "bg-transparent hover:bg-brand-surface text-brand-text border border-brand-border hover:border-brand-cyan/50",
    ghost: "bg-transparent hover:bg-brand-surface text-brand-muted hover:text-brand-text border border-transparent",
    danger: "bg-brand-danger hover:bg-brand-danger/90 text-white font-bold border border-brand-danger/80 shadow-md shadow-brand-danger/20",
    safe: "bg-brand-safe hover:bg-brand-safe/90 text-slate-950 font-black border border-brand-safe shadow-md shadow-brand-safe/20",
    glass: "glass-card hover:bg-brand-elevated text-brand-text border border-brand-borderSubtle hover:border-brand-border"
  };

  const sizeStyles: Record<ButtonSize, string> = {
    xs: "text-[10px] px-2.5 py-1 gap-1 rounded-md font-mono",
    sm: "text-[11px] px-3 py-1.5 gap-1.5 rounded-lg font-mono",
    md: "text-xs px-4 py-2 gap-2 rounded-xl font-mono",
    lg: "text-sm px-5 py-2.5 gap-2.5 rounded-xl font-mono"
  };

  const iconSizes: Record<ButtonSize, string> = {
    xs: "w-3 h-3",
    sm: "w-3.5 h-3.5",
    md: "w-4 h-4",
    lg: "w-4.5 h-4.5"
  };

  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-bold uppercase tracking-wider transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 select-none ${
        variantStyles[variant]
      } ${sizeStyles[size]} ${fullWidth ? "w-full" : ""} ${className}`}
      {...props}
    >
      {loading ? (
        <RefreshCw className={`${iconSizes[size]} animate-spin flex-shrink-0`} />
      ) : Icon ? (
        <Icon className={`${iconSizes[size]} flex-shrink-0`} />
      ) : null}
      
      <span>{children}</span>

      {!loading && IconRight && (
        <IconRight className={`${iconSizes[size]} flex-shrink-0`} />
      )}
    </button>
  );
};
