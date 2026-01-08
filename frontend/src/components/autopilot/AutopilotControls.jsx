/**
 * OSPRA INTELLIGENCE - AUTOPILOT CONTROLS
 * ========================================
 * 
 * Full autopilot configuration interface.
 * 
 * @author OspraOS
 * @date December 2024
 */

import React, { useState, useEffect } from 'react';
import { useAuth, useAuthenticatedFetch, useRequireTier } from '../../hooks/useAuth';

function PresetCard({ name, description, isActive, onClick, disabled, locked }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || locked}
      className={`p-4 rounded-xl border text-left transition-all ${
        isActive
          ? 'bg-purple-500/20 border-purple-500/50 ring-2 ring-purple-500/30'
          : locked
          ? 'bg-white/5 border-white/10 opacity-50 cursor-not-allowed'
          : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-purple-500/30'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-white font-semibold">{name}</span>
        {locked && <span className="text-xs text-yellow-400">[LOCKED] Soar+</span>}
        {isActive && <span className="text-xs text-green-400">Active</span>}
      </div>
      <p className="text-white/50 text-sm">{description}</p>
    </button>
  );
}

function ActionToggle({ name, label, enabled, confidence, onToggle, onConfidenceChange }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-white/5 last:border-0">
      <div className="flex-1">
        <p className="text-white/90 text-sm">{label}</p>
        <p className="text-white/40 text-xs">Min confidence: {Math.round(confidence * 100)}%</p>
      </div>
      
      <div className="flex items-center space-x-3">
        <input
          type="range"
          min="50"
          max="99"
          value={confidence * 100}
          onChange={(e) => onConfidenceChange(name, parseInt(e.target.value) / 100)}
          className="w-20 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-purple-500"
        />
        
        <button
          onClick={() => onToggle(name)}
          className={`w-12 h-6 rounded-full transition-colors ${
            enabled ? 'bg-purple-500' : 'bg-white/20'
          }`}
        >
          <div className={`w-5 h-5 rounded-full bg-white shadow-md transform transition-transform ${
            enabled ? 'translate-x-6' : 'translate-x-0.5'
          }`} />
        </button>
      </div>
    </div>
  );
}

export function AutopilotControls() {
  const { user, hasTier } = useAuth();
  const { get, post, put, loading } = useAuthenticatedFetch();
  
  const [config, setConfig] = useState(null);
  const [status, setStatus] = useState(null);
  const [activePreset, setActivePreset] = useState('conservative');
  const [saving, setSaving] = useState(false);

  const canUseAggressive = hasTier('soar');

  // Fetch config on mount
  useEffect(() => {
    async function fetchConfig() {
      try {
        const [configData, statusData] = await Promise.all([
          get('/api/autopilot/config'),
          get('/api/autopilot/status'),
        ]);
        
        setConfig(configData.config);
        setStatus(statusData);
        
        // Determine active preset from config
        if (configData.config?.preset) {
          setActivePreset(configData.config.preset);
        }
      } catch (error) {
        console.error('Failed to fetch autopilot config:', error);
      }
    }
    
    fetchConfig();
  }, []);

  const handlePresetChange = async (preset) => {
    if (preset === 'aggressive' && !canUseAggressive) return;
    
    setSaving(true);
    try {
      await post(`/api/autopilot/presets/${preset}`);
      setActivePreset(preset);
      
      // Refresh config
      const configData = await get('/api/autopilot/config');
      setConfig(configData.config);
    } catch (error) {
      console.error('Failed to apply preset:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleAutopilot = async () => {
    setSaving(true);
    try {
      if (status?.is_active) {
        await post('/api/autopilot/disable');
      } else {
        await post('/api/autopilot/enable');
      }
      
      // Refresh status
      const statusData = await get('/api/autopilot/status');
      setStatus(statusData);
    } catch (error) {
      console.error('Failed to toggle autopilot:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleActionToggle = async (actionType) => {
    if (!config?.action_configs?.[actionType]) return;
    
    const currentConfig = config.action_configs[actionType];
    
    try {
      await put(`/api/autopilot/action/${actionType}`, {
        enabled: !currentConfig.enabled,
        min_confidence: currentConfig.min_confidence,
      });
      
      // Refresh config
      const configData = await get('/api/autopilot/config');
      setConfig(configData.config);
    } catch (error) {
      console.error('Failed to toggle action:', error);
    }
  };

  const handleConfidenceChange = async (actionType, confidence) => {
    if (!config?.action_configs?.[actionType]) return;
    
    const currentConfig = config.action_configs[actionType];
    
    try {
      await put(`/api/autopilot/action/${actionType}`, {
        enabled: currentConfig.enabled,
        min_confidence: confidence,
      });
      
      // Update local state immediately
      setConfig(prev => ({
        ...prev,
        action_configs: {
          ...prev.action_configs,
          [actionType]: {
            ...prev.action_configs[actionType],
            min_confidence: confidence,
          },
        },
      }));
    } catch (error) {
      console.error('Failed to update confidence:', error);
    }
  };

  const presets = [
    { id: 'conservative', name: ' Conservative', description: 'High confidence required, low daily limits. Safe for beginners.' },
    { id: 'balanced', name: ' Balanced', description: 'Moderate confidence and limits. Good for most users.' },
    { id: 'aggressive', name: '[START] Aggressive', description: 'Lower thresholds, higher limits. For experienced users.', locked: !canUseAggressive },
  ];

  const actionTypes = [
    { name: 'deploy_product', label: 'Deploy Products' },
    { name: 'adjust_pricing', label: 'Adjust Pricing' },
    { name: 'pause_ads', label: 'Pause Ads' },
    { name: 'restock_inventory', label: 'Restock Inventory' },
  ];

  if (loading && !config) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">[AI] Auto-Pilot Settings</h1>
          <p className="text-white/60 mt-1">Configure how Oi automates your business</p>
        </div>
        
        <button
          onClick={handleToggleAutopilot}
          disabled={saving}
          className={`px-6 py-3 rounded-xl font-semibold transition-all ${
            status?.is_active
              ? 'bg-red-500/20 border border-red-500/50 text-red-400 hover:bg-red-500/30'
              : 'bg-gradient-to-r from-purple-600 to-cyan-600 text-white hover:from-purple-500 hover:to-cyan-500'
          }`}
        >
          {status?.is_active ? 'Disable Auto-Pilot' : 'Enable Auto-Pilot'}
        </button>
      </div>

      {/* Status Banner */}
      <div className={`p-4 rounded-xl border ${
        status?.is_active
          ? 'bg-green-500/10 border-green-500/30'
          : 'bg-white/5 border-white/10'
      }`}>
        <div className="flex items-center">
          <div className={`w-3 h-3 rounded-full mr-3 ${status?.is_active ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-white font-medium">
            Auto-Pilot is {status?.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        {status?.is_active && (
          <p className="text-white/60 text-sm mt-2 ml-6">
            {status?.actions_today || 0} actions executed today
          </p>
        )}
      </div>

      {/* Presets */}
      <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
        <h2 className="text-white font-semibold mb-4">Automation Presets</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {presets.map((preset) => (
            <PresetCard
              key={preset.id}
              name={preset.name}
              description={preset.description}
              isActive={activePreset === preset.id}
              onClick={() => handlePresetChange(preset.id)}
              disabled={saving}
              locked={preset.locked}
            />
          ))}
        </div>
      </div>

      {/* Action Configuration */}
      <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
        <h2 className="text-white font-semibold mb-4">Action Settings</h2>
        <p className="text-white/50 text-sm mb-4">
          Configure which actions Oi can perform automatically and their confidence thresholds.
        </p>
        
        <div>
          {actionTypes.map((action) => {
            const actionConfig = config?.action_configs?.[action.name] || { enabled: false, min_confidence: 0.9 };
            return (
              <ActionToggle
                key={action.name}
                name={action.name}
                label={action.label}
                enabled={actionConfig.enabled}
                confidence={actionConfig.min_confidence}
                onToggle={handleActionToggle}
                onConfidenceChange={handleConfidenceChange}
              />
            );
          })}
        </div>
      </div>

      {/* Daily Limits */}
      <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
        <h2 className="text-white font-semibold mb-4">Daily Limits</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-white/5 rounded-xl">
            <p className="text-white/60 text-sm">Max Daily Actions</p>
            <p className="text-2xl font-bold text-white mt-1">{config?.max_daily_actions || 10}</p>
          </div>
          <div className="p-4 bg-white/5 rounded-xl">
            <p className="text-white/60 text-sm">Max Daily Spend</p>
            <p className="text-2xl font-bold text-white mt-1">${config?.max_daily_spend || 100}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AutopilotControls;
