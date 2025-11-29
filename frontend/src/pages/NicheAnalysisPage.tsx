import { useState, useEffect } from 'react';
import axios from 'axios';
import { Target, RefreshCw, AlertCircle, TrendingUp, BarChart } from 'lucide-react';
import { GlassPanel } from '@/components/GlassPanel';

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
      <div className="min-h-screen bg-gray-50 p-12 flex items-center justify-center" style={{ perspective: '1500px' }}>
        <GlassPanel depth={60} delay={0}>
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
            <p className="text-gray-600 font-light">Loading niche data...</p>
          </div>
        </GlassPanel>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-12 flex items-center justify-center" style={{ perspective: '1500px' }}>
        <GlassPanel depth={60} delay={0}>
          <div className="text-center p-8 max-w-md">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-600" />
            <h2 className="text-2xl font-light mb-2 text-gray-900">Error</h2>
            <p className="text-gray-600 mb-4">{error}</p>
            <button
              onClick={fetchNiches}
              className="px-6 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg font-light transition"
            >
              Try Again
            </button>
          </div>
        </GlassPanel>
      </div>
    );
  }

  const trendingNiches = niches.filter(n => n.trending);
  const stableNiches = niches.filter(n => !n.trending);

  return (
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-8">
        <GlassPanel depth={80} delay={0.1}>
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-light text-gray-900 mb-1">
                Niche Analysis
              </h1>
              <p className="text-gray-600">Market opportunities and niche performance insights</p>
            </div>
            <button
              onClick={fetchNiches}
              className="flex items-center gap-2 px-4 py-2 bg-white/50 border border-gray-200 text-gray-700 rounded-lg hover:bg-white transition"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </GlassPanel>

        {/* Trending Niches */}
        {trendingNiches.length > 0 && (
          <div>
            <h2 className="text-xl font-light text-gray-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-green-600" />
              Trending Niches
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {trendingNiches.map((niche, idx) => (
                <GlassPanel key={niche.id} depth={65} delay={0.15 + idx * 0.05}>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-lg font-light text-gray-900">{niche.name}</h3>
                    <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-500/20 text-green-700 text-xs font-light rounded-full">
                      <TrendingUp className="w-3 h-3" />
                      HOT
                    </span>
                  </div>
                  <p className="text-gray-600 text-sm mb-4">High growth potential with increasing demand</p>
                  <button className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-light transition">
                    Explore Products
                  </button>
                </GlassPanel>
              ))}
            </div>
          </div>
        )}

        {/* Stable Niches */}
        {stableNiches.length > 0 && (
          <div>
            <h2 className="text-xl font-light text-gray-900 mb-4 flex items-center gap-2">
              <BarChart className="w-6 h-6 text-blue-600" />
              Stable Markets
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {stableNiches.map((niche, idx) => (
                <GlassPanel key={niche.id} depth={60} delay={0.2 + idx * 0.05}>
                  <h3 className="text-lg font-light text-gray-900 mb-3">{niche.name}</h3>
                  <p className="text-gray-600 text-sm mb-4">Consistent demand with steady growth</p>
                  <button className="w-full px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg font-light transition">
                    View Analysis
                  </button>
                </GlassPanel>
              ))}
            </div>
          </div>
        )}

        {niches.length === 0 && (
          <GlassPanel depth={60} delay={0.3}>
            <div className="p-12 text-center">
              <Target className="w-16 h-16 mx-auto mb-4 text-gray-400 opacity-30" />
              <p className="text-gray-600 text-lg font-light">No niche data available</p>
            </div>
          </GlassPanel>
        )}
      </div>
    </div>
  );
};
