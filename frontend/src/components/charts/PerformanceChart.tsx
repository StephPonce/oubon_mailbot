// Performance Bar Chart Component
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell
} from 'recharts';

interface PerformanceDataPoint {
  name: string;
  value: number;
  change?: number;
}

interface PerformanceChartProps {
  data: PerformanceDataPoint[];
  height?: number;
  color?: string;
  showChange?: boolean;
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;

  return (
    <div className="glass-card-static p-3 border border-white/10">
      <p className="text-sm text-white/90 font-medium mb-1">{data.name}</p>
      <p className="text-sm text-white/70">
        Value: <span className="text-white font-medium">{data.value.toLocaleString()}</span>
      </p>
      {data.change !== undefined && (
        <p className={`text-xs mt-1 ${data.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {data.change >= 0 ? '+' : ''}{data.change}% vs last period
        </p>
      )}
    </div>
  );
}

export function PerformanceChart({ 
  data, 
  height = 300,
  color = '#3b82f6',
  showChange = true
}: PerformanceChartProps) {
  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 20, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={1} />
              <stop offset="100%" stopColor={color} stopOpacity={0.6} />
            </linearGradient>
          </defs>
          
          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke="rgba(255,255,255,0.05)" 
            vertical={false}
          />
          
          <XAxis 
            dataKey="name" 
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }}
            dy={10}
          />
          
          <YAxis 
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }}
            tickFormatter={(value) => value.toLocaleString()}
            dx={-10}
          />
          
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          
          <Bar 
            dataKey="value" 
            radius={[6, 6, 0, 0]}
            maxBarSize={50}
          >
            {data.map((entry, index) => (
              <Cell 
                key={`cell-${index}`}
                fill="url(#barGradient)"
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PerformanceChart;
