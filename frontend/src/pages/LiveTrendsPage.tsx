import { useState, useEffect } from 'react';
import axios from 'axios';
import { TrendingUp, RefreshCw, AlertCircle, Flame } from 'lucide-react';
import { ProductCard } from '../components/ProductCard';

interface TrendingProduct {
  id: string;
  name: string;
  velocity_score: number;
  trend_score: number;
  score: number;
  niche: string;
  price: number;
  cost: number;
  profit_margin: number;
  platform_badges?: any[];
}

export default function LiveTrendsPage() {
  const [products, setProducts] = useState<TrendingProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTrends = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post('http://localhost:8001/api/intelligence/discover', {
        query: 'trending products',
        max_results: 24,
        sources: ['google_trends', 'tiktok_shop', 'amazon']
      });

      if (response.data.success && response.data.products) {
        // Sort by velocity score
        const sorted = response.data.products.sort((a: any, b: any) =>
          (b.velocity_score || 0) - (a.velocity_score || 0)
        );
        setProducts(sorted);
      }
    } catch (err) {
      console.error('Failed to fetch trends:', err);
      setError('Failed to load trending products');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrends();
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-xl text-gray-300">Discovering trending products...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-center bg-red-500/10 border border-red-500/20 rounded-xl p-8 max-w-md">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          <h2 className="text-2xl font-bold mb-2 text-red-400">Error</h2>
          <p className="text-gray-300 mb-4">{error}</p>
          <button
            onClick={fetchTrends}
            className="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-semibold transition"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 text-white">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-1">
              <Flame className="inline w-8 h-8 text-orange-500 mr-2" />
              Live Trends
            </h1>
            <p className="text-gray-400">Real-time trending products from multiple sources</p>
          </div>
          <button
            onClick={fetchTrends}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-500/50 font-semibold transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh Trends
          </button>
        </div>

        {products.length === 0 ? (
          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl p-12 text-center shadow-xl">
            <TrendingUp className="w-16 h-16 mx-auto mb-4 text-gray-500" />
            <p className="text-gray-300 text-lg">No trending products found</p>
            <button
              onClick={fetchTrends}
              className="mt-4 px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold"
            >
              Discover Trends
            </button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {products.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onAnalyze={() => {}}
                />
              ))}
            </div>
            <div className="mt-6 text-center text-gray-400">
              Showing {products.length} trending products
            </div>
          </>
        )}
      </div>
    </div>
  );
}
