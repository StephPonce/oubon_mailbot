import React, { useState } from 'react';
import { ArrowRight, Flame, BarChart2, Layers } from 'lucide-react';
import { ImageEnhanceModal } from './ImageEnhanceModal';
import { DeployPreviewModal } from './DeployPreviewModal';
import { ExplainTooltip } from './ui/ExplainTooltip';
import type { DeployResult } from '../services/api';

interface Product {
  id: string;
  name: string;
  image_url?: string;
  price: number;
  cost?: number;
  trend_score?: number;
  velocity_score?: number;
  score?: number;
  sales_rank?: number;
  orders?: number;
  competition_score?: number;
  profit_margin?: number;
  estimated_profit?: number;
  supplier_url?: string;
  niche?: string;
  discovered_at?: string;
  commission_rate?: number;
  tier?: string;
  rating?: number;
  original_price?: number;
  aliexpress_cost?: number;
  shipping_cost?: number;
  source?: string;
  data_sources?: {
    aliexpress?: { available: boolean; orders?: number };
    amazon?: { available: boolean; sales_rank?: number };
    tiktok?: { available: boolean; views?: number };
    google_trends?: { available: boolean; trend_score?: number };
  };
}

interface ProductCardProps {
  product: Product;
  onAnalyze: (product: Product) => void;
  isSelected?: boolean;
  onToggleSelect?: (productId: string) => void;
}

// Utility functions
function sanitizeImageUrl(url?: string, productName?: string): string {
  if (!url || url.trim() === '') {
    const text = encodeURIComponent(productName?.substring(0, 20) || 'Product');
    return `https://placehold.co/400x200/1a1a2e/eaeaea?text=${text}`;
  }
  let cleanUrl = url.replace(/^http:\/\//i, 'https://');
  if (cleanUrl.includes('alicdn.com') || cleanUrl.includes('aliexpress-media')) {
    cleanUrl = cleanUrl.split('_')[0];
    if (!cleanUrl.includes('?')) {
      cleanUrl = cleanUrl + '_400x200.jpg';
    }
  }
  return cleanUrl;
}

// ProductCardSkeleton Component - Loading state
export const ProductCardSkeleton: React.FC = () => {
  return (
    <div className="bg-white border border-white/10 rounded-xl overflow-hidden shadow-sm animate-pulse">
      {/* Image skeleton */}
      <div className="h-[200px] bg-gray-200" />

      {/* Content skeleton */}
      <div className="p-4 space-y-3">
        {/* Title skeleton */}
        <div className="h-5 bg-gray-200 rounded w-3/4" />

        {/* Niche badge skeleton */}
        <div className="h-4 bg-gray-200 rounded w-1/3" />

        {/* Metrics row skeleton */}
        <div className="flex justify-between py-3 border-y border-white/10">
          <div className="text-center space-y-2">
            <div className="h-6 bg-gray-200 rounded w-12 mx-auto" />
            <div className="h-3 bg-gray-200 rounded w-10 mx-auto" />
          </div>
          <div className="text-center space-y-2">
            <div className="h-6 bg-gray-200 rounded w-12 mx-auto" />
            <div className="h-3 bg-gray-200 rounded w-10 mx-auto" />
          </div>
          <div className="text-center space-y-2">
            <div className="h-6 bg-gray-200 rounded w-12 mx-auto" />
            <div className="h-3 bg-gray-200 rounded w-10 mx-auto" />
          </div>
        </div>

        {/* Action buttons skeleton */}
        <div className="flex gap-2 pt-2">
          <div className="h-10 bg-gray-200 rounded-lg flex-1" />
          <div className="h-10 bg-gray-200 rounded-lg flex-1" />
        </div>
      </div>
    </div>
  );
};

// MetricPill Component
const MetricPill: React.FC<{
  icon: string;
  value: string | number;
  label: string;
  color: 'green' | 'blue' | 'purple';
}> = ({ icon, value, label, color }) => {
  const colorClasses = {
    green: 'text-green-600',
    blue: 'text-blue-600',
    purple: 'text-purple-600',
  };

  return (
    <div className="text-center">
      <div className={`text-lg font-bold ${colorClasses[color]} flex items-center justify-center gap-1`}>
        <span>{icon}</span>
        <span>{value}</span>
      </div>
      <div className="text-xs text-tertiary mt-0.5">{label}</div>
    </div>
  );
};

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
    deployed_at?: string;
  } | null>(null);
  const [showEnhanceModal, setShowEnhanceModal] = useState(false);
  const [enhancedImageUrl, setEnhancedImageUrl] = useState<string | null>(null);

  const handleOpenDeployModal = () => {
    if (product.id.startsWith('demo-') || product.source === 'DEMO_FALLBACK') {
      alert('Demo products cannot be deployed. Please run real product discovery first or configure real data sources.');
      return;
    }
    setShowDeployModal(true);
  };

  const handleDeploymentSuccess = (result: DeployResult) => {
    setDeploymentStatus({
      deployed: true,
      shopify_url: result.shopify_url,
      deployed_at: new Date().toISOString()
    });
  };

  const handleUseEnhanced = (enhancedUrl: string) => {
    setEnhancedImageUrl(enhancedUrl);
  };

  // Calculate metrics
  const score = (product.velocity_score || 0) / 10; // Convert 0-100 to 0-10
  const profit = product.estimated_profit || (product.price - (product.cost || 0));
  const margin = Math.round(product.profit_margin || ((product.price - (product.cost || 0)) / product.price * 100));
  const velocity = product.velocity_score || 0;

  // Determine if product is "hot"
  const isHot = velocity > 80 || product.data_sources?.tiktok?.available;

  // Get score color
  const getScoreColor = () => {
    if (score >= 8) return 'bg-green-500/100/90';
    if (score >= 6) return 'bg-cyan-500/100/90';
    return 'bg-amber-500/90';
  };

  // Generate rationale for the recommendation
  const generateRationale = () => {
    const factors = [];
    const parts = [];
    let confidenceBoost = 0;

    // Velocity analysis
    if (velocity > 80) {
      factors.push({ label: "Exceptional demand velocity", value: 15, icon: "trend" as const });
      parts.push("selling rapidly");
      confidenceBoost += 15;
    } else if (velocity > 60) {
      factors.push({ label: "Strong demand", value: 10, icon: "trend" as const });
      parts.push("steady sales");
      confidenceBoost += 10;
    }

    // Margin analysis
    if (margin > 50) {
      factors.push({ label: "Excellent margins", value: 20, icon: "success" as const });
      parts.push(`${margin}% profit margin`);
      confidenceBoost += 20;
    } else if (margin > 30) {
      factors.push({ label: "Healthy margins", value: 12, icon: "success" as const });
      parts.push(`${margin}% margin`);
      confidenceBoost += 12;
    }

    // Rating analysis
    if (product.rating && product.rating >= 4.5) {
      factors.push({ label: "Excellent reviews", value: 10, icon: "success" as const });
      parts.push(`${product.rating}★ rating`);
      confidenceBoost += 10;
    }

    // Orders analysis
    if (product.orders && product.orders > 1000) {
      factors.push({ label: "High sales volume", value: 12, icon: "success" as const });
      parts.push(`${product.orders}+ sales`);
      confidenceBoost += 12;
    }

    const rationaleText = parts.length > 0
      ? `This product shows ${parts.slice(0, 3).join(", ")}. ${score >= 8 ? "Strong buy signal." : score >= 6 ? "Good potential." : "Consider testing."}`
      : "Meets baseline criteria for dropshipping.";

    const confidence = Math.min(95, Math.max(40, Math.round(score * 10 + confidenceBoost)));

    return { rationale: rationaleText, confidence, factors: factors.slice(0, 4) };
  };

  const explanation = generateRationale();

  return (
    <div className={`relative bg-white border ${isSelected ? 'border-blue-500 ring-2 ring-blue-500/50' : 'border-white/10'} rounded-xl overflow-hidden shadow-sm hover:shadow-xl hover:scale-[1.02] transition-all duration-300`}>

      {/* Selection Checkbox */}
      {onToggleSelect && (
        <div className="absolute top-3 left-3 z-20">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(product.id)}
            onClick={(e) => e.stopPropagation()}
            className="w-5 h-5 rounded-md bg-white/90 backdrop-blur-sm border-white/10 text-blue-600 focus:ring-2 focus:ring-blue-500 cursor-pointer"
          />
        </div>
      )}

      {/* ========================================
          IMAGE SECTION - 200px height
      ======================================== */}
      <div className="relative h-[200px] bg-gray-100 overflow-hidden">
        <img
          src={sanitizeImageUrl(enhancedImageUrl || product.image_url, product.name)}
          alt={product.name}
          className="w-full h-full object-cover"
          crossOrigin="anonymous"
          referrerPolicy="no-referrer"
          onError={(e) => {
            const target = e.currentTarget;
            if (!target.dataset.retried) {
              target.dataset.retried = 'true';
              const text = encodeURIComponent(product.name.substring(0, 20));
              target.src = `https://placehold.co/400x200/1a1a2e/eaeaea?text=${text}`;
            }
          }}
        />

        {/* Gradient overlay at bottom */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent pointer-events-none" />

        {/* HOT/TRENDING Badge (top left) */}
        {isHot && (
          <div className="absolute top-3 left-3 px-2 py-1 bg-gradient-to-r from-orange-500 to-red-500 text-white text-xs font-bold rounded-full flex items-center gap-1 shadow-lg">
            <Flame className="w-3 h-3" />
            HOT
          </div>
        )}

        {/* Score Badge (top right) with Explain Tooltip */}
        <div className={`absolute top-3 right-3 px-3 py-2 rounded-xl backdrop-blur-md ${getScoreColor()} shadow-lg`}>
          <div className="flex items-center gap-2 mb-1">
            <div className="text-white font-bold text-lg text-center">{score.toFixed(1)}</div>
            <ExplainTooltip
              rationale={explanation.rationale}
              confidence={explanation.confidence}
              factors={explanation.factors}
              position="bottom"
            />
          </div>
          <div className="flex gap-0.5">
            {[...Array(10)].map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full ${i < Math.floor(score) ? 'bg-white' : 'bg-white/30'}`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* ========================================
          CONTENT SECTION
      ======================================== */}
      <div className="p-4 space-y-3">

        {/* Product Name & Niche */}
        <div>
          <h3 className="font-bold text-primary text-base line-clamp-2 mb-2">
            {product.name}
          </h3>
          <span className="text-xs text-tertiary bg-gray-100 px-2 py-0.5 rounded-full">
            {product.niche?.replace(/_/g, ' ') || 'General'}
          </span>
        </div>

        {/* ========================================
            METRICS ROW (compact, scannable)
        ======================================== */}
        <div className="flex justify-between items-center py-3 border-y border-white/10">
          <MetricPill
            icon="💰"
            value={`$${profit.toFixed(0)}`}
            label="Profit"
            color="green"
          />
          <MetricPill
            icon="📊"
            value={`${margin}%`}
            label="Margin"
            color="blue"
          />
          <MetricPill
            icon="🚀"
            value={velocity}
            label="Velocity"
            color="purple"
          />
        </div>

        {/* ========================================
            ACTION BUTTONS
        ======================================== */}
        <div className="flex gap-2 pt-2">
          <button
            onClick={() => onAnalyze(product)}
            className="flex-1 py-2.5 text-sm font-medium text-secondary bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors duration-200 flex items-center justify-center gap-1"
          >
            <BarChart2 className="w-4 h-4" />
            Analyze
          </button>
          <button
            onClick={handleOpenDeployModal}
            disabled={deploymentStatus?.deployed}
            className="flex-1 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed rounded-lg transition-all duration-200 flex items-center justify-center gap-1 shadow-md"
          >
            {deploymentStatus?.deployed ? (
              <>
                <Layers className="w-4 h-4" />
                Deployed
              </>
            ) : (
              <>
                Deploy
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>

        {/* Deployment Status (if deployed) */}
        {deploymentStatus?.deployed && (
          <div className="flex items-center gap-2 p-2 rounded-lg bg-green-500/100/10 border border-green-200">
            <div className="w-2 h-2 rounded-full bg-green-500/100 animate-pulse" />
            <span className="text-xs text-green-400 font-medium flex-1">
              Live on Shopify
            </span>
            {deploymentStatus.shopify_url && (
              <a
                href={deploymentStatus.shopify_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-green-600 hover:text-green-400 font-medium"
              >
                View →
              </a>
            )}
          </div>
        )}
      </div>

      {/* ========================================
          MODALS
      ======================================== */}
      {/* Image Enhancement Modal */}
      {showEnhanceModal && (
        <ImageEnhanceModal
          product={{
            id: product.id,
            name: product.name,
            image_url: product.image_url,
          }}
          onClose={() => setShowEnhanceModal(false)}
          onUseEnhanced={handleUseEnhanced}
        />
      )}

      {/* Deploy Preview Modal */}
      {showDeployModal && (
        <DeployPreviewModal
          product={{
            id: product.id,
            name: product.name,
            niche: product.niche,
            image_url: enhancedImageUrl || product.image_url,
            cost: product.cost,
            price: product.price,
            supplier_url: product.supplier_url,
            description: product.description,
          }}
          onClose={() => setShowDeployModal(false)}
          onSuccess={handleDeploymentSuccess}
        />
      )}
    </div>
  );
};
