// Revenue Chart Component
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend
} from 'recharts';

interface RevenueDataPoint {
  date: string;
  revenue: number;
  orders?: number;
  profit?: number;
}

interface RevenueChartProps {
  data: RevenueDataPoint[];
  height?: number;
  showOrders?: boolean;
  showProfit?: boolean;
}

// Custom tooltip component
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="p-3 rounded-xl bg-white/90 backdrop-blur-xl border border-black/10 shadow-lg">
      <p className="text-xs text-tertiary mb-2">{label}</p>
      {payload.map((entry: any, index: number) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <div 
            className="w-2 h-2 rounded-full" 
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-secondary">{entry.name}:</span>
          <span className="text-primary font-medium">
            {entry.name === 'Orders' 
              ? entry.value?.toLocaleString() || 0
              : `$${entry.value?.toLocaleString() || 0}`
            }
          </span>
        </div>
      ))}
    </div>
  );
}

export function RevenueChart({ 
  data, 
  height = 300, 
  showOrders = true,
  showProfit = false 
}: RevenueChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-tertiary">
        No data available
      </div>
    );
  }

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="ordersGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
            </linearGradient>
          </defs>
          
          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke="rgba(0,0,0,0.08)" 
            vertical={false}
          />
          
          <XAxis 
            dataKey="date" 
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#86868B', fontSize: 11 }}
            dy={10}
          />
          
          <YAxis 
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#86868B', fontSize: 11 }}
            tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
            dx={-10}
          />
          
          <Tooltip content={<CustomTooltip />} />
          
          <Legend 
            wrapperStyle={{ paddingTop: 20 }}
            iconType="circle"
            iconSize={8}
            formatter={(value) => (
              <span style={{ color: '#6E6E73', fontSize: '12px' }}>{value}</span>
            )}
          />
          
          <Area
            type="monotone"
            dataKey="revenue"
            name="Revenue"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#revenueGradient)"
          />
          
          {showOrders && (
            <Area
              type="monotone"
              dataKey="orders"
              name="Orders"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#ordersGradient)"
            />
          )}
          
          {showProfit && data[0]?.profit !== undefined && (
            <Area
              type="monotone"
              dataKey="profit"
              name="Profit"
              stroke="#8b5cf6"
              strokeWidth={2}
              fill="url(#profitGradient)"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default RevenueChart;
