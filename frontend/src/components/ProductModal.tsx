import { useState } from 'react';
import {
  X,
  ExternalLink,
  Sparkles,
  DollarSign,
  TrendingUp,
  Percent,
  Zap,
  Package,
  Loader2,
  ShoppingBag,
  AlertCircle,
  Star,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import { productsAPI } from '../services/api';

interface ProductModalProps {
  product: {
    id: string;
    name: string;
    price: number;
    cost?: number;
    velocity_score?: number;
    niche?: string;
    image_url?: string;
    supplier_url?: string;
    aliexpress_url?: string;
    profit_margin?: number;
    estimated_profit?: number;
    score?: number;
    rating?: number;
    orders?: number;
    description?: string;
  };
  onClose: () => void;
}

// Utility: Format niche name
function formatNiche(niche?: string): string {
  if (!niche) return 'General';
  return niche.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// Utility: Sanitize image URL
function sanitizeImageUrl(url?: string, productName?: string): string {
  if (!url) {
    const text = encodeURIComponent(productName?.substring(0, 20) || 'Product');
    return `https://placehold.co/400x400/1f2937/9ca3af?text=${text}`;
  }
  return url.replace(/^http:\/\//i, 'https://');
}

export default function ProductModal({ product, onClose }: ProductModalProps) {
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Calculate metrics
  const price = product.price || 0;
  const cost = product.cost || 0;
  const profit = product.estimated_profit ?? (price - cost);
  const margin = product.profit_margin ?? (price > 0 ? ((price - cost) / price) * 100 : 0);
  const velocity = product.velocity_score || 0;
  const aiScore = product.score ?? 0;
  const supplierUrl = product.aliexpress_url || product.supplier_url;
  const isProfitable = profit > 0;

  const analyzeProduct = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await productsAPI.analyze(product.id);
      setAnalysis(response);
    } catch (err: any) {
      console.error('Analysis failed:', err);
      setError(err.message || 'Analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Get recommendation color
  const getRecommendationStyle = (rec?: string) => {
    switch (rec) {
      case 'STRONG_BUY': return 'bg-green-500 text-white';
      case 'BUY': return 'bg-cyan-500 text-white';
      case 'HOLD': return 'bg-amber-500 text-black';
      case 'AVOID': return 'bg-red-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 border border-white/10 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ============ HEADER ============ */}
        <div className="relative p-6 border-b border-white/10">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/10 transition"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>

          <div className="flex gap-4">
            {/* Image */}
            <div className="w-24 h-24 rounded-xl overflow-hidden bg-gray-800 flex-shrink-0">
              <img
                src={sanitizeImageUrl(product.image_url, product.name)}
                alt={product.name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.src = `https://placehold.co/400x400/1f2937/9ca3af?text=No+Image`;
                }}
              />
            </div>

            {/* Title & Info */}
            <div className="flex-1 min-w-0">
              <h2 className="text-xl font-bold text-white leading-tight mb-2">
                {product.name}
              </h2>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-purple-500/20 text-purple-300 text-xs font-medium rounded-full">
                  <Package className="w-3 h-3" />
                  {formatNiche(product.niche)}
                </span>
                {product.rating && (
                  <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-500/20 text-amber-300 text-xs font-medium rounded-full">
                    <Star className="w-3 h-3 fill-current" />
                    {product.rating.toFixed(1)}
                  </span>
                )}
                {product.orders && (
                  <span className="text-xs text-gray-400">
                    {product.orders.toLocaleString()} orders
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ============ METRICS GRID ============ */}
        <div className="p-6 border-b border-white/10">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {/* AI Score */}
            <div className="text-center p-4 bg-white/5 rounded-xl">
              <div className="flex justify-center mb-2">
                <Star className="w-5 h-5 text-cyan-400" />
              </div>
              <div className="text-2xl font-bold text-cyan-400">
                {aiScore.toFixed(1)}
              </div>
              <div className="text-xs text-gray-400 mt-1">AI Score</div>
            </div>

            {/* Cost */}
            <div className="text-center p-4 bg-white/5 rounded-xl">
              <div className="flex justify-center mb-2">
                <ShoppingBag className="w-5 h-5 text-gray-400" />
              </div>
              <div className="text-2xl font-bold text-white">
                ${cost.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400 mt-1">Your Cost</div>
            </div>

            {/* Profit */}
            <div className={`text-center p-4 rounded-xl ${isProfitable ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
              <div className="flex justify-center mb-2">
                <TrendingUp className={`w-5 h-5 ${isProfitable ? 'text-green-400' : 'text-red-400'}`} />
              </div>
              <div className={`text-2xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                ${profit.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400 mt-1">Est. Profit</div>
            </div>

            {/* Margin */}
            <div className={`text-center p-4 rounded-xl ${margin >= 30 ? 'bg-cyan-500/10' : 'bg-amber-500/10'}`}>
              <div className="flex justify-center mb-2">
                <Percent className={`w-5 h-5 ${margin >= 30 ? 'text-cyan-400' : 'text-amber-400'}`} />
              </div>
              <div className={`text-2xl font-bold ${margin >= 30 ? 'text-cyan-400' : 'text-amber-400'}`}>
                {margin.toFixed(0)}%
              </div>
              <div className="text-xs text-gray-400 mt-1">Margin</div>
            </div>
          </div>

          {/* Velocity Bar */}
          {velocity > 0 && (
            <div className="mt-4 p-4 bg-white/5 rounded-xl">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-purple-400" />
                  <span className="text-sm font-medium text-gray-300">Market Velocity</span>
                </div>
                <span className="text-lg font-bold text-purple-400">{velocity}</span>
              </div>
              <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, velocity)}%` }}
                />
              </div>
            </div>
          )}

          {/* Product Description */}
          {product.description && (
            <div className="mt-4 p-4 bg-white/5 rounded-xl">
              <p className="text-sm text-gray-300 leading-relaxed">
                {product.description}
              </p>
            </div>
          )}

          {/* Warning if not profitable */}
          {!isProfitable && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-300">Low Profit Margin</p>
                <p className="text-xs text-red-400/80 mt-1">
                  Consider adjusting your sell price to improve profitability.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ============ AI ANALYSIS SECTION ============ */}
        <div className="p-6 border-b border-white/10">
          {!analysis && !loading && (
            <button
              onClick={analyzeProduct}
              className="w-full py-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2 shadow-lg"
            >
              <Sparkles className="w-5 h-5" />
              Deep Analysis with AI
            </button>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center gap-3 py-8">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
              <span className="text-gray-300 font-medium">Analyzing product...</span>
              <span className="text-gray-500 text-sm">This may take a few seconds</span>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-center">
              <p className="text-red-300">{error}</p>
              <button
                onClick={analyzeProduct}
                className="mt-2 text-sm text-red-400 hover:text-red-300 underline"
              >
                Try again
              </button>
            </div>
          )}

          {analysis && (
            <div className="space-y-4">
              {/* AI Score & Recommendation */}
              <div className="flex items-center justify-between p-5 bg-gradient-to-r from-gray-800 to-gray-900 rounded-xl border border-white/5">
                <div>
                  <p className="text-gray-400 text-sm mb-1">AI Analysis Score</p>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-white">{analysis.score?.toFixed(1) || aiScore.toFixed(1)}</span>
                    <span className="text-xl text-gray-500">/10</span>
                  </div>
                </div>
                <div className={`px-4 py-2 rounded-lg font-bold text-sm ${getRecommendationStyle(analysis.recommendation)}`}>
                  {analysis.recommendation?.replace('_', ' ') || 'PENDING'}
                </div>
              </div>

              {/* Analysis Text */}
              {analysis.analysis && (
                <div className="p-4 bg-white/5 rounded-xl">
                  <p className="text-gray-300 text-sm leading-relaxed">{analysis.analysis}</p>
                </div>
              )}

              {/* Success Prediction */}
              {analysis.success_prediction && (
                <div className="p-4 bg-cyan-500/10 rounded-xl flex items-center gap-3">
                  <TrendingUp className="w-5 h-5 text-cyan-400" />
                  <div>
                    <span className="text-sm text-gray-300">Success Prediction: </span>
                    <span className="text-cyan-400 font-bold">{analysis.success_prediction}</span>
                  </div>
                </div>
              )}

              {/* Reasoning */}
              {analysis.reasoning?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-white mb-3 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    Why This Product Wins
                  </h4>
                  <div className="space-y-2">
                    {analysis.reasoning.map((reason: string, i: number) => (
                      <div key={i} className="flex gap-3 p-3 bg-green-500/10 rounded-lg">
                        <span className="text-green-400 mt-0.5">✓</span>
                        <p className="text-sm text-gray-300">{reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risks */}
              {analysis.risks?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-white mb-3 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    Risks to Consider
                  </h4>
                  <div className="space-y-2">
                    {analysis.risks.map((risk: string, i: number) => (
                      <div key={i} className="flex gap-3 p-3 bg-amber-500/10 rounded-lg">
                        <span className="text-amber-400 mt-0.5">!</span>
                        <p className="text-sm text-gray-300">{risk}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ============ ACTION FOOTER ============ */}
        <div className="p-6 flex gap-3">
          <button className="flex-1 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-xl font-semibold transition flex items-center justify-center gap-2">
            <ShoppingBag className="w-5 h-5" />
            Deploy to Shopify
          </button>
          {supplierUrl && (
            <a
              href={supplierUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 border border-white/20 hover:border-white/40 hover:bg-white/5 rounded-xl font-medium transition flex items-center gap-2 text-gray-300"
            >
              <ExternalLink className="w-5 h-5" />
              AliExpress
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
