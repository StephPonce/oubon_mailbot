/**
 * OSPRA INTELLIGENCE - ACTION QUEUE
 * Integrated with DashboardProvider for Oi context awareness
 */

import React, { useState, useEffect } from 'react';
import { 
  Zap, Rocket, DollarSign, Pause, TrendingUp, Package, XCircle, 
  Check, X, Info, Clock, CheckCircle, XOctagon, ClipboardList, Loader2, Sparkles
} from 'lucide-react';
import { useDashboardContext } from '../hooks/useDashboardContext';
import { api } from '../services/api';
import { PageLayout } from './Layout';

function ActionCard({ action, onAccept, onDecline, onView }) {
  const [processing, setProcessing] = useState(false);

  const actionIcons = {
    deploy_product: Rocket,
    adjust_price: DollarSign,
    pause_ad: Pause,
    boost_ad: TrendingUp,
    restock: Package,
    drop_product: XCircle,
  };

  const Icon = actionIcons[action.action_type] || Zap;

  const handleAccept = async () => {
    setProcessing(true);
    try {
      await onAccept(action.id, action);
    } finally {
      setProcessing(false);
    }
  };

  const handleDecline = async () => {
    setProcessing(true);
    try {
      await onDecline(action.id, action);
    } finally {
      setProcessing(false);
    }
  };

  const confidence = Math.round((action.confidence || 0) * 100);

  return (
    <div 
      onClick={() => onView?.(action)}
      className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6 hover:border-purple-500/30 transition-all cursor-pointer"
    >
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center flex-shrink-0">
          <Icon className="w-6 h-6 text-purple-400" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-white font-semibold">{action.title || action.action_type}</h3>
            <div className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              confidence >= 90 ? 'bg-green-500/20 text-green-400' :
              confidence >= 70 ? 'bg-yellow-500/20 text-yellow-400' :
              'bg-red-500/20 text-red-400'
            }`}>
              {confidence}% confidence
            </div>
          </div>
          
          <p className="text-white/60 text-sm mb-3">
            {action.description || action.impact_summary}
          </p>

          {action.parameters && (
            <div className="flex flex-wrap gap-2 mb-4">
              {Object.entries(action.parameters).map(([key, value]) => (
                <span key={key} className="px-2 py-1 rounded bg-white/5 text-white/60 text-xs">
                  {key}: {JSON.stringify(value)}
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-3" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={handleAccept}
              disabled={processing}
              className="px-4 py-2 rounded-xl bg-green-500/20 border border-green-500/30 text-green-400 text-sm font-medium hover:bg-green-500/30 disabled:opacity-50 transition-all flex items-center gap-2"
            >
              <Check className="w-4 h-4" />
              Accept
            </button>
            <button
              onClick={handleDecline}
              disabled={processing}
              className="px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/30 disabled:opacity-50 transition-all flex items-center gap-2"
            >
              <X className="w-4 h-4" />
              Decline
            </button>
            <button className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-white/60 text-sm hover:bg-white/10 transition-all flex items-center gap-2">
              <Info className="w-4 h-4" />
              Details
            </button>
          </div>
        </div>

        <div className="text-white/40 text-xs text-right">
          {action.created_at && new Date(action.created_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

function StatsCard({ label, value, icon: Icon }) {
  return (
    <div className="backdrop-blur-xl bg-white/5 rounded-xl border border-white/10 p-4">
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5 text-white/60" />
        <div>
          <p className="text-white/40 text-xs">{label}</p>
          <p className="text-white font-semibold text-lg">{value}</p>
        </div>
      </div>
    </div>
  );
}

export function ActionQueue() {
  const { setPendingActions, trackInteraction, setActiveFilters } = useDashboardContext();
  
  const [actions, setActions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');

  useEffect(() => {
    loadData();
  }, [filter]);

  // Update dashboard context when actions change
  useEffect(() => {
    if (filter === 'pending') {
      // Format actions for dashboard context
      const formattedActions = actions.map(a => ({
        id: a.id,
        action_type: a.action_type,
        type: a.action_type,
        title: a.title || a.action_type,
        confidence: a.confidence,
        status: a.status || 'pending',
      }));
      setPendingActions(formattedActions);
    }
  }, [actions, filter, setPendingActions]);

  // Update filter in dashboard context
  useEffect(() => {
    setActiveFilters({ filter, view: 'actions' });
  }, [filter, setActiveFilters]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [actionsRes, statsRes] = await Promise.all([
        api.getPendingActions({ status: filter }),
        api.getActionStats(),
      ]);
      setActions(Array.isArray(actionsRes) ? actionsRes : []);
      setStats(statsRes);
    } catch (error) {
      console.error('Failed to load actions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (actionId, action) => {
    try {
      await api.acceptAction(actionId);
      setActions(prev => prev.filter(a => a.id !== actionId));
      
      // Track action acceptance
      trackInteraction('action_accept', {
        action_id: actionId,
        action_type: action.action_type,
        confidence: action.confidence,
      });
    } catch (error) {
      console.error('Accept failed:', error);
    }
  };

  const handleDecline = async (actionId, action) => {
    try {
      await api.declineAction(actionId, 'Declined by user');
      setActions(prev => prev.filter(a => a.id !== actionId));
      
      // Track action decline
      trackInteraction('action_decline', {
        action_id: actionId,
        action_type: action.action_type,
        confidence: action.confidence,
      });
    } catch (error) {
      console.error('Decline failed:', error);
    }
  };

  const handleActionView = (action) => {
    // Track viewing an action's details
    trackInteraction('action_view', {
      action_id: action.id,
      action_type: action.action_type,
    });
  };

  return (
    <PageLayout title="Action Queue" subtitle="Review and manage AI-proposed actions">
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatsCard label="Total Proposed" value={stats.total_proposed || 0} icon={ClipboardList} />
          <StatsCard label="Accepted" value={stats.total_accepted || 0} icon={CheckCircle} />
          <StatsCard label="Declined" value={stats.total_declined || 0} icon={XOctagon} />
          <StatsCard label="Pending" value={stats.pending || actions.length} icon={Clock} />
        </div>
      )}

      <div className="flex gap-2 mb-6">
        {['pending', 'accepted', 'declined', 'all'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === f
                ? 'bg-purple-500/20 border border-purple-500/30 text-purple-300'
                : 'bg-white/5 border border-white/10 text-white/60 hover:text-white'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6 animate-pulse">
              <div className="flex gap-4">
                <div className="w-12 h-12 rounded-xl bg-white/10" />
                <div className="flex-1 space-y-3">
                  <div className="h-4 bg-white/10 rounded w-1/3" />
                  <div className="h-3 bg-white/10 rounded w-2/3" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : actions.length > 0 ? (
        <div className="space-y-4">
          {actions.map((action) => (
            <ActionCard
              key={action.id}
              action={action}
              onAccept={handleAccept}
              onDecline={handleDecline}
              onView={handleActionView}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <Sparkles className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">All caught up!</h3>
          <p className="text-white/60">No {filter} actions at the moment</p>
        </div>
      )}
    </PageLayout>
  );
}

export default ActionQueue;
