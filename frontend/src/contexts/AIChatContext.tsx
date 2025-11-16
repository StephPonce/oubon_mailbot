import React, { createContext, useContext, useState, useEffect } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface AIChatContextType {
  messages: Message[];
  isOpen: boolean;
  isMinimized: boolean;
  loading: boolean;
  addMessage: (message: Message) => void;
  setIsOpen: (open: boolean) => void;
  setIsMinimized: (minimized: boolean) => void;
  clearMessages: () => void;
  sendMessage: (text: string) => Promise<void>;
}

const AIChatContext = createContext<AIChatContextType | undefined>(undefined);

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
        setMessages(data.messages.map((m: any) => ({
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

  const gatherContextFromPage = async () => {
    const context: any = {
      url: window.location.href,
      pathname: window.location.pathname,
      timestamp: new Date().toISOString(),
      data: {}
    };

    // Determine current page and gather relevant data
    const path = window.location.pathname;

    try {
      // Always get portfolio overview
      const overviewRes = await fetch('http://localhost:8000/api/portfolio/overview');
      if (overviewRes.ok) {
        context.data.portfolio = await overviewRes.json();
      }

      // Page-specific data
      if (path.includes('products') || path.includes('product')) {
        // Get products data
        const productsRes = await fetch('http://localhost:8000/api/intelligence/discover', {
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
        // Get email data
        const emailRes = await fetch('http://localhost:8000/api/dashboard/emails');
        if (emailRes.ok) {
          context.data.emails = await emailRes.json();
          context.page_type = 'emails';
        }
      } else if (path.includes('analytics')) {
        context.page_type = 'analytics';
      } else {
        context.page_type = 'portfolio';
      }

      // Always get store data
      const rankingsRes = await fetch('http://localhost:8000/api/portfolio/rankings');
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

      const res = await fetch('http://localhost:8000/api/claude/chat', {
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
    } catch (err: any) {
      addMessage({
        role: 'assistant',
        content: `❌ Error: ${err.message}`,
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
