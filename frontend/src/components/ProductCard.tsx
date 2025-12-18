import React, { useState } from 'react';
import { ExternalLink, Flame, BarChart2, Layers, Star, ShoppingCart } from 'lucide-react';
import { DeployPreviewModal } from './DeployPreviewModal';
import type { DeployResult } from '../services/api';

interface Product {
  id: string;
  name: string;
  image_url?: string;
  price: number;
  cost?: number;
  score?: number;           // AI Score 0-10 (use this directly!)
  velocity_score?: number;  // 0-100 trend velocity
  profit_margin?: number;
  estimated_profit?: number;
  aliexpress_url?: string;
  supplier_url?: string;
  niche?: string;
  rating?: number;
  orders?: number;
  source?: string;
}

interface ProductCardProps {
  product: Product;
  onAnalyze: (product: Product) => void;
  isSelected?: boolean;
  onToggleSelect?: (productId: string) => void;
}

// Utility: Sanitize image URL
function sanitizeImageUrl(url?: string, productName?: string): string {
  if (!url || url.trim() === '') {
    const text = encodeURIComponent(productName?.substring(0, 15) || 'Product');
    return `https://placehold.co/400x200/1a1a2e/eaeaea?text=${text}`;
  }
  let cleanUrl = url.replace(/^http:\/\//i, 'https://');
  return cleanUrl;
}

// Loading skeleton
export const ProductCardSkeleton: React.FC = () => (
  <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl overflow-hidden animate-pulse">
    <div className="h-[160px] bg-white/10" />
    <div className="p-4 space-y-3">
      <div className="h-5 bg-white/10 rounded w-3/4" />
      <div className="h-4 bg-white/10 rounded w-1/3" />
      <div className="flex justify-between py-3">
        <div className="h-6 bg-white/10 rounded w-16" />
        <div className="h-6 bg-white/10 rounded w-16" />
        <div className="h-6 bg-white/10 rounded w-16" />
      </div>
      <div className="flex gap-2">
        <div className="h-10 bg-white/10 rounded flex-1" />
        <div className="h-10 bg-white/10 rounded flex-1" />
      </div>
    </div>
  </div>
);

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  onAnalyze,
  isSelected = false,
  onToggleSelect
}) => {
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deploymentStatus, setDeploymentStatus] = useState<{
    deployed: boolean;
    shopify_url?: string;
  } | null>(null);

  // ==========================================
  // METRIC CALCULATIONS (using real data!)
  // ==========================================
  
  // AI Score: Use product.score directly (0-10), NOT velocity_score/10!
  const aiScore = product.score ?? 0;
  
  // Profit: Use estimated_profit or calculate from price - cost
  const cost = product.cost ?? 0;
  const price = product.price ?? 0;
  const profit = product.estimated_profit ?? (price - cost);
  
  // Margin: Use profit_margin or calculate
  const margin = product.profit_margin ?? (price > 0 ? ((price - cost) / price) * 100 : 0);
  
  // Velocity: 0-100 trend score
  const velocity = product.velocity_score ?? 0;
  
  // Product URL: Prefer aliexpress_url, fallback to supplier_url
  const productUrl = product.aliexpress_url || product.supplier_url;
  
  // Is this product "hot"?
  const isHot = velocity > 70 || (product.orders && product.orders > 5000);
  
  // Is profitable?
  const isProfitable = profit > 0;

  // Score color
  const getScoreColor = () => {
    if (aiScore >= 7) return 'from-green-500 to-emerald-600';
    if (aiScore >= 5) return 'from-cyan-500 to-blue-600';
    if (aiScore >= 3) return 'from-amber-500 to-orange-600';
    return 'from-gray-500 to-gray-600';
  };

  const handleDeploy = () => {
    if (product.id.startsWith('demo-') || product.source === 'DEMO_FALLBACK') {
      alert('Demo products cannot be deployed.');
      return;
    }
    setShowDeployModal(true);
  };

  const handleDeploySuccess = (result: DeployResult) => {
    setDeploymentStatus({ deployed: true, shopify_url: result.shopify_url });
  };

  return (
    <div className={`
      relative bg-white/5 backdrop-blur-sm border rounded-xl overflow-hidden
      transition-all duration-300 hover:shadow-xl hover:scale-[1.02] hover:bg-white/10
      ${isSelected ? 'border-cyan-500 ring-2 ring-cyan-500/50' : 'border-white/10'}
    `}>
      
      {/* Selection Checkbox */}
      {onToggleSelect && (
        <div className="absolute top-3 left-3 z-20">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(product.id)}
            onClick={(e) => e.stopPropagation()}
            className="w-5 h-5 rounded bg-black/50 border-white/30 text-cyan-500 focus:ring-cyan-500 cursor-pointer"
          />
        </div>
      )}

      {/* ====== IMAGE SECTION ====== */}
      <div className="relative h-[160px] bg-gray-900 overflow-hidden">
        <img
          src={sanitizeImageUrl(product.image_url, product.name)}
          alt={product.name}
          className="w-full h-full object-cover"
          crossOrigin="anonymous"
          referrerPolicy="no-referrer"
          onError={(e) => {
            const target = e.currentTarget;
            if (!target.dataset.retried) {
              target.dataset.retried = 'true';
              const text = encodeURIComponent(product.name.substring(0, 15));
              target.src = `https://placehold.co/400x200/1a1a2e/eaeaea?text=${text}`;
            }
          }}
        />

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />

        {/* HOT Badge */}
        {isHot && (
          <div className="absolute top-3 left-3 px-2 py-1 bg-gradient-to-r from-orange-500 to-red-500 text-white text-xs font-bold rounded-full flex items-center gap-1 shadow-lg">
            <Flame className="w-3 h-3" />
            HOT
          </div>
        )}

        {/* AI Score Badge */}
        <div className={`absolute top-3 right-3 px-3 py-1.5 rounded-lg bg-gradient-to-r ${getScoreColor()} shadow-lg`}>
          <div className="flex items-center gap-1">
            <Star className="w-3.5 h-3.5 text-white fill-white" />
            <span className="text-white font-bold text-sm">{aiScore.toFixed(1)}</span>
          </div>
        </div>

        {/* Orders badge (if available) */}
        {product.orders && product.orders > 0 && (
          <div className="absolute bottom-3 left-3 px-2 py-1 bg-black/60 backdrop-blur-sm text-white text-xs rounded-full flex items-center gap-1">
            <ShoppingCart className="w-3 h-3" />
            {product.orders.toLocaleString()} sold
          </div>
        )}
      </div>

      {/* ====== CONTENT SECTION ====== */}
      <div className="p-4 space-y-3">
        
        {/* Product Name */}
        <h3 className="font-semibold text-white text-sm line-clamp-2 leading-tight min-h-[2.5rem]">
          {product.name}
        </h3>

        {/* Niche Badge */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-cyan-400 bg-cyan-500/20 px-2 py-0.5 rounded-full">
            {product.niche?.replace(/_/g, ' ') || 'General'}
          </span>
          {product.source && (
            <span className="text-xs text-gray-400">
              {product.source === 'aliexpress_api' ? 'AliExpress' : product.source}
            </span>
          )}
        </div>

        {/* ====== METRICS ROW ====== */}
        <div className="grid grid-cols-3 gap-2 py-3 border-y border-white/10">
          {/* Profit */}
          <div className="text-center">
            <div className={`text-lg font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
              ${profit.toFixed(2)}
            </div>
            <div className="text-[10px] text-gray-400 uppercase tracking-wide">Profit</div>
          </div>
          
          {/* Cost */}
          <div className="text-center">
            <div className="text-lg font-bold text-white">
              ${cost.toFixed(2)}
            </div>
            <div className="text-[10px] text-gray-400 uppercase tracking-wide">Cost</div>
          </div>
          
          {/* Margin */}
          <div className="text-center">
            <div className={`text-lg font-bold ${margin >= 30 ? 'text-cyan-400' : 'text-amber-400'}`}>
              {margin.toFixed(0)}%
            </div>
            <div className="text-[10px] text-gray-400 uppercase tracking-wide">Margin</div>
          </div>
        </div>

        {/* ====== VIEW PRODUCT LINK ====== */}
        {productUrl && (
          <a
            href={productUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 transition-colors py-1"
          >
            <ExternalLink className="w-4 h-4" />
            View on AliExpress
          </a>
        )}

        {/* ====== ACTION BUTTONS ====== */}
        <div className="flex gap-2">
          <button
            onClick={() => onAnalyze(product)}
            className="flex-1 py-2.5 text-sm font-medium text-white bg-white/10 hover:bg-white/20 rounded-lg transition-colors flex items-center justify-center gap-1.5"
          >
            <BarChart2 className="w-4 h-4" />
            Analyze
          </button>
          
          <button
            onClick={handleDeploy}
            disabled={deploymentStatus?.deployed}
            className="flex-1 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed rounded-lg transition-all flex items-center justify-center gap-1.5 shadow-md"
          >
            {deploymentStatus?.deployed ? (
              <>
                <Layers className="w-4 h-4" />
                Live
              </>
            ) : (
              'Deploy'
            )}
          </button>
        </div>

        {/* Deployment Status */}
        {deploymentStatus?.deployed && deploymentStatus.shopify_url && (
          <a
            href={deploymentStatus.shopify_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 text-xs text-green-400 hover:text-green-300"
          >
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            View on Shopify →
          </a>
        )}
      </div>

      {/* ====== DEPLOY MODAL ====== */}
      {showDeployModal && (
        <DeployPreviewModal
          product={{
            id: product.id,
            name: product.name,
            niche: product.niche,
            image_url: product.image_url,
            cost: product.cost,
            price: product.price,
            supplier_url: productUrl,
          }}
          onClose={() => setShowDeployModal(false)}
          onSuccess={handleDeploySuccess}
        />
      )}
    </div>
  );
};

export default ProductCard;
