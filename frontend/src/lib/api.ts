import axios from 'axios';
import type { Product, DashboardStats, Niche } from '../types';

const API_BASE_URL = 'http://127.0.0.1:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// PRODUCT DISCOVERY API
// ============================================================================

export const productAPI = {
  async getProducts(niche: string, page: number = 1, perPage: number = 20) {
    try {
      const response = await api.get('/api/dashboard/v2/products', {
        params: { niche, page, per_page: perPage },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch products:', error);
      throw error;
    }
  },

  async getStats(niche: string): Promise<DashboardStats> {
    try {
      const response = await api.get('/api/dashboard/v2/overview', {
        params: { niche },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      throw error;
    }
  },

  async getNiches(): Promise<{ niches: Niche[] }> {
    try {
      const response = await api.get('/api/dashboard/v2/niches');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch niches:', error);
      throw error;
    }
  },

  async discoverProducts(niche: string, count: number = 20) {
    try {
      const response = await api.post('/api/v2/discover', {
        niche,
        max_products: count,
        min_score: 40.0
      });
      return response.data;
    } catch (error) {
      console.error('Failed to discover products:', error);
      throw error;
    }
  },
};

// ============================================================================
// SHOPIFY API
// ============================================================================

export interface ShopifyProduct {
  id: number;
  title: string;
  handle: string;
  status: string;
  price: number;
  inventory_quantity: number;
  created_at: string;
  image_url?: string;
  ospra_tracked: boolean;
}

export interface DeployRequest {
  product_id: string;
  name: string;
  niche?: string;
  supplier_cost?: number;
  supplier_url?: string;
  images?: string[];
  description?: string;
  trend_score?: number;
  generate_ai_description?: boolean;
  auto_publish?: boolean;
}

export interface DeployResult {
  success: boolean;
  product_id: string;
  shopify_product_id?: number;
  shopify_url?: string;
  admin_url?: string;
  price?: number;
  error?: string;
  deployed_at?: string;
}

export const shopifyAPI = {
  async getStatus() {
    try {
      // Use the health integrations endpoint instead
      const response = await api.get('/api/health/integrations');
      const shopifyHealth = response.data.shopify;

      // Transform health data to status format
      return {
        configured: shopifyHealth.status !== 'DISCONNECTED',
        store_name: 'Oubon Shop',  // User-friendly store name
        store_domain: 'rxxj7d-1i.myshopify.com',  // From env SHOPIFY_STORE_DOMAIN
        connection: shopifyHealth.status === 'CONNECTED' ? 'active' : 'offline',
        error: shopifyHealth.last_error || undefined,
        latency_ms: shopifyHealth.latency_ms,
        rate_limit: `${shopifyHealth.rate_limit_remaining}/${shopifyHealth.rate_limit_total}`
      };
    } catch (error) {
      console.error('Failed to get Shopify status:', error);
      // Return offline status if health check fails
      return {
        configured: false,
        store_name: 'rxxj7d-1i',
        connection: 'offline',
        error: 'Failed to connect to Shopify'
      };
    }
  },

  async getProducts(limit: number = 50): Promise<ShopifyProduct[]> {
    try {
      const response = await api.get('/api/shopify/products', {
        params: { limit }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch Shopify products:', error);
      throw error;
    }
  },

  async deployProduct(data: DeployRequest): Promise<DeployResult> {
    try {
      const response = await api.post('/api/shopify/deploy', data);
      return response.data;
    } catch (error) {
      console.error('Failed to deploy product:', error);
      throw error;
    }
  },

  async bulkDeploy(products: DeployRequest[]): Promise<DeployResult[]> {
    try {
      const response = await api.post('/api/shopify/deploy/bulk', {
        products,
        max_concurrent: 3
      });
      return response.data;
    } catch (error) {
      console.error('Failed to bulk deploy:', error);
      throw error;
    }
  },

  async deleteProduct(productId: number) {
    try {
      const response = await api.delete(`/api/shopify/products/${productId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to delete product:', error);
      throw error;
    }
  },

  async updateInventory(productId: number, quantity: number) {
    try {
      const response = await api.patch(`/api/shopify/products/${productId}/inventory`, null, {
        params: { quantity }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to update inventory:', error);
      throw error;
    }
  },

  async getAnalytics() {
    try {
      const response = await api.get('/api/shopify/analytics');
      return response.data;
    } catch (error) {
      console.error('Failed to get Shopify analytics:', error);
      throw error;
    }
  },
};

// ============================================================================
// EMAIL API
// ============================================================================

export const emailAPI = {
  async sync() {
    try {
      const response = await api.post('/api/email/sync');
      return response.data;
    } catch (error) {
      console.error('Failed to sync emails:', error);
      throw error;
    }
  },

  async getStats() {
    try {
      const response = await api.get('/analytics/daily');
      return response.data;
    } catch (error) {
      console.error('Failed to get email stats:', error);
      throw error;
    }
  },
};

// ============================================================================
// AI CHAT API
// ============================================================================

export const aiAPI = {
  async chat(message: string, context?: Record<string, unknown>) {
    try {
      const response = await api.post('/api/ai/chat', { message, context });
      return response.data;
    } catch (error) {
      console.error('Failed to chat with AI:', error);
      throw error;
    }
  },

  async getDailyBriefing(date?: string) {
    try {
      const response = await api.get('/api/claude/daily-briefing', {
        params: date ? { date } : {}
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get daily briefing:', error);
      throw error;
    }
  },
};

// ============================================================================
// TRENDS API
// ============================================================================

export const trendsAPI = {
  async getEcommerceTrends() {
    try {
      const response = await api.get('/api/trends/ecommerce');
      return response.data;
    } catch (error) {
      console.error('Failed to get trends:', error);
      throw error;
    }
  },
};

// ============================================================================
// SYSTEM HEALTH API
// ============================================================================

export const systemAPI = {
  async getHealth() {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      console.error('Failed to get health:', error);
      throw error;
    }
  },

  async getApifyStatus() {
    try {
      const response = await api.get('/api/apify/status');
      return response.data;
    } catch (error) {
      console.error('Failed to get Apify status:', error);
      throw error;
    }
  },
};

export default api;
