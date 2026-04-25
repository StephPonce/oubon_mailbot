/**
 * OSPRA INTELLIGENCE - AUTHENTICATION HOOKS
 * ==========================================
 * 
 * React hooks for authentication state and protected routes.
 * 
 * Hooks:
 *   useAuth()          - Get auth state and methods
 *   useRequireAuth()   - Redirect if not authenticated
 *   useRequireTier()   - Redirect if tier too low
 * 
 * @author OspraOS
 * @date December 2024
 */

import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { authService } from '../services/auth';
import { initAnalytics, identifyUser, resetUser, capture, EVENTS } from '../services/analytics';


// =============================================================================
// AUTH CONTEXT
// =============================================================================

const AuthContext = createContext(null);

/**
 * Auth Provider Component
 * Wrap your app with this to provide auth state to all components.
 * 
 * Usage:
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 */
export function AuthProvider({ children }) {
  const [state, setState] = useState(() => authService.getState());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initialize PostHog once on mount. No-op if VITE_POSTHOG_KEY isn't
    // set in env or if posthog-js isn't installed (see services/analytics.js).
    initAnalytics();

    // Subscribe to auth changes — identify/reset PostHog on transitions.
    let prevAuthed = false;
    const unsubscribe = authService.subscribe((newState) => {
      setState(newState);
      setLoading(false);

      const nowAuthed = !!newState.isAuthenticated;
      if (nowAuthed && !prevAuthed && newState.user) {
        // Just logged in — identify the user and capture the event.
        identifyUser(newState.user);
        capture(EVENTS.LOGIN_SUCCEEDED, { tier: newState.user.tier });
      } else if (!nowAuthed && prevAuthed) {
        // Just logged out — reset analytics user.
        capture(EVENTS.LOGOUT);
        resetUser();
      }
      prevAuthed = nowAuthed;
    });

    return unsubscribe;
  }, []);

  const value = {
    ...state,
    loading,
    login: authService.login.bind(authService),
    logout: authService.logout.bind(authService),
    register: authService.register.bind(authService),
    hasTier: authService.hasTier.bind(authService),
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}


// =============================================================================
// useAuth HOOK
// =============================================================================

/**
 * Get authentication state and methods.
 * 
 * Usage:
 *   const { isAuthenticated, user, login, logout } = useAuth();
 * 
 * Returns:
 *   - isAuthenticated: boolean
 *   - user: { user_id, email, tier } | null
 *   - loading: boolean
 *   - login: (email, password) => Promise
 *   - logout: () => Promise
 *   - register: (email, password, tier?) => Promise
 *   - hasTier: (tier) => boolean
 */
export function useAuth() {
  const context = useContext(AuthContext);
  
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
}


// =============================================================================
// useRequireAuth HOOK
// =============================================================================

/**
 * Require authentication for a route.
 * Redirects to login page if not authenticated.
 * 
 * Usage:
 *   function Dashboard() {
 *     useRequireAuth();  // Will redirect to /login if not authenticated
 *     return <div>Dashboard</div>;
 *   }
 * 
 * Options:
 *   - redirectTo: string (default: '/login')
 */
export function useRequireAuth(options = {}) {
  const { redirectTo = '/login' } = options;
  const { isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      // Save intended destination
      navigate(redirectTo, { 
        state: { from: location.pathname },
        replace: true 
      });
    }
  }, [isAuthenticated, loading, navigate, redirectTo, location]);

  return { isAuthenticated, loading };
}


// =============================================================================
// useRequireTier HOOK
// =============================================================================

/**
 * Require a minimum tier for a route.
 * Redirects to upgrade page if tier is too low.
 * 
 * Usage:
 *   function PremiumFeature() {
 *     useRequireTier('soar');  // Requires Soar tier or higher
 *     return <div>Premium Feature</div>;
 *   }
 * 
 * Options:
 *   - redirectTo: string (default: '/upgrade')
 */
export function useRequireTier(requiredTier, options = {}) {
  const { redirectTo = '/upgrade' } = options;
  const { isAuthenticated, user, loading, hasTier } = useAuth();
  const navigate = useNavigate();

  const hasAccess = isAuthenticated && hasTier(requiredTier);

  useEffect(() => {
    if (!loading && isAuthenticated && !hasAccess) {
      navigate(redirectTo, { 
        state: { requiredTier, currentTier: user?.tier },
        replace: true 
      });
    }
  }, [hasAccess, loading, isAuthenticated, navigate, redirectTo, requiredTier, user]);

  return { hasAccess, loading, currentTier: user?.tier };
}


// =============================================================================
// useAuthenticatedFetch HOOK
// =============================================================================

/**
 * Hook for making authenticated API requests.
 * 
 * Usage:
 *   const { get, post, loading, error } = useAuthenticatedFetch();
 *   
 *   const data = await get('/api/autopilot/status');
 *   await post('/api/autopilot/enable');
 */
export function useAuthenticatedFetch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const request = useCallback(async (method, endpoint, data = null) => {
    setLoading(true);
    setError(null);

    try {
      let result;
      switch (method) {
        case 'GET':
          result = await authService.get(endpoint, data);
          break;
        case 'POST':
          result = await authService.post(endpoint, data);
          break;
        case 'PUT':
          result = await authService.put(endpoint, data);
          break;
        case 'DELETE':
          result = await authService.delete(endpoint);
          break;
        default:
          throw new Error(`Unknown method: ${method}`);
      }
      return result;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    get: useCallback((endpoint, params) => request('GET', endpoint, params), [request]),
    post: useCallback((endpoint, data) => request('POST', endpoint, data), [request]),
    put: useCallback((endpoint, data) => request('PUT', endpoint, data), [request]),
    delete: useCallback((endpoint) => request('DELETE', endpoint), [request]),
    clearError: useCallback(() => setError(null), []),
  };
}


// =============================================================================
// useTokenRefresh HOOK
// =============================================================================

/**
 * Hook that handles automatic token refresh.
 * Use this in your root component to keep tokens fresh.
 * 
 * Usage:
 *   function App() {
 *     useTokenRefresh();
 *     return <Router>...</Router>;
 *   }
 */
export function useTokenRefresh() {
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) return;

    // Check token every minute and refresh if needed
    const interval = setInterval(() => {
      // The authService.fetch method handles refresh automatically
      // This is just a safety check
      authService.get('/health').catch(() => {
        // Ignore errors - just checking if we need to refresh
      });
    }, 60 * 1000); // Every minute

    return () => clearInterval(interval);
  }, [isAuthenticated]);
}
