import { useState, useEffect, useCallback } from 'react';
import { 
  ShoppingBag, 
  RefreshCw, 
  Rocket, 
  Trash2, 
  ExternalLink,
  Package,
  DollarSign,
  TrendingUp,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-react';
import { GlassPanel } from '../components/GlassPanel';
import { shopifyAPI, type ShopifyProduct, type DeployRequest, type DeployResult } from '../lib/api';

interface ShopifyStatus {
  configured: boolean;
  store_name: string;
  store_domain?: string;
  connection: string;
  error?: string;
}

interface ShopifyAnalytics {
  total_products: number;
  total_inventory: number;
  estimated_value: number;
  ospra_tracked: number;
}

export const ShopifyPage = () => {
  const [status, setStatus] = useState<ShopifyStatus | null>(null);
  const [products, setProducts] = useState<ShopifyProduct[]>([]);
  const [analytics, setAnalytics] = useState<ShopifyAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [deploying, setDeploying] = useState(false);
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deployResult, setDeployResult] = useState<DeployResult | null>(null);

  // Deploy form state
  const [deployForm, setDeployForm] = useState({
    name: '',
    niche: 'smart home',
    supplier_cost: '',
    supplier_url: '',
    image_url: '',
    generate_ai_description: true,
  });

  const fetchStatus = useCallback(async () => {
    try {
      const data = await shopifyAPI.getStatus();
      setStatus(data);
    } catch (error) {
      console.error('Failed to fetch status:', error);
      setStatus({ configured: false, store_name: 'Not configured', connection: 'error' });
    }
  }, []);

  const fetchProducts = useCallback(async () => {
    try {
      const data = await shopifyAPI.getProducts(50);
      setProducts(data);
    } catch (error) {
      console.error('Failed to fetch products:', error);
    }
  }, []);

  const fetchAnalytics = useCallback(async () => {
    try {
      const data = await shopifyAPI.getAnalytics();
      setAnalytics(data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchStatus(), fetchProducts(), fetchAnalytics()]);
    setLoading(false);
  }, [fetchStatus, fetchProducts, fetchAnalytics]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDeploy = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeploying(true);
    setDeployResult(null);

    const request: DeployRequest = {
      product_id: `ospra_${Date.now()}`,
      name: deployForm.name,
      niche: deployForm.niche,
      supplier_cost: parseFloat(deployForm.supplier_cost) || 0,
      supplier_url: deployForm.supplier_url,
      images: deployForm.image_url ? [deployForm.image_url] : [],
      generate_ai_description: deployForm.generate_ai_description,
      auto_publish: true,
    };

    try {
      const result = await shopifyAPI.deployProduct(request);
      setDeployResult(result);
      
      if (result.success) {
        // Refresh products list
        await fetchProducts();
        await fetchAnalytics();
        
        // Reset form
        setDeployForm({
          name: '',
          niche: 'smart home',
          supplier_cost: '',
          supplier_url: '',
          image_url: '',
          generate_ai_description: true,
        });
      }
    } catch (error) {
      setDeployResult({
        success: false,
        product_id: request.product_id,
        error: 'Deployment failed. Check console for details.',
      });
    } finally {
      setDeploying(false);
    }
  };

  const handleDelete = async (productId: number) => {
    if (!confirm('Are you sure you want to delete this product from Shopify?')) return;
    
    try {
      await shopifyAPI.deleteProduct(productId);
      await fetchProducts();
      await fetchAnalytics();
    } catch (error) {
      console.error('Failed to delete:', error);
      alert('Failed to delete product');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-12 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-indigo-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading Shopify data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-12">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-light text-gray-900 flex items-center gap-3">
              <ShoppingBag className="w-8 h-8 text-indigo-600" />
              Shopify Store
            </h1>
            <p className="text-gray-500 mt-1">Manage your products and deploy from Ospra Intelligence</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={loadData}
              className="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
            <button
              onClick={() => setShowDeployModal(true)}
              className="px-5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:opacity-90 transition flex items-center gap-2 shadow-lg shadow-indigo-500/25"
            >
              <Rocket className="w-4 h-4" />
              Deploy Product
            </button>
          </div>
        </div>

        {/* Connection Status */}
        <GlassPanel className="p-6">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${
                status?.connection === 'active' ? 'bg-green-500 animate-pulse' : 'bg-red-500'
              }`} />
              <span className="font-medium text-gray-900">
                {status?.connection === 'active' ? 'Connected' : 'Not Connected'}
              </span>
            </div>
            <div className="text-gray-400">|</div>
            <div className="text-gray-600">
              Store: <span className="text-indigo-600 font-medium">{status?.store_name || 'N/A'}</span>
            </div>
            {status?.store_domain && (
              <>
                <div className="text-gray-400">|</div>
                <a 
                  href={`https://${status.store_domain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:underline flex items-center gap-1"
                >
                  View Store <ExternalLink className="w-3 h-3" />
                </a>
              </>
            )}
          </div>
        </GlassPanel>

        {/* Analytics Cards */}
        {analytics && (
          <div className="grid grid-cols-4 gap-6">
            <GlassPanel className="p-6">
              <div className="flex items-center justify-between mb-4">
                <Package className="w-8 h-8 text-indigo-500" />
                <span className="text-xs text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full">Products</span>
              </div>
              <p className="text-3xl font-bold text-gray-900">{analytics.total_products}</p>
              <p className="text-sm text-gray-500">Total Products</p>
            </GlassPanel>

            <GlassPanel className="p-6">
              <div className="flex items-center justify-between mb-4">
                <TrendingUp className="w-8 h-8 text-emerald-500" />
                <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">Inventory</span>
              </div>
              <p className="text-3xl font-bold text-gray-900">{analytics.total_inventory.toLocaleString()}</p>
              <p className="text-sm text-gray-500">Units in Stock</p>
            </GlassPanel>

            <GlassPanel className="p-6">
              <div className="flex items-center justify-between mb-4">
                <DollarSign className="w-8 h-8 text-amber-500" />
                <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-full">Value</span>
              </div>
              <p className="text-3xl font-bold text-gray-900">${analytics.estimated_value.toLocaleString()}</p>
              <p className="text-sm text-gray-500">Estimated Value</p>
            </GlassPanel>

            <GlassPanel className="p-6">
              <div className="flex items-center justify-between mb-4">
                <CheckCircle className="w-8 h-8 text-purple-500" />
                <span className="text-xs text-purple-600 bg-purple-50 px-2 py-1 rounded-full">Ospra</span>
              </div>
              <p className="text-3xl font-bold text-gray-900">{analytics.ospra_tracked}</p>
              <p className="text-sm text-gray-500">Ospra Tracked</p>
            </GlassPanel>
          </div>
        )}

        {/* Products Grid */}
        <GlassPanel className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">Store Products</h2>
          
          {products.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-lg">
              <Package className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No products in your store yet.</p>
              <p className="text-sm text-gray-400 mt-1">Deploy your first product to get started!</p>
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-4">
              {products.map((product) => (
                <div 
                  key={product.id}
                  className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:border-indigo-300 hover:shadow-lg transition group"
                >
                  <div className="aspect-square bg-gray-100 relative">
                    {product.image_url ? (
                      <img 
                        src={product.image_url} 
                        alt={product.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-12 h-12 text-gray-300" />
                      </div>
                    )}
                    <button
                      onClick={() => handleDelete(product.id)}
                      className="absolute top-2 right-2 p-2 bg-red-500 text-white rounded-lg opacity-0 group-hover:opacity-100 transition hover:bg-red-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="p-4">
                    <h3 className="font-medium text-gray-900 truncate">{product.title}</h3>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-lg font-bold text-indigo-600">${product.price}</span>
                      <span className="text-sm text-gray-500">{product.inventory_quantity} in stock</span>
                    </div>
                    {product.ospra_tracked && (
                      <span className="inline-flex items-center gap-1 text-xs text-green-600 mt-2">
                        <CheckCircle className="w-3 h-3" /> Ospra Tracked
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassPanel>

        {/* Deploy Modal */}
        {showDeployModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  <Rocket className="w-5 h-5 text-indigo-600" />
                  Deploy Product to Shopify
                </h2>
                <button 
                  onClick={() => {
                    setShowDeployModal(false);
                    setDeployResult(null);
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XCircle className="w-6 h-6" />
                </button>
              </div>

              {deployResult && (
                <div className={`mb-6 p-4 rounded-lg ${
                  deployResult.success 
                    ? 'bg-green-50 border border-green-200' 
                    : 'bg-red-50 border border-red-200'
                }`}>
                  {deployResult.success ? (
                    <div>
                      <p className="font-semibold text-green-800 flex items-center gap-2">
                        <CheckCircle className="w-5 h-5" /> Deployed Successfully!
                      </p>
                      <p className="text-sm text-green-700 mt-1">Price: ${deployResult.price}</p>
                      {deployResult.shopify_url && (
                        <a 
                          href={deployResult.shopify_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-green-600 hover:underline flex items-center gap-1 mt-2"
                        >
                          View Product <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  ) : (
                    <p className="text-red-800 flex items-center gap-2">
                      <XCircle className="w-5 h-5" /> {deployResult.error}
                    </p>
                  )}
                </div>
              )}

              <form onSubmit={handleDeploy} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Product Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={deployForm.name}
                    onChange={(e) => setDeployForm({ ...deployForm, name: e.target.value })}
                    placeholder="Smart LED Strip Lights"
                    className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Niche / Category
                  </label>
                  <input
                    type="text"
                    value={deployForm.niche}
                    onChange={(e) => setDeployForm({ ...deployForm, niche: e.target.value })}
                    placeholder="smart home"
                    className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Supplier Cost ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={deployForm.supplier_cost}
                    onChange={(e) => setDeployForm({ ...deployForm, supplier_cost: e.target.value })}
                    placeholder="8.50"
                    className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Supplier URL (AliExpress)
                  </label>
                  <input
                    type="url"
                    value={deployForm.supplier_url}
                    onChange={(e) => setDeployForm({ ...deployForm, supplier_url: e.target.value })}
                    placeholder="https://aliexpress.com/item/..."
                    className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Image URL
                  </label>
                  <input
                    type="url"
                    value={deployForm.image_url}
                    onChange={(e) => setDeployForm({ ...deployForm, image_url: e.target.value })}
                    placeholder="https://..."
                    className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="generateAI"
                    checked={deployForm.generate_ai_description}
                    onChange={(e) => setDeployForm({ ...deployForm, generate_ai_description: e.target.checked })}
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <label htmlFor="generateAI" className="text-sm text-gray-700">
                    Generate AI description (Claude)
                  </label>
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowDeployModal(false);
                      setDeployResult(null);
                    }}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={deploying || !deployForm.name}
                    className="flex-1 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:opacity-90 transition flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {deploying ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Deploying...
                      </>
                    ) : (
                      <>
                        <Rocket className="w-4 h-4" />
                        Deploy
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ShopifyPage;
