import React, { useEffect } from "react";
import { X } from "lucide-react";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl";
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  maxWidth = "lg"
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
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
    xl: "max-w-xl",
    "2xl": "max-w-2xl"
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
      {/* Translucent Backdrop */}
      <div 
        onClick={onClose}
        className="fixed inset-0 bg-brand-abyss/70 dark:bg-black/80 backdrop-blur-md transition-opacity animate-in fade-in duration-200" 
      />

      {/* Dialog Box */}
      <div className={`relative w-full ${widthMap[maxWidth]} bg-brand-elevated backdrop-blur-2xl border border-brand-border rounded-2xl shadow-2xl overflow-hidden z-10 animate-in fade-in zoom-in-95 duration-150`}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-brand-border flex items-center justify-between surface-base/70">
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

        {/* Content */}
        <div className="p-6 max-h-[80vh] overflow-y-auto space-y-4">
          {children}
        </div>
      </div>
    </div>
  );
};

