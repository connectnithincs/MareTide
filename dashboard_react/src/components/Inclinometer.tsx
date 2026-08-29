import React from "react";

interface InclinometerProps {
  roll: number;
  pitch: number;
}

export const Inclinometer: React.FC<InclinometerProps> = ({ roll, pitch }) => {
  const absRoll = Math.abs(roll);
  let statusCol = "#10b981"; // Safe: Green
  if (absRoll > 5.0) {
    statusCol = "#E7594B"; // Critical: Danger Red
  } else if (absRoll > 2.0) {
    statusCol = "#f59e0b"; // Warning: Amber
  }

  return (
    <div className="w-full flex flex-col items-center justify-center p-4 border border-brand-border bg-brand-card rounded-2xl glass-panel shadow-md">
      <div className="flex justify-between w-full mb-3 px-2">
        <span className="text-xs text-brand-muted font-bold tracking-wider uppercase">Live Inclinometer</span>
        <span className="text-xs text-brand-text font-bold">Heel & Trim Monitor</span>
      </div>

      <div className="relative w-full max-w-[200px] h-[160px] flex items-center justify-center">
        {/* Scale Dial (Static outer arc) */}
        <svg viewBox="0 0 200 160" className="absolute top-0 left-0 w-full h-full">
          {/* Tick marks */}
          <path d="M 30 110 A 80 80 0 0 1 170 110" fill="none" stroke="var(--border-brand)" strokeWidth="3" strokeDasharray="2, 6" />
          {/* Degree labels */}
          <text x="30" y="125" fill="var(--text-muted)" fontSize="8.5" fontWeight="bold" textAnchor="middle">-15°</text>
          <text x="100" y="24" fill="var(--text-muted)" fontSize="8.5" fontWeight="bold" textAnchor="middle">0°</text>
          <text x="170" y="125" fill="var(--text-muted)" fontSize="8.5" fontWeight="bold" textAnchor="middle">15°</text>
          {/* Center reference crosshair */}
          <line x1="100" y1="30" x2="100" y2="130" stroke="var(--border-brand)" strokeWidth="1.5" strokeDasharray="3,3" />
          <line x1="30" y1="80" x2="170" y2="80" stroke="var(--border-brand)" strokeWidth="1.5" strokeDasharray="3,3" />
        </svg>

        {/* Dynamic Hull Cross section (Rotates according to roll value) */}
        <div 
          style={{ transform: `rotate(${roll}deg)` }}
          className="transition-transform duration-200 ease-out w-[120px] h-[90px] flex items-center justify-center"
        >
          <svg viewBox="0 0 120 90" className="w-full h-full overflow-visible">
            {/* Draw Vessel Hull cross section */}
            <path 
              d="M 20 40 L 30 75 Q 60 85, 90 75 L 100 40 Z" 
              fill="#052659" 
              stroke={statusCol} 
              strokeWidth="2.5" 
            />
            {/* Deck load indicator */}
            <rect x="35" y="22" width="50" height="16" fill="#5483B3" stroke="#C1E8FF" strokeWidth="1.2" rx="3" />
            <text x="60" y="33" fill="#ffffff" fontSize="7.5" fontWeight="900" textAnchor="middle" style={{ letterSpacing: "0.5px" }}>CARGO</text>
            
            {/* Mast/Center indicator pointer */}
            <line x1="60" y1="40" x2="60" y2="10" stroke={statusCol} strokeWidth="2.5" />
            <polygon points="60,6 57,12 63,12" fill={statusCol} />
          </svg>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="flex gap-4 w-full mt-2">
        <div className="flex-1 bg-brand-app p-2.5 rounded-xl border border-brand-border flex flex-col items-center shadow-sm">
          <span className="text-[10px] text-brand-muted uppercase font-bold tracking-wider">Roll (Heel)</span>
          <span className="text-sm text-brand-text font-black tracking-tight">{roll.toFixed(2)}°</span>
        </div>
        <div className="flex-1 bg-brand-app p-2.5 rounded-xl border border-brand-border flex flex-col items-center shadow-sm">
          <span className="text-[10px] text-brand-muted uppercase font-bold tracking-wider">Pitch (Trim)</span>
          <span className="text-sm text-brand-text font-black tracking-tight">{pitch.toFixed(2)}°</span>
        </div>
      </div>
    </div>
  );
};
