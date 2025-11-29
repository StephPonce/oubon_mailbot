import React, { useEffect, useState } from 'react';
import { GlassPanel } from '@/components/GlassPanel';
import { Trophy, Medal, RefreshCw, ChevronRight, X, TrendingUp } from 'lucide-react';
import axios from 'axios';
import StoreRankingsTable from '../components/portfolio/StoreRankingsTable';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface PortfolioData {
  monthlyRevenue: number;
  totalOrders: number;
  activeStores: number;
  totalStores: number;
  activeProducts: number;
  totalProducts: number;
  totalRevenue: number;
  avgConversion: number;
}

interface StoreRanking {
  id: number;
  store_name: string;
  platform: string;
  monthly_revenue: number;
  total_revenue: number;
  conversion_rate: number;
  product_count: number;
  active_products: number;
  rank_position: number;
  rank_change: number;
  rank_change_label: string;
}

interface RevenueDataPoint {
  date: string;
  revenue: number;
}

export default function PortfolioDashboard() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [rankings, setRankings] = useState<StoreRanking[]>([]);
  const [loadingRankings, setLoadingRankings] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [revenueTrends, setRevenueTrends] = useState<RevenueDataPoint[]>([]);

  const fetchRankings = async () => {
    setLoadingRankings(true);
    try {
      const response = await axios.get('http://localhost:8001/api/portfolio/rankings');
      setRankings(response.data);
    } catch (err) {
      console.error('Failed to fetch rankings:', err);
    } finally {
      setLoadingRankings(false);
    }
  };

  useEffect(() => {
    fetchRankings();
  }, []);

  useEffect(() => {
    axios.get('http://localhost:8001/api/portfolio/overview')
      .then(res => {
        // Map API response (snake_case) to frontend interface (camelCase)
        const apiData = res.data;

        setData({
          monthlyRevenue: apiData.monthly_revenue || 0,
          totalOrders: apiData.total_orders || 0,
          activeStores: apiData.active_stores || 0,
          totalStores: apiData.total_stores || 0,
          activeProducts: apiData.active_products || 0,
          totalProducts: apiData.total_products || 0,
          totalRevenue: apiData.total_revenue || 0,
          avgConversion: apiData.avg_conversion_rate || 0,
        });
      })
      .catch(err => {
        console.error('Failed to load portfolio data:', err);
        setError('Failed to load portfolio data');
      });
  }, []);

  // Fetch revenue trends
  useEffect(() => {
    axios.get('http://localhost:8001/api/dashboard/v2/analytics/business')
      .then(res => {
        const revenueByDay = res.data.revenue_by_day || [];
        // Transform the data for the chart
        const formattedData = revenueByDay.map((item: any) => ({
          date: item.date || item.day,
          revenue: item.revenue || item.total || 0
        }));
        setRevenueTrends(formattedData);
      })
      .catch(err => {
        console.error('Failed to load revenue trends:', err);
      });
  }, []);

  if (error) return <div className="h-screen flex items-center justify-center text-red-600">{error}</div>;
  if (!data) return (
    <div className="h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
    </div>
  );

  const topStore = rankings[0];
  const metrics = [
    {
      id: "revenue",
      label: "Monthly Revenue",
      value: `$${data.monthlyRevenue.toLocaleString()}`,
      subtitle: `$${data.totalRevenue.toLocaleString()} total`
    },
    {
      id: "orders",
      label: "Total Orders",
      value: data.totalOrders.toString(),
      subtitle: "All time"
    },
    {
      id: "stores",
      label: "Active Stores",
      value: data.activeStores.toString(),
      subtitle: `${data.totalStores} total`
    },
    {
      id: "products",
      label: "Active Products",
      value: data.activeProducts.toString(),
      subtitle: `${data.totalProducts} total`
    },
    {
      id: "conversion",
      label: "Avg. Conversion",
      value: `${data.avgConversion.toFixed(2)}%`,
      subtitle: "Portfolio average"
    },
  ];

  const Modal = ({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) => (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-4xl max-h-[80vh] overflow-y-auto rounded-2xl border shadow-2xl"
        style={{
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(24px)',
          borderColor: 'rgba(0, 0, 0, 0.1)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.2)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-6 border-b border-gray-200/50">
          <h2 className="text-2xl font-light text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-200/50 transition-colors"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );

  const renderModalContent = () => {
    if (!selectedMetric) return null;

    switch (selectedMetric) {
      case 'revenue':
        return (
          <Modal title="Revenue Breakdown" onClose={() => setSelectedMetric(null)}>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="text-center">
                  <div className="text-3xl font-light text-gray-900 mb-2">
                    ${data.monthlyRevenue.toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-600 font-light">Monthly Revenue</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-light text-green-600 mb-2">
                    ${data.totalRevenue.toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-600 font-light">Total Revenue</div>
                </div>
              </div>

              {rankings.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-light text-gray-900 mb-4">Revenue by Store</h3>
                  <div className="space-y-3">
                    {rankings.map((store) => (
                      <div
                        key={store.id}
                        className="rounded-xl p-4 border bg-white/50"
                        style={{ borderColor: 'rgba(0, 0, 0, 0.1)' }}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-gray-900 font-light">{store.store_name}</div>
                            <div className="text-sm text-gray-500">{store.platform}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-gray-900 font-light">
                              ${store.monthly_revenue.toLocaleString()}
                            </div>
                            <div className="text-sm text-gray-500">
                              ${store.total_revenue.toLocaleString()} total
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Modal>
        );

      case 'orders':
        return (
          <Modal title="Order Details" onClose={() => setSelectedMetric(null)}>
            <div className="space-y-6">
              <div className="text-center">
                <div className="text-4xl font-light text-gray-900 mb-2">
                  {data.totalOrders.toLocaleString()}
                </div>
                <div className="text-sm text-gray-600 font-light">Total Orders (All Time)</div>
              </div>

              {rankings.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-light text-gray-900 mb-4">Orders by Store</h3>
                  <div className="space-y-3">
                    {rankings.map((store) => (
                      <div
                        key={store.id}
                        className="rounded-xl p-4 border bg-white/50"
                        style={{ borderColor: 'rgba(0, 0, 0, 0.1)' }}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-gray-900 font-light">{store.store_name}</div>
                            <div className="text-sm text-gray-500">{store.platform}</div>
                          </div>
                          <div className="text-gray-900 font-light">
                            View orders in OrdersPage
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Modal>
        );

      case 'stores':
        return (
          <Modal title="Store Details" onClose={() => setSelectedMetric(null)}>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="text-center">
                  <div className="text-3xl font-light text-green-600 mb-2">
                    {data.activeStores}
                  </div>
                  <div className="text-sm text-gray-600 font-light">Active Stores</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-light text-gray-900 mb-2">
                    {data.totalStores}
                  </div>
                  <div className="text-sm text-gray-600 font-light">Total Stores</div>
                </div>
              </div>

              {rankings.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-light text-gray-900 mb-4">All Stores</h3>
                  <div className="space-y-3">
                    {rankings.map((store) => (
                      <div
                        key={store.id}
                        className="rounded-xl p-4 border bg-white/50"
                        style={{ borderColor: 'rgba(0, 0, 0, 0.1)' }}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="text-gray-900 font-light text-lg">{store.store_name}</div>
                            <div className="text-sm text-gray-500 capitalize">{store.platform}</div>
                          </div>
                          <div className="text-yellow-600 font-light">
                            Rank #{store.rank_position}
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-4 text-sm font-light">
                          <div>
                            <span className="text-gray-600 block">Revenue</span>
                            <span className="text-gray-900">${store.monthly_revenue.toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="text-gray-600 block">Conversion</span>
                            <span className="text-gray-900">{store.conversion_rate.toFixed(2)}%</span>
                          </div>
                          <div>
                            <span className="text-gray-600 block">Products</span>
                            <span className="text-gray-900">{store.active_products}/{store.product_count}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Modal>
        );

      case 'products':
        return (
          <Modal title="Product Overview" onClose={() => setSelectedMetric(null)}>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="text-center">
                  <div className="text-3xl font-light text-green-600 mb-2">
                    {data.activeProducts}
                  </div>
                  <div className="text-sm text-gray-600 font-light">Active Products</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-light text-gray-900 mb-2">
                    {data.totalProducts}
                  </div>
                  <div className="text-sm text-gray-600 font-light">Total Products</div>
                </div>
              </div>

              {rankings.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-light text-gray-900 mb-4">Products by Store</h3>
                  <div className="space-y-3">
                    {rankings.map((store) => (
                      <div
                        key={store.id}
                        className="rounded-xl p-4 border bg-white/50"
                        style={{ borderColor: 'rgba(0, 0, 0, 0.1)' }}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-gray-900 font-light">{store.store_name}</div>
                            <div className="text-sm text-gray-500">{store.platform}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-gray-900 font-light">
                              {store.active_products} active
                            </div>
                            <div className="text-sm text-gray-500">
                              {store.product_count} total
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Modal>
        );

      case 'conversion':
        return (
          <Modal title="Conversion Rate Analysis" onClose={() => setSelectedMetric(null)}>
            <div className="space-y-6">
              <div className="text-center">
                <div className="text-4xl font-light text-blue-600 mb-2">
                  {data.avgConversion.toFixed(2)}%
                </div>
                <div className="text-sm text-gray-600 font-light">Portfolio Average Conversion Rate</div>
              </div>

              {rankings.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-light text-gray-900 mb-4">Conversion by Store</h3>
                  <div className="space-y-3">
                    {rankings.map((store) => (
                      <div
                        key={store.id}
                        className="rounded-xl p-4 border bg-white/50"
                        style={{ borderColor: 'rgba(0, 0, 0, 0.1)' }}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-gray-900 font-light">{store.store_name}</div>
                            <div className="text-sm text-gray-500">{store.platform}</div>
                          </div>
                          <div className="text-right">
                            <div className={`text-lg font-light ${
                              store.conversion_rate > data.avgConversion ? 'text-green-600' : 'text-gray-900'
                            }`}>
                              {store.conversion_rate.toFixed(2)}%
                            </div>
                            <div className="text-sm text-gray-500">
                              {store.conversion_rate > data.avgConversion ? 'Above avg' : 'Below avg'}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Modal>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-12">

        {/* Header */}
        <GlassPanel depth={80} delay={0.2}>
          <h1 className="text-title">Portfolio Dashboard</h1>
          <p className="text-subtitle mt-2">Monitor your stores, revenue, and performance</p>
        </GlassPanel>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
          {metrics.map((m, i) => (
            <GlassPanel key={i} depth={30 + i * 5} delay={0.3 + i * 0.05} className="p-0">
              <button
                onClick={() => setSelectedMetric(m.id)}
                className="w-full text-left p-6 transition-all hover:scale-[1.02] cursor-pointer group"
              >
                <div className="flex items-start justify-between mb-2">
                  <p className="text-metric-label">{m.label}</p>
                  <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-gray-900 transition-colors" />
                </div>
                <p className="text-metric-value mt-2">{m.value}</p>
                <p className="text-xs text-gray-500 mt-2">{m.subtitle}</p>
              </button>
            </GlassPanel>
          ))}
        </div>

        {/* Revenue Trend Chart */}
        <GlassPanel depth={70} delay={0.6}>
          <div className="flex items-center gap-3 mb-6">
            <TrendingUp className="w-6 h-6 text-green-600" />
            <h2 className="text-2xl font-light text-gray-900">Revenue Trends</h2>
          </div>
          <div className="h-80">
            {revenueTrends.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={revenueTrends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="date"
                    stroke="#6b7280"
                    style={{ fontSize: '12px', fontWeight: 300 }}
                  />
                  <YAxis
                    stroke="#6b7280"
                    style={{ fontSize: '12px', fontWeight: 300 }}
                    tickFormatter={(value) => `$${value.toLocaleString()}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                    }}
                    formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']}
                    labelStyle={{ fontWeight: 300 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="revenue"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ fill: '#10b981', r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <TrendingUp className="w-12 h-12 text-gray-400 mx-auto mb-4 opacity-30" />
                  <p className="text-gray-600 text-lg font-light">No revenue data yet</p>
                  <p className="text-gray-500 text-sm mt-2">
                    Revenue trends will appear once you start processing orders
                  </p>
                </div>
              </div>
            )}
          </div>
        </GlassPanel>

        {/* Store Rankings Section */}
        <GlassPanel depth={80} delay={0.7}>
          <div className="flex justify-between items-center mb-6">
            <div className="flex items-center gap-3">
              <Trophy className="w-6 h-6 text-yellow-600" />
              <h2 className="text-2xl font-light text-gray-900">Store Rankings</h2>
            </div>
            <button
              onClick={fetchRankings}
              disabled={loadingRankings}
              className="flex items-center gap-2 px-4 py-2 bg-white/50 border border-gray-200 text-gray-700 rounded-lg hover:bg-white transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loadingRankings ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </GlassPanel>

        {/* Top Performer Card */}
        {topStore && (
          <GlassPanel depth={70} delay={0.8}>
            <div className="flex items-center gap-4">
              <Medal className="w-12 h-12 text-yellow-600" />
              <div className="flex-1">
                <h3 className="text-sm text-gray-600 uppercase tracking-wide mb-1 font-light">Top Performer</h3>
                <h2 className="text-2xl font-light text-gray-900">{topStore.store_name}</h2>
                <p className="text-gray-600">{topStore.platform} • {topStore.product_count} products</p>
              </div>
              <div className="text-right">
                <div className="text-3xl font-light text-green-600">${topStore.monthly_revenue.toFixed(2)}</div>
                <div className="text-sm text-gray-500">Monthly Revenue</div>
              </div>
            </div>
          </GlassPanel>
        )}

        {/* Rankings Table */}
        {loadingRankings ? (
          <GlassPanel depth={60} delay={0.9}>
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
              <p className="text-gray-600 font-light">Loading rankings...</p>
            </div>
          </GlassPanel>
        ) : rankings.length > 0 ? (
          <StoreRankingsTable stores={rankings} />
        ) : (
          <GlassPanel depth={60} delay={0.9}>
            <div className="p-12 text-center">
              <Trophy className="w-16 h-16 mx-auto mb-4 text-gray-400 opacity-30" />
              <p className="text-gray-600 text-lg font-light">No stores to rank yet</p>
              <p className="text-gray-500 mt-2">Add stores to see performance rankings</p>
            </div>
          </GlassPanel>
        )}
      </div>

      {/* Modals */}
      {renderModalContent()}
    </div>
  );
}
