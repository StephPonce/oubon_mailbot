import { useState, useEffect } from 'react';
import {
  Megaphone,
  TrendingUp,
  Play,
  Pause,
  Sparkles,
  DollarSign,
  Eye,
  MousePointer,
  ShoppingCart,
  Filter,
  ArrowUpDown,
  Plus,
  Loader2,
  Calendar,
  Check,
  X as XIcon,
  Settings,
  AlertCircle
} from 'lucide-react';
import api from '../lib/api';

// Type definitions
interface MetaCampaign {
  id: string;
  name: string;
  status: string;
  objective: string;
  daily_budget: number | null;
  spend: number;
  impressions: number;
  clicks: number;
  roas: number;
}

interface MetaPerformance {
  connected: boolean;
  period?: string;
  spend?: number;
  impressions?: number;
  clicks?: number;
  cpc?: number;
  cpm?: number;
  roas?: number;
  message?: string;
}

interface MetaStatus {
  connected: boolean;
  message: string;
}

interface GeneratedAdCopy {
  headline: string;
  primary_text: string;
  description: string;
  cta: string;
  selling_angle: string;
}

export default function AdsPage() {
  // State management
  const [metaStatus, setMetaStatus] = useState<MetaStatus | null>(null);
  const [metaCampaigns, setMetaCampaigns] = useState<MetaCampaign[]>([]);
  const [metaPerformance, setMetaPerformance] = useState<MetaPerformance | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<any>(null);
  const [generatedCopy, setGeneratedCopy] = useState<GeneratedAdCopy | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('meta');

  // Fetch data
  useEffect(() => {
    checkMetaConnection();
  }, []);

  const checkMetaConnection = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/api/meta/status');
      setMetaStatus(response.data);

      if (response.data.connected) {
        // Fetch campaigns and performance if connected
        fetchMetaCampaigns();
        fetchMetaPerformance();
      }
    } catch (error) {
      console.error('Failed to check Meta connection:', error);
      setMetaStatus({ connected: false, message: 'Failed to connect to Meta API' });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchMetaCampaigns = async () => {
    try {
      const response = await api.get('/api/meta/campaigns');
      if (response.data.connected && response.data.campaigns) {
        setMetaCampaigns(response.data.campaigns);
      }
    } catch (error) {
      console.error('Failed to fetch Meta campaigns:', error);
    }
  };

  const fetchMetaPerformance = async () => {
    try {
      const response = await api.get('/api/meta/performance');
      setMetaPerformance(response.data);
    } catch (error) {
      console.error('Failed to fetch Meta performance:', error);
    }
  };

  const pauseCampaign = async (campaignId: string) => {
    try {
      await api.post(`/api/meta/campaigns/${campaignId}/pause`);
      fetchMetaCampaigns();
      fetchMetaPerformance();
    } catch (error) {
      console.error('Failed to pause campaign:', error);
    }
  };

  const resumeCampaign = async (campaignId: string) => {
    try {
      await api.post(`/api/meta/campaigns/${campaignId}/resume`);
      fetchMetaCampaigns();
      fetchMetaPerformance();
    } catch (error) {
      console.error('Failed to resume campaign:', error);
    }
  };

  const generateAdCopy = async () => {
    if (!selectedProduct) return;

    try {
      setIsGenerating(true);
      const response = await api.post('/api/ads/generate-copy', {
        product_id: selectedProduct.id,
        product_name: selectedProduct.name,
        product_description: selectedProduct.description || selectedProduct.name,
        platform: selectedPlatform,
        variations: 1
      });

      const creative = response.data.creative;
      if (creative.variations && creative.variations.length > 0) {
        const variation = creative.variations[0];
        setGeneratedCopy({
          headline: variation.headline,
          primary_text: variation.body || variation.description,
          description: variation.description || variation.body,
          cta: variation.cta,
          selling_angle: variation.selling_angle || 'Value-driven approach'
        });
      }
    } catch (error) {
      console.error('Failed to generate ad copy:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // Platform colors
  const platformColors: Record<string, string> = {
    meta: '#0081FB',
    tiktok: '#000000',
    google: '#4285F4'
  };

  // Platform icons
  const platformIcons: Record<string, string> = {
    meta: '',
    tiktok: '🎵',
    google: '🔍'
  };

  // Show loading state
  if (isLoading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-12 h-12 animate-spin text-accent" />
        </div>
      </div>
    );
  }

  // Show "Not Connected" state
  if (!metaStatus?.connected) {
    return (
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
              <Megaphone className="w-7 h-7 text-accent" />
              Advertisement Command Center
            </h1>
            <p className="text-sm text-secondary mt-1">
              Connect your Meta Ads account to manage campaigns
            </p>
          </div>
        </div>

        {/* Not Connected Card */}
        <div className="glass-card p-8 border-2 border-dashed border-white/10">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-cyan-500/10 rounded-lg">
              <Settings className="w-8 h-8 text-blue-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-xl font-semibold text-primary mb-2">
                Connect Meta Ads Account
              </h2>
              <p className="text-secondary mb-4">
                {metaStatus?.message || 'Meta Ads not configured. Add credentials to get started.'}
              </p>

              <div className="  rounded-lg p-4 mb-4">
                <h3 className="text-sm font-semibold text-primary mb-2">Setup Instructions:</h3>
                <ol className="text-sm text-secondary space-y-2 list-decimal list-inside">
                  <li>Go to Facebook Business Manager (business.facebook.com)</li>
                  <li>Create a new app or select an existing one</li>
                  <li>Enable Marketing API access</li>
                  <li>Generate an Access Token with ads_read and ads_management permissions</li>
                  <li>Find your Ad Account ID in Ads Manager settings</li>
                  <li>Add these credentials to your .env file:
                    <div className="mt-2 p-3 bg-gray-800 rounded text-xs text-green-400 font-mono">
                      META_ACCESS_TOKEN=your_access_token<br/>
                      META_AD_ACCOUNT_ID=your_account_id<br/>
                      META_APP_ID=your_app_id<br/>
                      META_APP_SECRET=your_app_secret
                    </div>
                  </li>
                  <li>Restart the backend server</li>
                </ol>
              </div>

              <button
                onClick={checkMetaConnection}
                className="btn-primary"
              >
                <Check className="w-4 h-4" />
                <span>Test Connection</span>
              </button>
            </div>
          </div>
        </div>

        {/* Info Card */}
        <div className="glass-card p-4 bg-cyan-500/10 border-l-4 border-blue-500">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-blue-900 mb-1">Why Connect Meta Ads?</p>
              <p className="text-sm text-cyan-400">
                Once connected, you'll be able to view real campaign performance, manage budgets,
                pause/resume campaigns, and access AI-powered ad copy generation - all from this dashboard.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show Connected state with real data
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
            <Megaphone className="w-7 h-7 text-accent" />
            Meta Ads Dashboard
          </h1>
          <p className="text-sm text-secondary mt-1">
            Real-time campaign management and performance tracking
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/100/10 rounded-lg">
          <div className="w-2 h-2 bg-green-500/100 rounded-full animate-pulse"></div>
          <span className="text-sm font-medium text-green-400">Connected</span>
        </div>
      </div>

      {/* Performance Overview */}
      {metaPerformance?.connected && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-tertiary uppercase">Total Spend</p>
                <p className="text-2xl font-bold text-primary mt-1">
                  ${metaPerformance.spend?.toFixed(2) || '0.00'}
                </p>
                <p className="text-xs text-secondary mt-1">Last 30 days</p>
              </div>
              <DollarSign className="w-10 h-10 text-accent opacity-20" />
            </div>
          </div>

          <div className="glass-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-tertiary uppercase">ROAS</p>
                <p className="text-2xl font-bold text-primary mt-1">
                  {metaPerformance.roas?.toFixed(2) || '0.00'}x
                </p>
                <p className="text-xs text-secondary mt-1">Return on ad spend</p>
              </div>
              <TrendingUp className="w-10 h-10 text-green-500 opacity-20" />
            </div>
          </div>

          <div className="glass-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-tertiary uppercase">Impressions</p>
                <p className="text-2xl font-bold text-primary mt-1">
                  {metaPerformance.impressions?.toLocaleString() || 0}
                </p>
                <p className="text-xs text-secondary mt-1">Total views</p>
              </div>
              <Eye className="w-10 h-10 text-blue-500 opacity-20" />
            </div>
          </div>

          <div className="glass-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-tertiary uppercase">Clicks</p>
                <p className="text-2xl font-bold text-primary mt-1">
                  {metaPerformance.clicks?.toLocaleString() || 0}
                </p>
                <p className="text-xs text-secondary mt-1">
                  ${metaPerformance.cpc?.toFixed(2) || '0.00'} CPC
                </p>
              </div>
              <MousePointer className="w-10 h-10 text-purple-500 opacity-20" />
            </div>
          </div>
        </div>
      )}

      {/* AI Ad Generator */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="w-5 h-5 text-accent" />
          <h2 className="text-lg font-semibold text-primary">AI Ad Copy Generator</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-secondary mb-2">
                Select Product
              </label>
              <select
                className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-accent focus:border-transparent"
                value={selectedProduct?.id || ''}
                onChange={(e) => {
                  const product = { id: e.target.value, name: e.target.selectedOptions[0].text };
                  setSelectedProduct(product);
                }}
              >
                <option value="">Choose a product...</option>
                <option value="demo-1">Smart LED Strip Lights</option>
                <option value="demo-2">Wireless Security Camera</option>
                <option value="demo-3">Smart Door Lock</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary mb-2">
                Platform
              </label>
              <div className="flex gap-2">
                {['meta', 'tiktok', 'google'].map((platform) => (
                  <button
                    key={platform}
                    onClick={() => setSelectedPlatform(platform)}
                    className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      selectedPlatform === platform
                        ? 'bg-accent text-white'
                        : 'bg-gray-100 text-secondary hover:bg-gray-200'
                    }`}
                  >
                    {platform === 'meta' ? 'Meta' : platform.charAt(0).toUpperCase() + platform.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={generateAdCopy}
              disabled={!selectedProduct || isGenerating}
              className="w-full btn-primary"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Generating...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generate Ad Copy</span>
                </>
              )}
            </button>
          </div>

          {generatedCopy && (
            <div className="space-y-4 p-4   rounded-lg">
              <h3 className="font-semibold text-primary">Generated Ad Copy</h3>

              <div>
                <p className="text-xs text-tertiary uppercase mb-1">Headline</p>
                <p className="text-sm font-medium text-primary">{generatedCopy.headline}</p>
              </div>

              <div>
                <p className="text-xs text-tertiary uppercase mb-1">Primary Text</p>
                <p className="text-sm text-secondary">{generatedCopy.primary_text}</p>
              </div>

              <div>
                <p className="text-xs text-tertiary uppercase mb-1">Call-to-Action</p>
                <p className="text-sm font-medium text-accent">{generatedCopy.cta}</p>
              </div>

              <div>
                <p className="text-xs text-tertiary uppercase mb-1">Selling Angle</p>
                <p className="text-sm text-secondary">{generatedCopy.selling_angle}</p>
              </div>

              <button className="w-full btn-secondary text-sm">
                <Plus className="w-4 h-4" />
                <span>Deploy to {selectedPlatform.charAt(0).toUpperCase() + selectedPlatform.slice(1)}</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Campaign Table */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-primary">Meta Ad Campaigns</h2>
          <button
            onClick={() => {
              fetchMetaCampaigns();
              fetchMetaPerformance();
            }}
            className="btn-secondary text-sm"
          >
            <TrendingUp className="w-4 h-4" />
            <span>Refresh</span>
          </button>
        </div>

        {metaCampaigns.length === 0 ? (
          <div className="py-12 text-center text-tertiary">
            <Megaphone className="w-16 h-16 mx-auto mb-4 opacity-20" />
            <p>No campaigns found</p>
            <p className="text-sm mt-1">Create campaigns in Meta Ads Manager to see them here</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Campaign
                  </th>
                  <th className="text-left text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Objective
                  </th>
                  <th className="text-left text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Status
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Daily Budget
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Spend (30d)
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Clicks
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    ROAS
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {metaCampaigns.map((campaign) => (
                  <tr key={campaign.id} className="border-b border-gray-100 hover: ">
                    <td className="py-3 px-4">
                      <p className="text-sm font-medium text-primary">{campaign.name}</p>
                      <p className="text-xs text-tertiary">ID: {campaign.id}</p>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-xs px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded-full">
                        {campaign.objective}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                          campaign.status === 'ACTIVE'
                            ? 'bg-green-100 text-green-400'
                            : 'bg-gray-100 text-secondary'
                        }`}
                      >
                        {campaign.status === 'ACTIVE' ? <Check className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                        {campaign.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-secondary">
                      {campaign.daily_budget ? `$${campaign.daily_budget.toFixed(2)}` : 'N/A'}
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-primary font-medium">
                      ${campaign.spend.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-secondary">
                      {campaign.clicks.toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right text-sm font-semibold text-green-600">
                      {campaign.roas.toFixed(2)}x
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {campaign.status === 'ACTIVE' ? (
                          <button
                            onClick={() => pauseCampaign(campaign.id)}
                            className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                            title="Pause campaign"
                          >
                            <Pause className="w-4 h-4 text-secondary" />
                          </button>
                        ) : (
                          <button
                            onClick={() => resumeCampaign(campaign.id)}
                            className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                            title="Resume campaign"
                          >
                            <Play className="w-4 h-4 text-green-600" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
