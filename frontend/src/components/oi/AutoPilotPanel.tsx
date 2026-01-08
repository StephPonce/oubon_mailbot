/**
 * AUTO-PILOT CONTROL PANEL
 * ========================
 * 
 * UI for managing Oi's autonomous operation mode.
 * 
 * Features:
 * - Enable/disable/pause auto-pilot
 * - Configure per-action-type thresholds
 * - View recent auto-executed actions
 * - Undo actions within the undo window
 * - Apply preset configurations
 */

import React, { useState, useEffect, useCallback } from 'react';

// Types
interface ActionTypeConfig {
  enabled: boolean;
  min_confidence: number;
  max_per_day: number;
  max_value: number | null;
  require_review_above: number | null;
  cooldown_minutes: number;
}

interface AutoPilotConfig {
  user_id: number;
  status: 'enabled' | 'disabled' | 'paused' | 'safety_stop';
  max_daily_spend: number;
  max_daily_actions: number;
  action_configs: Record<string, ActionTypeConfig>;
  undo_window_hours: number;
  notify_on_action: boolean;
  notify_on_limit: boolean;
  daily_summary: boolean;
}

interface AutoPilotAction {
  action_id: string;
  action_type: string;
  title: string;
  description: string;
  confidence: number;
  executed_at: string;
  success: boolean;
  can_undo: boolean;
  undo_deadline: string | null;
  undone: boolean;
  monetary_value: number;
}

interface DailySummary {
  date: string;
  status: string;
  actions_executed: number;
  successful: number;
  failed: number;
  undone: number;
  total_spend: number;
  limits: {
    daily_actions: string;
    daily_spend: string;
  };
  remaining: {
    actions: number;
    spend: number;
  };
}

// Action type display info
const ACTION_TYPE_INFO: Record<string, { label: string; icon: string; description: string }> = {
  deploy_product: {
    label: 'Deploy Products',
    icon: '[START]',
    description: 'Automatically publish products to your store'
  },
  pause_ad: {
    label: 'Pause Ads',
    icon: '[PAUSE]',
    description: 'Pause underperforming ad campaigns'
  },
  resume_ad: {
    label: 'Resume Ads',
    icon: '',
    description: 'Resume paused ad campaigns'
  },
  increase_ad_budget: {
    label: 'Increase Ad Budget',
    icon: '[TREND]',
    description: 'Boost budget on performing ads'
  },
  decrease_ad_budget: {
    label: 'Decrease Ad Budget',
    icon: '[DECLINE]',
    description: 'Reduce budget on underperforming ads'
  },
  adjust_price: {
    label: 'Adjust Prices',
    icon: '[PRICE]',
    description: 'Modify product pricing'
  },
  drop_product: {
    label: 'Drop Products',
    icon: '',
    description: 'Remove underperforming products'
  },
  reorder_inventory: {
    label: 'Reorder Inventory',
    icon: '[PACKAGE]',
    description: 'Automatically restock products'
  }
};

// Status badge component
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const styles: Record<string, string> = {
    enabled: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    disabled: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    paused: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    safety_stop: 'bg-red-500/20 text-red-400 border-red-500/30'
  };

  const labels: Record<string, string> = {
    enabled: ' ENABLED',
    disabled: ' DISABLED',
    paused: ' PAUSED',
    safety_stop: ' SAFETY STOP'
  };

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium border ${styles[status] || styles.disabled}`}>
      {labels[status] || status}
    </span>
  );
};

// Confidence slider component
const ConfidenceSlider: React.FC<{
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}> = ({ value, onChange, disabled }) => {
  const getColor = (v: number) => {
    if (v >= 0.9) return 'bg-emerald-500';
    if (v >= 0.8) return 'bg-green-500';
    if (v >= 0.7) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min="0.5"
        max="0.99"
        step="0.01"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        disabled={disabled}
        className="flex-1 h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
      />
      <span className={`px-2 py-0.5 rounded text-sm font-mono ${getColor(value)} text-white`}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
};

// Action type config card
const ActionTypeCard: React.FC<{
  actionType: string;
  config: ActionTypeConfig;
  onUpdate: (updates: Partial<ActionTypeConfig>) => void;
}> = ({ actionType, config, onUpdate }) => {
  const info = ACTION_TYPE_INFO[actionType] || { label: actionType, icon: '[CONFIG]', description: '' };

  return (
    <div className={`
      p-4 rounded-xl border transition-all duration-300
      ${config.enabled 
        ? 'bg-white/5 border-emerald-500/30 shadow-lg shadow-emerald-500/5' 
        : 'bg-white/[0.02] border-white/10 opacity-60'
      }
    `}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{info.icon}</span>
          <span className="font-medium text-white">{info.label}</span>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => onUpdate({ enabled: e.target.checked })}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500"></div>
        </label>
      </div>

      <p className="text-sm text-white/50 mb-4">{info.description}</p>

      {/* Config fields */}
      <div className="space-y-3">
        {/* Confidence threshold */}
        <div>
          <label className="text-xs text-white/60 block mb-1">Min Confidence</label>
          <ConfidenceSlider
            value={config.min_confidence}
            onChange={(v) => onUpdate({ min_confidence: v })}
            disabled={!config.enabled}
          />
        </div>

        {/* Max per day */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-white/60">Max/Day:</label>
          <input
            type="number"
            min="1"
            max="100"
            value={config.max_per_day}
            onChange={(e) => onUpdate({ max_per_day: parseInt(e.target.value) })}
            disabled={!config.enabled}
            className="w-16 px-2 py-1 bg-white/5 border border-white/10 rounded text-sm text-white disabled:opacity-50"
          />
        </div>

        {/* Max value (if applicable) */}
        {config.max_value !== null && (
          <div className="flex items-center gap-3">
            <label className="text-xs text-white/60">Max Value:</label>
            <div className="flex items-center">
              <span className="text-white/40 mr-1">$</span>
              <input
                type="number"
                min="0"
                value={config.max_value || 0}
                onChange={(e) => onUpdate({ max_value: parseFloat(e.target.value) })}
                disabled={!config.enabled}
                className="w-20 px-2 py-1 bg-white/5 border border-white/10 rounded text-sm text-white disabled:opacity-50"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Recent action item
const ActionItem: React.FC<{
  action: AutoPilotAction;
  onUndo: (actionId: string) => void;
}> = ({ action, onUndo }) => {
  const info = ACTION_TYPE_INFO[action.action_type] || { icon: '[CONFIG]', label: action.action_type };
  const timeAgo = getTimeAgo(action.executed_at);

  return (
    <div className={`
      p-3 rounded-lg border transition-all
      ${action.undone 
        ? 'bg-white/[0.02] border-white/5 opacity-50' 
        : action.success 
          ? 'bg-emerald-500/5 border-emerald-500/20'
          : 'bg-red-500/5 border-red-500/20'
      }
    `}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <span className="text-lg">{info.icon}</span>
          <div>
            <div className="font-medium text-white text-sm">
              {action.title}
              {action.undone && <span className="ml-2 text-amber-400">(Undone)</span>}
            </div>
            <div className="text-xs text-white/50 mt-0.5">{timeAgo}</div>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <span className={`
            text-xs px-2 py-0.5 rounded
            ${action.success ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}
          `}>
            {(action.confidence * 100).toFixed(0)}%
          </span>
          
          {action.can_undo && !action.undone && (
            <button
              onClick={() => onUndo(action.action_id)}
              className="text-xs px-2 py-1 bg-amber-500/20 text-amber-400 rounded hover:bg-amber-500/30 transition-colors"
            >
              Undo
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

// Helper function for time ago
function getTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

// Main Auto-Pilot Panel Component
export const AutoPilotPanel: React.FC<{
  userId?: number;
  className?: string;
}> = ({ userId = 1, className = '' }) => {
  const [config, setConfig] = useState<AutoPilotConfig | null>(null);
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [recentActions, setRecentActions] = useState<AutoPilotAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'actions' | 'history'>('overview');

  // Fetch config and data
  const fetchData = useCallback(async () => {
    try {
      const [configRes, summaryRes, actionsRes] = await Promise.all([
        fetch(`/api/autopilot/config?user_id=${userId}`),
        fetch(`/api/autopilot/summary?user_id=${userId}`),
        fetch(`/api/autopilot/actions?user_id=${userId}&limit=10`)
      ]);

      const configData = await configRes.json();
      const summaryData = await summaryRes.json();
      const actionsData = await actionsRes.json();

      if (configData.success) setConfig(configData.config);
      if (summaryData.success) setSummary(summaryData.summary);
      if (actionsData.success) setRecentActions(actionsData.actions);
    } catch (error) {
      console.error('Failed to fetch auto-pilot data:', error);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  // Toggle auto-pilot
  const toggleAutoPilot = async () => {
    if (!config) return;
    
    const endpoint = config.status === 'enabled' ? 'disable' : 'enable';
    try {
      const res = await fetch(`/api/autopilot/${endpoint}?user_id=${userId}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setConfig({ ...config, status: data.status });
      }
    } catch (error) {
      console.error('Failed to toggle auto-pilot:', error);
    }
  };

  // Apply preset
  const applyPreset = async (preset: 'conservative' | 'balanced' | 'aggressive') => {
    try {
      const res = await fetch(`/api/autopilot/presets/${preset}?user_id=${userId}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setConfig(data.config);
      }
    } catch (error) {
      console.error('Failed to apply preset:', error);
    }
  };

  // Update action config
  const updateActionConfig = async (actionType: string, updates: Partial<ActionTypeConfig>) => {
    if (!config) return;

    try {
      const res = await fetch(`/api/autopilot/action/${actionType}?user_id=${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      const data = await res.json();
      if (data.success) {
        setConfig({
          ...config,
          action_configs: {
            ...config.action_configs,
            [actionType]: { ...config.action_configs[actionType], ...data.config }
          }
        });
      }
    } catch (error) {
      console.error('Failed to update action config:', error);
    }
  };

  // Undo action
  const undoAction = async (actionId: string) => {
    try {
      const res = await fetch(`/api/autopilot/actions/${actionId}/undo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'User requested undo' })
      });
      const data = await res.json();
      if (data.success) {
        fetchData(); // Refresh
      }
    } catch (error) {
      console.error('Failed to undo action:', error);
    }
  };

  if (loading) {
    return (
      <div className={`p-6 bg-black/40 backdrop-blur-xl rounded-2xl border border-white/10 ${className}`}>
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className={`p-6 bg-black/40 backdrop-blur-xl rounded-2xl border border-white/10 ${className}`}>
        <p className="text-white/50 text-center">Failed to load auto-pilot configuration</p>
      </div>
    );
  }

  return (
    <div className={`bg-black/40 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
              <span className="text-xl">[AI]</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Auto-Pilot Mode</h2>
              <p className="text-sm text-white/50">Let Oi run your store autonomously</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <StatusBadge status={config.status} />
            <button
              onClick={toggleAutoPilot}
              className={`
                px-4 py-2 rounded-lg font-medium transition-all
                ${config.status === 'enabled'
                  ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                  : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                }
              `}
            >
              {config.status === 'enabled' ? 'Disable' : 'Enable'}
            </button>
          </div>
        </div>

        {/* Daily Stats */}
        {summary && config.status === 'enabled' && (
          <div className="mt-4 grid grid-cols-4 gap-4">
            <div className="p-3 bg-white/5 rounded-lg">
              <div className="text-2xl font-bold text-white">{summary.actions_executed}</div>
              <div className="text-xs text-white/50">Actions Today</div>
            </div>
            <div className="p-3 bg-white/5 rounded-lg">
              <div className="text-2xl font-bold text-emerald-400">{summary.successful}</div>
              <div className="text-xs text-white/50">Successful</div>
            </div>
            <div className="p-3 bg-white/5 rounded-lg">
              <div className="text-2xl font-bold text-white">${summary.total_spend.toFixed(0)}</div>
              <div className="text-xs text-white/50">Spent Today</div>
            </div>
            <div className="p-3 bg-white/5 rounded-lg">
              <div className="text-2xl font-bold text-cyan-400">{summary.remaining.actions}</div>
              <div className="text-xs text-white/50">Actions Left</div>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/10">
        {(['overview', 'actions', 'history'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`
              flex-1 px-4 py-3 text-sm font-medium transition-colors
              ${activeTab === tab 
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-white/5' 
                : 'text-white/50 hover:text-white/80'
              }
            `}
          >
            {tab === 'overview' && '[CONFIG] Overview'}
            {tab === 'actions' && '[TARGET] Action Types'}
            {tab === 'history' && ' History'}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Presets */}
            <div>
              <h3 className="text-sm font-medium text-white/80 mb-3">Quick Presets</h3>
              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={() => applyPreset('conservative')}
                  className="p-3 bg-white/5 rounded-lg border border-white/10 hover:border-emerald-500/50 transition-all text-left"
                >
                  <div className="text-lg mb-1"></div>
                  <div className="font-medium text-white text-sm">Conservative</div>
                  <div className="text-xs text-white/50">Safe & cautious</div>
                </button>
                <button
                  onClick={() => applyPreset('balanced')}
                  className="p-3 bg-white/5 rounded-lg border border-white/10 hover:border-cyan-500/50 transition-all text-left"
                >
                  <div className="text-lg mb-1"></div>
                  <div className="font-medium text-white text-sm">Balanced</div>
                  <div className="text-xs text-white/50">Best of both</div>
                </button>
                <button
                  onClick={() => applyPreset('aggressive')}
                  className="p-3 bg-white/5 rounded-lg border border-white/10 hover:border-orange-500/50 transition-all text-left"
                >
                  <div className="text-lg mb-1">[HOT]</div>
                  <div className="font-medium text-white text-sm">Aggressive</div>
                  <div className="text-xs text-white/50">Max automation</div>
                </button>
              </div>
            </div>

            {/* Global Limits */}
            <div>
              <h3 className="text-sm font-medium text-white/80 mb-3">Daily Limits</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-white/5 rounded-lg">
                  <label className="text-xs text-white/60 block mb-2">Max Daily Spend</label>
                  <div className="flex items-center gap-2">
                    <span className="text-white/40">$</span>
                    <input
                      type="number"
                      value={config.max_daily_spend}
                      onChange={(e) => setConfig({ ...config, max_daily_spend: parseFloat(e.target.value) })}
                      className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white"
                    />
                  </div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <label className="text-xs text-white/60 block mb-2">Max Daily Actions</label>
                  <input
                    type="number"
                    value={config.max_daily_actions}
                    onChange={(e) => setConfig({ ...config, max_daily_actions: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white"
                  />
                </div>
              </div>
            </div>

            {/* Notifications */}
            <div>
              <h3 className="text-sm font-medium text-white/80 mb-3">Notifications</h3>
              <div className="space-y-2">
                {[
                  { key: 'notify_on_action', label: 'Notify on each action' },
                  { key: 'notify_on_limit', label: 'Notify when limits approached' },
                  { key: 'daily_summary', label: 'Send daily summary' }
                ].map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg cursor-pointer">
                    <input
                      type="checkbox"
                      checked={(config as any)[key]}
                      onChange={(e) => setConfig({ ...config, [key]: e.target.checked })}
                      className="w-4 h-4 rounded bg-white/10 border-white/20 text-cyan-500 focus:ring-cyan-500"
                    />
                    <span className="text-sm text-white">{label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Actions Tab */}
        {activeTab === 'actions' && (
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(config.action_configs).map(([actionType, actionConfig]) => (
              <ActionTypeCard
                key={actionType}
                actionType={actionType}
                config={actionConfig}
                onUpdate={(updates) => updateActionConfig(actionType, updates)}
              />
            ))}
          </div>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <div className="space-y-3">
            {recentActions.length === 0 ? (
              <div className="text-center py-8 text-white/50">
                <div className="text-3xl mb-2">[AI]</div>
                <p>No auto-executed actions yet</p>
                <p className="text-sm">Enable auto-pilot to see actions here</p>
              </div>
            ) : (
              recentActions.map((action) => (
                <ActionItem
                  key={action.action_id}
                  action={action}
                  onUndo={undoAction}
                />
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Compact status widget for dashboard
export const AutoPilotStatusWidget: React.FC<{
  onClick?: () => void;
}> = ({ onClick }) => {
  const [status, setStatus] = useState<{
    status: string;
    is_active: boolean;
    enabled_count: number;
    today: { actions_executed: number; successful: number };
  } | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/autopilot/status?user_id=1');
        const data = await res.json();
        if (data.success) setStatus(data);
      } catch (error) {
        console.error('Failed to fetch auto-pilot status:', error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  return (
    <button
      onClick={onClick}
      className={`
        p-4 rounded-xl border transition-all hover:scale-[1.02]
        ${status.is_active 
          ? 'bg-emerald-500/10 border-emerald-500/30' 
          : 'bg-white/5 border-white/10'
        }
      `}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">[AI]</span>
          <span className="font-medium text-white">Auto-Pilot</span>
        </div>
        <StatusBadge status={status.status} />
      </div>
      
      {status.is_active && (
        <div className="mt-3 flex items-center gap-4 text-sm">
          <div>
            <span className="text-white/50">Actions: </span>
            <span className="text-white font-medium">{status.today.actions_executed}</span>
          </div>
          <div>
            <span className="text-white/50">Types: </span>
            <span className="text-white font-medium">{status.enabled_count}</span>
          </div>
        </div>
      )}
    </button>
  );
};

export default AutoPilotPanel;
