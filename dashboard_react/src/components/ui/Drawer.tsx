import React, { useEffect } from "react";
import { X } from "lucide-react";

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  width?: "sm" | "md" | "lg" | "xl";
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  width = "md"
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const widthMap = {
    sm: "max-w-md",
    md: "max-w-lg",
    lg: "max-w-2xl",
    xl: "max-w-4xl"
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Translucent Backdrop */}
      <div 
        onClick={onClose}
        className="fixed inset-0 bg-brand-abyss/70 dark:bg-black/80 backdrop-blur-md transition-opacity animate-in fade-in duration-200" 
      />

      {/* Glass Slide-over Drawer */}
      <div className={`relative w-full ${widthMap[width]} bg-brand-elevated backdrop-blur-2xl border-l border-brand-border h-full shadow-2xl flex flex-col z-10 animate-in slide-in-from-right duration-250`}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-brand-border flex items-center justify-between surface-base/60 backdrop-blur-lg">
          <div>
            <h2 className="text-xs font-black text-brand-text font-mono uppercase tracking-widest">
              {title}
            </h2>
            {subtitle && (
              <p className="text-[11px] text-brand-muted font-medium mt-0.5">
                {subtitle}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg border border-brand-borderSubtle surface-base hover:bg-brand-hover text-brand-muted hover:text-brand-text transition-colors shadow-sm"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {children}
        </div>
      </div>
    </div>
  );
};

