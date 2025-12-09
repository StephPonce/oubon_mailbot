// Custom Hooks for Data Fetching
// Provides caching, error handling, and loading states

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  productsAPI,
  trendsAPI,
  nichesAPI,
  analyticsAPI,
  competitorsAPI,
  emailAPI,
  abTestingAPI,
  systemAPI,
  intelligenceAPI,
  rankingsAPI,
} from '../services/api';
import type {
  Product,
  ProductFilters,
  Trend,
  Niche,
} from '../services/api';

// Generic fetch hook with caching
interface UseQueryOptions {
  enabled?: boolean;
  refetchInterval?: number;
  staleTime?: number;
  onError?: (error: Error) => void;
}

interface UseQueryResult<T> {
  data: T | null;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  lastUpdated: Date | null;
}

function useQuery<T>(
  key: string,
  fetcher: () => Promise<T>,
  options: UseQueryOptions = {}
): UseQueryResult<T> {
  const { enabled = true, refetchInterval, onError } = options;
  
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setError(null);

    try {
      const result = await fetcherRef.current();
      setData(result);
      setLastUpdated(new Date());
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      setError(error);
      setIsError(true);
      onError?.(error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    if (enabled) {
      refetch();
    }
  }, [enabled, key]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (refetchInterval && enabled) {
      const interval = setInterval(refetch, refetchInterval);
      return () => clearInterval(interval);
    }
  }, [refetchInterval, enabled, refetch]);

  return { data, isLoading, isError, error, refetch, lastUpdated };
}

// ============================================
// PRODUCTS HOOKS
// ============================================
export function useProducts(filters?: ProductFilters) {
  return useQuery(
    `products-${JSON.stringify(filters)}`,
    () => productsAPI.getAll(filters),
    { staleTime: 60000 }
  );
}

export function useProduct(id: string) {
  return useQuery(
    `product-${id}`,
    () => productsAPI.getById(id),
    { enabled: !!id }
  );
}

export function useProductRecommendations(limit = 10) {
  return useQuery(
    `product-recommendations-${limit}`,
    () => productsAPI.getRecommendations(limit),
    { refetchInterval: 300000 } // Refresh every 5 minutes
  );
}

export function useProductRankings(limit = 20) {
  return useQuery(
    `product-rankings-${limit}`,
    () => productsAPI.getRankings(limit),
    { refetchInterval: 60000 } // Refresh every minute
  );
}

export function useProductDiscovery(niches: string[], limit = 10) {
  return useQuery(
    `product-discovery-${niches.join(',')}-${limit}`,
    () => productsAPI.discover(niches, limit),
    { enabled: niches.length > 0 }
  );
}

// Deploy to Shopify mutation hook
export function useDeployToShopify() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const deploy = useCallback(async (productId: string, productData?: any) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await productsAPI.deployToShopify(productId, productData);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Deploy failed');
      setError(error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { deploy, isLoading, error };
}

// Analyze product mutation hook
export function useAnalyzeProduct() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const analyze = useCallback(async (productId: string, productData?: any) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await productsAPI.analyze(productId, productData);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Analysis failed');
      setError(error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { analyze, isLoading, error };
}

// ============================================
// TRENDS HOOKS
// ============================================
export function useLiveTrends() {
  return useQuery<Trend[]>(
    'live-trends',
    () => trendsAPI.getLive(),
    { refetchInterval: 30000 } // Refresh every 30 seconds
  );
}

export function useTrendMovers(direction: 'up' | 'down' = 'up', limit = 10) {
  return useQuery<Product[]>(
    `trend-movers-${direction}-${limit}`,
    () => trendsAPI.getMovers(direction, limit),
    { refetchInterval: 60000 }
  );
}

export function useBreakoutProducts(limit = 10) {
  return useQuery<Product[]>(
    `breakout-products-${limit}`,
    () => trendsAPI.getBreakouts(limit),
    { refetchInterval: 60000 }
  );
}

export function useTrendsByPlatform(platform: string) {
  return useQuery(
    `trends-${platform}`,
    () => trendsAPI.getByPlatform(platform),
    { enabled: !!platform }
  );
}

export function useTrendHistory(trendId: string, days = 30) {
  return useQuery(
    `trend-history-${trendId}-${days}`,
    () => trendsAPI.getHistory(trendId, days),
    { enabled: !!trendId }
  );
}

export function useTrendHeatmap() {
  return useQuery(
    'trend-heatmap',
    () => trendsAPI.getHeatmap(),
    { refetchInterval: 300000 }
  );
}

export function useProductMomentum(productId: string) {
  return useQuery(
    `product-momentum-${productId}`,
    () => trendsAPI.getProductMomentum(productId),
    { enabled: !!productId, refetchInterval: 60000 }
  );
}

// ============================================
// NICHES HOOKS
// ============================================
export function useNiches() {
  return useQuery<Niche[]>(
    'niches',
    () => nichesAPI.getAll(),
    { staleTime: 120000 }
  );
}

export function useNiche(id: string) {
  return useQuery(
    `niche-${id}`,
    () => nichesAPI.getById(id),
    { enabled: !!id }
  );
}

export function useNicheProducts(nicheId: string) {
  return useQuery(
    `niche-products-${nicheId}`,
    () => nichesAPI.getProducts(nicheId),
    { enabled: !!nicheId }
  );
}

export function useNicheAnalysis(nicheId: string) {
  return useQuery(
    `niche-analysis-${nicheId}`,
    () => nichesAPI.analyze(nicheId),
    { enabled: !!nicheId }
  );
}

// ============================================
// ANALYTICS HOOKS
// ============================================
export function useDashboardMetrics() {
  return useQuery(
    'dashboard-metrics',
    () => analyticsAPI.getDashboardMetrics(),
    { refetchInterval: 60000 }
  );
}

export function useRevenue(period: 'day' | 'week' | 'month' | 'quarter' | 'year' = 'month') {
  return useQuery(
    `revenue-${period}`,
    () => analyticsAPI.getRevenue(period),
    { staleTime: 300000 }
  );
}

export function useCustomerSegments() {
  return useQuery(
    'customer-segments',
    () => analyticsAPI.getCustomerSegments(),
    { staleTime: 600000 }
  );
}

export function useProductPerformance() {
  return useQuery(
    'product-performance',
    () => analyticsAPI.getProductPerformance(),
    { refetchInterval: 300000 }
  );
}

export function useConversionFunnel() {
  return useQuery(
    'conversion-funnel',
    () => analyticsAPI.getConversionFunnel(),
    { staleTime: 300000 }
  );
}

// ============================================
// COMPETITORS HOOKS
// ============================================
export function useCompetitors() {
  return useQuery(
    'competitors',
    () => competitorsAPI.getAll(),
    { staleTime: 600000 }
  );
}

export function useCompetitor(id: string) {
  return useQuery(
    `competitor-${id}`,
    () => competitorsAPI.getById(id),
    { enabled: !!id }
  );
}

export function usePriceComparison() {
  return useQuery(
    'price-comparison',
    () => competitorsAPI.getPriceComparison(),
    { staleTime: 300000 }
  );
}

export function useCompetitorAnalysis(id: string) {
  return useQuery(
    `competitor-analysis-${id}`,
    () => competitorsAPI.analyze(id),
    { enabled: !!id }
  );
}

// ============================================
// EMAIL HOOKS
// ============================================
export function useEmails(status?: string) {
  return useQuery(
    `emails-${status || 'all'}`,
    () => emailAPI.getAll(status),
    { refetchInterval: 60000 }
  );
}

export function useEmailStats() {
  return useQuery(
    'email-stats',
    () => emailAPI.getStats(),
    { refetchInterval: 60000 }
  );
}

export function useEmailMetrics() {
  return useQuery(
    'email-metrics',
    async () => {
      const [stats, performance, recent] = await Promise.all([
        emailAPI.getStats(),
        emailAPI.getPerformanceMetrics(),
        emailAPI.getAll().then(emails => emails.slice(0, 5))
      ]);
      return {
        stats,
        performance,
        recentEmails: recent
      };
    },
    { refetchInterval: 30000 } // Auto-refresh every 30 seconds
  );
}

// ============================================
// A/B TESTING HOOKS
// ============================================
export function useABTests() {
  return useQuery(
    'ab-tests',
    () => abTestingAPI.getAll(),
    { refetchInterval: 60000 }
  );
}

export function useABTest(id: string) {
  return useQuery(
    `ab-test-${id}`,
    () => abTestingAPI.getById(id),
    { enabled: !!id }
  );
}

export function useABTestResults(id: string) {
  return useQuery(
    `ab-test-results-${id}`,
    () => abTestingAPI.getResults(id),
    { enabled: !!id, refetchInterval: 30000 }
  );
}

// ============================================
// SYSTEM HOOKS
// ============================================
export function useSystemHealth() {
  return useQuery(
    'system-health',
    () => systemAPI.getHealth(),
    { refetchInterval: 10000 }
  );
}

export function useSystemServices() {
  return useQuery(
    'system-services',
    () => systemAPI.getServices(),
    { refetchInterval: 10000 }
  );
}

// ============================================
// INTELLIGENCE HOOKS
// ============================================
export function useOiInsights() {
  return useQuery(
    'oi-insights',
    () => intelligenceAPI.getInsights(),
    { refetchInterval: 60000 }
  );
}

export function useOiRecommendations() {
  return useQuery(
    'oi-recommendations',
    () => intelligenceAPI.getRecommendations(),
    { refetchInterval: 300000 }
  );
}

export function useOiContext() {
  return useQuery(
    'oi-context',
    () => intelligenceAPI.getContext(),
    { refetchInterval: 60000 }
  );
}

// Chat hook with streaming support
export function useOiChat() {
  const [messages, setMessages] = useState<Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    actions?: any[];
  }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');

  const sendMessage = useCallback(async (content: string, context?: any, useStream = true) => {
    const userMessage = {
      id: Date.now().toString(),
      role: 'user' as const,
      content,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setStreamingContent('');

    try {
      if (useStream) {
        // Streaming response
        let fullContent = '';
        await intelligenceAPI.chatStream(content, context, (chunk) => {
          fullContent += chunk;
          setStreamingContent(fullContent);
        });

        const assistantMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant' as const,
          content: fullContent,
          timestamp: new Date(),
        };

        setMessages(prev => [...prev, assistantMessage]);
      } else {
        // Regular response
        const response = await intelligenceAPI.chat(content, context);
        
        const assistantMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant' as const,
          content: response.message,
          timestamp: new Date(),
          actions: response.actions,
        };

        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant' as const,
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setStreamingContent('');
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isLoading,
    streamingContent,
    sendMessage,
    clearMessages,
  };
}

// ============================================
// RANKINGS HOOKS
// ============================================
export function useTop20Rankings(niche?: string) {
  return useQuery(
    `top-20-rankings-${niche || 'all'}`,
    () => rankingsAPI.getTop(20, niche),
    { refetchInterval: 300000 } // Refresh every 5 minutes
  );
}

export default useQuery;
