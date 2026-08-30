import React from "react";

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "panel" | "card" | "elevated" | "interactive";
  padding?: "none" | "sm" | "md" | "lg";
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  variant = "card",
  padding = "md",
  className = "",
  ...props
}) => {
  const variantStyles = {
    panel: "surface-elevated border border-brand-borderSubtle",
    card: "glass-card",
    elevated: "glass-elevated",
    interactive: "glass-card hover:bg-brand-hover hover:border-brand-border transition-all duration-200 cursor-pointer active:scale-[0.99]"
  };

  const paddingStyles = {
    none: "",
    sm: "p-3",
    md: "p-4 sm:p-5",
    lg: "p-6"
  };

  return (
    <div
      className={`${variantStyles[variant]} ${paddingStyles[padding]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

