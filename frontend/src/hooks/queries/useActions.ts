import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';

// Types
export interface Action {
  id: string;
  type: 'deploy_product' | 'adjust_price' | 'pause_ad' | 'resume_ad' | 'drop_product' | 'send_refund' | 'reply_email' | 'restock_alert';
  title: string;
  description: string;
  payload: Record<string, any>;
  confidence: number;
  rationale: string;
  factors: { label: string; value: number; icon?: string }[];
  status: 'pending' | 'approved' | 'executed' | 'skipped' | 'failed';
  created_at: string;
  executed_at?: string;
  product_image?: string;
  estimated_impact?: string;
}

/**
 * Fetch pending actions waiting for approval
 * Refetches every 30 seconds to check for new actions
 */
export function usePendingActions() {
  return useQuery({
    queryKey: ['actions', 'pending'],
    queryFn: async () => {
      const response = await api.get('/api/actions?status=pending');
      return response.data as Action[];
    },
    refetchInterval: 30000, // Check for new actions every 30s
    retry: 1,
    staleTime: 10000,
  });
}

/**
 * Fetch all actions (pending, approved, skipped, etc.)
 */
export function useAllActions(status?: string) {
  return useQuery({
    queryKey: ['actions', 'all', status],
    queryFn: async () => {
      const params = status ? `?status=${status}` : '';
      const response = await api.get(`/api/actions${params}`);
      return response.data as Action[];
    },
    retry: 1,
    staleTime: 10000,
  });
}

/**
 * Approve a specific action
 * Triggers the action to be executed
 */
export function useApproveAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (actionId: string) => {
      const response = await api.post(`/api/actions/${actionId}/approve`);
      return response.data;
    },
    onSuccess: (_, actionId) => {
      // Invalidate actions queries to refetch updated data
      queryClient.invalidateQueries({ queryKey: ['actions'] });

      // Optional: Show success notification
      console.log(`Action ${actionId} approved successfully`);
    },
    onError: (error, actionId) => {
      console.error(`Failed to approve action ${actionId}:`, error);
    },
  });
}

/**
 * Skip/dismiss an action without executing it
 */
export function useSkipAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (actionId: string) => {
      const response = await api.post(`/api/actions/${actionId}/skip`);
      return response.data;
    },
    onSuccess: (_, actionId) => {
      queryClient.invalidateQueries({ queryKey: ['actions'] });
      console.log(`Action ${actionId} skipped`);
    },
    onError: (error, actionId) => {
      console.error(`Failed to skip action ${actionId}:`, error);
    },
  });
}

/**
 * Edit an action's payload before approval
 */
export function useEditAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ actionId, updatedPayload }: { actionId: string; updatedPayload: Record<string, any> }) => {
      const response = await api.patch(`/api/actions/${actionId}`, { payload: updatedPayload });
      return response.data;
    },
    onSuccess: (_, { actionId }) => {
      queryClient.invalidateQueries({ queryKey: ['actions'] });
      console.log(`Action ${actionId} updated`);
    },
    onError: (error, { actionId }) => {
      console.error(`Failed to edit action ${actionId}:`, error);
    },
  });
}

/**
 * Approve all high-confidence actions
 * Useful for bulk approval of AI recommendations
 */
export function useApproveAllHighConfidence() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (threshold: number = 85) => {
      const response = await api.post(`/api/actions/approve-all?confidence_threshold=${threshold}`);
      return response.data;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['actions'] });
      console.log(`Approved ${result.approved_count} high-confidence actions`);
    },
    onError: (error) => {
      console.error('Failed to approve all high-confidence actions:', error);
    },
  });
}

/**
 * Delete/cancel an action
 * Removes action from queue completely
 */
export function useDeleteAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (actionId: string) => {
      const response = await api.delete(`/api/actions/${actionId}`);
      return response.data;
    },
    onSuccess: (_, actionId) => {
      queryClient.invalidateQueries({ queryKey: ['actions'] });
      console.log(`Action ${actionId} deleted`);
    },
    onError: (error, actionId) => {
      console.error(`Failed to delete action ${actionId}:`, error);
    },
  });
}

/**
 * Get action statistics
 * Returns counts of pending, approved, skipped, executed actions
 */
export function useActionStats() {
  return useQuery({
    queryKey: ['actions', 'stats'],
    queryFn: async () => {
      const response = await api.get('/api/actions/stats');
      return response.data as {
        pending: number;
        approved: number;
        executed: number;
        skipped: number;
        failed: number;
        avg_confidence: number;
      };
    },
    refetchInterval: 30000,
    retry: 1,
  });
}
