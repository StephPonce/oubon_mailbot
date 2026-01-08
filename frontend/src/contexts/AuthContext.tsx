// 
// AUTH CONTEXT
// Manages authentication state across the application
// 

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import type { User, LoginCredentials, AuthContextType } from '../types';
import { authApi, getStoredToken, getStoredUser, storeAuth, clearAuth } from '../api/auth';

// Create context with default values
const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => ({ success: false }),
  logout: () => {},
  checkAuth: async () => {},
});

// Hook to use auth context
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Auth Provider component
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check if user is authenticated on mount
  const checkAuth = useCallback(async () => {
    setIsLoading(true);
    
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    // Try to get user from storage first (faster)
    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }

    // Verify token is still valid with backend
    try {
      const response = await authApi.me();
      if (response.success && response.user) {
        setUser(response.user);
      } else {
        // Token invalid, clear storage
        clearAuth();
        setUser(null);
      }
    } catch {
      // Network error - keep user logged in with stored data
      // They can still use cached data
      if (!storedUser) {
        clearAuth();
        setUser(null);
      }
    }
    
    setIsLoading(false);
  }, []);

  // Check auth on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Login function
  const login = useCallback(async (credentials: LoginCredentials) => {
    setIsLoading(true);
    
    const response = await authApi.login(credentials);
    
    if (response.success && response.access_token && response.user) {
      storeAuth(response.access_token, response.user, credentials.remember_me || false);
      setUser(response.user);
      setIsLoading(false);
      return { success: true };
    }
    
    setIsLoading(false);
    return { success: false, error: response.error || 'Login failed' };
  }, []);

  // Logout function
  const logout = useCallback(() => {
    authApi.logout();
    setUser(null);
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    checkAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export default AuthContext;
