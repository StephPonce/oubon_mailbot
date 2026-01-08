/**
 * Oi Context - The Brain's Awareness System
 *
 * This context gives Oi awareness of what the user is doing:
 * - Current page/view
 * - Selected items (product, store, etc.)
 * - Visible data on screen
 * - Store metrics
 * - Interaction history (for self-learning)
 *
 * @author OspraOS
 * @date December 2024
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { authService } from '../services/auth';

// ============================================================================
// TYPES
// ============================================================================

export interface SelectedProduct {
  id: string;
  name: string;
  price?: number;
  supplier_cost?: number;
  score?: number;
  niche?: string;
  trend_score?: number;
  source?: string;
  image_url?: string;
}

export interface SelectedStore {
  id: string;
  platform: 'shopify' | 'woocommerce';
  store_name: string;
  store_url: string;
  currency?: string;
}

export interface StoreMetrics {
  revenue_7d: number;
  revenue_30d: number;
  orders_7d: number;
  orders_30d: number;
  products_count: number;
  customers_count: number;
  avg_order_value: number;
}

export interface TrendingProduct {
  id: string;
  name: string;
  score: number;
  trend_direction: 'up' | 'down' | 'stable';
  niche: string;
  source?: string;
}

export interface EmailStats {
  unread_count: number;
  auto_replied_count: number;
  pending_review: number;
  last_processed?: string;
}

export interface AdStats {
  total_spend: number;
  total_impressions: number;
  total_clicks: number;
  roas: number;
  active_campaigns: number;
}

export interface UserInteraction {
  timestamp: string;
  type: 'product_view' | 'product_deploy' | 'search' | 'filter' | 'oi_query' | 'feedback' | 'action';
  data: Record<string, unknown>;
}

export interface DashboardContext {
  // Current navigation state
  currentPage: string;
  currentView?: string;
  
  // Selected items
  selectedProduct: SelectedProduct | null;
  selectedStore: SelectedStore | null;
  
  // Visible data
  visibleProducts: SelectedProduct[];
  trendingProducts: TrendingProduct[];
  
  // Connected data sources
  storeMetrics: StoreMetrics | null;
  emailStats: EmailStats | null;
  adStats: AdStats | null;
  
  // User state
  userPreferences: Record<string, unknown>;
  recentSearches: string[];
  activeFilters: Record<string, unknown>;
  
  // Interaction history (for self-learning)
  recentInteractions: UserInteraction[];
  
  // Connection status
  connectionStatus: {
    stores: boolean;
    email: boolean;
    intelligence: boolean;
    ads: boolean;
  };
}

export interface OiContextType {
  // Dashboard context
  dashboardContext: DashboardContext;
  
  // Setters for pages to register their data
  setCurrentPage: (page: string, view?: string) => void;
  setSelectedProduct: (product: SelectedProduct | null) => void;
  setSelectedStore: (store: SelectedStore | null) => void;
  setVisibleProducts: (products: SelectedProduct[]) => void;
  setTrendingProducts: (products: TrendingProduct[]) => void;
  setStoreMetrics: (metrics: StoreMetrics | null) => void;
  setEmailStats: (stats: EmailStats | null) => void;
  setAdStats: (stats: AdStats | null) => void;
  setActiveFilters: (filters: Record<string, unknown>) => void;
  
  // Interaction tracking (for self-learning)
  trackInteraction: (type: UserInteraction['type'], data: Record<string, unknown>) => void;
  trackSearch: (query: string) => void;
  trackFeedback: (messageId: string, helpful: boolean, comment?: string) => void;
  
  // Chat with Oi
  chatWithOi: (message: string, options?: ChatOptions) => Promise<OiResponse>;
  
  // Oi state
  isOiOpen: boolean;
  setIsOiOpen: (open: boolean) => void;
  isOiLoading: boolean;
  lastOiResponse: OiResponse | null;
}

export interface ChatOptions {
  refreshContext?: boolean;
  executeActions?: boolean;
  includeScreenshot?: boolean;  // Future: visual understanding
}

export interface OiResponse {
  message: string;
  actions_taken: Array<{
    action: string;
    status: string;
    message: string;
    data?: Record<string, unknown>;
  }>;
  suggestions: string[];
  tokens_used: number;
  timestamp: string;
  data_disclaimer?: string;
  validation_warnings?: string[];
  data_sources?: Record<string, boolean>;
  learned_from?: string[];  // What Oi learned from this interaction
}

// ============================================================================
// CONTEXT
// ============================================================================

const defaultContext: DashboardContext = {
  currentPage: 'overview',
  currentView: undefined,
  selectedProduct: null,
  selectedStore: null,
  visibleProducts: [],
  trendingProducts: [],
  storeMetrics: null,
  emailStats: null,
  adStats: null,
  userPreferences: {},
  recentSearches: [],
  activeFilters: {},
  recentInteractions: [],
  connectionStatus: {
    stores: false,
    email: false,
    intelligence: false,
    ads: false,
  },
};

const OiContext = createContext<OiContextType | null>(null);

// ============================================================================
// API SERVICE
// ============================================================================

const oiApi = {
  async chat(
    message: string,
    dashboardContext: DashboardContext,
    options: ChatOptions = {}
  ): Promise<OiResponse> {
    // Use authenticated request via authService
    // Note: Using /api/oi/chat endpoint (the correct backend implementation)
    const response = await authService.post('/api/oi/chat', {
      message,
      dashboard_context: dashboardContext,
      context_refresh: options.refreshContext || false,
    });

    // Backend returns ChatResponse which matches OiResponse structure
    return {
      message: response.message || "I didn't quite understand that. Could you rephrase?",
      actions_taken: response.actions_taken || [],
      suggestions: response.suggestions || [],
      tokens_used: response.tokens_used || 0,
      timestamp: response.timestamp || new Date().toISOString(),
      data_disclaimer: response.data_disclaimer,
      validation_warnings: response.validation_warnings,
      data_sources: response.data_sources,
      learned_from: response.learned_from,
    };
  },

  async trackInteraction(interaction: UserInteraction): Promise<void> {
    try {
      await authService.post('/api/oi/learn', interaction);
    } catch (error) {
      console.warn('Failed to track interaction:', error);
    }
  },

  async trackFeedback(
    messageId: string,
    helpful: boolean,
    comment?: string,
    context?: DashboardContext
  ): Promise<void> {
    try {
      await authService.post('/api/oi/feedback', {
        message_id: messageId,
        helpful,
        comment,
        context,
      });
    } catch (error) {
      console.warn('Failed to track feedback:', error);
    }
  },
};

// ============================================================================
// PROVIDER COMPONENT
// ============================================================================

export const OiProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dashboardContext, setDashboardContext] = useState<DashboardContext>(defaultContext);
  const [isOiOpen, setIsOiOpen] = useState(false);
  const [isOiLoading, setIsOiLoading] = useState(false);
  const [lastOiResponse, setLastOiResponse] = useState<OiResponse | null>(null);
  
  // Ref to batch interaction tracking
  const interactionBuffer = useRef<UserInteraction[]>([]);
  const flushTimeoutRef = useRef<number | null>(null);

  // Flush interactions to backend periodically
  const flushInteractions = useCallback(async () => {
    if (interactionBuffer.current.length === 0) return;
    
    const interactions = [...interactionBuffer.current];
    interactionBuffer.current = [];
    
    for (const interaction of interactions) {
      await oiApi.trackInteraction(interaction);
    }
  }, []);

  // Auto-flush interactions every 30 seconds
  useEffect(() => {
    const interval = setInterval(flushInteractions, 30000);
    return () => clearInterval(interval);
  }, [flushInteractions]);

  // Flush on unmount
  useEffect(() => {
    return () => {
      flushInteractions();
    };
  }, [flushInteractions]);

  // ========================================================================
  // SETTERS
  // ========================================================================

  const setCurrentPage = useCallback((page: string, view?: string) => {
    setDashboardContext(prev => ({
      ...prev,
      currentPage: page,
      currentView: view,
    }));
    
    // Track navigation
    interactionBuffer.current.push({
      timestamp: new Date().toISOString(),
      type: 'action',
      data: { action: 'navigate', page, view },
    });
  }, []);

  const setSelectedProduct = useCallback((product: SelectedProduct | null) => {
    setDashboardContext(prev => ({
      ...prev,
      selectedProduct: product,
    }));
    
    if (product) {
      interactionBuffer.current.push({
        timestamp: new Date().toISOString(),
        type: 'product_view',
        data: { product_id: product.id, product_name: product.name, niche: product.niche },
      });
    }
  }, []);

  const setSelectedStore = useCallback((store: SelectedStore | null) => {
    setDashboardContext(prev => ({
      ...prev,
      selectedStore: store,
      connectionStatus: {
        ...prev.connectionStatus,
        stores: store !== null,
      },
    }));
  }, []);

  const setVisibleProducts = useCallback((products: SelectedProduct[]) => {
    setDashboardContext(prev => ({
      ...prev,
      visibleProducts: products,
    }));
  }, []);

  const setTrendingProducts = useCallback((products: TrendingProduct[]) => {
    setDashboardContext(prev => ({
      ...prev,
      trendingProducts: products,
      connectionStatus: {
        ...prev.connectionStatus,
        intelligence: products.length > 0,
      },
    }));
  }, []);

  const setStoreMetrics = useCallback((metrics: StoreMetrics | null) => {
    setDashboardContext(prev => ({
      ...prev,
      storeMetrics: metrics,
    }));
  }, []);

  const setEmailStats = useCallback((stats: EmailStats | null) => {
    setDashboardContext(prev => ({
      ...prev,
      emailStats: stats,
      connectionStatus: {
        ...prev.connectionStatus,
        email: stats !== null,
      },
    }));
  }, []);

  const setAdStats = useCallback((stats: AdStats | null) => {
    setDashboardContext(prev => ({
      ...prev,
      adStats: stats,
      connectionStatus: {
        ...prev.connectionStatus,
        ads: stats !== null,
      },
    }));
  }, []);

  const setActiveFilters = useCallback((filters: Record<string, unknown>) => {
    setDashboardContext(prev => ({
      ...prev,
      activeFilters: filters,
    }));
    
    interactionBuffer.current.push({
      timestamp: new Date().toISOString(),
      type: 'filter',
      data: filters,
    });
  }, []);

  // ========================================================================
  // INTERACTION TRACKING
  // ========================================================================

  const trackInteraction = useCallback((type: UserInteraction['type'], data: Record<string, unknown>) => {
    const interaction: UserInteraction = {
      timestamp: new Date().toISOString(),
      type,
      data,
    };
    
    interactionBuffer.current.push(interaction);
    
    // Keep last 50 interactions in context
    setDashboardContext(prev => ({
      ...prev,
      recentInteractions: [interaction, ...prev.recentInteractions].slice(0, 50),
    }));
  }, []);

  const trackSearch = useCallback((query: string) => {
    setDashboardContext(prev => ({
      ...prev,
      recentSearches: [query, ...prev.recentSearches.filter(s => s !== query)].slice(0, 20),
    }));
    
    interactionBuffer.current.push({
      timestamp: new Date().toISOString(),
      type: 'search',
      data: { query },
    });
  }, []);

  const trackFeedback = useCallback((messageId: string, helpful: boolean, comment?: string) => {
    oiApi.trackFeedback(messageId, helpful, comment, dashboardContext);
    
    trackInteraction('feedback', { message_id: messageId, helpful, comment });
  }, [dashboardContext, trackInteraction]);

  // ========================================================================
  // CHAT WITH OI
  // ========================================================================

  const chatWithOi = useCallback(async (message: string, options: ChatOptions = {}): Promise<OiResponse> => {
    setIsOiLoading(true);
    
    try {
      // Track the query
      trackInteraction('oi_query', { message, page: dashboardContext.currentPage });
      
      // Send message with full dashboard context
      const response = await oiApi.chat(message, dashboardContext, options);
      
      setLastOiResponse(response);
      return response;
    } finally {
      setIsOiLoading(false);
    }
  }, [dashboardContext, trackInteraction]);

  // ========================================================================
  // KEYBOARD SHORTCUT
  // ========================================================================

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K to toggle Oi
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOiOpen(prev => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // ========================================================================
  // CONTEXT VALUE
  // ========================================================================

  const value: OiContextType = {
    dashboardContext,
    setCurrentPage,
    setSelectedProduct,
    setSelectedStore,
    setVisibleProducts,
    setTrendingProducts,
    setStoreMetrics,
    setEmailStats,
    setAdStats,
    setActiveFilters,
    trackInteraction,
    trackSearch,
    trackFeedback,
    chatWithOi,
    isOiOpen,
    setIsOiOpen,
    isOiLoading,
    lastOiResponse,
  };

  return <OiContext.Provider value={value}>{children}</OiContext.Provider>;
};

// ============================================================================
// HOOKS
// ============================================================================

export function useOi(): OiContextType {
  const context = useContext(OiContext);
  if (!context) {
    throw new Error('useOi must be used within an OiProvider');
  }
  return context;
}

/**
 * Hook for pages to register what data they're displaying
 * This data is automatically sent to Oi for context-aware responses
 */
export function useDashboardContext() {
  const {
    setCurrentPage,
    setSelectedProduct,
    setSelectedStore,
    setVisibleProducts,
    setTrendingProducts,
    setStoreMetrics,
    setEmailStats,
    setAdStats,
    setActiveFilters,
    trackSearch,
    trackInteraction,
    dashboardContext,
  } = useOi();

  return {
    // Register current page
    registerPage: setCurrentPage,
    
    // Register visible data
    registerProducts: setVisibleProducts,
    registerTrending: setTrendingProducts,
    registerMetrics: setStoreMetrics,
    registerEmailStats: setEmailStats,
    registerAdStats: setAdStats,
    
    // Register selections
    selectProduct: setSelectedProduct,
    selectStore: setSelectedStore,
    
    // Register filters
    applyFilters: setActiveFilters,
    
    // Track user actions
    trackSearch,
    trackAction: (action: string, data: Record<string, unknown>) => 
      trackInteraction('action', { action, ...data }),
    
    // Access current context
    currentContext: dashboardContext,
  };
}

/**
 * Hook specifically for the Oi chat panel
 */
export function useOiChat() {
  const {
    chatWithOi,
    isOiLoading,
    lastOiResponse,
    trackFeedback,
    dashboardContext,
  } = useOi();

  return {
    sendMessage: chatWithOi,
    isLoading: isOiLoading,
    lastResponse: lastOiResponse,
    provideFeedback: trackFeedback,
    currentContext: dashboardContext,
  };
}

export default OiContext;
