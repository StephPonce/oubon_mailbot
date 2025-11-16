import { useState, useEffect } from 'react';
import { ProductCard } from './components/ProductCard';
import ProductModal from './components/ProductModal';
import { NotificationBell } from './components/NotificationBell';
import { OrdersPage } from './pages/OrdersPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import PortfolioDashboard from './pages/PortfolioDashboard';
import EmailDashboard from './pages/EmailDashboard';
import { AIChatProvider } from './contexts/AIChatContext';
import GlobalAIChat from './components/GlobalAIChat';
import axios from 'axios';

interface Product {
  id: string;
  name: string;
  price: number;
  cost: number;
  score: number;
  profit_margin: number;
  estimated_profit: number;
  rating: number;
  orders: number;
  velocity_score: number;
  image_url: string;
  category: string;
  niche: string;
  aliexpress_url?: string;
  source: string;
}

export default function App() {
  const [currentPage, setCurrentPage] = useState<'portfolio' | 'products' | 'orders' | 'analytics' | 'emails'>('portfolio');
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [niche, setNiche] = useState('smart_home');
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [dataSource, setDataSource] = useState('');
  const [sortBy, setSortBy] = useState('velocity_score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [bulkDeploying, setBulkDeploying] = useState(false);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`http://127.0.0.1:8000/api/dashboard/v2/products`, {
        params: { niche, per_page: 20 }
      });
      setProducts(response.data.products || []);
      setDataSource(response.data.data_source || 'Unknown');
      setLastRefresh(new Date());
    } catch (error) {
      console.error('Failed to fetch:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentPage === 'products') {
      fetchProducts();
    }
  }, [niche, currentPage]);

  // Listen for navigation events from child components
  useEffect(() => {
    const handleNavigate = (event: CustomEvent<{ page: string }>) => {
      const page = event.detail.page as 'portfolio' | 'products' | 'orders' | 'analytics' | 'emails';
      setCurrentPage(page);
    };

    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => {
      window.removeEventListener('navigate', handleNavigate as EventListener);
    };
  }, []);

  const sortedProducts = [...products].sort((a, b) => {
    const aVal = a[sortBy as keyof Product] as number;
    const bVal = b[sortBy as keyof Product] as number;
    return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
  });

  const filteredProducts = sortedProducts.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleSelectAll = () => {
    if (selectedProducts.size === filteredProducts.length) {
      setSelectedProducts(new Set());
    } else {
      setSelectedProducts(new Set(filteredProducts.map(p => p.id)));
    }
  };

  const toggleProductSelection = (productId: string) => {
    const newSelected = new Set(selectedProducts);
    if (newSelected.has(productId)) {
      newSelected.delete(productId);
    } else {
      newSelected.add(productId);
    }
    setSelectedProducts(newSelected);
  };

  const bulkDeployProducts = async () => {
    if (selectedProducts.size === 0) {
      alert('Please select products to deploy');
      return;
    }

    setBulkDeploying(true);

    try {
      const response = await axios.post(
        'http://127.0.0.1:8000/api/dashboard/v2/products/bulk-deploy',
        Array.from(selectedProducts)
      );

      const { summary } = response.data;
      alert(
        `Deployment Complete!\n\n` +
        `✅ Successful: ${summary.successful}\n` +
        `❌ Failed: ${summary.failed}\n` +
        `⚠️ Already Deployed: ${summary.already_deployed}`
      );

      setSelectedProducts(new Set());
      fetchProducts();
    } catch (error) {
      console.error('Bulk deploy failed:', error);
      alert('Bulk deployment failed');
    } finally {
      setBulkDeploying(false);
    }
  };

  return (
    <AIChatProvider>
      <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-4xl font-bold text-gray-800">Ospra Intelligence</h1>
          <div className="flex items-center gap-4">
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage('portfolio')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentPage === 'portfolio'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                🏪 Portfolio
              </button>
              <button
                onClick={() => setCurrentPage('products')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentPage === 'products'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                📦 Products
              </button>
              <button
                onClick={() => setCurrentPage('emails')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentPage === 'emails'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                📧 Emails
              </button>
              <button
                onClick={() => setCurrentPage('orders')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentPage === 'orders'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                🛒 Orders
              </button>
              <button
                onClick={() => setCurrentPage('analytics')}
                className={`px-4 py-2 rounded-lg font-semibold transition ${
                  currentPage === 'analytics'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                📊 Analytics
              </button>
            </div>
            <NotificationBell />
          </div>
        </div>
      </div>

      {currentPage === 'portfolio' ? (
        <PortfolioDashboard />
      ) : currentPage === 'products' ? (
        <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <div className={`inline-block px-3 py-1 rounded-full text-sm font-bold mb-4 ${
              dataSource.includes('REAL_TIME') ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
            }`}>
              📡 {dataSource.includes('REAL_TIME') ? 'Real-Time Data Active' : 'Fallback Mode'}
            </div>

            {selectedProducts.size > 0 && (
              <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <span className="font-semibold text-blue-900">
                    {selectedProducts.size} product{selectedProducts.size !== 1 ? 's' : ''} selected
                  </span>
                  <button
                    onClick={() => setSelectedProducts(new Set())}
                    className="text-sm text-blue-700 hover:text-blue-900 underline"
                  >
                    Clear selection
                  </button>
                </div>
                <button
                  onClick={bulkDeployProducts}
                  disabled={bulkDeploying}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold disabled:bg-gray-400"
                >
                  {bulkDeploying ? 'Deploying...' : `🚀 Deploy ${selectedProducts.size} to Shopify`}
                </button>
              </div>
            )}

            <div className="flex gap-4 items-center flex-wrap">
              <button
                onClick={fetchProducts}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 font-semibold"
              >
                {loading ? 'Loading...' : '🔄 Refresh'}
              </button>

              <label className="flex items-center gap-2 px-4 py-2 border rounded cursor-pointer hover:bg-gray-50">
                <input
                  type="checkbox"
                  checked={selectedProducts.size === filteredProducts.length && filteredProducts.length > 0}
                  onChange={toggleSelectAll}
                  className="w-4 h-4 cursor-pointer"
                />
                <span className="font-semibold">Select All</span>
              </label>

              <select
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
                className="px-4 py-2 border rounded font-semibold"
              >
                <option value="smart_home">Smart Home</option>
                <option value="fitness">Fitness</option>
                <option value="kitchen">Kitchen</option>
              </select>

              <input
                type="text"
                placeholder="🔍 Search products..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="px-4 py-2 border rounded w-64"
              />

              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-4 py-2 border rounded font-semibold"
              >
                <option value="velocity_score">Velocity</option>
                <option value="price">Price</option>
                <option value="estimated_profit">Profit</option>
                <option value="score">Score</option>
              </select>

              <button
                onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
                className="px-4 py-2 border rounded font-semibold hover:bg-gray-100"
              >
                {sortOrder === 'desc' ? '↓ High to Low' : '↑ Low to High'}
              </button>

              {lastRefresh && (
                <span className="text-sm text-gray-600">
                  Last refresh: {lastRefresh.toLocaleTimeString()}
                </span>
              )}

              <span className="text-sm font-semibold text-gray-700">
                {filteredProducts.length} of {products.length} products
              </span>
            </div>
          </div>

          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-4 border-blue-600 mb-4"></div>
              <p className="text-gray-600 font-semibold">Loading products...</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onAnalyze={(product) => setSelectedProduct(product)}
                  isSelected={selectedProducts.has(product.id)}
                  onToggleSelect={toggleProductSelection}
                />
              ))}
            </div>
          )}

          {!loading && products.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No products found
            </div>
          )}

          {selectedProduct && (
            <ProductModal
              product={selectedProduct}
              onClose={() => setSelectedProduct(null)}
            />
          )}
        </div>
      ) : currentPage === 'emails' ? (
        <EmailDashboard />
      ) : currentPage === 'orders' ? (
        <OrdersPage />
      ) : (
        <AnalyticsPage />
      )}
      </div>

      {/* Global AI Chat - available on all pages */}
      <GlobalAIChat />
    </AIChatProvider>
  );
}
