import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Undo2, X, AlertTriangle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

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

interface UndoConfirmModalProps {
  action: ExecutedAction;
  onConfirm: (actionId: number, reason?: string) => Promise<void>;
  onCancel: () => void;
}

const ACTION_UNDO_DESCRIPTIONS: Record<string, (payload: any, result: any) => string> = {
  deploy_product: (payload, result) =>
    `This will unpublish "${payload.product_name}" from your store. The product will return to draft status.`,
  adjust_price: (payload, result) =>
    `This will revert the price of "${payload.product_name}" from $${payload.new_price} back to $${payload.current_price}.`,
  pause_ad: (payload, result) =>
    `This will resume the "${payload.campaign_name}" ad campaign on ${payload.platform}.`,
  resume_ad: (payload, result) =>
    `This will pause the "${payload.campaign_name}" ad campaign on ${payload.platform} again.`,
  drop_product: (payload, result) =>
    `This will republish "${payload.product_name}" and make it active in your store again.`,
  send_refund: () => 'Refunds cannot be undone.',
  reply_email: () => 'Sent emails cannot be undone.',
  restock_alert: () => 'Alerts do not need to be undone.',
};

export function UndoConfirmModal({ action, onConfirm, onCancel }: UndoConfirmModalProps) {
  const [reason, setReason] = useState('');
  const [isUndoing, setIsUndoing] = useState(false);

  const handleConfirm = async () => {
    setIsUndoing(true);
    try {
      await onConfirm(action.id, reason || undefined);
    } catch (error) {
      // Error handling is done in the parent component
    } finally {
      setIsUndoing(false);
    }
  };

  const getUndoDescription = () => {
    const descFn = ACTION_UNDO_DESCRIPTIONS[action.action_type];
    if (descFn) {
      return descFn(action.payload, action.execution_result);
    }
    return 'This will reverse the action.';
  };

  const formatTimeRemaining = (hours: number | null): string => {
    if (hours === null) return 'N/A';
    if (hours < 1) {
      const minutes = Math.floor(hours * 60);
      return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
    }
    if (hours < 24) {
      return `${Math.floor(hours)} hour${Math.floor(hours) !== 1 ? 's' : ''}`;
    }
    const days = Math.floor(hours / 24);
    return `${days} day${days !== 1 ? 's' : ''}`;
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onCancel}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: 'spring', duration: 0.3 }}
          className="glass p-6 rounded-2xl max-w-lg w-full border border-orange-500/30"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gradient-to-br from-orange-500/20 to-red-500/20">
                <AlertTriangle className="w-6 h-6 text-orange-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Confirm Undo Action</h2>
                <p className="text-xs text-tertiary">This action will be reversed</p>
              </div>
            </div>
            <button
              onClick={onCancel}
              className="p-1 rounded-lg hover:bg-white/10 transition-colors"
              disabled={isUndoing}
            >
              <X className="w-5 h-5 text-tertiary" />
            </button>
          </div>

          {/* Action Details */}
          <div className="space-y-4 mb-6">
            {/* Action Title */}
            <div className="p-4 rounded-lg bg-white/5 border border-white/10">
              <p className="text-xs text-tertiary mb-1">Action to Undo:</p>
              <p className="text-sm font-medium text-white">{action.title}</p>
              {action.description && (
                <p className="text-xs text-tertiary mt-1">{action.description}</p>
              )}
            </div>

            {/* What Will Happen */}
            <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <p className="text-xs text-orange-300 font-medium mb-2 flex items-center gap-1">
                <Undo2 className="w-3 h-3" />
                What will happen:
              </p>
              <p className="text-sm text-gray-300">{getUndoDescription()}</p>
            </div>

            {/* Time Remaining */}
            {action.hours_remaining !== null && (
              <div className="p-3 rounded-lg bg-cyan-500/100/10 border border-blue-500/20">
                <p className="text-xs text-blue-300 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  You have {formatTimeRemaining(action.hours_remaining)} left to undo this action
                </p>
              </div>
            )}

            {/* Reason Input */}
            <div>
              <label className="block text-xs text-tertiary mb-2">
                Reason for undo (optional):
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={isUndoing}
                placeholder="e.g., Deployed wrong product variant"
                className={cn(
                  "w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10",
                  "text-sm text-white placeholder-gray-500",
                  "focus:outline-none focus:border-purple-500/50",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "resize-none"
                )}
                rows={3}
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={onCancel}
              disabled={isUndoing}
              className="flex-1 px-4 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-white text-sm font-medium border border-white/10 hover:border-white/20 transition-all disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={isUndoing}
              className={cn(
                "flex-1 px-4 py-2.5 rounded-lg text-white text-sm font-medium transition-all flex items-center justify-center gap-2",
                "bg-gradient-to-r from-orange-500/20 to-red-500/20",
                "hover:from-orange-500/30 hover:to-red-500/30",
                "border border-orange-500/30 hover:border-orange-500/50",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {isUndoing ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  >
                    <Undo2 className="w-4 h-4" />
                  </motion.div>
                  Undoing...
                </>
              ) : (
                <>
                  <Undo2 className="w-4 h-4" />
                  Confirm Undo
                </>
              )}
            </button>
          </div>

          {/* Warning */}
          <p className="text-[10px] text-tertiary text-center mt-4">
            This will reverse the action and update your store/campaigns accordingly
          </p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
