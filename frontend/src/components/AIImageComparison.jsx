/**
 * AI Image Mode Comparison Tool - V3
 * ===================================
 * Side-by-side comparison of all AI image generation modes.
 * 
 * V3 Features:
 * - Multi-image support (feed up to 3 images for vision_enhanced)
 * - View prompts used for generation
 * - Better error details
 * - Niche-specific styling info
 */

import React, { useState, useEffect } from 'react';
import {
  Sparkles, Loader2, X, Eye, Wand2, Camera, Check, AlertTriangle,
  DollarSign, Clock, Target, ChevronRight, RefreshCw, Star, Info,
  Zap, Brain, Image as ImageIcon, ArrowRight, ExternalLink, Plus,
  FileText, Trash2, ChevronDown, ChevronUp
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
    best_for: 'Generic lifestyle shots when product accuracy isn\'t critical',
    supports_multi_image: false
  },
  vision_enhanced: {
    name: 'Vision Enhanced',
    provider: 'GPT-4V + DALL-E 3',
    icon: Eye,
    color: 'purple',
    description: 'AI analyzes up to 3 product images, then generates matching styled version',
    pros: ['Good product match', 'Analyzes multiple angles', 'Understands product details'],
    cons: ['More expensive ($0.07)', 'Slower (~8s)'],
    best_for: 'When you need AI to understand the product before generating',
    supports_multi_image: true
  },
  img2img: {
    name: 'Image Transform',
    provider: 'Stability AI',
    icon: Camera,
    color: 'green',
    description: 'Transforms original while keeping product structure',
    pros: ['Best accuracy', 'Keeps exact shape', 'Cheap ($0.03)'],
    cons: ['Requires Stability API key', 'Medium speed (~5s)'],
    best_for: 'Best overall choice - keeps product but improves styling',
    supports_multi_image: false
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

// Niche options
const NICHE_OPTIONS = [
  { value: 'smart_home', label: 'Smart Home', emoji: '🏠' },
  { value: 'kitchen', label: 'Kitchen', emoji: '🍳' },
  { value: 'fitness', label: 'Fitness', emoji: '💪' },
  { value: 'beauty', label: 'Beauty', emoji: '✨' },
  { value: 'tech', label: 'Tech', emoji: '💻' },
  { value: 'home_decor', label: 'Home Decor', emoji: '🛋️' },
  { value: 'outdoor', label: 'Outdoor', emoji: '🏕️' },
  { value: 'pet', label: 'Pet', emoji: '🐾' }
];

/**
 * Comparison Result Card with expandable prompt view
 */
function ComparisonCard({ mode, result, originalUrl, isRecommended }) {
  const [imageError, setImageError] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  
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
        
        {/* Images Analyzed Badge */}
        {result.images_analyzed > 1 && (
          <div className="absolute top-3 right-3 px-2 py-1 rounded-full text-xs font-medium bg-purple-500/30 text-purple-200">
            {result.images_analyzed} images analyzed
          </div>
        )}
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
      
      {/* Expandable: Product Analysis (for vision mode) */}
      {result.product_analysis && (
        <div className={`border-t ${colors.border}`}>
          <button
            onClick={() => setShowAnalysis(!showAnalysis)}
            className="w-full px-4 py-3 flex items-center justify-between text-sm hover:bg-white/5"
          >
            <span className="text-purple-300 flex items-center gap-2">
              <Brain className="w-4 h-4" />
              AI Product Analysis
            </span>
            {showAnalysis ? <ChevronUp className="w-4 h-4 text-white/40" /> : <ChevronDown className="w-4 h-4 text-white/40" />}
          </button>
          {showAnalysis && (
            <div className="px-4 pb-4">
              <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/20">
                <p className="text-white/70 text-xs whitespace-pre-wrap">{result.product_analysis}</p>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Expandable: Prompt Used */}
      {result.prompt_preview && (
        <div className={`border-t ${colors.border}`}>
          <button
            onClick={() => setShowPrompt(!showPrompt)}
            className="w-full px-4 py-3 flex items-center justify-between text-sm hover:bg-white/5"
          >
            <span className="text-white/60 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              View Prompt Used
            </span>
            {showPrompt ? <ChevronUp className="w-4 h-4 text-white/40" /> : <ChevronDown className="w-4 h-4 text-white/40" />}
          </button>
          {showPrompt && (
            <div className="px-4 pb-4">
              <div className="p-3 rounded-xl bg-white/5 border border-white/10 max-h-40 overflow-y-auto">
                <p className="text-white/60 text-xs font-mono whitespace-pre-wrap">{result.prompt_preview}</p>
              </div>
            </div>
          )}
        </div>
      )}
      
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
 * Multi-Image URL Input Component
 */
function MultiImageInput({ images, onChange, maxImages = 3 }) {
  const addImage = () => {
    if (images.length < maxImages) {
      onChange([...images, '']);
    }
  };
  
  const updateImage = (index, value) => {
    const newImages = [...images];
    newImages[index] = value;
    onChange(newImages);
  };
  
  const removeImage = (index) => {
    onChange(images.filter((_, i) => i !== index));
  };
  
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-white/60 text-sm flex items-center gap-2">
          Product Image URLs
          <span className="text-purple-400">({images.filter(u => u).length}/{maxImages})</span>
        </label>
        {images.length < maxImages && (
          <button
            onClick={addImage}
            className="text-purple-400 text-sm hover:text-purple-300 flex items-center gap-1"
          >
            <Plus className="w-4 h-4" />
            Add Image
          </button>
        )}
      </div>
      
      {images.map((url, index) => (
        <div key={index} className="flex items-center gap-2">
          <div className="flex-1 relative">
            <input
              type="url"
              value={url}
              onChange={(e) => updateImage(index, e.target.value)}
              placeholder={index === 0 ? "Primary image URL (required for Vision/Img2Img)" : `Additional angle ${index + 1} (optional)`}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50 pr-12"
            />
            {url && (
              <div className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg overflow-hidden bg-white/10">
                <img 
                  src={url} 
                  alt={`Preview ${index + 1}`}
                  className="w-full h-full object-cover"
                  onError={(e) => e.target.style.display = 'none'}
                />
              </div>
            )}
          </div>
          {index > 0 && (
            <button
              onClick={() => removeImage(index)}
              className="p-2 rounded-lg hover:bg-red-500/20 text-red-400"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}
      
      <p className="text-white/40 text-xs">
        💡 <strong>Tip:</strong> Vision Enhanced mode can analyze up to 3 images for better accuracy. 
        Add different angles of the same product for best results.
      </p>
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
  const [imageUrls, setImageUrls] = useState([product?.image_url || '']);
  const [comparing, setComparing] = useState(false);
  const [results, setResults] = useState(null);
  const [availableModes, setAvailableModes] = useState([]);
  const [apiKeyStatus, setApiKeyStatus] = useState({});
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
      
      // Collect all available images from product - prioritize all_images from backend
      let urls = [];
      
      if (product.all_images && Array.isArray(product.all_images) && product.all_images.length > 0) {
        // Use pre-collected images from backend (up to 3 for AI)
        urls = product.all_images.slice(0, 3);
      } else {
        // Fallback: build from various fields
        if (product.image_url) urls.push(product.image_url);
        if (product.additional_images) urls.push(...product.additional_images.slice(0, 2));
        if (product.images) urls.push(...product.images.slice(0, 3 - urls.length));
      }
      
      setImageUrls(urls.length > 0 ? urls : ['']);
    }
  }, [product]);
  
  const checkAvailableModes = async () => {
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/images/compare/status`);
      const data = await response.json();
      setAvailableModes(data.modes || []);
      setApiKeyStatus(data.api_keys_status || {});
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
    
    // Filter valid URLs
    const validUrls = imageUrls.filter(url => url.trim());
    const primaryUrl = validUrls[0] || null;
    const additionalUrls = validUrls.slice(1);
    
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/images/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_title: productTitle,
          niche: productNiche,
          original_image_url: primaryUrl,
          additional_image_urls: additionalUrls.length > 0 ? additionalUrls : null
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
            Compare all generation modes side-by-side • Multi-image support enabled
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
      
      {/* API Status Banner */}
      {Object.keys(apiKeyStatus).length > 0 && (
        <div className="p-4 rounded-xl bg-white/5 border border-white/10 flex items-center gap-4">
          <Info className="w-5 h-5 text-blue-400" />
          <div className="flex-1 flex items-center gap-4 text-sm">
            <span className="text-white/60">API Status:</span>
            {Object.entries(apiKeyStatus).map(([key, status]) => (
              <span key={key} className={status.includes('✅') ? 'text-green-400' : 'text-red-400'}>
                {key}: {status}
              </span>
            ))}
          </div>
        </div>
      )}
      
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
                  {info.supports_multi_image && (
                    <span className="ml-auto px-2 py-1 rounded text-xs bg-purple-500/20 text-purple-300">
                      Multi-Image
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
                {!isAvailable && (
                  <p className="mt-3 text-red-300/70 text-xs">
                    ❌ Not configured - add API key in Render
                  </p>
                )}
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
        
        <div className="space-y-4">
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
              <label className="text-white/60 text-sm mb-2 block">Category (affects styling)</label>
              <select
                value={productNiche}
                onChange={(e) => setProductNiche(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50"
              >
                {NICHE_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>
                    {opt.emoji} {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          
          {/* Multi-Image Input */}
          <MultiImageInput 
            images={imageUrls}
            onChange={setImageUrls}
            maxImages={3}
          />
        </div>
        
        {/* Image Previews */}
        {imageUrls.some(url => url) && (
          <div className="mt-4 flex items-center gap-4 overflow-x-auto pb-2">
            {imageUrls.filter(url => url).map((url, index) => (
              <div key={index} className="flex-shrink-0">
                <div className="w-20 h-20 rounded-xl overflow-hidden bg-white/5 border border-white/10">
                  <img 
                    src={url} 
                    alt={`Preview ${index + 1}`}
                    className="w-full h-full object-cover"
                    onError={(e) => e.target.parentElement.innerHTML = '<div class="w-full h-full flex items-center justify-center text-white/30 text-xs">Error</div>'}
                  />
                </div>
                <p className="text-white/40 text-xs text-center mt-1">
                  {index === 0 ? 'Primary' : `Angle ${index + 1}`}
                </p>
              </div>
            ))}
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
          Estimated total cost: ~$0.14 (testing all 3 modes) • Images provided: {imageUrls.filter(u => u).length}
        </p>
      </div>
      
      {/* Results */}
      {results && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <h3 className="text-white font-semibold">Comparison Complete</h3>
                <p className="text-white/50 text-sm">
                  {results.modes_tested?.length || 0} modes tested • 
                  {results.total_images || 1} image(s) provided • 
                  Total cost: {results.total_cost}
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
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
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
                {results.additional_images_provided > 0 && (
                  <p className="text-purple-400 text-xs mt-2">
                    +{results.additional_images_provided} additional image(s) analyzed
                  </p>
                )}
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
