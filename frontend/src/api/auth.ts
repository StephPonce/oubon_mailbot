// 
// AUTH API SERVICE
// Handles all authentication API calls
// Fixed: Maps subscription_tier to tier for frontend
// 

import type { LoginCredentials, AuthResponse, User } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Storage keys
const TOKEN_KEY = 'ospra_token';
const USER_KEY = 'ospra_user';
const REMEMBER_KEY = 'ospra_remember';

// 
// USER NORMALIZATION
// 

/**
 * Normalize user object from backend
 * Maps subscription_tier -> tier for consistency
 */
function normalizeUser(data: any): User {
  if (!data) return data;
  
  return {
    id: data.id,
    email: data.email,
    name: data.name || data.username,
    // Map subscription_tier to tier (backend uses subscription_tier)
    tier: data.tier || data.subscription_tier || 'nest',
    created_at: data.created_at,
    last_login: data.last_login,
  };
}

// 
// TOKEN MANAGEMENT
// 

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  const userStr = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
  return null;
}

export function storeAuth(token: string, user: User, rememberMe: boolean): void {
  const storage = rememberMe ? localStorage : sessionStorage;
  storage.setItem(TOKEN_KEY, token);
  storage.setItem(USER_KEY, JSON.stringify(user));
  if (rememberMe) {
    localStorage.setItem(REMEMBER_KEY, 'true');
  }
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(REMEMBER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function wasRemembered(): boolean {
  return localStorage.getItem(REMEMBER_KEY) === 'true';
}

// 
// ERROR PARSING HELPER
// 

function parseErrorMessage(data: any, fallback: string = 'An error occurred'): string {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  
  if (data?.error?.message && typeof data.error.message === 'string') {
    return data.error.message;
  }
  
  if (data?.detail && typeof data.detail === 'string') {
    return data.detail;
  }
  
  if (data?.message && typeof data.message === 'string') {
    return data.message;
  }
  
  if (data?.error && typeof data.error === 'string') {
    return data.error;
  }
  
  return fallback;
}

// 
// AUTH API
// 

export const authApi = {
  // Register new user
  register: async (credentials: { name: string; email: string; password: string; tier?: string }): Promise<AuthResponse> => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      });
      
      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: parseErrorMessage(data, 'Registration failed'),
        };
      }
      
      return {
        success: true,
        access_token: data.access_token,
        token_type: data.token_type,
        user: normalizeUser(data.user),
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
      };
    }
  },

  // Login
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: credentials.email,
          password: credentials.password,
        }),
      });
      
      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: parseErrorMessage(data, 'Login failed'),
        };
      }
      
      return {
        success: true,
        access_token: data.access_token,
        token_type: data.token_type,
        user: normalizeUser(data.user) || { id: 1, email: credentials.email, tier: 'nest' },
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
      };
    }
  },

  // Forgot password
  forgotPassword: async (email: string): Promise<{ success: boolean; error?: string }> => {
    try {
      await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
      };
    }
  },

  // Verify reset token
  verifyResetToken: async (token: string): Promise<{ valid: boolean }> => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/verify-reset-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      const data = await response.json();
      return { valid: data.valid || false };
    } catch {
      return { valid: false };
    }
  },

  // Reset password
  resetPassword: async (token: string, newPassword: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        return {
          success: false,
          error: parseErrorMessage(data, 'Failed to reset password'),
        };
      }
      
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
      };
    }
  },
  
  // Get current user
  me: async (): Promise<{ success: boolean; user?: User; error?: string }> => {
    try {
      const token = getStoredToken();
      if (!token) {
        return { success: false, error: 'No token' };
      }
      
      const response = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        return {
          success: false,
          error: parseErrorMessage(data, 'Session expired'),
        };
      }
      
      // Handle nested user object from /me endpoint and normalize
      return { success: true, user: normalizeUser(data.user || data) };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Session expired',
      };
    }
  },
  
  // Logout
  logout: (): void => {
    clearAuth();
  },
};

export default authApi;
