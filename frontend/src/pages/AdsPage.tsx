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
  X as XIcon
} from 'lucide-react';
import api from '../lib/api';

// Type definitions
interface CampaignMetrics {
  campaign_id: string;
  platform: string;
  status: string;
  daily_budget: number;
  total_spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  ctr: number;
  cpc: number;
  roas: number;
  created_at: string;
  activated_at: string | null;
}

interface Analytics {
  total_campaigns: number;
  active_campaigns: number;
  paused_campaigns: number;
  total_spend: number;
  total_impressions: number;
  total_clicks: number;
  total_conversions: number;
  total_revenue: number;
  average_ctr: number;
  average_cpc: number;
  average_roas: number;
  by_platform: Record<string, any>;
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
  const [campaigns, setCampaigns] = useState<CampaignMetrics[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [filterPlatform, setFilterPlatform] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [selectedProduct, setSelectedProduct] = useState<any>(null);
  const [generatedCopy, setGeneratedCopy] = useState<GeneratedAdCopy | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('meta');

  // Fetch data
  useEffect(() => {
    fetchAnalytics();
    fetchCampaigns();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await api.get('/api/ads/analytics');
      setAnalytics(response.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    }
  };

  const fetchCampaigns = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/api/ads/campaigns', {
        params: {
          platform: filterPlatform !== 'all' ? filterPlatform : undefined,
          status: filterStatus !== 'all' ? filterStatus : undefined,
          limit: 100
        }
      });
      setCampaigns(response.data);
    } catch (error) {
      console.error('Failed to fetch campaigns:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const pauseCampaign = async (campaignId: string) => {
    try {
      await api.post(`/api/ads/campaigns/${campaignId}/pause`);
      fetchCampaigns();
      fetchAnalytics();
    } catch (error) {
      console.error('Failed to pause campaign:', error);
    }
  };

  const activateCampaign = async (campaignId: string) => {
    try {
      await api.post(`/api/ads/campaigns/${campaignId}/activate`);
      fetchCampaigns();
      fetchAnalytics();
    } catch (error) {
      console.error('Failed to activate campaign:', error);
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
            Unified control for all advertising campaigns across Meta, TikTok, and Google
          </p>
        </div>
      </div>

      {/* Overview Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-tertiary uppercase">Total Spend</p>
              <p className="text-2xl font-bold text-primary mt-1">
                ${analytics?.total_spend.toFixed(2) || '0.00'}
              </p>
              <p className="text-xs text-secondary mt-1">This month</p>
            </div>
            <DollarSign className="w-10 h-10 text-accent opacity-20" />
          </div>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-tertiary uppercase">Average ROAS</p>
              <p className="text-2xl font-bold text-primary mt-1">
                {analytics?.average_roas.toFixed(2) || '0.00'}x
              </p>
              <p className="text-xs text-secondary mt-1">Return on ad spend</p>
            </div>
            <TrendingUp className="w-10 h-10 text-green-500 opacity-20" />
          </div>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-tertiary uppercase">Active Campaigns</p>
              <p className="text-2xl font-bold text-primary mt-1">
                {analytics?.active_campaigns || 0}
              </p>
              <p className="text-xs text-secondary mt-1">
                of {analytics?.total_campaigns || 0} total
              </p>
            </div>
            <Play className="w-10 h-10 text-blue-500 opacity-20" />
          </div>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-tertiary uppercase">Conversions</p>
              <p className="text-2xl font-bold text-primary mt-1">
                {analytics?.total_conversions || 0}
              </p>
              <p className="text-xs text-secondary mt-1">
                {analytics?.average_ctr.toFixed(2) || '0'}% CTR
              </p>
            </div>
            <ShoppingCart className="w-10 h-10 text-purple-500 opacity-20" />
          </div>
        </div>
      </div>

      {/* Platform Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {['meta', 'tiktok', 'google'].map((platform) => {
          const platformData = analytics?.by_platform?.[platform];
          const hasData = platformData && platformData.campaigns > 0;

          return (
            <div
              key={platform}
              className="glass-card p-5"
              style={{ borderTop: `3px solid ${platformColors[platform]}` }}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{platformIcons[platform]}</span>
                  <div>
                    <h3 className="text-lg font-semibold text-primary capitalize">
                      {platform === 'meta' ? 'Meta (FB/IG)' : platform}
                    </h3>
                    <p className="text-xs text-tertiary">
                      {hasData ? `${platformData.campaigns} campaigns` : 'No campaigns'}
                    </p>
                  </div>
                </div>
                <div
                  className={`px-2 py-1 rounded-full text-xs font-medium ${
                    hasData ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {hasData ? 'Active' : 'Inactive'}
                </div>
              </div>

              {hasData ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-secondary">Spend:</span>
                    <span className="font-semibold text-primary">
                      ${platformData.spend?.toFixed(2) || '0.00'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-secondary">Clicks:</span>
                    <span className="font-semibold text-primary">
                      {platformData.clicks?.toLocaleString() || 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-secondary">Conversions:</span>
                    <span className="font-semibold text-primary">
                      {platformData.conversions || 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-secondary">Revenue:</span>
                    <span className="font-semibold text-green-600">
                      ${platformData.revenue?.toFixed(2) || '0.00'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center text-tertiary text-sm">
                  No active campaigns on this platform
                </div>
              )}
            </div>
          );
        })}
      </div>

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
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-accent focus:border-transparent"
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
            <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
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
          <h2 className="text-lg font-semibold text-primary">All Campaigns</h2>

          <div className="flex items-center gap-3">
            <select
              value={filterPlatform}
              onChange={(e) => {
                setFilterPlatform(e.target.value);
                fetchCampaigns();
              }}
              className="text-sm px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="all">All Platforms</option>
              <option value="meta">Meta</option>
              <option value="tiktok">TikTok</option>
              <option value="google">Google</option>
            </select>

            <select
              value={filterStatus}
              onChange={(e) => {
                setFilterStatus(e.target.value);
                fetchCampaigns();
              }}
              className="text-sm px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="py-12 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-accent" />
          </div>
        ) : campaigns.length === 0 ? (
          <div className="py-12 text-center text-tertiary">
            <Megaphone className="w-16 h-16 mx-auto mb-4 opacity-20" />
            <p>No campaigns found</p>
            <p className="text-sm mt-1">Create your first campaign to get started</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Campaign
                  </th>
                  <th className="text-left text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Platform
                  </th>
                  <th className="text-left text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Status
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Spend
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Clicks
                  </th>
                  <th className="text-right text-xs font-semibold text-tertiary uppercase py-3 px-4">
                    Conv.
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
                {campaigns.map((campaign) => (
                  <tr key={campaign.campaign_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <p className="text-sm font-medium text-primary">{campaign.campaign_id}</p>
                      <p className="text-xs text-tertiary">
                        Created {new Date(campaign.created_at).toLocaleDateString()}
                      </p>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium text-white"
                        style={{ backgroundColor: platformColors[campaign.platform] }}
                      >
                        {platformIcons[campaign.platform]} {campaign.platform.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                          campaign.status === 'active'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {campaign.status === 'active' ? <Check className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                        {campaign.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-primary font-medium">
                      ${campaign.total_spend.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-secondary">
                      {campaign.clicks.toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-secondary">
                      {campaign.conversions}
                    </td>
                    <td className="py-3 px-4 text-right text-sm font-semibold text-green-600">
                      {campaign.roas.toFixed(2)}x
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {campaign.status === 'active' ? (
                          <button
                            onClick={() => pauseCampaign(campaign.campaign_id)}
                            className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                            title="Pause campaign"
                          >
                            <Pause className="w-4 h-4 text-gray-600" />
                          </button>
                        ) : (
                          <button
                            onClick={() => activateCampaign(campaign.campaign_id)}
                            className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                            title="Activate campaign"
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
