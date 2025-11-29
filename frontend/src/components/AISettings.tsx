import React, { useState, useEffect } from 'react';
import {
  Brain,
  Zap,
  DollarSign,
  Shield,
  Check,
  AlertCircle,
  TrendingDown,
  TrendingUp,
  Lock,
  Key,
  Sparkles,
  Info,
  Save,
  Loader2,
  Eye,
  EyeOff
} from 'lucide-react';

// Types
interface AIProvider {
  id: string;
  name: string;
  displayName: string;
  icon: string;
  costPer1k: number;
  speedRating: number; // 1-5
  qualityRating: number; // 1-5
  bestFor: string[];
  recommended?: boolean;
  comingSoon?: boolean;
  color: string;
}

interface UsageStats {
  currentMonth: {
    totalTokens: number;
    totalCost: number;
    byProvider: Record<string, { tokens: number; cost: number }>;
  };
}

interface AISettingsProps {
  onSave?: (settings: { provider: string; customApiKey?: string }) => void;
}

// AI Provider configurations
const AI_PROVIDERS: AIProvider[] = [
  {
    id: 'claude',
    name: 'claude',
    displayName: 'Claude Sonnet 4',
    icon: '🤖',
    costPer1k: 0.003,
    speedRating: 5,
    qualityRating: 5,
    bestFor: ['Product analysis', 'Detailed descriptions', 'Market research', 'Customer support'],
    recommended: true,
    color: 'purple'
  },
  {
    id: 'openai',
    name: 'openai',
    displayName: 'OpenAI GPT-4',
    icon: '🧠',
    costPer1k: 0.03,
    speedRating: 4,
    qualityRating: 5,
    bestFor: ['Complex reasoning', 'Code generation', 'Creative writing', 'Problem solving'],
    color: 'green'
  },
  {
    id: 'gemini',
    name: 'gemini',
    displayName: 'Google Gemini Pro',
    icon: '✨',
    costPer1k: 0.00025,
    speedRating: 5,
    qualityRating: 4,
    bestFor: ['Budget-conscious users', 'High volume tasks', 'Quick responses', 'Basic analysis'],
    color: 'blue'
  },
  {
    id: 'grok',
    name: 'grok',
    displayName: 'Grok AI',
    icon: '🚀',
    costPer1k: 0.005,
    speedRating: 4,
    qualityRating: 4,
    bestFor: ['Real-time data', 'News analysis', 'Trend detection'],
    comingSoon: true,
    color: 'orange'
  }
];

const AISettings: React.FC<AISettingsProps> = ({ onSave }) => {
  const [selectedProvider, setSelectedProvider] = useState<string>('claude');
  const [originalProvider, setOriginalProvider] = useState<string>('claude');
  const [useCustomKey, setUseCustomKey] = useState(false);
  const [customApiKey, setCustomApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [testingApiKey, setTestingApiKey] = useState(false);
  const [apiKeyValid, setApiKeyValid] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [usageStats, setUsageStats] = useState<UsageStats>({
    currentMonth: {
      totalTokens: 245680,
      totalCost: 7.37,
      byProvider: {
        claude: { tokens: 180000, cost: 5.40 },
        openai: { tokens: 45680, cost: 1.37 },
        gemini: { tokens: 20000, cost: 0.60 }
      }
    }
  });

  // Calculate potential savings
  const calculateSavings = () => {
    const originalProviderData = AI_PROVIDERS.find(p => p.id === originalProvider);
    const newProviderData = AI_PROVIDERS.find(p => p.id === selectedProvider);

    if (!originalProviderData || !newProviderData) return null;

    const avgMonthlyTokens = usageStats.currentMonth.totalTokens;
    const currentCost = (avgMonthlyTokens / 1000) * originalProviderData.costPer1k;
    const newCost = (avgMonthlyTokens / 1000) * newProviderData.costPer1k;
    const savings = currentCost - newCost;
    const savingsPercent = (savings / currentCost) * 100;

    return {
      currentCost,
      newCost,
      savings,
      savingsPercent
    };
  };

  // Test API key
  const testApiKey = async () => {
    if (!customApiKey.trim()) {
      setApiKeyValid(false);
      return;
    }

    setTestingApiKey(true);
    setApiKeyValid(null);

    try {
      const response = await fetch('http://localhost:8001/api/settings/ai-provider/test-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          apiKey: customApiKey
        })
      });

      const data = await response.json();
      setApiKeyValid(data.valid);
    } catch (error) {
      setApiKeyValid(false);
    } finally {
      setTestingApiKey(false);
    }
  };

  // Save settings
  const handleSave = async () => {
    setSaving(true);

    try {
      const response = await fetch('http://localhost:8001/api/settings/ai-provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          customApiKey: useCustomKey ? customApiKey : null
        })
      });

      if (response.ok) {
        setOriginalProvider(selectedProvider);
        if (onSave) {
          onSave({
            provider: selectedProvider,
            customApiKey: useCustomKey ? customApiKey : undefined
          });
        }
        // Show success message
        alert('AI settings saved successfully!');
      } else {
        throw new Error('Failed to save settings');
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('Failed to save AI settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // Check if settings have changed
  const hasChanges = selectedProvider !== originalProvider ||
                     (useCustomKey && customApiKey.trim() !== '');

  // Get rating stars
  const getRatingStars = (rating: number) => {
    return '⭐'.repeat(rating) + '☆'.repeat(5 - rating);
  };

  // Get provider color class
  const getProviderColorClass = (color: string, type: 'bg' | 'text' | 'border') => {
    const colors: Record<string, Record<string, string>> = {
      purple: { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/50' },
      green: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/50' },
      blue: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/50' },
      orange: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/50' }
    };
    return colors[color]?.[type] || colors.blue[type];
  };

  const savings = calculateSavings();

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-light text-white mb-2 flex items-center gap-3">
          <Brain className="w-8 h-8 text-blue-400" />
          AI Provider Settings
        </h1>
        <p className="text-gray-400">
          Choose your preferred AI provider and manage API credentials
        </p>
      </div>

      {/* Current Usage Stats */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-light text-white mb-4 flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-green-400" />
          Current Month Usage
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <p className="text-sm text-gray-500 uppercase mb-1">Total Tokens</p>
            <p className="text-2xl font-bold text-white">
              {usageStats.currentMonth.totalTokens.toLocaleString()}
            </p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <p className="text-sm text-gray-500 uppercase mb-1">Total Cost</p>
            <p className="text-2xl font-bold text-white">
              ${usageStats.currentMonth.totalCost.toFixed(2)}
            </p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <p className="text-sm text-gray-500 uppercase mb-1">Avg Cost/Day</p>
            <p className="text-2xl font-bold text-white">
              ${(usageStats.currentMonth.totalCost / 30).toFixed(2)}
            </p>
          </div>
        </div>
      </div>

      {/* Savings Indicator */}
      {savings && savings.savings !== 0 && (
        <div className={`rounded-lg border p-4 ${
          savings.savings > 0
            ? 'bg-green-500/10 border-green-500/50'
            : 'bg-red-500/10 border-red-500/50'
        }`}>
          <div className="flex items-center gap-3">
            {savings.savings > 0 ? (
              <TrendingDown className="w-6 h-6 text-green-400" />
            ) : (
              <TrendingUp className="w-6 h-6 text-red-400" />
            )}
            <div>
              <p className="font-medium text-white">
                {savings.savings > 0 ? 'Potential Savings' : 'Estimated Additional Cost'}
              </p>
              <p className={`text-sm ${
                savings.savings > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {savings.savings > 0 ? 'Save' : 'Additional'} ${Math.abs(savings.savings).toFixed(2)}/month
                ({Math.abs(savings.savingsPercent).toFixed(1)}%) by switching to {AI_PROVIDERS.find(p => p.id === selectedProvider)?.displayName}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Provider Selection */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-light text-white mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-blue-400" />
          Select AI Provider
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {AI_PROVIDERS.map((provider) => (
            <button
              key={provider.id}
              onClick={() => !provider.comingSoon && setSelectedProvider(provider.id)}
              disabled={provider.comingSoon}
              className={`relative p-5 rounded-lg border text-left transition-all ${
                selectedProvider === provider.id && !provider.comingSoon
                  ? 'bg-gray-900 text-white shadow-lg border-gray-900'
                  : 'bg-white/50 border-gray-200 hover:bg-gray-200/50 text-gray-900'
              } ${provider.comingSoon ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              {/* Recommended Badge */}
              {provider.recommended && (
                <div className="absolute top-2 right-2 px-2 py-1 bg-blue-500 text-white text-xs font-bold rounded-full flex items-center gap-1">
                  <Sparkles className="w-3 h-3" />
                  Recommended
                </div>
              )}

              {/* Coming Soon Badge */}
              {provider.comingSoon && (
                <div className="absolute top-2 right-2 px-2 py-1 bg-orange-500 text-white text-xs font-bold rounded-full">
                  Coming Soon
                </div>
              )}

              {/* Selected Indicator */}
              {selectedProvider === provider.id && !provider.comingSoon && (
                <div className="absolute top-2 left-2">
                  <Check className={`w-5 h-5 ${getProviderColorClass(provider.color, 'text')}`} />
                </div>
              )}

              {/* Provider Icon & Name */}
              <div className="flex items-start gap-3 mb-3 mt-4">
                <div className="text-3xl">{provider.icon}</div>
                <div>
                  <h3 className={`font-light text-lg ${selectedProvider === provider.id ? 'text-white' : 'text-gray-900'}`}>{provider.displayName}</h3>
                  <p className={`text-sm ${selectedProvider === provider.id ? 'text-gray-300' : 'text-gray-600'}`}>{provider.name}</p>
                </div>
              </div>

              {/* Pricing */}
              <div className="mb-3 p-2 bg-gray-800 rounded">
                <p className="text-xs text-gray-500 uppercase">Pricing</p>
                <p className="text-lg font-bold text-white">
                  ${provider.costPer1k.toFixed(5)}/1K tokens
                </p>
              </div>

              {/* Ratings */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                <div>
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <Zap className="w-3 h-3" /> Speed
                  </p>
                  <p className="text-sm">{getRatingStars(provider.speedRating)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <Brain className="w-3 h-3" /> Quality
                  </p>
                  <p className="text-sm">{getRatingStars(provider.qualityRating)}</p>
                </div>
              </div>

              {/* Best For */}
              <div>
                <p className="text-xs text-gray-500 uppercase mb-1">Best for:</p>
                <div className="flex flex-wrap gap-1">
                  {provider.bestFor.slice(0, 2).map((use, idx) => (
                    <span
                      key={idx}
                      className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded"
                    >
                      {use}
                    </span>
                  ))}
                  {provider.bestFor.length > 2 && (
                    <span className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded">
                      +{provider.bestFor.length - 2} more
                    </span>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Custom API Key Section */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-lg font-light text-white flex items-center gap-2">
              <Key className="w-5 h-5 text-yellow-400" />
              Custom API Key (Advanced)
            </h2>
            <p className="text-sm text-gray-400 mt-1">
              Use your own API key for the selected provider
            </p>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useCustomKey}
              onChange={(e) => setUseCustomKey(e.target.checked)}
              className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-300">Enable</span>
          </label>
        </div>

        {useCustomKey && (
          <div className="space-y-4">
            {/* Security Notice */}
            <div className="bg-blue-500/10 border border-blue-500/50 rounded-lg p-4 flex items-start gap-3">
              <Shield className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-blue-400 mb-1">Your API key is secure</p>
                <p className="text-xs text-gray-400">
                  Your API key will be encrypted using AES-256 encryption and stored securely. We never share or log your API keys.
                </p>
              </div>
            </div>

            {/* API Key Input */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                API Key for {AI_PROVIDERS.find(p => p.id === selectedProvider)?.displayName}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={customApiKey}
                  onChange={(e) => {
                    setCustomApiKey(e.target.value);
                    setApiKeyValid(null);
                  }}
                  placeholder={`Enter your ${selectedProvider.toUpperCase()} API key...`}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-11 pr-20 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <button
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="p-2 hover:bg-gray-700 rounded transition"
                  >
                    {showApiKey ? (
                      <EyeOff className="w-4 h-4 text-gray-400" />
                    ) : (
                      <Eye className="w-4 h-4 text-gray-400" />
                    )}
                  </button>
                </div>
              </div>

              {/* API Key Validation Status */}
              {apiKeyValid === true && (
                <p className="text-sm text-green-400 mt-2 flex items-center gap-1">
                  <Check className="w-4 h-4" />
                  API key is valid and working
                </p>
              )}
              {apiKeyValid === false && (
                <p className="text-sm text-red-400 mt-2 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" />
                  Invalid API key. Please check and try again.
                </p>
              )}
            </div>

            {/* Test Button */}
            <button
              onClick={testApiKey}
              disabled={testingApiKey || !customApiKey.trim()}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {testingApiKey ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Key className="w-4 h-4" />
                  Test API Key
                </>
              )}
            </button>

            {/* Cost Comparison */}
            <div className="bg-gray-900/50 rounded-lg p-4">
              <p className="text-sm text-gray-400 mb-2">With your own API key:</p>
              <ul className="space-y-1 text-sm text-gray-300">
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  Pay only for what you use (no markup)
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  Direct billing from {AI_PROVIDERS.find(p => p.id === selectedProvider)?.displayName}
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  Full control over usage limits
                </li>
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Warning for Quality Downgrade */}
      {selectedProvider !== 'claude' && originalProvider === 'claude' && (
        <div className="bg-yellow-500/10 border border-yellow-500/50 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-yellow-400 mb-1">Quality Notice</p>
            <p className="text-sm text-gray-400">
              Switching from Claude Sonnet 4 may result in lower quality product descriptions and analysis.
              Consider testing the output quality before making this permanent.
            </p>
          </div>
        </div>
      )}

      {/* Comparison Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-light text-white mb-4 flex items-center gap-2">
          <Info className="w-5 h-5 text-blue-400" />
          Provider Comparison
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Provider</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-gray-400">Cost/1K</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-gray-400">Speed</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-gray-400">Quality</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Est. Monthly Cost*</th>
              </tr>
            </thead>
            <tbody>
              {AI_PROVIDERS.filter(p => !p.comingSoon).map((provider) => {
                const monthlyCost = (usageStats.currentMonth.totalTokens / 1000) * provider.costPer1k;
                return (
                  <tr
                    key={provider.id}
                    className={`border-b border-gray-700/50 ${
                      selectedProvider === provider.id ? 'bg-blue-500/10' : ''
                    }`}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{provider.icon}</span>
                        <span className="text-white font-medium">{provider.displayName}</span>
                        {provider.recommended && (
                          <span className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded-full">
                            Recommended
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="text-center py-3 px-4 text-white font-mono">
                      ${provider.costPer1k.toFixed(5)}
                    </td>
                    <td className="text-center py-3 px-4">
                      <span className="text-sm">{getRatingStars(provider.speedRating)}</span>
                    </td>
                    <td className="text-center py-3 px-4">
                      <span className="text-sm">{getRatingStars(provider.qualityRating)}</span>
                    </td>
                    <td className="py-3 px-4 text-white font-medium">
                      ${monthlyCost.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="text-xs text-gray-500 mt-2">
            * Based on your current monthly usage of {usageStats.currentMonth.totalTokens.toLocaleString()} tokens
          </p>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex items-center justify-between bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div>
          <p className="text-white font-medium">Ready to save your preferences?</p>
          <p className="text-sm text-gray-400 mt-1">
            {hasChanges
              ? 'You have unsaved changes'
              : 'No changes to save'
            }
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving || (useCustomKey && !apiKeyValid)}
          className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {saving ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-5 h-5" />
              Save Preferences
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default AISettings;
