import React, { useState, useEffect } from 'react';
import {
  User,
  Mail,
  Lock,
  Shield,
  CreditCard,
  Bell,
  Plug,
  Brain,
  MessageSquare,
  Users,
  Key,
  Database,
  Trash2,
  Download,
  Save,
  Check,
  X,
  AlertCircle,
  ExternalLink,
  Crown,
  Zap,
  Rocket,
  Store,
  ChevronDown,
  CheckCircle,
  XCircle,
  Calendar,
  DollarSign,
  TrendingUp,
  Globe,
  Clock,
  Send,
  UserPlus,
  Copy,
  RefreshCw,
  Eye,
  EyeOff,
  Loader2
} from 'lucide-react';
import AISettings from '../components/AISettings';

// Types
interface UserProfile {
  id: number;
  name: string;
  email: string;
  avatar?: string;
  timezone: string;
  twoFactorEnabled: boolean;
}

interface SubscriptionInfo {
  tier: 'NEST' | 'FLIGHT' | 'SOAR' | 'STRATOSPHERE';
  status: 'active' | 'trial' | 'expired';
  billingCycle: 'monthly' | 'yearly';
  nextBillingDate: string;
  usage: {
    discoveries: { used: number; limit: number };
    stores: { used: number; limit: number };
    teamMembers: { used: number; limit: number };
  };
}

interface Integration {
  id: string;
  name: string;
  icon: React.ReactNode;
  status: 'connected' | 'disconnected' | 'error';
  lastSync?: string;
  canDisconnect?: boolean;
}

interface TeamMember {
  id: number;
  name: string;
  email: string;
  role: 'admin' | 'editor' | 'viewer';
  joinedAt: string;
  avatar?: string;
}

interface NotificationSettings {
  emailNotifications: {
    dailyDigest: boolean;
    productRecommendations: boolean;
    priceAlerts: boolean;
    lowStockWarnings: boolean;
    adPerformance: boolean;
  };
  pushNotifications: boolean;
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
}

// Tier configurations
const TIER_INFO = {
  NEST: { name: 'Nest', icon: <Store className="w-5 h-5" />, color: 'text-secondary', price: 0, stores: 1, team: 0, apiAccess: false },
  FLIGHT: { name: 'Flight', icon: <Zap className="w-5 h-5" />, color: 'text-blue-600', price: 49, stores: 1, team: 0, apiAccess: false },
  SOAR: { name: 'Soar', icon: <Rocket className="w-5 h-5" />, color: 'text-purple-600', price: 99, stores: 5, team: 0, apiAccess: true },
  STRATOSPHERE: { name: 'Stratosphere', icon: <Crown className="w-5 h-5" />, color: 'text-yellow-600', price: 199, stores: Infinity, team: 3, apiAccess: true }
};

export default function NewSettingsPage() {
  const [activeTab, setActiveTab] = useState('profile');
  const [saving, setSaving] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // User profile state
  const [profile, setProfile] = useState<UserProfile>({
    id: 1,
    name: 'Steph Ponce',
    email: 'steph@ospra.io',
    timezone: 'America/Los_Angeles',
    twoFactorEnabled: false
  });

  // Subscription state
  const [subscription, setSubscription] = useState<SubscriptionInfo>({
    tier: 'STRATOSPHERE',
    status: 'active',
    billingCycle: 'monthly',
    nextBillingDate: '2025-01-09',
    usage: {
      discoveries: { used: 15, limit: Infinity },
      stores: { used: 2, limit: Infinity },
      teamMembers: { used: 1, limit: 3 }
    }
  });

  // Notifications state
  const [notifications, setNotifications] = useState<NotificationSettings>({
    emailNotifications: {
      dailyDigest: true,
      productRecommendations: true,
      priceAlerts: true,
      lowStockWarnings: true,
      adPerformance: false
    },
    pushNotifications: true,
    quietHoursEnabled: true,
    quietHoursStart: '22:00',
    quietHoursEnd: '08:00'
  });

  // Integrations state
  const [integrations, setIntegrations] = useState<Integration[]>([
    { id: 'shopify', name: 'Shopify', icon: <span className="text-green-600 font-bold">S</span>, status: 'connected', lastSync: '2 mins ago', canDisconnect: true },
    { id: 'aliexpress', name: 'AliExpress', icon: <span className="text-red-600 font-bold">A</span>, status: 'connected', lastSync: '1 hour ago', canDisconnect: true },
    { id: 'meta', name: 'Meta Ads', icon: <Globe className="w-4 h-4 text-blue-600" />, status: 'disconnected', canDisconnect: false },
    { id: 'tiktok', name: 'TikTok Ads', icon: <span className="text-black font-bold">T</span>, status: 'disconnected', canDisconnect: false },
    { id: 'gmail', name: 'Gmail', icon: <Mail className="w-4 h-4 text-red-600" />, status: 'connected', lastSync: '5 mins ago', canDisconnect: true }
  ]);

  // AI preferences state
  const [aiPreferences, setAiPreferences] = useState({
    personality: 'professional',
    autoSuggestions: true,
    autoDeployContent: false,
    preferredNiches: ['fitness', 'smart_home', 'pet_supplies']
  });

  // Brand voice state
  const [brandVoice, setBrandVoice] = useState({
    storeId: 1,
    brandName: 'Oubon Shop',
    description: 'Premium dropshipping store focused on quality lifestyle products',
    tone: 'modern',
    targetAudience: 'Health-conscious millennials aged 25-40'
  });

  // Team members state
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([
    { id: 1, name: 'Steph Ponce', email: 'steph@ospra.io', role: 'admin', joinedAt: '2024-12-01', avatar: undefined }
  ]);

  // API key state
  const [apiKey, setApiKey] = useState('ospra_sk_1234567890abcdefghijklmnopqrstuvwxyz');
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKeyRegenerated, setApiKeyRegenerated] = useState(false);

  // Helper functions
  const handleSave = async () => {
    setSaving(true);
    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate API call
    setSaving(false);
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 3000);
  };

  const canAccessTeam = () => subscription.tier === 'STRATOSPHERE';
  const canAccessApi = () => ['SOAR', 'STRATOSPHERE'].includes(subscription.tier);

  const tierInfo = TIER_INFO[subscription.tier];

  // Navigation tabs
  const tabs = [
    { id: 'profile', label: 'Profile', icon: <User className="w-4 h-4" /> },
    { id: 'subscription', label: 'Subscription', icon: <CreditCard className="w-4 h-4" /> },
    { id: 'notifications', label: 'Notifications', icon: <Bell className="w-4 h-4" /> },
    { id: 'integrations', label: 'Integrations', icon: <Plug className="w-4 h-4" /> },
    { id: 'ai', label: 'AI Preferences', icon: <Brain className="w-4 h-4" /> },
    { id: 'brand', label: 'Brand Voice', icon: <MessageSquare className="w-4 h-4" /> },
    ...(canAccessTeam() ? [{ id: 'team', label: 'Team', icon: <Users className="w-4 h-4" /> }] : []),
    ...(canAccessApi() ? [{ id: 'api', label: 'API Access', icon: <Key className="w-4 h-4" /> }] : []),
    { id: 'privacy', label: 'Privacy', icon: <Database className="w-4 h-4" /> }
  ];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-primary">Settings</h1>
        <p className="text-sm text-tertiary mt-1">Manage your account, preferences, and integrations</p>
      </div>

      {/* Success notification */}
      {showSuccess && (
        <div className="mb-6 p-4 bg-green-500/100/10 border border-green-500/50 rounded-lg flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-600" />
          <p className="text-sm text-green-400">Settings saved successfully!</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <nav className="glass-card p-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-cyan-500/10 text-cyan-400'
                    : 'text-secondary hover:bg-white/5'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content Area */}
        <div className="lg:col-span-3 space-y-6">
          {/* A) Profile Section */}
          {activeTab === 'profile' && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold text-primary mb-6 flex items-center gap-2">
                <User className="w-5 h-5" />
                Profile Settings
              </h2>

              <div className="space-y-6">
                {/* Avatar & Basic Info */}
                <div className="flex items-start gap-6">
                  <div className="w-24 h-24 rounded-full bg-cyan-500/10 flex items-center justify-center text-3xl font-bold text-cyan-400">
                    {profile.name.split(' ').map(n => n[0]).join('')}
                  </div>
                  <div className="flex-1 space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">Full Name</label>
                      <input
                        type="text"
                        value={profile.name}
                        onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">Email Address</label>
                      <input
                        type="email"
                        value={profile.email}
                        onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                    </div>
                  </div>
                </div>

                {/* Timezone */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Timezone</label>
                  <select
                    value={profile.timezone}
                    onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                    className="w-full px-4 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  >
                    <option value="America/Los_Angeles">Pacific Time (US & Canada)</option>
                    <option value="America/New_York">Eastern Time (US & Canada)</option>
                    <option value="America/Chicago">Central Time (US & Canada)</option>
                    <option value="America/Denver">Mountain Time (US & Canada)</option>
                    <option value="UTC">UTC</option>
                    <option value="Europe/London">London</option>
                  </select>
                </div>

                {/* Two-Factor Authentication */}
                <div className="flex items-center justify-between p-4 bg-black/20 rounded-lg">
                  <div>
                    <div className="flex items-center gap-2 font-medium text-primary">
                      <Shield className="w-4 h-4" />
                      Two-Factor Authentication
                    </div>
                    <p className="text-sm text-tertiary mt-1">Add an extra layer of security to your account</p>
                  </div>
                  <button
                    onClick={() => setProfile({ ...profile, twoFactorEnabled: !profile.twoFactorEnabled })}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      profile.twoFactorEnabled
                        ? 'bg-success text-white'
                        : 'bg-white/10 text-primary hover:bg-white/20'
                    }`}
                  >
                    {profile.twoFactorEnabled ? 'Enabled' : 'Enable'}
                  </button>
                </div>

                {/* Change Password */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Change Password</label>
                  <button className="px-4 py-2 bg-white/10 text-primary rounded-lg hover:bg-white/20 transition-colors flex items-center gap-2">
                    <Lock className="w-4 h-4" />
                    Update Password
                  </button>
                </div>

                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-6 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors flex items-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Profile
                </button>
              </div>
            </div>
          )}

          {/* B) Subscription & Billing */}
          {activeTab === 'subscription' && (
            <div className="space-y-6">
              {/* Current Plan */}
              <div className="glass-card p-6">
                <h2 className="text-lg font-semibold text-primary mb-6 flex items-center gap-2">
                  <CreditCard className="w-5 h-5" />
                  Subscription & Billing
                </h2>

                {/* Tier Badge */}
                <div className="mb-6 p-6 bg-gradient-to-br from-cyan-500/10 to-purple-500/10 rounded-xl border border-white/10">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`${tierInfo.color}`}>{tierInfo.icon}</div>
                      <div>
                        <h3 className="text-xl font-bold text-primary">{tierInfo.name} Plan</h3>
                        <p className="text-sm text-tertiary">${tierInfo.price}/month</p>
                      </div>
                    </div>
                    <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                      subscription.status === 'active' ? 'bg-success/20 text-success' :
                      subscription.status === 'trial' ? 'bg-cyan-500/20 text-cyan-400' :
                      'bg-error/20 text-error'
                    }`}>
                      {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
                    </div>
                  </div>

                  {/* Next Billing */}
                  <div className="flex items-center gap-2 text-sm text-tertiary">
                    <Calendar className="w-4 h-4" />
                    Next billing date: {new Date(subscription.nextBillingDate).toLocaleDateString()}
                  </div>
                </div>

                {/* Usage Stats */}
                <div className="space-y-4 mb-6">
                  <h3 className="text-sm font-medium text-primary">Usage This Month</h3>

                  {/* Discoveries */}
                  <div>
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-tertiary">Product Discoveries</span>
                      <span className="font-medium text-primary">
                        {subscription.usage.discoveries.used} / {subscription.usage.discoveries.limit === Infinity ? '∞' : subscription.usage.discoveries.limit}
                      </span>
                    </div>
                    {subscription.usage.discoveries.limit !== Infinity && (
                      <div className="h-2 bg-black/20 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-cyan-500"
                          style={{ width: `${(subscription.usage.discoveries.used / subscription.usage.discoveries.limit) * 100}%` }}
                        />
                      </div>
                    )}
                  </div>

                  {/* Stores */}
                  <div>
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-tertiary">Connected Stores</span>
                      <span className="font-medium text-primary">
                        {subscription.usage.stores.used} / {subscription.usage.stores.limit === Infinity ? '∞' : subscription.usage.stores.limit}
                      </span>
                    </div>
                    {subscription.usage.stores.limit !== Infinity && (
                      <div className="h-2 bg-black/20 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-purple-500"
                          style={{ width: `${(subscription.usage.stores.used / subscription.usage.stores.limit) * 100}%` }}
                        />
                      </div>
                    )}
                  </div>

                  {/* Team Members */}
                  {subscription.tier === 'STRATOSPHERE' && (
                    <div>
                      <div className="flex items-center justify-between text-sm mb-2">
                        <span className="text-tertiary">Team Members</span>
                        <span className="font-medium text-primary">
                          {subscription.usage.teamMembers.used} / {subscription.usage.teamMembers.limit}
                        </span>
                      </div>
                      <div className="h-2 bg-black/20 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-amber-500/100"
                          style={{ width: `${(subscription.usage.teamMembers.used / subscription.usage.teamMembers.limit) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3">
                  <button className="flex-1 px-4 py-2 bg-gradient-to-r from-cyan-500 to-purple-500 text-white rounded-lg hover:scale-105 transition-transform font-medium">
                    Upgrade Plan
                  </button>
                  <button className="px-4 py-2 bg-white/10 text-primary rounded-lg hover:bg-white/20 transition-colors font-medium flex items-center gap-2">
                    <ExternalLink className="w-4 h-4" />
                    Manage Billing
                  </button>
                </div>
              </div>

              {/* Invoice History */}
              <div className="glass-card p-6">
                <h3 className="text-lg font-semibold text-primary mb-4">Invoice History</h3>
                <div className="space-y-2">
                  {[
                    { date: '2024-12-09', amount: 199, status: 'paid' },
                    { date: '2024-11-09', amount: 199, status: 'paid' },
                    { date: '2024-10-09', amount: 199, status: 'paid' }
                  ].map((invoice, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                      <div className="flex items-center gap-3">
                        <DollarSign className="w-4 h-4 text-success" />
                        <div>
                          <div className="text-sm font-medium text-primary">${invoice.amount.toFixed(2)}</div>
                          <div className="text-xs text-tertiary">{new Date(invoice.date).toLocaleDateString()}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs px-2 py-1 rounded-full bg-success/20 text-success">Paid</span>
                        <button className="p-2 hover:bg-white/10 rounded transition-colors">
                          <Download className="w-4 h-4 text-tertiary" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* C) Notifications */}
          {activeTab === 'notifications' && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold text-primary mb-6 flex items-center gap-2">
                <Bell className="w-5 h-5" />
                Notification Preferences
              </h2>

              <div className="space-y-6">
                {/* Email Notifications */}
                <div>
                  <h3 className="text-sm font-medium text-primary mb-4">Email Notifications</h3>
                  <div className="space-y-3">
                    {Object.entries({
                      dailyDigest: 'Daily Digest',
                      productRecommendations: 'New Product Recommendations',
                      priceAlerts: 'Price Alerts',
                      lowStockWarnings: 'Low Stock Warnings',
                      adPerformance: 'Ad Performance Alerts'
                    }).map(([key, label]) => (
                      <div key={key} className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                        <span className="text-sm text-primary">{label}</span>
                        <button
                          onClick={() => setNotifications({
                            ...notifications,
                            emailNotifications: {
                              ...notifications.emailNotifications,
                              [key]: !notifications.emailNotifications[key as keyof typeof notifications.emailNotifications]
                            }
                          })}
                          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                            notifications.emailNotifications[key as keyof typeof notifications.emailNotifications]
                              ? 'bg-cyan-500'
                              : 'bg-black/20'
                          }`}
                        >
                          <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                              notifications.emailNotifications[key as keyof typeof notifications.emailNotifications]
                                ? 'translate-x-6'
                                : 'translate-x-1'
                            }`}
                          />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Push Notifications */}
                <div>
                  <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                    <div>
                      <div className="text-sm font-medium text-primary">Push Notifications</div>
                      <p className="text-xs text-tertiary mt-1">Browser notifications for real-time updates</p>
                    </div>
                    <button
                      onClick={() => setNotifications({ ...notifications, pushNotifications: !notifications.pushNotifications })}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        notifications.pushNotifications ? 'bg-cyan-500' : 'bg-black/20'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          notifications.pushNotifications ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                </div>

                {/* Quiet Hours */}
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="text-sm font-medium text-primary flex items-center gap-2">
                        <Clock className="w-4 h-4" />
                        Quiet Hours
                      </div>
                      <p className="text-xs text-tertiary mt-1">Mute notifications during specific hours</p>
                    </div>
                    <button
                      onClick={() => setNotifications({ ...notifications, quietHoursEnabled: !notifications.quietHoursEnabled })}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        notifications.quietHoursEnabled ? 'bg-cyan-500' : 'bg-black/20'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          notifications.quietHoursEnabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                  {notifications.quietHoursEnabled && (
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-tertiary mb-2">Start Time</label>
                        <input
                          type="time"
                          value={notifications.quietHoursStart}
                          onChange={(e) => setNotifications({ ...notifications, quietHoursStart: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-tertiary mb-2">End Time</label>
                        <input
                          type="time"
                          value={notifications.quietHoursEnd}
                          onChange={(e) => setNotifications({ ...notifications, quietHoursEnd: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500"
                        />
                      </div>
                    </div>
                  )}
                </div>

                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-6 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors flex items-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Preferences
                </button>
              </div>
            </div>
          )}

          {/* D) Integrations */}
          {activeTab === 'integrations' && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold text-primary mb-6 flex items-center gap-2">
                <Plug className="w-5 h-5" />
                Connected Services
              </h2>

              <div className="space-y-3">
                {integrations.map((integration) => (
                  <div key={integration.id} className="flex items-center justify-between p-4 bg-black/20 rounded-lg">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-black/20 border border-white/10 flex items-center justify-center">
                        {integration.icon}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-primary">{integration.name}</div>
                        <div className="text-xs text-tertiary mt-1">
                          {integration.status === 'connected' ? (
                            <span className="flex items-center gap-1">
                              <CheckCircle className="w-3 h-3 text-success" />
                              Connected • Last sync: {integration.lastSync}
                            </span>
                          ) : (
                            <span className="flex items-center gap-1">
                              <XCircle className="w-3 h-3 text-tertiary" />
                              Not connected
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {integration.status === 'connected' ? (
                        <>
                          <button className="px-3 py-1.5 bg-white/5 text-primary rounded-lg hover:bg-white/10 transition-colors text-sm font-medium">
                            Refresh
                          </button>
                          {integration.canDisconnect && (
                            <button
                              onClick={() => {
                                const updated = integrations.map(i =>
                                  i.id === integration.id ? { ...i, status: 'disconnected' as const, lastSync: undefined } : i
                                );
                                setIntegrations(updated);
                              }}
                              className="px-3 py-1.5 bg-error/10 text-error rounded-lg hover:bg-error/20 transition-colors text-sm font-medium"
                            >
                              Disconnect
                            </button>
                          )}
                        </>
                      ) : (
                        <button
                          onClick={() => {
                            const updated = integrations.map(i =>
                              i.id === integration.id ? { ...i, status: 'connected' as const, lastSync: 'Just now' } : i
                            );
                            setIntegrations(updated);
                          }}
                          className="px-3 py-1.5 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors text-sm font-medium"
                        >
                          Connect
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* E) AI Preferences */}
          {activeTab === 'ai' && (
            <div className="space-y-6">
              {/* Quick AI Settings */}
              <div className="glass-card p-6">
                <h2 className="text-lg font-semibold text-primary mb-6 flex items-center gap-2">
                  <Brain className="w-5 h-5" />
                  AI Preferences
                </h2>

                <div className="space-y-6">
                  {/* Personality */}
                  <div>
                    <label className="block text-sm font-medium text-primary mb-3">Ospra Personality</label>
                    <div className="grid grid-cols-3 gap-3">
                      {['professional', 'friendly', 'concise'].map((style) => (
                        <button
                          key={style}
                          onClick={() => setAiPreferences({ ...aiPreferences, personality: style })}
                          className={`p-3 rounded-lg border-2 transition-all ${
                            aiPreferences.personality === style
                              ? 'border-cyan-500 bg-cyan-500/10'
                              : 'border-white/10 hover:border-white/20'
                          }`}
                        >
                          <div className="text-sm font-medium text-primary capitalize">{style}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Auto Features */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                      <div>
                        <div className="text-sm font-medium text-primary">Auto-Suggestions</div>
                        <p className="text-xs text-tertiary mt-1">Get AI-powered product recommendations</p>
                      </div>
                      <button
                        onClick={() => setAiPreferences({ ...aiPreferences, autoSuggestions: !aiPreferences.autoSuggestions })}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          aiPreferences.autoSuggestions ? 'bg-cyan-500' : 'bg-black/20'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            aiPreferences.autoSuggestions ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </div>

                    <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                      <div>
                        <div className="text-sm font-medium text-primary">Auto-Deploy AI Content</div>
                        <p className="text-xs text-tertiary mt-1">Automatically use AI-generated descriptions</p>
                      </div>
                      <button
                        onClick={() => setAiPreferences({ ...aiPreferences, autoDeployContent: !aiPreferences.autoDeployContent })}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          aiPreferences.autoDeployContent ? 'bg-cyan-500' : 'bg-black/20'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            aiPreferences.autoDeployContent ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </div>
                  </div>

                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="px-6 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors flex items-center gap-2"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Save Preferences
                  </button>
                </div>
              </div>

              {/* Full AI Provider Settings */}
              <AISettings onSave={(settings) => console.log('AI settings saved:', settings)} />
            </div>
          )}

          {/* F) Brand Voice */}
          {activeTab === 'brand' && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold text-primary mb-6 flex items-center gap-2">
                <MessageSquare className="w-5 h-5" />
                Brand Voice
              </h2>

              <div className="space-y-6">
                {/* Store Selector */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Store</label>
                  <select className="w-full px-4 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500">
                    <option>Oubon Shop (Primary)</option>
                    <option>Store 2</option>
                  </select>
                </div>

                {/* Brand Name */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Brand Name</label>
                  <input
                    type="text"
                    value={brandVoice.brandName}
                    onChange={(e) => setBrandVoice({ ...brandVoice, brandName: e.target.value })}
                    className="w-full px-4 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Brand Description</label>
                  <textarea
                    value={brandVoice.description}
                    onChange={(e) => setBrandVoice({ ...brandVoice, description: e.target.value })}
                    rows={3}
                    className="w-full px-4 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none"
                  />
                </div>

                {/* Tone */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-3">Brand Tone</label>
                  <div className="grid grid-cols-4 gap-3">
                    {['modern', 'luxury', 'playful', 'professional'].map((tone) => (
                      <button
                        key={tone}
                        onClick={() => setBrandVoice({ ...brandVoice, tone })}
                        className={`p-3 rounded-lg border-2 transition-all ${
                          brandVoice.tone === tone
                            ? 'border-cyan-500 bg-cyan-500/10'
                            : 'border-white/10 hover:border-white/20'
                        }`}
                      >
                        <div className="text-sm font-medium text-primary capitalize">{tone}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Target Audience */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Target Audience</label>
                  <input
                    type="text"
                    value={brandVoice.targetAudience}
                    onChange={(e) => setBrandVoice({ ...brandVoice, targetAudience: e.target.value })}
                    placeholder="e.g., Young professionals aged 25-35"
                    className="w-full px-4 py-2 rounded-lg border border-white/10 bg-black/20 text-primary focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                </div>

                {/* AI Preview */}
                <div className="p-4 bg-cyan-500/10 border border-cyan-500/50 rounded-lg">
                  <div className="text-sm font-medium text-cyan-400 mb-2">AI Output Preview</div>
                  <p className="text-sm text-tertiary">
                    Based on your brand voice, AI-generated content will have a <strong>{brandVoice.tone}</strong> tone,
                    targeting <strong>{brandVoice.targetAudience.toLowerCase()}</strong>.
                  </p>
                </div>

                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-6 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors flex items-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Brand Voice
                </button>
              </div>
            </div>
          )}

          {/* G) Team Members (Stratosphere Only) */}
          {activeTab === 'team' && (
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-primary flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  Team Members
                </h2>
                <button className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors flex items-center gap-2">
                  <UserPlus className="w-4 h-4" />
                  Invite Member
                </button>
              </div>

              {/* Usage */}
              <div className="mb-6 p-4 bg-cyan-500/10 border border-cyan-500/50 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-cyan-400">Team Seats</span>
                  <span className="text-sm font-medium text-cyan-400">
                    {subscription.usage.teamMembers.used} of {subscription.usage.teamMembers.limit} seats used
                  </span>
                </div>
              </div>

              {/* Members List */}
              <div className="space-y-3">
                {teamMembers.map((member) => (
                  <div key={member.id} className="flex items-center justify-between p-4 bg-black/20 rounded-lg">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-cyan-500/10 flex items-center justify-center text-sm font-bold text-cyan-400">
                        {member.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-primary">{member.name}</div>
                        <div className="text-xs text-tertiary">{member.email}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <select
                        value={member.role}
                        onChange={(e) => {
                          const updated = teamMembers.map(m =>
                            m.id === member.id ? { ...m, role: e.target.value as TeamMember['role'] } : m
                          );
                          setTeamMembers(updated);
                        }}
                        className="px-3 py-1.5 rounded-lg border border-white/10 bg-black/20 text-primary text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      >
                        <option value="admin">Admin</option>
                        <option value="editor">Editor</option>
                        <option value="viewer">Viewer</option>
                      </select>
                      {member.role !== 'admin' && (
                        <button className="p-2 text-error hover:bg-error/10 rounded-lg transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* H) API Access (Soar+ Only) */}
          {activeTab === 'api' && (
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold text-primary mb-6 flex items-center gap-2">
                <Key className="w-5 h-5" />
                API Access
              </h2>

              <div className="space-y-6">
                {/* API Key */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">API Key</label>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 relative">
                      <input
                        type={showApiKey ? 'text' : 'password'}
                        value={apiKey}
                        readOnly
                        className="w-full px-4 py-2 pr-10 rounded-lg border border-white/10 bg-black/20 font-mono text-sm focus:outline-none text-primary"
                      />
                      <button
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-tertiary hover:text-primary"
                      >
                        {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(apiKey);
                        alert('API key copied!');
                      }}
                      className="px-4 py-2 bg-white/10 text-primary rounded-lg hover:bg-white/20 transition-colors"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        if (confirm('Regenerate API key? Your old key will stop working immediately.')) {
                          setApiKey('ospra_sk_' + Math.random().toString(36).substring(2, 40));
                          setApiKeyRegenerated(true);
                          setTimeout(() => setApiKeyRegenerated(false), 3000);
                        }
                      }}
                      className="px-4 py-2 bg-error/10 text-error rounded-lg hover:bg-error/20 transition-colors"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                  {apiKeyRegenerated && (
                    <p className="text-sm text-success mt-2 flex items-center gap-1">
                      <Check className="w-4 h-4" />
                      API key regenerated successfully
                    </p>
                  )}
                </div>

                {/* Usage Stats */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-black/20 rounded-lg">
                    <div className="text-xs text-tertiary mb-1">Requests (30d)</div>
                    <div className="text-2xl font-bold text-primary">12,450</div>
                  </div>
                  <div className="p-4 bg-black/20 rounded-lg">
                    <div className="text-xs text-tertiary mb-1">Avg Response</div>
                    <div className="text-2xl font-bold text-primary">245ms</div>
                  </div>
                  <div className="p-4 bg-black/20 rounded-lg">
                    <div className="text-xs text-tertiary mb-1">Errors</div>
                    <div className="text-2xl font-bold text-primary">12</div>
                  </div>
                </div>

                {/* Documentation */}
                <div className="p-4 bg-cyan-500/10 border border-cyan-500/50 rounded-lg">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-cyan-400 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-cyan-400 mb-1">API Documentation</p>
                      <p className="text-xs text-cyan-300 mb-3">
                        Learn how to integrate Ospra Intelligence into your applications
                      </p>
                      <a
                        href="https://docs.ospra.io/api"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-sm font-medium text-cyan-400 hover:underline"
                      >
                        View Documentation
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* I) Data & Privacy */}
          {activeTab === 'privacy' && (
            <div className="space-y-6">
              {/* Export Data */}
              <div className="glass-card p-6">
                <h2 className="text-lg font-semibold text-primary mb-4 flex items-center gap-2">
                  <Database className="w-5 h-5" />
                  Export Your Data
                </h2>
                <p className="text-sm text-tertiary mb-4">
                  Download all your data including products, analytics, and settings in JSON format
                </p>
                <button className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors flex items-center gap-2">
                  <Download className="w-4 h-4" />
                  Export Data
                </button>
              </div>

              {/* Privacy Settings */}
              <div className="glass-card p-6">
                <h2 className="text-lg font-semibold text-primary mb-4 flex items-center gap-2">
                  <Shield className="w-5 h-5" />
                  Privacy Settings
                </h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                    <div>
                      <div className="text-sm font-medium text-primary">Analytics Tracking</div>
                      <p className="text-xs text-tertiary mt-1">Help us improve by sharing usage data</p>
                    </div>
                    <button className="relative inline-flex h-6 w-11 items-center rounded-full bg-cyan-500">
                      <span className="inline-block h-4 w-4 transform rounded-full bg-white translate-x-6" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Delete Account */}
              <div className="glass-card p-6 border-2 border-error/50">
                <h2 className="text-lg font-semibold text-error mb-4 flex items-center gap-2">
                  <Trash2 className="w-5 h-5" />
                  Delete Account
                </h2>
                <p className="text-sm text-tertiary mb-4">
                  Permanently delete your account and all associated data. This action cannot be undone.
                </p>
                <button className="px-4 py-2 bg-error text-white rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2">
                  <Trash2 className="w-4 h-4" />
                  Delete Account
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
