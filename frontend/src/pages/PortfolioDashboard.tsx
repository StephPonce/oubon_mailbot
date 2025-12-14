import { useState, useEffect } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Package,
  DollarSign,
  ShoppingCart,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  BarChart3,
  Activity,
  Target,
  Brain,
  RefreshCw,
  ChevronRight,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  Download,
  FileText,
  PieChart,
  Globe,
  MapPin,
  Play,
  Pause,
  ArrowRight
} from 'lucide-react';

// Import hooks and components
import { useAnalyticsOverview, usePortfolioRankings } from '../hooks/queries/useAnalytics';
import { useProducts } from '../hooks/queries/useProducts';
import { useSystemHealth } from '../hooks/queries/useHealth';
import { useSocket } from '../hooks/useSocket';
import { useAppStore } from '../stores/appStore';
import { RevenueChart, TrendSparkline } from '../components/charts';
import { EmailOverview } from '../components/dashboard/EmailOverview';
import { ExplainTooltip } from '../components/ui/ExplainTooltip';
import { RecentActions } from '../components/RecentActions';

// Types (assuming they are defined in a types file or within the hooks)
interface MetricData {
  label: string;
  value: string;
  change: number;
  changeLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
}

interface ProductRecommendation {
  id: string;
  name: string;
  image: string;
  score: number;
  profit: string;
  trend: 'up' | 'down' | 'stable';
  trendValue: string;
  source: string;
  niche: string;
  reason: string;
  sparklineData?: { value: number }[];
}

interface AIInsight {
  id: string;
  type: 'opportunity' | 'warning' | 'success';
  title: string;
  description: string;
  action?: string;
  timestamp: string;
}

interface SystemStatus {
  name: string;
  status: 'online' | 'processing' | 'warning' | 'offline';
  detail: string;
}

interface ProductPerformance {
  id: string;
  name: string;
  revenue: number;
  units_sold: number;
  profit: number;
  roas: number;
  status: 'active' | 'paused' | 'low-stock';
  niche: string;
  image?: string;
}

interface ChannelData {
  name: string;
  revenue: number;
  percentage: number;
  roi: number;
  color: string;
}

interface GeographicData {
  country: string;
  revenue: number;
  customers: number;
  orders: number;
}

interface ProjectionData {
  period: string;
  value: number;
  confidence_low: number;
  confidence_high: number;
}

// Sub-components with fixes applied

function MetricCard({ metric, delay, isLive }: { metric: MetricData; delay: number; isLive?: boolean }) {
  return (
    <div className="glass-card p-5 animate-fadeIn" style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-start justify-between mb-4">
        <div className={`stat-card-icon ${metric.iconColor}`}>
          <metric.icon className="w-5 h-5" />
        </div>
        <div className="flex items-center gap-2">
          {isLive && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/100/10 border border-green-500/20">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500/100 animate-pulse" />
              <span className="text-[10px] text-success font-medium">LIVE</span>
            </div>
          )}
          <div className={`metric-change ${metric.change >= 0 ? 'text-success' : 'text-error'}`}>
            {metric.change >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
            <span>{Math.abs(metric.change)}%</span>
          </div>
        </div>
      </div>
      <div className="text-3xl font-bold text-primary">{metric.value}</div>
      <div className="text-sm text-secondary">{metric.label}</div>
      <div className="text-xs text-tertiary mt-1">{metric.changeLabel}</div>
    </div>
  );
}

function ProductRecommendationCard({ product, index }: { product: ProductRecommendation; index: number }) {
  const getScoreColor = (score: number) => {
    if (score >= 8) return 'bg-success text-white';
    if (score >= 6) return 'bg-warning text-black';
    return 'bg-error text-white';
  };

  return (
    <div className="product-card animate-fadeIn" style={{ animationDelay: `${index * 100}ms` }}>
      <div className="relative">
        <div className="w-full h-44 bg-black/20 flex items-center justify-center">
          {product.image ? <img src={product.image} alt={product.name} className="w-full h-full object-cover" /> : <Package className="w-12 h-12 text-tertiary" />}
        </div>
        <div className={`product-score ${getScoreColor(product.score || 0)}`}>
          {(product.score || 0).toFixed(1)}
        </div>
        <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-lg bg-black/40 backdrop-blur-sm border border-white/10">
          {product.trend === 'up' ? <TrendingUp className="w-3.5 h-3.5 text-success" /> : product.trend === 'down' ? <TrendingDown className="w-3.5 h-3.5 text-error" /> : <Activity className="w-3.5 h-3.5 text-tertiary" />}
          <span className={`text-xs font-medium ${product.trend === 'up' ? 'text-success' : product.trend === 'down' ? 'text-error' : 'text-tertiary'}`}>{product.trendValue}</span>
        </div>
      </div>
      <div className="p-4">
        <h3 className="text-sm font-medium text-primary line-clamp-2 leading-tight mb-2">{product.name}</h3>
        <div className="flex items-center gap-2 mb-3">
          <span className="badge badge-purple">{product.niche}</span>
          <span className="text-xs text-tertiary">{product.source}</span>
        </div>
        {product.sparklineData && <div className="h-8 mb-3"><TrendSparkline data={product.sparklineData} color="auto" /></div>}
        <div className="p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 mb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2 flex-1 min-w-0">
              <Brain className="w-3.5 h-3.5 text-cyan-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-secondary leading-relaxed line-clamp-2">{product.reason}</p>
            </div>
            <ExplainTooltip rationale={product.reason || "AI recommendation"} confidence={Math.round((product.score || 0) * 10)} factors={[]} position="bottom" />
          </div>
        </div>
        <div className="flex items-center justify-between pt-3 border-t border-white/10">
          <div>
            <div className="text-xs text-tertiary">Est. Profit</div>
            <div className="text-sm font-semibold text-success">{product.profit}</div>
          </div>
          <button className="btn-ghost text-xs"><span>Analyze</span><ChevronRight className="w-3.5 h-3.5" /></button>
        </div>
      </div>
    </div>
  );
}

function AIInsightCard({ insight }: { insight: AIInsight }) {
  const typeConfig = {
    opportunity: { icon: Sparkles, color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
    warning: { icon: AlertCircle, color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/20' },
    success: { icon: CheckCircle2, color: 'text-success', bg: 'bg-success/10', border: 'border-success/20' },
  };
  const config = typeConfig[insight.type];
  const Icon = config.icon;

  return (
    <div className={`p-4 rounded-xl ${config.bg} border ${config.border}`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg bg-black/20 ${config.color}`}><Icon className="w-4 h-4" /></div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-primary mb-1">{insight.title}</h4>
          <p className="text-xs text-secondary leading-relaxed line-clamp-2">{insight.description}</p>
          {insight.action && <button className="mt-2 text-xs font-medium text-accent hover:text-accent-hover flex items-center gap-1">{insight.action}<ExternalLink className="w-3 h-3" /></button>}
        </div>
        <span className="text-[10px] text-tertiary flex-shrink-0">{insight.timestamp}</span>
      </div>
    </div>
  );
}

function SystemStatusPanel({ systems, isLoading }: { systems: SystemStatus[]; isLoading: boolean }) {
  return (
    <div className="glass-card-static p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-primary">System Status</h3>
        <button className="p-1.5 rounded-lg hover:bg-white/10 text-tertiary"><RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} /></button>
      </div>
      <div className="space-y-3">
        {systems.map((system, index) => (
          <div key={index} className="flex items-center gap-3">
            <div className={`status-dot ${system.status}`} />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-primary">{system.name}</div>
              <div className="text-xs text-tertiary line-clamp-1">{system.detail}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function QuickActionsPanel() {
  const actions = [
    { icon: Brain, label: 'Ask Ospra for Recommendations', iconColor: 'purple' },
    { icon: Package, label: 'Deploy Product to Shopify', iconColor: 'green' },
    { icon: Target, label: 'Run Niche Analysis', iconColor: 'cyan' },
    { icon: BarChart3, label: 'Generate Report', iconColor: 'blue' },
  ];
  return (
    <div className="glass-card-static p-5">
      <h3 className="text-sm font-medium text-primary mb-4">Quick Actions</h3>
      <div className="space-y-2">
        {actions.map((action, index) => (
          <button key={index} className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 transition-all text-left group">
            <div className={`stat-card-icon ${action.iconColor}`}><action.icon className="w-4 h-4" /></div>
            <span className="text-sm text-primary flex-1 min-w-0">{action.label}</span>
            <ChevronRight className="w-4 h-4 text-tertiary group-hover:translate-x-1 transition-transform" />
          </button>
        ))}
      </div>
    </div>
  );
}

function ProductPerformanceTable({ products }: { products: ProductPerformance[] }) {
  const getStatusColor = (status: string) => {
    if (status === 'active') return 'bg-success/10 text-success border-success/20';
    if (status === 'paused') return 'bg-warning/10 text-warning border-warning/20';
    return 'bg-error/10 text-error border-error/20';
  };
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2"><BarChart3 className="w-5 h-5 text-accent" /><h2 className="text-lg font-medium text-primary">Product Performance</h2></div>
        <button className="btn-ghost text-sm">Export<Download className="w-4 h-4" /></button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/10"><th className="text-left py-3 px-4 text-sm font-medium text-secondary">Product</th><th className="text-right py-3 px-4 text-sm font-medium text-secondary">Revenue</th><th className="text-right py-3 px-4 text-sm font-medium text-secondary">Units Sold</th><th className="text-right py-3 px-4 text-sm font-medium text-secondary">Profit</th><th className="text-right py-3 px-4 text-sm font-medium text-secondary">ROAS</th><th className="text-center py-3 px-4 text-sm font-medium text-secondary">Status</th><th className="text-center py-3 px-4 text-sm font-medium text-secondary">Actions</th></tr>
          </thead>
          <tbody>
            {products.map((product) => (
              <tr key={product.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-3">
                    {product.image && <img src={product.image} alt={product.name} className="w-10 h-10 rounded-lg object-cover" />}
                    <div>
                      <div className="text-sm font-medium text-primary">{product.name}</div>
                      <div className="text-xs text-tertiary">{product.niche}</div>
                    </div>
                  </div>
                </td>
                <td className="text-right py-3 px-4 text-sm font-medium text-primary">${product.revenue.toLocaleString()}</td>
                <td className="text-right py-3 px-4 text-sm text-secondary">{product.units_sold}</td>
                <td className="text-right py-3 px-4 text-sm font-medium text-success">${product.profit.toLocaleString()}</td>
                <td className="text-right py-3 px-4 text-sm font-medium text-primary">{product.roas.toFixed(2)}x</td>
                <td className="text-center py-3 px-4"><span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${getStatusColor(product.status)}`}>{product.status}</span></td>
                <td className="text-center py-3 px-4"><div className="flex items-center justify-center gap-2"><button className="p-1.5 rounded-lg hover:bg-white/10 text-tertiary"><Play className="w-4 h-4" /></button><button className="p-1.5 rounded-lg hover:bg-white/10 text-tertiary"><Pause className="w-4 h-4" /></button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AIWeeklyBriefing({ data }: { data: any }) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2"><FileText className="w-5 h-5 text-accent-secondary" /><h2 className="text-lg font-medium text-primary">Ospra's Weekly Briefing</h2></div>
        <button className="btn-primary text-sm bg-accent-secondary">Generate PDF<Download className="w-4 h-4" /></button>
      </div>
      <div className="space-y-4">
        <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20">
          <div className="flex items-start gap-3 mb-3">
            <Brain className="w-5 h-5 text-cyan-400 mt-0.5" />
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-medium text-primary mb-2">Key Insights This Week</h3>
              <ul className="space-y-2 text-sm text-secondary">
                <li className="flex items-start gap-2"><ArrowRight className="w-4 h-4 text-success mt-0.5 flex-shrink-0" /><span>Revenue is up 23% this week, driven by LED strip sales.</span></li>
                <li className="flex items-start gap-2"><ArrowRight className="w-4 h-4 text-warning mt-0.5 flex-shrink-0" /><span>Kitchen gadgets niche showing declining engagement - consider pausing ad spend.</span></li>
                <li className="flex items-start gap-2"><ArrowRight className="w-4 h-4 text-error mt-0.5 flex-shrink-0" /><span>3 products need restocking within 7 days.</span></li>
              </ul>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-success/10 border border-success/20">
          <h3 className="text-sm font-medium text-primary mb-2 flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-success" />Recommended Actions</h3>
          <div className="space-y-2 text-sm text-secondary">
            <div className="flex items-center justify-between p-2 rounded-lg hover:bg-black/20"><span className="flex-1 min-w-0 line-clamp-1">Launch Meta ad campaign for LED strips</span><button className="text-xs text-accent hover:text-white font-medium">Start Campaign</button></div>
            <div className="flex items-center justify-between p-2 rounded-lg hover:bg-black/20"><span className="flex-1 min-w-0 line-clamp-1">Reorder inventory for top 3 products</span><button className="text-xs text-accent hover:text-white font-medium">View Products</button></div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RevenueProjections({ projections }: { projections: ProjectionData[] }) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2"><TrendingUp className="w-5 h-5 text-success" /><h2 className="text-lg font-medium text-primary">Revenue Projections</h2></div>
        <div className="text-xs text-tertiary">Based on current trends & seasonality</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {projections.map((proj, index) => (
          <div key={index} className="p-4 rounded-xl bg-white/5 border border-white/10">
            <div className="text-xs text-tertiary mb-1">{proj.period}</div>
            <div className="text-2xl font-semibold text-primary mb-2">${proj.value.toLocaleString()}</div>
            <div className="text-xs text-secondary">Range: ${proj.confidence_low.toLocaleString()} - ${proj.confidence_high.toLocaleString()}</div>
          </div>
        ))}
      </div>
      <div className="p-4 rounded-xl bg-accent-secondary/10 border border-accent-secondary/20">
        <div className="flex items-start gap-3"><Brain className="w-5 h-5 text-accent-secondary mt-0.5" /><div className="flex-1 text-sm text-secondary"><p className="mb-2"><span className="font-medium text-primary">Projection Assumptions:</span></p><ul className="space-y-1"><li>• Current conversion rate of 2.3% maintained</li><li>• Seasonal uptick expected in Q4 (+15%)</li></ul></div></div>
      </div>
    </div>
  );
}

function ChannelBreakdown({ channels }: { channels: ChannelData[] }) {
  const total = channels.reduce((sum, ch) => sum + ch.revenue, 0);
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2"><PieChart className="w-5 h-5 text-cyan-400" /><h2 className="text-lg font-medium text-primary">Revenue by Channel</h2></div>
        <div className="text-sm text-secondary">Total: ${total.toLocaleString()}</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="flex items-center justify-center">
          <div className="relative w-48 h-48">
            {/* Pie chart rendering would go here */}
            <div className="absolute inset-8 rounded-full bg-bg-dark-elevated flex items-center justify-center"><div className="text-center"><div className="text-2xl font-semibold text-primary">{channels.length}</div><div className="text-xs text-tertiary">Channels</div></div></div>
          </div>
        </div>
        <div className="space-y-3">
          {channels.map((channel) => (
            <div key={channel.name} className="p-4 rounded-xl border border-white/10 hover:border-white/20 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ backgroundColor: channel.color }} /><span className="text-sm font-medium text-primary">{channel.name}</span></div>
                <span className="text-sm font-semibold text-primary">${channel.revenue.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-secondary"><span>{channel.percentage.toFixed(1)}% of total</span><span className="text-success font-medium">{channel.roi.toFixed(2)}x ROI</span></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function GeographicDistribution({ locations }: { locations: GeographicData[] }) {
  const total = locations.reduce((sum, loc) => sum + loc.revenue, 0);
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6"><div className="flex items-center gap-2"><Globe className="w-5 h-5 text-accent" /><h2 className="text-lg font-medium text-primary">Top Markets</h2></div></div>
      <div className="space-y-3">
        {locations.map((location) => {
          const percentage = (location.revenue / total) * 100;
          return (
            <div key={location.country} className="p-4 rounded-xl border border-white/10">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center"><MapPin className="w-4 h-4 text-accent" /></div>
                  <div><div className="text-sm font-medium text-primary">{location.country}</div><div className="text-xs text-tertiary">{location.customers} customers • {location.orders} orders</div></div>
                </div>
                <div className="text-right"><div className="text-sm font-semibold text-primary">${location.revenue.toLocaleString()}</div><div className="text-xs text-secondary">{percentage.toFixed(1)}%</div></div>
              </div>
              <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-accent-secondary to-accent rounded-full" style={{ width: `${percentage}%` }} /></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="h-32 bg-white/5 rounded-2xl" />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-96 bg-white/5 rounded-2xl" />
        <div className="h-96 bg-white/5 rounded-2xl" />
      </div>
    </div>
  );
}

// Main Dashboard Component
export default function PortfolioDashboard() {
  const { data: dashboardData, isLoading: metricsLoading } = useAnalyticsOverview();
  const { data: productsData, isLoading: productsLoading } = useProducts({ limit: 4 });
  const { data: healthData, isLoading: healthLoading } = useSystemHealth();
  const { isConnected } = useSocket();

  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [recommendations, setRecommendations] = useState<ProductRecommendation[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [systems, setSystems] = useState<SystemStatus[]>([]);
  
  // Dummy data for new sections
  const [productPerformance] = useState<ProductPerformance[]>([
    { id: '1', name: 'LED Strip Lights 16ft', revenue: 4850, units_sold: 97, profit: 1940, roas: 4.2, status: 'active', niche: 'Smart Home', image: '/placeholder.svg' },
    { id: '2', name: 'Wireless Phone Charger', revenue: 3200, units_sold: 128, profit: 1120, roas: 3.5, status: 'active', niche: 'Tech Accessories', image: '/placeholder.svg' },
  ]);
  const [projections] = useState<ProjectionData[]>([
    { period: 'Next 7 Days', value: 12500, confidence_low: 10800, confidence_high: 14200 },
    { period: 'Next 30 Days', value: 48000, confidence_low: 42000, confidence_high: 54000 },
    { period: 'Next 90 Days', value: 152000, confidence_low: 135000, confidence_high: 170000 },
  ]);
  const [channels] = useState<ChannelData[]>([
    { name: 'Organic Search', revenue: 5200, percentage: 36.6, roi: 8.5, color: '#10b981' },
    { name: 'Meta Ads', revenue: 4100, percentage: 28.9, roi: 4.2, color: '#3b82f6' },
  ]);
  const [geoData] = useState<GeographicData[]>([
    { country: 'United States', revenue: 8500, customers: 245, orders: 387 },
    { country: 'United Kingdom', revenue: 3200, customers: 98, orders: 156 },
  ]);

  useEffect(() => {
    // Data transformation logic...
    if (dashboardData) {
        setMetrics([
            { label: 'Total Revenue', value: `$${(dashboardData?.total_revenue || 0).toLocaleString()}`, change: dashboardData?.revenue_change || 12.5, changeLabel: 'vs last month', icon: DollarSign, iconColor: 'green' },
            { label: 'Active Products', value: String(dashboardData?.total_products || 0), change: dashboardData?.products_change || 8, changeLabel: '5 new this week', icon: Package, iconColor: 'blue' },
            { label: 'Conversion Rate', value: `${(dashboardData?.conversion_rate || 0)}%`, change: dashboardData?.conversion_change || 5.2, changeLabel: 'vs last week', icon: Target, iconColor: 'purple' },
            { label: 'Orders Today', value: String(dashboardData?.orders_count || 0), change: dashboardData?.orders_change || 3, changeLabel: 'vs yesterday', icon: ShoppingCart, iconColor: 'cyan' },
        ]);
        setInsights([
            { id: '1', type: 'opportunity', title: 'Revenue Growth Opportunity', description: `Your revenue is ${dashboardData.total_revenue > 0 ? 'trending upward' : 'ready to launch'}. Consider expanding your product catalog.`, action: 'View Products', timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })},
            { id: '2', type: 'warning', title: 'No Active Products', description: 'Start by discovering and deploying products to your store.', action: 'Discover Products', timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })},
        ]);
    }
    if(productsData?.products) {
        setRecommendations(productsData.products.slice(0, 4).map((p: any) => ({...p, id: p.id || p.product_id, name: p.name || p.title, image: p.image_url || '', score: p.score || 0, profit: `$${(p.estimated_profit || 0).toFixed(2)}`, trend: p.trend || 'stable', trendValue: p.trend_value || '0%', source: p.source || 'N/A', niche: p.niche || 'N/A', reason: p.ai_reason || 'AI recommended'})));
    }
    if(healthData?.services) {
        setSystems(Object.entries(healthData.services).map(([key, value]: [string, any]) => ({ name: key, status: value.status === 'CONNECTED' ? 'online' : 'offline', detail: value.detail || value.message || 'Connected' })));
    } else if (healthData?.status) {
        setSystems([{ name: 'System', status: healthData.status === 'healthy' ? 'online' : 'warning', detail: healthData.message || 'Operational' }]);
    }
  }, [dashboardData, productsData, healthData]);

  const isLoading = metricsLoading && productsLoading;
  if (isLoading) return <DashboardSkeleton />;

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary mb-1">Command Center</h1>
          <p className="text-sm text-secondary">Welcome back. Ospra has found {recommendations.length} new opportunities for you today.</p>
        </div>
        <div className="flex items-center gap-3">
          {isConnected && <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-success/10 border border-success/20"><div className="w-2 h-2 rounded-full bg-success animate-pulse" /><span className="text-xs text-success font-medium">Live Data</span></div>}
          <div className="flex items-center gap-2 text-xs text-tertiary"><Clock className="w-3.5 h-3.5" /><span>Last updated: Just now</span></div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((metric, index) => <MetricCard key={metric.label} metric={metric} delay={index * 100} isLive={isConnected && metric.label === 'Orders Today'} />)}
      </div>

      <RecentActions limit={5} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2"><Brain className="w-5 h-5 text-accent" /><h2 className="text-lg font-medium text-primary">Ospra Recommendations</h2>{productsLoading && <Loader2 className="w-4 h-4 text-tertiary animate-spin" />}</div>
            <button className="btn-ghost text-sm">View All<ChevronRight className="w-4 h-4" /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {recommendations.length > 0 ? recommendations.map((product, index) => <ProductRecommendationCard key={product.id} product={product} index={index} />) : <div className="sm:col-span-2 glass-card p-12 text-center"><Package className="w-12 h-12 mx-auto text-tertiary mb-4" /><h3 className="font-medium text-primary">No Recommendations Yet</h3><p className="text-sm text-secondary mt-1">Run product discovery to get AI-powered recommendations.</p></div>}
          </div>
        </div>

        <div className="space-y-6">
          <EmailOverview delay={400} />
          <div className="glass-card-static p-5">
            <div className="flex items-center gap-2 mb-4"><Sparkles className="w-5 h-5 text-accent-secondary" /><h3 className="text-sm font-medium text-primary">Ospra Insights</h3>{metricsLoading && <Loader2 className="w-3 h-3 text-tertiary animate-spin" />}</div>
            <div className="space-y-3">
              {insights.map((insight) => <AIInsightCard key={insight.id} insight={insight} />)}
            </div>
          </div>
          <SystemStatusPanel systems={systems} isLoading={healthLoading} />
          <QuickActionsPanel />
        </div>
      </div>

      {productPerformance.length > 0 && <ProductPerformanceTable products={productPerformance} />}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"><AIWeeklyBriefing data={{}} /><RevenueProjections projections={projections} /></div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"><ChannelBreakdown channels={channels} /><GeographicDistribution locations={geoData} /></div>
    </div>
  );
}
