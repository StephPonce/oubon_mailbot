import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { ProductCard } from '../components/ProductCard';
import ProductModal from '../components/ProductModal';
import { Layers, ChevronDown, RefreshCw, Search, ArrowDownUp } from 'lucide-react';
import { useProducts } from '../contexts/ProductsContext';

interface Product {
  id: string;
  name: string;
  image_url?: string;
  price: number;
  cost?: number;
  trend_score?: number;
  velocity_score?: number;
  score?: number;
  sales_rank?: number;
  orders?: number;
  competition_score?: number;
  profit_margin?: number;
  estimated_profit?: number;
  supplier_url?: string;
  niche?: string;
  discovered_at?: string;
  commission_rate?: number;
  tier?: string;
  rating?: number;
  original_price?: number;
  aliexpress_cost?: number;
  shipping_cost?: number;
  source?: string;
}

interface RawProduct {
  product_id: string;
  title: string;
  main_image: string;
  price: number;
  trend_score: number;
  rating: number;
  commission_rate: number;
  final_score: number; // Used for velocity_score
  sales_volume: number; // Used for orders/sales_rank
  competition_score: number;
  affiliate_link: string; // Used for supplier_url
  niche: string;
  discovered_at: string;
  tier: string;
}

interface Niche {
  id: string;
  name: string;
  trending: boolean;
}

export const ProductsPage = () => {
  // Use global products context for persistence across navigation
  const {
    products,
    setProducts,
    dataSource,
    setDataSource,
    lastRefresh,
    setLastRefresh,
    currentNiche: niche,
    setCurrentNiche: setNiche
  } = useProducts();

  // Local state for UI
  const [loading, setLoading] = useState(false);
  const [niches, setNiches] = useState<Niche[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [sortBy, setSortBy] = useState('velocity_score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [bulkDeploying, setBulkDeploying] = useState(false);
  const [discovering, setDiscovering] = useState(false);

  const fetchNiches = useCallback(async () => {
    try {
      // Use new unified discovery niches endpoint
      const response = await axios.get('http://localhost:8001/api/discovery/niches');
      if (response.data.success && response.data.niches) {
        setNiches(response.data.niches.map((n: Niche) => ({
          id: n.id,
          name: n.name,
          trending: true // All niches are live with AliExpress
        })));
      }
    } catch (error) {
      console.error('Failed to fetch niches:', error);
      // Fallback niches
      setNiches([
        {id: 'smart_home', name: 'Smart Home', trending: true},
        {id: 'fitness', name: 'Fitness', trending: true},
        {id: 'kitchen', name: 'Kitchen', trending: false},
        {id: 'beauty', name: 'Beauty', trending: false},
        {id: 'pet', name: 'Pet Products', trending: false}
      ]);
    }
  }, [setNiches]);

  const fetchProducts = useCallback(async (forceDiscovery = false) => {
    setLoading(true);
    try {
      if (forceDiscovery) {
        // Use new unified discovery API (AliExpress Affiliate + Google Trends)
        const response = await axios.get(`http://localhost:8001/api/discovery/quick/${niche}`, {
          params: { count: 20 }
        });

        if (response.data.success && response.data.products) {
          // Transform products to match existing Product interface
          const transformedProducts = response.data.products.map((p: RawProduct) => {
            // Calculate Ospra Score (0-10) based on multiple factors
            const trendWeight = 0.3;
            const ratingWeight = 0.3;
            const commissionWeight = 0.2;
            const priceWeight = 0.2;

            const trendScore = (p.trend_score / 100) * 10; // Convert 0-100 to 0-10
            const ratingScore = (p.rating / 5) * 10; // Convert 0-5 stars to 0-10
            const commissionScore = Math.min((p.commission_rate / 10) * 10, 10); // Cap at 10
            const priceScore = (p.price >= 10 && p.price <= 50) ? 10 : 5; // Sweet spot pricing

            const ospraScore = (
              trendScore * trendWeight +
              ratingScore * ratingWeight +
              commissionScore * commissionWeight +
              priceWeight * priceWeight
            );

            // Calculate realistic profit after all costs
            const aliexpressCost = p.price;
            const shippingCost = aliexpressCost * 0.15; // ~15% shipping from China
            const totalCost = aliexpressCost + shippingCost;

            // Typical dropshipping markup: 2-3x cost
            const suggestedRetailPrice = totalCost * 2.5;

            // Revenue calculations
            const grossRevenue = suggestedRetailPrice;
            const shopifyFees = grossRevenue * 0.029 + 0.30; // 2.9% + $0.30 per transaction
            const paymentProcessingFees = grossRevenue * 0.03; // ~3% credit card fees


            // Net profit
            const netProfit = grossRevenue - totalCost - shopifyFees - paymentProcessingFees;
            const profitMargin = ((netProfit / grossRevenue) * 100);

            return {
              id: p.product_id,
              name: p.title,
              image_url: p.main_image,
              price: suggestedRetailPrice, // Show suggested retail price instead of cost
              cost: totalCost, // Store actual cost for analysis
              trend_score: p.trend_score,
              velocity_score: p.final_score, // Use final_score as velocity
              score: ospraScore, // Calculated Ospra score (0-10)
              sales_rank: p.sales_volume,
              orders: p.sales_volume || 0, // Map sales_volume to orders
              competition_score: p.competition_score || 0,
              profit_margin: profitMargin, // Real profit margin percentage
              estimated_profit: netProfit, // Net profit after all fees
              supplier_url: p.affiliate_link, // Use affiliate link for direct access
              niche: p.niche,
              discovered_at: p.discovered_at,
              commission_rate: p.commission_rate,
              tier: p.tier,
              rating: p.rating,
              original_price: p.price, // Original AliExpress price
              aliexpress_cost: aliexpressCost,
              shipping_cost: shippingCost
            };
          });

          // Filter for quality products only (min 4.0 rating)
          const qualityProducts = transformedProducts.filter((p: Product) =>
            p.rating >= 4.0 && p.estimated_profit > 5 // Min $5 profit
          );

          setProducts(qualityProducts);
          setDataSource('REAL_TIME_ALIEXPRESS_AFFILIATE'); // New data source
          setLastRefresh(new Date());
        } else {
          setProducts([]);
          setDataSource('No Data');
        }
      }
    } catch (error) {
      console.error('Failed to fetch:', error);
      setProducts([]);
      setDataSource('Error');
    } finally {
      setLoading(false);
    }
  }, [niche, setProducts, setDataSource, setLastRefresh, setLoading]);

  const runDiscovery = async () => {
    setDiscovering(true);
    await fetchProducts(true);
    setDiscovering(false);
  };

  useEffect(() => {
    fetchNiches();
    // Only fetch products if we don't have any cached
    if (products.length === 0) {
      fetchProducts();
    }
  }, [fetchNiches]);

  useEffect(() => {
    // Re-discover when niche changes
    if (niches.length > 0) {
      fetchProducts();
    }
  }, [niche, niches.length]);

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
      const response = await axios.post('http://127.0.0.1:8001/api/dashboard/v2/products/bulk-deploy', Array.from(selectedProducts));
      const { summary } = response.data;
      alert(`Deployment Complete!\n\nSuccessful: ${summary.successful}\nFailed: ${summary.failed}\nAlready Deployed: ${summary.already_deployed}`);
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
    <div className="space-y-6 px-8 py-6">
      {/* Header and Filters */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <h2 className="text-2xl font-bold text-gray-200">Product Discovery</h2>
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
              dataSource.includes('REAL_TIME') ? 'bg-green-500/20 text-green-300' : 'bg-yellow-500/20 text-yellow-300'
            }`}>
              {dataSource.includes('REAL_TIME') ? 'Live Data' : 'Fallback Data'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            {lastRefresh && (
              <span className="text-sm text-gray-500">
                Updated: {lastRefresh.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={runDiscovery}
              disabled={loading || discovering}
              className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-lg transition-all flex items-center gap-2 shadow-lg shadow-blue-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-5 h-5 ${(loading || discovering) ? 'animate-spin' : ''}`} />
              {loading || discovering ? 'Discovering...' : 'Discover New Products'}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-grow min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
            <input
              type="text"
              placeholder="Search products..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-900/70 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-blue"
            />
          </div>

          {/* Niche Select */}
          <div className="relative">
            <select
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              className="bg-gray-900/70 border border-gray-700 rounded-lg px-4 py-2 pr-8 text-gray-200 appearance-none cursor-pointer hover:border-brand-blue transition focus:outline-none focus:ring-2 focus:ring-brand-blue"
            >
              {niches.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}{n.trending ? ' (Trending)' : ''}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          </div>

          {/* Sort By Select */}
          <div className="relative">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-gray-900/70 border border-gray-700 rounded-lg px-4 py-2 pr-8 text-gray-200 appearance-none cursor-pointer hover:border-brand-blue transition focus:outline-none focus:ring-2 focus:ring-brand-blue"
            >
              <option value="velocity_score">Sort by Velocity</option>
              <option value="score">Sort by Grade</option>
              <option value="rating">Sort by Rating</option>
              <option value="estimated_profit">Sort by Profit</option>
              <option value="price">Sort by Price</option>
              <option value="orders">Sort by Sales</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          </div>

          <button
            onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
            className="px-3 py-2 bg-gray-900/70 border border-gray-700 text-gray-300 rounded-lg hover:bg-glass-white flex items-center gap-2"
            title="Toggle Sort Order"
          >
            <ArrowDownUp className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Bulk Actions Bar */}
      {selectedProducts.size > 0 && (
        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-4 flex items-center justify-between sticky top-4 z-10">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedProducts.size === filteredProducts.length}
                onChange={toggleSelectAll}
                className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-brand-blue focus:ring-brand-blue"
              />
              <span className="font-semibold text-gray-200">
                {selectedProducts.size} product{selectedProducts.size !== 1 ? 's' : ''} selected
              </span>
            </label>
            <button
              onClick={() => setSelectedProducts(new Set())}
              className="text-sm text-gray-400 hover:text-white hover:underline"
            >
              Clear
            </button>
          </div>
          <button
            onClick={bulkDeployProducts}
            disabled={bulkDeploying}
            className="px-5 py-2 bg-brand-blue text-white rounded-lg font-semibold hover:opacity-90 transition flex items-center gap-2 disabled:bg-gray-600 disabled:cursor-not-allowed"
          >
            <Layers className="w-4 h-4" />
            {bulkDeploying ? 'Deploying...' : `Deploy to Store`}
          </button>
        </div>
      )}

      {/* Product Grid */}
      {loading ? (
        <div className="text-center py-20">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mb-4"></div>
          <p className="text-gray-400 font-semibold">Discovering products...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6">
          {filteredProducts.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onAnalyze={(product: Product) => setSelectedProduct(product)}
              isSelected={selectedProducts.has(product.id)}
              onToggleSelect={toggleProductSelection}
            />
          ))}
        </div>
      )}

      {!loading && products.length === 0 && (
        <div className="text-center py-20 border-2 border-dashed border-gray-800 rounded-xl">
          <p className="text-gray-500">No products found for this niche.</p>
        </div>
      )}

      {selectedProduct && (
        <ProductModal
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
        />
      )}
    </div>
  );
};