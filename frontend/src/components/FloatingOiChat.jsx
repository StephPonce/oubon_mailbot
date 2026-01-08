/**
 * OSPRA INTELLIGENCE - FLOATING OI CHAT (PERSISTENT)
 * ====================================================
 * 
 * NOW WITH:
 * - Conversation persists across page navigation
 * - Conversation survives page reload (localStorage)
 * - Real-time alerts from Oi
 * - Inline action execution
 * - Full dashboard awareness
 * 
 * @author OspraOS
 * @date January 2025
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Send, Sparkles, Loader2, X, Minimize2, Maximize2,
  ThumbsUp, ThumbsDown, Brain, RefreshCw, ChevronRight,
  Bell, Check, XCircle, Rocket, TrendingUp, AlertTriangle,
  Zap, Eye, Package, DollarSign, Trash2
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useDashboardContext } from '../hooks/useDashboardContext';
import { api } from '../services/api';

// ============================================================================
// PERSISTENCE KEYS
// ============================================================================

const STORAGE_KEYS = {
  MESSAGES: 'oi_chat_messages',
  CONVERSATION_ID: 'oi_conversation_id',
  IS_OPEN: 'oi_chat_open',
  IS_EXPANDED: 'oi_chat_expanded',
  ACTIVE_TAB: 'oi_chat_tab',
};

// Max messages to persist (prevent localStorage bloat)
const MAX_PERSISTED_MESSAGES = 50;

// ============================================================================
// PERSISTENCE HELPERS
// ============================================================================

function saveToStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn('Failed to save to localStorage:', e);
  }
}

function loadFromStorage(key, defaultValue) {
  try {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : defaultValue;
  } catch (e) {
    console.warn('Failed to load from localStorage:', e);
    return defaultValue;
  }
}

function clearStorage(key) {
  try {
    localStorage.removeItem(key);
  } catch (e) {
    console.warn('Failed to clear localStorage:', e);
  }
}

// ============================================================================
// ALERT COMPONENT
// ============================================================================

function OiAlert({ alert, onAction, onDismiss }) {
  const [executing, setExecuting] = useState(false);
  
  const iconMap = {
    trending_product: TrendingUp,
    price_drop: DollarSign,
    action_needed: Zap,
    opportunity: Rocket,
    warning: AlertTriangle,
    product_found: Package,
  };
  
  const Icon = iconMap[alert.type] || Bell;
  
  const priorityColors = {
    high: 'border-red-500/50 bg-red-500/10',
    medium: 'border-yellow-500/50 bg-yellow-500/10',
    low: 'border-blue-500/50 bg-blue-500/10',
  };
  
  const handleAction = async (action) => {
    setExecuting(true);
    try {
      await onAction(alert.id, action);
    } finally {
      setExecuting(false);
    }
  };
  
  return (
    <div className={`rounded-xl border p-3 mb-3 ${priorityColors[alert.priority] || priorityColors.medium}`}>
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center flex-shrink-0">
          <Icon className="w-4 h-4 text-white" />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-white font-medium text-sm">{alert.title}</span>
            {alert.score && (
              <span className="px-1.5 py-0.5 rounded bg-purple-500/30 text-purple-300 text-xs">
                {alert.score}/100
              </span>
            )}
          </div>
          
          <p className="text-white/60 text-xs mb-2">{alert.message}</p>
          
          {alert.actions && alert.actions.length > 0 && !alert.actioned && (
            <div className="flex gap-2">
              {alert.actions.map((action, i) => (
                <button
                  key={i}
                  onClick={() => handleAction(action.id)}
                  disabled={executing}
                  className={`px-2 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1 ${
                    action.primary 
                      ? 'bg-purple-500/30 text-purple-300 hover:bg-purple-500/50' 
                      : 'bg-white/10 text-white/60 hover:bg-white/20'
                  } disabled:opacity-50`}
                >
                  {executing ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                  {action.label}
                </button>
              ))}
            </div>
          )}
          
          {alert.actioned && (
            <div className="flex items-center gap-1 text-green-400 text-xs">
              <Check className="w-3 h-3" />
              {alert.actionResult || 'Done'}
            </div>
          )}
        </div>
        
        <button
          onClick={() => onDismiss(alert.id)}
          className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-white/60 transition-colors"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// CHAT MESSAGE COMPONENT
// ============================================================================

function ChatMessage({ message, isUser, onFeedback, showFeedback }) {
  const [feedbackGiven, setFeedbackGiven] = useState(null);
  
  const handleFeedback = (helpful) => {
    setFeedbackGiven(helpful);
    onFeedback?.(message.id, helpful);
  };
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-[85%]`}>
        {!isUser && (
          <div className="flex items-center gap-2 mb-1">
            <div className="w-5 h-5 rounded-md bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
              <Sparkles className="w-2.5 h-2.5 text-white" />
            </div>
            <span className="text-white/60 text-xs">Oi</span>
            {message.rememberedContext?.length > 0 && (
              <span className="text-purple-400/60 text-xs flex items-center gap-1">
                <Brain className="w-3 h-3" />
                remembered
              </span>
            )}
          </div>
        )}
        <div className={`rounded-xl px-3 py-2 text-sm ${
          isUser 
            ? 'bg-gradient-to-r from-purple-600 to-cyan-600 text-white' 
            : 'bg-white/10 text-white border border-white/10'
        }`}>
          <div className="whitespace-pre-wrap">{message.content}</div>
          
          {!isUser && message.inlineActions && message.inlineActions.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t border-white/10">
              {message.inlineActions.map((action, i) => (
                <button
                  key={i}
                  onClick={action.onClick}
                  className="px-2 py-1 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 transition-colors flex items-center gap-1"
                >
                  {action.icon && <action.icon className="w-3 h-3" />}
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>
        
        {!isUser && showFeedback && !feedbackGiven && (
          <div className="flex items-center gap-1 mt-1 ml-1">
            <button
              onClick={() => handleFeedback(true)}
              className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-green-400 transition-colors"
              title="Helpful"
            >
              <ThumbsUp className="w-3 h-3" />
            </button>
            <button
              onClick={() => handleFeedback(false)}
              className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-red-400 transition-colors"
              title="Not helpful"
            >
              <ThumbsDown className="w-3 h-3" />
            </button>
          </div>
        )}
        
        {feedbackGiven !== null && (
          <div className="text-xs text-white/40 mt-1 ml-1">
            Thanks for the feedback!
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// CONTEXT INDICATOR
// ============================================================================

function ContextIndicator({ context }) {
  const [expanded, setExpanded] = useState(false);
  
  if (!context) return null;
  
  const page = context.currentPage || 'dashboard';
  const productCount = context.allProducts?.trending_count || 0;
  const actionCount = context.pendingActions?.count || 0;
  const hasStore = context.connectionStatus?.stores;
  const hasProduct = !!context.selectedProduct;
  const isRealtime = context.connectionStatus?.realtime;
  
  return (
    <div className="px-3 py-2 border-b border-white/10 bg-white/5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs text-white/60 hover:text-white/80 transition-colors w-full"
      >
        <Brain className="w-3 h-3 text-purple-400" />
        <span>Viewing: {page}</span>
        {hasProduct && <span className="text-cyan-400">• product</span>}
        {productCount > 0 && <span className="text-purple-400">• {productCount} trending</span>}
        {actionCount > 0 && <span className="text-yellow-400">• {actionCount} actions</span>}
        {isRealtime && <span className="text-green-400">• live</span>}
        <ChevronRight className={`w-3 h-3 ml-auto transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      
      {expanded && (
        <div className="mt-2 text-xs text-white/50 space-y-1 pl-5">
          <div>Page: {page}</div>
          {hasProduct && <div>Selected: {context.selectedProduct?.name}</div>}
          <div>Trending products: {context.allProducts?.trending_count || 0}</div>
          <div>Recommended products: {context.allProducts?.recommended_count || 0}</div>
          <div>Pending actions: {actionCount}</div>
          <div>Autopilot: {context.autopilot?.is_active ? 'Active' : 'Disabled'}</div>
          <div>Store connected: {hasStore ? 'Yes' : 'No'}</div>
          <div>Real-time: {isRealtime ? 'Connected' : 'Polling'}</div>
          {context.recentSearches?.length > 0 && (
            <div>Recent searches: {context.recentSearches.slice(0, 3).join(', ')}</div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// MAIN FLOATING CHAT COMPONENT (PERSISTENT)
// ============================================================================

const DEFAULT_WELCOME = {
  id: 'welcome',
  content: "Hey! I'm Oi. I can see your entire dashboard - all products, actions, and metrics. I'll also alert you when I find opportunities. What would you like to do?",
  isUser: false,
  timestamp: new Date().toISOString(),
  rememberedContext: [],
};

export function FloatingOiChat() {
  const { user } = useAuth();
  const { 
    getFullContext, 
    trackInteraction, 
    state: dashboardState,
    executeAlertAction,
    dismissAlert,
    markAlertRead,
  } = useDashboardContext();
  
  // =========================================================================
  // PERSISTENT STATE - Survives page reload
  // =========================================================================
  
  const [isOpen, setIsOpen] = useState(() => loadFromStorage(STORAGE_KEYS.IS_OPEN, false));
  const [isExpanded, setIsExpanded] = useState(() => loadFromStorage(STORAGE_KEYS.IS_EXPANDED, false));
  const [activeTab, setActiveTab] = useState(() => loadFromStorage(STORAGE_KEYS.ACTIVE_TAB, 'chat'));
  const [conversationId, setConversationId] = useState(() => loadFromStorage(STORAGE_KEYS.CONVERSATION_ID, null));
  const [messages, setMessages] = useState(() => {
    const stored = loadFromStorage(STORAGE_KEYS.MESSAGES, null);
    if (stored && stored.length > 0) {
      // Restore timestamps as strings (they're serialized)
      return stored.map(m => ({ ...m, timestamp: m.timestamp }));
    }
    return [DEFAULT_WELCOME];
  });
  
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showContextIndicator, setShowContextIndicator] = useState(true);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const unreadAlertCount = dashboardState.unreadAlertCount || 0;
  const alerts = dashboardState.alerts || [];

  // =========================================================================
  // PERSIST STATE CHANGES
  // =========================================================================
  
  // Persist messages (debounced to avoid excessive writes)
  useEffect(() => {
    const timeout = setTimeout(() => {
      // Only persist non-welcome messages or if there's actual conversation
      const toSave = messages.slice(-MAX_PERSISTED_MESSAGES);
      saveToStorage(STORAGE_KEYS.MESSAGES, toSave);
    }, 500);
    
    return () => clearTimeout(timeout);
  }, [messages]);
  
  // Persist conversation ID
  useEffect(() => {
    if (conversationId) {
      saveToStorage(STORAGE_KEYS.CONVERSATION_ID, conversationId);
    }
  }, [conversationId]);
  
  // Persist open/expanded state
  useEffect(() => {
    saveToStorage(STORAGE_KEYS.IS_OPEN, isOpen);
  }, [isOpen]);
  
  useEffect(() => {
    saveToStorage(STORAGE_KEYS.IS_EXPANDED, isExpanded);
  }, [isExpanded]);
  
  // Persist active tab
  useEffect(() => {
    saveToStorage(STORAGE_KEYS.ACTIVE_TAB, activeTab);
  }, [activeTab]);

  // =========================================================================
  // UI EFFECTS
  // =========================================================================

  // Scroll to bottom when messages change
  useEffect(() => {
    if (isOpen && activeTab === 'chat') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen, activeTab]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen && activeTab === 'chat') {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, activeTab]);

  // Mark alerts as read when viewing alerts tab
  useEffect(() => {
    if (isOpen && activeTab === 'alerts') {
      alerts.filter(a => !a.read).forEach(a => markAlertRead(a.id));
    }
  }, [isOpen, activeTab, alerts, markAlertRead]);

  // =========================================================================
  // SUGGESTIONS
  // =========================================================================

  const getSuggestions = useCallback(() => {
    const page = dashboardState.currentPage;
    const hasProduct = !!dashboardState.selectedProduct;
    const trendingCount = dashboardState.allProducts?.trending?.length || 0;
    const actionCount = dashboardState.pendingActions?.length || 0;
    const autopilotActive = dashboardState.autopilotStatus?.is_active;
    
    const suggestions = [];
    
    if (hasProduct) {
      const productName = dashboardState.selectedProduct.name?.slice(0, 20) || 'this product';
      suggestions.push(`Analyze ${productName}`);
      suggestions.push('Deploy to store');
    }
    
    if (trendingCount > 0) {
      suggestions.push(`Show top ${Math.min(5, trendingCount)} trending`);
    }
    
    if (actionCount > 0) {
      suggestions.push(`Review ${actionCount} actions`);
    }
    
    if (!autopilotActive) {
      suggestions.push('Enable autopilot');
    }
    
    switch (page) {
      case 'dashboard':
      case 'overview':
        suggestions.push("How's my store doing?");
        break;
      case 'products':
        suggestions.push('Find similar products');
        break;
      case 'autopilot':
        suggestions.push('Autopilot recommendations');
        break;
    }
    
    return suggestions.slice(0, 4);
  }, [dashboardState]);

  // =========================================================================
  // HANDLERS
  // =========================================================================

  const handleAlertAction = async (alertId, action) => {
    try {
      const result = await executeAlertAction(alertId, action);
      
      setMessages(prev => [...prev, {
        id: `action-${Date.now()}`,
        content: `[OK] Done: ${result?.message || action}`,
        isUser: false,
        timestamp: new Date().toISOString(),
      }]);
      
      return result;
    } catch (error) {
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        content: `Failed: ${error.message}`,
        isUser: false,
        timestamp: new Date().toISOString(),
      }]);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      content: input,
      isUser: true,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    const userInput = input;
    setInput('');
    setLoading(true);

    try {
      const dashboardContext = getFullContext();
      
      const response = await api.chatWithContext(userInput, {
        dashboard_context: dashboardContext,
        conversation_id: conversationId,
        execute_actions: true,
      });
      
      if (response.conversation_id && !conversationId) {
        setConversationId(response.conversation_id);
      }
      
      const aiContent = response.message 
        || response.response 
        || response.content 
        || "I received your message but couldn't generate a response.";

      const inlineActions = response.suggested_actions?.map(action => ({
        label: action.label,
        icon: action.icon === 'deploy' ? Rocket : action.icon === 'analyze' ? Eye : Zap,
        onClick: () => handleAlertAction(action.id, action.action),
      })) || [];

      const aiMessage = {
        id: response.message_id || `ai-${Date.now()}`,
        content: aiContent,
        isUser: false,
        timestamp: new Date().toISOString(),
        rememberedContext: response.remembered_context || [],
        inlineActions,
      };

      setMessages(prev => [...prev, aiMessage]);
      
      trackInteraction('oi_chat', {
        query: userInput,
        page: dashboardContext.currentPage,
        had_selected_product: !!dashboardContext.selectedProduct,
        context_size: JSON.stringify(dashboardContext).length,
      });

    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        content: `Connection error: ${error.message}. Make sure the backend is running.`,
        isUser: false,
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (messageId, helpful) => {
    try {
      const dashboardContext = getFullContext();
      await api.submitOiFeedback({
        message_id: messageId,
        helpful,
        context: dashboardContext,
      });
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setInput(suggestion);
    inputRef.current?.focus();
  };

  const clearConversation = () => {
    setMessages([{
      ...DEFAULT_WELCOME,
      id: `welcome-${Date.now()}`,
      content: "Conversation cleared. I still have full visibility into your dashboard. How can I help?",
      timestamp: new Date().toISOString(),
    }]);
    setConversationId(null);
    clearStorage(STORAGE_KEYS.CONVERSATION_ID);
  };

  // =========================================================================
  // RENDER
  // =========================================================================

  // Floating button when closed
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-to-r from-purple-600 to-cyan-600 text-white shadow-lg hover:shadow-xl hover:scale-105 transition-all z-50 flex items-center justify-center group"
      >
        <Sparkles className="w-6 h-6" />
        
        {/* Unread alert badge */}
        {unreadAlertCount > 0 && (
          <div className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center font-bold">
            {unreadAlertCount > 9 ? '9+' : unreadAlertCount}
          </div>
        )}
        
        {/* Message count indicator (shows conversation exists) */}
        {messages.length > 1 && (
          <div className="absolute -bottom-1 -left-1 w-4 h-4 rounded-full bg-purple-500 text-white text-[10px] flex items-center justify-center">
            {messages.length > 99 ? '99' : messages.length - 1}
          </div>
        )}
        
        <span className="absolute right-full mr-3 px-3 py-1.5 rounded-lg bg-black/80 text-white text-sm whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
          Chat with Oi {unreadAlertCount > 0 ? `(${unreadAlertCount} new)` : ''}
        </span>
      </button>
    );
  }

  const windowSize = isExpanded 
    ? 'w-[500px] h-[700px]' 
    : 'w-[400px] h-[560px]';

  const currentContext = getFullContext();
  const suggestions = getSuggestions();

  return (
    <div className={`fixed bottom-6 right-6 ${windowSize} z-50 flex flex-col rounded-2xl overflow-hidden shadow-2xl border border-white/20 backdrop-blur-xl bg-slate-900/95 transition-all duration-200`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-white font-semibold text-sm">Oi Assistant</h3>
            <div className="flex items-center gap-1">
              <div className={`w-1.5 h-1.5 rounded-full ${dashboardState.connectionStatus?.websocket ? 'bg-green-500' : 'bg-yellow-500'}`} />
              <span className={`text-xs ${dashboardState.connectionStatus?.websocket ? 'text-green-400' : 'text-yellow-400'}`}>
                {dashboardState.connectionStatus?.websocket ? 'Live' : 'Polling'}
              </span>
              {messages.length > 1 && (
                <span className="text-white/40 text-xs ml-2">
                  • {messages.length - 1} messages
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={clearConversation}
            className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
            title="Clear conversation"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/10">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 py-2 text-sm font-medium transition-colors ${
            activeTab === 'chat' 
              ? 'text-white border-b-2 border-purple-500' 
              : 'text-white/60 hover:text-white'
          }`}
        >
          Chat
          {messages.length > 1 && (
            <span className="ml-1 text-xs text-white/40">({messages.length - 1})</span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('alerts')}
          className={`flex-1 py-2 text-sm font-medium transition-colors relative ${
            activeTab === 'alerts' 
              ? 'text-white border-b-2 border-purple-500' 
              : 'text-white/60 hover:text-white'
          }`}
        >
          Alerts
          {unreadAlertCount > 0 && (
            <span className="absolute top-1 right-1/4 w-4 h-4 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">
              {unreadAlertCount > 9 ? '9+' : unreadAlertCount}
            </span>
          )}
        </button>
      </div>

      {/* Context Indicator (chat tab only) */}
      {activeTab === 'chat' && showContextIndicator && (
        <ContextIndicator context={currentContext} />
      )}

      {/* Content */}
      {activeTab === 'chat' ? (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4">
            {messages.map((message, index) => (
              <ChatMessage 
                key={message.id} 
                message={message} 
                isUser={message.isUser}
                onFeedback={handleFeedback}
                showFeedback={!message.isUser && index === messages.length - 1 && !loading}
              />
            ))}
            
            {loading && (
              <div className="flex items-center gap-2 text-white/60">
                <div className="w-5 h-5 rounded-md bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
                  <Loader2 className="w-2.5 h-2.5 text-white animate-spin" />
                </div>
                <span className="text-xs">Oi is analyzing your dashboard...</span>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Context-aware suggestions (only show for new conversations) */}
          {messages.length <= 2 && suggestions.length > 0 && (
            <div className="px-4 py-2 border-t border-white/10">
              <div className="text-xs text-white/40 mb-1.5">Quick actions:</div>
              <div className="flex flex-wrap gap-1.5">
                {suggestions.map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="px-2.5 py-1 rounded-lg bg-white/5 text-white/70 text-xs hover:bg-purple-500/20 hover:text-white border border-white/10 transition-all"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="p-3 border-t border-white/10">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask Oi anything..."
                disabled={loading}
                className="flex-1 px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder-white/40 focus:outline-none focus:border-purple-500/50 transition-all disabled:opacity-50"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="p-2 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white hover:from-purple-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </>
      ) : (
        /* Alerts Tab */
        <div className="flex-1 overflow-y-auto p-4">
          {alerts.length > 0 ? (
            alerts.map(alert => (
              <OiAlert
                key={alert.id}
                alert={alert}
                onAction={handleAlertAction}
                onDismiss={dismissAlert}
              />
            ))
          ) : (
            <div className="text-center py-12">
              <Bell className="w-12 h-12 text-white/20 mx-auto mb-3" />
              <p className="text-white/60 text-sm">No alerts yet</p>
              <p className="text-white/40 text-xs mt-1">I'll notify you when I find opportunities</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default FloatingOiChat;
