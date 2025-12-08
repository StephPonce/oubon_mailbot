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
  Loader2
} from 'lucide-react';

// Import hooks and charts
import { 
  useDashboardMetrics, 
  useProductRecommendations, 
  useOiInsights,
  useSystemHealth
} from '../hooks/useData';
import { useRealtimeAnalytics } from '../services/websocket';
import { RevenueChart, TrendSparkline } from '../components/charts';

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

        {/* AI Reason */}
        <div className="p-2.5 rounded-lg bg-blue-500/8 border border-blue-500/15 mb-3">
          <div className="flex items-start gap-2">
            <Brain className="w-3.5 h-3.5 text-blue-600 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-secondary leading-relaxed line-clamp-2">
              {product.reason}
            </p>
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
  // API Hooks
  const { data: dashboardData, isLoading: metricsLoading, refetch: refetchMetrics } = useDashboardMetrics();
  const { data: recommendationsData, isLoading: recommendationsLoading } = useProductRecommendations(4);
  const { data: insightsData, isLoading: insightsLoading } = useOiInsights();
  const { data: healthData, isLoading: healthLoading } = useSystemHealth();
  
  // Real-time data
  const { analytics: realtimeAnalytics, isConnected } = useRealtimeAnalytics();

  // Fallback data for demo
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [recommendations, setRecommendations] = useState<ProductRecommendation[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [systems, setSystems] = useState<SystemStatus[]>([]);

  // Transform API data - use real 0 values from database
  useEffect(() => {
    const revenue = dashboardData?.revenue || 0;
    const activeProducts = dashboardData?.active_products || 0;
    const conversionRate = dashboardData?.conversion_rate || 0;
    const ordersToday = realtimeAnalytics?.ordersToday || dashboardData?.orders_today || 0;

    setMetrics([
      {
        label: 'Total Revenue',
        value: `$${revenue.toLocaleString()}`,
        change: dashboardData?.revenue_change || 0,
        changeLabel: 'vs last month',
        icon: DollarSign,
        iconColor: 'green',
      },
      {
        label: 'Active Products',
        value: String(activeProducts),
        change: dashboardData?.products_change || 0,
        changeLabel: activeProducts > 0 ? '5 new this week' : 'No products yet',
        icon: Package,
        iconColor: 'blue',
      },
      {
        label: 'Conversion Rate',
        value: `${conversionRate}%`,
        change: dashboardData?.conversion_change || 0,
        changeLabel: 'vs last week',
        icon: Target,
        iconColor: 'purple',
      },
      {
        label: 'Orders Today',
        value: String(ordersToday),
        change: dashboardData?.orders_change || 0,
        changeLabel: 'vs yesterday',
        icon: ShoppingCart,
        iconColor: 'cyan',
      },
    ]);
  }, [dashboardData, realtimeAnalytics]);

  useEffect(() => {
    if (recommendationsData?.products) {
      setRecommendations(recommendationsData.products.map((p: any) => ({
        id: p.id,
        name: p.name,
        image: p.image_url || '',
        score: p.score,
        profit: `$${p.profit_margin?.toFixed(2) || '0.00'}`,
        trend: p.trend,
        trendValue: p.trend_value,
        source: p.source,
        niche: p.niche,
        reason: p.ai_reason,
        sparklineData: p.trend_data?.map((v: number) => ({ value: v })),
      })));
    } else {
      // No data from API - show empty array
      setRecommendations([]);
    }
  }, [recommendationsData]);

  useEffect(() => {
    if (insightsData?.insights) {
      setInsights(insightsData.insights.slice(0, 3).map((i: any) => ({
        id: i.id,
        type: i.type,
        title: i.title,
        description: i.description,
        action: i.action_label,
        timestamp: new Date(i.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      })));
    } else {
      // No data from API - show empty array
      setInsights([]);
    }
  }, [insightsData]);

  useEffect(() => {
    if (healthData?.services) {
      setSystems(healthData.services.slice(0, 5).map((s: any) => ({
        name: s.name,
        status: s.status,
        detail: s.detail || `Last check ${s.last_check}`,
      })));
    } else {
      // No data from API - show empty array
      setSystems([]);
    }
  }, [healthData]);

  const isLoading = metricsLoading && recommendationsLoading && !metrics.length;

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

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Product Recommendations */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-accent" />
              <h2 className="text-lg font-medium text-primary">Ospra Recommendations</h2>
              {recommendationsLoading && <Loader2 className="w-4 h-4 text-tertiary animate-spin" />}
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
          {/* AI Insights */}
          <div className="glass-card-static p-5">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-purple-600" />
              <h3 className="text-sm font-medium text-primary">Ospra Insights</h3>
              {insightsLoading && <Loader2 className="w-3 h-3 text-tertiary animate-spin" />}
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
    </div>
  );
}
