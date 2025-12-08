// Trend Sparkline Component
import { 
  LineChart, 
  Line, 
  ResponsiveContainer,
  Tooltip
} from 'recharts';

interface TrendSparklineProps {
  data: { value: number }[];
  color?: string;
  height?: number;
  showTooltip?: boolean;
}

export function TrendSparkline({ 
  data, 
  color = '#3b82f6', 
  height = 40,
  showTooltip = false
}: TrendSparklineProps) {
  // Determine if trend is positive
  const isPositive = data.length >= 2 && data[data.length - 1].value > data[0].value;
  const lineColor = color === 'auto' ? (isPositive ? '#10b981' : '#ef4444') : color;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
        {showTooltip && (
          <Tooltip
            contentStyle={{
              background: 'rgba(10, 14, 23, 0.9)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              padding: '8px 12px',
            }}
            labelStyle={{ display: 'none' }}
            formatter={(value: number) => [`${value.toLocaleString()}`, '']}
          />
        )}
        <Line
          type="monotone"
          dataKey="value"
          stroke={lineColor}
          strokeWidth={2}
          dot={false}
          activeDot={showTooltip ? { r: 4, fill: lineColor } : false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default TrendSparkline;
