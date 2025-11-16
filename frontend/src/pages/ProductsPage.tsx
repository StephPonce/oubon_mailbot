import { useState, useEffect } from 'react';
import ProductCard from '../components/ProductCard';
import ProductModal from '../components/ProductModal';
import axios from 'axios';

interface Product {
  id: string;
  name: string;
  price: number;
  cost: number;
  profit_margin: number;
  estimated_profit: number;
  velocity_score: number;
  score: number;
  orders: number;
  rating: number;
  niche: string;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [niche, setNiche] = useState('smart_home');
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [dataSource, setDataSource] = useState('');
  const [sortBy, setSortBy] = useState('velocity_score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchProducts = async (forceDiscovery = false) => {
    setLoading(true);
    try {
      if (forceDiscovery) {
        // Use test discovery endpoint for fresh product discovery
        const response = await axios.get(`http://localhost:8000/api/products/test-discovery`, {
          params: { niche, max_products: 20 }
        });

        if (response.data.success && response.data.products) {
          setProducts(response.data.products);
          setDataSource('REAL_TIME_DISCOVERY');
          setLastRefresh(new Date());
          return;
        }
      }

      // Fallback to regular V2 endpoint
      const response = await axios.get(`http://localhost:8000/api/dashboard/v2/products`, {
        params: { niche, per_page: 20 }
      });
      setProducts(response.data.products || []);
      setDataSource(response.data.data_source || 'Database Cache');
      setLastRefresh(new Date());
    } catch (error) {
      console.error('Failed to fetch:', error);
      setProducts([]);
      setDataSource('Error');
    } finally {
      setLoading(false);
    }
  };

  const discoverProducts = async () => {
    await fetchProducts(true);
  };

  useEffect(() => {
    // Trigger fresh discovery whenever niche changes
    fetchProducts(true);
  }, [niche]);

  const sortedProducts = [...products].sort((a, b) => {
    const aVal = a[sortBy as keyof Product] as number;
    const bVal = b[sortBy as keyof Product] as number;
    return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
  });

  const filteredProducts = sortedProducts.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Product Intelligence
        </h1>

        <div className={`inline-block px-3 py-1 rounded-full text-sm font-bold mb-4 ${
          dataSource.includes('REAL_TIME') ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
        }`}>
          📡 {dataSource.includes('REAL_TIME') ? 'Real-Time Data Active' : 'Fallback Mode'}
        </div>

        <div className="flex gap-4 items-center flex-wrap">
          <button
            onClick={() => fetchProducts(true)}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 font-semibold"
          >
            {loading ? 'Discovering...' : '🔄 Discover Fresh Products'}
          </button>

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
              onClick={() => setSelectedProduct(product)}
            />
          ))}
        </div>
      )}

      {!loading && products.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg mb-4">
            No products found for "{niche.replace('_', ' ')}"
          </p>
          <p className="text-gray-400 text-sm mb-6">
            The database doesn't have products for this niche yet.
          </p>
          <button
            onClick={discoverProducts}
            className="px-6 py-3 bg-blue-600 text-white rounded hover:bg-blue-700 font-semibold inline-flex items-center gap-2"
          >
            <span>🔍</span>
            Discover Products for {niche.replace('_', ' ')}
          </button>
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
}
