import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authAPI } from '../services/api';

interface User {
  id: number;
  email: string;
  name: string;
  subscription_tier: string;
  created_at?: string;
  last_login?: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
  tier: string;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check for stored auth token on mount
    const token = localStorage.getItem('ospra_token');
    if (token) {
      fetchUser();
    } else {
      setIsLoading(false);
    }
  }, []);

  const fetchUser = async () => {
    try {
      const response = await authAPI.getProfile();
      setUser(response.user);
    } catch (error) {
      console.error('Failed to fetch user profile:', error);
      // Clear invalid token
      localStorage.removeItem('ospra_token');
      localStorage.removeItem('ospra_user');
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const response = await authAPI.login(email, password);

    // Store tokens
    localStorage.setItem('ospra_token', response.access_token);
    if (response.refresh_token) {
      localStorage.setItem('ospra_refresh_token', response.refresh_token);
    }

    // Set user from response
    setUser(response.user);
  };

  const register = async (email: string, password: string, name: string) => {
    const response = await authAPI.register(email, password, name);

    // Store tokens
    localStorage.setItem('ospra_token', response.access_token);
    if (response.refresh_token) {
      localStorage.setItem('ospra_refresh_token', response.refresh_token);
    }

    // Set user from response
    setUser(response.user);
  };

  const logout = () => {
    // Call logout endpoint (fire and forget)
    authAPI.logout().catch(() => {});

    // Clear local storage
    localStorage.removeItem('ospra_token');
    localStorage.removeItem('ospra_refresh_token');
    localStorage.removeItem('ospra_user');

    // Clear user state
    setUser(null);

    // Redirect to auth page
    window.location.href = '/auth';
  };

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
      tier: user?.subscription_tier || 'nest',
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
