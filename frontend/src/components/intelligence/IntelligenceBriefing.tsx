import React, { useState, useEffect } from 'react';
import { GlassPanel } from '../GlassPanel';

interface BriefingData {
  timestamp: string;
  briefing_text: string;
  attention_items: Array<{
    type: string;
    message: string;
    severity: string;
    product_id?: number;
  }>;
  key_metrics: {
    total_products?: number;
    active_campaigns?: number;
    total_revenue?: number;
  };
  recommended_actions: Array<{
    action: string;
    description: string;
    priority: string;
  }>;
}

export const IntelligenceBriefing: React.FC = () => {
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [briefingType, setBriefingType] = useState<'morning' | 'on-demand'>('morning');

  const fetchBriefing = async (type: 'morning' | 'on-demand') => {
    setLoading(true);
    setError(null);

    try {
      const endpoint = type === 'morning'
        ? '/api/intelligence/briefing/morning'
        : '/api/intelligence/briefing/on-demand';

      const response = await fetch(`http://localhost:8001${endpoint}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setBriefing(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch briefing');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBriefing('morning');
  }, []);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'bg-red-100 text-red-800 border-red-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low': return 'bg-blue-100 text-blue-800 border-blue-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'high': return 'bg-red-500 text-white';
      case 'medium': return 'bg-yellow-500 text-white';
      case 'low': return 'bg-green-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  return (
    <GlassPanel depth={60} delay={0.3}>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-light text-gray-900">Intelligence Briefing</h2>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setBriefingType('morning');
              fetchBriefing('morning');
            }}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              briefingType === 'morning'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Morning Briefing
          </button>
          <button
            onClick={() => {
              setBriefingType('on-demand');
              fetchBriefing('on-demand');
            }}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              briefingType === 'on-demand'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            On-Demand
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-red-800">Error: {error}</p>
        </div>
      )}

      {briefing && !loading && (
        <div className="space-y-6">
          {/* Key Metrics */}
          {briefing.key_metrics && (
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <p className="text-sm text-blue-600 font-medium">Total Products</p>
                <p className="text-2xl font-bold text-blue-900">
                  {briefing.key_metrics.total_products || 0}
                </p>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <p className="text-sm text-green-600 font-medium">Active Campaigns</p>
                <p className="text-2xl font-bold text-green-900">
                  {briefing.key_metrics.active_campaigns || 0}
                </p>
              </div>
              <div className="bg-purple-50 rounded-lg p-4">
                <p className="text-sm text-purple-600 font-medium">Total Revenue</p>
                <p className="text-2xl font-bold text-purple-900">
                  ${briefing.key_metrics.total_revenue?.toLocaleString() || 0}
                </p>
              </div>
            </div>
          )}

          {/* Attention Items */}
          {briefing.attention_items && briefing.attention_items.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Attention Required ({briefing.attention_items.length})
              </h3>
              <div className="space-y-2">
                {briefing.attention_items.map((item, index) => (
                  <div
                    key={index}
                    className={`border rounded-lg p-3 ${getSeverityColor(item.severity)}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="font-medium">{item.type}</p>
                        <p className="text-sm mt-1">{item.message}</p>
                      </div>
                      <span className="text-xs font-semibold uppercase px-2 py-1 rounded">
                        {item.severity}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Briefing Text */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Executive Summary</h3>
            <div className="bg-gray-50 rounded-lg p-4 prose max-w-none">
              <p className="text-gray-700 whitespace-pre-wrap">{briefing.briefing_text}</p>
            </div>
          </div>

          {/* Recommended Actions */}
          {briefing.recommended_actions && briefing.recommended_actions.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Recommended Actions</h3>
              <div className="space-y-2">
                {briefing.recommended_actions.map((action, index) => (
                  <div
                    key={index}
                    className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-medium text-gray-900">{action.action}</p>
                      <span className={`text-xs font-semibold px-2 py-1 rounded ${getPriorityBadge(action.priority)}`}>
                        {action.priority}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">{action.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timestamp */}
          <div className="text-sm text-gray-500 text-right">
            Generated: {new Date(briefing.timestamp).toLocaleString()}
          </div>
        </div>
      )}
    </GlassPanel>
  );
};
