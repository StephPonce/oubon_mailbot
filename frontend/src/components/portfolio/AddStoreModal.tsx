import React, { useState } from 'react';
import { X, CheckCircle, AlertCircle } from 'lucide-react';

interface AddStoreModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export default function AddStoreModal({ onClose, onSuccess }: AddStoreModalProps) {
  const [step, setStep] = useState(1);
  const [platform, setPlatform] = useState('');
  const [formData, setFormData] = useState({
    store_name: '',
    store_url: '',
    niche: 'smart_home',
    credentials: {} as any
  });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);

  const platforms = [
    { id: 'shopify', name: 'Shopify', color: 'purple', icon: '🛍️' },
    { id: 'amazon', name: 'Amazon', color: 'orange', icon: '📦' },
    { id: 'woocommerce', name: 'WooCommerce', color: 'blue', icon: '🔌' }
  ];

  const niches = [
    'smart_home', 'fitness', 'pet_tech', 'kitchen', 'outdoor',
    'beauty', 'gaming', 'baby', 'fashion', 'electronics'
  ];

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const res = await fetch(`http://localhost:8001/api/platforms/${platform}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData.credentials)
      });
      const data = await res.json();
      setTestResult(data);
    } catch (err: any) {
      setTestResult({ success: false, error: err.message });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    try {
      const res = await fetch('http://localhost:8001/api/portfolio/stores/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          platform
        })
      });
      const data = await res.json();

      if (data.success) {
        onSuccess();
        onClose();
      } else {
        alert('Failed to add store: ' + data.error);
      }
    } catch (err: any) {
      alert('Error: ' + err.message);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800">
          <div>
            <h2 className="text-2xl font-bold text-white">Add New Store</h2>
            <p className="text-gray-400 text-sm mt-1">Step {step} of 3</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-6">
          {/* Step 1: Platform Selection */}
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white mb-4">Select Platform</h3>
              <div className="grid grid-cols-3 gap-4">
                {platforms.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setPlatform(p.id);
                      setStep(2);
                    }}
                    className={`
                      p-6 rounded-lg border-2 transition-all text-center
                      ${platform === p.id
                        ? `border-${p.color}-500 bg-${p.color}-500/10`
                        : 'border-gray-700 hover:border-gray-600'
                      }
                    `}
                  >
                    <div className="text-4xl mb-2">{p.icon}</div>
                    <div className="font-semibold text-white">{p.name}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Store Details */}
          {step === 2 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white mb-4">Store Details</h3>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Store Name *</label>
                <input
                  type="text"
                  value={formData.store_name}
                  onChange={(e) => setFormData({...formData, store_name: e.target.value})}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                  placeholder="My Awesome Store"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Store URL (optional)</label>
                <input
                  type="text"
                  value={formData.store_url}
                  onChange={(e) => setFormData({...formData, store_url: e.target.value})}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                  placeholder="https://mystore.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Niche *</label>
                <select
                  value={formData.niche}
                  onChange={(e) => setFormData({...formData, niche: e.target.value})}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                >
                  {niches.map(n => (
                    <option key={n} value={n}>{n.replace('_', ' ').toUpperCase()}</option>
                  ))}
                </select>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setStep(1)}
                  className="px-6 py-2 border border-gray-700 rounded-lg text-white hover:bg-gray-800"
                >
                  Back
                </button>
                <button
                  onClick={() => setStep(3)}
                  className="flex-1 px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white"
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Credentials */}
          {step === 3 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white mb-4">{platform.charAt(0).toUpperCase() + platform.slice(1)} Credentials</h3>

              {platform === 'shopify' && (
                <>
                  <div className="mb-6 p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                    <h4 className="text-white font-medium mb-2">🔐 OAuth 2.0 (Recommended)</h4>
                    <p className="text-sm text-gray-400 mb-4">
                      Securely connect via Shopify OAuth. You'll be redirected to Shopify to authorize.
                    </p>

                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-400 mb-2">Store Domain *</label>
                      <input
                        type="text"
                        value={formData.credentials.store_domain || ''}
                        onChange={(e) => setFormData({
                          ...formData,
                          credentials: {...formData.credentials, store_domain: e.target.value}
                        })}
                        className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                        placeholder="mystore.myshopify.com"
                      />
                    </div>

                    <button
                      onClick={() => {
                        const domain = formData.credentials.store_domain;
                        if (!domain) {
                          alert('Please enter your store domain first');
                          return;
                        }
                        const shopDomain = domain.includes('.myshopify.com') ? domain : `${domain}.myshopify.com`;
                        window.location.href = `http://localhost:8001/oauth/shopify/install?shop=${shopDomain}`;
                      }}
                      className="w-full px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-lg font-medium transition-all"
                    >
                      🔗 Connect with Shopify OAuth
                    </button>
                  </div>

                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-gray-700"></div>
                    </div>
                    <div className="relative flex justify-center text-xs">
                      <span className="px-2 bg-gray-900 text-gray-500">OR manual token</span>
                    </div>
                  </div>

                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-400 mb-2">Admin API Token (Optional)</label>
                    <input
                      type="password"
                      onChange={(e) => setFormData({
                        ...formData,
                        credentials: {...formData.credentials, admin_api_token: e.target.value}
                      })}
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      placeholder="shpat_... (if not using OAuth)"
                    />
                  </div>
                </>
              )}

              {platform === 'amazon' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Seller ID *</label>
                    <input
                      type="text"
                      onChange={(e) => setFormData({
                        ...formData,
                        credentials: {...formData.credentials, seller_id: e.target.value}
                      })}
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      placeholder="A1BCDXXX..."
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">MWS Auth Token *</label>
                    <input
                      type="password"
                      onChange={(e) => setFormData({
                        ...formData,
                        credentials: {...formData.credentials, mws_auth_token: e.target.value}
                      })}
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      placeholder="amzn.mws..."
                    />
                  </div>
                </>
              )}

              {platform === 'woocommerce' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Store URL *</label>
                    <input
                      type="text"
                      onChange={(e) => setFormData({
                        ...formData,
                        credentials: {...formData.credentials, store_url: e.target.value}
                      })}
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      placeholder="https://mystore.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Consumer Key *</label>
                    <input
                      type="text"
                      onChange={(e) => setFormData({
                        ...formData,
                        credentials: {...formData.credentials, consumer_key: e.target.value}
                      })}
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      placeholder="ck_..."
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">Consumer Secret *</label>
                    <input
                      type="password"
                      onChange={(e) => setFormData({
                        ...formData,
                        credentials: {...formData.credentials, consumer_secret: e.target.value}
                      })}
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                      placeholder="cs_..."
                    />
                  </div>
                </>
              )}

              {/* Test Connection */}
              <button
                onClick={testConnection}
                disabled={testing}
                className="w-full px-6 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded-lg text-white font-medium transition"
              >
                {testing ? 'Testing Connection...' : '🔌 Test Connection'}
              </button>

              {testResult && (
                <div className={`p-4 rounded-lg ${testResult.success ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
                  <div className="flex items-center gap-2">
                    {testResult.success ? (
                      <>
                        <CheckCircle className="w-5 h-5 text-green-500" />
                        <span className="text-green-400 font-medium">Connection successful!</span>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="w-5 h-5 text-red-500" />
                        <span className="text-red-400">Connection failed: {testResult.error}</span>
                      </>
                    )}
                  </div>
                </div>
              )}

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setStep(2)}
                  className="px-6 py-2 border border-gray-700 rounded-lg text-white hover:bg-gray-800 transition"
                >
                  Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!testResult?.success}
                  className="flex-1 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white font-medium transition"
                >
                  {testResult?.success ? '✅ Add Store' : 'Test Connection First'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
