import React from "react";

interface SCADADigitalTwinProps {
  tanks: {
    [key: string]: {
      name: string;
      current_volume: number;
      capacity: number;
      fill_ratio: number;
    };
  };
}

export const SCADADigitalTwin: React.FC<SCADADigitalTwinProps> = ({ tanks }) => {
  // Safe accessor to retrieve tank levels
  const getTank = (side: "port" | "starboard", bay: number) => {
    const key = `${side}_${bay}`;
    return tanks[key] || { name: `${side.toUpperCase()}-${bay}`, current_volume: 0, capacity: 300, fill_ratio: 0 };
  };

  const renderTank = (x: number, y: number, width: number, height: number, side: "port" | "starboard", bay: number) => {
    const tank = getTank(side, bay);
    const pct = tank.fill_ratio; // 0.0 to 1.0
    const fillHeight = height * pct;
    const fillY = y + (height - fillHeight);

    // Pick color based on fill ratio
    let fillCol = "fill-[#5483B3]"; // Normal: Premium brand blue
    if (pct > 0.85) fillCol = "fill-[#052659] fill-opacity-40 stroke-[#7DA0CA]/50 stroke-1"; // Full: Marine blue
    if (pct < 0.15) fillCol = "fill-[#7DA0CA]"; // Low: Soft blue-gray
    
    // Customize full state to look like a high-density water layer
    if (pct > 0.85) {
      fillCol = "fill-sky-600";
    } else if (pct > 0.15) {
      fillCol = "fill-sky-500/80";
    } else {
      fillCol = "fill-sky-400/40";
    }

    return (
      <g key={`${side}-${bay}`} className="transition-all duration-300">
        {/* Outline container */}
        <rect 
          x={x} 
          y={y} 
          width={width} 
          height={height} 
          fill="#021024" 
          stroke="#5483B3" 
          strokeWidth="1.5" 
          rx="6" 
        />
        
        {/* Dynamic Water fill */}
        <rect 
          x={x + 1} 
          y={fillY + 1} 
          width={width - 2} 
          height={Math.max(0, fillHeight - 2)} 
          className={`${fillCol} transition-all duration-500`}
          rx="5" 
        />
        
        {/* Labels & Metrics */}
        <text 
          x={x + width / 2} 
          y={y + 16} 
          textAnchor="middle" 
          fill="#ffffff" 
          fontSize="10" 
          fontWeight="800"
          style={{ textShadow: "0 1px 3px rgba(2, 16, 36, 0.95)" }}
        >
          {side.toUpperCase()[0]}T-{bay}
        </text>
        <text 
          x={x + width / 2} 
          y={y + height / 2 + 6} 
          textAnchor="middle" 
          fill="#C1E8FF" 
          fontSize="9" 
          fontWeight="700"
          style={{ textShadow: "0 1px 3px rgba(2, 16, 36, 0.95)" }}
        >
          {Math.round(pct * 100)}%
        </text>
        <text 
          x={x + width / 2} 
          y={y + height - 8} 
          textAnchor="middle" 
          fill="#ffffff" 
          fontSize="8.5" 
          fontWeight="600"
          style={{ textShadow: "0 1px 3px rgba(2, 16, 36, 0.95)" }}
        >
          {Math.round(tank.current_volume)}t
        </text>
      </g>
    );
  };

  return (
    <div className="w-full flex flex-col items-center justify-center p-4 border border-brand-border bg-brand-card rounded-2xl glass-panel shadow-md">
      <div className="flex justify-between w-full mb-3 px-2">
        <span className="text-xs text-brand-muted font-bold tracking-wider uppercase">SCADA Digital Twin Monitoring</span>
        <span className="text-xs text-brand-accent font-bold">● Active Feedback Loop</span>
      </div>
      
      {/* Ship Hull top view SVG */}
      <svg viewBox="0 0 600 220" className="w-full max-w-[560px] h-auto">
        {/* Outer Hull Outline */}
        <path 
          d="M 60 110 Q 120 20, 200 20 L 520 20 C 560 20, 580 60, 590 110 C 580 160, 560 200, 520 200 L 200 200 Q 120 200, 60 110 Z" 
          fill="none" 
          stroke="#5483B3" 
          strokeWidth="3.5" 
        />
        
        {/* Center Line (Keel) */}
        <line x1="60" y1="110" x2="590" y2="110" stroke="#7DA0CA" strokeDasharray="5,5" strokeWidth="1.5" />

        {/* PORT TANKS (Top row) */}
        {renderTank(150, 30, 80, 68, "port", 1)}
        {renderTank(240, 30, 80, 68, "port", 2)}
        {renderTank(330, 30, 80, 68, "port", 3)}
        {renderTank(420, 30, 80, 68, "port", 4)}

        {/* STARBOARD TANKS (Bottom row) */}
        {renderTank(150, 122, 80, 68, "starboard", 1)}
        {renderTank(240, 122, 80, 68, "starboard", 2)}
        {renderTank(330, 122, 80, 68, "starboard", 3)}
        {renderTank(420, 122, 80, 68, "starboard", 4)}

        {/* Bow and Stern Labels */}
        <text x="85" y="114" fill="#3D5A80" fontSize="10" fontWeight="bold" textAnchor="middle">BOW</text>
        <text x="565" y="114" fill="#3D5A80" fontSize="10" fontWeight="bold" textAnchor="middle">STERN</text>
      </svg>
    </div>
  );
};
