/**
 * OSPRA INTELLIGENCE - DASHBOARD CONTEXT PROVIDER (ENHANCED)
 * ===========================================================
 * 
 * NOW WITH:
 * - Cross-tab visibility (loads ALL data on init)
 * - Real-time alerts via WebSocket
 * - Background refresh
 * - Action execution from chat
 * 
 * Oi now sees EVERYTHING, not just current page.
 * 
 * @author OspraOS
 * @date January 2025
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../services/api';
import { authService } from '../services/auth';

// WebSocket URL (same host, different path)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = API_URL.replace('http://', 'ws://').replace('https://', 'wss://');

// Helper to ensure value is an array
const ensureArray = (val) => Array.isArray(val) ? val : [];

// Helper to safely extract products from various API response formats
const extractProducts = (res) => {
  if (!res) return [];
  if (Array.isArray(res)) return res;
  if (Array.isArray(res.products)) return res.products;
  if (Array.isArray(res.data)) return res.data;
  if (Array.isArray(res.items)) return res.items;
  return [];
};

// Initial state - now includes ALL data, not just current view
const initialState = {
  // Navigation
  currentPage: 'dashboard',
  currentView: null,
  
  // Selected items (current page)
  selectedProduct: null,
  selectedStore: null,
  
  // =========================================================================
  // GLOBAL DATA - Available regardless of current page
  // =========================================================================
  
  // Products (always loaded)
  allProducts: {
    trending: [],
    recommended: [],
    deployed: [],
    watchlist: [],
  },
  visibleProducts: [], // Current page products (subset)
  
  // Store data (always loaded)
  stores: [],
  storeMetrics: null,
  
  // Autopilot (always loaded)
  autopilotStatus: null,
  autopilotConfig: null,
  
  // Actions (always loaded)
  pendingActions: [],
  recentActions: [],
  actionStats: null,
  
  // =========================================================================
  // ALERTS - Real-time from Oi
  // =========================================================================
  
  alerts: [],
  unreadAlertCount: 0,
  alertsLoading: false,
  
  // =========================================================================
  // USER BEHAVIOR
  // =========================================================================
  
  activeFilters: {},
  recentSearches: [],
  
  // Connection status
  connectionStatus: {
    stores: false,
    email: false,
    intelligence: false,
    ads: false,
    websocket: false,
  },
  
  // Timestamps
  lastUpdated: null,
  lastFullRefresh: null,
};

const DashboardContext = createContext({
  state: initialState,
  // Setters - current page
  setCurrentPage: () => {},
  setSelectedProduct: () => {},
  setSelectedStore: () => {},
  setVisibleProducts: () => {},
  // Setters - global
  setStoreMetrics: () => {},
  setAutopilotStatus: () => {},
  setPendingActions: () => {},
  addRecentSearch: () => {},
  setActiveFilters: () => {},
  setConnectionStatus: () => {},
  // Alerts
  markAlertRead: () => {},
  dismissAlert: () => {},
  executeAlertAction: () => {},
  // Getters
  getFullContext: () => ({}),
  // Actions
  refreshAll: () => {},
  refreshSection: () => {},
  trackInteraction: () => {},
});

export function DashboardProvider({ children }) {
  const location = useLocation();
  const [state, setState] = useState(initialState);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const refreshIntervalRef = useRef(null);
  
  // =========================================================================
  // INITIALIZATION - Load ALL data on mount (only if authenticated)
  // =========================================================================

  useEffect(() => {
    // Only load data and connect WebSocket if user is authenticated
    // This prevents "Load failed" errors on login/register pages
    if (!authService.isAuthenticated()) {
      console.debug('[DashboardContext] Skipping init - user not authenticated');
      return;
    }

    // Load all data immediately
    refreshAll();

    // Connect to WebSocket for real-time alerts
    connectWebSocket();

    // Set up periodic refresh (every 5 minutes)
    refreshIntervalRef.current = setInterval(() => {
      // Re-check auth before refreshing (user might have logged out)
      if (authService.isAuthenticated()) {
        refreshAll(true); // Silent refresh
      }
    }, 5 * 60 * 1000);

    return () => {
      // Cleanup
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, []);
  
  // Update current page when route changes
  useEffect(() => {
    const page = location.pathname.replace('/', '') || 'dashboard';
    setState(prev => ({
      ...prev,
      currentPage: page,
      lastUpdated: new Date().toISOString(),
    }));

    // Track page view (only if authenticated)
    if (authService.isAuthenticated()) {
      trackInteraction('page_view', { page });
    }
  }, [location.pathname]);

  // Listen for auth state changes (load data when user logs in)
  useEffect(() => {
    const unsubscribe = authService.subscribe((authState) => {
      if (authState.isAuthenticated) {
        // User just logged in - load dashboard data
        console.debug('[DashboardContext] User authenticated - loading data');
        refreshAll();
        connectWebSocket();

        // Set up periodic refresh
        if (!refreshIntervalRef.current) {
          refreshIntervalRef.current = setInterval(() => {
            if (authService.isAuthenticated()) {
              refreshAll(true);
            }
          }, 5 * 60 * 1000);
        }
      } else {
        // User logged out - cleanup
        console.debug('[DashboardContext] User logged out - cleaning up');
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
          refreshIntervalRef.current = null;
        }
        // Reset state to initial
        setState(initialState);
      }
    });

    return () => unsubscribe();
  }, [refreshAll, connectWebSocket]);
  
  // =========================================================================
  // WEBSOCKET - Real-time alerts from Oi
  // =========================================================================
  
  // Track reconnection attempts to implement exponential backoff
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;
  
  const connectWebSocket = useCallback(() => {
    // Skip if not authenticated
    if (!authService.isAuthenticated()) {
      console.debug('[DashboardContext] Skipping WebSocket - not authenticated');
      return;
    }

    // Skip if we've exceeded max attempts
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      console.log('[PLUGIN] WebSocket: Max reconnection attempts reached, using polling mode');
      return;
    }
    
    try {
      const ws = new WebSocket(`${WS_BASE_URL}/ws/oi/alerts`);
      
      ws.onopen = () => {
        console.log('[PLUGIN] Oi WebSocket connected');
        reconnectAttemptsRef.current = 0; // Reset on successful connection
        setState(prev => ({
          ...prev,
          connectionStatus: { ...prev.connectionStatus, websocket: true },
        }));
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
      
      ws.onclose = () => {
        console.log('[PLUGIN] Oi WebSocket disconnected');
        setState(prev => ({
          ...prev,
          connectionStatus: { ...prev.connectionStatus, websocket: false },
        }));
        
        // Exponential backoff: 5s, 10s, 20s, 40s, 80s
        const delay = Math.min(5000 * Math.pow(2, reconnectAttemptsRef.current), 80000);
        reconnectAttemptsRef.current += 1;
        
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          console.log(`[PLUGIN] WebSocket reconnecting in ${delay/1000}s (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket();
          }, delay);
        }
      };
      
      ws.onerror = (error) => {
        // Only log first error to reduce noise
        if (reconnectAttemptsRef.current === 0) {
          console.warn('WebSocket error (will retry):', error);
        }
      };
      
      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      // Retry with backoff
      const delay = Math.min(10000 * Math.pow(2, reconnectAttemptsRef.current), 80000);
      reconnectAttemptsRef.current += 1;
      
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, delay);
      }
    }
  }, []);
  
  const handleWebSocketMessage = useCallback((data) => {
    switch (data.type) {
      case 'alert':
        // New alert from Oi
        setState(prev => ({
          ...prev,
          alerts: [data.alert, ...prev.alerts].slice(0, 50), // Keep last 50
          unreadAlertCount: prev.unreadAlertCount + 1,
        }));
        break;
        
      case 'action_update':
        // Action status changed
        refreshSection('actions');
        break;
        
      case 'product_update':
        // Product data changed
        refreshSection('products');
        break;
        
      case 'metrics_update':
        // Store metrics updated
        refreshSection('metrics');
        break;
        
      default:
        console.log('Unknown WebSocket message type:', data.type);
    }
  }, []);
  
  // =========================================================================
  // DATA LOADING - Fetch all sections
  // =========================================================================
  
  const refreshAll = useCallback(async (silent = false) => {
    // Skip if not authenticated
    if (!authService.isAuthenticated()) {
      console.debug('[DashboardContext] Skipping refresh - not authenticated');
      return;
    }

    if (!silent) {
      setState(prev => ({ ...prev, alertsLoading: true }));
    }

    try {
      // Fetch ALL data in parallel
      const [
        trendingRes,
        recommendedRes,
        autopilotRes,
        autopilotConfigRes,
        actionsRes,
        actionStatsRes,
        alertsRes,
      ] = await Promise.all([
        api.getTrendingProducts().catch(() => ({ products: [] })),
        api.getProductRecommendations(20).catch(() => []),
        api.getAutopilotStatus().catch(() => null),
        api.getAutopilotConfig().catch(() => null),
        api.getPendingActions({ limit: 50 }).catch(() => []),
        api.getActionStats().catch(() => null),
        api.getOiAlerts?.().catch(() => ({ alerts: [] })),
      ]);
      
      setState(prev => ({
        ...prev,
        allProducts: {
          ...prev.allProducts,
          trending: extractProducts(trendingRes),
          recommended: extractProducts(recommendedRes),
        },
        autopilotStatus: autopilotRes,
        autopilotConfig: autopilotConfigRes,
        pendingActions: Array.isArray(actionsRes) ? actionsRes : [],
        actionStats: actionStatsRes,
        alerts: alertsRes?.alerts || prev.alerts,
        unreadAlertCount: alertsRes?.unread_count ?? prev.unreadAlertCount,
        connectionStatus: {
          ...prev.connectionStatus,
          intelligence: !!autopilotRes,
        },
        lastFullRefresh: new Date().toISOString(),
        lastUpdated: new Date().toISOString(),
        alertsLoading: false,
      }));
      
    } catch (error) {
      console.error('Failed to refresh dashboard data:', error);
      setState(prev => ({ ...prev, alertsLoading: false }));
    }
  }, []);
  
  const refreshSection = useCallback(async (section) => {
    // Skip if not authenticated
    if (!authService.isAuthenticated()) {
      console.debug(`[DashboardContext] Skipping refresh ${section} - not authenticated`);
      return;
    }

    try {
      switch (section) {
        case 'products':
          const [trending, recommended] = await Promise.all([
            api.getTrendingProducts().catch(() => ({ products: [] })),
            api.getProductRecommendations(20).catch(() => []),
          ]);
          setState(prev => ({
            ...prev,
            allProducts: {
              ...prev.allProducts,
              trending: extractProducts(trending),
              recommended: extractProducts(recommended),
            },
          }));
          break;
          
        case 'actions':
          const [actions, stats] = await Promise.all([
            api.getPendingActions({ limit: 50 }).catch(() => []),
            api.getActionStats().catch(() => null),
          ]);
          setState(prev => ({
            ...prev,
            pendingActions: Array.isArray(actions) ? actions : [],
            actionStats: stats,
          }));
          break;
          
        case 'autopilot':
          const [status, config] = await Promise.all([
            api.getAutopilotStatus().catch(() => null),
            api.getAutopilotConfig().catch(() => null),
          ]);
          setState(prev => ({
            ...prev,
            autopilotStatus: status,
            autopilotConfig: config,
          }));
          break;
          
        case 'metrics':
          // TODO: Fetch store metrics when connected
          break;
          
        case 'alerts':
          const alertsRes = await api.getOiAlerts?.().catch(() => ({ alerts: [] }));
          setState(prev => ({
            ...prev,
            alerts: alertsRes?.alerts || [],
            unreadAlertCount: alertsRes?.unread_count ?? 0,
          }));
          break;
      }
    } catch (error) {
      console.error(`Failed to refresh ${section}:`, error);
    }
  }, []);
  
  // =========================================================================
  // ALERT ACTIONS
  // =========================================================================
  
  const markAlertRead = useCallback((alertId) => {
    setState(prev => ({
      ...prev,
      alerts: prev.alerts.map(a => 
        a.id === alertId ? { ...a, read: true } : a
      ),
      unreadAlertCount: Math.max(0, prev.unreadAlertCount - 1),
    }));
    
    // Sync to backend
    api.markAlertRead?.(alertId).catch(console.error);
  }, []);
  
  const dismissAlert = useCallback((alertId) => {
    setState(prev => ({
      ...prev,
      alerts: prev.alerts.filter(a => a.id !== alertId),
      unreadAlertCount: prev.alerts.find(a => a.id === alertId && !a.read) 
        ? Math.max(0, prev.unreadAlertCount - 1) 
        : prev.unreadAlertCount,
    }));
    
    // Sync to backend
    api.dismissAlert?.(alertId).catch(console.error);
  }, []);
  
  const executeAlertAction = useCallback(async (alertId, action, params = {}) => {
    try {
      const result = await api.executeAlertAction?.(alertId, action, params);
      
      // Mark as actioned
      setState(prev => ({
        ...prev,
        alerts: prev.alerts.map(a => 
          a.id === alertId ? { ...a, actioned: true, actionResult: result } : a
        ),
      }));
      
      // Refresh relevant data
      if (action === 'deploy' || action === 'add_to_watchlist') {
        refreshSection('products');
      } else if (action === 'approve' || action === 'decline') {
        refreshSection('actions');
      }
      
      return result;
    } catch (error) {
      console.error('Failed to execute alert action:', error);
      throw error;
    }
  }, [refreshSection]);
  
  // =========================================================================
  // SETTERS - Current page state
  // =========================================================================
  
  const setCurrentPage = useCallback((page, view = null) => {
    setState(prev => ({
      ...prev,
      currentPage: page,
      currentView: view,
      lastUpdated: new Date().toISOString(),
    }));
  }, []);
  
  const setSelectedProduct = useCallback((product) => {
    setState(prev => ({
      ...prev,
      selectedProduct: product,
      lastUpdated: new Date().toISOString(),
    }));
    
    if (product) {
      trackInteraction('product_select', {
        product_id: product.id,
        product_name: product.name,
        niche: product.niche,
        score: product.score,
      });
    }
  }, []);
  
  const setSelectedStore = useCallback((store) => {
    setState(prev => ({
      ...prev,
      selectedStore: store,
      lastUpdated: new Date().toISOString(),
    }));
  }, []);
  
  const setVisibleProducts = useCallback((products) => {
    setState(prev => ({
      ...prev,
      visibleProducts: products.slice(0, 50),
      lastUpdated: new Date().toISOString(),
    }));
  }, []);
  
  const setStoreMetrics = useCallback((metrics) => {
    setState(prev => ({
      ...prev,
      storeMetrics: metrics,
      connectionStatus: {
        ...prev.connectionStatus,
        stores: !!metrics,
      },
      lastUpdated: new Date().toISOString(),
    }));
  }, []);
  
  const setAutopilotStatus = useCallback((status, config = null) => {
    setState(prev => ({
      ...prev,
      autopilotStatus: status,
      autopilotConfig: config || prev.autopilotConfig,
      lastUpdated: new Date().toISOString(),
    }));
  }, []);
  
  const setPendingActions = useCallback((actions) => {
    setState(prev => ({
      ...prev,
      pendingActions: actions,
      lastUpdated: new Date().toISOString(),
    }));
  }, []);
  
  const addRecentSearch = useCallback((query) => {
    if (!query?.trim()) return;
    
    setState(prev => {
      const searches = [query, ...prev.recentSearches.filter(s => s !== query)].slice(0, 10);
      return {
        ...prev,
        recentSearches: searches,
        lastUpdated: new Date().toISOString(),
      };
    });
    
    trackInteraction('search', { query });
  }, []);
  
  const setActiveFilters = useCallback((filters) => {
    setState(prev => ({
      ...prev,
      activeFilters: filters,
      lastUpdated: new Date().toISOString(),
    }));
    
    trackInteraction('filter', filters);
  }, []);
  
  const setConnectionStatus = useCallback((status) => {
    setState(prev => ({
      ...prev,
      connectionStatus: { ...prev.connectionStatus, ...status },
      lastUpdated: new Date().toISOString(),
    }));
  }, []);
  
  // =========================================================================
  // GETTERS - Full context for Oi
  // =========================================================================
  
  const getFullContext = useCallback(() => {
    // Format context with ALL data, not just current page
    return {
      // Current view
      currentPage: state.currentPage,
      currentView: state.currentView,
      
      // Selected items
      selectedProduct: state.selectedProduct ? {
        id: state.selectedProduct.id || '',
        name: state.selectedProduct.name || '',
        price: state.selectedProduct.price,
        supplier_cost: state.selectedProduct.supplier_cost || state.selectedProduct.supplierCost,
        score: state.selectedProduct.score || state.selectedProduct.oi_score,
        niche: state.selectedProduct.niche,
        trend_score: state.selectedProduct.trend_score || state.selectedProduct.trendScore,
        source: state.selectedProduct.source,
      } : null,
      
      selectedStore: state.selectedStore ? {
        id: state.selectedStore.id || '',
        platform: state.selectedStore.platform || 'shopify',
        store_name: state.selectedStore.store_name || state.selectedStore.name,
        store_url: state.selectedStore.store_url || state.selectedStore.url,
        currency: state.selectedStore.currency,
      } : null,
      
      // ALL PRODUCTS (not just visible) - with defensive array access
      allProducts: {
        trending_count: ensureArray(state.allProducts?.trending).length,
        trending_top5: ensureArray(state.allProducts?.trending).slice(0, 5).map(p => ({
          id: p?.id || '',
          name: p?.title || p?.name || '',
          score: p?.score || 0,
          niche: p?.niche || '',
        })),
        recommended_count: ensureArray(state.allProducts?.recommended).length,
        recommended_top5: ensureArray(state.allProducts?.recommended).slice(0, 5).map(p => ({
          id: p?.id || '',
          name: p?.title || p?.name || '',
          score: p?.score || 0,
          niche: p?.niche || '',
        })),
      },
      
      // Currently visible (for page context)
      visibleProducts: ensureArray(state.visibleProducts).slice(0, 20).map(p => ({
        id: p?.id || '',
        name: p?.name || '',
        price: p?.price,
        score: p?.score || p?.oi_score,
        niche: p?.niche,
      })),
      
      // Store metrics
      storeMetrics: state.storeMetrics ? {
        revenue_7d: state.storeMetrics.revenue_7d || state.storeMetrics.revenue7d || 0,
        revenue_30d: state.storeMetrics.revenue_30d || state.storeMetrics.revenue30d || 0,
        orders_7d: state.storeMetrics.orders_7d || state.storeMetrics.orders7d || 0,
        orders_30d: state.storeMetrics.orders_30d || state.storeMetrics.orders30d || 0,
        products_count: state.storeMetrics.products_count || state.storeMetrics.productsCount || 0,
      } : null,
      
      // Autopilot
      autopilot: {
        is_active: state.autopilotStatus?.is_active || false,
        mode: state.autopilotStatus?.mode || 'disabled',
        confidence_threshold: state.autopilotConfig?.confidence_threshold || 85,
        actions_today: state.autopilotStatus?.actions_today || 0,
      },
      
      // Pending actions (ALL, not just visible)
      pendingActions: (() => {
        const actions = ensureArray(state.pendingActions);
        return {
          count: actions.length,
          high_confidence: actions.filter(a => (a?.confidence || 0) >= 0.85).length,
          by_type: actions.reduce((acc, a) => {
            const type = a?.action_type || a?.type || 'unknown';
            acc[type] = (acc[type] || 0) + 1;
            return acc;
          }, {}),
          top5: actions.slice(0, 5).map(a => ({
            id: a?.id,
            type: a?.action_type || a?.type,
            title: a?.title,
            confidence: a?.confidence,
          })),
        };
      })(),
      
      // Alerts
      alerts: (() => {
        const alertsList = ensureArray(state.alerts);
        return {
          unread_count: state.unreadAlertCount || 0,
          total_count: alertsList.length,
          recent: alertsList.slice(0, 5).map(a => ({
            id: a?.id,
            type: a?.type,
            title: a?.title,
            priority: a?.priority,
            read: a?.read,
          })),
        };
      })(),
      
      // User behavior
      activeFilters: state.activeFilters,
      recentSearches: state.recentSearches,
      
      // Connection status
      connectionStatus: {
        stores: state.connectionStatus.stores,
        email: state.connectionStatus.email,
        intelligence: state.connectionStatus.intelligence,
        ads: state.connectionStatus.ads,
        realtime: state.connectionStatus.websocket,
      },
      
      // Timestamps
      lastUpdated: state.lastUpdated,
      lastFullRefresh: state.lastFullRefresh,
    };
  }, [state]);
  
  // =========================================================================
  // TRACKING
  // =========================================================================
  
  const trackInteraction = useCallback(async (type, data) => {
    try {
      await api.trackInteraction?.({
        timestamp: new Date().toISOString(),
        type,
        data,
      });
    } catch (error) {
      console.debug('Interaction tracking failed:', error);
    }
  }, []);
  
  // =========================================================================
  // CONTEXT VALUE
  // =========================================================================
  
  const value = {
    state,
    // Setters - current page
    setCurrentPage,
    setSelectedProduct,
    setSelectedStore,
    setVisibleProducts,
    // Setters - global
    setStoreMetrics,
    setAutopilotStatus,
    setPendingActions,
    addRecentSearch,
    setActiveFilters,
    setConnectionStatus,
    // Alerts
    markAlertRead,
    dismissAlert,
    executeAlertAction,
    // Getters
    getFullContext,
    // Actions
    refreshAll,
    refreshSection,
    trackInteraction,
  };
  
  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
}

// Hook for consuming dashboard context
export function useDashboardContext() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboardContext must be used within a DashboardProvider');
  }
  return context;
}

export default DashboardContext;
