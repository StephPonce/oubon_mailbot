/**
 * EXAMPLE: Integrating AISettings Component
 *
 * This file demonstrates various integration patterns for the AISettings component
 * in different application contexts and architectures.
 */

import React, { useState, useEffect } from 'react';
import AISettings from './components/AISettings';

// ============================================================================
// PATTERN 1: Basic Integration with State-Based Navigation
// ============================================================================

export function BasicAISettingsIntegration() {
  const [currentPage, setCurrentPage] = useState<'dashboard' | 'ai-settings'>('dashboard');

  const handleSave = (settings: { provider: string; customApiKey?: string }) => {
    console.log('AI Settings saved:', settings);

    // Show success message
    alert(`Switched to ${settings.provider.toUpperCase()}`);

    // Navigate back to dashboard
    setCurrentPage('dashboard');
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Navigation */}
      <nav className="border-b border-gray-800 p-4">
        <div className="flex gap-4">
          <button
            onClick={() => setCurrentPage('dashboard')}
            className={`px-4 py-2 rounded-lg transition ${
              currentPage === 'dashboard'
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            📊 Dashboard
          </button>
          <button
            onClick={() => setCurrentPage('ai-settings')}
            className={`px-4 py-2 rounded-lg transition ${
              currentPage === 'ai-settings'
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            🤖 AI Settings
          </button>
        </div>
      </nav>

      {/* Page Content */}
      <div className="p-6">
        {currentPage === 'dashboard' ? (
          <div>
            <h1 className="text-3xl font-bold mb-4">Dashboard</h1>
            <p className="text-gray-400">Your dashboard content here...</p>
          </div>
        ) : (
          <AISettings onSave={handleSave} />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// PATTERN 2: With React Router Integration
// ============================================================================

import { useNavigate, useLocation } from 'react-router-dom';

export function AISettingsWithRouter() {
  const navigate = useNavigate();
  const location = useLocation();

  const handleSave = (settings: { provider: string; customApiKey?: string }) => {
    console.log('Settings saved:', settings);

    // Check if we should navigate back or to a specific page
    const returnTo = (location.state as any)?.returnTo || '/dashboard';

    // Navigate with state
    navigate(returnTo, {
      state: {
        message: `AI provider switched to ${settings.provider}`,
        type: 'success'
      }
    });
  };

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Back Button */}
      <div className="p-6 border-b border-gray-800">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-400 hover:text-white transition flex items-center gap-2"
        >
          ← Back
        </button>
      </div>

      {/* Settings */}
      <AISettings onSave={handleSave} />
    </div>
  );
}

// Route configuration example:
/*
<Routes>
  <Route path="/dashboard" element={<Dashboard />} />
  <Route path="/settings/ai" element={<AISettingsWithRouter />} />
  <Route path="/products" element={<Products />} />
</Routes>
*/

// ============================================================================
// PATTERN 3: With Toast Notifications
// ============================================================================

import { toast } from 'react-hot-toast';

export function AISettingsWithToasts() {
  const handleSave = async (settings: { provider: string; customApiKey?: string }) => {
    // Show loading toast
    const loadingToast = toast.loading('Saving AI settings...');

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1500));

      // Dismiss loading and show success
      toast.dismiss(loadingToast);
      toast.success(
        `Successfully switched to ${settings.provider.toUpperCase()}`,
        {
          icon: '🤖',
          duration: 4000,
          style: {
            background: '#1F2937',
            color: '#fff',
            border: '1px solid #374151'
          }
        }
      );

      // If using custom key
      if (settings.customApiKey) {
        toast.success('Custom API key configured', {
          icon: '🔑',
          duration: 3000
        });
      }

    } catch (error) {
      toast.dismiss(loadingToast);
      toast.error('Failed to save settings. Please try again.', {
        duration: 4000,
        style: {
          background: '#1F2937',
          color: '#fff',
          border: '1px solid #EF4444'
        }
      });
    }
  };

  return (
    <div className="min-h-screen bg-gray-900">
      <AISettings onSave={handleSave} />
    </div>
  );
}

// ============================================================================
// PATTERN 4: With Context/State Management
// ============================================================================

import { createContext, useContext } from 'react';

// Settings Context
interface SettingsContextType {
  aiProvider: string;
  customApiKey: string | null;
  updateAISettings: (settings: { provider: string; customApiKey?: string }) => Promise<void>;
}

const SettingsContext = createContext<SettingsContextType | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [aiProvider, setAiProvider] = useState('claude');
  const [customApiKey, setCustomApiKey] = useState<string | null>(null);

  const updateAISettings = async (settings: { provider: string; customApiKey?: string }) => {
    // Save to backend
    const response = await fetch('http://localhost:8001/api/settings/ai-provider', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });

    if (response.ok) {
      setAiProvider(settings.provider);
      setCustomApiKey(settings.customApiKey || null);
    } else {
      throw new Error('Failed to save settings');
    }
  };

  return (
    <SettingsContext.Provider value={{ aiProvider, customApiKey, updateAISettings }}>
      {children}
    </SettingsContext.Provider>
  );
}

// Use in component
export function AISettingsWithContext() {
  const context = useContext(SettingsContext);

  if (!context) {
    throw new Error('Must be used within SettingsProvider');
  }

  const { updateAISettings } = context;

  return (
    <div className="min-h-screen bg-gray-900">
      <AISettings onSave={updateAISettings} />
    </div>
  );
}

// ============================================================================
// PATTERN 5: With Analytics Tracking
// ============================================================================

// Analytics utility
const analytics = {
  track: (event: string, properties?: any) => {
    console.log('Analytics:', event, properties);
    // Integrate with your analytics service (Mixpanel, Segment, etc.)
  }
};

export function AISettingsWithAnalytics() {
  const [originalProvider, setOriginalProvider] = useState('claude');

  const handleSave = async (settings: { provider: string; customApiKey?: string }) => {
    // Track provider change
    analytics.track('AI Provider Changed', {
      from: originalProvider,
      to: settings.provider,
      usingCustomKey: !!settings.customApiKey,
      timestamp: new Date().toISOString()
    });

    // Calculate cost impact
    const providers = {
      claude: 0.003,
      openai: 0.03,
      gemini: 0.00025
    };
    const costChange = providers[settings.provider] - providers[originalProvider];

    analytics.track('AI Cost Impact', {
      costChangePerThousand: costChange,
      expectedMonthlySavings: costChange * 245.68, // Based on avg usage
      provider: settings.provider
    });

    // Track custom key usage
    if (settings.customApiKey) {
      analytics.track('Custom API Key Configured', {
        provider: settings.provider
      });
    }

    // Save settings
    await saveSettings(settings);
    setOriginalProvider(settings.provider);

    // Track success
    analytics.track('AI Settings Saved', {
      provider: settings.provider,
      success: true
    });
  };

  return <AISettings onSave={handleSave} />;
}

// ============================================================================
// PATTERN 6: With Loading Overlay and Error Handling
// ============================================================================

export function AISettingsWithLoadingAndErrors() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async (settings: { provider: string; customApiKey?: string }) => {
    setLoading(true);
    setError(null);

    try {
      // Validate settings
      if (settings.customApiKey && settings.customApiKey.length < 20) {
        throw new Error('API key appears to be invalid (too short)');
      }

      // Save to backend
      const response = await fetch('http://localhost:8001/api/settings/ai-provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to save settings');
      }

      // Success
      console.log('Settings saved successfully');

    } catch (err) {
      setError(err.message);
      console.error('Error saving AI settings:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-gray-900">
      {/* Error Banner */}
      {error && (
        <div className="fixed top-0 left-0 right-0 bg-red-500 text-white p-4 text-center z-50">
          <strong>Error:</strong> {error}
          <button
            onClick={() => setError(null)}
            className="ml-4 underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Settings Component */}
      <AISettings onSave={handleSave} />

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-8 text-center max-w-sm">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <h3 className="text-xl font-bold text-white mb-2">Saving Settings</h3>
            <p className="text-gray-400">
              Configuring your AI provider...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// PATTERN 7: With Cost Alert System
// ============================================================================

export function AISettingsWithCostAlerts() {
  const [showCostWarning, setShowCostWarning] = useState(false);
  const [pendingSettings, setPendingSettings] = useState<any>(null);

  const calculateCostIncrease = (newProvider: string) => {
    const currentCost = 0.003; // Claude
    const costs = { claude: 0.003, openai: 0.03, gemini: 0.00025 };
    const newCost = costs[newProvider];
    return ((newCost - currentCost) / currentCost) * 100;
  };

  const handleSave = (settings: { provider: string; customApiKey?: string }) => {
    const costIncrease = calculateCostIncrease(settings.provider);

    // Show warning if cost increases by more than 50%
    if (costIncrease > 50) {
      setPendingSettings(settings);
      setShowCostWarning(true);
      return;
    }

    // Save directly
    confirmSave(settings);
  };

  const confirmSave = async (settings: { provider: string; customApiKey?: string }) => {
    console.log('Saving settings:', settings);
    setShowCostWarning(false);
    setPendingSettings(null);

    // Save to backend
    await saveSettings(settings);
  };

  return (
    <>
      <AISettings onSave={handleSave} />

      {/* Cost Warning Modal */}
      {showCostWarning && pendingSettings && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
              ⚠️ Cost Increase Warning
            </h3>
            <p className="text-gray-400 mb-4">
              Switching to {pendingSettings.provider.toUpperCase()} will significantly increase
              your AI costs. Are you sure you want to continue?
            </p>

            <div className="bg-yellow-500/10 border border-yellow-500/50 rounded p-3 mb-4">
              <p className="text-sm text-yellow-400">
                Estimated cost increase: <strong>+{calculateCostIncrease(pendingSettings.provider).toFixed(0)}%</strong>
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowCostWarning(false);
                  setPendingSettings(null);
                }}
                className="flex-1 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => confirmSave(pendingSettings)}
                className="flex-1 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition font-medium"
              >
                Continue Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ============================================================================
// PATTERN 8: With Redux Integration
// ============================================================================

import { useDispatch, useSelector } from 'react-redux';

// Redux actions
const updateAIProvider = (provider: string) => ({
  type: 'UPDATE_AI_PROVIDER',
  payload: provider
});

const updateCustomKey = (key: string | null) => ({
  type: 'UPDATE_CUSTOM_KEY',
  payload: key
});

export function AISettingsWithRedux() {
  const dispatch = useDispatch();
  const currentProvider = useSelector((state: any) => state.settings.aiProvider);

  const handleSave = async (settings: { provider: string; customApiKey?: string }) => {
    try {
      // Save to backend
      await saveSettings(settings);

      // Update Redux store
      dispatch(updateAIProvider(settings.provider));
      if (settings.customApiKey) {
        dispatch(updateCustomKey(settings.customApiKey));
      }

      console.log('Settings saved and Redux updated');
    } catch (error) {
      console.error('Failed to save:', error);
    }
  };

  return <AISettings onSave={handleSave} />;
}

// ============================================================================
// Helper Functions
// ============================================================================

async function saveSettings(settings: { provider: string; customApiKey?: string }) {
  const response = await fetch('http://localhost:8001/api/settings/ai-provider', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  });

  if (!response.ok) {
    throw new Error('Failed to save settings');
  }

  return response.json();
}

// ============================================================================
// Complete Application Example
// ============================================================================

export function CompleteAISettingsApp() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'settings'>('dashboard');
  const [aiProvider, setAiProvider] = useState('claude');
  const [loading, setLoading] = useState(false);

  const handleSave = async (settings: { provider: string; customApiKey?: string }) => {
    setLoading(true);

    try {
      // Save to backend
      await saveSettings(settings);

      // Update local state
      setAiProvider(settings.provider);

      // Track event
      analytics.track('AI Settings Changed', {
        provider: settings.provider,
        customKey: !!settings.customApiKey
      });

      // Show success
      toast.success(`Switched to ${settings.provider.toUpperCase()}`, {
        icon: '🤖',
        duration: 3000
      });

      // Navigate back
      setTimeout(() => {
        setCurrentView('dashboard');
      }, 1500);

    } catch (error) {
      console.error('Error:', error);
      toast.error('Failed to save settings');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">OspraOS</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">
              AI: <strong className="text-white">{aiProvider.toUpperCase()}</strong>
            </span>
            <button
              onClick={() => setCurrentView('settings')}
              className="px-4 py-2 bg-gray-800 rounded-lg hover:bg-gray-700 transition"
            >
              ⚙️ Settings
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main>
        {currentView === 'dashboard' ? (
          <div className="max-w-7xl mx-auto p-6">
            <h2 className="text-3xl font-bold mb-4">Dashboard</h2>
            <p className="text-gray-400">Your main dashboard content here...</p>
          </div>
        ) : (
          <>
            <div className="p-6 border-b border-gray-800">
              <button
                onClick={() => setCurrentView('dashboard')}
                className="text-gray-400 hover:text-white transition"
              >
                ← Back to Dashboard
              </button>
            </div>
            <AISettings onSave={handleSave} />
          </>
        )}
      </main>

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p>Saving settings...</p>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * USAGE NOTES:
 *
 * 1. Choose the pattern that best fits your architecture
 * 2. All patterns handle onSave callback differently
 * 3. Consider adding analytics tracking for important events
 * 4. Implement proper error handling and user feedback
 * 5. Use loading states for better UX
 * 6. Consider cost warnings for significant provider changes
 * 7. Test API key validation before allowing save
 */
