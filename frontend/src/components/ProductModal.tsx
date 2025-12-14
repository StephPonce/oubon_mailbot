import { useState } from 'react';
import axios from 'axios';
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
} from 'lucide-react';

interface ProductModalProps {
  product: {
    id: string;
    name: string;
    price: number;         // Customer pays this
    cost?: number;         // You pay this
    velocity_score?: number;
    niche?: string;
    image_url?: string;
    supplier_url?: string;
    aliexpress_url?: string;
    profit_margin?: number;
    estimated_profit?: number;
    score?: number;        // 0-10 Ospra score (pre-calculated)
    rating?: number;
    orders?: number;
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

  // Enhanced debugging - complete product inspection
  console.log('ProductModal received:', product);
  console.log('image_url:', product.image_url);
  console.log('velocity_score:', product.velocity_score);
  console.log('score:', product.score);
  console.log('price:', product.price, 'cost:', product.cost, 'estimated_profit:', product.estimated_profit);

  // Calculate metrics with fallbacks
  const customerPrice = product.price || 0;
  const yourCost = product.cost || 0;
  const profit = product.estimated_profit ?? (customerPrice - yourCost);
  const margin = product.profit_margin ?? (customerPrice > 0 ? ((customerPrice - yourCost) / customerPrice) * 100 : 0);
  const velocity = product.velocity_score || 0;
  const supplierUrl = product.aliexpress_url || product.supplier_url;

  // Determine if this product is profitable
  const isProfitable = profit > 0;

  console.log('Calculated metrics:', {
    customerPrice,
    yourCost,
    profit,
    margin,
    velocity,
    isProfitable
  });

  const analyzeProduct = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post(
        `http://127.0.0.1:8001/api/dashboard/v2/products/${product.id}/analyze`
      );
      setAnalysis(response.data);
    } catch (err) {
      console.error('Analysis failed:', err);
      setError('Analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ============ HEADER ============ */}
        <div className="relative p-6 border-b border-white/10">
          {/* Close Button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 rounded-full hover:bg-gray-100 transition"
          >
            <X className="w-5 h-5 text-tertiary" />
          </button>

          {/* Product Info */}
          <div className="flex gap-4">
            {/* Image */}
            <div className="w-24 h-24 rounded-xl overflow-hidden bg-gray-100 flex-shrink-0">
              <img
                src={sanitizeImageUrl(product.image_url, product.name)}
                alt={product.name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  console.error('Image load failed:', {
                    original_url: product.image_url,
                    fallback_url: e.currentTarget.src
                  });
                  e.currentTarget.src = `https://placehold.co/400x400/1f2937/9ca3af?text=No+Image`;
                }}
              />
            </div>

            {/* Title & Niche */}
            <div className="flex-1 min-w-0">
              <h2 className="text-xl font-bold text-primary leading-tight mb-2">
                {product.name}
              </h2>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-700 text-xs font-medium rounded-full">
                  <Package className="w-3 h-3" />
                  {formatNiche(product.niche)}
                </span>
                <span className="text-xs text-tertiary">via AliExpress</span>
              </div>
            </div>
          </div>
        </div>

        {/* ============ METRICS GRID ============ */}
        <div className="p-6 border-b border-white/10">
          <div className="grid grid-cols-4 gap-4">
            {/* Customer Price */}
            <div className="text-center p-4   rounded-xl">
              <div className="flex justify-center mb-2">
                <DollarSign className="w-5 h-5 text-secondary" />
              </div>
              <div className="text-2xl font-bold text-primary">
                ${customerPrice.toFixed(2)}
              </div>
              <div className="text-xs text-tertiary mt-1">Sell Price</div>
            </div>

            {/* Your Cost */}
            <div className="text-center p-4   rounded-xl">
              <div className="flex justify-center mb-2">
                <ShoppingBag className="w-5 h-5 text-secondary" />
              </div>
              <div className="text-2xl font-bold text-primary">
                ${yourCost.toFixed(2)}
              </div>
              <div className="text-xs text-tertiary mt-1">Your Cost</div>
            </div>

            {/* Profit */}
            <div className={`text-center p-4 rounded-xl ${isProfitable ? 'bg-green-500/100/10' : 'bg-red-500/10'}`}>
              <div className="flex justify-center mb-2">
                <TrendingUp className={`w-5 h-5 ${isProfitable ? 'text-green-600' : 'text-red-600'}`} />
              </div>
              <div className={`text-2xl font-bold ${isProfitable ? 'text-green-600' : 'text-red-600'}`}>
                ${profit.toFixed(2)}
              </div>
              <div className="text-xs text-tertiary mt-1">Est. Profit</div>
            </div>

            {/* Margin */}
            <div className={`text-center p-4 rounded-xl ${margin >= 30 ? 'bg-cyan-500/10' : 'bg-amber-500/10'}`}>
              <div className="flex justify-center mb-2">
                <Percent className={`w-5 h-5 ${margin >= 30 ? 'text-blue-600' : 'text-yellow-600'}`} />
              </div>
              <div className={`text-2xl font-bold ${margin >= 30 ? 'text-blue-600' : 'text-yellow-600'}`}>
                {margin.toFixed(0)}%
              </div>
              <div className="text-xs text-tertiary mt-1">Margin</div>
            </div>
          </div>

          {/* Velocity Bar */}
          <div className="mt-4 p-4   rounded-xl">
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-secondary">Market Velocity</span>
              </div>
              <span className="text-lg font-bold text-purple-600">{velocity}/100</span>
            </div>
            <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-500"
                style={{ width: `${velocity}%` }}
              />
            </div>
          </div>

          {/* Warning if not profitable */}
          {!isProfitable && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-200 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">Low Profit Margin</p>
                <p className="text-xs text-red-600 mt-1">
                  This product may not be profitable at current pricing. Consider adjusting your sell price.
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
              className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-purple-700 transition-all flex items-center justify-center gap-2 shadow-lg"
            >
              <Sparkles className="w-5 h-5" />
              Deep Analysis with Claude AI
            </button>
          )}

          {loading && (
            <div className="flex items-center justify-center gap-3 py-8">
              <Loader2 className="w-6 h-6 text-purple-600 animate-spin" />
              <span className="text-secondary font-medium">Claude is analyzing this product...</span>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-200 rounded-xl text-center">
              <p className="text-red-600">{error}</p>
              <button
                onClick={analyzeProduct}
                className="mt-2 text-sm text-red-700 underline"
              >
                Try again
              </button>
            </div>
          )}

          {analysis && (
            <div className="space-y-4">
              {/* AI Score Hero */}
              <div className="flex items-center justify-between p-6 bg-gradient-to-r from-gray-900 to-gray-800 rounded-xl">
                <div>
                  <p className="text-tertiary text-sm">AI Score</p>
                  <div className="flex items-baseline gap-1">
                    <span className="text-5xl font-bold text-white">{analysis.score || 0}</span>
                    <span className="text-2xl text-tertiary">/10</span>
                  </div>
                </div>
                <div className={`px-4 py-2 rounded-lg font-bold ${
                  analysis.recommendation === 'STRONG_BUY' ? 'bg-green-500/100 text-white' :
                  analysis.recommendation === 'BUY' ? 'bg-cyan-500/100 text-white' :
                  analysis.recommendation === 'HOLD' ? 'bg-amber-500/100 text-primary' :
                  'bg-red-500/100 text-white'
                }`}>
                  {analysis.recommendation?.replace('_', ' ') || 'PENDING'}
                </div>
              </div>

              {/* Reasoning */}
              {analysis.reasoning?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-primary mb-3">✨ Why This Product Wins</h4>
                  <div className="space-y-2">
                    {analysis.reasoning.map((reason: string, i: number) => (
                      <div key={i} className="flex gap-2 p-3 bg-green-500/100/10 rounded-lg">
                        <span className="text-green-500">✓</span>
                        <p className="text-sm text-secondary">{reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risks */}
              {analysis.risks?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-primary mb-3">⚠️ Risks to Consider</h4>
                  <div className="space-y-2">
                    {analysis.risks.map((risk: string, i: number) => (
                      <div key={i} className="flex gap-2 p-3 bg-amber-500/10 rounded-lg">
                        <span className="text-yellow-500">!</span>
                        <p className="text-sm text-secondary">{risk}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ============ ACTION FOOTER ============ */}
        <div className="p-6   flex gap-3">
          <button className="flex-1 py-3 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl font-semibold transition flex items-center justify-center gap-2">
            <ShoppingBag className="w-5 h-5" />
            Deploy to Shopify
          </button>
          {supplierUrl && (
            <a
              href={supplierUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 border border-white/10 hover:border-gray-400 rounded-xl font-medium transition flex items-center gap-2"
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
