import { useState, useEffect } from 'react';
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
  Edit2,
  ExternalLink,
  ShoppingBag,
} from 'lucide-react';
import { shopifyAPI, type DeployRequest, type DeployResult } from '../services/api';

interface DeployPreviewModalProps {
  product: {
    id: string;
    name: string;
    niche?: string;
    image_url?: string;
    cost?: number;
    price?: number;
    supplier_url?: string;
    features?: string[];
    description?: string;
  };
  onClose: () => void;
  onSuccess?: (result: DeployResult) => void;
}

export const DeployPreviewModal: React.FC<DeployPreviewModalProps> = ({
  product,
  onClose,
  onSuccess,
}) => {
  const [loading, setLoading] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [preview, setPreview] = useState<DeployResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [deploymentSuccess, setDeploymentSuccess] = useState<DeployResult | null>(null);

  // Editable fields
  const [editedTitle, setEditedTitle] = useState('');
  const [editedDescription, setEditedDescription] = useState('');
  const [editedPrice, setEditedPrice] = useState('');
  const [editedTags, setEditedTags] = useState<string[]>([]);

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

  // Auto-generate preview on mount
  useEffect(() => {
    handleGeneratePreview();
  }, []);

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

      // Set editable fields from preview
      if (result.content_generated) {
        setEditedTitle(result.content_generated.title || product.name);
        setEditedDescription(result.content_generated.description || product.description || '');
        setEditedTags(result.content_generated.tags || []);
      }
      if (result.price) {
        setEditedPrice(result.price);
      }
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
        name: editedTitle, // Use edited title
        niche: product.niche || 'general',
        supplier_cost: product.cost || 0,
        supplier_url: product.supplier_url,
        images: product.image_url ? [product.image_url] : [],
        description: editedDescription, // Use edited description
        features: product.features || [],
        ...aiSettings,
      };

      const result = await shopifyAPI.deployProduct(request);
      if (result.success) {
        setDeploymentSuccess(result);
        onSuccess?.(result);
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

  // Success Modal
  if (deploymentSuccess) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full">
          <div className="p-8 text-center">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-12 h-12 text-green-600" />
            </div>
            <h2 className="text-3xl font-bold text-primary mb-3">
              Product Deployed Successfully!
            </h2>
            <p className="text-secondary mb-6">
              Your product has been {deploymentSuccess.published ? 'published' : 'saved as draft'} to your Shopify store
            </p>

            {/* Deployment Details */}
            <div className="  rounded-lg p-4 mb-6 text-left">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-tertiary uppercase font-medium">Product Title</p>
                  <p className="text-sm font-semibold text-primary mt-1">{editedTitle}</p>
                </div>
                {editedPrice && (
                  <div>
                    <p className="text-xs text-tertiary uppercase font-medium">Price</p>
                    <p className="text-sm font-semibold text-primary mt-1">${editedPrice}</p>
                  </div>
                )}
                {deploymentSuccess.ai_costs && (
                  <div>
                    <p className="text-xs text-tertiary uppercase font-medium">AI Cost</p>
                    <p className="text-sm font-semibold text-primary mt-1">
                      ${deploymentSuccess.ai_costs.total.toFixed(2)}
                    </p>
                  </div>
                )}
                {deploymentSuccess.processing_time_seconds && (
                  <div>
                    <p className="text-xs text-tertiary uppercase font-medium">Processing Time</p>
                    <p className="text-sm font-semibold text-primary mt-1">
                      {deploymentSuccess.processing_time_seconds.toFixed(1)}s
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              {deploymentSuccess.shopify_url && (
                <a
                  href={deploymentSuccess.shopify_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:opacity-90 transition flex items-center justify-center gap-2 font-semibold"
                >
                  <ExternalLink className="w-5 h-5" />
                  View in Store
                </a>
              )}
              {deploymentSuccess.admin_url && (
                <a
                  href={deploymentSuccess.admin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition flex items-center justify-center gap-2 font-semibold"
                >
                  <ShoppingBag className="w-5 h-5" />
                  Edit in Shopify
                </a>
              )}
            </div>

            <button
              onClick={onClose}
              className="mt-4 w-full px-6 py-3 border border-white/10 rounded-lg hover:  transition font-medium text-secondary"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-2xl max-w-5xl w-full my-8">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-white/10 sticky top-0 bg-white rounded-t-xl z-10">
          <div>
            <h2 className="text-2xl font-bold text-primary flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-indigo-600" />
              Deploy to Shopify - AI Preview
            </h2>
            <p className="text-tertiary mt-1">Review and edit AI-generated content before deploying</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            <X className="w-5 h-5 text-tertiary" />
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="p-12 text-center">
            <Loader2 className="w-16 h-16 animate-spin text-indigo-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-primary mb-2">
              Generating AI Preview...
            </h3>
            <p className="text-secondary">
              Our AI is creating optimized content for your product
            </p>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="p-6">
            <div className="p-4 bg-red-500/10 border border-red-200 rounded-lg flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-red-800">
                <p className="font-medium">Error</p>
                <p className="mt-1">{error}</p>
              </div>
            </div>
            <button
              onClick={handleGeneratePreview}
              className="mt-4 w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Preview Content */}
        {preview && !loading && (
          <div className="max-h-[calc(90vh-200px)] overflow-y-auto">
            {/* Product Info */}
            <div className="p-6 border-b border-white/10 bg-gradient-to-r from-indigo-50 to-purple-50">
              <div className="flex items-start gap-4">
                {product.image_url && (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="w-24 h-24 rounded-lg object-cover shadow-md"
                  />
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-primary">{product.name}</h3>
                  <div className="flex items-center gap-3 mt-2">
                    {product.niche && (
                      <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-1 rounded-full font-medium">
                        {product.niche}
                      </span>
                    )}
                    {product.cost && (
                      <span className="text-sm text-secondary">
                        Supplier Cost: ${product.cost.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Editable Title */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Edit2 className="w-4 h-4 text-tertiary" />
                  <label className="text-sm font-medium text-secondary">Product Title</label>
                </div>
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="w-full border border-white/10 rounded-lg px-4 py-2 text-primary focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="Enter product title"
                />
              </div>

              {/* Editable Description */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-tertiary" />
                  <label className="text-sm font-medium text-secondary">Product Description</label>
                </div>
                <textarea
                  value={editedDescription}
                  onChange={(e) => setEditedDescription(e.target.value)}
                  rows={6}
                  className="w-full border border-white/10 rounded-lg px-4 py-2 text-primary focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="Enter product description"
                />
              </div>

              {/* SEO Preview */}
              <div className="  border border-white/10 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Tag className="w-4 h-4 text-secondary" />
                  <h3 className="font-semibold text-primary">SEO Preview</h3>
                </div>
                <div className="space-y-2">
                  <div>
                    <p className="text-xs text-tertiary uppercase font-medium">Meta Title</p>
                    <p className="text-sm text-indigo-600 font-medium mt-1">{editedTitle}</p>
                  </div>
                  <div>
                    <p className="text-xs text-tertiary uppercase font-medium">Meta Description</p>
                    <p className="text-sm text-secondary mt-1 line-clamp-2">
                      {editedDescription.substring(0, 160)}...
                    </p>
                  </div>
                  {editedTags.length > 0 && (
                    <div>
                      <p className="text-xs text-tertiary uppercase font-medium">Tags</p>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {editedTags.map((tag, idx) => (
                          <span key={idx} className="text-xs bg-gray-100 text-secondary px-2 py-1 rounded-full">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Pricing */}
              {editedPrice && (
                <div className="bg-green-500/100/10 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <DollarSign className="w-4 h-4 text-green-600" />
                    <h3 className="font-semibold text-green-900">Pricing</h3>
                  </div>
                  <div className="flex items-center gap-4">
                    <div>
                      <label className="text-xs text-green-400 font-medium">Selling Price</label>
                      <input
                        type="number"
                        step="0.01"
                        value={editedPrice}
                        onChange={(e) => setEditedPrice(e.target.value)}
                        className="w-32 border border-green-300 rounded-lg px-3 py-2 text-xl font-bold text-green-600 mt-1"
                      />
                    </div>
                    {product.cost && (
                      <div>
                        <p className="text-xs text-green-400 font-medium">Profit Margin</p>
                        <p className="text-lg font-bold text-green-600 mt-1">
                          {(((Number(editedPrice) - product.cost) / Number(editedPrice)) * 100).toFixed(1)}%
                        </p>
                      </div>
                    )}
                    {product.cost && (
                      <div>
                        <p className="text-xs text-green-400 font-medium">Profit</p>
                        <p className="text-lg font-bold text-green-600 mt-1">
                          ${(Number(editedPrice) - product.cost).toFixed(2)}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Image Enhancement Status */}
              {preview.images_enhanced !== undefined && preview.images_enhanced > 0 && (
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-purple-700">
                    <ImageIcon className="w-5 h-5" />
                    <h3 className="font-semibold">Images Enhanced</h3>
                  </div>
                  <p className="text-sm text-purple-700 mt-1">
                    {preview.images_enhanced} image{preview.images_enhanced !== 1 ? 's' : ''} processed with AI background removal
                  </p>
                </div>
              )}

              {/* AI Costs */}
              {preview.ai_costs && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-amber-700 mb-3">
                    <Tag className="w-5 h-5" />
                    <h3 className="font-semibold">Estimated AI Processing Costs</h3>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <p className="text-xs text-amber-600 font-medium">Content Generation</p>
                      <p className="text-lg font-bold text-amber-900">${preview.ai_costs.content.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-amber-600 font-medium">Image Enhancement</p>
                      <p className="text-lg font-bold text-amber-900">${preview.ai_costs.images.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-amber-600 font-medium">Total Cost</p>
                      <p className="text-lg font-bold text-amber-900">${preview.ai_costs.total.toFixed(2)}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* AI Settings (Collapsible) */}
              <div>
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-2 text-secondary hover:text-primary mb-3 font-medium"
                >
                  <Settings className="w-4 h-4" />
                  <span>AI Settings</span>
                  <span className="text-xs text-tertiary">({showAdvanced ? 'Hide' : 'Show'})</span>
                </button>

                {showAdvanced && (
                  <div className="  border border-white/10 rounded-lg p-4">
                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={aiSettings.ai_content}
                          onChange={(e) => setAiSettings({ ...aiSettings, ai_content: e.target.checked })}
                          className="rounded border-white/10 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm">Generate AI Content</span>
                      </label>

                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={aiSettings.ai_images}
                          onChange={(e) => setAiSettings({ ...aiSettings, ai_images: e.target.checked })}
                          className="rounded border-white/10 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm">Enhance Images</span>
                      </label>

                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={aiSettings.publish}
                          onChange={(e) => setAiSettings({ ...aiSettings, publish: e.target.checked })}
                          className="rounded border-white/10 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm">Auto-Publish (vs Draft)</span>
                      </label>

                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={aiSettings.add_branding}
                          onChange={(e) => setAiSettings({ ...aiSettings, add_branding: e.target.checked })}
                          className="rounded border-white/10 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm">Add Branding</span>
                      </label>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Footer Actions */}
        {preview && !loading && (
          <div className="flex items-center justify-between p-6 border-t border-white/10   sticky bottom-0 rounded-b-xl">
            <button
              onClick={onClose}
              className="px-6 py-2.5 border border-white/10 rounded-lg hover:bg-white transition font-medium text-secondary"
            >
              Cancel
            </button>

            <button
              onClick={handleDeploy}
              disabled={deploying || !editedTitle || !editedDescription}
              className="px-8 py-2.5 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:opacity-90 transition flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg"
            >
              {deploying ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Deploying to Shopify...
                </>
              ) : (
                <>
                  <Rocket className="w-5 h-5" />
                  Deploy to Shopify
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default DeployPreviewModal;
