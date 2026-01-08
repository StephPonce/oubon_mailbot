/**
 * Intelligence API Service
 * 
 * Handles all communication with the Ospra Intelligence Engine:
 * - Trend discovery
 * - Product analysis
 * - Image generation
 * - Data source status
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface TrendOpportunity {
  id: string;
  trend_keyword: string;
  trend_score: number;
  opportunity_score: number;
  velocity: 'rising' | 'stable' | 'falling';
  category: string;
  source: string;
  matched_products: MatchedProduct[];
  ai_analysis?: string;
  discovered_at: string;
}

export interface MatchedProduct {
  name: string;
  price: number;
  image_url?: string;
  supplier: string;
  orders?: number;
  rating?: number;
  url?: string;
}

export interface ProductAnalysis {
  product_id: string;
  product_name: string;
  ospra_score: number;
  anti_saturation_score: number;
  recommendation: string;
  why_it_will_succeed: string[];
  risk_factors: string[];
  suggested_price: number;
  suggested_niche: string;
  trend_data: Record<string, unknown>;
  social_sentiment: Record<string, unknown>;
  competitor_analysis: Record<string, unknown>;
}

export interface DataSourceStatus {
  total: number;
  connected: number;
  sources: Record<string, { status: string; type: string }>;
}

export interface ImageGenerationResult {
  product_name: string;
  images: string[];
  count: number;
  quality: string;
  generated_at: string;
}

// Helper function for API calls
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('token');
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Discover trending product opportunities
 */
export async function discoverTrends(params?: {
  categories?: string[];
  limit?: number;
  min_trend_score?: number;
}): Promise<TrendOpportunity[]> {
  return apiCall<TrendOpportunity[]>('/api/intelligence/discover', {
    method: 'POST',
    body: JSON.stringify({
      categories: params?.categories || ['smart_home', 'kitchen', 'fitness'],
      limit: params?.limit || 10,
      min_trend_score: params?.min_trend_score || 50,
    }),
  });
}

/**
 * Get currently trending products (quick endpoint)
 */
export async function getTrending(
  category: string = 'all',
  limit: number = 10
): Promise<{ count: number; category: string; trends: TrendOpportunity[]; updated_at: string }> {
  return apiCall(`/api/intelligence/trending?category=${category}&limit=${limit}`);
}

/**
 * Analyze a specific product
 */
export async function analyzeProduct(params: {
  product_name: string;
  product_url?: string;
  supplier_price?: number;
  category?: string;
}): Promise<ProductAnalysis> {
  return apiCall<ProductAnalysis>('/api/intelligence/analyze', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * Generate AI product images
 */
export async function generateProductImages(params: {
  product_name: string;
  style?: 'professional' | 'minimal' | 'luxury' | 'lifestyle';
  quality?: 'premium' | 'standard' | 'bulk';
  count?: number;
}): Promise<ImageGenerationResult> {
  return apiCall<ImageGenerationResult>('/api/intelligence/generate-image', {
    method: 'POST',
    body: JSON.stringify({
      product_name: params.product_name,
      style: params.style || 'professional',
      quality: params.quality || 'standard',
      count: params.count || 1,
    }),
  });
}

/**
 * Get status of all data sources
 */
export async function getDataSources(): Promise<DataSourceStatus> {
  return apiCall<DataSourceStatus>('/api/intelligence/sources');
}

/**
 * Get product rankings
 */
export async function getProductRankings(params?: {
  timeframe?: '7d' | '30d' | 'all';
  category?: string;
  limit?: number;
}): Promise<{ timeframe: string; category: string; rankings: unknown[] }> {
  const query = new URLSearchParams({
    timeframe: params?.timeframe || '7d',
    category: params?.category || 'all',
    limit: String(params?.limit || 20),
  });
  return apiCall(`/api/intelligence/rankings?${query}`);
}

/**
 * Health check for intelligence engine
 */
export async function healthCheck(): Promise<{
  status: string;
  timestamp: string;
  services: Record<string, boolean>;
}> {
  return apiCall('/api/intelligence/health');
}

// Export all functions as a service object
export const intelligenceApi = {
  discoverTrends,
  getTrending,
  analyzeProduct,
  generateProductImages,
  getDataSources,
  getProductRankings,
  healthCheck,
};

export default intelligenceApi;
