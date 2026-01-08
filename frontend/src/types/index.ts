// 
// OSPRA INTELLIGENCE V5 - TYPE DEFINITIONS
// 

// User type - handles both `tier` and `subscription_tier` from backend
export interface User {
  id: number;
  email: string;
  name?: string;
  username?: string;  // Legacy alias for name
  tier?: string;      // Subscription tier: nest, flight, soar, stratosphere
  subscription_tier?: string; // Backend returns this
  created_at?: string;
  last_login?: string;
}

// Auth types
export interface LoginCredentials {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterCredentials {
  email: string;
  password: string;
  name?: string;
  username?: string;  // Legacy alias
}

export interface AuthResponse {
  success: boolean;
  access_token?: string;
  token_type?: string;
  user?: User;
  error?: string;
  detail?: string;
}

// Auth context type
export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}
