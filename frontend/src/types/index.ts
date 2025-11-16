export interface Product {
  id: string;
  name: string;
  category: string;
  niche: string;
  price: number;
  cost: number;
  shipping_cost?: number;
  shopify_fee?: number;
  total_costs?: number;
  score: number;
  profit_margin: number;
  rating: number;
  orders: number;
  image_url?: string;
  aliexpress_url?: string;
  supplier_url?: string;
  description?: string;
  ai_analysis?: string;
  features?: string[];
  estimated_profit?: number;
  velocity_score?: number;  // Can be at root level OR in market_intelligence
  market_intelligence?: {
    ai_analysis: string;
    google_trends: {
      average_interest: number;
      current_interest: number;
      trend_direction: string;
    };
    demand_level: string;
    market_saturation: string;
    growth_potential: string;
    velocity_score?: number;
  };
}

export interface DashboardStats {
  total_products: number;
  avg_score: number;
  avg_margin: number;
  trending_up: number;
  high_potential: number;
  total_pages?: number;
  avg_profit_margin?: number;
  total_revenue?: number;
}

export interface EmailMetrics {
  total_processed: number;
  auto_replied: number;
  pending: number;
  response_rate: number;
  categories: Array<{
    name: string;
    count: number;
  }>;
}

export interface Niche {
  key: string;
  name: string;
  description?: string;
  product_count: number;
  avg_score?: number;
  target_audience?: string;
}
