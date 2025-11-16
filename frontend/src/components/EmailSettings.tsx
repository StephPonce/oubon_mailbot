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

// Email Provider configurations
const EMAIL_PROVIDERS: EmailProvider[] = [
  {
    id: 'gmail',
    name: 'Gmail',
    icon: '📧',
    color: 'red',
    description: 'Connect your Gmail account for email automation'
  },
  {
    id: 'outlook',
    name: 'Microsoft Outlook',
    icon: '📨',
    color: 'blue',
    description: 'Connect your Outlook/Office 365 account'
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
      const response = await fetch(`http://localhost:8000/api/email-oauth/accounts?user_id=${userId}`);

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
        `http://localhost:8000/api/email-oauth/${provider}/connect?user_id=${userId}`
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

  // Disconnect account
  const handleDisconnect = async (accountId: number) => {
    if (!confirm('Are you sure you want to disconnect this email account?')) {
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8000/api/email-oauth/accounts/${accountId}?user_id=${userId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        throw new Error('Failed to disconnect account');
      }

      await fetchAccounts();
    } catch (err) {
      console.error('Error disconnecting account:', err);
      setError('Failed to disconnect account. Please try again.');
    }
  };

  // Set primary account
  const handleSetPrimary = async (accountId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/email-oauth/accounts/${accountId}/set-primary?user_id=${userId}`,
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

  // Get provider color class
  const getProviderColorClass = (color: string, type: 'bg' | 'text' | 'border') => {
    const colors: Record<string, Record<string, string>> = {
      red: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/50' },
      blue: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/50' }
    };
    return colors[color]?.[type] || colors.blue[type];
  };

  // Get status badge
  const getStatusBadge = (status: string, isActive: boolean) => {
    if (!isActive) {
      return (
        <span className="px-2 py-1 bg-gray-500/20 text-gray-400 text-xs font-medium rounded-full flex items-center gap-1">
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
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
          <Mail className="w-8 h-8 text-blue-400" />
          Email Account Settings
        </h1>
        <p className="text-gray-400">
          Connect and manage your email accounts for automated email processing
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-400">{error}</p>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-300"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Connected Accounts */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Mail className="w-5 h-5 text-blue-400" />
            Connected Email Accounts
          </h2>
          <button
            onClick={fetchAccounts}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-12">
            <Mail className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400">No email accounts connected yet</p>
            <p className="text-sm text-gray-500 mt-1">
              Connect an account below to get started
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {accounts.map((account) => {
              const provider = EMAIL_PROVIDERS.find(p => p.id === account.provider);

              return (
                <div
                  key={account.id}
                  className="bg-gray-900/50 rounded-lg border border-gray-700 p-4 flex items-center justify-between"
                >
                  <div className="flex items-center gap-4">
                    {/* Provider Icon */}
                    <div className="text-3xl">
                      {provider?.icon || '📧'}
                    </div>

                    {/* Account Info */}
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-white">{account.email_address}</p>
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
                      onClick={() => handleDisconnect(account.id)}
                      className="p-2 text-red-400 hover:bg-red-500/10 rounded transition"
                      title="Disconnect"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Connect New Account */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <ExternalLink className="w-5 h-5 text-blue-400" />
          Connect New Email Account
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {EMAIL_PROVIDERS.map((provider) => (
            <button
              key={provider.id}
              onClick={() => handleConnect(provider.id)}
              disabled={connecting === provider.id}
              className={`relative p-5 rounded-lg border-2 text-left transition-all ${
                connecting === provider.id
                  ? 'border-blue-500/50 bg-blue-500/10'
                  : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'
              } disabled:cursor-not-allowed`}
            >
              {/* Provider Icon & Name */}
              <div className="flex items-start gap-3 mb-3">
                <div className="text-3xl">{provider.icon}</div>
                <div>
                  <h3 className="font-bold text-white text-lg">{provider.name}</h3>
                  <p className="text-sm text-gray-400 mt-1">{provider.description}</p>
                </div>
              </div>

              {/* Connect Button */}
              <div className="mt-4">
                {connecting === provider.id ? (
                  <div className="flex items-center gap-2 text-blue-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm font-medium">Connecting...</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-gray-400">
                    <ExternalLink className="w-4 h-4" />
                    <span className="text-sm font-medium">Connect Account</span>
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* OAuth Instructions */}
        <div className="mt-4 bg-blue-500/10 border border-blue-500/50 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-blue-400 mb-1">Secure OAuth Connection</p>
            <p className="text-xs text-gray-400">
              You'll be redirected to your email provider to grant access. Your credentials are never stored by us - we only receive secure OAuth tokens.
            </p>
          </div>
        </div>
      </div>

      {/* Feature Info */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 className="text-lg font-bold text-white mb-4">What you can do with connected accounts:</h2>
        <ul className="space-y-2 text-gray-300">
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
      </div>
    </div>
  );
};

export default EmailSettings;
