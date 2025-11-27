import React, { useState, useEffect, useContext } from 'react';
import { AIChatContext, type Message } from './AIChat.types';

export function AIChatProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [loading, setLoading] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('ospra_ai_chat');
    if (saved) {
      try {
        const data = JSON.parse(saved);
        setMessages(data.messages.map((m: Message) => ({
          ...m,
          timestamp: new Date(m.timestamp)
        })));
        setIsOpen(data.isOpen || false);
        setIsMinimized(data.isMinimized || false);
      } catch (e) {
        console.error('Failed to load chat:', e);
      }
    }
  }, []);

  // Save to localStorage on every change
  useEffect(() => {
    localStorage.setItem('ospra_ai_chat', JSON.stringify({
      messages,
      isOpen,
      isMinimized
    }));
  }, [messages, isOpen, isMinimized]);

  const addMessage = (message: Message) => {
    setMessages(prev => [...prev, message]);
  };

  const clearMessages = () => {
    if (confirm('Clear conversation history?')) {
      setMessages([]);
      localStorage.removeItem('ospra_ai_chat');
    }
  };

interface DashboardContext {
  url?: string;
  pathname?: string;
  timestamp: string;
  current_page?: string;
  page_type?: string;
  capabilities?: Record<string, any>;
  data: {
    portfolio?: any;
    rankings?: any;
    stores?: any;
    products?: {
      count: number;
      samples: any[];
      data_source: string;
    };
    emails?: any;
    email_stats?: any;
    tier?: any;
  };
}

  const gatherContextFromPage = async () => {
    const context: DashboardContext = {
      url: window.location.href,
      pathname: window.location.pathname,
      timestamp: new Date().toISOString(),
      data: {}
    };

    // Determine current page and gather relevant data
    const path = window.location.pathname;

    try {
      // Always get portfolio overview
      const overviewRes = await fetch('http://localhost:8001/api/portfolio/overview');
      if (overviewRes.ok) {
        context.data.portfolio = await overviewRes.json();
      }

      // Page-specific data
      if (path.includes('products') || path.includes('product')) {
        // Get products data
        const productsRes = await fetch('http://localhost:8001/api/intelligence/discover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ niches: ['smart_home'], max_per_niche: 10 })
        });
        if (productsRes.ok) {
          const data = await productsRes.json();
          context.data.products = data.products;
          context.page_type = 'products';
        }
      } else if (path.includes('email')) {
        // Get email data using correct unified API
        const userId = 1; // Default user ID

        // Get email stats
        const statsRes = await fetch(`http://localhost:8001/api/emails/stats/summary?user_id=${userId}`);
        if (statsRes.ok) {
          context.data.email_stats = await statsRes.json();
        }

        // Get recent emails list
        const emailsRes = await fetch(`http://localhost:8001/api/emails/list?user_id=${userId}&limit=20`);
        if (emailsRes.ok) {
          context.data.emails = await emailsRes.json();
        }

        context.page_type = 'emails';
        context.capabilities = {
          can_read_emails: true,
          can_reply_to_emails: true,
          can_mark_as_read: true,
          can_sync_emails: true
        };
      } else if (path.includes('analytics')) {
        context.page_type = 'analytics';
      } else {
        context.page_type = 'portfolio';
      }

      // Always get store data
      const rankingsRes = await fetch('http://localhost:8001/api/portfolio/rankings');
      if (rankingsRes.ok) {
        context.data.stores = await rankingsRes.json();
      }

    } catch (e) {
      console.error('Error gathering context:', e);
    }

    return context;
  };

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: text,
      timestamp: new Date()
    };

    addMessage(userMessage);
    setLoading(true);

    try {
      const context = await gatherContextFromPage();

      const res = await fetch('http://localhost:8001/api/claude/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          dashboard_context: context,
          conversation_history: messages.slice(-10)
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();

      if (data.success) {
        addMessage({
          role: 'assistant',
          content: data.message,
          timestamp: new Date()
        });
      } else {
        throw new Error(data.error);
      }
    } catch (err: unknown) {
      addMessage({
        role: 'assistant',
        content: `❌ Error: ${(err instanceof Error) ? err.message : 'An unknown error occurred'}`,
        timestamp: new Date()
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AIChatContext.Provider value={{
      messages,
      isOpen,
      isMinimized,
      loading,
      addMessage,
      setIsOpen,
      setIsMinimized,
      clearMessages,
      sendMessage
    }}>
      {children}
    </AIChatContext.Provider>
  );
}

export function useAIChat() {
  const context = useContext(AIChatContext);
  if (!context) {
    throw new Error('useAIChat must be used within AIChatProvider');
  }
  return context;
}




