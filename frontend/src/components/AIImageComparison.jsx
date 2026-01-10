/**
 * AI Image Mode Comparison Tool
 * =============================
 * Side-by-side comparison of all AI image generation modes.
 * 
 * Lets you see the difference between:
 * - Text Only (DALL-E from title)
 * - Vision Enhanced (GPT-4V analyzes → DALL-E generates)
 * - Image Transform (Stability AI img2img)
 */

import React, { useState, useEffect } from 'react';
import {
  Sparkles, Loader2, X, Eye, Wand2, Camera, Check, AlertTriangle,
  DollarSign, Clock, Target, ChevronRight, RefreshCw, Star, Info,
  Zap, Brain, Image as ImageIcon, ArrowRight, ExternalLink
} from 'lucide-react';

// Mode metadata
const MODE_INFO = {
  text_only: {
    name: 'Text Only',
    provider: 'DALL-E 3',
    icon: Wand2,
    color: 'blue',
    description: 'Generates from product title only',
    pros: ['Fast (~3s)', 'Cheapest ($0.04)'],
    cons: ['May not match actual product', 'Doesn\'t see original image'],
    best_for: 'Generic lifestyle shots when product accuracy isn\'t critical'
  },
  vision_enhanced: {
    name: 'Vision Enhanced',
    provider: 'GPT-4V + DALL-E 3',
    icon: Eye,
    color: 'purple',
    description: 'AI analyzes your image, then generates matching styled version',
    pros: ['Good product match', 'Understands product details'],
    cons: ['More expensive ($0.07)', 'Slower (~8s)'],
    best_for: 'When you need AI to understand the product before generating'
  },
  img2img: {
    name: 'Image Transform',
    provider: 'Stability AI',
    icon: Camera,
    color: 'green',
    description: 'Transforms original while keeping product structure',
    pros: ['Best accuracy', 'Keeps exact shape', 'Cheap ($0.03)'],
    cons: ['Requires Stability API key', 'Medium speed (~5s)'],
    best_for: 'Best overall choice - keeps product but improves styling'
  }
};

// Color classes for each mode
const MODE_COLORS = {
  text_only: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    badge: 'bg-blue-500/20 text-blue-300'
  },
  vision_enhanced: {
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    text: 'text-purple-400',
    badge: 'bg-purple-500/20 text-purple-300'
  },
  img2img: {
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    text: 'text-green-400',
    badge: 'bg-green-500/20 text-green-300'
  }
};

/**
 * Comparison Result Card
 */
function ComparisonCard({ mode, result, originalUrl, isRecommended }) {
  const [imageError, setImageError] = useState(false);
  const info = MODE_INFO[mode];
  const colors = MODE_COLORS[mode];
  const Icon = info?.icon || Sparkles;
  
  if (!result) return null;
  
  return (
    <div className={`backdrop-blur-xl rounded-2xl border overflow-hidden transition-all ${
      isRecommended 
        ? `${colors.bg} ${colors.border} ring-2 ring-offset-2 ring-offset-black ring-${colors.text.split('-')[1]}-500/50` 
        : 'bg-white/5 border-white/10'
    }`}>
      {/* Header */}
      <div className={`p-4 border-b ${colors.border}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl ${colors.bg}`}>
              <Icon className={`w-5 h-5 ${colors.text}`} />
            </div>
            <div>
              <h3 className="text-white font-semibold">{info?.name || mode}</h3>
              <p className="text-white/50 text-xs">{info?.provider}</p>
            </div>
          </div>
          {isRecommended && (
            <div className="px-3 py-1 rounded-full bg-yellow-500/20 text-yellow-300 text-xs font-medium flex items-center gap-1">
              <Star className="w-3 h-3" />
              Recommended
            </div>
          )}
        </div>
      </div>
      
      {/* Image */}
      <div className="aspect-square bg-gradient-to-br from-white/5 to-white/0 relative">
        {result.success && result.ai_image_url && !imageError ? (
          <img 
            src={result.ai_image_url}
            alt={`${mode} result`}
            className="w-full h-full object-contain"
            onError={() => setImageError(true)}
          />
        ) : result.success ? (
          <div className="w-full h-full flex items-center justify-center flex-col gap-2">
            <ImageIcon className="w-12 h-12 text-white/20" />
            <p className="text-white/40 text-sm">Image generated but URL unavailable</p>
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center flex-col gap-3 p-4">
            <AlertTriangle className="w-12 h-12 text-red-400/50" />
            <p className="text-red-300/70 text-sm text-center">{result.error || 'Generation failed'}</p>
          </div>
        )}
        
        {/* Mode Badge */}
        <div className={`absolute top-3 left-3 px-2 py-1 rounded-full text-xs font-medium ${colors.badge}`}>
          {info?.name}
        </div>
      </div>
      
      {/* Stats */}
      <div className="p-4 space-y-3">
        {result.success ? (
          <>
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/50 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Time
              </span>
              <span className="text-white font-medium">{result.time_seconds}s</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/50 flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                Cost
              </span>
              <span className="text-green-400 font-medium">{result.estimated_cost}</span>
            </div>
            {result.note && (
              <p className="text-white/40 text-xs italic">{result.note}</p>
            )}
          </>
        ) : (
          <p className="text-red-300/70 text-sm">Generation failed - check API keys</p>
        )}
      </div>
      
      {/* Best For */}
      {info?.best_for && result.success && (
        <div className={`px-4 py-3 border-t ${colors.border} ${colors.bg}`}>
          <p className={`text-xs ${colors.text}`}>
            <strong>Best for:</strong> {info.best_for}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Main Comparison Tool Component
 */
export function AIImageComparison({ 
  product = null, 
  onClose = null,
  isModal = false 
}) {
  const [productTitle, setProductTitle] = useState(product?.title || '');
  const [productNiche, setProductNiche] = useState(product?.niche || 'smart_home');
  const [originalImageUrl, setOriginalImageUrl] = useState(product?.image_url || '');
  const [comparing, setComparing] = useState(false);
  const [results, setResults] = useState(null);
  const [availableModes, setAvailableModes] = useState([]);
  const [error, setError] = useState(null);
  
  // Check available modes on mount
  useEffect(() => {
    checkAvailableModes();
  }, []);
  
  // Update form when product prop changes
  useEffect(() => {
    if (product) {
      setProductTitle(product.title || '');
      setProductNiche(product.niche || 'smart_home');
      setOriginalImageUrl(product.image_url || '');
    }
  }, [product]);
  
  const checkAvailableModes = async () => {
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/images/compare/status`);
      const data = await response.json();
      setAvailableModes(data.modes || []);
    } catch (e) {
      console.error('Failed to check modes:', e);
      setAvailableModes([]);
    }
  };
  
  const runComparison = async () => {
    if (!productTitle.trim()) {
      setError('Please enter a product title');
      return;
    }
    
    setComparing(true);
    setError(null);
    setResults(null);
    
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/images/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_title: productTitle,
          niche: productNiche,
          original_image_url: originalImageUrl || null
        })
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data = await response.json();
      setResults(data);
      
    } catch (e) {
      console.error('Comparison failed:', e);
      setError(e.message || 'Comparison failed. Check API connection.');
    } finally {
      setComparing(false);
    }
  };
  
  const content = (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20">
              <Sparkles className="w-6 h-6 text-purple-400" />
            </div>
            AI Image Mode Comparison
          </h2>
          <p className="text-white/50 mt-1">
            Compare all generation modes side-by-side to find what works best
          </p>
        </div>
        {isModal && onClose && (
          <button 
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-white/10 text-white/60 hover:text-white"
          >
            <X className="w-6 h-6" />
          </button>
        )}
      </div>
      
      {/* Mode Info Cards */}
      {!results && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(MODE_INFO).map(([modeId, info]) => {
            const colors = MODE_COLORS[modeId];
            const Icon = info.icon;
            const isAvailable = availableModes.some(m => m.id === modeId);
            
            return (
              <div 
                key={modeId}
                className={`p-4 rounded-xl border transition-all ${
                  isAvailable 
                    ? `${colors.bg} ${colors.border}` 
                    : 'bg-white/5 border-white/10 opacity-50'
                }`}
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className={`p-2 rounded-lg ${colors.bg}`}>
                    <Icon className={`w-5 h-5 ${colors.text}`} />
                  </div>
                  <div>
                    <h3 className="text-white font-semibold text-sm">{info.name}</h3>
                    <p className="text-white/40 text-xs">{info.provider}</p>
                  </div>
                  {!isAvailable && (
                    <span className="ml-auto px-2 py-1 rounded text-xs bg-red-500/20 text-red-300">
                      Not configured
                    </span>
                  )}
                </div>
                <p className="text-white/60 text-xs mb-3">{info.description}</p>
                <div className="space-y-1">
                  {info.pros.map((pro, i) => (
                    <p key={i} className="text-green-400/70 text-xs flex items-center gap-1">
                      <Check className="w-3 h-3" /> {pro}
                    </p>
                  ))}
                  {info.cons.map((con, i) => (
                    <p key={i} className="text-red-400/70 text-xs flex items-center gap-1">
                      <X className="w-3 h-3" /> {con}
                    </p>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      
      {/* Input Form */}
      <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <Target className="w-5 h-5 text-purple-400" />
          Test Product
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-white/60 text-sm mb-2 block">Product Title *</label>
            <input
              type="text"
              value={productTitle}
              onChange={(e) => setProductTitle(e.target.value)}
              placeholder="e.g., Smart LED Desk Lamp with USB Charging"
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50"
            />
          </div>
          
          <div>
            <label className="text-white/60 text-sm mb-2 block">Category</label>
            <select
              value={productNiche}
              onChange={(e) => setProductNiche(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50"
            >
              <option value="smart_home">Smart Home</option>
              <option value="kitchen">Kitchen</option>
              <option value="fitness">Fitness</option>
              <option value="beauty">Beauty</option>
              <option value="tech">Tech</option>
              <option value="home_decor">Home Decor</option>
              <option value="outdoor">Outdoor</option>
              <option value="pet">Pet</option>
            </select>
          </div>
          
          <div className="md:col-span-2">
            <label className="text-white/60 text-sm mb-2 block">
              Original Image URL 
              <span className="text-yellow-400/70 ml-2">(Required for Vision & Img2Img modes)</span>
            </label>
            <input
              type="url"
              value={originalImageUrl}
              onChange={(e) => setOriginalImageUrl(e.target.value)}
              placeholder="https://ae-pic-a1.aliexpress-media.com/..."
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50"
            />
          </div>
        </div>
        
        {/* Original Image Preview */}
        {originalImageUrl && (
          <div className="mt-4 flex items-center gap-4">
            <div className="w-20 h-20 rounded-xl overflow-hidden bg-white/5 border border-white/10">
              <img 
                src={originalImageUrl} 
                alt="Original" 
                className="w-full h-full object-cover"
                onError={(e) => e.target.style.display = 'none'}
              />
            </div>
            <div>
              <p className="text-white/60 text-sm">Original Image</p>
              <p className="text-white/40 text-xs">This will be analyzed/transformed by AI</p>
            </div>
          </div>
        )}
        
        {error && (
          <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
            {error}
          </div>
        )}
        
        {/* Run Button */}
        <button
          onClick={runComparison}
          disabled={comparing || !productTitle.trim()}
          className="mt-6 w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
        >
          {comparing ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Generating All Modes... (This may take 15-20 seconds)
            </>
          ) : (
            <>
              <Zap className="w-5 h-5" />
              Compare All AI Modes
              <ChevronRight className="w-5 h-5" />
            </>
          )}
        </button>
        
        {/* Cost Warning */}
        <p className="text-white/40 text-xs text-center mt-3">
          Estimated total cost: ~$0.14 (testing all 3 modes)
        </p>
      </div>
      
      {/* Results */}
      {results && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-white font-semibold">Comparison Complete</h3>
                <p className="text-white/50 text-sm">
                  {results.modes_tested?.length || 0} modes tested • Total cost: {results.total_cost}
                </p>
              </div>
              {results.recommendation && (
                <div className="px-4 py-2 rounded-xl bg-yellow-500/10 border border-yellow-500/20">
                  <p className="text-yellow-300 text-sm font-medium flex items-center gap-2">
                    <Star className="w-4 h-4" />
                    Recommended: {MODE_INFO[results.recommendation.best_match]?.name}
                  </p>
                  <p className="text-yellow-200/60 text-xs">{results.recommendation.reason}</p>
                </div>
              )}
            </div>
          </div>
          
          {/* Side-by-Side Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Original Image */}
            <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-white/10">
                    <ImageIcon className="w-5 h-5 text-white/60" />
                  </div>
                  <div>
                    <h3 className="text-white font-semibold">Original</h3>
                    <p className="text-white/50 text-xs">Supplier Image</p>
                  </div>
                </div>
              </div>
              <div className="aspect-square bg-gradient-to-br from-white/5 to-white/0">
                {results.original_image_url ? (
                  <img 
                    src={results.original_image_url}
                    alt="Original"
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center flex-col gap-2">
                    <ImageIcon className="w-12 h-12 text-white/20" />
                    <p className="text-white/40 text-sm">No original provided</p>
                  </div>
                )}
              </div>
              <div className="p-4">
                <p className="text-white/40 text-xs">
                  This is the original supplier image before AI enhancement
                </p>
              </div>
            </div>
            
            {/* AI Generated Results */}
            {Object.entries(results.comparisons || {}).map(([mode, result]) => (
              <ComparisonCard
                key={mode}
                mode={mode}
                result={result}
                originalUrl={results.original_image_url}
                isRecommended={results.recommendation?.best_match === mode}
              />
            ))}
          </div>
          
          {/* Reset Button */}
          <div className="text-center">
            <button
              onClick={() => setResults(null)}
              className="px-6 py-3 rounded-xl bg-white/10 text-white hover:bg-white/20 transition-colors flex items-center gap-2 mx-auto"
            >
              <RefreshCw className="w-4 h-4" />
              Test Another Product
            </button>
          </div>
        </div>
      )}
    </div>
  );
  
  // Render as modal or standalone
  if (isModal) {
    return (
      <>
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" onClick={onClose} />
        <div className="fixed inset-4 md:inset-10 bg-[#0a0a0f]/95 backdrop-blur-xl border border-white/10 rounded-2xl z-50 overflow-y-auto p-6">
          {content}
        </div>
      </>
    );
  }
  
  return content;
}

export default AIImageComparison;
