import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { History, Undo2, Clock, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api';
import { UndoConfirmModal } from './UndoConfirmModal';

interface ExecutedAction {
  id: number;
  action_type: string;
  title: string;
  description: string;
  executed_at: string;
  undone_at: string | null;
  can_undo: boolean;
  hours_remaining: number | null;
  undo_deadline: string | null;
  payload: Record<string, any>;
  execution_result: Record<string, any>;
}

interface RecentActionsResponse {
  actions: ExecutedAction[];
}

interface RecentActionsProps {
  className?: string;
  limit?: number;
}

const ACTION_TYPE_ICONS: Record<string, string> = {
  deploy_product: '🚀',
  adjust_price: '💰',
  pause_ad: '⏸️',
  resume_ad: '▶️',
  drop_product: '🗑️',
  send_refund: '💸',
  reply_email: '📧',
  restock_alert: '🔔',
};

const ACTION_TYPE_LABELS: Record<string, string> = {
  deploy_product: 'Product Deployment',
  adjust_price: 'Price Adjustment',
  pause_ad: 'Ad Pause',
  resume_ad: 'Ad Resume',
  drop_product: 'Product Removal',
  send_refund: 'Refund',
  reply_email: 'Email Reply',
  restock_alert: 'Restock Alert',
};

export function RecentActions({ className, limit = 10 }: RecentActionsProps) {
  const [actions, setActions] = useState<ExecutedAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [undoingActionId, setUndoingActionId] = useState<number | null>(null);
  const [selectedAction, setSelectedAction] = useState<ExecutedAction | null>(null);

  const fetchActions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get<RecentActionsResponse>(`/actions/recent-executed?limit=${limit}`);
      setActions(response.actions);
    } catch (err) {
      console.error('Failed to load recent actions:', err);
      setError('Failed to load recent actions. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActions();
    // Refresh every 30 seconds to update countdown timers
    const interval = setInterval(fetchActions, 30000);
    return () => clearInterval(interval);
  }, [limit]);

  const handleUndoClick = (action: ExecutedAction) => {
    setSelectedAction(action);
  };

  const handleUndoConfirm = async (actionId: number, reason?: string) => {
    try {
      setUndoingActionId(actionId);
      const queryParams = reason ? `?reason=${encodeURIComponent(reason)}` : '';
      await apiClient.post(`/actions/${actionId}/undo${queryParams}`, {});

      // Refresh the list
      await fetchActions();
      setSelectedAction(null);
    } catch (err: any) {
      console.error('Failed to undo action:', err);
      alert(err.response?.data?.detail || 'Failed to undo action. Please try again.');
    } finally {
      setUndoingActionId(null);
    }
  };

  const handleUndoCancel = () => {
    setSelectedAction(null);
  };

  const formatTimeRemaining = (hours: number | null): string => {
    if (hours === null) return 'N/A';
    if (hours < 1) {
      const minutes = Math.floor(hours * 60);
      return `${minutes}m`;
    }
    if (hours < 24) {
      return `${Math.floor(hours)}h`;
    }
    const days = Math.floor(hours / 24);
    return `${days}d`;
  };

  const getUrgencyColor = (hours: number | null): string => {
    if (hours === null) return 'text-tertiary';
    if (hours < 1) return 'text-red-400';
    if (hours < 6) return 'text-orange-400';
    if (hours < 24) return 'text-yellow-400';
    return 'text-green-400';
  };

  if (loading && actions.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn("glass p-6 rounded-2xl", className)}
      >
        <div className="flex items-center gap-3">
          <History className="w-5 h-5 animate-spin text-purple-400" />
          <p className="text-sm text-tertiary">Loading recent actions...</p>
        </div>
      </motion.div>
    );
  }

  if (error && actions.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn("glass p-6 rounded-2xl border border-red-500/20", className)}
      >
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <div>
            <p className="text-sm text-red-400">{error}</p>
            <button
              onClick={fetchActions}
              className="text-xs text-purple-400 hover:text-purple-300 mt-1 underline"
            >
              Try again
            </button>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className={cn("glass p-6 rounded-2xl", className)}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20">
              <History className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Recent Actions</h2>
              <p className="text-xs text-tertiary">
                {actions.length} action{actions.length !== 1 ? 's' : ''} in history
              </p>
            </div>
          </div>

          <button
            onClick={fetchActions}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 text-xs font-medium border border-purple-500/30 hover:border-purple-500/50 transition-all disabled:opacity-50"
          >
            Refresh
          </button>
        </div>

        {/* Actions List */}
        {actions.length === 0 ? (
          <div className="text-center py-8">
            <History className="w-12 h-12 text-secondary mx-auto mb-3" />
            <p className="text-sm text-tertiary">No recent actions to display</p>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence mode="popLayout">
              {actions.map((action) => (
                <motion.div
                  key={action.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                  className={cn(
                    "p-4 rounded-lg border transition-all",
                    action.undone_at
                      ? " 0/10 border-gray-500/20"
                      : "bg-white/5 border-white/10 hover:bg-white/10"
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      {/* Title and Icon */}
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">
                          {ACTION_TYPE_ICONS[action.action_type] || '⚡'}
                        </span>
                        <h3 className="text-sm font-medium text-white truncate">
                          {action.title}
                        </h3>
                        {action.undone_at && (
                          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/100/20 text-yellow-300 border border-yellow-500/30">
                            <Undo2 className="w-3 h-3" />
                            UNDONE
                          </span>
                        )}
                      </div>

                      {/* Description */}
                      {action.description && (
                        <p className="text-xs text-tertiary mb-2">{action.description}</p>
                      )}

                      {/* Metadata */}
                      <div className="flex items-center gap-3 text-[10px] text-tertiary">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(action.executed_at).toLocaleString()}
                        </span>
                        <span>•</span>
                        <span>{ACTION_TYPE_LABELS[action.action_type] || action.action_type}</span>
                      </div>
                    </div>

                    {/* Undo Button */}
                    <div className="flex items-center gap-2">
                      {action.can_undo && !action.undone_at && (
                        <div className="flex flex-col items-end gap-1">
                          <span className={cn(
                            "text-[10px] font-medium flex items-center gap-1",
                            getUrgencyColor(action.hours_remaining)
                          )}>
                            <Clock className="w-3 h-3" />
                            {formatTimeRemaining(action.hours_remaining)} left
                          </span>
                          <button
                            onClick={() => handleUndoClick(action)}
                            disabled={undoingActionId === action.id}
                            className="px-3 py-1.5 rounded-lg bg-orange-500/20 hover:bg-orange-500/30 text-orange-300 text-xs font-medium border border-orange-500/30 hover:border-orange-500/50 transition-all flex items-center gap-1 disabled:opacity-50"
                          >
                            <Undo2 className="w-3 h-3" />
                            {undoingActionId === action.id ? 'Undoing...' : 'Undo'}
                          </button>
                        </div>
                      )}

                      {!action.can_undo && !action.undone_at && (
                        <div className="flex flex-col items-end">
                          <span className="text-[10px] text-tertiary flex items-center gap-1">
                            <XCircle className="w-3 h-3" />
                            Cannot undo
                          </span>
                        </div>
                      )}

                      {action.undone_at && (
                        <div className="flex flex-col items-end">
                          <span className="text-[10px] text-tertiary">
                            {new Date(action.undone_at).toLocaleString()}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </motion.div>

      {/* Undo Confirmation Modal */}
      {selectedAction && (
        <UndoConfirmModal
          action={selectedAction}
          onConfirm={handleUndoConfirm}
          onCancel={handleUndoCancel}
        />
      )}
    </>
  );
}
