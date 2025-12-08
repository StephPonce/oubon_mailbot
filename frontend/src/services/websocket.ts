// WebSocket Service for Real-Time Updates
// Handles live trends, product updates, notifications, and system status

type MessageHandler = (data: any) => void;
type ConnectionHandler = () => void;

interface WebSocketConfig {
  url: string;
  reconnectInterval: number;
  maxReconnectAttempts: number;
  heartbeatInterval: number;
}

interface Subscription {
  channel: string;
  handler: MessageHandler;
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private subscriptions: Map<string, Set<MessageHandler>> = new Map();
  private reconnectAttempts = 0;
  private heartbeatTimer: number | null = null;
  private reconnectTimer: number | null = null;
  private isConnecting = false;
  private onConnectHandlers: Set<ConnectionHandler> = new Set();
  private onDisconnectHandlers: Set<ConnectionHandler> = new Set();

  constructor(config?: Partial<WebSocketConfig>) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = import.meta.env.VITE_WS_URL || `${wsProtocol}//localhost:8001`;
    
    this.config = {
      url: `${wsHost}/ws`,
      reconnectInterval: 10000,  // 10 seconds between retries
      maxReconnectAttempts: 3,   // Only try 3 times (WebSocket is optional)
      heartbeatInterval: 30000,
      ...config,
    };
  }

  // Connect to WebSocket server
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      if (this.isConnecting) {
        // Wait for existing connection attempt
        const checkConnection = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            clearInterval(checkConnection);
            resolve();
          }
        }, 100);
        return;
      }

      this.isConnecting = true;

      try {
        const token = localStorage.getItem('ospra_token');
        const url = token ? `${this.config.url}?token=${token}` : this.config.url;
        
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log('[WS] Connected to Ospra Intelligence');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.onConnectHandlers.forEach(handler => handler());
          
          // Resubscribe to all channels
          this.subscriptions.forEach((_, channel) => {
            this.sendSubscribe(channel);
          });
          
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.ws.onclose = (event) => {
          console.log('[WS] Disconnected:', event.code, event.reason);
          this.isConnecting = false;
          this.stopHeartbeat();
          this.onDisconnectHandlers.forEach(handler => handler());
          
          if (!event.wasClean) {
            this.scheduleReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error('[WS] Error:', error);
          this.isConnecting = false;
          reject(error);
        };
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  // Disconnect from WebSocket server
  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  // Subscribe to a channel
  subscribe(channel: string, handler: MessageHandler): () => void {
    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, new Set());
    }
    
    this.subscriptions.get(channel)!.add(handler);
    
    // Send subscribe message if connected
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendSubscribe(channel);
    }

    // Return unsubscribe function
    return () => this.unsubscribe(channel, handler);
  }

  // Unsubscribe from a channel
  unsubscribe(channel: string, handler: MessageHandler): void {
    const handlers = this.subscriptions.get(channel);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.subscriptions.delete(channel);
        this.sendUnsubscribe(channel);
      }
    }
  }

  // Send a message to the server
  send(type: string, data: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data, timestamp: Date.now() }));
    } else {
      console.warn('[WS] Cannot send message - not connected');
    }
  }

  // Add connection handler
  onConnect(handler: ConnectionHandler): () => void {
    this.onConnectHandlers.add(handler);
    return () => this.onConnectHandlers.delete(handler);
  }

  // Add disconnection handler
  onDisconnect(handler: ConnectionHandler): () => void {
    this.onDisconnectHandlers.add(handler);
    return () => this.onDisconnectHandlers.delete(handler);
  }

  // Check if connected
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // Private methods
  private handleMessage(rawData: string): void {
    try {
      const message = JSON.parse(rawData);
      const { type, channel, data } = message;

      // Handle system messages
      if (type === 'pong') {
        return; // Heartbeat response
      }

      if (type === 'error') {
        console.error('[WS] Server error:', data);
        return;
      }

      // Dispatch to channel subscribers
      if (channel && this.subscriptions.has(channel)) {
        this.subscriptions.get(channel)!.forEach(handler => {
          try {
            handler(data);
          } catch (error) {
            console.error(`[WS] Handler error for channel ${channel}:`, error);
          }
        });
      }

      // Also dispatch to type-based subscribers (e.g., 'trend_update')
      if (type && this.subscriptions.has(type)) {
        this.subscriptions.get(type)!.forEach(handler => {
          try {
            handler(data);
          } catch (error) {
            console.error(`[WS] Handler error for type ${type}:`, error);
          }
        });
      }
    } catch (error) {
      console.error('[WS] Failed to parse message:', error);
    }
  }

  private sendSubscribe(channel: string): void {
    this.send('subscribe', { channel });
  }

  private sendUnsubscribe(channel: string): void {
    this.send('unsubscribe', { channel });
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send('ping', {});
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.config.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);
    
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    this.reconnectTimer = window.setTimeout(() => {
      this.connect().catch(console.error);
    }, delay);
  }
}

// Create singleton instance
export const wsService = new WebSocketService();

// ============================================
// CHANNEL CONSTANTS
// ============================================
export const WS_CHANNELS = {
  // Trends
  TRENDS_LIVE: 'trends:live',
  TRENDS_UPDATES: 'trends:updates',
  
  // Products
  PRODUCTS_RANKINGS: 'products:rankings',
  PRODUCTS_NEW: 'products:new',
  PRODUCTS_ALERTS: 'products:alerts',
  
  // Intelligence
  OI_INSIGHTS: 'oi:insights',
  OI_RECOMMENDATIONS: 'oi:recommendations',
  
  // System
  SYSTEM_STATUS: 'system:status',
  SYSTEM_ALERTS: 'system:alerts',
  
  // Analytics
  ANALYTICS_REALTIME: 'analytics:realtime',
  
  // Notifications
  NOTIFICATIONS: 'notifications',
} as const;

// ============================================
// REACT HOOKS
// ============================================
import { useState, useEffect, useCallback } from 'react';

// Hook to manage WebSocket connection
export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(wsService.isConnected());

  useEffect(() => {
    const unsubConnect = wsService.onConnect(() => setIsConnected(true));
    const unsubDisconnect = wsService.onDisconnect(() => setIsConnected(false));

    // Connect if not already connected
    if (!wsService.isConnected()) {
      wsService.connect().catch(console.error);
    }

    return () => {
      unsubConnect();
      unsubDisconnect();
    };
  }, []);

  return { isConnected, wsService };
}

// Hook to subscribe to a channel
export function useChannel<T = any>(channel: string) {
  const [data, setData] = useState<T | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const { isConnected } = useWebSocket();

  useEffect(() => {
    if (!isConnected) return;

    const unsubscribe = wsService.subscribe(channel, (newData: T) => {
      setData(newData);
      setLastUpdate(new Date());
    });

    return unsubscribe;
  }, [channel, isConnected]);

  return { data, lastUpdate, isConnected };
}

// Hook for live trends
export function useLiveTrends() {
  const { data, lastUpdate, isConnected } = useChannel<any[]>(WS_CHANNELS.TRENDS_LIVE);
  return { trends: data || [], lastUpdate, isConnected };
}

// Hook for product rankings
export function useProductRankings() {
  const { data, lastUpdate, isConnected } = useChannel<any[]>(WS_CHANNELS.PRODUCTS_RANKINGS);
  return { rankings: data || [], lastUpdate, isConnected };
}

// Hook for system status
export function useSystemStatus() {
  const { data, lastUpdate, isConnected } = useChannel<any>(WS_CHANNELS.SYSTEM_STATUS);
  return { status: data, lastUpdate, isConnected };
}

// Hook for Ospra insights
export function useOiInsights() {
  const { data, lastUpdate, isConnected } = useChannel<any[]>(WS_CHANNELS.OI_INSIGHTS);
  return { insights: data || [], lastUpdate, isConnected };
}

// Hook for notifications
export function useNotifications() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const { isConnected } = useWebSocket();

  useEffect(() => {
    if (!isConnected) return;

    const unsubscribe = wsService.subscribe(WS_CHANNELS.NOTIFICATIONS, (notification) => {
      setNotifications(prev => [notification, ...prev].slice(0, 50));
    });

    return unsubscribe;
  }, [isConnected]);

  const clearNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  return { notifications, clearNotification, clearAll, isConnected };
}

// Hook for real-time analytics
const DEFAULT_ANALYTICS = { visitors: 0, activeUsers: 0, ordersToday: 0, revenueToday: 0 };

export function useRealtimeAnalytics() {
  const { data, lastUpdate, isConnected } = useChannel<{
    visitors: number;
    activeUsers: number;
    ordersToday: number;
    revenueToday: number;
  }>(WS_CHANNELS.ANALYTICS_REALTIME);

  return {
    analytics: data || DEFAULT_ANALYTICS,
    lastUpdate,
    isConnected
  };
}

export default wsService;
