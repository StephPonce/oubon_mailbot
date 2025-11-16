import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, X, Minimize2, Maximize2, Trash2 } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface AIChatProps {
  // We gather context ourselves instead of relying on props
}

export default function AIChat(props: AIChatProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const quickPrompts = [
    "Analyze my store performance",
    "Suggest products for my niche",
    "What should I focus on today?",
    "How can I improve conversions?",
    "Review my product lineup",
  ];

  // Load conversation from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('claude_conversation');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setMessages(parsed.map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp)
        })));
      } catch (e) {
        console.error('Failed to load conversation:', e);
      }
    }
  }, []);

  // Save conversation to localStorage whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('claude_conversation', JSON.stringify(messages));
    }
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const gatherDashboardContext = async () => {
    /**
     * Gather comprehensive dashboard data for Claude
     */
    const context: any = {
      timestamp: new Date().toISOString(),
      current_page: window.location.pathname,
      data: {}
    };

    try {
      // Get portfolio overview
      try {
        const overviewRes = await fetch('http://localhost:8000/api/portfolio/overview');
        if (overviewRes.ok) {
          context.data.portfolio = await overviewRes.json();
        }
      } catch (e) {
        console.log('Portfolio data not available');
      }

      // Get store rankings
      try {
        const rankingsRes = await fetch('http://localhost:8000/api/portfolio/rankings');
        if (rankingsRes.ok) {
          context.data.rankings = await rankingsRes.json();
        }
      } catch (e) {
        console.log('Rankings data not available');
      }

      // Get products based on current page
      if (window.location.pathname.includes('products')) {
        try {
          const productsRes = await fetch('http://localhost:8000/api/dashboard/v2/products?niche=smart_home&per_page=10');
          if (productsRes.ok) {
            const productsData = await productsRes.json();
            context.data.products = {
              count: productsData.products?.length || 0,
              samples: productsData.products?.slice(0, 5) || [],
              data_source: productsData.data_source
            };
          }
        } catch (e) {
          console.log('Products data not available');
        }
      }

      // Get email stats if available
      try {
        const emailRes = await fetch('http://localhost:8000/api/dashboard/emails');
        if (emailRes.ok) {
          context.data.emails = await emailRes.json();
        }
      } catch (e) {
        console.log('Email data not available');
      }

      // Get user tier info
      try {
        const tierRes = await fetch('http://localhost:8000/api/user/tier?user_id=1');
        if (tierRes.ok) {
          context.data.tier = await tierRes.json();
        }
      } catch (e) {
        console.log('Tier info not available');
      }

    } catch (e) {
      console.error('Error gathering context:', e);
    }

    return context;
  };

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: messageText,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // Gather comprehensive dashboard context
      const dashboardContext = await gatherDashboardContext();

      const res = await fetch('http://localhost:8000/api/claude/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageText,
          dashboard_context: dashboardContext,
          conversation_history: messages.slice(-10) // Last 10 messages for context
        })
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();

      if (data.success) {
        const aiMessage: Message = {
          role: 'assistant',
          content: data.demo_mode
            ? "💡 " + data.message
            : data.message,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, aiMessage]);
      } else {
        throw new Error(data.error || 'Unknown error');
      }
    } catch (err: any) {
      console.error('Chat error:', err);
      const errorMessage: Message = {
        role: 'assistant',
        content: `❌ Error: ${err.message}\n\nTip: Make sure the backend is running and ANTHROPIC_API_KEY is set.`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const clearConversation = () => {
    if (confirm('Clear conversation history?')) {
      setMessages([]);
      localStorage.removeItem('claude_conversation');
    }
  };

  const handleQuickPrompt = (prompt: string) => {
    sendMessage(prompt);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-full p-4 shadow-lg transition-all z-50 flex items-center gap-2"
      >
        <Sparkles className="w-6 h-6" />
        <span className="font-semibold">Ask Claude AI</span>
      </button>
    );
  }

  return (
    <div className={`fixed ${isMinimized ? 'bottom-6 right-6' : 'bottom-6 right-6'} z-50 transition-all`}>
      <div className={`bg-gray-900 rounded-xl shadow-2xl border border-gray-800 ${isMinimized ? 'w-80' : 'w-96 h-[600px]'} flex flex-col`}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gradient-to-r from-blue-600 to-purple-600">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-white" />
            <h3 className="font-semibold text-white">Claude AI Assistant</h3>
          </div>
          <div className="flex items-center gap-3">
            {messages.length > 0 && (
              <button
                onClick={clearConversation}
                className="text-white/60 hover:text-white transition-colors"
                title="Clear conversation"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              className="text-white/80 hover:text-white"
            >
              {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white/80 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {!isMinimized && (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="text-center py-8">
                  <Sparkles className="w-12 h-12 text-blue-500 mx-auto mb-4" />
                  <p className="text-gray-400 mb-4">How can I help you today?</p>
                  <div className="space-y-2">
                    {quickPrompts.map((prompt, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleQuickPrompt(prompt)}
                        className="w-full text-left px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition-colors"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-2 ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-200'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <p className="text-xs opacity-60 mt-1">
                      {msg.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-800 rounded-lg px-4 py-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-800">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  sendMessage(input);
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask Claude anything..."
                  className="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-white transition-colors"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
