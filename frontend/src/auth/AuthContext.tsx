/**
 * OSPRA INTELLIGENCE - AUTH CONTEXT
 * ==================================
 * 
 * React Context for JWT authentication state management.
 * 
 * Features:
 * - Automatic token refresh
 * - Persistent login (localStorage)
 * - User tier information
 * - Protected route support
 * 
 * Author: OspraOS
 * Date: December 2024
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi, User, AuthTokens, LoginCredentials, RegisterCredentials } from './authApi';

// =============================================================================
// TYPES
// =============================================================================

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<boolean>;
  register: (credentials: RegisterCredentials) => Promise<boolean>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  clearError: () => void;
}

// =============================================================================
// CONTEXT
// =============================================================================

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// =============================================================================
// PROVIDER
// =============================================================================

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  // ---------------------------------------------------------------------------
  // Initialize auth state from stored tokens
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Check if we have stored tokens
        const accessToken = localStorage.getItem('access_token');
        
        if (!accessToken) {
          setState(prev => ({ ...prev, isLoading: false }));
          return;
        }

        // Validate token and get user info
        const user = await authApi.getCurrentUser();
        
        if (user) {
          setState({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } else {
          // Token invalid, try refresh
          const refreshed = await authApi.refreshToken();
          
          if (refreshed) {
            const refreshedUser = await authApi.getCurrentUser();
            setState({
              user: refreshedUser,
              isAuthenticated: !!refreshedUser,
              isLoading: false,
              error: null,
            });
          } else {
            // Refresh failed, clear tokens
            authApi.clearTokens();
            setState({
              user: null,
              isAuthenticated: false,
              isLoading: false,
              error: null,
            });
          }
        }
      } catch (error) {
        console.error('Auth initialization error:', error);
        authApi.clearTokens();
        setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      }
    };

    initAuth();
  }, []);

  // ---------------------------------------------------------------------------
  // Set up token refresh interval
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!state.isAuthenticated) return;

    // Refresh token every 10 minutes (before 15 min expiry)
    const refreshInterval = setInterval(async () => {
      try {
        await authApi.refreshToken();
      } catch (error) {
        console.error('Token refresh failed:', error);
        // Don't logout immediately, let the next API call handle it
      }
    }, 10 * 60 * 1000); // 10 minutes

    return () => clearInterval(refreshInterval);
  }, [state.isAuthenticated]);

  // ---------------------------------------------------------------------------
  // Login
  // ---------------------------------------------------------------------------
  const login = useCallback(async (credentials: LoginCredentials): Promise<boolean> => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const result = await authApi.login(credentials);

      if (result.success && result.user) {
        setState({
          user: result.user,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
        return true;
      } else {
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: result.error || 'Login failed',
        }));
        return false;
      }
    } catch (error: any) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Login failed',
      }));
      return false;
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Register
  // ---------------------------------------------------------------------------
  const register = useCallback(async (credentials: RegisterCredentials): Promise<boolean> => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const result = await authApi.register(credentials);

      if (result.success && result.user) {
        setState({
          user: result.user,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
        return true;
      } else {
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: result.error || 'Registration failed',
        }));
        return false;
      }
    } catch (error: any) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Registration failed',
      }));
      return false;
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Logout
  // ---------------------------------------------------------------------------
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Refresh user info
  // ---------------------------------------------------------------------------
  const refreshUser = useCallback(async () => {
    try {
      const user = await authApi.getCurrentUser();
      if (user) {
        setState(prev => ({ ...prev, user }));
      }
    } catch (error) {
      console.error('Failed to refresh user:', error);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Clear error
  // ---------------------------------------------------------------------------
  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  // ---------------------------------------------------------------------------
  // Context value
  // ---------------------------------------------------------------------------
  const value: AuthContextType = {
    ...state,
    login,
    register,
    logout,
    refreshUser,
    clearError,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// =============================================================================
// HOOK
// =============================================================================

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
};

// =============================================================================
// PROTECTED ROUTE COMPONENT
// =============================================================================

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredTier?: 'nest' | 'flight' | 'soar' | 'stratosphere';
  fallback?: React.ReactNode;
}

const TIER_LEVELS: Record<string, number> = {
  nest: 0,
  flight: 1,
  soar: 2,
  stratosphere: 3,
  admin: 99,
};

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredTier,
  fallback = null,
}) => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Redirect to login or show fallback
    if (fallback) return <>{fallback}</>;
    
    // Could use react-router-dom's Navigate here
    window.location.href = '/login';
    return null;
  }

  // Check tier if required
  if (requiredTier && user) {
    const userTierLevel = TIER_LEVELS[user.tier] ?? 0;
    const requiredTierLevel = TIER_LEVELS[requiredTier] ?? 0;

    if (userTierLevel < requiredTierLevel) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen">
          <h2 className="text-2xl font-bold mb-4">Upgrade Required</h2>
          <p className="text-gray-600 mb-4">
            This feature requires {requiredTier} tier or higher.
          </p>
          <button
            onClick={() => window.location.href = '/settings/subscription'}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Upgrade Now
          </button>
        </div>
      );
    }
  }

  return <>{children}</>;
};

export default AuthContext;
