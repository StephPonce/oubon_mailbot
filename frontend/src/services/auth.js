/**
 * OSPRA INTELLIGENCE - AUTHENTICATION SERVICE
 * ============================================
 * 
 * Frontend authentication service for React/Vite.
 * Handles JWT tokens, refresh, and secure API calls.
 * 
 * Usage:
 *   import { authService } from '@/services/auth';
 *   
 *   // Login
 *   const result = await authService.login(email, password);
 *   
 *   // Make authenticated API call
 *   const data = await authService.fetch('/api/autopilot/status');
 *   
 *   // Logout
 *   authService.logout();
 * 
 * @author OspraOS
 * @date December 2024
 */

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Token storage keys
const ACCESS_TOKEN_KEY = 'ospra_access_token';
const REFRESH_TOKEN_KEY = 'ospra_refresh_token';
const USER_KEY = 'ospra_user';

// Token refresh threshold (refresh when less than 2 minutes remaining)
const REFRESH_THRESHOLD_MS = 2 * 60 * 1000;


// =============================================================================
// TOKEN UTILITIES
// =============================================================================

/**
 * Parse JWT token payload without verification.
 * Note: Verification happens server-side.
 */
function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error('Failed to parse JWT:', e);
    return null;
  }
}

/**
 * Check if a token is expired or about to expire.
 */
function isTokenExpired(token, thresholdMs = 0) {
  if (!token) return true;
  
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return true;
  
  const expirationMs = payload.exp * 1000;
  const nowMs = Date.now();
  
  return nowMs >= (expirationMs - thresholdMs);
}

/**
 * Get time until token expiration in milliseconds.
 */
function getTokenTimeRemaining(token) {
  if (!token) return 0;
  
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return 0;
  
  const expirationMs = payload.exp * 1000;
  return Math.max(0, expirationMs - Date.now());
}


// =============================================================================
// STORAGE UTILITIES
// =============================================================================

/**
 * Securely store tokens.
 * Uses localStorage for persistence across tabs.
 * 
 * Note: For maximum security, consider:
 * - HttpOnly cookies (requires server changes)
 * - Memory-only storage (loses on refresh)
 */
function storeTokens(accessToken, refreshToken) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function storeUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function getStoredUser() {
  const data = localStorage.getItem(USER_KEY);
  return data ? JSON.parse(data) : null;
}


// =============================================================================
// AUTH SERVICE
// =============================================================================

class AuthService {
  constructor() {
    this._refreshPromise = null;
    this._listeners = new Set();
  }

  // ---------------------------------------------------------------------------
  // Event System
  // ---------------------------------------------------------------------------

  /**
   * Subscribe to auth state changes.
   * @param {Function} callback - Called with { isAuthenticated, user }
   * @returns {Function} Unsubscribe function
   */
  subscribe(callback) {
    this._listeners.add(callback);
    // Immediately notify with current state
    callback(this.getState());
    return () => this._listeners.delete(callback);
  }

  _notify() {
    const state = this.getState();
    this._listeners.forEach(callback => callback(state));
  }

  getState() {
    const token = getAccessToken();
    const isAuthenticated = token && !isTokenExpired(token);
    const user = isAuthenticated ? this.getCurrentUser() : null;
    
    return { isAuthenticated, user };
  }

  // ---------------------------------------------------------------------------
  // Authentication
  // ---------------------------------------------------------------------------

  /**
   * Register a new user.
   */
  async register(name, email, password, tier = 'nest') {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Registration failed');
    }

    // Store tokens and user
    storeTokens(data.access_token, data.refresh_token);
    storeUser(data.user);

    this._notify();

    return data;
  }

  /**
   * Login with email and password.
   */
  async login(email, password) {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    // Store tokens and user
    storeTokens(data.access_token, data.refresh_token);
    storeUser(data.user);

    this._notify();

    return data;
  }

  /**
   * Logout and clear all tokens.
   */
  async logout() {
    const refreshToken = getRefreshToken();

    // Attempt server-side logout (revoke token)
    if (refreshToken) {
      try {
        await fetch(`${API_BASE_URL}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAccessToken()}`,
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch (e) {
        // Ignore errors - still clear local tokens
        console.warn('Server logout failed:', e);
      }
    }

    clearTokens();
    this._notify();
  }

  /**
   * Refresh the access token.
   */
  async refreshAccessToken() {
    // Prevent multiple simultaneous refresh requests
    if (this._refreshPromise) {
      return this._refreshPromise;
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    this._refreshPromise = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        const data = await response.json();

        if (!response.ok) {
          // Refresh token invalid - force logout
          clearTokens();
          this._notify();
          throw new Error(data.detail || 'Token refresh failed');
        }

        // Store new tokens
        storeTokens(data.access_token, data.refresh_token);

        return data.access_token;
      } finally {
        this._refreshPromise = null;
      }
    })();

    return this._refreshPromise;
  }

  // ---------------------------------------------------------------------------
  // User Info
  // ---------------------------------------------------------------------------

  /**
   * Get current user from token.
   */
  getCurrentUser() {
    const token = getAccessToken();
    if (!token) return null;

    const payload = parseJwt(token);
    if (!payload) return null;

    // Merge with stored user data for additional fields
    const storedUser = getStoredUser();

    return {
      user_id: payload.sub,
      email: payload.email,
      tier: payload.tier,
      ...storedUser,
    };
  }

  /**
   * Check if user is authenticated.
   */
  isAuthenticated() {
    const token = getAccessToken();
    return token && !isTokenExpired(token);
  }

  /**
   * Get user's tier.
   */
  getTier() {
    const user = this.getCurrentUser();
    return user?.tier || 'nest';
  }

  /**
   * Check if user has at least the specified tier.
   */
  hasTier(requiredTier) {
    const tierLevels = {
      nest: 0,
      flight: 1,
      soar: 2,
      stratosphere: 3,
      admin: 99,
    };

    const userTier = this.getTier();
    return (tierLevels[userTier] || 0) >= (tierLevels[requiredTier] || 0);
  }

  // ---------------------------------------------------------------------------
  // Authenticated Fetch
  // ---------------------------------------------------------------------------

  /**
   * Make an authenticated API request.
   * Automatically refreshes token if needed.
   */
  async fetch(endpoint, options = {}) {
    let token = getAccessToken();

    // Check if token needs refresh
    if (token && isTokenExpired(token, REFRESH_THRESHOLD_MS)) {
      try {
        token = await this.refreshAccessToken();
      } catch (e) {
        // Refresh failed - redirect to login
        this._notify();
        throw new Error('Session expired. Please login again.');
      }
    }

    if (!token) {
      throw new Error('Not authenticated');
    }

    // Make the request
    const url = endpoint.startsWith('http') 
      ? endpoint 
      : `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
        'Authorization': `Bearer ${token}`,
      },
    });

    // Handle 401 - token might have been revoked
    if (response.status === 401) {
      clearTokens();
      this._notify();
      throw new Error('Session expired. Please login again.');
    }

    return response;
  }

  /**
   * Make an authenticated GET request.
   */
  async get(endpoint, params = {}) {
    const url = new URL(endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, value);
      }
    });

    const response = await this.fetch(url.toString());
    return response.json();
  }

  /**
   * Make an authenticated POST request.
   */
  async post(endpoint, data = {}) {
    const response = await this.fetch(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return response.json();
  }

  /**
   * Make an authenticated PUT request.
   */
  async put(endpoint, data = {}) {
    const response = await this.fetch(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    return response.json();
  }

  /**
   * Make an authenticated DELETE request.
   */
  async delete(endpoint) {
    const response = await this.fetch(endpoint, {
      method: 'DELETE',
    });
    return response.json();
  }
}


// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const authService = new AuthService();

// Also export individual utilities for advanced use
export {
  parseJwt,
  isTokenExpired,
  getTokenTimeRemaining,
  getAccessToken,
  API_BASE_URL,
};
