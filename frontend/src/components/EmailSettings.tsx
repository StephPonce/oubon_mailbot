import React, { useState, useEffect } from 'react';
import {
  Mail,
  Check,
  X,
  AlertCircle,
  Loader2,
  ExternalLink,
  Trash2,
  Star,
  RefreshCw
} from 'lucide-react';
import { GlassPanel } from './GlassPanel';

// Types
interface EmailAccount {
  id: number;
  provider: string;
  email_address: string;
  is_active: boolean;
  is_primary: boolean;
  last_synced: string | null;
  sync_status: string;
  created_at: string;
}

interface EmailProvider {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string;
}

// Email Provider configurations with proper branding
const EMAIL_PROVIDERS: EmailProvider[] = [
  {
    id: 'gmail',
    name: 'Gmail',
    icon: 'https://cdn.simpleicons.org/gmail/EA4335',
    color: 'red',
    description: 'Google workspace email automation'
  },
  {
    id: 'outlook',
    name: 'Microsoft Outlook',
    icon: 'https://logo.clearbit.com/outlook.com',
    color: 'blue',
    description: 'Office 365 and Outlook.com'
  },
  {
    id: 'yahoo',
    name: 'Yahoo Mail',
    icon: 'https://logo.clearbit.com/yahoo.com',
    color: 'purple',
    description: 'Yahoo email integration'
  },
  {
    id: 'icloud',
    name: 'iCloud Mail',
    icon: 'https://cdn.simpleicons.org/icloud/3693F3',
    color: 'blue',
    description: 'Apple iCloud email service'
  },
  {
    id: 'protonmail',
    name: 'ProtonMail',
    icon: 'https://cdn.simpleicons.org/protonmail/6D4AFF',
    color: 'purple',
    description: 'Secure encrypted email'
  },
  {
    id: 'zoho',
    name: 'Zoho Mail',
    icon: 'https://cdn.simpleicons.org/zoho/C8202E',
    color: 'orange',
    description: 'Zoho business email'
  }
];

const EmailSettings: React.FC = () => {
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const userId = 1; // TODO: Get from auth context

  // Fetch connected accounts
  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`http://localhost:8001/api/email-oauth/accounts?user_id=${userId}`);

      if (!response.ok) {
        throw new Error('Failed to fetch email accounts');
      }

      const data = await response.json();
      setAccounts(data);
    } catch (err) {
      console.error('Error fetching accounts:', err);
      setError('Failed to load email accounts. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Connect new email account
  const handleConnect = async (provider: string) => {
    setConnecting(provider);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8001/api/email-oauth/${provider}/connect?user_id=${userId}`
      );

      if (!response.ok) {
        throw new Error('Failed to initiate OAuth flow');
      }

      const data = await response.json();

      // Open OAuth URL in new window
      window.open(data.authorization_url, '_blank', 'width=600,height=700');

      // Poll for account connection (in production, use webhooks or better mechanism)
      const pollInterval = setInterval(async () => {
        await fetchAccounts();
      }, 3000);

      // Stop polling after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setConnecting(null);
      }, 120000);

    } catch (err) {
      console.error('Error connecting account:', err);
      setError(`Failed to connect ${provider} account. Please try again.`);
      setConnecting(null);
    }
  };

  // Delete account
  const handleDeleteAccount = async (accountId: number) => {
    if (!confirm('Are you sure you want to permanently delete this email account? This action cannot be undone.')) {
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8001/api/email-oauth/accounts/${accountId}?user_id=${userId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        throw new Error('Failed to delete account');
      }

      await fetchAccounts();
    } catch (err) {
      console.error('Error deleting account:', err);
      setError('Failed to delete account. Please try again.');
    }
  };

  // Set primary account
  const handleSetPrimary = async (accountId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8001/api/email-oauth/accounts/${accountId}/set-primary?user_id=${userId}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to set primary account');
      }

      await fetchAccounts();
    } catch (err) {
      console.error('Error setting primary:', err);
      setError('Failed to set primary account. Please try again.');
    }
  };

  // Get status badge
  const getStatusBadge = (status: string, isActive: boolean) => {
    if (!isActive) {
      return (
        <span className="px-2 py-1 bg-gray-500/20 text-gray-600 text-xs font-medium rounded-full flex items-center gap-1">
          <X className="w-3 h-3" />
          Disconnected
        </span>
      );
    }

    if (status === 'active') {
      return (
        <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs font-medium rounded-full flex items-center gap-1">
          <Check className="w-3 h-3" />
          Active
        </span>
      );
    }

    return (
      <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs font-medium rounded-full flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {status}
        </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-12">
        {/* Header */}
        <GlassPanel depth={80} delay={0.2}>
          <h1 className="text-4xl font-light text-gray-900 mb-3">
            Email Account Settings
          </h1>
          <p className="text-lg text-gray-600">
            Connect and manage your email accounts for automated email processing
          </p>
        </GlassPanel>

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-5 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-red-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-base font-medium text-red-400">{error}</p>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-300 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Connected Accounts */}
      <GlassPanel depth={60} delay={0.3}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-light text-gray-900 flex items-center gap-3">
            <Mail className="w-6 h-6 text-blue-400" />
            Connected Email Accounts
          </h2>
          <button
            onClick={fetchAccounts}
            disabled={loading}
            className="p-2.5 text-gray-600 hover:text-gray-900 hover:bg-gray-200/50 rounded-lg transition"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-12">
            <Mail className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-600">No email accounts connected yet</p>
            <p className="text-sm text-gray-500 mt-1">
              Connect an account below to get started
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {accounts.map((account) => {
              const provider = EMAIL_PROVIDERS.find(p => p.id === account.provider);

              return (
                <div
                  key={account.id}
                  className="bg-gray-100 rounded-xl border border-gray-200 p-5 flex items-center justify-between hover:bg-gray-200/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    {/* Provider Icon */}
                    <div className="w-12 h-12 flex-shrink-0 bg-white rounded-lg p-2 flex items-center justify-center">
                      {provider?.icon ? (
                        <img src={provider.icon} alt={provider.name} className="w-full h-full object-contain" />
                      ) : (
                        <Mail className="w-6 h-6 text-gray-600" />
                      )}
                    </div>

                    {/* Account Info */}
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-gray-900">{account.email_address}</p>
                        {account.is_primary && (
                          <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs font-bold rounded-full flex items-center gap-1">
                            <Star className="w-3 h-3" />
                            Primary
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <p className="text-sm text-gray-500">{provider?.name || account.provider}</p>
                        <span className="text-gray-600">•</span>
                        {getStatusBadge(account.sync_status, account.is_active)}
                      </div>
                      {account.last_synced && (
                        <p className="text-xs text-gray-500 mt-1">
                          Last synced: {new Date(account.last_synced).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {!account.is_primary && account.is_active && (
                      <button
                        onClick={() => handleSetPrimary(account.id)}
                        className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded hover:bg-yellow-500/30 transition text-sm font-medium flex items-center gap-1"
                      >
                        <Star className="w-3 h-3" />
                        Set Primary
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteAccount(account.id)}
                      className="p-2 text-red-400 hover:bg-red-500/10 rounded transition"
                      title="Delete Account"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </GlassPanel>

      {/* Connect New Account */}
      <GlassPanel depth={60} delay={0.4}>
        <h2 className="text-xl font-light text-gray-900 mb-6 flex items-center gap-3">
          <ExternalLink className="w-6 h-6 text-blue-400" />
          Connect New Email Account
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {EMAIL_PROVIDERS.map((provider) => (
            <button
              key={provider.id}
              onClick={() => handleConnect(provider.id)}
              disabled={connecting === provider.id}
              className={`group relative p-6 rounded-xl border-2 text-left transition-all ${
                connecting === provider.id
                  ? 'border-blue-500/50 bg-blue-500/10'
                  : 'border-gray-200 bg-gray-100 hover:border-gray-600 hover:bg-white/50/50'
              } disabled:cursor-not-allowed`}
            >
              {/* Provider Icon & Name */}
              <div className="flex flex-col items-center text-center mb-4">
                <div className="w-16 h-16 mb-4 bg-white rounded-xl p-3 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                  <img src={provider.icon} alt={provider.name} className="w-full h-full object-contain" />
                </div>
                <h3 className="font-light text-gray-900 text-lg mb-1">{provider.name}</h3>
                <p className="text-sm text-gray-600">{provider.description}</p>
              </div>

              {/* Connect Button */}
              <div className="mt-4 pt-4 border-t border-gray-200">
                {connecting === provider.id ? (
                  <div className="flex items-center justify-center gap-2 text-blue-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm font-medium">Connecting...</span>
                  </div>
                ) : (
                  <div className="flex items-center justify-center gap-2 text-gray-600 group-hover:text-blue-400 transition-colors">
                    <ExternalLink className="w-4 h-4" />
                    <span className="text-sm font-medium">Connect Account</span>
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* OAuth Instructions */}
        <div className="mt-6 bg-blue-500/10 border border-blue-500/50 rounded-xl p-5 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-base font-semibold text-blue-400 mb-2">Secure OAuth Connection</p>
            <p className="text-sm text-gray-600">
              You'll be redirected to your email provider to grant access. Your credentials are never stored by us - we only receive secure OAuth tokens.
            </p>
          </div>
        </div>
      </GlassPanel>

      {/* Feature Info */}
      <GlassPanel depth={60} delay={0.5}>
        <h2 className="text-xl font-light text-gray-900 mb-6">What you can do with connected accounts:</h2>
        <ul className="space-y-3 text-gray-600">
          <li className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-400" />
            Automated email classification and routing
          </li>
          <li className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-400" />
            AI-powered auto-replies to customer inquiries
          </li>
          <li className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-400" />
            Priority alerts for VIP customers and urgent matters
          </li>
          <li className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-400" />
            Order tracking integration and automated status updates
          </li>
        </ul>
      </GlassPanel>
    </div>
  </div>
  );
};

export default EmailSettings;
