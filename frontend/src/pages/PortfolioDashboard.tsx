import React, { useEffect, useState, useCallback } from 'react';
import { GlassPanel } from '@/components/GlassPanel';
import { 
  Trophy, Medal, RefreshCw, ChevronRight, X, TrendingUp, 
  ShoppingBag, Package, DollarSign, Zap, ExternalLink, 
  CheckCircle, AlertCircle, Loader2, Eye, Trash2,
  ArrowUpRight, ArrowDownRight, Minus, Store, Plus, Settings
} from 'lucide-react';
import api, { shopifyAPI } from '../lib/api';
import StoreRankingsTable from '../components/portfolio/StoreRankingsTable';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

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

interface ShopifyProduct {
  id: number;
  title: string;
  handle: string;
  status: string;
  price: number;
  inventory_quantity: number;
  created_at: string;
  image_url?: string;
  ospra_tracked?: boolean;
}

interface ShopifyStatus {
  configured: boolean;
  store_name: string;
  store_domain?: string;
  connection: string;
  error?: string;
}

interface ShopifyAnalytics {
  total_products: number;
  total_inventory: number;
  estimated_value: number;
  ospra_tracked: number;
}

export default function PortfolioDashboard() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [rankings, setRankings] = useState<StoreRanking[]>([]);
  const [loadingRankings, setLoadingRankings] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [revenueTrends, setRevenueTrends] = useState<RevenueDataPoint[]>([]);

  // Shopify State
  const [shopifyStatus, setShopifyStatus] = useState<ShopifyStatus | null>(null);
  const [shopifyProducts, setShopifyProducts] = useState<ShopifyProduct[]>([]);
  const [shopifyAnalytics, setShopifyAnalytics] = useState<ShopifyAnalytics | null>(null);
  const [loadingShopify, setLoadingShopify] = useState(true);
  const [selectedShopifyProduct, setSelectedShopifyProduct] = useState<ShopifyProduct | null>(null);
  const [showAddStoreModal, setShowAddStoreModal] = useState(false);
  const [addingStore, setAddingStore] = useState(false);
  const [newStore, setNewStore] = useState({
    store_name: '',
    store_url: '',
    platform: 'shopify',
    niche: '',
    shop_url: '',
    access_token: ''
  });

  // Fetch Shopify data
  const fetchShopifyData = useCallback(async () => {
    setLoadingShopify(true);
    try {
      // Fetch status first
      try {
        const status = await shopifyAPI.getStatus();
        setShopifyStatus(status);
      } catch (err) {
        console.error('Shopify status error:', err);
        setShopifyStatus({ configured: false, store_name: 'Not Connected', connection: 'error' });
      }

      // Fetch products
      try {
        const products = await shopifyAPI.getProducts(12);
        setShopifyProducts(Array.isArray(products) ? products : []);
      } catch (err) {
        console.error('Shopify products error:', err);
        setShopifyProducts([]);
      }

      // Fetch analytics
      try {
        const analytics = await shopifyAPI.getAnalytics();
        setShopifyAnalytics(analytics);
      } catch (err) {
        console.error('Shopify analytics error:', err);
        setShopifyAnalytics(null);
      }
    } catch (err) {
      console.error('Failed to fetch Shopify data:', err);
      setShopifyStatus({ configured: false, store_name: 'Error', connection: 'error' });
    } finally {
      setLoadingShopify(false);
    }
  }, []);

  const fetchRankings = async () => {
    setLoadingRankings(true);
    try {
      const response = await api.get('/api/portfolio/rankings');
      setRankings(response.data);
    } catch (err) {
      console.error('Failed to fetch rankings:', err);
    } finally {
      setLoadingRankings(false);
    }
  };

  useEffect(() => {
    fetchRankings();
    fetchShopifyData();
  }, [fetchShopifyData]);

  useEffect(() => {
    api.get('/api/portfolio/overview')
      .then(res => {
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

  useEffect(() => {
    api.get('/api/dashboard/v2/analytics/business')
      .then(res => {
        const revenueByDay = res.data.revenue_by_day || [];
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

  const handleDeleteProduct = async (productId: number) => {
    if (!confirm('Remove this product from your Shopify store?')) return;
    try {
      await shopifyAPI.deleteProduct(productId);
      setShopifyProducts(prev => prev.filter(p => p.id !== productId));
      if (shopifyAnalytics) {
        setShopifyAnalytics({
          ...shopifyAnalytics,
          total_products: shopifyAnalytics.total_products - 1
        });
      }
    } catch (err) {
      console.error('Failed to delete product:', err);
      alert('Failed to remove product');
    }
  };

  const handleAddStore = async () => {
    if (!newStore.store_name || !newStore.shop_url || !newStore.access_token) {
      alert('Please fill in all required fields');
      return;
    }
    
    setAddingStore(true);
    try {
      await api.post('/api/portfolio/stores/add', {
        store_name: newStore.store_name,
        store_url: `https://${newStore.shop_url}.myshopify.com`,
        platform: newStore.platform,
        niche: newStore.niche || 'general',
        target_market: 'US',
        currency: 'USD',
        credentials: {
          shop_url: newStore.shop_url,
          access_token: newStore.access_token
        }
      });
      
      // Reset form and refresh
      setNewStore({
        store_name: '',
        store_url: '',
        platform: 'shopify',
        niche: '',
        shop_url: '',
        access_token: ''
      });
      setShowAddStoreModal(false);
      fetchRankings();
      fetchShopifyData();
      alert('Store added successfully!');
    } catch (err: any) {
      console.error('Failed to add store:', err);
      alert(err.response?.data?.detail || 'Failed to add store');
    } finally {
      setAddingStore(false);
    }
  };

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
      subtitle: `$${data.totalRevenue.toLocaleString()} total`,
      icon: DollarSign,
      color: "text-emerald-600",
      bgColor: "bg-emerald-50"
    },
    {
      id: "orders",
      label: "Total Orders",
      value: data.totalOrders.toString(),
      subtitle: "All time",
      icon: Package,
      color: "text-blue-600",
      bgColor: "bg-blue-50"
    },
    {
      id: "stores",
      label: "Active Stores",
      value: data.activeStores.toString(),
      subtitle: `${data.totalStores} total`,
      icon: Store,
      color: "text-purple-600",
      bgColor: "bg-purple-50"
    },
    {
      id: "products",
      label: "Active Products",
      value: data.activeProducts.toString(),
      subtitle: `${data.totalProducts} total`,
      icon: ShoppingBag,
      color: "text-amber-600",
      bgColor: "bg-amber-50"
    },
    {
      id: "conversion",
      label: "Avg. Conversion",
      value: `${data.avgConversion.toFixed(2)}%`,
      subtitle: "Portfolio average",
      icon: TrendingUp,
      color: "text-rose-600",
      bgColor: "bg-rose-50"
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
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-200/50 transition-colors">
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );

  // Shopify connection indicator component
  const ShopifyConnectionBadge = () => {
    if (loadingShopify) {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100 text-gray-600">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm font-medium">Connecting...</span>
        </div>
      );
    }

    const isConnected = shopifyStatus?.connection === 'active';
    return (
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
        isConnected ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
      }`}>
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
        <span className="text-sm font-medium">
          {isConnected ? shopifyStatus?.store_name : 'Store Offline'}
        </span>
        {isConnected && shopifyStatus?.store_domain && (
          <a 
            href={`https://${shopifyStatus.store_domain}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    );
  };

  const renderModalContent = () => {
    if (!selectedMetric) return null;

    switch (selectedMetric) {
      case 'revenue':
        return (
          <Modal title="Revenue Breakdown" onClose={() => setSelectedMetric(null)}>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="text-center p-6 rounded-xl bg-emerald-50">
                  <div className="text-3xl font-light text-emerald-700 mb-2">
                    ${data.monthlyRevenue.toLocaleString()}
                  </div>
                  <div className="text-sm text-emerald-600 font-medium">Monthly Revenue</div>
                </div>
                <div className="text-center p-6 rounded-xl bg-gray-50">
                  <div className="text-3xl font-light text-gray-900 mb-2">
                    ${data.totalRevenue.toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-600 font-medium">Total Revenue</div>
                </div>
              </div>

              {rankings.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Revenue by Store</h3>
                  <div className="space-y-3">
                    {rankings.map((store) => (
                      <div key={store.id} className="rounded-xl p-4 border border-gray-100 bg-white hover:shadow-md transition">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-gray-900 font-medium">{store.store_name}</div>
                            <div className="text-sm text-gray-500 capitalize">{store.platform}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-semibold text-emerald-600">
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

      case 'shopify':
        return (
          <Modal title="Shopify Store Details" onClose={() => setSelectedMetric(null)}>
            <div className="space-y-6">
              {/* Store Status */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-gray-50">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    shopifyStatus?.connection === 'active' ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
                  }`} />
                  <div>
                    <div className="font-medium text-gray-900">{shopifyStatus?.store_name}</div>
                    <div className="text-sm text-gray-500">{shopifyStatus?.store_domain}</div>
                  </div>
                </div>
                {shopifyStatus?.store_domain && (
                  <a 
                    href={`https://${shopifyStatus.store_domain}/admin`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition flex items-center gap-2"
                  >
                    Open Admin <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>

              {/* Analytics Grid */}
              {shopifyAnalytics && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-indigo-50 text-center">
                    <div className="text-2xl font-bold text-indigo-700">{shopifyAnalytics.total_products}</div>
                    <div className="text-sm text-indigo-600">Products</div>
                  </div>
                  <div className="p-4 rounded-xl bg-emerald-50 text-center">
                    <div className="text-2xl font-bold text-emerald-700">{shopifyAnalytics.total_inventory.toLocaleString()}</div>
                    <div className="text-sm text-emerald-600">Units in Stock</div>
                  </div>
                  <div className="p-4 rounded-xl bg-amber-50 text-center">
                    <div className="text-2xl font-bold text-amber-700">${shopifyAnalytics.estimated_value.toLocaleString()}</div>
                    <div className="text-sm text-amber-600">Inventory Value</div>
                  </div>
                  <div className="p-4 rounded-xl bg-purple-50 text-center">
                    <div className="text-2xl font-bold text-purple-700">{shopifyAnalytics.ospra_tracked}</div>
                    <div className="text-sm text-purple-600">Ospra Deployed</div>
                  </div>
                </div>
              )}

              {/* All Products */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">All Products ({shopifyProducts.length})</h3>
                <div className="grid grid-cols-3 gap-4 max-h-96 overflow-y-auto">
                  {shopifyProducts.map((product) => (
                    <div key={product.id} className="border border-gray-100 rounded-lg overflow-hidden hover:shadow-md transition group">
                      <div className="aspect-square bg-gray-100 relative">
                        {product.image_url ? (
                          <img src={product.image_url} alt={product.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <Package className="w-8 h-8 text-gray-300" />
                          </div>
                        )}
                        <button
                          onClick={() => handleDeleteProduct(product.id)}
                          className="absolute top-2 right-2 p-1.5 bg-red-500 text-white rounded-lg opacity-0 group-hover:opacity-100 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <div className="p-3">
                        <div className="text-sm font-medium text-gray-900 truncate">{product.title}</div>
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-sm font-bold text-indigo-600">${product.price}</span>
                          <span className="text-xs text-gray-500">{product.inventory_quantity} in stock</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Modal>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header with Shopify Status */}
        <GlassPanel depth={80} delay={0.2}>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-light text-gray-900">Portfolio Command Center</h1>
              <p className="text-gray-500 mt-1">Real-time intelligence across all your stores</p>
            </div>
            <div className="flex items-center gap-4">
              <ShopifyConnectionBadge />
              <button
                onClick={() => setShowAddStoreModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition text-sm font-medium"
              >
                <Plus className="w-4 h-4" /> Add Store
              </button>
              <button
                onClick={() => {
                  fetchRankings();
                  fetchShopifyData();
                }}
                className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 transition"
              >
                <RefreshCw className="w-5 h-5 text-gray-600" />
              </button>
            </div>
          </div>
        </GlassPanel>

        {/* Premium Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {metrics.map((m, i) => (
            <GlassPanel key={i} depth={30 + i * 5} delay={0.3 + i * 0.05} className="p-0">
              <button
                onClick={() => setSelectedMetric(m.id)}
                className="w-full text-left p-5 transition-all hover:scale-[1.02] cursor-pointer group"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className={`p-2 rounded-lg ${m.bgColor}`}>
                    <m.icon className={`w-4 h-4 ${m.color}`} />
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-gray-600 transition-colors" />
                </div>
                <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">{m.label}</p>
                <p className="text-2xl font-semibold text-gray-900 mt-1">{m.value}</p>
                <p className="text-xs text-gray-400 mt-1">{m.subtitle}</p>
              </button>
            </GlassPanel>
          ))}
        </div>

        {/* Shopify Live Store Section */}
        <GlassPanel depth={75} delay={0.5}>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                <ShoppingBag className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Live Store</h2>
                <p className="text-sm text-gray-500">Products currently on Shopify</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {shopifyAnalytics && (
                <div className="flex items-center gap-6 mr-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">{shopifyAnalytics.total_products}</div>
                    <div className="text-xs text-gray-500">Products</div>
                  </div>
                  <div className="w-px h-8 bg-gray-200" />
                  <div className="text-center">
                    <div className="text-2xl font-bold text-emerald-600">${shopifyAnalytics.estimated_value.toLocaleString()}</div>
                    <div className="text-xs text-gray-500">Value</div>
                  </div>
                </div>
              )}
              <button
                onClick={() => setSelectedMetric('shopify')}
                className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition flex items-center gap-2 text-sm font-medium"
              >
                View All <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {loadingShopify ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            </div>
          ) : shopifyProducts.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-xl">
              <Package className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">No products in your store yet</p>
              <p className="text-sm text-gray-400 mt-1">Deploy products from the Discovery page</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {shopifyProducts.slice(0, 6).map((product) => (
                <div 
                  key={product.id}
                  className="group relative bg-white border border-gray-100 rounded-xl overflow-hidden hover:shadow-lg hover:border-indigo-200 transition-all cursor-pointer"
                  onClick={() => setSelectedShopifyProduct(product)}
                >
                  <div className="aspect-square bg-gray-50 relative overflow-hidden">
                    {product.image_url ? (
                      <img 
                        src={product.image_url} 
                        alt={product.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-8 h-8 text-gray-300" />
                      </div>
                    )}
                    {product.ospra_tracked && (
                      <div className="absolute top-2 left-2 px-2 py-0.5 bg-indigo-600 text-white text-xs font-medium rounded-full flex items-center gap-1">
                        <Zap className="w-3 h-3" /> Ospra
                      </div>
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    <div className="absolute bottom-2 left-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteProduct(product.id);
                        }}
                        className="w-full py-1.5 bg-white/90 text-red-600 text-xs font-medium rounded-lg hover:bg-white transition"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                  <div className="p-3">
                    <h3 className="text-sm font-medium text-gray-900 truncate">{product.title}</h3>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-sm font-bold text-indigo-600">${product.price}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        product.inventory_quantity > 10 
                          ? 'bg-emerald-50 text-emerald-700' 
                          : product.inventory_quantity > 0 
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-red-50 text-red-700'
                      }`}>
                        {product.inventory_quantity} left
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassPanel>

        {/* Two Column: Revenue Chart + Top Performer */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Revenue Trend Chart - Takes 2 columns */}
          <GlassPanel depth={70} delay={0.6} className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-emerald-50">
                <TrendingUp className="w-5 h-5 text-emerald-600" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900">Revenue Trends</h2>
            </div>
            <div className="h-64">
              {revenueTrends.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={revenueTrends}>
                    <defs>
                      <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                    <XAxis 
                      dataKey="date" 
                      stroke="#9ca3af" 
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis 
                      stroke="#9ca3af" 
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `$${value.toLocaleString()}`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        border: 'none',
                        borderRadius: '12px',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)'
                      }}
                      formatter={(value: any) => [`$${value.toLocaleString()}`, 'Revenue']}
                    />
                    <Area
                      type="monotone"
                      dataKey="revenue"
                      stroke="#10b981"
                      strokeWidth={2}
                      fill="url(#revenueGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <TrendingUp className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500 font-medium">No revenue data yet</p>
                    <p className="text-gray-400 text-sm mt-1">Start selling to see trends</p>
                  </div>
                </div>
              )}
            </div>
          </GlassPanel>

          {/* Top Performer Card - Takes 1 column */}
          {topStore ? (
            <GlassPanel depth={70} delay={0.7}>
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 rounded-lg bg-amber-50">
                  <Trophy className="w-5 h-5 text-amber-600" />
                </div>
                <h2 className="text-xl font-semibold text-gray-900">Top Performer</h2>
              </div>
              <div className="text-center py-4">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
                  <Medal className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900">{topStore.store_name}</h3>
                <p className="text-sm text-gray-500 capitalize mt-1">{topStore.platform}</p>
                <div className="mt-6 p-4 rounded-xl bg-emerald-50">
                  <div className="text-3xl font-bold text-emerald-600">
                    ${topStore.monthly_revenue.toLocaleString()}
                  </div>
                  <div className="text-sm text-emerald-700 mt-1">Monthly Revenue</div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="p-3 rounded-lg bg-gray-50">
                    <div className="text-lg font-semibold text-gray-900">{topStore.conversion_rate.toFixed(1)}%</div>
                    <div className="text-xs text-gray-500">Conversion</div>
                  </div>
                  <div className="p-3 rounded-lg bg-gray-50">
                    <div className="text-lg font-semibold text-gray-900">{topStore.product_count}</div>
                    <div className="text-xs text-gray-500">Products</div>
                  </div>
                </div>
              </div>
            </GlassPanel>
          ) : (
            <GlassPanel depth={70} delay={0.7}>
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 rounded-lg bg-amber-50">
                  <Trophy className="w-5 h-5 text-amber-600" />
                </div>
                <h2 className="text-xl font-semibold text-gray-900">Top Performer</h2>
              </div>
              <div className="text-center py-8">
                <Trophy className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No stores ranked yet</p>
              </div>
            </GlassPanel>
          )}
        </div>

        {/* Store Rankings Section */}
        <GlassPanel depth={80} delay={0.8}>
          <div className="flex justify-between items-center mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-50">
                <Trophy className="w-5 h-5 text-purple-600" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900">Store Rankings</h2>
            </div>
            <button
              onClick={fetchRankings}
              disabled={loadingRankings}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loadingRankings ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {loadingRankings ? (
            <div className="text-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">Loading rankings...</p>
            </div>
          ) : rankings.length > 0 ? (
            <StoreRankingsTable stores={rankings} />
          ) : (
            <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-xl">
              <Trophy className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 font-medium">No stores to rank yet</p>
              <p className="text-gray-400 text-sm mt-1">Add stores to see performance rankings</p>
            </div>
          )}
        </GlassPanel>
      </div>

      {/* Modals */}
      {renderModalContent()}

      {/* Product Detail Modal */}
      {selectedShopifyProduct && (
        <Modal title="Product Details" onClose={() => setSelectedShopifyProduct(null)}>
          <div className="grid grid-cols-2 gap-8">
            <div className="aspect-square bg-gray-100 rounded-xl overflow-hidden">
              {selectedShopifyProduct.image_url ? (
                <img 
                  src={selectedShopifyProduct.image_url} 
                  alt={selectedShopifyProduct.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Package className="w-16 h-16 text-gray-300" />
                </div>
              )}
            </div>
            <div>
              <h3 className="text-2xl font-semibold text-gray-900">{selectedShopifyProduct.title}</h3>
              <div className="flex items-center gap-3 mt-4">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  selectedShopifyProduct.status === 'active' 
                    ? 'bg-emerald-50 text-emerald-700' 
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {selectedShopifyProduct.status}
                </span>
                {selectedShopifyProduct.ospra_tracked && (
                  <span className="px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-sm font-medium flex items-center gap-1">
                    <Zap className="w-3 h-3" /> Ospra Tracked
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4 mt-6">
                <div className="p-4 rounded-xl bg-gray-50">
                  <div className="text-2xl font-bold text-gray-900">${selectedShopifyProduct.price}</div>
                  <div className="text-sm text-gray-500">Price</div>
                </div>
                <div className="p-4 rounded-xl bg-gray-50">
                  <div className="text-2xl font-bold text-gray-900">{selectedShopifyProduct.inventory_quantity}</div>
                  <div className="text-sm text-gray-500">In Stock</div>
                </div>
              </div>
              <div className="mt-6 space-y-3">
                <a
                  href={`https://${shopifyStatus?.store_domain}/products/${selectedShopifyProduct.handle}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition flex items-center justify-center gap-2 font-medium"
                >
                  <Eye className="w-4 h-4" /> View on Store
                </a>
                <button
                  onClick={() => {
                    handleDeleteProduct(selectedShopifyProduct.id);
                    setSelectedShopifyProduct(null);
                  }}
                  className="w-full py-3 border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition flex items-center justify-center gap-2 font-medium"
                >
                  <Trash2 className="w-4 h-4" /> Remove from Store
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Add Store Modal */}
      {showAddStoreModal && (
        <Modal title="Add New Store" onClose={() => setShowAddStoreModal(false)}>
          <div className="space-y-6">
            <p className="text-gray-600">
              Connect a new e-commerce store to your Ospra Intelligence portfolio.
            </p>
            
            {/* Platform Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Platform</label>
              <div className="grid grid-cols-3 gap-3">
                {['shopify', 'amazon', 'woocommerce'].map((platform) => (
                  <button
                    key={platform}
                    onClick={() => setNewStore({ ...newStore, platform })}
                    className={`p-4 rounded-xl border-2 transition ${
                      newStore.platform === platform
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="text-center">
                      <Store className={`w-8 h-8 mx-auto mb-2 ${
                        newStore.platform === platform ? 'text-indigo-600' : 'text-gray-400'
                      }`} />
                      <span className={`text-sm font-medium capitalize ${
                        newStore.platform === platform ? 'text-indigo-700' : 'text-gray-600'
                      }`}>
                        {platform}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Store Details */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Display Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newStore.store_name}
                  onChange={(e) => setNewStore({ ...newStore, store_name: e.target.value })}
                  placeholder="e.g., Oubon Shop"
                  className="w-full px-4 py-3 rounded-lg border border-gray-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Niche
                </label>
                <input
                  type="text"
                  value={newStore.niche}
                  onChange={(e) => setNewStore({ ...newStore, niche: e.target.value })}
                  placeholder="e.g., Smart Home"
                  className="w-full px-4 py-3 rounded-lg border border-gray-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition"
                />
              </div>
            </div>

            {/* Shopify Credentials */}
            {newStore.platform === 'shopify' && (
              <div className="p-4 rounded-xl bg-gray-50 space-y-4">
                <h4 className="font-medium text-gray-900 flex items-center gap-2">
                  <Store className="w-4 h-4" /> Shopify Credentials
                </h4>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Store Subdomain <span className="text-red-500">*</span>
                  </label>
                  <div className="flex items-center">
                    <input
                      type="text"
                      value={newStore.shop_url}
                      onChange={(e) => setNewStore({ ...newStore, shop_url: e.target.value })}
                      placeholder="your-store"
                      className="flex-1 px-4 py-3 rounded-l-lg border border-gray-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition"
                    />
                    <span className="px-4 py-3 bg-gray-100 border border-l-0 border-gray-200 rounded-r-lg text-gray-500 text-sm">
                      .myshopify.com
                    </span>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Admin API Access Token <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="password"
                    value={newStore.access_token}
                    onChange={(e) => setNewStore({ ...newStore, access_token: e.target.value })}
                    placeholder="shpat_xxxxxxxxxxxxx"
                    className="w-full px-4 py-3 rounded-lg border border-gray-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition"
                  />
                  <p className="text-xs text-gray-500 mt-2">
                    Get this from Shopify Admin → Settings → Apps → Develop apps
                  </p>
                </div>
              </div>
            )}

            {/* Amazon/WooCommerce placeholders */}
            {newStore.platform === 'amazon' && (
              <div className="p-6 rounded-xl bg-amber-50 text-center">
                <AlertCircle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
                <p className="text-amber-700 font-medium">Amazon integration coming soon!</p>
                <p className="text-sm text-amber-600 mt-1">We're working on SP-API integration.</p>
              </div>
            )}

            {newStore.platform === 'woocommerce' && (
              <div className="p-6 rounded-xl bg-purple-50 text-center">
                <AlertCircle className="w-8 h-8 text-purple-500 mx-auto mb-2" />
                <p className="text-purple-700 font-medium">WooCommerce integration coming soon!</p>
                <p className="text-sm text-purple-600 mt-1">REST API support in development.</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100">
              <button
                onClick={() => setShowAddStoreModal(false)}
                className="px-6 py-2.5 text-gray-600 hover:text-gray-900 transition font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleAddStore}
                disabled={addingStore || newStore.platform !== 'shopify'}
                className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {addingStore ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Connecting...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" /> Add Store
                  </>
                )}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
