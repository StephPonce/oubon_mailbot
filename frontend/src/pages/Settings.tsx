// 
// SETTINGS PAGE - Profile, Subscription, Notifications, API Keys, Security
// FIXED: Notifications, Billing Link, Downgrade, Security 404
// 

import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { 
  User, 
  CreditCard, 
  Bell, 
  Key, 
  Shield, 
  Save, 
  Eye, 
  EyeOff,
  Copy,
  Check,
  Crown,
  Zap,
  Rocket,
  Star,
  AlertCircle,
  RefreshCw,
  ExternalLink
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Token helper
function getToken(): string | null {
  return localStorage.getItem('ospra_token') || sessionStorage.getItem('ospra_token');
}

// API helper with auth
async function apiCall<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// 
// TIER CONFIGURATION
// 

const TIERS = [
  {
    id: 'nest',
    name: 'Nest',
    price: 0,
    icon: Star,
    color: 'from-gray-500 to-gray-600',
    borderColor: 'border-gray-500/30',
    features: [
      '1 connected store',
      '50 products/month',
      'Basic trend discovery',
      'Email support',
    ],
  },
  {
    id: 'flight',
    name: 'Flight',
    price: 29,
    icon: Zap,
    color: 'from-blue-500 to-blue-600',
    borderColor: 'border-blue-500/30',
    features: [
      '3 connected stores',
      '500 products/month',
      'Advanced trend discovery',
      '24-hour early access',
      'Priority support',
    ],
  },
  {
    id: 'soar',
    name: 'Soar',
    price: 79,
    icon: Rocket,
    color: 'from-purple-500 to-purple-600',
    borderColor: 'border-purple-500/30',
    popular: true,
    features: [
      '10 connected stores',
      'Unlimited products',
      'AI-powered automation',
      '7-day early access',
      'Custom branding',
      'API access',
    ],
  },
  {
    id: 'stratosphere',
    name: 'Stratosphere',
    price: 199,
    icon: Crown,
    color: 'from-amber-500 to-orange-500',
    borderColor: 'border-amber-500/30',
    features: [
      'Unlimited stores',
      'Unlimited everything',
      'First access to trends (30+ days)',
      'White-label options',
      'Dedicated account manager',
      'Custom integrations',
    ],
  },
];

// 
// TABS
// 

const TABS = [
  { id: 'profile', name: 'Profile', icon: User },
  { id: 'subscription', name: 'Subscription', icon: CreditCard },
  { id: 'notifications', name: 'Notifications', icon: Bell },
  { id: 'api', name: 'API Keys', icon: Key },
  { id: 'security', name: 'Security', icon: Shield },
];

// 
// MAIN COMPONENT
// 

export default function Settings() {
  const { user, checkAuth } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  
  // Profile state
  const [name, setName] = useState(user?.name || '');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Subscription state
  const [currentTier, setCurrentTier] = useState('nest');
  const [loadingTier, setLoadingTier] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null); // Track which tier is being processed
  
  // Security state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  
  // API Key state
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [generatingKey, setGeneratingKey] = useState(false);
  
  // Notification preferences
  const [notifications, setNotifications] = useState({
    email_new_products: true,
    email_price_drops: true,
    email_trend_alerts: false,
    email_weekly_digest: true,
    email_marketing: false,
  });
  const [savingNotifications, setSavingNotifications] = useState(false);

  // Load subscription info
  useEffect(() => {
    async function loadSubscription() {
      try {
        const response = await apiCall<{ success: boolean; subscription?: { tier: string } }>('/api/subscription/current');
        if (response.success && response.subscription) {
          setCurrentTier(response.subscription.tier.toLowerCase());
        }
      } catch (err) {
        console.error('Failed to load subscription:', err);
        // Fallback to user tier from auth context
        if (user?.tier) {
          setCurrentTier(user.tier.toLowerCase());
        }
      } finally {
        setLoadingTier(false);
      }
    }
    
    loadSubscription();
  }, [user]);

  // Load notification settings
  useEffect(() => {
    async function loadNotifications() {
      try {
        const response = await apiCall<{ success: boolean; settings?: typeof notifications }>('/api/user/settings');
        if (response.success && response.settings) {
          setNotifications({
            email_new_products: response.settings.notify_new_products ?? true,
            email_price_drops: response.settings.notify_price_drops ?? true,
            email_trend_alerts: response.settings.notify_trend_spikes ?? false,
            email_weekly_digest: response.settings.email_notifications ?? true,
            email_marketing: false,
          });
        }
      } catch (err) {
        console.error('Failed to load notifications:', err);
        // Keep defaults
      }
    }
    
    loadNotifications();
  }, []);

  // Update name when user changes
  useEffect(() => {
    if (user?.name) {
      setName(user.name);
    }
  }, [user]);

  // Auto-clear messages after 5 seconds
  useEffect(() => {
    if (saveMessage) {
      const timer = setTimeout(() => setSaveMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [saveMessage]);

  // 
  // HANDLERS
  // 

  async function handleSaveProfile() {
    setSaving(true);
    setSaveMessage(null);
    
    try {
      await apiCall('/api/user/profile', {
        method: 'PATCH',
        body: JSON.stringify({ name }),
      });
      
      setSaveMessage({ type: 'success', text: 'Profile saved successfully!' });
      await checkAuth(); // Refresh user data
    } catch (err) {
      setSaveMessage({ 
        type: 'error', 
        text: err instanceof Error ? err.message : 'Failed to save profile' 
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleChangePassword() {
    if (newPassword !== confirmPassword) {
      setSaveMessage({ type: 'error', text: 'Passwords do not match' });
      return;
    }
    
    if (newPassword.length < 8) {
      setSaveMessage({ type: 'error', text: 'Password must be at least 8 characters' });
      return;
    }
    
    setSaving(true);
    setSaveMessage(null);
    
    try {
      // FIXED: Send as JSON body, not query params
      await apiCall('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      
      setSaveMessage({ type: 'success', text: 'Password changed successfully!' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setSaveMessage({ 
        type: 'error', 
        text: err instanceof Error ? err.message : 'Failed to change password' 
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleTierChange(tierId: string) {
    const tierIndex = TIERS.findIndex(t => t.id === tierId);
    const currentIndex = TIERS.findIndex(t => t.id === currentTier);
    const isDowngrade = tierIndex < currentIndex;
    
    // Confirm downgrade
    if (isDowngrade && tierId !== 'nest') {
      const confirmed = window.confirm(
        `Are you sure you want to downgrade to ${TIERS[tierIndex].name}? You'll lose access to some features.`
      );
      if (!confirmed) return;
    }
    
    // Confirm cancel (downgrade to nest)
    if (tierId === 'nest' && currentTier !== 'nest') {
      const confirmed = window.confirm(
        'Are you sure you want to cancel your subscription? You\'ll be moved to the free Nest plan.'
      );
      if (!confirmed) return;
    }
    
    setUpgrading(tierId);
    
    try {
      const response = await apiCall<{ 
        success: boolean; 
        checkout_url?: string; 
        action?: string;
        message?: string;
      }>('/api/subscription/upgrade', {
        method: 'POST',
        body: JSON.stringify({ tier: tierId }),
      });
      
      if (response.checkout_url) {
        // Redirect to payment (open in new tab)
        window.open(response.checkout_url, '_blank');
      } else if (response.success) {
        setCurrentTier(tierId);
        await checkAuth();
        setSaveMessage({ 
          type: 'success', 
          text: response.message || `Successfully changed to ${TIERS.find(t => t.id === tierId)?.name}!` 
        });
      }
    } catch (err) {
      setSaveMessage({ 
        type: 'error', 
        text: err instanceof Error ? err.message : 'Failed to change plan' 
      });
    } finally {
      setUpgrading(null);
    }
  }

  async function handleNotificationToggle(key: keyof typeof notifications) {
    const newValue = !notifications[key];
    
    // Optimistic update
    setNotifications(prev => ({ ...prev, [key]: newValue }));
    
    // Map frontend keys to backend keys
    const backendKeyMap: Record<string, string> = {
      email_new_products: 'notify_new_products',
      email_price_drops: 'notify_price_drops',
      email_trend_alerts: 'notify_trend_spikes',
      email_weekly_digest: 'email_notifications',
      email_marketing: 'email_marketing',
    };
    
    try {
      await apiCall('/api/user/settings', {
        method: 'PATCH',
        body: JSON.stringify({ [backendKeyMap[key]]: newValue }),
      });
    } catch (err) {
      // Revert on error
      setNotifications(prev => ({ ...prev, [key]: !newValue }));
      console.error('Failed to save notification setting:', err);
    }
  }

  async function handleGenerateApiKey() {
    setGeneratingKey(true);
    
    try {
      const response = await apiCall<{ success: boolean; api_key: string }>('/api/user/api-key', {
        method: 'POST',
      });
      
      if (response.success && response.api_key) {
        setApiKey(response.api_key);
      }
    } catch (err) {
      setSaveMessage({ 
        type: 'error', 
        text: err instanceof Error ? err.message : 'Failed to generate API key' 
      });
    } finally {
      setGeneratingKey(false);
    }
  }

  function handleCopyApiKey() {
    if (apiKey) {
      navigator.clipboard.writeText(apiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  // 
  // RENDER FUNCTIONS
  // 

  function renderProfileTab() {
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Profile Information</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-2">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:border-cyan-500/50 focus:outline-none"
                placeholder="Your name"
              />
            </div>
            
            <div>
              <label className="block text-sm text-white/60 mb-2">Email</label>
              <input
                type="email"
                value={user?.email || ''}
                disabled
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white/50 cursor-not-allowed"
              />
              <p className="text-xs text-white/40 mt-1">Email cannot be changed</p>
            </div>
            
            <div>
              <label className="block text-sm text-white/60 mb-2">Account Created</label>
              <p className="text-white/80">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'Unknown'}
              </p>
            </div>
          </div>
        </div>
        
        <button
          onClick={handleSaveProfile}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-xl text-white font-medium hover:opacity-90 disabled:opacity-50 transition-all"
        >
          {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    );
  }

  function renderSubscriptionTab() {
    const currentTierData = TIERS.find(t => t.id === currentTier) || TIERS[0];
    const CurrentIcon = currentTierData.icon;
    
    return (
      <div className="space-y-6">
        {/* Current Plan */}
        <div className={`p-6 rounded-2xl bg-gradient-to-r ${currentTierData.color} border ${currentTierData.borderColor}`}>
          <div className="flex items-center gap-3 mb-2">
            <CurrentIcon className="w-6 h-6 text-white" />
            <h3 className="text-xl font-bold text-white">Current Plan: {currentTierData.name}</h3>
          </div>
          <p className="text-white/80">
            {currentTierData.price === 0 ? 'Free forever' : `$${currentTierData.price}/month`}
          </p>
        </div>

        {loadingTier ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {TIERS.map((tier) => {
              const TierIcon = tier.icon;
              const isCurrent = tier.id === currentTier;
              const tierIndex = TIERS.findIndex(t => t.id === tier.id);
              const currentIndex = TIERS.findIndex(t => t.id === currentTier);
              const isUpgrade = tierIndex > currentIndex;
              const isDowngrade = tierIndex < currentIndex;
              const isProcessing = upgrading === tier.id;
              
              return (
                <div
                  key={tier.id}
                  className={`relative p-6 rounded-2xl border transition-all ${
                    isCurrent
                      ? `bg-gradient-to-br ${tier.color} border-white/30`
                      : 'bg-white/5 border-white/10 hover:border-white/20'
                  }`}
                >
                  {tier.popular && !isCurrent && (
                    <span className="absolute -top-2 left-4 px-2 py-0.5 bg-purple-500 text-white text-xs rounded-full">
                      Popular
                    </span>
                  )}
                  
                  {isCurrent && (
                    <span className="absolute -top-2 right-4 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full flex items-center gap-1">
                      <Check className="w-3 h-3" /> Current
                    </span>
                  )}
                  
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${tier.color} flex items-center justify-center`}>
                      <TierIcon className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h4 className="font-bold text-white">{tier.name}</h4>
                      <p className="text-white/60 text-sm">
                        {tier.price === 0 ? 'Free' : `$${tier.price}/mo`}
                      </p>
                    </div>
                  </div>
                  
                  <ul className="space-y-2 mb-4">
                    {tier.features.map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm text-white/70">
                        <Check className="w-4 h-4 text-green-400 flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  
                  {!isCurrent && (
                    <button
                      onClick={() => handleTierChange(tier.id)}
                      disabled={isProcessing || upgrading !== null}
                      className={`w-full py-2 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                        isUpgrade
                          ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white hover:opacity-90'
                          : 'bg-white/10 text-white/60 hover:bg-white/20'
                      } disabled:opacity-50`}
                    >
                      {isProcessing ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        isUpgrade ? 'Upgrade' : 'Downgrade'
                      )}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
        
        {/* Billing Management - FIXED: Opens in new tab */}
        {currentTier !== 'nest' && (
          <div className="p-4 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-white font-medium">Billing Management</h4>
                <p className="text-white/50 text-sm">Update payment method, view invoices</p>
              </div>
              <a
                href="https://billing.stripe.com/p/login/test_00g00000000000"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-white transition-colors"
              >
                Manage Billing
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>
        )}
        
        <p className="text-center text-white/40 text-sm">
          Questions about billing? Contact <a href="mailto:support@ospra.io" className="text-cyan-400 hover:underline">support@ospra.io</a>
        </p>
      </div>
    );
  }

  function renderNotificationsTab() {
    const notificationOptions = [
      { key: 'email_new_products' as const, label: 'New product discoveries', description: 'Get notified when Oi finds new winning products' },
      { key: 'email_price_drops' as const, label: 'Price drop alerts', description: 'Supplier price changes on watched products' },
      { key: 'email_trend_alerts' as const, label: 'Trend spike alerts', description: 'Immediate alerts for viral trends' },
      { key: 'email_weekly_digest' as const, label: 'Weekly digest', description: 'Summary of top opportunities each week' },
      { key: 'email_marketing' as const, label: 'Product updates', description: 'New features and tips from Ospra' },
    ];
    
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">Email Notifications</h3>
          <p className="text-white/50 text-sm mb-4">Choose what updates you want to receive</p>
        </div>
        
        <div className="space-y-3">
          {notificationOptions.map((option) => (
            <div
              key={option.key}
              className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/[0.07] transition-colors"
            >
              <div className="flex-1 mr-4">
                <p className="text-white font-medium">{option.label}</p>
                <p className="text-white/50 text-sm">{option.description}</p>
              </div>
              <button
                onClick={() => handleNotificationToggle(option.key)}
                disabled={savingNotifications}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  notifications[option.key]
                    ? 'bg-cyan-500'
                    : 'bg-white/20'
                }`}
              >
                <div
                  className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    notifications[option.key]
                      ? 'translate-x-6'
                      : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
        
        <p className="text-white/40 text-sm">
          Changes are saved automatically
        </p>
      </div>
    );
  }

  function renderApiTab() {
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">API Access</h3>
          <p className="text-white/60 text-sm mb-4">
            Generate an API key to integrate Ospra with your own applications.
          </p>
        </div>
        
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl flex gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="text-amber-200 font-medium">Keep your API key secure</p>
            <p className="text-amber-200/70">
              Never share your API key or commit it to version control. 
              Regenerating will invalidate the previous key.
            </p>
          </div>
        </div>
        
        {apiKey ? (
          <div className="space-y-4">
            <div className="p-4 bg-white/5 border border-white/10 rounded-xl">
              <label className="block text-sm text-white/60 mb-2">Your API Key</label>
              <div className="flex gap-2">
                <code className="flex-1 px-4 py-2 bg-black/30 rounded-lg text-cyan-400 font-mono text-sm overflow-x-auto">
                  {apiKey}
                </code>
                <button
                  onClick={handleCopyApiKey}
                  className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                  title="Copy to clipboard"
                >
                  {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-white" />}
                </button>
              </div>
              <p className="text-xs text-amber-400 mt-2">
                [WARNING] Save this key now - it won't be shown again!
              </p>
            </div>
            
            <button
              onClick={() => setApiKey(null)}
              className="text-white/50 hover:text-white text-sm transition-colors"
            >
              Generate new key (invalidates current)
            </button>
          </div>
        ) : (
          <button
            onClick={handleGenerateApiKey}
            disabled={generatingKey}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-xl text-white font-medium hover:opacity-90 disabled:opacity-50 transition-all"
          >
            {generatingKey ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Key className="w-4 h-4" />
            )}
            {generatingKey ? 'Generating...' : 'Generate API Key'}
          </button>
        )}
        
        <div className="p-4 bg-white/5 border border-white/10 rounded-xl">
          <h4 className="text-white font-medium mb-2">API Documentation</h4>
          <p className="text-white/50 text-sm mb-3">
            Learn how to integrate Ospra's product intelligence into your applications.
          </p>
          <a
            href="https://docs.ospra.io/api"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-cyan-400 hover:text-cyan-300 text-sm transition-colors"
          >
            View API Docs
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    );
  }

  function renderSecurityTab() {
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Change Password</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-2">Current Password</label>
              <input
                type={showPasswords ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:border-cyan-500/50 focus:outline-none"
                placeholder="Enter current password"
              />
            </div>
            
            <div>
              <label className="block text-sm text-white/60 mb-2">New Password</label>
              <input
                type={showPasswords ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:border-cyan-500/50 focus:outline-none"
                placeholder="Enter new password (min 8 characters)"
              />
            </div>
            
            <div>
              <label className="block text-sm text-white/60 mb-2">Confirm New Password</label>
              <div className="relative">
                <input
                  type={showPasswords ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-3 pr-12 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:border-cyan-500/50 focus:outline-none"
                  placeholder="Confirm new password"
                />
                <button
                  type="button"
                  onClick={() => setShowPasswords(!showPasswords)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/60 transition-colors"
                >
                  {showPasswords ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <button
          onClick={handleChangePassword}
          disabled={saving || !currentPassword || !newPassword || !confirmPassword}
          className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-xl text-white font-medium hover:opacity-90 disabled:opacity-50 transition-all"
        >
          {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
          {saving ? 'Updating...' : 'Update Password'}
        </button>
        
        <div className="pt-8 border-t border-white/10">
          <h3 className="text-lg font-semibold text-red-400 mb-2">Danger Zone</h3>
          <p className="text-white/60 text-sm mb-4">
            Permanently delete your account and all associated data. This action cannot be undone.
          </p>
          <button 
            onClick={() => {
              if (window.confirm('Are you sure you want to delete your account? This cannot be undone.')) {
                // TODO: Implement account deletion
                alert('Please contact support@ospra.io to delete your account.');
              }
            }}
            className="px-6 py-3 bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl font-medium hover:bg-red-500/20 transition-colors"
          >
            Delete Account
          </button>
        </div>
      </div>
    );
  }

  // 
  // MAIN RENDER
  // 

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
          <p className="text-white/60">Manage your account, subscription, and preferences</p>
        </div>
        
        {/* Status Message */}
        {saveMessage && (
          <div className={`mb-6 p-4 rounded-xl flex items-center gap-3 ${
            saveMessage.type === 'success' 
              ? 'bg-green-500/10 border border-green-500/30 text-green-400'
              : 'bg-red-500/10 border border-red-500/30 text-red-400'
          }`}>
            {saveMessage.type === 'success' ? (
              <Check className="w-5 h-5" />
            ) : (
              <AlertCircle className="w-5 h-5" />
            )}
            {saveMessage.text}
          </div>
        )}
        
        {/* Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {TABS.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white'
                    : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white'
                }`}
              >
                <TabIcon className="w-4 h-4" />
                {tab.name}
              </button>
            );
          })}
        </div>
        
        {/* Tab Content */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
          {activeTab === 'profile' && renderProfileTab()}
          {activeTab === 'subscription' && renderSubscriptionTab()}
          {activeTab === 'notifications' && renderNotificationsTab()}
          {activeTab === 'api' && renderApiTab()}
          {activeTab === 'security' && renderSecurityTab()}
        </div>
      </div>
    </div>
  );
}
