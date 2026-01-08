/**
 * OSPRA INTELLIGENCE - AUTH API CLIENT
 * =====================================
 * 
 * API client for JWT authentication endpoints.
 * 
 * Handles:
 * - Login / Register / Logout
 * - Token storage and refresh
 * - Authenticated API requests
 * 
 * Author: OspraOS
 * Date: December 2024
 */

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// =============================================================================
// TYPES
// =============================================================================

export interface User {
  user_id: string;
  email: string;
  tier: 'nest' | 'flight' | 'soar' | 'stratosphere' | 'admin';
  created_at: string;
  updated_at?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  password: string;
  tier?: string;
}

export interface AuthResult {
  success: boolean;
  user?: User;
  tokens?: AuthTokens;
  error?: string;
}

// =============================================================================
// TOKEN MANAGEMENT
// =============================================================================

const getAccessToken = (): string | null => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

const setTokens = (tokens: AuthTokens): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
};

const clearTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

// =============================================================================
// API CLIENT
// =============================================================================

/**
 * Make an authenticated API request
 */
const apiRequest = async <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> => {
  const accessToken = getAccessToken();
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (accessToken) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 - try refresh
  if (response.status === 401 && accessToken) {
    const refreshed = await refreshToken();
    
    if (refreshed) {
      // Retry with new token
      const newToken = getAccessToken();
      (headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`;
      
      const retryResponse = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
      });
      
      if (!retryResponse.ok) {
        throw new Error(`API Error: ${retryResponse.status}`);
      }
      
      return retryResponse.json();
    } else {
      // Refresh failed, clear tokens
      clearTokens();
      throw new Error('Session expired. Please login again.');
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json();
};

// =============================================================================
// AUTH FUNCTIONS
// =============================================================================

/**
 * Login with email and password
 */
const login = async (credentials: LoginCredentials): Promise<AuthResult> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: data.detail || 'Login failed',
      };
    }

    // Store tokens
    setTokens({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: data.token_type,
      expires_in: data.expires_in,
    });

    return {
      success: true,
      user: data.user,
      tokens: data,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || 'Network error',
    };
  }
};

/**
 * Register a new user
 */
const register = async (credentials: RegisterCredentials): Promise<AuthResult> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: data.detail || 'Registration failed',
      };
    }

    // Store tokens
    setTokens({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: data.token_type,
      expires_in: data.expires_in,
    });

    return {
      success: true,
      user: data.user,
      tokens: data,
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || 'Network error',
    };
  }
};

/**
 * Logout (revoke tokens)
 */
const logout = async (): Promise<void> => {
  try {
    const refreshTokenValue = getRefreshToken();
    
    if (refreshTokenValue) {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({ refresh_token: refreshTokenValue }),
      });
    }
  } catch (error) {
    console.error('Logout error:', error);
  } finally {
    clearTokens();
  }
};

/**
 * Refresh the access token
 */
const refreshToken = async (): Promise<boolean> => {
  try {
    const refreshTokenValue = getRefreshToken();
    
    if (!refreshTokenValue) {
      return false;
    }

    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshTokenValue }),
    });

    if (!response.ok) {
      clearTokens();
      return false;
    }

    const data = await response.json();
    
    setTokens({
      access_token: data.access_token,
      refresh_token: data.refresh_token || refreshTokenValue,
      token_type: data.token_type,
      expires_in: data.expires_in,
    });

    return true;
  } catch (error) {
    console.error('Token refresh error:', error);
    clearTokens();
    return false;
  }
};

/**
 * Get current user info
 */
const getCurrentUser = async (): Promise<User | null> => {
  try {
    const accessToken = getAccessToken();
    
    if (!accessToken) {
      return null;
    }

    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch (error) {
    console.error('Get user error:', error);
    return null;
  }
};

/**
 * Change password
 */
const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<{ success: boolean; error?: string }> => {
  try {
    const response = await apiRequest<{ success: boolean }>('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });

    return { success: true };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || 'Failed to change password',
    };
  }
};

// =============================================================================
// AUTHENTICATED API HELPERS
// =============================================================================

/**
 * Make a GET request with authentication
 */
const get = async <T>(endpoint: string): Promise<T> => {
  return apiRequest<T>(endpoint, { method: 'GET' });
};

/**
 * Make a POST request with authentication
 */
const post = async <T>(endpoint: string, data?: any): Promise<T> => {
  return apiRequest<T>(endpoint, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  });
};

/**
 * Make a PUT request with authentication
 */
const put = async <T>(endpoint: string, data?: any): Promise<T> => {
  return apiRequest<T>(endpoint, {
    method: 'PUT',
    body: data ? JSON.stringify(data) : undefined,
  });
};

/**
 * Make a DELETE request with authentication
 */
const del = async <T>(endpoint: string): Promise<T> => {
  return apiRequest<T>(endpoint, { method: 'DELETE' });
};

// =============================================================================
// EXPORT
// =============================================================================

export const authApi = {
  // Auth functions
  login,
  register,
  logout,
  refreshToken,
  getCurrentUser,
  changePassword,
  
  // Token management
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  
  // Authenticated requests
  get,
  post,
  put,
  delete: del,
  request: apiRequest,
};

export default authApi;
