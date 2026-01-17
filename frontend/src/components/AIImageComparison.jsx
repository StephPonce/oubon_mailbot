/**
 * AI Image Enhancer for Oubon Shop
 * =================================
 * Simple component to enhance product images.
 * Removes ugly backgrounds, adds clean professional ones.
 */

import React, { useState, useEffect } from 'react';
import {
  Sparkles, Loader2, X, Check, AlertTriangle,
  DollarSign, Clock, RefreshCw, ImageIcon, Wand2
} from 'lucide-react';

// Background style options
const BACKGROUND_STYLES = {
  clean_white: { name: 'Clean White', description: 'Pure white - classic e-commerce' },
  soft_gray: { name: 'Soft Gray', description: 'Light gray for subtle contrast' },
  warm_gradient: { name: 'Warm Gradient', description: 'Soft warm tones - premium feel' },
  cool_gradient: { name: 'Cool Gradient', description: 'Cool tones - tech/modern feel' },
  lifestyle_shadow: { name: 'White + Shadow', description: 'White with soft shadow' }
};

/**
 * Main Image Enhancer Component
 */
export function AIImageEnhancer({ 
  product = null, 
  onClose = null,
  onImageEnhanced = null,
  isModal = false 
}) {
  const [imageUrl, setImageUrl] = useState(product?.image_url || '');
  const [niche, setNiche] = useState(product?.niche || 'smart_home');
  const [backgroundStyle, setBackgroundStyle] = useState('');
  const [enhancing, setEnhancing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [apiAvailable, setApiAvailable] = useState(true);
  
  // Check API status on mount
  useEffect(() => {
    checkStatus();
  }, []);
  
  // Update when product changes
  useEffect(() => {
    if (product) {
      setImageUrl(product.image_url || '');
      setNiche(product.niche || 'smart_home');
      setResult(null);
    }
  }, [product]);
  
  const checkStatus = async () => {
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/images/status`);
      const data = await response.json();
      setApiAvailable(data.available);
    } catch (e) {
      setApiAvailable(false);
    }
  };
  
  const enhanceImage = async () => {
    if (!imageUrl.trim()) {
      setError('Please enter an image URL');
      return;
    }
    
    setEnhancing(true);
    setError(null);
    setResult(null);
    
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/images/enhance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_url: imageUrl,
          niche: niche,
          background_style: backgroundStyle || null,
          add_shadow: true
        })
      });
      
      const data = await response.json();
      setResult(data);
      
      // Callback if provided
      if (data.success && onImageEnhanced) {
        onImageEnhanced(data.enhanced_image_url);
      }
      
    } catch (e) {
      setError(e.message || 'Enhancement failed');
    } finally {
      setEnhancing(false);
    }
  };
  
  const content = (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20">
              <Wand2 className="w-6 h-6 text-purple-400" />
            </div>
            Enhance Product Image
          </h2>
          <p className="text-white/50 mt-1">
            Remove ugly backgrounds • Add clean professional styling
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
      
      {/* API Status */}
      {!apiAvailable && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <div>
            <p className="text-red-300 font-medium">Enhancement Unavailable</p>
            <p className="text-red-300/70 text-sm">Stability API key not configured in Render</p>
          </div>
        </div>
      )}
      
      {/* How It Works */}
      <div className="p-4 rounded-xl bg-white/5 border border-white/10">
        <h3 className="text-white font-semibold mb-3">How It Works</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="p-3 rounded-lg bg-white/5">
            <div className="text-2xl mb-2">📸</div>
            <p className="text-white/60 text-sm">Original supplier image</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5">
            <div className="text-2xl mb-2">✂️</div>
            <p className="text-white/60 text-sm">AI removes background</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5">
            <div className="text-2xl mb-2">✨</div>
            <p className="text-white/60 text-sm">Clean professional result</p>
          </div>
        </div>
        <p className="text-white/40 text-xs text-center mt-3">
          Product stays exactly the same • Only background changes • ~$0.06 per image
        </p>
      </div>
      
      {/* Input Form */}
      <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6 space-y-4">
        {/* Image URL */}
        <div>
          <label className="text-white/60 text-sm mb-2 block">Product Image URL</label>
          <input
            type="url"
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            placeholder="https://aliexpress.com/product-image.jpg"
            className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50"
          />
        </div>
        
        {/* Preview */}
        {imageUrl && (
          <div className="flex justify-center">
            <div className="w-32 h-32 rounded-xl overflow-hidden bg-white/5 border border-white/10">
              <img 
                src={imageUrl} 
                alt="Preview"
                className="w-full h-full object-contain"
                onError={(e) => e.target.style.display = 'none'}
              />
            </div>
          </div>
        )}
        
        {/* Options Row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Niche */}
          <div>
            <label className="text-white/60 text-sm mb-2 block">Category</label>
            <select
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50"
            >
              <option value="smart_home">🏠 Smart Home</option>
              <option value="kitchen">🍳 Kitchen</option>
              <option value="tech">💻 Tech</option>
              <option value="fitness">💪 Fitness</option>
              <option value="beauty">✨ Beauty</option>
              <option value="home_decor">🛋️ Home Decor</option>
              <option value="outdoor">🏕️ Outdoor</option>
              <option value="pet">🐾 Pet</option>
            </select>
          </div>
          
          {/* Background Style Override */}
          <div>
            <label className="text-white/60 text-sm mb-2 block">Background (optional)</label>
            <select
              value={backgroundStyle}
              onChange={(e) => setBackgroundStyle(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50"
            >
              <option value="">Auto (based on category)</option>
              {Object.entries(BACKGROUND_STYLES).map(([key, style]) => (
                <option key={key} value={key}>{style.name}</option>
              ))}
            </select>
          </div>
        </div>
        
        {error && (
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
            {error}
          </div>
        )}
        
        {/* Enhance Button */}
        <button
          onClick={enhanceImage}
          disabled={enhancing || !imageUrl.trim() || !apiAvailable}
          className="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
        >
          {enhancing ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Enhancing... (3-5 seconds)
            </>
          ) : (
            <>
              <Wand2 className="w-5 h-5" />
              Enhance Image
            </>
          )}
        </button>
        
        <p className="text-white/40 text-xs text-center">
          Cost: ~$0.06 • Product stays exactly the same • Only background changes
        </p>
      </div>
      
      {/* Result */}
      {result && (
        <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            {result.success ? (
              <><Check className="w-5 h-5 text-green-400" /> Enhancement Complete</>
            ) : (
              <><AlertTriangle className="w-5 h-5 text-red-400" /> Enhancement Failed</>
            )}
          </h3>
          
          {result.success ? (
            <div className="space-y-4">
              {/* Before/After Comparison */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-white/60 text-sm mb-2 text-center">Original</p>
                  <div className="aspect-square rounded-xl overflow-hidden bg-white/5 border border-white/10">
                    <img 
                      src={result.original_url}
                      alt="Original"
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>
                <div>
                  <p className="text-white/60 text-sm mb-2 text-center">Enhanced</p>
                  <div className="aspect-square rounded-xl overflow-hidden bg-white/5 border border-green-500/30">
                    <img 
                      src={result.enhanced_image_url}
                      alt="Enhanced"
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>
              </div>
              
              {/* Stats */}
              <div className="flex items-center justify-center gap-6 text-sm">
                <span className="text-white/50 flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  {result.processing_time}s
                </span>
                <span className="text-green-400 flex items-center gap-2">
                  <DollarSign className="w-4 h-4" />
                  {result.estimated_cost}
                </span>
                <span className="text-purple-400">
                  {result.background_name}
                </span>
              </div>
              
              {/* Actions */}
              <div className="flex gap-3">
                <button
                  onClick={() => setResult(null)}
                  className="flex-1 py-3 rounded-xl bg-white/10 text-white hover:bg-white/20 flex items-center justify-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Enhance Another
                </button>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20">
              <p className="text-red-300">{result.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
  
  // Render as modal or standalone
  if (isModal) {
    return (
      <>
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" onClick={onClose} />
        <div className="fixed inset-4 md:inset-10 lg:inset-20 bg-[#0a0a0f]/95 backdrop-blur-xl border border-white/10 rounded-2xl z-50 overflow-y-auto p-6">
          {content}
        </div>
      </>
    );
  }
  
  return content;
}

// Keep old name for backwards compatibility
export const AIImageComparison = AIImageEnhancer;
export default AIImageEnhancer;
