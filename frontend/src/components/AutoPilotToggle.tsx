/**
 * Auto-Pilot Toggle Component
 *
 * Implements GROK RECOMMENDATION #7: Auto-Pilot Mode Toggle
 *
 * Features:
 * - Toggle auto-pilot on/off
 * - Configure global confidence threshold
 * - Set daily execution limits and spend caps
 * - Configure per-action-type rules
 * - View real-time statistics (today's executions, remaining limit)
 * - See skip breakdown (why actions weren't auto-executed)
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Zap,
  ZapOff,
  Settings,
  ChevronDown,
  ChevronUp,
  Shield,
  TrendingUp,
  DollarSign,
  CheckCircle,
  AlertTriangle,
  Info
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api';

interface AutoPilotStatus {
  enabled: boolean;
  threshold: number;
  today: {
    executed: number;
    skipped: number;
    remaining_limit: number;
  };
  week: {
    executed: number;
  };
  skip_breakdown: Record<string, number>;
  settings: {
    auto_pilot_enabled: boolean;
    auto_pilot_threshold: number;
    auto_pilot_rules: Record<string, any>;
    notify_on_auto_execute: boolean;
    daily_summary_email: boolean;
    daily_auto_execute_limit: number;
    max_auto_spend: number;
  };
}

interface AutoPilotToggleProps {
  className?: string;
  onStatusChange?: (enabled: boolean) => void;
}

export function AutoPilotToggle({ className, onStatusChange }: AutoPilotToggleProps) {
  const [status, setStatus] = useState<AutoPilotStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [saving, setSaving] = useState(false);

  // Local state for settings form
  const [threshold, setThreshold] = useState(85);
  const [dailyLimit, setDailyLimit] = useState(20);
  const [maxSpend, setMaxSpend] = useState(500);
  const [notifyOnExecute, setNotifyOnExecute] = useState(true);
  const [dailySummary, setDailySummary] = useState(true);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.get<AutoPilotStatus>('/auto-pilot/status');
      setStatus(data);

      // Update form with current settings
      if (data.settings) {
        setThreshold(data.settings.auto_pilot_threshold);
        setDailyLimit(data.settings.daily_auto_execute_limit);
        setMaxSpend(data.settings.max_auto_spend);
        setNotifyOnExecute(data.settings.notify_on_auto_execute);
        setDailySummary(data.settings.daily_summary_email);
      }
    } catch (err) {
      console.error('Failed to load auto-pilot status:', err);
      setError('Failed to load auto-pilot status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const toggleAutoPilot = async () => {
    if (!status) return;

    try {
      setSaving(true);
      const newEnabled = !status.enabled;

      await apiClient.post('/auto-pilot/toggle', {
        enabled: newEnabled
      });

      setStatus(prev => prev ? { ...prev, enabled: newEnabled } : null);
      onStatusChange?.(newEnabled);
    } catch (err) {
      console.error('Failed to toggle auto-pilot:', err);
      setError('Failed to toggle auto-pilot');
    } finally {
      setSaving(false);
    }
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setError(null);

      await apiClient.put('/auto-pilot/settings', {
        auto_pilot_threshold: threshold,
        daily_auto_execute_limit: dailyLimit,
        max_auto_spend: maxSpend,
        notify_on_auto_execute: notifyOnExecute,
        daily_summary_email: dailySummary
      });

      // Refresh status to get updated data
      await fetchStatus();
      setShowSettings(false);
    } catch (err) {
      console.error('Failed to save settings:', err);
      setError('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn('bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700 p-6', className)}
      >
        <div className="flex items-center space-x-3">
          <div className="animate-pulse h-8 w-8 bg-gray-700 rounded-lg" />
          <div className="flex-1 space-y-2">
            <div className="animate-pulse h-5 w-32 bg-gray-700 rounded" />
            <div className="animate-pulse h-4 w-48 bg-gray-700 rounded" />
          </div>
        </div>
      </motion.div>
    );
  }

  if (error || !status) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn('bg-red-900/20 backdrop-blur-sm rounded-lg border border-red-500/30 p-6', className)}
      >
        <div className="flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <p className="text-red-300">{error || 'Failed to load auto-pilot status'}</p>
        </div>
      </motion.div>
    );
  }

  const getSkipReasonLabel = (reason: string): string => {
    const labels: Record<string, string> = {
      'auto_pilot_disabled': 'Auto-pilot disabled',
      'action_type_blocked': 'Action type blocked',
      'action_type_disabled': 'Action type disabled',
      'daily_limit_reached': 'Daily limit reached',
      'spend_limit_reached': 'Spend limit reached'
    };

    if (reason.startsWith('below_threshold_')) {
      return 'Below confidence threshold';
    }

    return labels[reason] || reason;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700', className)}
    >
      {/* Header */}
      <div className="p-6 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={cn(
              'w-10 h-10 rounded-lg flex items-center justify-center',
              status.enabled ? 'bg-green-500/100/20' : 'bg-gray-700'
            )}>
              {status.enabled ? (
                <Zap className="w-5 h-5 text-green-400" />
              ) : (
                <ZapOff className="w-5 h-5 text-tertiary" />
              )}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Auto-Pilot Mode</h3>
              <p className="text-sm text-tertiary">
                {status.enabled
                  ? `Active - Auto-executing actions ≥${status.threshold}% confidence`
                  : 'Disabled - All actions require manual approval'
                }
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5 text-gray-300" />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={toggleAutoPilot}
              disabled={saving}
              className={cn(
                'px-6 py-2 rounded-lg font-medium transition-colors',
                status.enabled
                  ? 'bg-red-500/100/20 text-red-300 hover:bg-red-500/100/30 border border-red-500/30'
                  : 'bg-green-500/100/20 text-green-300 hover:bg-green-500/100/30 border border-green-500/30'
              )}
            >
              {saving ? 'Updating...' : status.enabled ? 'Disable' : 'Enable'}
            </motion.button>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="p-6 grid grid-cols-3 gap-4 border-b border-gray-700">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 text-green-400" />
            <p className="text-sm text-tertiary">Auto-Executed Today</p>
          </div>
          <p className="text-2xl font-bold text-white">{status.today.executed}</p>
        </div>

        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            <p className="text-sm text-tertiary">Skipped Today</p>
          </div>
          <p className="text-2xl font-bold text-white">{status.today.skipped}</p>
        </div>

        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-blue-400" />
            <p className="text-sm text-tertiary">Remaining Limit</p>
          </div>
          <p className="text-2xl font-bold text-white">{status.today.remaining_limit}</p>
        </div>
      </div>

      {/* Skip Breakdown */}
      {status.today.skipped > 0 && Object.keys(status.skip_breakdown).length > 0 && (
        <div className="p-6 border-b border-gray-700">
          <h4 className="text-sm font-medium text-gray-300 mb-3">Why Actions Were Skipped</h4>
          <div className="space-y-2">
            {Object.entries(status.skip_breakdown).map(([reason, count]) => (
              <div key={reason} className="flex items-center justify-between text-sm">
                <span className="text-tertiary">{getSkipReasonLabel(reason)}</span>
                <span className="text-white font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Settings Panel */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-6 space-y-6 bg-gray-900/50">
              <div className="flex items-center justify-between">
                <h4 className="text-lg font-semibold text-white">Auto-Pilot Settings</h4>
                <Info className="w-4 h-4 text-tertiary" />
              </div>

              {/* Confidence Threshold */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-300">
                    Confidence Threshold
                  </label>
                  <span className="text-sm text-white font-mono">{threshold}%</span>
                </div>
                <input
                  type="range"
                  min="50"
                  max="100"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <p className="text-xs text-tertiary">
                  Actions with confidence ≥ {threshold}% will be auto-executed
                </p>
              </div>

              {/* Daily Limit */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-300">
                    Daily Execution Limit
                  </label>
                  <span className="text-sm text-white font-mono">{dailyLimit}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={dailyLimit}
                  onChange={(e) => setDailyLimit(Number(e.target.value))}
                  className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <p className="text-xs text-tertiary">
                  Maximum number of actions to auto-execute per day
                </p>
              </div>

              {/* Max Spend */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-300">
                    Daily Spend Limit
                  </label>
                  <span className="text-sm text-white font-mono">${maxSpend}</span>
                </div>
                <input
                  type="number"
                  min="0"
                  step="50"
                  value={maxSpend}
                  onChange={(e) => setMaxSpend(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-tertiary">
                  Maximum $ impact from auto-executed actions per day
                </p>
              </div>

              {/* Notification Settings */}
              <div className="space-y-3">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifyOnExecute}
                    onChange={(e) => setNotifyOnExecute(e.target.checked)}
                    className="w-4 h-4 text-blue-500 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-300">Notify me when actions are auto-executed</span>
                </label>

                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={dailySummary}
                    onChange={(e) => setDailySummary(e.target.checked)}
                    className="w-4 h-4 text-blue-500 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-300">Send me daily summary emails</span>
                </label>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-700">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setShowSettings(false)}
                  className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
                >
                  Cancel
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={saveSettings}
                  disabled={saving}
                  className="px-6 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white font-medium transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Settings'}
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
