import React, { useState, useEffect } from 'react';
import {
  Store,
  Plus,
  Settings,
  Pause,
  Play,
  Trash2,
  ExternalLink,
  Star,
  TrendingUp,
  Package,
  DollarSign,
  ShoppingCart,
  AlertCircle,
  CheckCircle,
  XCircle,
  Crown,
  Zap,
  Rocket,
  Globe
} from 'lucide-react';

// Types
interface StoreData {
  id: number;
  store_name: string;
  store_url: string;
  platform: string;
  total_revenue: number;
  monthly_revenue: number;
  total_orders: number;
  conversion_rate: number;
  product_count: number;
  is_active: boolean;
  rank_position: number;
  rank_change: number;
  rank_change_label: string;
  last_sync: string | null;
  niche?: string;
  brand_voice?: string;
  notifications_enabled?: boolean;
  auto_deploy_enabled?: boolean;
}

interface AddStoreRequest {
  store_name: string;
  store_url: string;
  platform: string;
  credentials: {
    access_token: string;
    shop_domain: string;
  };
}

interface SubscriptionTier {
  name: string;
  store_limit: number;
  icon: React.ReactNode;
  color: string;
}

const TIERS: Record<string, SubscriptionTier> = {
  NEST: { name: 'Nest', store_limit: 1, icon: <Store className="w-5 h-5" />, color: 'text-gray-600' },
  FLIGHT: { name: 'Flight', store_limit: 1, icon: <Zap className="w-5 h-5" />, color: 'text-blue-600' },
  SOAR: { name: 'Soar', store_limit: 5, icon: <Rocket className="w-5 h-5" />, color: 'text-purple-600' },
  STRATOSPHERE: { name: 'Stratosphere', store_limit: Infinity, icon: <Crown className="w-5 h-5" />, color: 'text-yellow-600' }
};

export default function StoresPage() {
  const [stores, setStores] = useState<StoreData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddFlow, setShowAddFlow] = useState(false);
  const [selectedStore, setSelectedStore] = useState<StoreData | null>(null);
  const [userTier, setUserTier] = useState<string>('NEST');

  useEffect(() => {
    fetchStores();
  }, []);

  const fetchStores = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/portfolio/rankings');
      if (response.ok) {
        const data = await response.json();
        setStores(data);
      }
    } catch (error) {
      console.error('Failed to fetch stores:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePauseStore = async (storeId: number) => {
    try {
      const response = await fetch(`http://localhost:8001/api/portfolio/stores/${storeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: false })
      });
      if (response.ok) {
        fetchStores();
      }
    } catch (error) {
      console.error('Failed to pause store:', error);
    }
  };

  const handleActivateStore = async (storeId: number) => {
    try {
      const response = await fetch(`http://localhost:8001/api/portfolio/stores/${storeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: true })
      });
      if (response.ok) {
        fetchStores();
      }
    } catch (error) {
      console.error('Failed to activate store:', error);
    }
  };

  const handleDeleteStore = async (storeId: number) => {
    if (!confirm('Are you sure you want to disconnect this store? This action cannot be undone.')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8001/api/portfolio/stores/${storeId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        fetchStores();
      }
    } catch (error) {
      console.error('Failed to delete store:', error);
    }
  };

  const handleMakePrimary = async (storeId: number) => {
    try {
      const response = await fetch(`http://localhost:8001/api/portfolio/stores/${storeId}/switch`, {
        method: 'POST'
      });
      if (response.ok) {
        fetchStores();
      }
    } catch (error) {
      console.error('Failed to make store primary:', error);
    }
  };

  const getPlatformIcon = (platform: string) => {
    const platformLower = platform.toLowerCase();
    if (platformLower === 'shopify') {
      return <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
        <span className="text-green-600 text-lg font-bold">S</span>
      </div>;
    } else if (platformLower === 'amazon') {
      return <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
        <span className="text-orange-600 text-lg font-bold">A</span>
      </div>;
    } else if (platformLower === 'woocommerce') {
      return <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
        <span className="text-purple-600 text-lg font-bold">W</span>
      </div>;
    }
    return <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
      <Store className="w-5 h-5 text-blue-600" />
    </div>;
  };

  const getStatusBadge = (store: StoreData) => {
    if (store.is_active) {
      return (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-green-500/10 text-green-700">
          <CheckCircle className="w-3.5 h-3.5" />
          <span className="text-xs font-medium">Active</span>
        </div>
      );
    } else {
      return (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-amber-500/10 text-amber-700">
          <Pause className="w-3.5 h-3.5" />
          <span className="text-xs font-medium">Paused</span>
        </div>
      );
    }
  };

  const currentTier = TIERS[userTier];
  const storeUsage = stores.length;
  const storeLimit = currentTier.store_limit;
  const canAddStore = storeUsage < storeLimit;
  const usagePercent = storeLimit === Infinity ? 0 : (storeUsage / storeLimit) * 100;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary">Store Management</h1>
          <p className="text-sm text-tertiary mt-1">Manage all your connected e-commerce stores</p>
        </div>
        <button
          onClick={() => setShowAddFlow(true)}
          disabled={!canAddStore}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
            canAddStore
              ? 'bg-blue-600 text-white hover:bg-blue-700 hover:scale-105'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          <Plus className="w-4 h-4" />
          Connect New Store
        </button>
      </div>

      {/* D) Store Limits by Tier */}
      <div className="bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl p-6 border border-blue-100">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`${currentTier.color}`}>
              {currentTier.icon}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-primary">{currentTier.name} Plan</h3>
              <p className="text-sm text-tertiary">
                {storeLimit === Infinity ? 'Unlimited stores' : `Up to ${storeLimit} store${storeLimit > 1 ? 's' : ''}`}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-primary">
              {storeUsage} <span className="text-tertiary text-lg">/ {storeLimit === Infinity ? '∞' : storeLimit}</span>
            </div>
            <p className="text-xs text-tertiary mt-1">Stores connected</p>
          </div>
        </div>

        {/* Usage Bar */}
        {storeLimit !== Infinity && (
          <div className="mt-4">
            <div className="h-2 bg-white rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  usagePercent >= 100 ? 'bg-red-500' : usagePercent >= 75 ? 'bg-amber-500' : 'bg-blue-500'
                }`}
                style={{ width: `${Math.min(usagePercent, 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Upgrade Prompt */}
        {!canAddStore && (
          <div className="mt-4 p-3 bg-white rounded-lg border border-amber-200">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-primary">Store limit reached</p>
                <p className="text-xs text-tertiary mt-1">
                  Upgrade to connect more stores and unlock advanced features
                </p>
              </div>
              <button className="px-3 py-1.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white text-xs font-medium rounded-lg hover:scale-105 transition-transform">
                Upgrade Now
              </button>
            </div>
          </div>
        )}

        {/* Tier Comparison */}
        <div className="mt-4 pt-4 border-t border-blue-100">
          <p className="text-xs font-medium text-tertiary uppercase tracking-wide mb-3">Available Plans</p>
          <div className="grid grid-cols-4 gap-3">
            {Object.entries(TIERS).map(([key, tier]) => (
              <div
                key={key}
                className={`p-3 rounded-lg border transition-all ${
                  userTier === key
                    ? 'bg-white border-blue-300 shadow-sm'
                    : 'bg-white/50 border-gray-200 hover:border-blue-200'
                }`}
              >
                <div className={`${tier.color} mb-2`}>{tier.icon}</div>
                <div className="text-sm font-semibold text-primary">{tier.name}</div>
                <div className="text-xs text-tertiary mt-1">
                  {tier.store_limit === Infinity ? 'Unlimited' : `${tier.store_limit} store${tier.store_limit > 1 ? 's' : ''}`}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* A) Connected Stores Grid */}
      <div>
        <h2 className="text-lg font-semibold text-primary mb-4">Connected Stores ({stores.length})</h2>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-xl p-6 border border-black/10 animate-pulse">
                <div className="h-10 w-10 bg-gray-200 rounded-lg mb-4" />
                <div className="h-4 bg-gray-200 rounded w-2/3 mb-2" />
                <div className="h-3 bg-gray-200 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : stores.length === 0 ? (
          <div className="bg-white rounded-xl p-12 border border-black/10 text-center">
            <Store className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-primary mb-2">No stores connected</h3>
            <p className="text-sm text-tertiary mb-6">Connect your first store to start managing your e-commerce portfolio</p>
            <button
              onClick={() => setShowAddFlow(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Connect Your First Store
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {stores.map((store) => (
              <div
                key={store.id}
                className="bg-white rounded-xl p-6 border border-black/10 hover:shadow-lg transition-all relative group"
              >
                {/* Primary Badge */}
                {store.rank_position === 1 && (
                  <div className="absolute top-3 right-3">
                    <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
                  </div>
                )}

                {/* Platform Icon & Name */}
                <div className="flex items-start gap-3 mb-4">
                  {getPlatformIcon(store.platform)}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold text-primary truncate">{store.store_name}</h3>
                    <a
                      href={store.store_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline flex items-center gap-1 mt-1"
                    >
                      <span className="truncate">{store.store_url.replace(/https?:\/\//, '')}</span>
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                    </a>
                  </div>
                </div>

                {/* Status Badge */}
                <div className="flex items-center justify-between mb-4">
                  {getStatusBadge(store)}
                  <div className="flex items-center gap-1 text-xs text-tertiary">
                    <span className="capitalize">{store.platform}</span>
                  </div>
                </div>

                {/* Metrics */}
                <div className="grid grid-cols-2 gap-3 mb-4 pb-4 border-b border-black/10">
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Package className="w-3.5 h-3.5 text-blue-600" />
                      <span className="text-xs text-tertiary">Products</span>
                    </div>
                    <div className="text-lg font-semibold text-primary">{store.product_count || 0}</div>
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <ShoppingCart className="w-3.5 h-3.5 text-purple-600" />
                      <span className="text-xs text-tertiary">Orders (30d)</span>
                    </div>
                    <div className="text-lg font-semibold text-primary">{store.total_orders || 0}</div>
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <DollarSign className="w-3.5 h-3.5 text-green-600" />
                      <span className="text-xs text-tertiary">Revenue (30d)</span>
                    </div>
                    <div className="text-lg font-semibold text-primary">${store.monthly_revenue.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <TrendingUp className="w-3.5 h-3.5 text-amber-600" />
                      <span className="text-xs text-tertiary">Conv. Rate</span>
                    </div>
                    <div className="text-lg font-semibold text-primary">{store.conversion_rate.toFixed(1)}%</div>
                  </div>
                </div>

                {/* Ranking */}
                <div className="flex items-center justify-between mb-4">
                  <div className="text-xs text-tertiary">
                    Rank #{store.rank_position}
                  </div>
                  <div className={`text-xs font-medium ${
                    store.rank_change > 0 ? 'text-green-600' :
                    store.rank_change < 0 ? 'text-red-600' :
                    'text-gray-500'
                  }`}>
                    {store.rank_change_label}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setSelectedStore(store)}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-black/5 hover:bg-black/10 text-primary rounded-lg text-sm font-medium transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                    Settings
                  </button>
                  {store.is_active ? (
                    <button
                      onClick={() => handlePauseStore(store.id)}
                      className="p-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-700 rounded-lg transition-colors"
                      title="Pause store"
                    >
                      <Pause className="w-4 h-4" />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleActivateStore(store.id)}
                      className="p-2 bg-green-500/10 hover:bg-green-500/20 text-green-700 rounded-lg transition-colors"
                      title="Activate store"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                  )}
                  {store.rank_position !== 1 && (
                    <button
                      onClick={() => handleMakePrimary(store.id)}
                      className="p-2 bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-700 rounded-lg transition-colors"
                      title="Make primary"
                    >
                      <Star className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={() => handleDeleteStore(store.id)}
                    className="p-2 bg-red-500/10 hover:bg-red-500/20 text-red-700 rounded-lg transition-colors"
                    title="Disconnect store"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {/* Last Sync */}
                {store.last_sync && (
                  <div className="text-xs text-tertiary mt-3 pt-3 border-t border-black/10">
                    Last synced: {new Date(store.last_sync).toLocaleDateString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* B) Add Store Flow Modal */}
      {showAddFlow && (
        <AddStoreModal
          onClose={() => setShowAddFlow(false)}
          onSuccess={() => {
            setShowAddFlow(false);
            fetchStores();
          }}
        />
      )}

      {/* C) Store Settings Modal */}
      {selectedStore && (
        <StoreSettingsModal
          store={selectedStore}
          onClose={() => setSelectedStore(null)}
          onSave={() => {
            setSelectedStore(null);
            fetchStores();
          }}
        />
      )}
    </div>
  );
}

// B) Add Store Flow Component
function AddStoreModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [step, setStep] = useState<'platform' | 'connect' | 'setup'>('platform');
  const [selectedPlatform, setSelectedPlatform] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    store_name: '',
    store_url: '',
    access_token: '',
    shop_domain: ''
  });

  const platforms = [
    { id: 'shopify', name: 'Shopify', icon: 'S', color: 'bg-green-500', available: true },
    { id: 'amazon', name: 'Amazon', icon: 'A', color: 'bg-orange-500', available: false },
    { id: 'woocommerce', name: 'WooCommerce', icon: 'W', color: 'bg-purple-500', available: false },
    { id: 'etsy', name: 'Etsy', icon: 'E', color: 'bg-red-500', available: false },
  ];

  const handleConnectShopify = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8001/api/portfolio/stores/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          store_name: formData.store_name,
          store_url: formData.store_url,
          platform: 'shopify',
          credentials: {
            access_token: formData.access_token,
            shop_domain: formData.shop_domain
          }
        })
      });

      if (response.ok) {
        onSuccess();
      } else {
        const error = await response.json();
        alert(`Failed to connect store: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to add store:', error);
      alert('Failed to connect store. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-black/10">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-primary">Connect New Store</h2>
            <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-lg transition-colors">
              <XCircle className="w-5 h-5 text-tertiary" />
            </button>
          </div>
        </div>

        <div className="p-6">
          {/* Step 1: Platform Selection */}
          {step === 'platform' && (
            <div>
              <h3 className="text-lg font-semibold text-primary mb-4">Select Platform</h3>
              <div className="grid grid-cols-2 gap-4">
                {platforms.map((platform) => (
                  <button
                    key={platform.id}
                    onClick={() => {
                      if (platform.available) {
                        setSelectedPlatform(platform.id);
                        setStep('connect');
                      }
                    }}
                    disabled={!platform.available}
                    className={`p-6 rounded-xl border-2 transition-all ${
                      platform.available
                        ? 'border-black/10 hover:border-blue-300 hover:bg-blue-50 cursor-pointer'
                        : 'border-black/5 bg-gray-50 cursor-not-allowed opacity-50'
                    }`}
                  >
                    <div className={`w-12 h-12 ${platform.color} rounded-lg flex items-center justify-center text-white text-2xl font-bold mb-3 mx-auto`}>
                      {platform.icon}
                    </div>
                    <div className="text-center">
                      <div className="font-semibold text-primary">{platform.name}</div>
                      {!platform.available && (
                        <div className="text-xs text-tertiary mt-1">Coming Soon</div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Connect Platform */}
          {step === 'connect' && selectedPlatform === 'shopify' && (
            <div>
              <button
                onClick={() => setStep('platform')}
                className="text-sm text-blue-600 hover:underline mb-4"
              >
                ← Back to platforms
              </button>

              <h3 className="text-lg font-semibold text-primary mb-4">Connect Shopify Store</h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Store Name</label>
                  <input
                    type="text"
                    placeholder="My Shopify Store"
                    value={formData.store_name}
                    onChange={(e) => setFormData({ ...formData, store_name: e.target.value })}
                    className="w-full px-3 py-2 border border-black/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Store URL</label>
                  <input
                    type="text"
                    placeholder="https://mystore.myshopify.com"
                    value={formData.store_url}
                    onChange={(e) => setFormData({ ...formData, store_url: e.target.value })}
                    className="w-full px-3 py-2 border border-black/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Shop Domain</label>
                  <input
                    type="text"
                    placeholder="mystore.myshopify.com"
                    value={formData.shop_domain}
                    onChange={(e) => setFormData({ ...formData, shop_domain: e.target.value })}
                    className="w-full px-3 py-2 border border-black/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Access Token</label>
                  <input
                    type="password"
                    placeholder="shpat_..."
                    value={formData.access_token}
                    onChange={(e) => setFormData({ ...formData, access_token: e.target.value })}
                    className="w-full px-3 py-2 border border-black/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-tertiary mt-1">
                    Get your access token from Shopify Admin → Apps → Develop apps
                  </p>
                </div>

                <button
                  onClick={handleConnectShopify}
                  disabled={loading || !formData.store_name || !formData.store_url || !formData.access_token}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Connect Store
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// C) Store Settings Component
function StoreSettingsModal({
  store,
  onClose,
  onSave
}: {
  store: StoreData;
  onClose: () => void;
  onSave: () => void;
}) {
  const [formData, setFormData] = useState({
    store_name: store.store_name,
    niche: store.niche || '',
    brand_voice: store.brand_voice || '',
    notifications_enabled: store.notifications_enabled ?? true,
    auto_deploy_enabled: store.auto_deploy_enabled ?? false
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch(`http://localhost:8001/api/portfolio/stores/${store.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        onSave();
      } else {
        alert('Failed to save settings');
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-black/10">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-primary">Store Settings</h2>
            <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-lg transition-colors">
              <XCircle className="w-5 h-5 text-tertiary" />
            </button>
          </div>
          <p className="text-sm text-tertiary mt-1">{store.store_name}</p>
        </div>

        <div className="p-6 space-y-6">
          {/* Store Name */}
          <div>
            <label className="block text-sm font-medium text-primary mb-2">Store Display Name</label>
            <input
              type="text"
              value={formData.store_name}
              onChange={(e) => setFormData({ ...formData, store_name: e.target.value })}
              className="w-full px-3 py-2 border border-black/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-tertiary mt-1">This name will appear in Ospra dashboards</p>
          </div>

          {/* Default Niche */}
          <div>
            <label className="block text-sm font-medium text-primary mb-2">Default Niche Focus</label>
            <select
              value={formData.niche}
              onChange={(e) => setFormData({ ...formData, niche: e.target.value })}
              className="w-full px-3 py-2 border border-black/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a niche...</option>
              <option value="fitness">Fitness & Health</option>
              <option value="smart_home">Smart Home</option>
              <option value="pet_supplies">Pet Supplies</option>
              <option value="beauty">Beauty & Skincare</option>
              <option value="tech">Tech Accessories</option>
              <option value="home_decor">Home Decor</option>
            </select>
            <p className="text-xs text-tertiary mt-1">Primary product category for this store</p>
          </div>

          {/* Brand Voice */}
          <div>
            <label className="block text-sm font-medium text-primary mb-2">Brand Voice</label>
            <textarea
              value={formData.brand_voice}
              onChange={(e) => setFormData({ ...formData, brand_voice: e.target.value })}
              rows={3}
              placeholder="Describe your brand's tone and style (e.g., 'Professional and friendly, emphasizing quality and sustainability')"
              className="w-full px-3 py-2 border border-black/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <p className="text-xs text-tertiary mt-1">Used for AI-generated product descriptions and marketing content</p>
          </div>

          {/* Notifications */}
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="notifications"
              checked={formData.notifications_enabled}
              onChange={(e) => setFormData({ ...formData, notifications_enabled: e.target.checked })}
              className="mt-1"
            />
            <div>
              <label htmlFor="notifications" className="text-sm font-medium text-primary cursor-pointer">
                Enable Notifications
              </label>
              <p className="text-xs text-tertiary mt-1">
                Receive alerts for important store events (low stock, high ROAS products, etc.)
              </p>
            </div>
          </div>

          {/* Auto-Deploy */}
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="auto-deploy"
              checked={formData.auto_deploy_enabled}
              onChange={(e) => setFormData({ ...formData, auto_deploy_enabled: e.target.checked })}
              className="mt-1"
            />
            <div>
              <label htmlFor="auto-deploy" className="text-sm font-medium text-primary cursor-pointer">
                Auto-Deploy Products
              </label>
              <p className="text-xs text-tertiary mt-1">
                Automatically deploy high-scoring products from discovery to this store
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-4 border-t border-black/10">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-black/5 hover:bg-black/10 text-primary rounded-lg font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:bg-gray-300"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
