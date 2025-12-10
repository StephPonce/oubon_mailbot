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
    // Don't log 404s here - handled by safeApiCall
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
  trend: 'up' | 'down' | 'stable';
  trend_value: string;
  trend_score?: number;
  velocity_score?: number;
  source: string;
  niche: string;
  niches?: string[];
  saturation_level: 'low' | 'medium' | 'high';
  sales_velocity?: number;
  social_mentions?: number;
  ai_reason?: string;
  rank?: number;
  previous_rank?: number;
  aliexpress_url?: string;
  created_at?: string;
  updated_at?: string;
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
  score: number;
  saturation: 'low' | 'medium' | 'high';
  trend: 'up' | 'down' | 'stable';
  trend_value: string;
  product_count: number;
  avg_profit: number;
  competition: string;
  updated_at: string;
}

// ============================================
// AUTH API (✅ All endpoints exist)
// ============================================
export const authAPI = {
  // POST /api/auth/login
  login: async (email: string, password: string) => {
    const response = await api.post('/api/auth/login', { email, password });
    return response.data;
  },

  // POST /api/auth/register
  register: async (email: string, password: string, name: string) => {
    const response = await api.post('/api/auth/register', { email, password, name });
    return response.data;
  },

  // GET /api/auth/me
  getProfile: async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  // POST /api/auth/logout
  logout: async () => {
    const response = await api.post('/api/auth/logout');
    return response.data;
  },
};

// ============================================
// PRODUCTS API (✅ All endpoints exist)
// ============================================
export const productsAPI = {
  // GET /api/dashboard/v2/products
  getAll: async (filters?: ProductFilters) => {
    const response = await api.get('/api/dashboard/v2/products', { params: filters });
    return response.data;
  },

  // GET /api/dashboard/v2/products/{id}
  getById: async (id: string) => {
    const response = await api.get(`/api/dashboard/v2/products/${id}`);
    return response.data;
  },

  // POST /api/intelligence/discover
  discover: async (niches: string[] = ['smart_home'], maxPerNiche = 10) => {
    const response = await api.post('/api/intelligence/discover', {
      niches,
      max_per_niche: maxPerNiche,
    });
    return response.data;
  },

  // GET /api/rankings/top
  getRankings: async (limit = 20) => {
    const response = await api.get('/api/rankings/top', { params: { limit } });
    return response.data;
  },

  // POST /api/dashboard/v2/products/{id}/analyze
  analyze: async (productId: string) => {
    const response = await api.post(`/api/dashboard/v2/products/${productId}/analyze`);
    return response.data;
  },

  // POST /api/shopify/deploy (✅ exists)
  deployToShopify: async (productData: any) => {
    const response = await api.post('/api/shopify/deploy', { product_data: productData });
    return response.data;
  },

  // Search - uses getAll with search param
  search: async (query: string) => {
    return productsAPI.getAll({ search: query } as any);
  },

  // Recommendations - uses discovery
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
// TRENDS API (✅ All endpoints exist)
// ============================================
export const trendsAPI = {
  // GET /api/trends/live (✅ exists)
  getLive: async () => {
    const response = await api.get('/api/trends/live', { params: { limit: 20 } });
    return response.data.products || [];
  },

  // GET /api/trends/movers (✅ exists)
  getMovers: async (direction: 'up' | 'down' = 'up', limit = 10) => {
    const response = await api.get('/api/trends/movers', { params: { direction, limit } });
    return response.data.movers || [];
  },

  // GET /api/trends/breakouts (✅ exists)
  getBreakouts: async (limit = 10) => {
    const response = await api.get('/api/trends/breakouts');
    return response.data.breakouts?.slice(0, limit) || [];
  },

  // GET /api/trends/heatmap (✅ exists)
  getHeatmap: async (rows = 10, cols = 5) => {
    const response = await api.get('/api/trends/heatmap', { params: { rows, cols } });
    return response.data;
  },

  // GET /api/trends/product/{id} (✅ exists)
  getProductMomentum: async (productId: string) => {
    const response = await api.get(`/api/trends/product/${productId}`);
    return response.data.product || null;
  },

  // Get by platform - uses live with filter
  getByPlatform: async (platform: string) => {
    const response = await api.get('/api/trends/live', { params: { platform } });
    return response.data.products || [];
  },

  // History - not implemented yet
  getHistory: async (trendId: string, days = 30) => {
    throw new Error('GET /api/trends/history not implemented');
  },
};

// ============================================
// NICHES API (✅ All endpoints exist via frontend_compat)
// ============================================
export const nichesAPI = {
  // GET /api/niches (✅ exists via frontend_compat)
  getAll: async () => {
    const response = await api.get('/api/niches');
    return response.data.niches || response.data || [];
  },

  // GET /api/niches/{id} (✅ exists)
  getById: async (id: string) => {
    const response = await api.get(`/api/niches/${id}`);
    return response.data;
  },

  // POST /api/niches/{id}/analyze (✅ exists)
  analyze: async (nicheId: string) => {
    const response = await api.post(`/api/niches/${nicheId}/analyze`);
    return response.data;
  },

  // GET /api/niches/{id}/products (✅ exists via frontend_compat)
  getProducts: async (nicheId: string) => {
    const response = await api.get(`/api/niches/${nicheId}/products`);
    return response.data.products || response.data || [];
  },
};

// ============================================
// INTELLIGENCE API (Ospra) (✅ All endpoints exist)
// ============================================
export const intelligenceAPI = {
  // POST /api/dashboard/v2/claude/chat (✅ exists)
  chat: async (message: string, context?: any) => {
    const response = await api.post('/api/dashboard/v2/claude/chat', { message, context });
    return {
      message: response.data.response || response.data.message,
      timestamp: response.data.timestamp || new Date().toISOString(),
    };
  },

  // POST /api/dashboard/v2/claude/chat with streaming
  chatStream: async (message: string, context?: any, onChunk?: (chunk: string) => void) => {
    const response = await fetch(`${API_BASE_URL}/api/dashboard/v2/claude/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('ospra_token')}`,
      },
      body: JSON.stringify({ message, context }),
    });

    if (!response.ok) {
      throw new Error('Chat failed');
    }

    const data = await response.json();
    const fullMessage = data.response || '';

    // Simulate streaming
    if (onChunk && fullMessage) {
      const words = fullMessage.split(' ');
      for (let i = 0; i < words.length; i++) {
        await new Promise(resolve => setTimeout(resolve, 30));
        onChunk(words.slice(0, i + 1).join(' '));
      }
    }

    return fullMessage;
  },

  // GET /api/intelligence/briefing/morning (✅ exists)
  getInsights: async () => {
    const response = await api.get('/api/intelligence/briefing/morning');
    const briefing = response.data;
    const insights = briefing.attention_items?.map((item: any, idx: number) => ({
      id: `insight-${idx}`,
      type: item.priority === 'high' ? 'warning' : item.priority === 'medium' ? 'opportunity' : 'success',
      title: item.title || item.item,
      description: item.description || item.details,
      action: item.action_label,
    })) || [];
    return { insights, briefing: briefing.briefing_text };
  },

  // POST /api/intelligence/analyze/product/{id} (✅ exists via frontend_compat)
  analyzeProduct: async (productId: string) => {
    const response = await api.post(`/api/intelligence/analyze/product/${productId}`);
    return response.data;
  },

  // POST /api/intelligence/analyze/niche/{id} (✅ exists via frontend_compat)
  analyzeNiche: async (nicheId: string) => {
    const response = await api.post(`/api/intelligence/analyze/niche/${nicheId}`);
    return response.data;
  },

  // POST /api/recommendations/smart (✅ exists)
  getRecommendations: async () => {
    const response = await api.post('/api/recommendations/smart', { user_id: 1, max_products: 10 });
    return response.data;
  },

  // POST /api/reports/generate (✅ exists via frontend_compat)
  generateReport: async (type: 'daily' | 'weekly' | 'monthly') => {
    const response = await api.post('/api/reports/generate', { report_type: type });
    return response.data;
  },

  // Get context for AI
  getContext: async () => {
    const [metrics, products] = await Promise.all([
      api.get('/api/dashboard/overview'),
      api.post('/api/intelligence/discover', { niches: ['smart_home'], max_per_niche: 5 }),
    ]);
    return {
      metrics: metrics.data,
      products: products.data.products?.slice(0, 5) || [],
    };
  },
};

// ============================================
// ANALYTICS API (⚠️ Some endpoints return demo data)
// ============================================
export const analyticsAPI = {
  // GET /api/dashboard/v2/overview (✅ exists, returns real data)
  getDashboardMetrics: async () => {
    const response = await api.get('/api/dashboard/v2/overview');
    return response.data;
  },

  // GET /api/analytics/revenue (✅ exists)
  getRevenue: async (period: 'day' | 'week' | 'month' | 'quarter' | 'year' = 'month') => {
    const response = await api.get('/api/analytics/revenue', { params: { period } });
    return response.data.data || response.data || [];
  },

  // GET /api/customers/segments (✅ exists)
  getCustomerSegments: async () => {
    const response = await api.get('/api/customers/segments');
    return response.data.segments || response.data || [];
  },

  // GET /api/analytics/products/performance (✅ exists via frontend_compat, returns demo data)
  getProductPerformance: async () => {
    const response = await api.get('/api/analytics/products/performance');
    return response.data;
  },

  // GET /api/analytics/funnel (✅ exists via frontend_compat, returns demo data)
  getConversionFunnel: async () => {
    const response = await api.get('/api/analytics/funnel');
    return response.data.funnel || response.data || [];
  },
};

// ============================================
// COMPETITORS API (⚠️ List endpoint may not exist)
// ============================================
export const competitorsAPI = {
  // GET /api/competitors (❌ may not exist - check backend)
  getAll: async () => {
    const response = await api.get('/api/competitors');
    return response.data.competitors || response.data || [];
  },

  // GET /api/competitors/{id} (✅ exists)
  getById: async (id: string) => {
    const response = await api.get(`/api/competitors/${id}`);
    return response.data;
  },

  // POST /api/competitors/{id}/analyze (✅ exists via frontend_compat)
  analyze: async (competitorId: string) => {
    const response = await api.post(`/api/competitors/${competitorId}/analyze`);
    return response.data;
  },

  // GET /api/competitors/prices (✅ exists via frontend_compat)
  getPriceComparison: async () => {
    const response = await api.get('/api/competitors/prices');
    return response.data;
  },
};

// ============================================
// EMAIL API (✅ All endpoints exist)
// ============================================
export const emailAPI = {
  // GET /api/emails/recent (✅ exists)
  getAll: async (status?: string) => {
    const response = await api.get('/api/emails/recent', { params: { status, limit: 50 } });
    return response.data.emails || response.data || [];
  },

  // GET /api/dashboard/emails (✅ exists)
  getStats: async () => {
    const response = await api.get('/api/dashboard/emails');
    return response.data;
  },

  // GET /api/emails/stats/weekly (✅ exists)
  getWeeklyStats: async () => {
    const response = await api.get('/api/emails/stats/weekly');
    return response.data;
  },

  // GET /api/emails/stats/categories (✅ exists)
  getCategories: async (days = 7) => {
    const response = await api.get('/api/emails/stats/categories', { params: { days } });
    return response.data;
  },

  // GET /api/emails/stats/performance (✅ exists)
  getPerformanceMetrics: async () => {
    const response = await api.get('/api/emails/stats/performance');
    return response.data;
  },

  // POST /api/emails/messages/{id}/reply (✅ exists via frontend_compat)
  reply: async (emailId: string, message: string) => {
    const response = await api.post(`/api/emails/messages/${emailId}/reply`, { message });
    return response.data;
  },

  // POST /api/emails/messages/{id}/ignore (✅ exists via frontend_compat)
  markAsIgnored: async (emailId: string) => {
    const response = await api.post(`/api/emails/messages/${emailId}/ignore`);
    return response.data;
  },

  // POST /api/emails/sync (✅ exists)
  sync: async () => {
    const response = await api.post('/api/emails/sync');
    return response.data;
  },
};

// ============================================
// A/B TESTING API (✅ All endpoints exist)
// ============================================
export const abTestingAPI = {
  // GET /api/abtesting/tests (✅ exists)
  getAll: async () => {
    const response = await api.get('/api/abtesting/tests');
    return response.data.tests || response.data || [];
  },

  // GET /api/abtesting/tests/{id} (✅ exists)
  getById: async (id: string) => {
    const response = await api.get(`/api/abtesting/tests/${id}`);
    return response.data;
  },

  // POST /api/abtesting/tests (✅ exists)
  create: async (test: any) => {
    const response = await api.post('/api/abtesting/tests', test);
    return response.data;
  },

  // POST /api/abtesting/tests/{id}/pause (✅ exists)
  pause: async (id: string) => {
    const response = await api.post(`/api/abtesting/tests/${id}/pause`);
    return response.data;
  },

  // POST /api/abtesting/tests/{id}/resume (✅ exists)
  resume: async (id: string) => {
    const response = await api.post(`/api/abtesting/tests/${id}/resume`);
    return response.data;
  },

  // GET /api/abtesting/tests/{id}/results (✅ exists)
  getResults: async (id: string) => {
    const response = await api.get(`/api/abtesting/tests/${id}/results`);
    return response.data;
  },
};

// ============================================
// SYSTEM API (✅ All endpoints exist)
// ============================================
export const systemAPI = {
  // GET /health (✅ exists)
  getHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  // GET /api/health/detailed (✅ exists)
  getServices: async () => {
    const response = await api.get('/api/health/detailed');
    return response.data;
  },

  // Service refresh - not implemented
  refreshService: async (serviceName: string) => {
    throw new Error('POST /api/system/services/refresh not implemented');
  },
};

// ============================================
// SHOPIFY API (✅ All endpoints exist)
// ============================================
export interface DeployRequest {
  product_id: string;
  name: string;
  niche?: string;
  supplier_cost?: number;
  supplier_url?: string;
  images?: string[];
  description?: string;
  trend_score?: number;
  features?: string[];

  // AI Control Flags
  ai_content?: boolean;
  ai_images?: boolean;
  ai_pricing?: boolean;
  ai_seo?: boolean;
  publish?: boolean;

  // Deployment Options
  target_margin?: number;
  add_branding?: boolean;
  max_images?: number;

  // Legacy support
  generate_ai_description?: boolean;
  auto_publish?: boolean;
}

export interface DeployResult {
  success: boolean;
  product_id: string;
  shopify_product_id?: string;
  shopify_url?: string;
  admin_url?: string;
  price?: string;
  error?: string;

  // AI Metrics
  content_generated?: {
    title: string;
    description: string;
    tags: string[];
  };
  images_enhanced?: number;
  ai_costs?: {
    content: number;
    images: number;
    total: number;
  };
  total_cost?: number;
  processing_time_seconds?: number;
  published?: boolean;
}

export interface ShopifyProduct {
  id: number;
  title: string;
  price: string;
  inventory_quantity: number;
  image_url?: string;
  ospra_tracked?: boolean;
  created_at?: string;
}

export interface ShopifyStatus {
  configured: boolean;
  store_name: string;
  store_domain?: string;
  connection: string;
  error?: string;
}

export interface ShopifyAnalytics {
  total_products: number;
  total_inventory: number;
  estimated_value: number;
  ospra_tracked: number;
}

export const shopifyAPI = {
  // GET /api/shopify/status (✅ exists)
  getStatus: async (): Promise<ShopifyStatus> => {
    const response = await api.get('/api/shopify/status');
    return response.data;
  },

  // GET /api/shopify/products (✅ exists)
  getProducts: async (limit = 50): Promise<ShopifyProduct[]> => {
    const response = await api.get('/api/shopify/products', { params: { limit } });
    return response.data.products || [];
  },

  // GET /api/shopify/analytics (✅ exists)
  getAnalytics: async (): Promise<ShopifyAnalytics> => {
    const response = await api.get('/api/shopify/analytics');
    return response.data;
  },

  // POST /api/shopify/deploy (✅ enhanced with AI)
  deployProduct: async (request: DeployRequest): Promise<DeployResult> => {
    const response = await api.post('/api/shopify/deploy', request);
    return response.data;
  },

  // POST /api/shopify/deploy/preview (✅ new endpoint)
  previewDeployment: async (request: DeployRequest): Promise<DeployResult> => {
    const response = await api.post('/api/shopify/deploy/preview', request);
    return response.data;
  },

  // DELETE /api/shopify/products/{id} (✅ exists)
  deleteProduct: async (productId: number): Promise<void> => {
    await api.delete(`/api/shopify/products/${productId}`);
  },

  // POST /api/shopify/bulk-deploy (✅ exists)
  bulkDeploy: async (products: DeployRequest[]): Promise<{ deployed: number; failed: number }> => {
    const response = await api.post('/api/shopify/bulk-deploy', { products });
    return response.data;
  },
};

// ============================================
// AUTO-DEPLOYMENT API (✅ All endpoints exist)
// ============================================
export interface AutoDeployCriteria {
  min_score?: number;
  min_profit_margin?: number;
  max_saturation?: 'low' | 'medium' | 'high';
  allowed_niches?: string[];
  max_per_day?: number;
  max_per_hour?: number;
  max_daily_cost?: number;
  require_multiple_sources?: boolean;
  min_trend_velocity?: number;
  auto_publish?: boolean;
}

export interface AutoDeployStatus {
  enabled: boolean;
  criteria: AutoDeployCriteria;
  last_run: string | null;
  total_deployed: number;
  total_cost: number;
}

export interface DeploymentHistoryItem {
  id: number;
  product_name: string;
  niche: string;
  score: number;
  shopify_url: string | null;
  success: boolean;
  error: string | null;
  ai_cost: number;
  deployed_at: string;
}

export interface RunNowResponse {
  success: boolean;
  deployed: number;
  failed: number;
  total_cost: number;
  message: string;
}

export const autoDeployAPI = {
  // GET /api/auto-deploy/status (✅ exists)
  getStatus: async (): Promise<AutoDeployStatus> => {
    const response = await api.get('/api/auto-deploy/status');
    return response.data;
  },

  // POST /api/auto-deploy/enable (✅ exists)
  enable: async (): Promise<{ success: boolean; message: string; criteria: AutoDeployCriteria }> => {
    const response = await api.post('/api/auto-deploy/enable');
    return response.data;
  },

  // POST /api/auto-deploy/disable (✅ exists)
  disable: async (): Promise<{ success: boolean; message: string }> => {
    const response = await api.post('/api/auto-deploy/disable');
    return response.data;
  },

  // PUT /api/auto-deploy/criteria (✅ exists)
  updateCriteria: async (criteria: Partial<AutoDeployCriteria>): Promise<{ success: boolean; criteria: AutoDeployCriteria }> => {
    const response = await api.put('/api/auto-deploy/criteria', criteria);
    return response.data;
  },

  // GET /api/auto-deploy/history (✅ exists)
  getHistory: async (limit = 50): Promise<DeploymentHistoryItem[]> => {
    const response = await api.get('/api/auto-deploy/history', { params: { limit } });
    return response.data;
  },

  // POST /api/auto-deploy/run-now (✅ exists)
  runNow: async (): Promise<RunNowResponse> => {
    const response = await api.post('/api/auto-deploy/run-now');
    return response.data;
  },

  // GET /api/auto-deploy/health (✅ exists)
  getHealth: async (): Promise<{ status: string; deployer_initialized: boolean; database_connected: boolean }> => {
    const response = await api.get('/api/auto-deploy/health');
    return response.data;
  },
};

// ============================================
// IMAGE ENHANCEMENT API (✅ All endpoints exist)
// ============================================
export interface ImageEnhanceRequest {
  product_id: string;
  image_url: string;
}

export interface ImageEnhanceResult {
  success: boolean;
  enhanced_url?: string;
  original_url: string;
  processing_time?: number;
  cost: number;
  error?: string;
}

export interface BatchEnhanceRequest {
  products: ImageEnhanceRequest[];
}

export interface BatchEnhanceResult {
  results: ImageEnhanceResult[];
  total_cost: number;
  succeeded: number;
  failed: number;
}

export const imageEnhanceAPI = {
  // POST /api/images/enhance-product (✅ exists)
  enhanceProduct: async (request: ImageEnhanceRequest): Promise<ImageEnhanceResult> => {
    const response = await api.post('/api/images/enhance-product', request);
    return response.data;
  },

  // POST /api/images/enhance-batch (✅ exists)
  enhanceBatch: async (products: ImageEnhanceRequest[]): Promise<BatchEnhanceResult> => {
    const response = await api.post('/api/images/enhance-batch', { products });
    return response.data;
  },
};

// ============================================
// RANKINGS API
// ============================================
export const rankingsAPI = {
  // GET /api/rankings/top (✅ exists)
  getTop: async (limit: number = 20, niche?: string) => {
    const params: any = { limit };
    if (niche) params.niche = niche;
    const response = await api.get('/api/rankings/top', { params });
    return response.data;
  },
};

// Export as both default and named export for backwards compatibility
export default api;
export const apiClient = api;
