import { useState } from 'react';
import {
  X,
  Sparkles,
  Image as ImageIcon,
  DollarSign,
  Tag,
  FileText,
  Rocket,
  Loader2,
  CheckCircle,
  AlertCircle,
  Settings,
} from 'lucide-react';
import { shopifyAPI, type DeployRequest, type DeployResult } from '../services/api';

interface AIDeploymentPreviewProps {
  product: {
    id: string;
    name: string;
    niche?: string;
    image_url?: string;
    cost?: number;
    supplier_url?: string;
    features?: string[];
    description?: string;
  };
  onClose: () => void;
  onSuccess?: (result: DeployResult) => void;
}

export const AIDeploymentPreview: React.FC<AIDeploymentPreviewProps> = ({
  product,
  onClose,
  onSuccess,
}) => {
  const [loading, setLoading] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [preview, setPreview] = useState<DeployResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // AI Control Flags
  const [aiSettings, setAiSettings] = useState({
    ai_content: true,
    ai_images: true,
    ai_pricing: true,
    ai_seo: true,
    publish: false,
    target_margin: 0.4,
    add_branding: true,
    max_images: 5,
  });

  const handleGeneratePreview = async () => {
    setLoading(true);
    setError(null);
    try {
      const request: DeployRequest = {
        product_id: product.id,
        name: product.name,
        niche: product.niche || 'general',
        supplier_cost: product.cost || 0,
        supplier_url: product.supplier_url,
        images: product.image_url ? [product.image_url] : [],
        description: product.description,
        features: product.features || [],
        ...aiSettings,
      };

      const result = await shopifyAPI.previewDeployment(request);
      setPreview(result);
    } catch (err: any) {
      console.error('Preview failed:', err);
      setError(err.response?.data?.detail || 'Failed to generate preview');
    } finally {
      setLoading(false);
    }
  };

  const handleDeploy = async () => {
    if (!preview) return;

    setDeploying(true);
    setError(null);
    try {
      const request: DeployRequest = {
        product_id: product.id,
        name: product.name,
        niche: product.niche || 'general',
        supplier_cost: product.cost || 0,
        supplier_url: product.supplier_url,
        images: product.image_url ? [product.image_url] : [],
        description: product.description,
        features: product.features || [],
        ...aiSettings,
      };

      const result = await shopifyAPI.deployProduct(request);
      if (result.success) {
        onSuccess?.(result);
        onClose();
      } else {
        setError(result.error || 'Deployment failed');
      }
    } catch (err: any) {
      console.error('Deployment failed:', err);
      setError(err.response?.data?.detail || 'Failed to deploy product');
    } finally {
      setDeploying(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-indigo-600" />
              AI Deployment Preview
            </h2>
            <p className="text-gray-500 mt-1">Review AI-generated content before deploying</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Product Info */}
        <div className="p-6 border-b border-gray-200 bg-gray-50">
          <div className="flex items-start gap-4">
            {product.image_url && (
              <img
                src={product.image_url}
                alt={product.name}
                className="w-24 h-24 rounded-lg object-cover"
              />
            )}
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{product.name}</h3>
              <div className="flex items-center gap-3 mt-2">
                {product.niche && (
                  <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded-full">
                    {product.niche}
                  </span>
                )}
                {product.cost && (
                  <span className="text-sm text-gray-600">
                    Cost: ${product.cost.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* AI Settings */}
        <div className="p-6 border-b border-gray-200">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-gray-700 hover:text-gray-900 mb-4"
          >
            <Settings className="w-4 h-4" />
            <span className="font-medium">AI Settings</span>
            <span className="text-xs text-gray-500">(Click to {showAdvanced ? 'hide' : 'show'})</span>
          </button>

          {showAdvanced && (
            <div className="grid grid-cols-2 gap-4 mb-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aiSettings.ai_content}
                  onChange={(e) => setAiSettings({ ...aiSettings, ai_content: e.target.checked })}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm">Generate AI Content</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aiSettings.ai_images}
                  onChange={(e) => setAiSettings({ ...aiSettings, ai_images: e.target.checked })}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm">Enhance Images</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aiSettings.ai_pricing}
                  onChange={(e) => setAiSettings({ ...aiSettings, ai_pricing: e.target.checked })}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm">AI Pricing</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aiSettings.ai_seo}
                  onChange={(e) => setAiSettings({ ...aiSettings, ai_seo: e.target.checked })}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm">SEO Optimization</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aiSettings.publish}
                  onChange={(e) => setAiSettings({ ...aiSettings, publish: e.target.checked })}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm">Auto-Publish (vs Draft)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aiSettings.add_branding}
                  onChange={(e) => setAiSettings({ ...aiSettings, add_branding: e.target.checked })}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm">Add Branding</span>
              </label>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Target Margin (%)</label>
                <input
                  type="number"
                  min="10"
                  max="90"
                  value={aiSettings.target_margin * 100}
                  onChange={(e) => setAiSettings({ ...aiSettings, target_margin: Number(e.target.value) / 100 })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Max Images</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={aiSettings.max_images}
                  onChange={(e) => setAiSettings({ ...aiSettings, max_images: Number(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
          )}

          {!preview && (
            <button
              onClick={handleGeneratePreview}
              disabled={loading}
              className="w-full px-4 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:opacity-90 transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Generating Preview...
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  Generate AI Preview
                </>
              )}
            </button>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <div className="p-6 border-b border-gray-200">
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-red-800">
                <p className="font-medium">Error</p>
                <p className="mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Preview Content */}
        {preview && (
          <div className="p-6 space-y-6">
            {/* AI-Generated Content */}
            {preview.content_generated && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-indigo-600">
                  <FileText className="w-5 h-5" />
                  <h3 className="font-semibold">AI-Generated Content</h3>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-medium text-gray-500 uppercase">Title</label>
                    <p className="mt-1 text-gray-900 font-medium">{preview.content_generated.title}</p>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-gray-500 uppercase">Description</label>
                    <p className="mt-1 text-gray-700 text-sm whitespace-pre-wrap">
                      {preview.content_generated.description}
                    </p>
                  </div>

                  {preview.content_generated.tags && preview.content_generated.tags.length > 0 && (
                    <div>
                      <label className="text-xs font-medium text-gray-500 uppercase">SEO Tags</label>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {preview.content_generated.tags.map((tag, idx) => (
                          <span key={idx} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Pricing */}
            {preview.price && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-2 text-green-700 mb-2">
                  <DollarSign className="w-5 h-5" />
                  <h3 className="font-semibold">AI-Generated Pricing</h3>
                </div>
                <p className="text-2xl font-bold text-green-600">${preview.price}</p>
                {product.cost && (
                  <p className="text-sm text-green-700 mt-1">
                    Margin: {(((Number(preview.price) - product.cost) / Number(preview.price)) * 100).toFixed(1)}%
                  </p>
                )}
              </div>
            )}

            {/* Image Enhancement */}
            {preview.images_enhanced !== undefined && preview.images_enhanced > 0 && (
              <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
                <div className="flex items-center gap-2 text-purple-700">
                  <ImageIcon className="w-5 h-5" />
                  <h3 className="font-semibold">Images Enhanced</h3>
                </div>
                <p className="text-sm text-purple-700 mt-1">
                  {preview.images_enhanced} image{preview.images_enhanced !== 1 ? 's' : ''} processed with AI
                </p>
              </div>
            )}

            {/* AI Costs */}
            {preview.ai_costs && (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-center gap-2 text-amber-700 mb-2">
                  <Tag className="w-5 h-5" />
                  <h3 className="font-semibold">AI Processing Costs</h3>
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-amber-600">Content</p>
                    <p className="font-semibold text-amber-900">${preview.ai_costs.content.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-amber-600">Images</p>
                    <p className="font-semibold text-amber-900">${preview.ai_costs.images.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-amber-600">Total</p>
                    <p className="font-semibold text-amber-900">${preview.ai_costs.total.toFixed(2)}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Success Indicator */}
            {preview.success && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-2 text-blue-700">
                  <CheckCircle className="w-5 h-5" />
                  <p className="font-medium">Preview generated successfully!</p>
                </div>
                <p className="text-sm text-blue-600 mt-1">
                  Review the content above and click "Deploy to Shopify" when ready.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
          >
            Cancel
          </button>

          {preview && (
            <button
              onClick={handleDeploy}
              disabled={deploying}
              className="px-6 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:opacity-90 transition flex items-center gap-2 disabled:opacity-50"
            >
              {deploying ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Deploying...
                </>
              ) : (
                <>
                  <Rocket className="w-5 h-5" />
                  Deploy to Shopify
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default AIDeploymentPreview;
