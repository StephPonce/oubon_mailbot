/**
 * Ospra Intelligence - AI Hook
 * 
 * Connects to real backend endpoints:
 * - POST /api/dashboard/v2/claude/chat - AI chat
 * - GET /api/intelligence/briefing/morning - Daily briefing
 * - GET /api/dashboard/v2/overview - Dashboard metrics
 * - GET /api/health - Backend status
 */

import { useCallback, useEffect, useRef } from 'react';
import { useOspraStore } from '../store/ospra.store';
import api from '../services/api';

// ============================================
// TYPES
// ============================================

interface ChatResponse {
  response: string;
  timestamp?: string;
  actions?: Array<{
    type: string;
    label: string;
    path?: string;
    payload?: Record<string, unknown>;
  }>;
}

interface BriefingResponse {
  briefing_text: string;
  attention_items: Array<{
    title: string;
    description?: string;
    details?: string;
    priority: 'high' | 'medium' | 'low';
    action_label?: string;
  }>;
  metrics?: {
    trending_products: number;
    products_needing_attention: number;
    revenue_yesterday: number;
  };
}

interface DashboardOverview {
  products_count: number;
  active_products: number;
  revenue_today: number;
  revenue_week: number;
  orders_pending: number;
  emails_pending: number;
}

// ============================================
// MAIN HOOK
// ============================================

export function useOspra() {
  const {
    messages,
    isTyping,
    streamingContent,
    addMessage,
    setTyping,
    setStreamingContent,
    clearMessages,
    openChat,
    setConnected,
    setBackendStatus,
    userName,
    preferences,
    lastBriefingDate,
    setLastBriefingDate,
    addInsight,
  } = useOspraStore();

  const abortControllerRef = useRef<AbortController | null>(null);

  // ============================================
  // BACKEND STATUS CHECK
  // ============================================

  const checkBackendStatus = useCallback(async () => {
    setBackendStatus('checking');
    try {
      const response = await api.get('/health', { timeout: 5000 });
      if (response.data?.status === 'ok' || response.status === 200) {
        setBackendStatus('online');
        setConnected(true);
        return true;
      }
    } catch (error) {
      console.warn('[Ospra] Backend offline:', error);
      setBackendStatus('offline');
      setConnected(false);
    }
    return false;
  }, [setBackendStatus, setConnected]);

  // ============================================
  // SEND MESSAGE TO CLAUDE
  // ============================================

  const sendMessage = useCallback(async (
    content: string,
    context?: Record<string, unknown>
  ): Promise<string> => {
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Add user message to store
    addMessage({
      role: 'user',
      content,
    });

    setTyping(true);
    setStreamingContent('');

    try {
      // Build context with user info
      const enrichedContext = {
        userName: userName || 'Steph',
        preferences,
        currentPage: window.location.pathname || '/command-center',
        ...context,
      };

      console.log('[Ospra] Sending to backend:', content);
      console.log('[Ospra] Context:', enrichedContext);

      const response = await api.post<ChatResponse>(
        '/api/dashboard/v2/claude/chat',
        {
          message: content,
          context: enrichedContext,
        },
        {
          signal: abortControllerRef.current.signal,
        }
      );

      console.log('[Ospra] Backend response:', response.data);

      const assistantMessage = response.data.response || 'I apologize, I couldn\'t process that request.';

      // Simulate streaming effect for better UX
      const words = assistantMessage.split(' ');
      for (let i = 0; i < words.length; i++) {
        if (abortControllerRef.current?.signal.aborted) break;
        await new Promise((resolve) => setTimeout(resolve, 25));
        setStreamingContent(words.slice(0, i + 1).join(' '));
      }

      // Add complete message to store
      addMessage({
        role: 'assistant',
        content: assistantMessage,
        actions: response.data.actions?.map((a, idx) => ({
          id: `action-${Date.now()}-${idx}`,
          type: a.type as 'navigate' | 'deploy' | 'analyze' | 'discover' | 'dismiss',
          label: a.label,
          path: a.path,
          payload: a.payload,
        })),
      });

      setStreamingContent('');
      return assistantMessage;

    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[Ospra] Request cancelled');
        return '';
      }

      console.error('[Ospra] Chat error:', error);

      const errorMessage = 'I\'m having trouble connecting right now. Please check if the backend is running.';
      addMessage({
        role: 'assistant',
        content: errorMessage,
      });

      return errorMessage;

    } finally {
      setTyping(false);
      setStreamingContent('');
    }
  }, [addMessage, setTyping, setStreamingContent, userName, preferences]);

  // ============================================
  // MORNING BRIEFING
  // ============================================

  const fetchMorningBriefing = useCallback(async (): Promise<string | null> => {
    try {
      const response = await api.get<BriefingResponse>('/api/intelligence/briefing/morning');
      const data = response.data;

      // Add insights from attention items
      if (data.attention_items?.length) {
        data.attention_items.forEach((item) => {
          addInsight({
            type: item.priority === 'high' ? 'warning' : 
                  item.priority === 'medium' ? 'opportunity' : 'success',
            title: item.title,
            description: item.description || item.details || '',
            priority: item.priority,
            action: item.action_label ? {
              id: `action-${Date.now()}`,
              type: 'navigate',
              label: item.action_label,
            } : undefined,
          });
        });
      }

      return data.briefing_text || null;

    } catch (error) {
      console.error('[Ospra] Briefing error:', error);
      return null;
    }
  }, [addInsight]);

  // ============================================
  // PROACTIVE GREETING
  // ============================================

  const getGreeting = useCallback((): string => {
    const hour = new Date().getHours();
    const name = userName || 'there';

    if (hour < 12) {
      return `Good morning, ${name}! ☀️`;
    } else if (hour < 17) {
      return `Good afternoon, ${name}!`;
    } else {
      return `Good evening, ${name}! 🌙`;
    }
  }, [userName]);

  const shouldShowBriefing = useCallback((): boolean => {
    if (!lastBriefingDate) return true;

    const today = new Date().toDateString();
    const lastDate = new Date(lastBriefingDate).toDateString();

    return today !== lastDate;
  }, [lastBriefingDate]);

  const sendProactiveGreeting = useCallback(async () => {
    const greeting = getGreeting();
    
    // Check if we should fetch a new briefing
    if (shouldShowBriefing()) {
      setTyping(true);
      
      const briefing = await fetchMorningBriefing();
      
      if (briefing) {
        const fullMessage = `${greeting}\n\nHere's your daily briefing:\n\n${briefing}\n\nWant me to show you the trending products or help with something else?`;
        
        addMessage({
          role: 'assistant',
          content: fullMessage,
          actions: [
            {
              id: 'action-trends',
              type: 'navigate',
              label: 'Show Trending Products',
              path: '/trends',
            },
            {
              id: 'action-discover',
              type: 'discover',
              label: 'Discover New Products',
            },
            {
              id: 'action-dismiss',
              type: 'dismiss',
              label: 'Maybe Later',
            },
          ],
        });

        setLastBriefingDate(new Date().toISOString());
      } else {
        // Fallback greeting without briefing
        addMessage({
          role: 'assistant',
          content: `${greeting}\n\nI'm Ospra, your AI-powered e-commerce intelligence. I can help you discover winning products, analyze trends, and automate your store.\n\nWhat would you like to do today?`,
          actions: [
            {
              id: 'action-discover',
              type: 'discover',
              label: 'Discover Products',
            },
            {
              id: 'action-trends',
              type: 'navigate',
              label: 'View Trends',
              path: '/trends',
            },
          ],
        });
      }

      setTyping(false);
    } else {
      // Simple greeting if briefing already shown today
      addMessage({
        role: 'assistant',
        content: `${greeting} How can I help you?`,
      });
    }
  }, [
    getGreeting,
    shouldShowBriefing,
    fetchMorningBriefing,
    addMessage,
    setTyping,
    setLastBriefingDate,
  ]);

  // ============================================
  // DASHBOARD CONTEXT
  // ============================================

  const fetchDashboardContext = useCallback(async (): Promise<DashboardOverview | null> => {
    try {
      const response = await api.get<DashboardOverview>('/api/dashboard/v2/overview');
      return response.data;
    } catch (error) {
      console.error('[Ospra] Dashboard context error:', error);
      return null;
    }
  }, []);

  // ============================================
  // QUICK ACTIONS
  // ============================================

  const askAboutProducts = useCallback(() => {
    return sendMessage('What products are trending right now? Show me the top opportunities.');
  }, [sendMessage]);

  const askForAnalysis = useCallback((productName?: string) => {
    const query = productName
      ? `Analyze the product "${productName}" and tell me if it's worth selling.`
      : 'Give me an analysis of my current product performance.';
    return sendMessage(query);
  }, [sendMessage]);

  const askForRecommendations = useCallback(() => {
    return sendMessage('Based on current trends, what products should I add to my store?');
  }, [sendMessage]);

  const askAboutEmails = useCallback(() => {
    return sendMessage('How is my email automation performing? Any issues I should know about?');
  }, [sendMessage]);

  // ============================================
  // CLEANUP
  // ============================================

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // ============================================
  // RETURN
  // ============================================

  return {
    // State
    messages,
    isTyping,
    streamingContent,

    // Core Actions
    sendMessage,
    clearMessages,
    openChat,

    // Proactive Features
    sendProactiveGreeting,
    fetchMorningBriefing,
    getGreeting,
    shouldShowBriefing,

    // Quick Actions
    askAboutProducts,
    askForAnalysis,
    askForRecommendations,
    askAboutEmails,

    // Utilities
    checkBackendStatus,
    fetchDashboardContext,
  };
}

// ============================================
// SUGGESTED PROMPTS
// ============================================

export const OSPRA_SUGGESTED_PROMPTS = [
  {
    id: 'trending',
    icon: '📈',
    label: 'Trending Products',
    prompt: 'What products are trending right now?',
  },
  {
    id: 'discover',
    icon: '🔍',
    label: 'Discover Products',
    prompt: 'Find me new winning products in the smart home niche.',
  },
  {
    id: 'analyze',
    icon: '🧠',
    label: 'Analyze Performance',
    prompt: 'How are my products performing this week?',
  },
  {
    id: 'optimize',
    icon: '⚡',
    label: 'Optimize Strategy',
    prompt: 'What should I focus on to increase sales?',
  },
  {
    id: 'emails',
    icon: '📧',
    label: 'Email Status',
    prompt: 'Show me my email automation status.',
  },
  {
    id: 'briefing',
    icon: '☀️',
    label: 'Daily Briefing',
    prompt: 'Give me my daily business briefing.',
  },
];

export default useOspra;
