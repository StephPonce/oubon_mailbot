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
  TrendingUpIcon,
  Play,
  Pause,
  ArrowRight
} from 'lucide-react';

// Import premium stack hooks
import { useAnalyticsOverview, usePortfolioRankings } from '../hooks/queries/useAnalytics';
import { useProducts } from '../hooks/queries/useProducts';
import { useSystemHealth } from '../hooks/queries/useHealth';
import { useSocket } from '../hooks/useSocket';
import { useAppStore } from '../stores/appStore';
import { RevenueChart, TrendSparkline } from '../components/charts';
import { EmailOverview } from '../components/dashboard/EmailOverview';
import { ExplainTooltip } from '../components/ui/ExplainTooltip';
import { RecentActions } from '../components/RecentActions';

// Types
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

// Metric Card Component - CLEAN WHITE GLASS
function MetricCard({ metric, delay, isLive }: { metric: MetricData; delay: number; isLive?: boolean }) {
  return (
    <div 
      className="glass-card p-5 animate-fadeIn"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`stat-card-icon ${metric.iconColor}`}>
          <metric.icon className="w-5 h-5" />
        </div>
        <div className="flex items-center gap-2">
          {isLive && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[10px] text-green-600 font-medium">LIVE</span>
            </div>
          )}
          <div className={`metric-change ${metric.change >= 0 ? 'positive' : 'negative'}`}>
            {metric.change >= 0 ? (
              <ArrowUpRight className="w-4 h-4" />
            ) : (
              <ArrowDownRight className="w-4 h-4" />
            )}
            <span>{Math.abs(metric.change)}%</span>
          </div>
        </div>
      </div>
      <div className="metric-value">{metric.value}</div>
      <div className="metric-label">{metric.label}</div>
      <div className="text-xs text-tertiary mt-1">{metric.changeLabel}</div>
    </div>
  );
}

// Product Recommendation Card - WHITE GLASS
function ProductRecommendationCard({ product, index }: { product: ProductRecommendation; index: number }) {
  const getScoreColor = (score: number) => {
    if (score >= 8) return 'bg-green-500';
    if (score >= 6) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div 
      className="product-card animate-fadeIn"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Image Section */}
      <div className="relative">
        <div className="w-full h-44 bg-gradient-to-br from-black/5 to-black/0 flex items-center justify-center">
          {product.image ? (
            <img 
              src={product.image} 
              alt={product.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <Package className="w-12 h-12 text-tertiary" />
          )}
        </div>
        
        {/* Score Badge */}
        <div className={`product-score ${getScoreColor(product.score || 0)}`}>
          {(product.score || 0).toFixed(1)}
        </div>

        {/* Trend Indicator */}
        <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/80 backdrop-blur-sm border border-black/5">
          {product.trend === 'up' ? (
            <TrendingUp className="w-3.5 h-3.5 text-green-600" />
          ) : product.trend === 'down' ? (
            <TrendingDown className="w-3.5 h-3.5 text-red-500" />
          ) : (
            <Activity className="w-3.5 h-3.5 text-tertiary" />
          )}
          <span className={`text-xs font-medium ${
            product.trend === 'up' ? 'text-green-600' : 
            product.trend === 'down' ? 'text-red-500' : 'text-tertiary'
          }`}>
            {product.trendValue}
          </span>
        </div>
      </div>

      {/* Content Section */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="text-sm font-medium text-primary line-clamp-2 leading-tight">
            {product.name}
          </h3>
        </div>

        <div className="flex items-center gap-2 mb-3">
          <span className="badge badge-blue">{product.niche}</span>
          <span className="text-xs text-tertiary">{product.source}</span>
        </div>

        {/* Sparkline */}
        {product.sparklineData && (
          <div className="h-8 mb-3">
            <TrendSparkline data={product.sparklineData} color="auto" />
          </div>
        )}

        {/* AI Reason with Explain Tooltip */}
        <div className="p-2.5 rounded-lg bg-blue-500/8 border border-blue-500/15 mb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2 flex-1">
              <Brain className="w-3.5 h-3.5 text-blue-600 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-secondary leading-relaxed line-clamp-2">
                {product.reason}
              </p>
            </div>
            <ExplainTooltip
              rationale={product.reason || "AI-powered recommendation based on market data"}
              confidence={Math.round((product.score || 0) * 10)}
              factors={[
                { label: "Market demand", value: 12, icon: "trend" },
                { label: "Profit potential", value: 15, icon: "success" },
              ]}
              position="bottom"
            />
          </div>
        </div>

        {/* Stats Row */}
        <div className="flex items-center justify-between pt-3 border-t border-black/5">
          <div>
            <div className="text-xs text-tertiary">Est. Profit</div>
            <div className="text-sm font-semibold text-green-600">{product.profit}</div>
          </div>
          <button className="btn-ghost text-xs">
            <span>Analyze</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

// AI Insight Card
function AIInsightCard({ insight }: { insight: AIInsight }) {
  const typeConfig = {
    opportunity: {
      icon: Sparkles,
      color: 'text-blue-600',
      bg: 'bg-blue-500/8',
      border: 'border-blue-500/15',
    },
    warning: {
      icon: AlertCircle,
      color: 'text-amber-600',
      bg: 'bg-amber-500/8',
      border: 'border-amber-500/15',
    },
    success: {
      icon: CheckCircle2,
      color: 'text-green-600',
      bg: 'bg-green-500/8',
      border: 'border-green-500/15',
    },
  };

  const config = typeConfig[insight.type];
  const Icon = config.icon;

  return (
    <div className={`p-4 rounded-xl ${config.bg} border ${config.border}`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg bg-white/50 ${config.color}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-primary mb-1">{insight.title}</h4>
          <p className="text-xs text-secondary leading-relaxed">{insight.description}</p>
          {insight.action && (
            <button className="mt-2 text-xs font-medium text-accent hover:text-accent-hover flex items-center gap-1">
              {insight.action}
              <ExternalLink className="w-3 h-3" />
            </button>
          )}
        </div>
        <span className="text-[10px] text-tertiary flex-shrink-0">{insight.timestamp}</span>
      </div>
    </div>
  );
}

// System Status Component
function SystemStatusPanel({ systems, isLoading }: { systems: SystemStatus[]; isLoading: boolean }) {
  return (
    <div className="glass-card-static p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-primary">System Status</h3>
        <button className="p-1.5 rounded-lg hover:bg-black/5 text-tertiary">
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>
      <div className="space-y-3">
        {systems.map((system, index) => (
          <div key={index} className="flex items-center gap-3">
            <div className={`status-dot ${system.status}`} />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-primary">{system.name}</div>
              <div className="text-xs text-tertiary">{system.detail}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Quick Actions Component
function QuickActionsPanel() {
  const actions = [
    { icon: Brain, label: 'Ask Ospra for Recommendations', iconColor: 'blue' },
    { icon: Package, label: 'Deploy Product to Shopify', iconColor: 'green' },
    { icon: Target, label: 'Run Niche Analysis', iconColor: 'purple' },
    { icon: BarChart3, label: 'Generate Report', iconColor: 'cyan' },
  ];

  return (
    <div className="glass-card-static p-5">
      <h3 className="text-sm font-medium text-primary mb-4">Quick Actions</h3>
      <div className="space-y-2">
        {actions.map((action, index) => (
          <button
            key={index}
            className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/30 hover:bg-white/50 border border-black/5 hover:border-black/10 transition-all text-left"
          >
            <div className={`stat-card-icon ${action.iconColor}`}>
              <action.icon className="w-4 h-4" />
            </div>
            <span className="text-sm text-primary">{action.label}</span>
            <ChevronRight className="w-4 h-4 text-tertiary ml-auto" />
          </button>
        ))}
      </div>
    </div>
  );
}

// Product Performance Table
function ProductPerformanceTable({ products }: { products: ProductPerformance[] }) {
  const getStatusColor = (status: string) => {
    if (status === 'active') return 'bg-green-500/10 text-green-600 border-green-500/20';
    if (status === 'paused') return 'bg-amber-500/10 text-amber-600 border-amber-500/20';
    return 'bg-red-500/10 text-red-600 border-red-500/20';
  };

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-accent" />
          <h2 className="text-lg font-medium text-primary">Product Performance</h2>
        </div>
        <button className="btn-ghost text-sm">
          Export
          <Download className="w-4 h-4" />
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-black/10">
              <th className="text-left py-3 px-4 text-sm font-medium text-secondary">Product</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-secondary">Revenue</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-secondary">Units Sold</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-secondary">Profit</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-secondary">ROAS</th>
              <th className="text-center py-3 px-4 text-sm font-medium text-secondary">Status</th>
              <th className="text-center py-3 px-4 text-sm font-medium text-secondary">Actions</th>
            </tr>
          </thead>
          <tbody>
            {products.map((product) => (
              <tr key={product.id} className="border-b border-black/5 hover:bg-black/5 transition-colors">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-3">
                    {product.image && (
                      <img src={product.image} alt={product.name} className="w-10 h-10 rounded-lg object-cover" />
                    )}
                    <div>
                      <div className="text-sm font-medium text-primary">{product.name}</div>
                      <div className="text-xs text-tertiary">{product.niche}</div>
                    </div>
                  </div>
                </td>
                <td className="text-right py-3 px-4 text-sm font-medium text-primary">${product.revenue.toLocaleString()}</td>
                <td className="text-right py-3 px-4 text-sm text-secondary">{product.units_sold}</td>
                <td className="text-right py-3 px-4 text-sm font-medium text-green-600">${product.profit.toLocaleString()}</td>
                <td className="text-right py-3 px-4 text-sm font-medium text-primary">{product.roas.toFixed(2)}x</td>
                <td className="text-center py-3 px-4">
                  <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${getStatusColor(product.status)}`}>
                    {product.status}
                  </span>
                </td>
                <td className="text-center py-3 px-4">
                  <div className="flex items-center justify-center gap-2">
                    <button className="p-1.5 rounded-lg hover:bg-black/10 text-tertiary">
                      <Play className="w-4 h-4" />
                    </button>
                    <button className="p-1.5 rounded-lg hover:bg-black/10 text-tertiary">
                      <Pause className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// AI Weekly Briefing
function AIWeeklyBriefing({ data }: { data: any }) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-purple-600" />
          <h2 className="text-lg font-medium text-primary">Ospra's Weekly Briefing</h2>
        </div>
        <button className="btn-primary text-sm">
          Generate PDF
          <Download className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-4">
        <div className="p-4 rounded-xl bg-blue-500/8 border border-blue-500/15">
          <div className="flex items-start gap-3 mb-3">
            <Brain className="w-5 h-5 text-blue-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-sm font-medium text-primary mb-2">Key Insights This Week</h3>
              <ul className="space-y-2 text-sm text-secondary">
                <li className="flex items-start gap-2">
                  <ArrowRight className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                  <span>Revenue is up 23% this week, driven by LED strip sales in smart home niche</span>
                </li>
                <li className="flex items-start gap-2">
                  <ArrowRight className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                  <span>Kitchen gadgets niche showing declining engagement - consider pausing ad spend</span>
                </li>
                <li className="flex items-start gap-2">
                  <ArrowRight className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                  <span>3 products need restocking within 7 days to avoid stockouts</span>
                </li>
                <li className="flex items-start gap-2">
                  <ArrowRight className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <span>New competitor detected in fitness accessories - monitor pricing</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-green-500/8 border border-green-500/15">
          <h3 className="text-sm font-medium text-primary mb-2 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            Recommended Actions
          </h3>
          <div className="space-y-2 text-sm text-secondary">
            <div className="flex items-center justify-between p-2 rounded-lg hover:bg-white/30">
              <span>Launch Meta ad campaign for LED strips</span>
              <button className="text-xs text-accent hover:text-accent-hover font-medium">Start Campaign</button>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg hover:bg-white/30">
              <span>Reorder inventory for top 3 products</span>
              <button className="text-xs text-accent hover:text-accent-hover font-medium">View Products</button>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg hover:bg-white/30">
              <span>Review kitchen niche profitability</span>
              <button className="text-xs text-accent hover:text-accent-hover font-medium">Open Analysis</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Revenue Projections
function RevenueProjections({ projections }: { projections: ProjectionData[] }) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-green-600" />
          <h2 className="text-lg font-medium text-primary">Revenue Projections</h2>
        </div>
        <div className="text-xs text-tertiary">Based on current trends & seasonality</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {projections.map((proj, index) => (
          <div key={index} className="p-4 rounded-xl bg-gradient-to-br from-green-500/10 to-blue-500/10 border border-green-500/20">
            <div className="text-xs text-tertiary mb-1">{proj.period}</div>
            <div className="text-2xl font-semibold text-primary mb-2">${proj.value.toLocaleString()}</div>
            <div className="text-xs text-secondary">
              Range: ${proj.confidence_low.toLocaleString()} - ${proj.confidence_high.toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 rounded-xl bg-purple-500/8 border border-purple-500/15">
        <div className="flex items-start gap-3">
          <Brain className="w-5 h-5 text-purple-600 mt-0.5" />
          <div className="flex-1 text-sm text-secondary">
            <p className="mb-2">
              <span className="font-medium text-primary">Projection Assumptions:</span>
            </p>
            <ul className="space-y-1">
              <li>• Current conversion rate of 2.3% maintained</li>
              <li>• Seasonal uptick expected in Q4 (+15%)</li>
              <li>• Ad spend efficiency improving by 5% month-over-month</li>
              <li>• New product launches contributing $2-3K monthly</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

// Channel Breakdown
function ChannelBreakdown({ channels }: { channels: ChannelData[] }) {
  const total = channels.reduce((sum, ch) => sum + ch.revenue, 0);

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <PieChart className="w-5 h-5 text-cyan-600" />
          <h2 className="text-lg font-medium text-primary">Revenue by Channel</h2>
        </div>
        <div className="text-sm text-secondary">Total: ${total.toLocaleString()}</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Pie Chart Visualization */}
        <div className="flex items-center justify-center">
          <div className="relative w-48 h-48">
            {channels.map((channel, index) => {
              const startAngle = channels.slice(0, index).reduce((sum, ch) => sum + ch.percentage * 3.6, 0);
              const endAngle = startAngle + (channel.percentage * 3.6);

              return (
                <div
                  key={channel.name}
                  className="absolute inset-0 rounded-full"
                  style={{
                    background: `conic-gradient(${channel.color} ${startAngle}deg, ${channel.color} ${endAngle}deg, transparent ${endAngle}deg)`,
                  }}
                />
              );
            })}
            <div className="absolute inset-8 rounded-full bg-white flex items-center justify-center">
              <div className="text-center">
                <div className="text-2xl font-semibold text-primary">{channels.length}</div>
                <div className="text-xs text-tertiary">Channels</div>
              </div>
            </div>
          </div>
        </div>

        {/* Channel Details */}
        <div className="space-y-3">
          {channels.map((channel) => (
            <div key={channel.name} className="p-4 rounded-xl border border-black/10 hover:border-black/20 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: channel.color }} />
                  <span className="text-sm font-medium text-primary">{channel.name}</span>
                </div>
                <span className="text-sm font-semibold text-primary">${channel.revenue.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-secondary">
                <span>{channel.percentage.toFixed(1)}% of total</span>
                <span className="text-green-600 font-medium">{channel.roi.toFixed(2)}x ROI</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Geographic Distribution
function GeographicDistribution({ locations }: { locations: GeographicData[] }) {
  const total = locations.reduce((sum, loc) => sum + loc.revenue, 0);

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-medium text-primary">Top Markets</h2>
        </div>
      </div>

      <div className="space-y-3">
        {locations.map((location, index) => {
          const percentage = (location.revenue / total) * 100;

          return (
            <div key={location.country} className="p-4 rounded-xl border border-black/10">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                    <MapPin className="w-4 h-4 text-blue-600" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-primary">{location.country}</div>
                    <div className="text-xs text-tertiary">{location.customers} customers • {location.orders} orders</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-primary">${location.revenue.toLocaleString()}</div>
                  <div className="text-xs text-secondary">{percentage.toFixed(1)}%</div>
                </div>
              </div>
              <div className="w-full h-2 bg-black/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full"
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Loading Skeleton
function DashboardSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 skeleton" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-96 skeleton" />
        <div className="h-96 skeleton" />
      </div>
    </div>
  );
}

// Main Dashboard Component
export default function PortfolioDashboard() {
  // Premium Stack Hooks - TanStack Query
  const { data: dashboardData, isLoading: metricsLoading, refetch: refetchMetrics } = useAnalyticsOverview();
  const { data: rankingsData, isLoading: rankingsLoading } = usePortfolioRankings();
  const { data: productsData, isLoading: productsLoading } = useProducts({ limit: 4 });
  const { data: healthData, isLoading: healthLoading } = useSystemHealth();
  const { user } = useAppStore();

  // Real-time data with Socket.io
  const { socket, isConnected } = useSocket();

  // Fallback data for demo
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [recommendations, setRecommendations] = useState<ProductRecommendation[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [systems, setSystems] = useState<SystemStatus[]>([]);

  // New sections data
  const [productPerformance] = useState<ProductPerformance[]>([
    { id: '1', name: 'LED Strip Lights 16ft', revenue: 4850, units_sold: 97, profit: 1940, roas: 4.2, status: 'active', niche: 'Smart Home' },
    { id: '2', name: 'Wireless Phone Charger', revenue: 3200, units_sold: 128, profit: 1120, roas: 3.5, status: 'active', niche: 'Tech Accessories' },
    { id: '3', name: 'Portable Blender', revenue: 2750, units_sold: 55, profit: 1375, roas: 5.0, status: 'active', niche: 'Kitchen' },
    { id: '4', name: 'Yoga Mat Premium', revenue: 1890, units_sold: 63, profit: 756, roas: 2.1, status: 'low-stock', niche: 'Fitness' },
    { id: '5', name: 'Pet Water Fountain', revenue: 1450, units_sold: 29, profit: 580, roas: 1.8, status: 'paused', niche: 'Pet Supplies' },
  ]);

  const [projections] = useState<ProjectionData[]>([
    { period: 'Next 7 Days', value: 12500, confidence_low: 10800, confidence_high: 14200 },
    { period: 'Next 30 Days', value: 48000, confidence_low: 42000, confidence_high: 54000 },
    { period: 'Next 90 Days', value: 152000, confidence_low: 135000, confidence_high: 170000 },
  ]);

  const [channels] = useState<ChannelData[]>([
    { name: 'Organic Search', revenue: 5200, percentage: 36.6, roi: 8.5, color: '#10b981' },
    { name: 'Meta Ads', revenue: 4100, percentage: 28.9, roi: 4.2, color: '#3b82f6' },
    { name: 'TikTok Ads', revenue: 3200, percentage: 22.5, roi: 3.8, color: '#a855f7' },
    { name: 'Email Marketing', revenue: 1700, percentage: 12.0, roi: 12.1, color: '#f59e0b' },
  ]);

  const [geoData] = useState<GeographicData[]>([
    { country: 'United States', revenue: 8500, customers: 245, orders: 387 },
    { country: 'United Kingdom', revenue: 3200, customers: 98, orders: 156 },
    { country: 'Canada', revenue: 2100, customers: 67, orders: 94 },
    { country: 'Australia', revenue: 1350, customers: 42, orders: 58 },
    { country: 'Germany', revenue: 990, customers: 28, orders: 41 },
  ]);

  // Transform API data from TanStack Query
  useEffect(() => {
    const revenue = dashboardData?.total_revenue || 0;
    const activeProducts = dashboardData?.total_products || 0;
    const conversionRate = dashboardData?.conversion_rate || 0;
    const ordersToday = dashboardData?.orders_count || 0;

    setMetrics([
      {
        label: 'Total Revenue',
        value: `$${revenue.toLocaleString()}`,
        change: dashboardData?.revenue_change || 12.5,
        changeLabel: 'vs last month',
        icon: DollarSign,
        iconColor: 'green',
      },
      {
        label: 'Active Products',
        value: String(activeProducts),
        change: dashboardData?.products_change || 8,
        changeLabel: activeProducts > 0 ? '5 new this week' : 'No products yet',
        icon: Package,
        iconColor: 'blue',
      },
      {
        label: 'Conversion Rate',
        value: `${conversionRate}%`,
        change: dashboardData?.conversion_change || 5.2,
        changeLabel: 'vs last week',
        icon: Target,
        iconColor: 'purple',
      },
      {
        label: 'Orders Today',
        value: String(ordersToday),
        change: dashboardData?.orders_change || 3,
        changeLabel: 'vs yesterday',
        icon: ShoppingCart,
        iconColor: 'cyan',
      },
    ]);
  }, [dashboardData]);

  useEffect(() => {
    if (productsData?.products) {
      setRecommendations(productsData.products.slice(0, 4).map((p: any) => ({
        id: p.id || p.product_id,
        name: p.name || p.title || 'Product',
        image: p.image_url || p.image || '',
        score: p.score || p.velocity_score || 0,
        profit: `$${p.estimated_profit?.toFixed(2) || p.profit_margin?.toFixed(2) || '0.00'}`,
        trend: p.trend || 'stable',
        trendValue: p.trend_value || '+0%',
        source: p.source || 'AliExpress',
        niche: p.niche || 'General',
        reason: p.ai_reason || 'High demand product with strong growth potential',
        sparklineData: p.trend_data?.map((v: number) => ({ value: v })),
      })));
    } else {
      // No data from API - show empty array
      setRecommendations([]);
    }
  }, [productsData]);

  // AI Insights - will be populated when insights endpoint is available
  useEffect(() => {
    // For now, show sample insights based on real data
    if (dashboardData) {
      const sampleInsights: AIInsight[] = [
        {
          id: '1',
          type: 'opportunity',
          title: 'Revenue Growth Opportunity',
          description: `Your revenue is ${dashboardData.total_revenue > 0 ? 'trending upward' : 'ready to launch'}. Consider expanding your product catalog.`,
          action: 'View Products',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ];
      if (dashboardData.total_products === 0) {
        sampleInsights.push({
          id: '2',
          type: 'warning',
          title: 'No Active Products',
          description: 'Start by discovering and deploying products to your store.',
          action: 'Discover Products',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        });
      }
      setInsights(sampleInsights);
    }
  }, [dashboardData]);

  useEffect(() => {
    if (healthData?.services) {
      const servicesList = Object.entries(healthData.services).map(([key, value]: [string, any]) => ({
        name: key,
        status: value.status === 'CONNECTED' ? 'online' : 'offline',
        detail: value.detail || value.message || 'Connected',
      }));
      setSystems(servicesList.slice(0, 5));
    } else if (healthData?.status) {
      // Fallback to simple status
      setSystems([{
        name: 'System',
        status: healthData.status === 'healthy' ? 'online' : 'warning',
        detail: healthData.message || 'Operational',
      }]);
    }
  }, [healthData]);

  const isLoading = metricsLoading && productsLoading && !metrics.length;

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary mb-1">Command Center</h1>
          <p className="text-sm text-secondary">
            Welcome back. Ospra has found {recommendations.length} new opportunities for you today.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isConnected && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-500/10 border border-green-500/20">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs text-green-600 font-medium">Live Data</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs text-tertiary">
            <Clock className="w-3.5 h-3.5" />
            <span>Last updated: Just now</span>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((metric, index) => (
          <MetricCard
            key={metric.label}
            metric={metric}
            delay={index * 100}
            isLive={isConnected && metric.label === 'Orders Today'}
          />
        ))}
      </div>

      {/* Recent Actions - Undo Support */}
      <RecentActions limit={5} />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Product Recommendations */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-accent" />
              <h2 className="text-lg font-medium text-primary">Ospra Recommendations</h2>
              {productsLoading && <Loader2 className="w-4 h-4 text-tertiary animate-spin" />}
            </div>
            <button className="btn-ghost text-sm">
              View All
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {recommendations.map((product, index) => (
              <ProductRecommendationCard 
                key={product.id} 
                product={product} 
                index={index}
              />
            ))}
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          {/* Email Automation Overview */}
          <EmailOverview delay={400} />

          {/* AI Insights */}
          <div className="glass-card-static p-5">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-purple-600" />
              <h3 className="text-sm font-medium text-primary">Ospra Insights</h3>
              {metricsLoading && <Loader2 className="w-3 h-3 text-tertiary animate-spin" />}
            </div>
            <div className="space-y-3">
              {insights.map((insight) => (
                <AIInsightCard key={insight.id} insight={insight} />
              ))}
            </div>
          </div>

          {/* System Status */}
          <SystemStatusPanel systems={systems} isLoading={healthLoading} />

          {/* Quick Actions */}
          <QuickActionsPanel />
        </div>
      </div>

      {/* Product Performance Table */}
      {productPerformance.length > 0 && (
        <ProductPerformanceTable products={productPerformance} />
      )}

      {/* AI Weekly Briefing & Revenue Projections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AIWeeklyBriefing data={{}} />
        <RevenueProjections projections={projections} />
      </div>

      {/* Channel Breakdown & Geographic Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChannelBreakdown channels={channels} />
        <GeographicDistribution locations={geoData} />
      </div>
    </div>
  );
}
