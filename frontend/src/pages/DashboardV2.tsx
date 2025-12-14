/**
 * Premium Dashboard V2 - Using TanStack Query + Zustand
 */
import { Card, Title, AreaChart, DonutChart, BarChart, Grid, Metric, Text } from '@tremor/react';
import { TrendingUp, Package, DollarSign, ShoppingCart } from 'lucide-react';
import { useAnalyticsOverview, usePortfolioRankings } from '../hooks/queries/useAnalytics';
import { useProducts } from '../hooks/queries/useProducts';
import { useSystemHealth } from '../hooks/queries/useHealth';
import { useAppStore } from '../stores/appStore';

export default function DashboardV2() {
  const { data: overview, isLoading: overviewLoading } = useAnalyticsOverview();
  const { data: rankings, isLoading: rankingsLoading } = usePortfolioRankings();
  const { data: products, isLoading: productsLoading } = useProducts({ limit: 5 });
  const { data: health } = useSystemHealth();
  const { user, theme } = useAppStore();

  if (overviewLoading || rankingsLoading || productsLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
        </div>
      </div>
    );
  }

  // Mock data for charts (replace with real data)
  const revenueData = [
    { date: 'Jan', revenue: 2400 },
    { date: 'Feb', revenue: 1398 },
    { date: 'Mar', revenue: 9800 },
    { date: 'Apr', revenue: 3908 },
    { date: 'May', revenue: 4800 },
    { date: 'Jun', revenue: 3800 },
  ];

  const nicheData = [
    { niche: 'Smart Home', sales: 456 },
    { niche: 'Fitness', sales: 351 },
    { niche: 'Beauty', sales: 271 },
    { niche: 'Pet', sales: 191 },
    { niche: 'Kitchen', sales: 91 },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-primary">Welcome back, {user?.name}!</h1>
        <p className="text-secondary mt-1">
          Here's what's happening with your stores today
        </p>
      </div>

      {/* Stats Grid */}
      <Grid numItemsMd={2} numItemsLg={4} className="gap-6">
        <Card decoration="top" decorationColor="blue">
          <div className="flex items-center space-x-2">
            <DollarSign className="h-5 w-5 text-blue-500" />
            <Text>Total Revenue</Text>
          </div>
          <Metric>${overview?.total_revenue || '0'}</Metric>
          <div className="mt-2 flex items-center space-x-2">
            <TrendingUp className="h-4 w-4 text-green-500" />
            <Text className="text-green-500">+12.5% from last month</Text>
          </div>
        </Card>

        <Card decoration="top" decorationColor="green">
          <div className="flex items-center space-x-2">
            <Package className="h-5 w-5 text-green-500" />
            <Text>Total Products</Text>
          </div>
          <Metric>{overview?.total_products || 0}</Metric>
          <Text className="mt-2 text-secondary">Across all stores</Text>
        </Card>

        <Card decoration="top" decorationColor="purple">
          <div className="flex items-center space-x-2">
            <ShoppingCart className="h-5 w-5 text-purple-500" />
            <Text>Orders This Month</Text>
          </div>
          <Metric>{overview?.orders_count || 0}</Metric>
          <Text className="mt-2 text-secondary">+8 from yesterday</Text>
        </Card>

        <Card decoration="top" decorationColor="amber">
          <div className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-amber-500" />
            <Text>Conversion Rate</Text>
          </div>
          <Metric>{overview?.conversion_rate || '2.4'}%</Metric>
          <Text className="mt-2 text-secondary">Industry avg: 1.8%</Text>
        </Card>
      </Grid>

      {/* Charts Row */}
      <Grid numItemsMd={2} numItemsLg={2} className="gap-6">
        <Card>
          <Title>Revenue Over Time</Title>
          <AreaChart
            className="mt-4 h-72"
            data={revenueData}
            index="date"
            categories={["revenue"]}
            colors={["blue"]}
            valueFormatter={(value) => `$${value.toLocaleString()}`}
            showLegend={false}
            showGridLines={true}
          />
        </Card>

        <Card>
          <Title>Sales by Niche</Title>
          <DonutChart
            className="mt-4 h-72"
            data={nicheData}
            category="sales"
            index="niche"
            colors={["blue", "cyan", "indigo", "violet", "fuchsia"]}
            valueFormatter={(value) => `${value} sales`}
          />
        </Card>
      </Grid>

      {/* Top Products */}
      <Card>
        <Title>Top Performing Products</Title>
        <div className="mt-4 space-y-4">
          {products?.products?.slice(0, 5).map((product: any, index: number) => (
            <div
              key={product.id || index}
              className="flex items-center justify-between p-4 rounded-lg border border-white/10 dark:border-gray-700"
            >
              <div className="flex items-center space-x-4">
                {product.image && (
                  <img
                    src={product.image}
                    alt={product.name}
                    className="w-12 h-12 rounded object-cover"
                  />
                )}
                <div>
                  <p className="font-medium text-primary">{product.name || 'Product'}</p>
                  <p className="text-sm text-secondary">{product.niche || 'General'}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-semibold text-primary">
                  ${product.price || '0.00'}
                </p>
                <p className="text-sm text-green-500">
                  {product.sales || 0} sales
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* System Health (if available) */}
      {health && (
        <Card>
          <Title>System Status</Title>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(health.services || {}).map(([service, status]: [string, any]) => (
              <div key={service} className="flex items-center space-x-2">
                <div className={`h-3 w-3 rounded-full ${
                  status.status === 'CONNECTED' ? 'bg-green-500/100' : 'bg-gray-400'
                }`} />
                <Text>{service}</Text>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
