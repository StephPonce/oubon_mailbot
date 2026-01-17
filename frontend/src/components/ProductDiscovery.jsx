/**
 * OSPRA INTELLIGENCE - PRODUCT DISCOVERY
 * ======================================
 * v5 - Jan 2025: FIXED - Real scores, image toggle, auto-analysis
 * 
 * FIXES:
 * - Image toggle between AI generated and original supplier images
 * - Auto-generate AI analysis when opening product detail
 * - Fixed regenerate image button
 * - Shows "estimated" label when scores are defaults
 * - All images array shown in detail view
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Search, Package, TrendingUp, Rocket, BarChart3, Tag, Loader2, Filter, 
  ArrowRight, Eye, AlertTriangle, RefreshCw, X, ExternalLink, Brain,
  ShoppingCart, Copy, Check, ChevronRight, Star, Link2, Database, 
  Zap, Target, Sparkles, DollarSign, Camera, Wand2, MessageSquare,
  ImageIcon, ToggleLeft, ToggleRight, Info, ChevronLeft
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useDashboardContext } from '../hooks/useDashboardContext';
import { api } from '../services/api';
import { PageLayout } from './Layout';
import { AIImageComparison } from './AIImageComparison';

// ============================================================================
// HELPER: Normalize product data from any API source
// ============================================================================
function normalizeProduct(p, fallbackNiche = 'general') {
  const costPrice = parseFloat(p.cost_price || p.supplier_cost || p.targetSalePrice || p.price || 0);
  
  let suggestedPrice = parseFloat(p.suggested_price || 0);
  if (!suggestedPrice && costPrice > 0) {
    suggestedPrice = costPrice * 2.5;
  }
  
  let profit = parseFloat(p.profit || 0);
  if (!profit && suggestedPrice > 0 && costPrice > 0) {
    profit = suggestedPrice - costPrice;
  }
  
  // Collect ALL image URLs from backend
  const mainImage = p.image_url || p.imageUrl || p.image || p.main_image || p.productMainImageUrl || null;
  
  // PRIORITY: Use backend's all_images if available (from product_discovery.py V3)
  let allImages = [];
  if (p.all_images && Array.isArray(p.all_images) && p.all_images.length > 0) {
    allImages = [...p.all_images];
  } else {
    // Fallback: build from various fields
    if (mainImage) allImages.push(mainImage);
    
    // Add additional images if available
    if (p.images && Array.isArray(p.images)) {
      p.images.forEach(img => {
        const url = typeof img === 'string' ? img : img.url;
        if (url && !allImages.includes(url)) allImages.push(url);
      });
    }
    if (p.additional_images && Array.isArray(p.additional_images)) {
      p.additional_images.forEach(img => {
        if (img && !allImages.includes(img)) allImages.push(img);
      });
    }
  }
  
  // Image count from backend or calculated
  const imageCount = p.image_count || allImages.length;
  
  // Oi Score - the single unified score
  const oiScore = Math.round(p.oi_score || p.score || p.final_score || p.productScore || p.opportunity_score || 50);
  
  // Supplier link - check ALL possible field names
  const supplierUrl = p.affiliate_url || p.affiliateUrl || p.affiliate_link || p.affiliateLink || 
                      p.promotionLink || p.promotion_link || p.supplier_url || p.supplierUrl ||
                      p.product_url || p.productUrl || p.url || null;
  
  // Check if scores are REAL or DEFAULT (50 = default)
  const hasRealDemandScore = p.demand_score !== undefined && p.demand_score !== 50;
  const hasRealTrendScore = p.trend_score !== undefined && p.trend_score !== 50;
  const hasRealSentimentScore = p.sentiment_score !== undefined && p.sentiment_score !== 50;
  const hasAnyRealScores = hasRealDemandScore || hasRealTrendScore || hasRealSentimentScore || (p.sales_count > 0);
  
  // Score breakdown - mark as estimated if default
  const demandScore = p.demand_score || p.demandScore || 50;
  const trendScore = p.trend_score || p.trendScore || 50;
  const sentimentScore = p.sentiment_score || p.sentimentScore || 50;
  const viralScore = p.viral_score || p.viralScore || 50;
  const profitMargin = (suggestedPrice > 0 && costPrice > 0) ? Math.round((profit / suggestedPrice) * 100) : 50;
  const profitScore = p.profit_score || p.profitScore || Math.min(100, profitMargin * 1.5);
  
  return {
    id: p.id || p.product_id || `prod_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    title: p.title || p.name || p.product_title || 'Untitled Product',
    image_url: mainImage,
    ai_image_url: p.ai_image_url || null,
    all_images: allImages,
    image_count: imageCount,
    cost_price: parseFloat(costPrice.toFixed(2)),
    suggested_price: parseFloat(suggestedPrice.toFixed(2)),
    profit: parseFloat(profit.toFixed(2)),
    oi_score: oiScore,
    niche: p.niche || p.category || fallbackNiche,
    tags: p.tags || [p.niche || p.category || 'trending'],
    source: p.source || 'aliexpress',
    is_mock: p.is_mock || p.source === 'mock_data',
    supplier_url: supplierUrl,
    sales_count: p.sales_count || p.salesCount || p.productSalesCount || 0,
    rating: p.rating || null,
    // Score breakdown with estimation flag
    demand_score: demandScore,
    trend_score: trendScore,
    sentiment_score: sentimentScore,
    viral_score: viralScore,
    profit_score: profitScore,
    scores_estimated: !hasAnyRealScores,
    commission_rate: p.commission_rate || p.commissionRate || null,
    recommendation: p.recommendation || null,
    reasons: p.reasons || [],
    risks: p.risks || [],
    data_sources: p.data_sources || {},
    raw_data: p,
  };
}

// ============================================================================
// HELPER: Score colors
// ============================================================================
function getScoreColor(score) {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-cyan-400';
  if (score >= 40) return 'text-yellow-400';
  return 'text-red-400';
}

function getScoreBgColor(score) {
  if (score >= 80) return 'from-green-500/20 to-green-600/10 border-green-500/30';
  if (score >= 60) return 'from-cyan-500/20 to-cyan-600/10 border-cyan-500/30';
  if (score >= 40) return 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30';
  return 'from-red-500/20 to-red-600/10 border-red-500/30';
}

// ============================================================================
// COMPONENT: Product Card - CLICKABLE, Oi Score ONLY (no source badges)
// ============================================================================
function ProductCard({ product, onClick }) {
  const [imageError, setImageError] = useState(false);
  const displayImage = product.ai_image_url || product.image_url;
  const hasAiImage = !!product.ai_image_url;

  return (
    <div 
      onClick={onClick}
      className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 overflow-hidden hover:border-purple-500/40 hover:scale-[1.02] transition-all cursor-pointer group"
    >
      {/* Image */}
      <div className="aspect-square bg-gradient-to-br from-purple-500/10 to-cyan-500/10 relative overflow-hidden">
        {displayImage && !imageError ? (
          <img 
            src={displayImage} 
            alt={product.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package className="w-12 h-12 text-white/20" />
          </div>
        )}
        
        {/* AI Image Badge */}
        {hasAiImage && (
          <div className="absolute bottom-3 right-3 px-2 py-1 rounded-full bg-purple-500/80 text-white text-xs font-medium flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            AI
          </div>
        )}
        
        {/* Multi-Image Badge - shows when product has multiple source images */}
        {!hasAiImage && product.image_count > 1 && (
          <div className="absolute bottom-3 right-3 px-2 py-1 rounded-full bg-cyan-500/80 text-white text-xs font-medium flex items-center gap-1">
            <ImageIcon className="w-3 h-3" />
            {product.image_count}
          </div>
        )}
        
        {/* Estimated Score Warning */}
        {product.scores_estimated && (
          <div className="absolute top-3 left-3 px-2 py-1 rounded-full bg-yellow-500/80 text-black text-xs font-medium flex items-center gap-1" title="Scores are estimated - limited data available">
            <Info className="w-3 h-3" />
            Est.
          </div>
        )}
        
        {/* Oi Score Badge - THE ONLY BADGE ON CARDS */}
        <div className={`absolute top-3 right-3 px-3 py-2 rounded-xl bg-gradient-to-br ${getScoreBgColor(product.oi_score)} border backdrop-blur-sm`}>
          <div className="flex items-center gap-1.5">
            <Brain className="w-4 h-4 text-purple-400" />
            <span className={`text-lg font-bold ${getScoreColor(product.oi_score)}`}>{product.oi_score}</span>
          </div>
        </div>

        {/* Hover Overlay */}
        <div className="absolute inset-0 bg-purple-500/0 group-hover:bg-purple-500/10 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
          <div className="px-4 py-2 rounded-xl bg-black/80 backdrop-blur-sm text-white text-sm font-medium flex items-center gap-2">
            <Eye className="w-4 h-4" />
            View Details
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="text-white font-semibold mb-2 line-clamp-2 group-hover:text-purple-300 transition-colors text-sm">
          {product.title}
        </h3>
        
        {/* Pricing */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-white/50 text-sm line-through">${product.cost_price.toFixed(2)}</span>
          <span className="text-green-400 font-medium">${product.suggested_price.toFixed(2)}</span>
          <span className="text-purple-400 font-bold ml-auto">+${product.profit.toFixed(2)}</span>
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-3 text-xs text-white/50">
          {product.sales_count > 0 && (
            <span className="flex items-center gap-1">
              <ShoppingCart className="w-3 h-3" />
              {product.sales_count.toLocaleString()}
            </span>
          )}
          {product.rating && (
            <span className="flex items-center gap-1">
              <Star className="w-3 h-3 text-yellow-400" />
              {product.rating.toFixed(1)}
            </span>
          )}
          {product.commission_rate && (
            <span className="flex items-center gap-1 text-green-400">
              {product.commission_rate}% comm
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// COMPONENT: Image Gallery with Toggle
// ============================================================================
function ImageGallery({ product, aiImageUrl, onRegenerateAi, regenerating }) {
  const [showAiImage, setShowAiImage] = useState(!!aiImageUrl);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [imageError, setImageError] = useState(false);
  
  const allOriginalImages = product.all_images || [product.image_url].filter(Boolean);
  const currentOriginalImage = allOriginalImages[selectedImageIndex] || product.image_url;
  const displayImage = showAiImage && aiImageUrl ? aiImageUrl : currentOriginalImage;
  
  return (
    <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-white font-semibold flex items-center gap-2">
          <Camera className="w-4 h-4 text-purple-400" />
          Product Images
        </h4>
        
        <div className="flex items-center gap-2">
          {/* Image Type Toggle */}
          <button
            onClick={() => setShowAiImage(!showAiImage)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all ${
              showAiImage 
                ? 'bg-purple-500/20 border border-purple-500/30 text-purple-300'
                : 'bg-white/5 border border-white/10 text-white/60'
            }`}
          >
            {showAiImage ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
            {showAiImage ? 'AI Image' : 'Original'}
          </button>
          
          {/* Regenerate Button */}
          <button
            onClick={onRegenerateAi}
            disabled={regenerating}
            className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-cyan-600 text-white text-xs font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
          >
            {regenerating ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Wand2 className="w-3 h-3" />
                {aiImageUrl ? 'Regenerate' : 'Generate AI'}
              </>
            )}
          </button>
        </div>
      </div>
      
      {/* Main Image Display */}
      <div className="relative aspect-video rounded-xl overflow-hidden bg-gradient-to-br from-purple-500/10 to-cyan-500/10 mb-3">
        {displayImage && !imageError ? (
          <img 
            src={displayImage} 
            alt={product.title} 
            className="w-full h-full object-contain"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center flex-col gap-3">
            <Package className="w-16 h-16 text-white/20" />
            <p className="text-white/40 text-sm">No image available</p>
          </div>
        )}
        
        {/* Image Type Badge */}
        <div className={`absolute top-3 left-3 px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${
          showAiImage && aiImageUrl 
            ? 'bg-purple-500/80 text-white' 
            : 'bg-white/20 text-white/80'
        }`}>
          {showAiImage && aiImageUrl ? (
            <><Sparkles className="w-3 h-3" /> AI Generated</>
          ) : (
            <><ImageIcon className="w-3 h-3" /> Original</>
          )}
        </div>
      </div>
      
      {/* Thumbnail Strip (Original Images Only) */}
      {allOriginalImages.length > 1 && !showAiImage && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {allOriginalImages.map((img, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedImageIndex(idx)}
              className={`flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all ${
                selectedImageIndex === idx 
                  ? 'border-purple-500' 
                  : 'border-transparent opacity-60 hover:opacity-100'
              }`}
            >
              <img src={img} alt={`View ${idx + 1}`} className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}
      
      {/* AI Image Notice */}
      {!aiImageUrl && (
        <p className="text-white/40 text-xs mt-2 text-center">
          Click "Generate AI" to create a professional lifestyle photo (~$0.04)
          {allOriginalImages.length > 1 && (
            <span className="block text-cyan-400 mt-1">
              💡 {allOriginalImages.length} images available - use "Compare AI Modes" to analyze all angles
            </span>
          )}
        </p>
      )}
      
      {/* Comparison Note */}
      {aiImageUrl && (
        <p className="text-white/40 text-xs mt-2 text-center">
          Toggle between AI and Original to compare. AI images are styled for Oubon Shop branding.
        </p>
      )}
    </div>
  );
}

// ============================================================================
// COMPONENT: Product Detail Panel - Auto-analysis, image toggle
// ============================================================================
function ProductDetailPanel({ product, onClose, onDeploy, onUpdateProduct, onCompare }) {
  const [caption, setCaption] = useState('');
  const [deploying, setDeploying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generatingCaption, setGeneratingCaption] = useState(false);
  const [generatingAnalysis, setGeneratingAnalysis] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [currentAiImageUrl, setCurrentAiImageUrl] = useState(product.ai_image_url);
  const [analysisError, setAnalysisError] = useState(null);
  
  // AUTO-GENERATE ANALYSIS ON MOUNT
  useEffect(() => {
    generateSEOCaption();
    generateAIAnalysis(); // Auto-generate analysis when panel opens
  }, [product.id]);
  
  // Generate AI image for this specific product - FIXED
  const generateAiImage = async () => {
    setGeneratingImage(true);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/images/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_title: product.title,
          niche: product.niche || 'smart_home',
          original_image_url: product.image_url,
          tags: product.tags || [product.niche],
          force_regenerate: true  // Force new generation
        })
      });
      
      const data = await response.json();
      
      if (data.success && data.ai_image_url) {
        setCurrentAiImageUrl(data.ai_image_url);
        // Update parent if callback provided
        if (onUpdateProduct) {
          onUpdateProduct({ ...product, ai_image_url: data.ai_image_url });
        }
      } else {
        alert('Failed to generate AI image. ' + (data.error || 'Check if OPENAI_API_KEY is configured.'));
      }
    } catch (error) {
      console.error('AI image generation failed:', error);
      alert('AI image generation failed: ' + (error.message || 'Unknown error'));
    } finally {
      setGeneratingImage(false);
    }
  };

  // STABLE score breakdown - computed once, memoized
  const scoreBreakdown = useMemo(() => [
    { key: 'demand_score', label: 'Demand', icon: TrendingUp, color: 'text-green-400', value: product.demand_score, estimated: product.demand_score === 50 },
    { key: 'trend_score', label: 'Trend', icon: Zap, color: 'text-cyan-400', value: product.trend_score, estimated: product.trend_score === 50 },
    { key: 'sentiment_score', label: 'Sentiment', icon: MessageSquare, color: 'text-blue-400', value: product.sentiment_score, estimated: product.sentiment_score === 50 },
    { key: 'viral_score', label: 'Viral Potential', icon: Sparkles, color: 'text-pink-400', value: product.viral_score, estimated: product.viral_score === 50 },
    { key: 'profit_score', label: 'Profit Margin', icon: DollarSign, color: 'text-purple-400', value: product.profit_score, estimated: false },
  ], [product.demand_score, product.trend_score, product.sentiment_score, product.viral_score, product.profit_score]);

  const generateSEOCaption = async () => {
    setGeneratingCaption(true);
    try {
      const response = await api.generateCaption(product.title, product.niche, product.suggested_price);
      if (response.success && response.caption) {
        setCaption(response.caption);
      } else {
        setCaption(createProfessionalCaption(product));
      }
    } catch (error) {
      console.error('Caption generation failed:', error);
      setCaption(createProfessionalCaption(product));
    } finally {
      setGeneratingCaption(false);
    }
  };

  // PROFESSIONAL caption template - NO EMOJIS, NO HASHTAGS
  const createProfessionalCaption = (p) => {
    const cleanTitle = p.title
      .replace(/\b(hot sale|new|2024|2025|premium|quality|best|cheap)\b/gi, '')
      .replace(/\s+/g, ' ')
      .trim();
    const nicheFormatted = p.niche.replace(/_/g, ' ');
    
    return `${cleanTitle}

Transform your ${nicheFormatted} experience with this thoughtfully designed essential. Quality construction ensures reliability while the modern design complements any space.

Free shipping on orders over $50. 30-day hassle-free returns.`;
  };

  const generateAIAnalysis = async () => {
    setGeneratingAnalysis(true);
    setAnalysisError(null);
    
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/oi/analyze-product`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_id: product.id,
          product_title: product.title,
          product_data: {
            niche: product.niche,
            cost_price: product.cost_price,
            suggested_price: product.suggested_price,
            profit: product.profit,
            oi_score: product.oi_score,
            demand_score: product.demand_score,
            trend_score: product.trend_score,
            sentiment_score: product.sentiment_score,
            sales_count: product.sales_count,
            rating: product.rating,
            source: product.source,
            data_sources: product.data_sources,
            scores_estimated: product.scores_estimated,
          }
        })
      });
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success && data.analysis) {
        // Format the analysis nicely
        const a = data.analysis;
        const formatted = `VERDICT: ${a.verdict || 'N/A'} (${a.confidence || 0}% confidence)

SUMMARY
${a.summary || 'No summary available.'}

STRENGTHS
${(a.strengths || []).map(s => `• ${s}`).join('\n') || '• No specific strengths identified'}

RISKS
${(a.risks || []).map(r => `• ${r}`).join('\n') || '• Standard market risks apply'}

TARGET AUDIENCE
${a.target_audience || 'General consumers'}

MARKETING ANGLES
${(a.marketing_angles || []).map(m => `• ${m}`).join('\n') || '• Focus on product benefits'}

AD SPEND RECOMMENDATION
${a.ad_spend_recommendation || 'Start with $5-10/day'}

PRICE STRATEGY
${a.price_strategy || 'Current pricing appears competitive'}

COMPETITION
${a.competition_assessment || 'Moderate competition in this niche'}

SEASONAL FACTORS
${a.seasonal_factors || 'Year-round demand expected'}`;
        
        setAiAnalysis(formatted);
      } else {
        setAnalysisError('Analysis returned empty. API may not have Claude key configured.');
      }
    } catch (error) {
      console.error('AI Analysis failed:', error);
      setAnalysisError(`Analysis failed: ${error.message}. Check API connection.`);
    } finally {
      setGeneratingAnalysis(false);
    }
  };

  const copyCaption = () => {
    navigator.clipboard.writeText(caption);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDeploy = async () => {
    if (product.is_mock) {
      alert('Cannot deploy demo products. Connect APIs for real products.');
      return;
    }
    setDeploying(true);
    try {
      await onDeploy(product, caption);
      alert(`${product.title} deployed to Shopify!`);
      onClose();
    } catch (error) {
      alert('Deploy failed: ' + (error.message || 'Unknown error'));
    } finally {
      setDeploying(false);
    }
  };

  // Get data sources that are actually present
  const dataSources = product.data_sources || {};
  const activeSourceKeys = Object.keys(dataSources).filter(k => dataSources[k]?.available);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" onClick={onClose} />

      {/* Panel */}
      <div 
        className="fixed right-0 top-0 h-full w-full max-w-2xl bg-[#0a0a0f]/95 backdrop-blur-xl border-l border-white/10 z-50 overflow-y-auto"
        style={{ animation: 'slideIn 0.3s ease-out' }}
      >
        {/* Header */}
        <div className="sticky top-0 bg-[#0a0a0f]/90 backdrop-blur-xl border-b border-white/10 p-4 flex items-center justify-between z-10">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-purple-400" />
            Product Details
          </h2>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-white/10 text-white/60 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Image Gallery with Toggle */}
          <ImageGallery 
            product={product}
            aiImageUrl={currentAiImageUrl}
            onRegenerateAi={generateAiImage}
            regenerating={generatingImage}
          />
          
          {/* Compare AI Modes Button */}
          {product.image_url && onCompare && (
            <button
              onClick={() => onCompare(product)}
              className="w-full py-3 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 font-medium hover:bg-cyan-500/30 flex items-center justify-center gap-2 transition-all"
            >
              <Beaker className="w-5 h-5" />
              Compare All AI Image Modes
              <span className="text-cyan-400/60 text-sm">(~$0.14)</span>
            </button>
          )}

          {/* Product Title + Oi Score */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h3 className="text-lg font-bold text-white mb-4">{product.title}</h3>
            
            {/* Estimated Scores Warning */}
            {product.scores_estimated && (
              <div className="mb-4 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20 flex items-center gap-2">
                <Info className="w-4 h-4 text-yellow-400 flex-shrink-0" />
                <p className="text-yellow-200 text-sm">
                  Scores are estimated due to limited data. Connect more APIs for accurate metrics.
                </p>
              </div>
            )}
            
            {/* MAIN Oi Score */}
            <div className={`p-4 rounded-xl bg-gradient-to-br ${getScoreBgColor(product.oi_score)} border`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-black/30">
                    <Brain className="w-6 h-6 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-white/60 text-sm">Oi Score {product.scores_estimated && <span className="text-yellow-400">(Est.)</span>}</p>
                    <p className={`text-3xl font-bold ${getScoreColor(product.oi_score)}`}>{product.oi_score}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-white/40 text-xs">out of 100</p>
                  <p className={`text-sm font-medium ${getScoreColor(product.oi_score)}`}>
                    {product.oi_score >= 80 ? 'Excellent' : product.oi_score >= 60 ? 'Good' : product.oi_score >= 40 ? 'Fair' : 'Poor'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Oi Score Breakdown */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-4 flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              Score Breakdown
            </h4>
            
            <div className="space-y-3">
              {scoreBreakdown.map((item) => {
                const Icon = item.icon;
                const value = Math.min(100, Math.max(0, item.value || 0));
                return (
                  <div key={item.key} className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-white/5">
                      <Icon className={`w-4 h-4 ${item.color}`} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-white/70 text-sm">
                          {item.label}
                          {item.estimated && <span className="text-yellow-400 text-xs ml-1">(Est.)</span>}
                        </span>
                        <span className={`font-bold ${item.color}`}>{value}</span>
                      </div>
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full bg-gradient-to-r ${
                            value >= 80 ? 'from-green-500 to-green-400' :
                            value >= 60 ? 'from-cyan-500 to-cyan-400' :
                            value >= 40 ? 'from-yellow-500 to-yellow-400' :
                            'from-red-500 to-red-400'
                          }`}
                          style={{ width: `${value}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Quick Recommendation */}
            <div className={`mt-4 p-3 rounded-xl ${
              product.oi_score >= 70 ? 'bg-green-500/10 border border-green-500/20' :
              product.oi_score >= 50 ? 'bg-yellow-500/10 border border-yellow-500/20' :
              'bg-red-500/10 border border-red-500/20'
            }`}>
              <p className={`text-sm font-medium ${
                product.oi_score >= 70 ? 'text-green-300' :
                product.oi_score >= 50 ? 'text-yellow-300' :
                'text-red-300'
              }`}>
                {product.recommendation || (
                  product.oi_score >= 70 ? 'HIGH OPPORTUNITY: Strong buy signal based on demand and trend data' :
                  product.oi_score >= 50 ? 'MODERATE: Worth testing with a small budget' :
                  'LOW POTENTIAL: Consider skipping this product'
                )}
              </p>
            </div>
          </div>

          {/* AI Analysis Section - AUTO-LOADED */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-white font-semibold flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-400" />
                AI Analysis
                {generatingAnalysis && <Loader2 className="w-4 h-4 animate-spin text-purple-400" />}
              </h4>
              <button
                onClick={generateAIAnalysis}
                disabled={generatingAnalysis}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {generatingAnalysis ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                  </>
                )}
              </button>
            </div>
            
            {generatingAnalysis && !aiAnalysis ? (
              <div className="p-8 text-center">
                <Loader2 className="w-8 h-8 animate-spin text-purple-400 mx-auto mb-3" />
                <p className="text-white/60 text-sm">Generating AI analysis...</p>
              </div>
            ) : aiAnalysis ? (
              <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                <pre className="text-white/80 text-sm whitespace-pre-wrap font-sans">{aiAnalysis}</pre>
              </div>
            ) : analysisError ? (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                <p className="text-red-300 text-sm">{analysisError}</p>
              </div>
            ) : (
              <p className="text-white/40 text-sm text-center py-8">
                Analysis loading...
              </p>
            )}
          </div>

          {/* Data Sources */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Database className="w-4 h-4 text-purple-400" />
              Data Sources
            </h4>
            <div className="flex flex-wrap gap-2">
              {/* Show actual data sources */}
              {dataSources.aliexpress?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  AliExpress <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.cj_dropshipping?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  CJ Dropshipping <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.google_trends?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  Google Trends <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.tiktok?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  TikTok <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.amazon?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  Amazon <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.x_twitter?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  X/Twitter <Check className="w-3 h-3" />
                </div>
              )}
              {dataSources.reddit?.available && (
                <div className="px-3 py-2 rounded-lg border bg-green-500/10 border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                  Reddit <Check className="w-3 h-3" />
                </div>
              )}
              {/* Show source from product if no detailed data_sources */}
              {activeSourceKeys.length === 0 && product.source && (
                <div className="px-3 py-2 rounded-lg border bg-blue-500/10 border-blue-500/30 text-blue-300 text-xs flex items-center gap-2">
                  {product.source.replace(/_/g, ' ')} <Check className="w-3 h-3" />
                </div>
              )}
              {activeSourceKeys.length === 0 && !product.source && (
                <div className="px-3 py-2 rounded-lg border bg-yellow-500/10 border-yellow-500/30 text-yellow-300 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-3 h-3" /> Limited data sources
                </div>
              )}
            </div>
          </div>

          {/* Pricing Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-white/5 text-center">
              <p className="text-white/40 text-xs mb-1">Supplier Cost</p>
              <p className="text-white font-bold text-xl">${product.cost_price.toFixed(2)}</p>
            </div>
            <div className="p-4 rounded-xl bg-green-500/10 text-center">
              <p className="text-green-300/60 text-xs mb-1">Sell Price</p>
              <p className="text-green-400 font-bold text-xl">${product.suggested_price.toFixed(2)}</p>
            </div>
            <div className="p-4 rounded-xl bg-purple-500/10 text-center">
              <p className="text-purple-300/60 text-xs mb-1">Profit</p>
              <p className="text-purple-400 font-bold text-xl">+${product.profit.toFixed(2)}</p>
            </div>
          </div>

          {/* Supplier Link */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Link2 className="w-4 h-4 text-purple-400" />
              Supplier Link
            </h4>
            {product.supplier_url ? (
              <a 
                href={product.supplier_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 rounded-xl bg-orange-500/10 border border-orange-500/20 hover:bg-orange-500/20 transition-colors group"
              >
                <span className="text-orange-300">
                  View on {product.source === 'cj_dropshipping' ? 'CJ Dropshipping' : 'AliExpress'} (Affiliate)
                </span>
                <ExternalLink className="w-4 h-4 text-orange-300 group-hover:translate-x-1 transition-transform" />
              </a>
            ) : (
              <div className="p-3 rounded-xl bg-white/5 text-white/40 text-sm text-center">
                {product.is_mock ? 'Demo product - no supplier link' : 'Supplier link not available'}
              </div>
            )}
          </div>

          {/* Deploy Section */}
          <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-4">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Rocket className="w-4 h-4 text-purple-400" />
              Deploy to Shopify
            </h4>
            
            {/* Caption */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white/60 text-sm">Product Caption</span>
                <button
                  onClick={generateSEOCaption}
                  disabled={generatingCaption}
                  className="px-3 py-1 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 flex items-center gap-1"
                >
                  {generatingCaption ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Wand2 className="w-3 h-3" />
                  )}
                  Regenerate
                </button>
              </div>
              <div className="relative">
                <textarea
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  className="w-full h-40 p-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50 text-sm"
                  placeholder={generatingCaption ? 'Generating caption...' : 'Product caption...'}
                />
                <button
                  onClick={copyCaption}
                  className="absolute top-2 right-2 p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white/60 hover:text-white"
                >
                  {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Deploy Button */}
            <button
              onClick={handleDeploy}
              disabled={product.is_mock || deploying}
              className="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
            >
              {deploying ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : product.is_mock ? (
                <>
                  <AlertTriangle className="w-5 h-5" />
                  Cannot Deploy Demo Products
                </>
              ) : (
                <>
                  <Rocket className="w-5 h-5" />
                  Deploy to Shopify
                  <ChevronRight className="w-5 h-5" />
                </>
              )}
            </button>
          </div>

          {/* Tags */}
          {product.tags?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {product.tags.map((tag, i) => (
                <span key={i} className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 text-sm flex items-center gap-1">
                  <Tag className="w-3 h-3" />
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </>
  );
}

// ============================================================================
// MAIN COMPONENT: Product Discovery
// ============================================================================
export function ProductDiscovery() {
  const { user, hasTier } = useAuth();
  const { 
    setVisibleProducts, 
    setSelectedProduct, 
    addRecentSearch, 
    setActiveFilters,
    trackInteraction,
    state: dashboardState 
  } = useDashboardContext();
  
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('trending');
  const [rateLimit, setRateLimit] = useState(null);
  const [selectedProduct, setSelectedProductState] = useState(null);
  const [hasMockData, setHasMockData] = useState(false);
  const [hasEstimatedScores, setHasEstimatedScores] = useState(false);
  const [generatingImages, setGeneratingImages] = useState(false);
  const [showEnhancer, setShowEnhancer] = useState(false);
  const [enhancerProduct, setEnhancerProduct] = useState(null);

  useEffect(() => {
    loadProducts();
    loadRateLimit();
  }, [filter]);

  useEffect(() => {
    if (products.length > 0) {
      const formattedProducts = products.map(p => ({
        id: p.id || '',
        name: p.title || p.name || '',
        price: p.suggested_price || p.price,
        supplier_cost: p.cost_price || p.supplier_cost,
        score: p.oi_score || 0,
        niche: p.niche || (p.tags?.[0]) || '',
        trend_score: p.trend_score,
        source: p.source || 'discovery',
      }));
      setVisibleProducts(formattedProducts);
    }
  }, [products, setVisibleProducts]);

  useEffect(() => {
    setActiveFilters({ filter, view: 'products' });
  }, [filter, setActiveFilters]);

  const loadProducts = async () => {
    setLoading(true);
    setHasMockData(false);
    setHasEstimatedScores(false);
    
    try {
      let niche = filter === 'trending' ? 'smart_home' : filter === 'recommended' ? 'tech' : 'fitness';
      const response = await api.discoverProducts({ niche, count: 20, includeAiImages: enableAiImages });
      const loadedProducts = Array.isArray(response) ? response : (response.products || []);
      const normalizedProducts = loadedProducts.map(p => normalizeProduct(p, niche));
      const mockCount = normalizedProducts.filter(p => p.is_mock).length;
      const estimatedCount = normalizedProducts.filter(p => p.scores_estimated).length;
      setHasMockData(mockCount > 0);
      setHasEstimatedScores(estimatedCount > normalizedProducts.length / 2);
      setProducts(normalizedProducts);
      trackInteraction('filter', { filter, result_count: normalizedProducts.length, mock_count: mockCount, ai_images: enableAiImages });
    } catch (error) {
      console.error('Failed to load products:', error);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };
  
  // Enhance images using background removal
  const enhanceProductImages = async () => {
    if (products.length === 0) return;
    setGeneratingImages(true);
    
    try {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      
      // Prepare batch request
      const imagesToEnhance = products.slice(0, 5).map(p => ({
        url: p.image_url,
        id: p.id,
        title: p.title,
        niche: p.niche || 'smart_home'
      }));
      
      const response = await fetch(`${apiBase}/api/images/enhance/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          images: imagesToEnhance,
          niche: 'smart_home',
          max_concurrent: 3
        })
      });
      
      const data = await response.json();
      
      if (data.results) {
        // Update products with enhanced images
        const updatedProducts = products.map(p => {
          const result = data.results.find(r => r.id === p.id);
          if (result?.success && result.enhanced_image_url) {
            return { ...p, ai_image_url: result.enhanced_image_url };
          }
          return p;
        });
        
        setProducts(updatedProducts);
        trackInteraction('enhance_images', {
          total: data.total,
          successful: data.successful,
          cost: data.estimated_cost
        });
      }
    } catch (error) {
      console.error('Image enhancement failed:', error);
      alert('Enhancement failed: ' + (error.message || 'Unknown error'));
    } finally {
      setGeneratingImages(false);
    }
  };

  // Legacy: Generate AI images for current products (kept for compatibility)
  const generateAiImages = async () => {
    if (products.length === 0) return;
    setGeneratingImages(true);
    try {
      // Send raw product data for enhancement
      const rawProducts = products.map(p => ({
        title: p.title,
        niche: p.niche,
        image_url: p.image_url,
        tags: p.tags,
      }));
      const enhanced = await api.enhanceProductsWithAiImages(rawProducts, 5);
      // Update products with AI images
      const updatedProducts = products.map((p, idx) => ({
        ...p,
        ai_image_url: enhanced[idx]?.ai_image_url || p.ai_image_url,
        image_source: enhanced[idx]?.image_source || p.image_source,
      }));
      setProducts(updatedProducts);
      trackInteraction('generate_ai_images', { count: updatedProducts.filter(p => p.ai_image_url).length });
    } catch (error) {
      console.error('Failed to generate AI images:', error);
    } finally {
      setGeneratingImages(false);
    }
  };

  const loadRateLimit = async () => {
    try {
      const response = await api.getRateLimitStatus();
      setRateLimit(response);
    } catch (error) {
      setRateLimit({ daily_remaining: '∞', daily_limit: '∞' });
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    addRecentSearch(searchQuery);
    setLoading(true);
    setHasMockData(false);
    
    try {
      const response = await api.discoverProducts({ niche: searchQuery.trim(), count: 20 });
      const searchResults = Array.isArray(response) ? response : (response.products || []);
      const normalizedResults = searchResults.map(p => normalizeProduct(p, searchQuery));
      const mockCount = normalizedResults.filter(p => p.is_mock).length;
      setHasMockData(mockCount > 0);
      setProducts(normalizedResults);
      trackInteraction('search', { query: searchQuery, result_count: normalizedResults.length, mock_count: mockCount });
    } catch (error) {
      console.error('Search failed:', error);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  const handleProductSelect = useCallback((product) => {
    setSelectedProductState(product);
    setSelectedProduct({
      id: product.id,
      name: product.title,
      price: product.suggested_price,
      supplier_cost: product.cost_price,
      score: product.oi_score,
      niche: product.niche,
      trend_score: product.trend_score,
      source: product.source,
    });
    trackInteraction('product_view', {
      product_id: product.id,
      product_name: product.title,
      niche: product.niche,
      score: product.oi_score,
      price: product.suggested_price,
    });
  }, [setSelectedProduct, trackInteraction]);

  const handleDeploy = async (product, caption) => {
    if (product.is_mock) return;
    await api.deployProduct(product.id, { caption });
    trackInteraction('product_deploy', {
      product_id: product.id,
      product_name: product.title,
      niche: product.niche,
      price: product.suggested_price,
    });
  };

  const getSubtitle = () => {
    if (rateLimit?.daily_remaining !== undefined && rateLimit?.daily_limit !== undefined) {
      return `${rateLimit.daily_remaining}/${rateLimit.daily_limit} discoveries today`;
    }
    return `${products.length} products loaded`;
  };

  return (
    <PageLayout title="Product Discovery" subtitle={getSubtitle()}>
      {/* Mock Data Warning */}
      {hasMockData && (
        <div className="mb-6 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
          <div>
            <p className="text-yellow-200 font-medium">Showing Demo Products</p>
            <p className="text-yellow-200/70 text-sm">APIs returned empty data. Check backend logs for connection issues.</p>
          </div>
        </div>
      )}
      
      {/* Estimated Scores Warning */}
      {hasEstimatedScores && !hasMockData && (
        <div className="mb-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0" />
          <div>
            <p className="text-blue-200 font-medium">Limited Data Available</p>
            <p className="text-blue-200/70 text-sm">Scores marked "Est." are estimates. Connect Google Trends, TikTok, and sentiment APIs for accurate metrics.</p>
          </div>
        </div>
      )}

      {/* Search & Filter */}
      <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6 mb-8">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search products or niches..."
                className="w-full pl-12 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-purple-500/50"
              />
            </div>
            <button onClick={handleSearch} className="px-6 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-semibold hover:opacity-90 transition-opacity">
              <Search className="w-4 h-4" />
            </button>
          </div>
          <div className="flex gap-2">
            {['trending', 'recommended', 'high-profit'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2 ${
                  filter === f
                    ? 'bg-purple-500/20 border border-purple-500/30 text-purple-300'
                    : 'bg-white/5 border border-white/10 text-white/60 hover:text-white hover:bg-white/10'
                }`}
              >
                {f === 'trending' && <TrendingUp className="w-4 h-4" />}
                {f === 'recommended' && <Filter className="w-4 h-4" />}
                {f === 'high-profit' && <BarChart3 className="w-4 h-4" />}
                {f.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </button>
            ))}
          </div>
        </div>
        
        {/* Image Enhancement Controls */}
        <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-white/50 text-sm">Product images can be enhanced with clean backgrounds</span>
            <span className="text-white/40 text-xs">(~$0.06/image)</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowEnhancer(true)}
              className="px-4 py-2 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-sm font-medium hover:bg-cyan-500/30 flex items-center gap-2"
            >
              <Wand2 className="w-4 h-4" />
              Enhance Single Image
            </button>
            <button
              onClick={enhanceProductImages}
              disabled={generatingImages || products.length === 0}
              className="px-4 py-2 rounded-xl bg-purple-500/20 border border-purple-500/30 text-purple-300 text-sm font-medium hover:bg-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {generatingImages ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Enhancing...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Enhance All (Top 5)
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Product Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 overflow-hidden animate-pulse">
              <div className="aspect-square bg-white/5" />
              <div className="p-4 space-y-3">
                <div className="h-4 bg-white/10 rounded w-3/4" />
                <div className="h-3 bg-white/10 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : products.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {products.map((product) => (
            <ProductCard 
              key={product.id} 
              product={product} 
              onClick={() => handleProductSelect(product)}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <Package className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">No products found</h3>
          <p className="text-white/50">Try a different search or filter</p>
        </div>
      )}

      {/* Detail Panel */}
      {selectedProduct && (
        <ProductDetailPanel
          product={selectedProduct}
          onClose={() => setSelectedProductState(null)}
          onDeploy={handleDeploy}
          onUpdateProduct={(updatedProduct) => {
            // Update product in list with new AI image
            setProducts(prev => prev.map(p => 
              p.id === updatedProduct.id ? updatedProduct : p
            ));
            setSelectedProductState(updatedProduct);
          }}
          onEnhance={(product) => {
            setEnhancerProduct(product);
            setShowEnhancer(true);
          }}
        />
      )}

      {/* Image Enhancer Modal */}
      {showEnhancer && (
        <AIImageComparison
          product={enhancerProduct || selectedProduct}
          isModal={true}
          onClose={() => {
            setShowEnhancer(false);
            setEnhancerProduct(null);
          }}
          onImageEnhanced={(enhancedUrl) => {
            // Update product with enhanced image
            const targetProduct = enhancerProduct || selectedProduct;
            if (targetProduct) {
              const updatedProduct = { ...targetProduct, ai_image_url: enhancedUrl };
              setProducts(prev => prev.map(p => 
                p.id === targetProduct.id ? updatedProduct : p
              ));
              if (selectedProduct?.id === targetProduct.id) {
                setSelectedProductState(updatedProduct);
              }
            }
          }}
        />
      )}
    </PageLayout>
  );
}

export default ProductDiscovery;
