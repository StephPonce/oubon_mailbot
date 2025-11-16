import React, { useState } from 'react';
import {
  X,
  ChevronLeft,
  ChevronRight,
  Check,
  AlertCircle,
  Loader2,
  Store,
  Globe,
  DollarSign,
  Key,
  ExternalLink
} from 'lucide-react';

// Types
interface AddStoreModalProps {
  onClose: () => void;
  onSuccess: (store: any) => void;
}

type Platform = 'shopify' | 'amazon' | 'woocommerce';
type Step = 1 | 2 | 3;

interface StoreData {
  // Platform
  platform: Platform | null;

  // Store Details
  store_name: string;
  store_url: string;
  niche: string;
  target_market: string;
  currency: string;

  // Shopify Credentials
  shopify_domain: string;
  shopify_api_token: string;
  shopify_api_version: string;

  // Amazon Credentials
  amazon_marketplace: string;
  amazon_seller_id: string;
  amazon_mws_token: string;
  amazon_access_key: string;
  amazon_secret_key: string;

  // WooCommerce Credentials
  woocommerce_url: string;
  woocommerce_consumer_key: string;
  woocommerce_consumer_secret: string;
}

// Platform configurations
const PLATFORMS = [
  {
    id: 'shopify' as Platform,
    name: 'Shopify',
    icon: '🛍️',
    color: 'purple',
    description: 'Connect your Shopify store with Admin API credentials'
  },
  {
    id: 'amazon' as Platform,
    name: 'Amazon',
    icon: '📦',
    color: 'orange',
    description: 'Link your Amazon Seller Central account'
  },
  {
    id: 'woocommerce' as Platform,
    name: 'WooCommerce',
    icon: '🔌',
    color: 'blue',
    description: 'Connect your WordPress/WooCommerce site'
  }
];

const NICHES = [
  'Smart Home',
  'Pet Products',
  'Fitness & Sports',
  'Fashion & Apparel',
  'Kitchen & Dining',
  'Beauty & Personal Care',
  'Electronics',
  'Home & Garden',
  'Baby & Kids',
  'Automotive'
];

const MARKETS = [
  { code: 'US', name: 'United States' },
  { code: 'CA', name: 'Canada' },
  { code: 'UK', name: 'United Kingdom' },
  { code: 'EU', name: 'European Union' },
  { code: 'AU', name: 'Australia' }
];

const CURRENCIES = [
  { code: 'USD', symbol: '$', name: 'US Dollar' },
  { code: 'CAD', symbol: 'C$', name: 'Canadian Dollar' },
  { code: 'GBP', symbol: '£', name: 'British Pound' },
  { code: 'EUR', symbol: '€', name: 'Euro' },
  { code: 'AUD', symbol: 'A$', name: 'Australian Dollar' }
];

const AddStoreModal: React.FC<AddStoreModalProps> = ({ onClose, onSuccess }) => {
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [formData, setFormData] = useState<StoreData>({
    platform: null,
    store_name: '',
    store_url: '',
    niche: '',
    target_market: 'US',
    currency: 'USD',
    shopify_domain: '',
    shopify_api_token: '',
    shopify_api_version: '2024-01',
    amazon_marketplace: 'US',
    amazon_seller_id: '',
    amazon_mws_token: '',
    amazon_access_key: '',
    amazon_secret_key: '',
    woocommerce_url: '',
    woocommerce_consumer_key: '',
    woocommerce_consumer_secret: ''
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Handle input change
  const handleChange = (field: keyof StoreData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error for this field
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  // Validate step
  const validateStep = (step: Step): boolean => {
    const newErrors: Record<string, string> = {};

    if (step === 1) {
      if (!formData.platform) {
        newErrors.platform = 'Please select a platform';
      }
    }

    if (step === 2) {
      if (!formData.store_name.trim()) {
        newErrors.store_name = 'Store name is required';
      }
      if (!formData.niche) {
        newErrors.niche = 'Please select a niche';
      }
    }

    if (step === 3) {
      if (formData.platform === 'shopify') {
        if (!formData.shopify_domain.trim()) {
          newErrors.shopify_domain = 'Shopify domain is required';
        } else if (!formData.shopify_domain.includes('.myshopify.com')) {
          newErrors.shopify_domain = 'Domain should be in format: store.myshopify.com';
        }
        if (!formData.shopify_api_token.trim()) {
          newErrors.shopify_api_token = 'API token is required';
        }
      }

      if (formData.platform === 'amazon') {
        if (!formData.amazon_seller_id.trim()) {
          newErrors.amazon_seller_id = 'Seller ID is required';
        }
        if (!formData.amazon_mws_token.trim()) {
          newErrors.amazon_mws_token = 'MWS Auth Token is required';
        }
        if (!formData.amazon_access_key.trim()) {
          newErrors.amazon_access_key = 'Access Key ID is required';
        }
        if (!formData.amazon_secret_key.trim()) {
          newErrors.amazon_secret_key = 'Secret Access Key is required';
        }
      }

      if (formData.platform === 'woocommerce') {
        if (!formData.woocommerce_url.trim()) {
          newErrors.woocommerce_url = 'Store URL is required';
        } else if (!formData.woocommerce_url.startsWith('http')) {
          newErrors.woocommerce_url = 'URL should start with http:// or https://';
        }
        if (!formData.woocommerce_consumer_key.trim()) {
          newErrors.woocommerce_consumer_key = 'Consumer Key is required';
        }
        if (!formData.woocommerce_consumer_secret.trim()) {
          newErrors.woocommerce_consumer_secret = 'Consumer Secret is required';
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Test connection
  const handleTestConnection = async () => {
    if (!validateStep(3)) return;

    setTestStatus('testing');
    setTestMessage('');

    try {
      const response = await fetch('http://localhost:8000/api/portfolio/stores/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setTestStatus('success');
        setTestMessage(data.message || 'Connection successful!');
      } else {
        setTestStatus('error');
        setTestMessage(data.error || 'Connection failed. Please check your credentials.');
      }
    } catch (error) {
      setTestStatus('error');
      setTestMessage('Network error. Please try again.');
    }
  };

  // Submit form
  const handleSubmit = async () => {
    if (testStatus !== 'success') {
      setTestMessage('Please test the connection first');
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/api/portfolio/stores/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok) {
        onSuccess(data.store);
        onClose();
      } else {
        setErrors({ submit: data.error || 'Failed to add store' });
      }
    } catch (error) {
      setErrors({ submit: 'Network error. Please try again.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Navigation
  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(3, prev + 1) as Step);
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(1, prev - 1) as Step);
    setTestStatus('idle');
    setTestMessage('');
  };

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium text-white mb-2">Select Your Platform</h3>
              <p className="text-sm text-gray-400">Choose the e-commerce platform for your store</p>
            </div>

            <div className="space-y-3">
              {PLATFORMS.map((platform) => (
                <button
                  key={platform.id}
                  onClick={() => handleChange('platform', platform.id)}
                  className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                    formData.platform === platform.id
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-gray-700 bg-gray-800 hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="text-3xl">{platform.icon}</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium text-white">{platform.name}</h4>
                        {formData.platform === platform.id && (
                          <Check className="w-5 h-5 text-blue-400" />
                        )}
                      </div>
                      <p className="text-sm text-gray-400 mt-1">{platform.description}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {errors.platform && (
              <p className="text-sm text-red-400 flex items-center gap-1">
                <AlertCircle className="w-4 h-4" />
                {errors.platform}
              </p>
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium text-white mb-2">Store Details</h3>
              <p className="text-sm text-gray-400">Tell us about your store</p>
            </div>

            {/* Store Name */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Store Name <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <Store className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
                <input
                  type="text"
                  value={formData.store_name}
                  onChange={(e) => handleChange('store_name', e.target.value)}
                  placeholder="My Awesome Store"
                  className={`w-full bg-gray-800 border ${
                    errors.store_name ? 'border-red-500' : 'border-gray-700'
                  } rounded-lg pl-11 pr-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                />
              </div>
              {errors.store_name && (
                <p className="text-sm text-red-400 mt-1">{errors.store_name}</p>
              )}
            </div>

            {/* Store URL (Optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Store URL <span className="text-gray-500">(optional)</span>
              </label>
              <div className="relative">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
                <input
                  type="url"
                  value={formData.store_url}
                  onChange={(e) => handleChange('store_url', e.target.value)}
                  placeholder="https://mystore.com"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-11 pr-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Niche */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Niche <span className="text-red-400">*</span>
              </label>
              <select
                value={formData.niche}
                onChange={(e) => handleChange('niche', e.target.value)}
                className={`w-full bg-gray-800 border ${
                  errors.niche ? 'border-red-500' : 'border-gray-700'
                } rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500`}
              >
                <option value="">Select a niche</option>
                {NICHES.map((niche) => (
                  <option key={niche} value={niche.toLowerCase().replace(/\s+/g, '_')}>
                    {niche}
                  </option>
                ))}
              </select>
              {errors.niche && (
                <p className="text-sm text-red-400 mt-1">{errors.niche}</p>
              )}
            </div>

            {/* Target Market & Currency */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Target Market
                </label>
                <select
                  value={formData.target_market}
                  onChange={(e) => handleChange('target_market', e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500"
                >
                  {MARKETS.map((market) => (
                    <option key={market.code} value={market.code}>
                      {market.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Currency
                </label>
                <select
                  value={formData.currency}
                  onChange={(e) => handleChange('currency', e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500"
                >
                  {CURRENCIES.map((currency) => (
                    <option key={currency.code} value={currency.code}>
                      {currency.symbol} {currency.code}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium text-white mb-2">
                {formData.platform === 'shopify' && 'Shopify Credentials'}
                {formData.platform === 'amazon' && 'Amazon Credentials'}
                {formData.platform === 'woocommerce' && 'WooCommerce Credentials'}
              </h3>
              <p className="text-sm text-gray-400">
                Enter your API credentials to connect
              </p>
            </div>

            {/* Shopify Credentials */}
            {formData.platform === 'shopify' && (
              <>
                <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <h4 className="text-white font-medium mb-2">🔐 Secure OAuth 2.0 Connection (Recommended)</h4>
                  <p className="text-sm text-gray-400 mb-4">
                    Connect your Shopify store securely using OAuth 2.0. You'll be redirected to Shopify to authorize access.
                  </p>

                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Store Domain <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.shopify_domain}
                      onChange={(e) => handleChange('shopify_domain', e.target.value)}
                      placeholder="mystore.myshopify.com"
                      className={`w-full bg-gray-800 border ${
                        errors.shopify_domain ? 'border-red-500' : 'border-gray-700'
                      } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                    />
                    {errors.shopify_domain && (
                      <p className="text-sm text-red-400 mt-1">{errors.shopify_domain}</p>
                    )}
                  </div>

                  <button
                    onClick={() => {
                      if (!formData.shopify_domain) {
                        setErrors({ shopify_domain: 'Please enter your store domain first' });
                        return;
                      }
                      const domain = formData.shopify_domain.includes('.myshopify.com')
                        ? formData.shopify_domain
                        : `${formData.shopify_domain}.myshopify.com`;
                      window.location.href = `http://localhost:8000/oauth/shopify/install?shop=${domain}`;
                    }}
                    className="w-full px-4 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all font-medium flex items-center justify-center gap-2"
                  >
                    <ExternalLink className="w-5 h-5" />
                    Connect with Shopify OAuth
                  </button>
                </div>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-700"></div>
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-gray-900 text-gray-500">OR use manual credentials</span>
                  </div>
                </div>

                <div className="mt-6 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Admin API Token
                    </label>
                    <input
                      type="password"
                      value={formData.shopify_api_token}
                      onChange={(e) => handleChange('shopify_api_token', e.target.value)}
                      placeholder="shpat_xxxxxxxxxxxxxxxxxx (optional if using OAuth)"
                      className={`w-full bg-gray-800 border ${
                        errors.shopify_api_token ? 'border-red-500' : 'border-gray-700'
                      } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                    />
                    {errors.shopify_api_token && (
                      <p className="text-sm text-red-400 mt-1">{errors.shopify_api_token}</p>
                    )}
                    <a
                      href="https://help.shopify.com/en/manual/apps/custom-apps"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-400 hover:text-blue-300 mt-1 inline-flex items-center gap-1"
                    >
                      How to get API token <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      API Version
                    </label>
                    <input
                      type="text"
                      value={formData.shopify_api_version}
                      onChange={(e) => handleChange('shopify_api_version', e.target.value)}
                      placeholder="2025-01"
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              </>
            )}

            {/* Amazon Credentials */}
            {formData.platform === 'amazon' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Marketplace
                  </label>
                  <select
                    value={formData.amazon_marketplace}
                    onChange={(e) => handleChange('amazon_marketplace', e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="US">United States</option>
                    <option value="CA">Canada</option>
                    <option value="UK">United Kingdom</option>
                    <option value="DE">Germany</option>
                    <option value="FR">France</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Seller ID <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.amazon_seller_id}
                    onChange={(e) => handleChange('amazon_seller_id', e.target.value)}
                    placeholder="A1XXXXXXXXX"
                    className={`w-full bg-gray-800 border ${
                      errors.amazon_seller_id ? 'border-red-500' : 'border-gray-700'
                    } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                  />
                  {errors.amazon_seller_id && (
                    <p className="text-sm text-red-400 mt-1">{errors.amazon_seller_id}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    MWS Auth Token <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={formData.amazon_mws_token}
                    onChange={(e) => handleChange('amazon_mws_token', e.target.value)}
                    placeholder="amzn.mws.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    className={`w-full bg-gray-800 border ${
                      errors.amazon_mws_token ? 'border-red-500' : 'border-gray-700'
                    } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                  />
                  {errors.amazon_mws_token && (
                    <p className="text-sm text-red-400 mt-1">{errors.amazon_mws_token}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Access Key ID <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.amazon_access_key}
                    onChange={(e) => handleChange('amazon_access_key', e.target.value)}
                    placeholder="AKIAIOSFODNN7EXAMPLE"
                    className={`w-full bg-gray-800 border ${
                      errors.amazon_access_key ? 'border-red-500' : 'border-gray-700'
                    } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                  />
                  {errors.amazon_access_key && (
                    <p className="text-sm text-red-400 mt-1">{errors.amazon_access_key}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Secret Access Key <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={formData.amazon_secret_key}
                    onChange={(e) => handleChange('amazon_secret_key', e.target.value)}
                    placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                    className={`w-full bg-gray-800 border ${
                      errors.amazon_secret_key ? 'border-red-500' : 'border-gray-700'
                    } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                  />
                  {errors.amazon_secret_key && (
                    <p className="text-sm text-red-400 mt-1">{errors.amazon_secret_key}</p>
                  )}
                </div>
              </>
            )}

            {/* WooCommerce Credentials */}
            {formData.platform === 'woocommerce' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Store URL <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="url"
                    value={formData.woocommerce_url}
                    onChange={(e) => handleChange('woocommerce_url', e.target.value)}
                    placeholder="https://mystore.com"
                    className={`w-full bg-gray-800 border ${
                      errors.woocommerce_url ? 'border-red-500' : 'border-gray-700'
                    } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                  />
                  {errors.woocommerce_url && (
                    <p className="text-sm text-red-400 mt-1">{errors.woocommerce_url}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Consumer Key <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.woocommerce_consumer_key}
                    onChange={(e) => handleChange('woocommerce_consumer_key', e.target.value)}
                    placeholder="ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    className={`w-full bg-gray-800 border ${
                      errors.woocommerce_consumer_key ? 'border-red-500' : 'border-gray-700'
                    } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                  />
                  {errors.woocommerce_consumer_key && (
                    <p className="text-sm text-red-400 mt-1">{errors.woocommerce_consumer_key}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Consumer Secret <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={formData.woocommerce_consumer_secret}
                    onChange={(e) => handleChange('woocommerce_consumer_secret', e.target.value)}
                    placeholder="cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    className={`w-full bg-gray-800 border ${
                      errors.woocommerce_consumer_secret ? 'border-red-500' : 'border-gray-700'
                    } rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500`}
                  />
                  {errors.woocommerce_consumer_secret && (
                    <p className="text-sm text-red-400 mt-1">{errors.woocommerce_consumer_secret}</p>
                  )}
                  <a
                    href="https://woocommerce.com/document/woocommerce-rest-api/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-400 hover:text-blue-300 mt-1 inline-flex items-center gap-1"
                  >
                    How to generate API keys <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </>
            )}

            {/* Test Connection Button */}
            <div className="pt-4">
              <button
                onClick={handleTestConnection}
                disabled={testStatus === 'testing'}
                className="w-full px-4 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors font-medium flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {testStatus === 'testing' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Testing Connection...
                  </>
                ) : (
                  <>
                    <Key className="w-5 h-5" />
                    Test Connection
                  </>
                )}
              </button>

              {/* Test Status */}
              {testStatus === 'success' && (
                <div className="mt-3 p-3 bg-green-500/10 border border-green-500/50 rounded-lg flex items-center gap-2 text-green-400">
                  <Check className="w-5 h-5" />
                  <span className="text-sm font-medium">{testMessage}</span>
                </div>
              )}

              {testStatus === 'error' && (
                <div className="mt-3 p-3 bg-red-500/10 border border-red-500/50 rounded-lg flex items-center gap-2 text-red-400">
                  <AlertCircle className="w-5 h-5" />
                  <span className="text-sm font-medium">{testMessage}</span>
                </div>
              )}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-gray-900 rounded-xl border border-gray-800 shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Add New Store</h2>
            <p className="text-sm text-gray-400 mt-1">
              Step {currentStep} of 3
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="px-6 py-4 bg-gray-800/50">
          <div className="flex items-center gap-2">
            {[1, 2, 3].map((step) => (
              <React.Fragment key={step}>
                <div
                  className={`flex-1 h-2 rounded-full transition-all ${
                    step <= currentStep ? 'bg-blue-500' : 'bg-gray-700'
                  }`}
                />
                {step < 3 && <div className="w-2" />}
              </React.Fragment>
            ))}
          </div>
          <div className="flex justify-between mt-2 text-xs text-gray-400">
            <span>Platform</span>
            <span>Details</span>
            <span>Credentials</span>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {renderStepContent()}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 flex items-center justify-between">
          <button
            onClick={handleBack}
            disabled={currentStep === 1}
            className="px-4 py-2 text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <ChevronLeft className="w-5 h-5" />
            Back
          </button>

          <div className="flex gap-2">
            {currentStep < 3 ? (
              <button
                onClick={handleNext}
                className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium flex items-center gap-2"
              >
                Next
                <ChevronRight className="w-5 h-5" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={testStatus !== 'success' || isSubmitting}
                className="px-6 py-2 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Adding Store...
                  </>
                ) : (
                  <>
                    <Check className="w-5 h-5" />
                    Add Store
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Submit Error */}
        {errors.submit && (
          <div className="px-6 pb-4">
            <div className="p-3 bg-red-500/10 border border-red-500/50 rounded-lg flex items-center gap-2 text-red-400">
              <AlertCircle className="w-5 h-5" />
              <span className="text-sm font-medium">{errors.submit}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AddStoreModal;
