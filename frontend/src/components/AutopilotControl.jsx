/**
 * OSPRA INTELLIGENCE - AUTOPILOT CONTROL
 * Integrated with DashboardProvider for Oi context awareness
 */

import React, { useState, useEffect } from 'react';
import { 
  Shield, Scale, Rocket, Lock, Loader2, Activity, Power, SlidersHorizontal
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useDashboardContext } from '../hooks/useDashboardContext';
import { api } from '../services/api';
import { PageLayout } from './Layout';

function PresetCard({ preset, active, onApply, disabled }) {
  const icons = {
    conservative: Shield,
    balanced: Scale,
    aggressive: Rocket,
  };
  const Icon = icons[preset.id] || Shield;

  return (
    <button
      onClick={() => onApply(preset.id)}
      disabled={disabled}
      className={`p-6 rounded-2xl border text-left transition-all ${
        active
          ? 'bg-purple-500/20 border-purple-500/50'
          : 'bg-white/5 border-white/10 hover:border-purple-500/30'
      } disabled:opacity-50`}
    >
      <Icon className={`w-8 h-8 mb-3 ${active ? 'text-purple-400' : 'text-white/60'}`} />
      <h3 className="text-white font-semibold mb-1">{preset.name}</h3>
      <p className="text-white/60 text-sm">{preset.description}</p>
    </button>
  );
}

function ConfigSlider({ label, value, min, max, onChange, disabled }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between">
        <span className="text-white/60 text-sm">{label}</span>
        <span className="text-white font-medium">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        className="w-full"
      />
    </div>
  );
}

export function AutopilotControl() {
  const { user, hasTier } = useAuth();
  const { setAutopilotStatus, trackInteraction, setConnectionStatus } = useDashboardContext();
  
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activePreset, setActivePreset] = useState(null);

  const presets = [
    { id: 'conservative', name: 'Conservative', description: 'Low risk, manual approval for most actions' },
    { id: 'balanced', name: 'Balanced', description: 'Moderate automation with safety checks' },
    { id: 'aggressive', name: 'Aggressive', description: 'Maximum automation, high confidence actions auto-execute' },
  ];

  useEffect(() => {
    loadData();
  }, []);

  // Update dashboard context when status/config changes
  useEffect(() => {
    if (status || config) {
      setAutopilotStatus(status, config);
      setConnectionStatus({ intelligence: !!status });
    }
  }, [status, config, setAutopilotStatus, setConnectionStatus]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statusRes, configRes] = await Promise.all([
        api.getAutopilotStatus(),
        api.getAutopilotConfig(),
      ]);
      setStatus(statusRes);
      setConfig(configRes);
    } catch (error) {
      console.error('Failed to load autopilot data:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleAutopilot = async () => {
    setSaving(true);
    try {
      if (status?.is_active) {
        await api.disableAutopilot();
        trackInteraction('autopilot_disable', { previous_state: 'active' });
      } else {
        await api.enableAutopilot();
        trackInteraction('autopilot_enable', { previous_state: 'inactive' });
      }
      await loadData();
    } catch (error) {
      console.error('Failed to toggle autopilot:', error);
    } finally {
      setSaving(false);
    }
  };

  const applyPreset = async (presetId) => {
    setSaving(true);
    try {
      await api.applyPreset(presetId);
      setActivePreset(presetId);
      
      // Track preset change
      trackInteraction('autopilot_preset', { 
        preset: presetId,
        previous_preset: activePreset 
      });
      
      await loadData();
    } catch (error) {
      console.error('Failed to apply preset:', error);
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = async (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      await api.updateAutopilotConfig(config);
      
      // Track config change
      trackInteraction('autopilot_config', { 
        confidence_threshold: config.confidence_threshold,
        max_daily_actions: config.max_daily_actions,
        max_daily_spend: config.max_daily_spend,
      });
    } catch (error) {
      console.error('Failed to save config:', error);
    } finally {
      setSaving(false);
    }
  };

  const canUseAutopilot = hasTier('flight');

  if (loading) {
    return (
      <PageLayout title="Auto-Pilot Control">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Auto-Pilot Control" subtitle="Configure automated actions and thresholds">
      {!canUseAutopilot && (
        <div className="backdrop-blur-xl bg-yellow-500/10 border border-yellow-500/30 rounded-2xl p-6 mb-8">
          <div className="flex items-center gap-4">
            <Lock className="w-8 h-8 text-yellow-500" />
            <div>
              <h3 className="text-white font-semibold">Upgrade Required</h3>
              <p className="text-white/60 text-sm">Auto-Pilot is available on Flight tier and above</p>
            </div>
          </div>
        </div>
      )}

      <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6 mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              status?.is_active ? 'bg-green-500/20' : 'bg-white/10'
            }`}>
              <Power className={`w-6 h-6 ${status?.is_active ? 'text-green-500' : 'text-white/60'}`} />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">Auto-Pilot Status</h2>
              <p className={`text-sm ${status?.is_active ? 'text-green-400' : 'text-white/60'}`}>
                {status?.is_active ? 'Active and monitoring' : 'Currently disabled'}
              </p>
            </div>
          </div>
          <button
            onClick={toggleAutopilot}
            disabled={!canUseAutopilot || saving}
            className={`px-6 py-3 rounded-xl font-semibold transition-all disabled:opacity-50 ${
              status?.is_active
                ? 'bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30'
                : 'bg-gradient-to-r from-purple-600 to-cyan-600 text-white hover:from-purple-500 hover:to-cyan-500'
            }`}
          >
            {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : status?.is_active ? 'Disable' : 'Enable'}
          </button>
        </div>
      </div>

      <div className="mb-8">
        <h3 className="text-lg font-semibold text-white mb-4">Quick Presets</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {presets.map(preset => (
            <PresetCard
              key={preset.id}
              preset={preset}
              active={activePreset === preset.id}
              onApply={applyPreset}
              disabled={!canUseAutopilot || saving}
            />
          ))}
        </div>
      </div>

      <div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6">
        <div className="flex items-center gap-3 mb-6">
          <SlidersHorizontal className="w-5 h-5 text-white/60" />
          <h3 className="text-lg font-semibold text-white">Advanced Configuration</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <ConfigSlider
            label="Confidence Threshold"
            value={config?.confidence_threshold || 85}
            min={50}
            max={100}
            onChange={(v) => updateConfig('confidence_threshold', v)}
            disabled={!canUseAutopilot}
          />
          <ConfigSlider
            label="Max Daily Actions"
            value={config?.max_daily_actions || 10}
            min={1}
            max={50}
            onChange={(v) => updateConfig('max_daily_actions', v)}
            disabled={!canUseAutopilot}
          />
          <ConfigSlider
            label="Max Daily Spend ($)"
            value={config?.max_daily_spend || 100}
            min={10}
            max={1000}
            onChange={(v) => updateConfig('max_daily_spend', v)}
            disabled={!canUseAutopilot}
          />
          <ConfigSlider
            label="Max Single Action ($)"
            value={config?.max_single_action || 50}
            min={5}
            max={500}
            onChange={(v) => updateConfig('max_single_action', v)}
            disabled={!canUseAutopilot}
          />
        </div>

        <div className="mt-6 pt-6 border-t border-white/10 flex justify-end">
          <button
            onClick={saveConfig}
            disabled={!canUseAutopilot || saving}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-semibold hover:from-purple-500 hover:to-cyan-500 disabled:opacity-50 transition-all flex items-center gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Save Configuration
          </button>
        </div>
      </div>
    </PageLayout>
  );
}

export default AutopilotControl;
