// 
// SHOPIFY API - Store management and data fetching
// 

import { getStoredToken } from './auth';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// ============================================================================
// TYPES
// ============================================================================

export interface ShopifyStore {
  id: number;
  store_name: string;
  store_url: string;
  domain?: string;
  email?: string;
  currency?: string;
  timezone?: string;
  plan?: string;
  status: string;
  last_sync?: string;
  created_at: string;
  error?: string;
}

export interface StoreStats {
  products_count: number;
  orders_count: number;
  customers_count: number;
  revenue_7d: number;
  revenue_30d: number;
  orders_7d: number;
  orders_30d: number;
  avg_order_value: number;
}

export interface ShopifyProduct {
  id: number;
  title: string;
  handle: string;
  status: string;
  vendor?: string;
  product_type?: string;
  created_at: string;
  updated_at: string;
  variants: Array<{
    id: number;
    title: string;
    price: string;
    inventory_quantity?: number;
  }>;
  images: Array<{
    id: number;
    src: string;
  }>;
}

export interface ShopifyOrder {
  id: number;
  order_number: number;
  name: string;
  email?: string;
  total_price: string;
  subtotal_price: string;
  currency: string;
  financial_status: string;
  fulfillment_status?: string;
  created_at: string;
  line_items: Array<{
    id: number;
    title: string;
    quantity: number;
    price: string;
  }>;
}

// ============================================================================
// HELPER
// ============================================================================

async function shopifyFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || error.error || 'Request failed');
  }
  
  return response.json();
}

// ============================================================================
// STORE MANAGEMENT
// ============================================================================

/**
 * List all connected Shopify stores
 */
export async function listStores(): Promise<{
  success: boolean;
  stores: ShopifyStore[];
  count: number;
}> {
  return shopifyFetch('/api/shopify/stores');
}

/**
 * Get details for a specific store
 */
export async function getStore(storeId: number): Promise<{
  success: boolean;
  store: ShopifyStore;
}> {
  return shopifyFetch(`/api/shopify/stores/${storeId}`);
}

/**
 * Disconnect a store
 */
export async function disconnectStore(storeId: number): Promise<{
  success: boolean;
  message: string;
}> {
  return shopifyFetch(`/api/shopify/stores/${storeId}`, {
    method: 'DELETE',
  });
}

/**
 * Get store statistics
 */
export async function getStoreStats(storeId: number): Promise<{
  success: boolean;
  stats: StoreStats;
}> {
  return shopifyFetch(`/api/shopify/stores/${storeId}/stats`);
}

// ============================================================================
// OAUTH
// ============================================================================

/**
 * Initiate OAuth flow for connecting a new store
 */
export async function initiateOAuth(shopDomain: string): Promise<{
  success: boolean;
  authorization_url: string;
  state: string;
}> {
  return shopifyFetch('/api/shopify/oauth/initiate', {
    method: 'POST',
    body: JSON.stringify({ shop_domain: shopDomain }),
  });
}

/**
 * Quick connect using environment credentials (for your own store)
 */
export async function quickConnect(): Promise<{
  success: boolean;
  message: string;
  store_id?: number;
  store?: {
    id: number;
    store_name: string;
    store_url: string;
    currency: string;
  };
}> {
  return shopifyFetch('/api/shopify/quick-connect', {
    method: 'POST',
  });
}

/**
 * Test Shopify connection (no auth required)
 */
export async function testConnection(): Promise<{
  success: boolean;
  store_name?: string;
  store_domain?: string;
  myshopify_domain?: string;
  email?: string;
  currency?: string;
  timezone?: string;
  plan_name?: string;
  error?: string;
}> {
  const response = await fetch(`${API_BASE}/api/shopify/test-connection`);
  return response.json();
}

// ============================================================================
// STORE DATA
// ============================================================================

/**
 * Get products from a store
 */
export async function getProducts(
  storeId: number,
  options: { limit?: number; status?: string } = {}
): Promise<{
  success: boolean;
  products: ShopifyProduct[];
  count: number;
}> {
  const params = new URLSearchParams();
  if (options.limit) params.set('limit', String(options.limit));
  if (options.status) params.set('status', options.status);
  
  const query = params.toString();
  return shopifyFetch(`/api/shopify/stores/${storeId}/products${query ? `?${query}` : ''}`);
}

/**
 * Get orders from a store
 */
export async function getOrders(
  storeId: number,
  options: { limit?: number; status?: string } = {}
): Promise<{
  success: boolean;
  orders: ShopifyOrder[];
  count: number;
}> {
  const params = new URLSearchParams();
  if (options.limit) params.set('limit', String(options.limit));
  if (options.status) params.set('status', options.status);
  
  const query = params.toString();
  return shopifyFetch(`/api/shopify/stores/${storeId}/orders${query ? `?${query}` : ''}`);
}

/**
 * Get customers from a store
 */
export async function getCustomers(
  storeId: number,
  options: { limit?: number } = {}
): Promise<{
  success: boolean;
  customers: Array<{
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
    orders_count: number;
    total_spent: string;
    created_at: string;
  }>;
  count: number;
}> {
  const params = new URLSearchParams();
  if (options.limit) params.set('limit', String(options.limit));
  
  const query = params.toString();
  return shopifyFetch(`/api/shopify/stores/${storeId}/customers${query ? `?${query}` : ''}`);
}

// ============================================================================
// EXPORTS
// ============================================================================

export const shopifyApi = {
  // Store management
  listStores,
  getStore,
  disconnectStore,
  getStoreStats,
  
  // OAuth
  initiateOAuth,
  quickConnect,
  testConnection,
  
  // Data
  getProducts,
  getOrders,
  getCustomers,
};

export default shopifyApi;
