import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';

// ============================================
// CONFIGURATION
// ============================================
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// ============================================
// AXIOS INSTANCE
// ============================================
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('ospra_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle auth errors silently
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('ospra_token');
      localStorage.removeItem('ospra_user');
    }
    return Promise.reject(error);
  }
);

// ============================================
// TYPES
// ============================================
export interface Product {
  id: string;
  name: string;
  image_url: string;
  score: number;
  price: number;
  cost: number;
  profit_margin: number;
  profit?: number;
  estimated_profit?: number;
  trend?: 'up' | 'down' | 'stable';
  trend_value?: string;
  trend_score?: number;
  velocity_score?: number;
  source?: string;
  niche: string;
  niches?: string[];
  saturation_level?: 'low' | 'medium' | 'high';
  sales_velocity?: number;
  social_mentions?: number;
  ai_reason?: string;
  rank?: number;
  previous_rank?: number;
  aliexpress_url?: string;
  supplier_url?: string;
  url?: string;
  created_at?: string;
  updated_at?: string;
  recommendation?: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'AVOID';
  confidence?: number;
  data_sources?: number;
  trend_direction?: 'rising' | 'stable' | 'declining' | 'unknown';
  live_price?: boolean;
  orders?: number;
  rating?: number;
  shipping_cost?: number;
  original_price?: number;
  description?: string;
  aliexpress_id?: string;
  score_breakdown?: {
    tiktok_viral?: number;
    google_trend?: number;
    aliexpress_orders?: number;
    profit_margin?: number;
    supplier_rating?: number;
  };
}

export interface ProductFilters {
  niches?: string[];
  min_score?: number;
  max_score?: number;
  min_profit?: number;
  source?: string;
  sort_by?: 'score' | 'profit' | 'trend' | 'newest';
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface Trend {
  id: string;
  name: string;
  category: string;
  platform: string;
  volume: number;
  change: number;
  velocity: 'rising' | 'falling' | 'stable';
  score: number;
  hashtags?: string[];
  updated_at: string;
}

export interface Niche {
  id: string;
  name: string;
  score?: number;
  saturation?: 'low' | 'medium' | 'high';
  trend?: 'up' | 'down' | 'stable';
  trend_value?: string;
  product_count?: number;
  avg_profit?: number;
  competition?: string;
  trending?: boolean;
  score_avg?: number;
  updated_at?: string;
}

export interface Email {
  id: string;
  subject: string;
  from: string;
  from_address?: string;
  to?: string;
  preview?: string;
  body?: string;
  timestamp?: string;
  date?: string;
  status: 'pending' | 'replied' | 'ignored';
  priority: 'high' | 'medium' | 'low';
  category?: string;
  is_read: boolean;
  auto_replied?: boolean;
  thread_id?: string;
  labels?: string[];
}

// ============================================
// AUTH API
// ============================================
export const authAPI = {
  login: async (email: string, password: string) => {
    const response = await api.post('/api/auth/login', { email, password });
    return response.data;
  },

  register: async (email: string, password: string, name: string) => {
    const response = await api.post('/api/auth/register', { email, password, name });
    return response.data;
  },

  getProfile: async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  logout: async () => {
    const response = await api.post('/api/auth/logout');
    return response.data;
  },
};

// ============================================
// PRODUCTS API
// ============================================
export const productsAPI = {
  getAll: async (filters?: ProductFilters) => {
    const cleanFilters = filters ? Object.fromEntries(
      Object.entries(filters).filter(([_, value]) => value !== undefined)
    ) : {};
    const response = await api.get('/api/dashboard/v2/products', { params: cleanFilters });
    return response.data;
  },

  getById: async (id: string) => {
    const response = await api.get(`/api/dashboard/v2/products/${id}`);
    return response.data;
  },

  discover: async (niches: string[] = ['smart_home'], maxPerNiche = 10) => {
    const response = await api.post('/api/intelligence/discover', {
      niches,
      max_per_niche: maxPerNiche,
    });
    return response.data;
  },

  getRankings: async (limit = 20) => {
    const response = await api.get('/api/rankings/top', { params: { limit } });
    return response.data;
  },

  analyze: async (productId: string, productData?: Product) => {
    const response = await api.post(`/api/dashboard/v2/products/${productId}/analyze`, {
      product_data: productData
    });
    return response.data;
  },

  deployToShopify: async (productId: string, productData?: Product) => {
    try {
      const response = await api.post(`/api/dashboard/v2/products/${productId}/deploy-to-shopify`);
      return { success: true, ...response.data };
    } catch (err) {
      const response = await api.post('/api/shopify/deploy', { product_data: productData });
      return { success: true, ...response.data };
    }
  },

  search: async (query: string) => {
    return productsAPI.getAll({ search: query } as any);
  },

  getRecommendations: async (limit = 10) => {
    const result = await productsAPI.discover(
      ['smart_home', 'tech_gadgets', 'home_security'],
      Math.ceil(limit / 3)
    );
    return {
      products: result.products?.slice(0, limit) || [],
      count: result.count || 0,
    };
  },
};

// ============================================
// TRENDS API
// ============================================
export const trendsAPI = {
  getLive: async () => {
    const response = await api.get('/api/trends/live', { params: { limit: 20 } });
    return response.data.products || [];
  },

  getMovers: async (direction: 'up' | 'down' = 'up', limit = 10) => {
    const response = await api.get('/api/trends/movers', { params: { direction, limit } });
    return response.data.movers || [];
  },

  getBreakouts: async (limit = 10) => {
    const response = await api.get('/api/trends/breakouts');
    return response.data.breakouts?.slice(0, limit) || [];
  },

  getHeatmap: async (rows = 10, cols = 5) => {
    const response = await api.get('/api/trends/heatmap', { params: { rows, cols } });
    return response.data;
  },

  getProductMomentum: async (productId: string) => {
    const response = await api.get(`/api/trends/product/${productId}`);
    return response.data.product || null;
  },

  getByPlatform: async (platform: string) => {
    const response = await api.get('/api/trends/live', { params: { platform } });
    return response.data.products || [];
  },

  getHistory: async (trendId: string, days = 30) => {
    try {
      const response = await api.get(`/api/trends/${trendId}/history`, { params: { days } });
      return response.data;
    } catch {
      return { history: [] };
    }
  },
};

// ============================================
// NICHES API
// ============================================
export const nichesAPI = {
  getAll: async () => {
    const response = await api.get('/api/dashboard/v2/niches');
    return response.data.niches || response.data || [];
  },

  getById: async (id: string) => {
    const response = await api.get(`/api/niches/${id}`);
    return response.data;
  },

  analyze: async (nicheId: string) => {
    const response = await api.post(`/api/niches/${nicheId}/analyze`);
    return response.data;
  },

  getProducts: async (nicheId: string) => {
    const response = await api.get(`/api/niches/${nicheId}/products`);
    return response.data.products || response.data || [];
  },
};

// ============================================
// EMAIL API
// ============================================
export const emailAPI = {
  getAll: async (status?: string) => {
    try {
      const params = status ? { status } : {};
      const response = await api.get('/api/emails', { params });
      return response.data.emails || response.data || [];
    } catch {
      return [];
    }
  },

  getById: async (emailId: string) => {
    const response = await api.get(`/api/emails/${emailId}`);
    return response.data;
  },

  sync: async () => {
    const response = await api.post('/api/emails/sync');
    return response.data;
  },

  reply: async (emailId: string, message: string) => {
    const response = await api.post(`/api/emails/${emailId}/reply`, { message });
    return response.data;
  },

  markAsIgnored: async (emailId: string) => {
    const response = await api.post(`/api/emails/${emailId}/ignore`);
    return response.data;
  },

  markAsRead: async (emailId: string) => {
    const response = await api.post(`/api/emails/${emailId}/read`);
    return response.data;
  },

  getStats: async () => {
    try {
      const response = await api.get('/api/emails/stats');
      return response.data;
    } catch {
      return { total: 0, pending: 0, replied: 0, ignored: 0, auto_replied: 0 };
    }
  },

  getPerformanceMetrics: async () => {
    try {
      const response = await api.get('/api/emails/performance');
      return response.data;
    } catch {
      return { avgResponseTime: 0, autoReplyRate: 0, successRate: 0 };
    }
  },

  getAutoReplySettings: async () => {
    const response = await api.get('/api/emails/auto-reply/settings');
    return response.data;
  },

  updateAutoReplySettings: async (settings: Record<string, unknown>) => {
    const response = await api.put('/api/emails/auto-reply/settings', settings);
    return response.data;
  },
};

// ============================================
// COMPETITORS API
// ============================================
export const competitorsAPI = {
  getAll: async () => {
    try {
      const response = await api.get('/api/competitors');
      return response.data.competitors || [];
    } catch {
      return [];
    }
  },

  getById: async (id: string) => {
    const response = await api.get(`/api/competitors/${id}`);
    return response.data;
  },

  getPriceComparison: async () => {
    try {
      const response = await api.get('/api/competitors/price-comparison');
      return response.data;
    } catch {
      return { comparisons: [] };
    }
  },

  analyze: async (id: string) => {
    const response = await api.post(`/api/competitors/${id}/analyze`);
    return response.data;
  },
};

// ============================================
// A/B TESTING API
// ============================================
export const abTestingAPI = {
  getAll: async () => {
    try {
      const response = await api.get('/api/ab-tests');
      return response.data.tests || [];
    } catch {
      return [];
    }
  },

  getById: async (id: string) => {
    const response = await api.get(`/api/ab-tests/${id}`);
    return response.data;
  },

  getResults: async (id: string) => {
    const response = await api.get(`/api/ab-tests/${id}/results`);
    return response.data;
  },

  create: async (test: any) => {
    const response = await api.post('/api/ab-tests', test);
    return response.data;
  },

  stop: async (id: string) => {
    const response = await api.post(`/api/ab-tests/${id}/stop`);
    return response.data;
  },
};

// ============================================
// SYSTEM API
// ============================================
export const systemAPI = {
  getHealth: async () => {
    try {
      const response = await api.get('/api/health');
      return response.data;
    } catch {
      return { status: 'offline', services: [] };
    }
  },

  getServices: async () => {
    try {
      const response = await api.get('/api/system/services');
      return response.data.services || [];
    } catch {
      return [];
    }
  },
};

// ============================================
// RANKINGS API
// ============================================
export const rankingsAPI = {
  getTop: async (limit = 20, niche?: string) => {
    try {
      const params: any = { limit };
      if (niche) params.niche = niche;
      const response = await api.get('/api/rankings/top', { params });
      return response.data;
    } catch {
      return { rankings: [] };
    }
  },
};

// ============================================
// INTELLIGENCE API (Ospra)
// ============================================
export const intelligenceAPI = {
  chat: async (message: string, context?: any) => {
    const response = await api.post('/api/dashboard/v2/claude/chat', { message, context });
    return {
      message: response.data.response || response.data.message,
      timestamp: response.data.timestamp || new Date().toISOString(),
    };
  },

  chatStream: async (message: string, context?: any, onChunk?: (chunk: string) => void) => {
    const response = await fetch(`${API_BASE_URL}/api/dashboard/v2/claude/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('ospra_token') || ''}`,
      },
      body: JSON.stringify({ message, context, stream: true }),
    });

    if (!response.ok) {
      throw new Error(`Chat failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let fullMessage = '';

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        fullMessage += chunk;
        onChunk?.(chunk);
      }
    }

    return {
      message: fullMessage,
      timestamp: new Date().toISOString(),
    };
  },

  analyzeProduct: async (productId: string, productData?: Product) => {
    const response = await api.post(`/api/dashboard/v2/products/${productId}/analyze`, {
      product_data: productData
    });
    return response.data;
  },

  getPatterns: async (days = 30) => {
    const response = await api.get('/api/dashboard/v2/intelligence/patterns', { params: { days } });
    return response.data;
  },

  getDropCandidates: async (minViews = 100, days = 30) => {
    const response = await api.get('/api/dashboard/v2/intelligence/drop-candidates', {
      params: { min_views: minViews, days }
    });
    return response.data;
  },

  predict: async (product: Product) => {
    const response = await api.post('/api/dashboard/v2/intelligence/predict', product);
    return response.data;
  },

  getConnections: async () => {
    const response = await api.get('/api/intelligence/connections');
    return response.data;
  },

  generateImage: async (productName: string, style = 'professional', count = 1) => {
    const response = await api.post('/api/intelligence/images/generate', {
      product_name: productName,
      style,
      count
    });
    return response.data;
  },

  generateBanner: async (productName: string, campaignType = 'social') => {
    const response = await api.post('/api/intelligence/images/banner', {
      product_name: productName,
      campaign_type: campaignType
    });
    return response.data;
  },

  getInsights: async () => {
    try {
      const response = await api.get('/api/intelligence/insights');
      return response.data.insights || [];
    } catch {
      return [];
    }
  },

  getRecommendations: async () => {
    try {
      const response = await api.get('/api/intelligence/recommendations');
      return response.data.recommendations || [];
    } catch {
      return [];
    }
  },

  getContext: async () => {
    try {
      const response = await api.get('/api/intelligence/context/summary');
      return response.data;
    } catch {
      return {};
    }
  },
};

// ============================================
// SHOPIFY API
// ============================================
export const shopifyAPI = {
  getStatus: async () => {
    const response = await api.get('/api/dashboard/v2/shopify/status');
    return response.data;
  },

  deploy: async (productId: string, productData?: Product) => {
    const response = await api.post(`/api/dashboard/v2/products/${productId}/deploy-to-shopify`);
    return response.data;
  },

  getDeployments: async () => {
    const response = await api.get('/api/dashboard/v2/deployments');
    return response.data;
  },

  getDeploymentStatus: async (productId: string) => {
    const response = await api.get(`/api/dashboard/v2/products/${productId}/deployment-status`);
    return response.data;
  },
};

// ============================================
// ANALYTICS API
// ============================================
export const analyticsAPI = {
  getSummary: async () => {
    const response = await api.get('/api/dashboard/v2/analytics/summary');
    return response.data;
  },

  getBusiness: async () => {
    const response = await api.get('/api/dashboard/v2/analytics/business');
    return response.data;
  },

  getOverview: async () => {
    const response = await api.get('/api/dashboard/v2/overview');
    return response.data;
  },

  getDashboardMetrics: async () => {
    try {
      const response = await api.get('/api/dashboard/v2/analytics/metrics');
      return response.data;
    } catch {
      return { revenue: 0, orders: 0, products: 0, conversionRate: 0 };
    }
  },

  getRevenue: async (period: string) => {
    try {
      const response = await api.get('/api/dashboard/v2/analytics/revenue', { params: { period } });
      return response.data;
    } catch {
      return { total: 0, trend: 0, history: [] };
    }
  },

  getCustomerSegments: async () => {
    try {
      const response = await api.get('/api/dashboard/v2/analytics/customers/segments');
      return response.data;
    } catch {
      return { segments: [] };
    }
  },

  getProductPerformance: async () => {
    try {
      const response = await api.get('/api/dashboard/v2/analytics/products/performance');
      return response.data;
    } catch {
      return { products: [] };
    }
  },

  getConversionFunnel: async () => {
    try {
      const response = await api.get('/api/dashboard/v2/analytics/funnel');
      return response.data;
    } catch {
      return { stages: [] };
    }
  },
};

// ============================================
// NOTIFICATIONS API
// ============================================
export const notificationsAPI = {
  getAll: async (unreadOnly = false, limit = 50) => {
    const response = await api.get('/api/dashboard/v2/notifications', {
      params: { unread_only: unreadOnly, limit }
    });
    return response.data;
  },

  markRead: async (notificationId: number) => {
    const response = await api.post(`/api/dashboard/v2/notifications/${notificationId}/read`);
    return response.data;
  },

  markAllRead: async () => {
    const response = await api.post('/api/dashboard/v2/notifications/mark-all-read');
    return response.data;
  },
};

// ============================================
// ORDERS API
// ============================================
export const ordersAPI = {
  getAll: async (limit = 50) => {
    const response = await api.get('/api/dashboard/v2/orders', { params: { limit } });
    return response.data;
  },

  addTracking: async (orderId: string, trackingNumber: string, trackingUrl: string, trackingCompany = 'Other') => {
    const response = await api.post(`/api/dashboard/v2/orders/${orderId}/tracking`, null, {
      params: { tracking_number: trackingNumber, tracking_url: trackingUrl, tracking_company: trackingCompany }
    });
    return response.data;
  },
};

// ============================================
// SUBSCRIPTION API
// ============================================
export const subscriptionAPI = {
  getCurrentTier: async (userId: number) => {
    try {
      const response = await api.get(`/api/subscription/tier/${userId}`);
      return response.data;
    } catch {
      return {
        tier: 'nest',
        tier_info: {
          name: 'Nest',
          price_monthly: 0,
          price_display: 'Free',
          product_freshness: '30+ days',
          products_per_week: 5,
          store_limit: 1,
          features: ['Basic product discovery', 'Email support']
        }
      };
    }
  },

  getPricing: async () => {
    try {
      const response = await api.get('/api/subscription/pricing');
      return response.data;
    } catch {
      return {
        tiers: [
          { tier: 'nest', name: 'Nest', price_monthly: 0, price_display: 'Free', tagline: 'Get started', features: ['5 products/week', '1 store'] },
          { tier: 'flight', name: 'Flight', price_monthly: 29, price_display: '$29/mo', tagline: 'For growing stores', features: ['20 products/week', '3 stores'] },
          { tier: 'soar', name: 'Soar', price_monthly: 79, price_display: '$79/mo', tagline: 'Scale your business', features: ['50 products/week', '10 stores'] },
          { tier: 'stratosphere', name: 'Stratosphere', price_monthly: 199, price_display: '$199/mo', tagline: 'Enterprise', features: ['Unlimited', 'Priority support'] }
        ]
      };
    }
  },

  upgrade: async (userId: number, tier: string) => {
    const response = await api.post('/api/subscription/upgrade', { user_id: userId, tier });
    return response.data;
  },
};

// ============================================
// USAGE API
// ============================================
export interface UsageDashboard {
  current_usage: {
    products_discovered: number;
    products_deployed: number;
    ai_analyses: number;
    email_responses: number;
  };
  limits: {
    products_per_week: number;
    stores: number;
    ai_analyses_per_day: number;
  };
  period_start: string;
  period_end: string;
}

export const usageAPI = {
  getDashboard: async (userId: number): Promise<UsageDashboard> => {
    try {
      const response = await api.get(`/api/usage/dashboard/${userId}`);
      return response.data;
    } catch {
      return {
        current_usage: { products_discovered: 0, products_deployed: 0, ai_analyses: 0, email_responses: 0 },
        limits: { products_per_week: 5, stores: 1, ai_analyses_per_day: 10 },
        period_start: new Date().toISOString(),
        period_end: new Date().toISOString(),
      };
    }
  },

  trackAction: async (userId: number, action: string) => {
    const response = await api.post('/api/usage/track', { user_id: userId, action });
    return response.data;
  },
};

// ============================================
// PAYMENTS API
// ============================================
export const paymentsAPI = {
  getCheckoutUrl: async (tier: string) => {
    try {
      const response = await api.post('/api/payments/checkout', { tier });
      return response.data;
    } catch {
      // Fallback to hardcoded URLs
      const urls: Record<string, string> = {
        flight: 'https://ospra.lemonsqueezy.com/buy/7f817d94-cf31-4ab6-9ff4-54de583f7920',
        soar: 'https://ospra.lemonsqueezy.com/buy/e1f7dd88-9c08-4486-ac77-be77af8bf976',
        stratosphere: 'https://ospra.lemonsqueezy.com/buy/5d7d273d-f3df-470a-8827-40c3cd975cfc',
      };
      return { checkout_url: urls[tier] || '' };
    }
  },

  getPortalUrl: async (userId: number) => {
    const response = await api.get(`/api/payments/portal/${userId}`);
    return response.data;
  },

  verifyWebhook: async (payload: any) => {
    const response = await api.post('/api/payments/webhook/verify', payload);
    return response.data;
  },
};

// ============================================
// AUTO-DEPLOY API
// ============================================
export interface AutoDeployCriteria {
  min_score: number;
  min_profit_margin: number;
  max_saturation: 'low' | 'medium' | 'high';
  max_per_day: number;
  max_per_hour: number;
  max_daily_cost: number;
  min_trend_velocity: number;
  require_multiple_sources: boolean;
  auto_publish: boolean;
}

export interface AutoDeployStatus {
  enabled: boolean;
  last_run: string | null;
  total_deployed: number;
  total_cost: number;
  criteria: AutoDeployCriteria;
}

export interface DeploymentHistoryItem {
  id: number;
  product_name: string;
  niche: string;
  score: number;
  ai_cost: number;
  success: boolean;
  error?: string;
  deployed_at: string;
  shopify_url?: string;
}

export const autoDeployAPI = {
  getStatus: async (): Promise<AutoDeployStatus> => {
    try {
      const response = await api.get('/api/auto-deploy/status');
      return response.data;
    } catch {
      return {
        enabled: false,
        last_run: null,
        total_deployed: 0,
        total_cost: 0,
        criteria: {
          min_score: 80,
          min_profit_margin: 0.35,
          max_saturation: 'medium',
          max_per_day: 5,
          max_per_hour: 2,
          max_daily_cost: 1.0,
          min_trend_velocity: 70,
          require_multiple_sources: true,
          auto_publish: false,
        },
      };
    }
  },

  getHistory: async (limit = 20): Promise<DeploymentHistoryItem[]> => {
    try {
      const response = await api.get(`/api/auto-deploy/history?limit=${limit}`);
      return response.data.history || [];
    } catch {
      return [];
    }
  },

  enable: async () => {
    const response = await api.post('/api/auto-deploy/enable');
    return response.data;
  },

  disable: async () => {
    const response = await api.post('/api/auto-deploy/disable');
    return response.data;
  },

  runNow: async () => {
    const response = await api.post('/api/auto-deploy/run');
    return response.data;
  },

  updateCriteria: async (criteria: Partial<AutoDeployCriteria>) => {
    const response = await api.put('/api/auto-deploy/criteria', criteria);
    return response.data;
  },
};

// Export the base api instance for custom requests
export { api };
export default api;
