import React from "react";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "circular" | "rectangular" | "rounded";
  width?: string | number;
  height?: string | number;
  animate?: boolean;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  variant = "rounded",
  width,
  height,
  animate = true,
  className = "",
  style,
  ...props
}) => {
  const variantStyles = {
    text: "rounded h-3 w-full",
    circular: "rounded-full",
    rectangular: "rounded-none",
    rounded: "rounded-xl"
  };

  const inlineStyles: React.CSSProperties = {
    width: typeof width === "number" ? `${width}px` : width,
    height: typeof height === "number" ? `${height}px` : height,
    ...style
  };

  return (
    <div
      className={`surface-base border border-brand-borderSubtle/50 ${
        animate ? "animate-pulse" : ""
      } ${variantStyles[variant]} ${className}`}
      style={inlineStyles}
      {...props}
    />
  );
};

export const SkeletonCard: React.FC<{ className?: string }> = ({ className = "" }) => (
  <div className={`p-4 rounded-xl border border-brand-borderSubtle surface-base/40 space-y-2.5 animate-pulse ${className}`}>
    <div className="flex items-center justify-between">
      <Skeleton variant="text" width="40%" height={12} />
      <Skeleton variant="rounded" width={45} height={16} />
    </div>
    <Skeleton variant="text" width="60%" height={24} />
    <Skeleton variant="text" width="80%" height={10} />
  </div>
);

