import React, { useState, useEffect } from 'react';
import axios from 'axios';

export interface Product {
  id: string;
  name: string;
  price: number;
  cost: number;
  profit_margin: number;
  estimated_profit: number;
  velocity_score: number;
  score: number;
  orders: number;
  rating: number;
  image_url?: string;
  category?: string;
  niche?: string;
  aliexpress_url?: string;
  source?: string;
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

  // Check deployment status on mount
  useEffect(() => {
    checkDeploymentStatus();
  }, [product.id]);

  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600';
    if (score >= 6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getVelocityColor = (velocity: number) => {
    if (velocity >= 70) return 'bg-green-100 text-green-800';
    if (velocity >= 50) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  const syncDeploymentStatus = async () => {
    try {
      const response = await axios.post(
        `http://127.0.0.1:8000/api/dashboard/v2/products/${product.id}/sync-deployment`
      );

      if (!response.data.deployed) {
        // Product was deleted from Shopify
        setDeploymentStatus(null);
      }
    } catch (error) {
      console.error('Sync failed:', error);
    }
  };

  const checkDeploymentStatus = async () => {
    try {
      // First check database
      const response = await axios.get(
        `http://127.0.0.1:8000/api/dashboard/v2/products/${product.id}/deployment-status`
      );

      if (response.data.deployed) {
        setDeploymentStatus(response.data);
        // Then sync with Shopify in background
        syncDeploymentStatus();
      }
    } catch (error) {
      // Not deployed or error - that's fine
    }
  };

  const deployToShopify = async () => {
    setDeploying(true);

    try {
      const response = await axios.post(
        `http://127.0.0.1:8000/api/dashboard/v2/products/${product.id}/deploy-to-shopify`
      );

      if (response.data.status === 'success' || response.data.status === 'already_deployed') {
        setDeploymentStatus({
          deployed: true,
          shopify_url: response.data.shopify_url,
          deployed_at: response.data.deployed_at || new Date().toISOString()
        });

        if (response.data.status === 'success') {
          alert(`✅ Product deployed to Shopify!\n\nView on store: ${response.data.shopify_url}`);
        } else {
          alert(`ℹ️ This product was already deployed on ${new Date(response.data.deployed_at).toLocaleDateString()}\n\nView on store: ${response.data.shopify_url}`);
        }
      }
    } catch (error) {
      console.error('Deploy failed:', error);
      alert('❌ Failed to deploy to Shopify. Check console for details.');
    } finally {
      setDeploying(false);
    }
  };

  return (
    <div className={`bg-white rounded-lg shadow-md overflow-hidden hover:shadow-xl transition ${isSelected ? 'ring-4 ring-blue-500' : ''}`}>
      {/* Product Image */}
      <div className="relative h-48 bg-gray-100">
        {onToggleSelect && (
          <div className="absolute top-2 left-2 z-10">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onToggleSelect(product.id)}
              onClick={(e) => e.stopPropagation()}
              className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </div>
        )}

        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover"
            onError={(e) => {
              // Better fallback with product-specific color
              const colors = ['3b82f6', '8b5cf6', '10b981', 'f59e0b', 'ef4444'];
              const color = colors[Math.floor(Math.random() * colors.length)];
              e.currentTarget.src = `https://via.placeholder.com/400x300/${color}/ffffff?text=${encodeURIComponent(product.name.substring(0, 25))}`;
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600">
            <span className="text-white text-sm font-medium px-4 text-center">
              {product.name.substring(0, 30)}
            </span>
          </div>
        )}

        {/* Velocity Badge - Top Right */}
        <div className={`absolute top-2 right-2 px-2 py-1 rounded-full text-xs font-semibold ${getVelocityColor(product.velocity_score || 0)}`}>
          📈 {product.velocity_score || 0}/100
        </div>

        {/* Score Badge - Bottom Right */}
        <div className="absolute bottom-2 right-2 bg-white px-2 py-1 rounded-full shadow-md">
          <span className={`text-sm font-bold ${getScoreColor(product.score || 0)}`}>
            ⭐ {product.score?.toFixed(1) || '0.0'}/10
          </span>
        </div>
      </div>

      {/* Product Details */}
      <div className="p-4">
        {/* Product Name */}
        <h3 className="font-semibold text-gray-800 mb-2 h-12 overflow-hidden">
          {product.name}
        </h3>

        {/* Price & Profit */}
        <div className="flex justify-between items-center mb-3">
          <div>
            <p className="text-2xl font-bold text-green-600">${product.price.toFixed(2)}</p>
            <p className="text-sm text-gray-500">Cost: ${product.cost.toFixed(2)}</p>
          </div>
          <div className="text-right">
            <p className="text-lg font-semibold text-blue-600">
              Profit: ${product.estimated_profit?.toFixed(2)}
            </p>
            <p className="text-xs text-gray-500">{product.profit_margin?.toFixed(0)}% margin</p>
          </div>
        </div>

        {/* Stats Row */}
        <div className="flex justify-between text-sm mb-3 text-gray-600">
          <div className="flex items-center">
            <span className="text-yellow-500 mr-1">⭐</span>
            <span>{product.rating}/5</span>
          </div>
          <div className="flex items-center">
            <span className="mr-1">📦</span>
            <span>{product.orders?.toLocaleString()} orders</span>
          </div>
        </div>

        {/* AliExpress Link */}
        {product.aliexpress_url && (
          <a
            href={product.aliexpress_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full text-center py-2 mb-2 bg-orange-100 text-orange-700 rounded-lg hover:bg-orange-200 transition text-sm font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            {product.source === 'fallback_data' ? (
              <>🔍 Search on AliExpress</>
            ) : (
              <>🔗 View on AliExpress</>
            )}
          </a>
        )}

        {/* Action Buttons */}
        {deploymentStatus?.deployed ? (
          <div className="space-y-2 mb-2">
            <div className="flex gap-2">
              <a
                href={deploymentStatus.shopify_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 py-2 px-4 rounded-lg font-semibold bg-green-500 text-white hover:bg-green-600 transition text-center text-sm"
              >
                ✅ View on Shopify
              </a>
              <button
                onClick={syncDeploymentStatus}
                className="py-2 px-3 rounded-lg font-semibold bg-gray-200 hover:bg-gray-300 transition"
                title="Refresh status"
              >
                🔄
              </button>
            </div>
            <p className="text-xs text-gray-500 text-center">
              Deployed {new Date(deploymentStatus.deployed_at || '').toLocaleDateString()}
            </p>
          </div>
        ) : (
          <div className="flex gap-2 mb-2">
            <button
              onClick={() => onAnalyze(product)}
              className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition font-semibold text-sm"
            >
              🔍 Analyze
            </button>
            <button
              onClick={deployToShopify}
              disabled={deploying}
              className={`flex-1 py-2 px-4 rounded-lg font-semibold transition text-sm ${
                deploying
                  ? 'bg-gray-400 text-white cursor-wait'
                  : 'bg-purple-600 text-white hover:bg-purple-700'
              }`}
            >
              {deploying ? '⏳ Deploying...' : '🚀 Deploy to Shopify'}
            </button>
          </div>
        )}

        {/* Source Badge */}
        <div className="text-xs text-gray-500 text-center">
          Source: {product.source?.replace(/_/g, ' ') || 'Unknown'}
        </div>
      </div>
    </div>
  );
}
