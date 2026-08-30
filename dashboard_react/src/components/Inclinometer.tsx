import React from "react";

interface InclinometerProps {
  roll: number;
  pitch: number;
}

export const Inclinometer: React.FC<InclinometerProps> = ({ roll, pitch }) => {
  const absRoll = Math.abs(roll);
  let statusCol = "var(--safe)"; // Safe: Emerald Green
  if (absRoll > 5.0) {
    statusCol = "var(--danger)"; // Critical: Coral Red
  } else if (absRoll > 2.0) {
    statusCol = "var(--warning)"; // Warning: Maritime Amber
  }

  return (
    <div className="w-full flex flex-col items-center justify-center p-3.5 border border-brand-borderSubtle surface-elevated rounded-2xl shadow-sm font-mono">
      <div className="flex justify-between w-full mb-2 px-1 text-xs">
        <span className="text-[10px] text-brand-muted font-bold tracking-wider uppercase">DYNAMIC INCLINOMETER</span>
        <span className="text-[10px] text-brand-cyan font-bold">10Hz DAMPED</span>
      </div>

      <div className="relative w-full max-w-[200px] h-[150px] flex items-center justify-center">
        {/* Scale Dial (Static outer arc) */}
        <svg viewBox="0 0 200 150" className="absolute top-0 left-0 w-full h-full">
          {/* Tick marks */}
          <path d="M 30 105 A 80 80 0 0 1 170 105" fill="none" stroke="var(--border-subtle)" strokeWidth="2.5" strokeDasharray="2, 6" />
          {/* Degree labels */}
          <text x="30" y="120" fill="var(--text-muted)" fontSize="8.5" fontWeight="bold" textAnchor="middle">-15°</text>
          <text x="100" y="20" fill="var(--text-muted)" fontSize="8.5" fontWeight="bold" textAnchor="middle">0°</text>
          <text x="170" y="120" fill="var(--text-muted)" fontSize="8.5" fontWeight="bold" textAnchor="middle">+15°</text>
          {/* Center reference crosshair */}
          <line x1="100" y1="26" x2="100" y2="124" stroke="var(--border-subtle)" strokeWidth="1" strokeDasharray="3,3" />
          <line x1="30" y1="75" x2="170" y2="75" stroke="var(--border-subtle)" strokeWidth="1" strokeDasharray="3,3" />
        </svg>

        {/* Dynamic Hull Cross section (Rotates according to roll value) */}
        <div 
          style={{ transform: `rotate(${roll}deg)` }}
          className="transition-transform duration-150 ease-out w-[120px] h-[90px] flex items-center justify-center select-none"
        >
          <svg viewBox="0 0 120 90" className="w-full h-full overflow-visible">
            {/* Vessel Hull Cross Section */}
            <path 
              d="M 20 40 L 30 75 Q 60 85, 90 75 L 100 40 Z" 
              fill="var(--bg-surface)" 
              stroke={statusCol} 
              strokeWidth="2.5" 
            />
            {/* Deck load indicator */}
            <rect x="35" y="22" width="50" height="16" fill="var(--bg-elevated)" stroke="var(--cyan)" strokeWidth="1.2" rx="3" />
            <text x="60" y="33" fill="var(--text-brand)" fontSize="7.5" fontWeight="900" textAnchor="middle" style={{ letterSpacing: "0.5px" }}>CARGO</text>
            
            {/* Mast pointer */}
            <line x1="60" y1="40" x2="60" y2="10" stroke={statusCol} strokeWidth="2.5" />
            <polygon points="60,6 57,12 63,12" fill={statusCol} />
          </svg>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 gap-2 w-full mt-2">
        <div className="surface-base p-2 rounded-xl border border-brand-borderSubtle flex flex-col items-center shadow-inner">
          <span className="text-[9px] text-brand-muted uppercase font-bold">List (Roll)</span>
          <span className="text-xs text-brand-text font-black">{Math.abs(roll).toFixed(2)}° {roll > 0 ? 'STBD' : roll < 0 ? 'PORT' : 'BAL'}</span>
        </div>
        <div className="surface-base p-2 rounded-xl border border-brand-borderSubtle flex flex-col items-center shadow-inner">
          <span className="text-[9px] text-brand-muted uppercase font-bold">Trim (Pitch)</span>
          <span className="text-xs text-brand-text font-black">{Math.abs(pitch).toFixed(2)}° {pitch > 0 ? 'AFT' : pitch < 0 ? 'FWD' : 'EVEN'}</span>
        </div>
      </div>
    </div>
  );
};


