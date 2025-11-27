import { useState, useEffect } from 'react';
import axios from 'axios';
import { Trophy, RefreshCw, AlertCircle, TrendingUp, Medal } from 'lucide-react';
import StoreRankingsTable from '../components/portfolio/StoreRankingsTable';

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

export default function RankingsPage() {
  const [rankings, setRankings] = useState<StoreRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRankings = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('http://localhost:8001/api/portfolio/rankings');
      setRankings(response.data);
    } catch (err) {
      console.error('Failed to fetch rankings:', err);
      setError('Failed to load store rankings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRankings();
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-xl text-gray-300">Loading rankings...</p>
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
            onClick={fetchRankings}
            className="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-semibold transition"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const topStore = rankings[0];

  return (
    <div className="p-6 text-white">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-1">
              <Trophy className="inline w-8 h-8 text-yellow-500 mr-2" />
              Store Rankings
            </h1>
            <p className="text-gray-400">Performance leaderboard across all your stores</p>
          </div>
          <button
            onClick={fetchRankings}
            className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Top Performer Card */}
        {topStore && (
          <div className="mb-6 bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 rounded-xl p-6 shadow-xl">
            <div className="flex items-center gap-4">
              <Medal className="w-12 h-12 text-yellow-500" />
              <div className="flex-1">
                <h3 className="text-sm text-gray-400 uppercase tracking-wide mb-1">Top Performer</h3>
                <h2 className="text-2xl font-bold text-white">{topStore.store_name}</h2>
                <p className="text-gray-300">{topStore.platform} • {topStore.product_count} products</p>
              </div>
              <div className="text-right">
                <div className="text-3xl font-bold text-green-400">${topStore.monthly_revenue.toFixed(2)}</div>
                <div className="text-sm text-gray-400">Monthly Revenue</div>
              </div>
            </div>
          </div>
        )}

        {/* Rankings Table */}
        {rankings.length > 0 ? (
          <StoreRankingsTable stores={rankings} />
        ) : (
          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl p-12 text-center shadow-xl">
            <TrendingUp className="w-16 h-16 mx-auto mb-4 text-gray-500" />
            <p className="text-gray-300 text-lg">No stores to rank yet</p>
            <p className="text-gray-500 mt-2">Add stores to see performance rankings</p>
          </div>
        )}
      </div>
    </div>
  );
}
