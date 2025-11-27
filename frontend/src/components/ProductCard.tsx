import React, { useState } from 'react';
import axios from 'axios';
import { Star, BarChart2, Layers, ExternalLink, TrendingUp, ShoppingBag, Search } from 'lucide-react';

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

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  onAnalyze,
  isSelected = false,
  onToggleSelect
}) => {
  const [deploying, setDeploying] = useState(false);
  const [deploymentStatus, setDeploymentStatus] = useState<{
    deployed: boolean;
    shopify_url?: string;
    deployed_at?: string;
  } | null>(null);

  const deployToShopify = async () => {
    // Check if this is a demo product
    if (product.id.startsWith('demo-') || product.source === 'DEMO_FALLBACK') {
      alert('Demo products cannot be deployed. Please run real product discovery first or configure real data sources.');
      return;
    }

    setDeploying(true);
    try {
      const response = await axios.post(
        `http://localhost:8001/api/dashboard/v2/products/${product.id}/deploy-to-shopify`
      );

      if (response.data.status === 'success' || response.data.status === 'already_deployed') {
        setDeploymentStatus({
          deployed: true,
          shopify_url: response.data.shopify_url,
          deployed_at: response.data.deployed_at || new Date().toISOString()
        });
        alert(response.data.message || 'Product deployed successfully!');
      }
    } catch (error: unknown) {
      console.error('Failed to deploy product:', error);
      const errorMsg = (error instanceof Error && error.message) || (typeof error === 'object' && error !== null && 'response' in error && typeof error.response === 'object' && error.response !== null && 'data' in error.response && typeof error.response.data === 'object' && error.response.data !== null && 'detail' in error.response.data && typeof error.response.data.detail === 'string' && error.response.data.detail) || 'Failed to deploy product to Shopify. Make sure Shopify is configured.';
      alert(errorMsg);
    } finally {
      setDeploying(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-success-green';
    if (score >= 6) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getVelocityColor = (velocity: number) => {
    if (velocity >= 70) return 'bg-success-green/10 text-success-green';
    if (velocity >= 50) return 'bg-yellow-500/10 text-yellow-400';
    return 'bg-red-500/10 text-red-400';
  };

  return (
    <div className={`relative bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl overflow-hidden transition-all duration-300 ${isSelected ? 'ring-2 ring-brand-blue' : 'hover:border-gray-700'}`}>
      {onToggleSelect && (
        <div className="absolute top-3 left-3 z-20">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(product.id)}
            onClick={(e) => e.stopPropagation()}
            className="w-5 h-5 rounded-md bg-gray-800/50 border-gray-600 text-brand-blue focus:ring-brand-blue cursor-pointer"
          />
        </div>
      )}
      
      <div className="relative h-48 bg-gray-800">
        <img
          src={product.image_url || `https://via.placeholder.com/400x300/161b22/d0d7de?text=${encodeURIComponent(product.name.substring(0,20))}`}
          alt={product.name}
          className="w-full h-full object-cover"
          onError={(e) => { e.currentTarget.src = `https://via.placeholder.com/400x300/161b22/d0d7de?text=Image+Error`; }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-gray-950/70 via-transparent to-transparent"></div>
        <div className={`absolute top-2 right-2 px-2 py-1 rounded-full text-xs font-semibold ${getVelocityColor(product.velocity_score || 0)}`}>
          Velocity: {product.velocity_score || 0}
        </div>

        {/* Platform Badges */}
        <div className="absolute bottom-2 left-2 flex gap-1.5">
          {product.data_sources?.tiktok?.available && (
            <div className="bg-black/70 backdrop-blur-sm px-2 py-1 rounded-md flex items-center gap-1 text-xs" title={`TikTok: ${product.data_sources.tiktok.views?.toLocaleString() || 'N/A'} views`}>
              <span className="text-[#FF0050]">♪</span>
              <span className="text-white font-semibold">TikTok</span>
            </div>
          )}
          {product.data_sources?.amazon?.available && (
            <div className="bg-black/70 backdrop-blur-sm px-2 py-1 rounded-md flex items-center gap-1 text-xs" title={`Amazon Rank: ${product.data_sources.amazon.sales_rank?.toLocaleString() || 'N/A'}`}>
              <ShoppingBag className="w-3 h-3 text-[#FF9900]" />
              <span className="text-white font-semibold">Amazon</span>
            </div>
          )}
          {product.data_sources?.google_trends?.available && (
            <div className="bg-black/70 backdrop-blur-sm px-2 py-1 rounded-md flex items-center gap-1 text-xs" title={`Google Trends: ${product.data_sources.google_trends.trend_score || 'N/A'}`}>
              <Search className="w-3 h-3 text-[#4285F4]" />
              <span className="text-white font-semibold">Trends</span>
            </div>
          )}
          {product.data_sources?.aliexpress?.available && (
            <div className="bg-black/70 backdrop-blur-sm px-2 py-1 rounded-md flex items-center gap-1 text-xs" title={`AliExpress: ${product.data_sources.aliexpress.orders?.toLocaleString() || 'N/A'} orders`}>
              <TrendingUp className="w-3 h-3 text-[#FF6A00]" />
              <span className="text-white font-semibold">AliEx</span>
            </div>
          )}
        </div>
      </div>

      <div className="p-4 space-y-4">
        <h3 className="font-semibold text-gray-200 h-10 line-clamp-2">
          {product.name}
        </h3>

        <div className="flex justify-between items-center">
          <div>
            <p className="text-xs text-gray-500">Ospra Score</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-2xl font-bold ${getScoreColor(product.velocity_score || 0)}`}>
                {product.velocity_score || 0}
              </span>
              <span className="text-sm text-gray-500">/100</span>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-1.5 justify-end text-gray-400" title="Customer Rating">
              <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
              <span className="font-semibold">{product.rating?.toFixed(1) || 'N/A'}</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">{product.tier || 'N/A'} tier</p>
          </div>
        </div>

        <div className="flex justify-between items-end bg-gray-800/50 p-3 rounded-lg">
          <div>
            <p className="text-xs text-gray-400">Profit</p>
            <p className="text-lg font-bold text-success-green">
              ${product.estimated_profit?.toFixed(2)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-400">Price</p>
            <p className="font-semibold text-gray-200">${product.price.toFixed(2)}</p>
          </div>
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={() => onAnalyze(product)}
            className="flex-1 bg-brand-blue/10 text-brand-blue border border-brand-blue/20 py-2 px-4 rounded-lg hover:bg-brand-blue/20 transition font-semibold text-sm flex items-center justify-center gap-2"
          >
            <BarChart2 className="w-4 h-4" />
            Analyze
          </button>
          <button
            onClick={deployToShopify}
            disabled={deploying || deploymentStatus?.deployed}
            className="flex-1 py-2 px-4 rounded-lg font-semibold transition text-sm flex items-center justify-center gap-2 bg-brand-blue text-white hover:opacity-90 disabled:bg-gray-600 disabled:cursor-not-allowed"
          >
            <Layers className="w-4 h-4" />
            {deploymentStatus?.deployed ? 'Deployed' : (deploying ? 'Deploying...' : 'Deploy')}
          </button>
        </div>

        {product.supplier_url && (
          <a
            href={product.supplier_url}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full mt-2 bg-orange-600/10 text-orange-400 border border-orange-500/20 py-2 px-4 rounded-lg hover:bg-orange-600/20 transition font-semibold text-sm flex items-center justify-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            View on AliExpress
          </a>
        )}
      </div>
    </div>
  );
}
