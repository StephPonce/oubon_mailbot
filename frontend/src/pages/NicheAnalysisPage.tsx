import { useState, useEffect } from 'react';
import axios from 'axios';
import { Target, RefreshCw, AlertCircle, TrendingUp, BarChart } from 'lucide-react';

interface Niche {
  id: string;
  name: string;
  trending: boolean;
}

export const NicheAnalysisPage = () => {
  const [niches, setNiches] = useState<Niche[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNiches = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('http://localhost:8001/api/dashboard/v2/niches');
      setNiches(response.data.niches || []);
    } catch (err) {
      console.error('Failed to fetch niches:', err);
      setError('Failed to load niche data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNiches();
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-xl text-gray-300">Loading niche data...</p>
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
            onClick={fetchNiches}
            className="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-semibold transition"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const trendingNiches = niches.filter(n => n.trending);
  const stableNiches = niches.filter(n => !n.trending);

  return (
    <div className="p-6 text-white">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-1">
              <Target className="inline w-8 h-8 text-purple-500 mr-2" />
              Niche Analysis
            </h1>
            <p className="text-gray-400">Market opportunities and niche performance insights</p>
          </div>
          <button
            onClick={fetchNiches}
            className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Trending Niches */}
        {trendingNiches.length > 0 && (
          <div className="mb-6">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-green-500" />
              Trending Niches
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {trendingNiches.map((niche) => (
                <div
                  key={niche.id}
                  className="bg-gradient-to-br from-green-500/10 to-blue-500/10 border border-green-500/20 rounded-xl p-6 shadow-xl hover:shadow-2xl transition-all hover:scale-105"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-lg font-bold text-white">{niche.name}</h3>
                    <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-500/20 text-green-300 text-xs font-bold rounded-full">
                      <TrendingUp className="w-3 h-3" />
                      HOT
                    </span>
                  </div>
                  <p className="text-gray-400 text-sm mb-4">High growth potential with increasing demand</p>
                  <button className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg font-semibold transition">
                    Explore Products
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stable Niches */}
        {stableNiches.length > 0 && (
          <div>
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <BarChart className="w-6 h-6 text-blue-500" />
              Stable Markets
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {stableNiches.map((niche) => (
                <div
                  key={niche.id}
                  className="bg-white/5 border border-white/10 rounded-xl p-6 shadow-xl hover:shadow-2xl transition-all hover:bg-white/10"
                >
                  <h3 className="text-lg font-bold text-white mb-3">{niche.name}</h3>
                  <p className="text-gray-400 text-sm mb-4">Consistent demand with steady growth</p>
                  <button className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold transition">
                    View Analysis
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {niches.length === 0 && (
          <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl p-12 text-center shadow-xl">
            <Target className="w-16 h-16 mx-auto mb-4 text-gray-500" />
            <p className="text-gray-300 text-lg">No niche data available</p>
          </div>
        )}
      </div>
    </div>
  );
};
