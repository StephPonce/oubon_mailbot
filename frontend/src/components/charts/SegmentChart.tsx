// Segment Donut Chart Component
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface SegmentDataPoint {
  name: string;
  value: number;
  color: string;
}

interface SegmentChartProps {
  data: SegmentDataPoint[];
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  centerLabel?: string;
  centerValue?: string;
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;

  return (
    <div className="glass-card-static p-3 border border-white/10">
      <div className="flex items-center gap-2 mb-1">
        <div 
          className="w-3 h-3 rounded-full" 
          style={{ backgroundColor: data.color }}
        />
        <span className="text-sm text-white/90 font-medium">{data.name}</span>
      </div>
      <p className="text-sm text-white/70">
        {data.value.toLocaleString()} ({data.percentage?.toFixed(1) || 0}%)
      </p>
    </div>
  );
}

export function SegmentChart({ 
  data, 
  height = 250,
  innerRadius = 60,
  outerRadius = 90,
  centerLabel,
  centerValue
}: SegmentChartProps) {
  // Calculate percentages
  const total = data.reduce((sum, item) => sum + item.value, 0);
  const dataWithPercentage = data.map(item => ({
    ...item,
    percentage: (item.value / total) * 100
  }));

  return (
    <div className="chart-container relative">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={dataWithPercentage}
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={2}
            dataKey="value"
            strokeWidth={0}
          >
            {dataWithPercentage.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={entry.color}
                className="transition-opacity hover:opacity-80"
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      
      {/* Center Label */}
      {(centerLabel || centerValue) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          {centerValue && (
            <span className="text-2xl font-semibold text-white">{centerValue}</span>
          )}
          {centerLabel && (
            <span className="text-xs text-white/50">{centerLabel}</span>
          )}
        </div>
      )}
      
      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-4 mt-4">
        {dataWithPercentage.map((item, index) => (
          <div key={index} className="flex items-center gap-2">
            <div 
              className="w-3 h-3 rounded-full" 
              style={{ backgroundColor: item.color }}
            />
            <span className="text-xs text-white/60">{item.name}</span>
            <span className="text-xs text-white/40">({item.percentage.toFixed(0)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SegmentChart;
