import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "surface" | "interactive";
  padding?: "none" | "sm" | "md" | "lg";
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = "default",
  padding = "md",
  className = "",
  ...props
}) => {
  const variantStyles = {
    default: "bg-brand-card border border-brand-borderSubtle shadow-elevation-1 rounded-xl",
    elevated: "bg-brand-elevated border border-brand-border shadow-elevation-2 rounded-2xl",
    surface: "bg-brand-surface border border-brand-borderSubtle rounded-xl",
    interactive: "bg-brand-card hover:bg-brand-surface border border-brand-borderSubtle hover:border-brand-border transition-all duration-200 cursor-pointer active:scale-[0.99] rounded-xl"
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
