// Trend Heatmap Grid Component
import { useMemo } from 'react';

interface HeatmapCell {
  label: string;
  value: number;
  max?: number;
}

interface TrendHeatmapProps {
  data: HeatmapCell[][];
  rowLabels: string[];
  columnLabels: string[];
  colorScale?: 'blue' | 'green' | 'purple' | 'amber';
}

export function TrendHeatmap({ 
  data, 
  rowLabels, 
  columnLabels,
  colorScale = 'blue'
}: TrendHeatmapProps) {
  const maxValue = useMemo(() => {
    return Math.max(...data.flat().map(cell => cell.value));
  }, [data]);

  const getColor = (value: number) => {
    const intensity = value / maxValue;
    
    const colors = {
      blue: `rgba(59, 130, 246, ${0.1 + intensity * 0.7})`,
      green: `rgba(16, 185, 129, ${0.1 + intensity * 0.7})`,
      purple: `rgba(139, 92, 246, ${0.1 + intensity * 0.7})`,
      amber: `rgba(245, 158, 11, ${0.1 + intensity * 0.7})`,
    };

    return colors[colorScale];
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr>
            <th className="p-2 text-xs text-white/40 text-left"></th>
            {columnLabels.map((label, i) => (
              <th key={i} className="p-2 text-xs text-white/40 text-center font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr key={rowIndex}>
              <td className="p-2 text-xs text-white/60 font-medium whitespace-nowrap">
                {rowLabels[rowIndex]}
              </td>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="p-1">
                  <div
                    className="w-full h-10 rounded-lg flex items-center justify-center text-xs font-medium text-white/80 transition-all hover:scale-105 cursor-default"
                    style={{ backgroundColor: getColor(cell.value) }}
                    title={`${cell.label}: ${cell.value.toLocaleString()}`}
                  >
                    {cell.value > 0 && cell.value.toLocaleString()}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default TrendHeatmap;
