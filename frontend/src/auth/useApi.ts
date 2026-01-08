/**
 * OSPRA INTELLIGENCE - useApi Hook
 * ==================================
 * 
 * React hook for making authenticated API calls.
 * 
 * Features:
 * - Automatic authentication
 * - Loading and error states
 * - Automatic logout on 401
 * - Type-safe requests
 * 
 * Author: OspraOS
 * Date: December 2024
 */

import { useState, useCallback } from 'react';
import { authApi } from './authApi';
import { useAuth } from './AuthContext';

// =============================================================================
// TYPES
// =============================================================================

interface ApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

interface UseApiResult<T> extends ApiState<T> {
  execute: () => Promise<T | null>;
  reset: () => void;
}

interface UseApiMutationResult<T, P> extends ApiState<T> {
  execute: (params: P) => Promise<T | null>;
  reset: () => void;
}

// =============================================================================
// useApi - For GET requests
// =============================================================================

export function useApi<T>(endpoint: string): UseApiResult<T> {
  const { logout } = useAuth();
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const execute = useCallback(async (): Promise<T | null> => {
    setState({ data: null, isLoading: true, error: null });

    try {
      const data = await authApi.get<T>(endpoint);
      setState({ data, isLoading: false, error: null });
      return data;
    } catch (error: any) {
      const errorMessage = error.message || 'Request failed';
      
      // Handle session expiry
      if (errorMessage.includes('Session expired')) {
        logout();
      }
      
      setState({ data: null, isLoading: false, error: errorMessage });
      return null;
    }
  }, [endpoint, logout]);

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return { ...state, execute, reset };
}

// =============================================================================
// useApiMutation - For POST/PUT/DELETE requests
// =============================================================================

export function useApiMutation<T, P = any>(
  endpoint: string,
  method: 'POST' | 'PUT' | 'DELETE' = 'POST'
): UseApiMutationResult<T, P> {
  const { logout } = useAuth();
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const execute = useCallback(async (params: P): Promise<T | null> => {
    setState({ data: null, isLoading: true, error: null });

    try {
      let data: T;
      
      switch (method) {
        case 'POST':
          data = await authApi.post<T>(endpoint, params);
          break;
        case 'PUT':
          data = await authApi.put<T>(endpoint, params);
          break;
        case 'DELETE':
          data = await authApi.delete<T>(endpoint);
          break;
      }
      
      setState({ data, isLoading: false, error: null });
      return data;
    } catch (error: any) {
      const errorMessage = error.message || 'Request failed';
      
      // Handle session expiry
      if (errorMessage.includes('Session expired')) {
        logout();
      }
      
      setState({ data: null, isLoading: false, error: errorMessage });
      return null;
    }
  }, [endpoint, method, logout]);

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return { ...state, execute, reset };
}

// =============================================================================
// useApiLazy - For manual triggering with dynamic endpoints
// =============================================================================

export function useApiLazy<T>(): {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  get: (endpoint: string) => Promise<T | null>;
  post: (endpoint: string, data?: any) => Promise<T | null>;
  put: (endpoint: string, data?: any) => Promise<T | null>;
  del: (endpoint: string) => Promise<T | null>;
  reset: () => void;
} {
  const { logout } = useAuth();
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const handleRequest = useCallback(async (
    requestFn: () => Promise<T>
  ): Promise<T | null> => {
    setState({ data: null, isLoading: true, error: null });

    try {
      const data = await requestFn();
      setState({ data, isLoading: false, error: null });
      return data;
    } catch (error: any) {
      const errorMessage = error.message || 'Request failed';
      
      if (errorMessage.includes('Session expired')) {
        logout();
      }
      
      setState({ data: null, isLoading: false, error: errorMessage });
      return null;
    }
  }, [logout]);

  const get = useCallback(
    (endpoint: string) => handleRequest(() => authApi.get<T>(endpoint)),
    [handleRequest]
  );

  const post = useCallback(
    (endpoint: string, data?: any) => handleRequest(() => authApi.post<T>(endpoint, data)),
    [handleRequest]
  );

  const put = useCallback(
    (endpoint: string, data?: any) => handleRequest(() => authApi.put<T>(endpoint, data)),
    [handleRequest]
  );

  const del = useCallback(
    (endpoint: string) => handleRequest(() => authApi.delete<T>(endpoint)),
    [handleRequest]
  );

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return { ...state, get, post, put, del, reset };
}

// =============================================================================
// SPECIFIC HOOKS FOR COMMON ENDPOINTS
// =============================================================================

/**
 * Hook for auto-pilot operations
 */
export function useAutopilot() {
  const getStatus = useApi<any>('/api/autopilot/status');
  const getConfig = useApi<any>('/api/autopilot/config');
  const enable = useApiMutation<any>('/api/autopilot/enable');
  const disable = useApiMutation<any>('/api/autopilot/disable');
  const pause = useApiMutation<any>('/api/autopilot/pause');

  return {
    status: getStatus,
    config: getConfig,
    enable,
    disable,
    pause,
  };
}

/**
 * Hook for AI actions
 */
export function useAIActions() {
  const actions = useApi<any[]>('/api/ai/actions');
  const stats = useApi<any>('/api/ai/actions/stats/summary');
  const accept = useApiMutation<any, { action_id: string }>('/api/ai/actions/{id}/accept');
  const decline = useApiMutation<any, { action_id: string; reason: string }>('/api/ai/actions/{id}/decline');

  return {
    actions,
    stats,
    accept,
    decline,
  };
}

/**
 * Hook for product discovery
 */
export function useDiscovery() {
  const discover = useApiMutation<any, { niche: string; max_products?: number }>('/api/v2/discover');
  const trending = useApi<any>('/api/v2/trending');

  return {
    discover,
    trending,
  };
}

/**
 * Hook for usage tracking
 */
export function useUsage() {
  const dashboard = useApi<any>('/api/usage/dashboard');
  const history = useApi<any>('/api/usage/history');

  return {
    dashboard,
    history,
  };
}

export default useApi;
