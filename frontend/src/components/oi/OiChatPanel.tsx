/**
 * Oi Chat Panel - The Brain of Ospra Intelligence
 * 
 * NOW WITH:
 * - Dashboard context awareness (knows what you're looking at)
 * - Self-learning (improves from feedback)
 * - Personalized responses
 * 
 * @author OspraOS
 * @date December 2024
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Send,
  X,
  Sparkles,
  Loader2,
  Zap,
  User,
  RefreshCw,
  Trash2,
  Maximize2,
  Minimize2,
  Copy,
  Check,
  AlertTriangle,
  Database,
  ThumbsUp,
  ThumbsDown,
  Eye,
  Lightbulb
} from 'lucide-react';
import { useOi, useOiChat, type OiResponse } from '../../contexts/OiContext';

// Types
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  actions?: ActionTaken[];
  suggestions?: string[];
  disclaimer?: string;
  warnings?: string[];
  messageId?: string;  // For feedback tracking
  learnedFrom?: string[];  // What Oi learned from
}

interface ActionTaken {
  action: string;
  status: string;
  message: string;
  data?: Record<string, unknown>;
}

interface OiChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

// API service
const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Data status banner component
const DataStatusBanner: React.FC<{ disclaimer: string; context: ReturnType<typeof useOi>['dashboardContext'] }> = ({ 
  disclaimer, 
  context 
}) => {
  if (!disclaimer) return null;
  
  const isWarning = disclaimer.includes('No data') || disclaimer.includes('Not connected');
  const isPartial = disclaimer.includes('Not connected:');
  
  // Show what Oi can see
  const canSee = [];
  if (context.selectedProduct) canSee.push(`product: ${context.selectedProduct.name}`);
  if (context.selectedStore) canSee.push(`store: ${context.selectedStore.store_name}`);
  if (context.visibleProducts.length > 0) canSee.push(`${context.visibleProducts.length} products on screen`);
  if (context.storeMetrics) canSee.push('store metrics');
  
  return (
    <div className={`
      px-4 py-2 text-xs border-b space-y-1
      ${isWarning 
        ? 'bg-amber-500/10 border-amber-500/20' 
        : isPartial
          ? 'bg-blue-500/10 border-blue-500/20'
          : 'bg-emerald-500/10 border-emerald-500/20'
      }
    `}>
      <div className="flex items-center gap-2">
        <Database className="w-3 h-3 flex-shrink-0 text-white/50" />
        <span className={isWarning ? 'text-amber-300' : isPartial ? 'text-blue-300' : 'text-emerald-300'}>
          {disclaimer}
        </span>
      </div>
      {canSee.length > 0 && (
        <div className="flex items-center gap-2 text-white/40">
          <Eye className="w-3 h-3 flex-shrink-0" />
          <span>Oi can see: {canSee.join(', ')}</span>
        </div>
      )}
    </div>
  );
};

// Validation warning component
const ValidationWarnings: React.FC<{ warnings: string[] }> = ({ warnings }) => {
  if (!warnings || warnings.length === 0) return null;
  
  return (
    <div className="mt-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
      <div className="flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-amber-300">
          <p className="font-medium mb-1">Data verification notice:</p>
          <ul className="space-y-0.5 text-amber-300/80">
            {warnings.map((warning, idx) => (
              <li key={idx}>• {warning}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

// Learning indicator
const LearnedFromIndicator: React.FC<{ patterns: string[] }> = ({ patterns }) => {
  if (!patterns || patterns.length === 0) return null;
  
  return (
    <div className="mt-2 flex items-center gap-1 text-xs text-cyan-400/60">
      <Lightbulb className="w-3 h-3" />
      <span>Personalized from: {patterns.join(', ')}</span>
    </div>
  );
};

// Typing indicator component
const TypingIndicator: React.FC = () => (
  <div className="flex items-center gap-1 px-4 py-2">
    <motion.div
      className="w-2 h-2 rounded-full bg-emerald-400"
      animate={{ y: [0, -4, 0] }}
      transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
    />
    <motion.div
      className="w-2 h-2 rounded-full bg-emerald-400"
      animate={{ y: [0, -4, 0] }}
      transition={{ duration: 0.6, repeat: Infinity, delay: 0.15 }}
    />
    <motion.div
      className="w-2 h-2 rounded-full bg-emerald-400"
      animate={{ y: [0, -4, 0] }}
      transition={{ duration: 0.6, repeat: Infinity, delay: 0.3 }}
    />
  </div>
);

// Feedback buttons component
const FeedbackButtons: React.FC<{ 
  messageId: string; 
  onFeedback: (helpful: boolean) => void;
  disabled?: boolean;
}> = ({ messageId, onFeedback, disabled }) => {
  const [submitted, setSubmitted] = useState<'up' | 'down' | null>(null);
  
  const handleFeedback = (helpful: boolean) => {
    if (disabled || submitted) return;
    setSubmitted(helpful ? 'up' : 'down');
    onFeedback(helpful);
  };
  
  return (
    <div className="flex items-center gap-1 mt-2">
      <span className="text-xs text-white/30 mr-1">Helpful?</span>
      <button
        onClick={() => handleFeedback(true)}
        disabled={disabled || submitted !== null}
        className={`p-1 rounded transition-colors ${
          submitted === 'up' 
            ? 'bg-emerald-500/20 text-emerald-400' 
            : 'hover:bg-white/10 text-white/40 hover:text-white/70'
        }`}
      >
        <ThumbsUp className="w-3 h-3" />
      </button>
      <button
        onClick={() => handleFeedback(false)}
        disabled={disabled || submitted !== null}
        className={`p-1 rounded transition-colors ${
          submitted === 'down' 
            ? 'bg-red-500/20 text-red-400' 
            : 'hover:bg-white/10 text-white/40 hover:text-white/70'
        }`}
      >
        <ThumbsDown className="w-3 h-3" />
      </button>
      {submitted && (
        <span className="text-xs text-white/30 ml-1">Thanks!</span>
      )}
    </div>
  );
};

// Message bubble component
const MessageBubble: React.FC<{ 
  message: Message; 
  onCopy: (text: string) => void;
  onFeedback: (messageId: string, helpful: boolean) => void;
}> = ({ message, onCopy, onFeedback }) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    onCopy(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
    >
      <div className={`flex items-start gap-3 max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
        {/* Avatar */}
        <div className={`
          w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
          ${isUser 
            ? 'bg-gradient-to-br from-blue-500 to-blue-600' 
            : 'bg-gradient-to-br from-emerald-500 to-cyan-500'
          }
        `}>
          {isUser ? (
            <User className="w-4 h-4 text-white" />
          ) : (
            <Brain className="w-4 h-4 text-white" />
          )}
        </div>

        {/* Message Content */}
        <div className={`
          rounded-2xl px-4 py-3 relative group
          ${isUser 
            ? 'bg-gradient-to-r from-blue-600/90 to-blue-500/90 text-white' 
            : 'bg-white/10 backdrop-blur-xl border border-white/20 text-white'
          }
        `}>
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
          
          {/* Learned from indicator */}
          {!isUser && message.learnedFrom && message.learnedFrom.length > 0 && (
            <LearnedFromIndicator patterns={message.learnedFrom} />
          )}
          
          {/* Validation warnings */}
          {!isUser && message.warnings && message.warnings.length > 0 && (
            <ValidationWarnings warnings={message.warnings} />
          )}
          
          {/* Actions taken */}
          {message.actions && message.actions.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/10">
              <p className="text-xs text-emerald-300 flex items-center gap-1 mb-2">
                <Zap className="w-3 h-3" /> Actions executed:
              </p>
              {message.actions.map((action, idx) => (
                <div key={idx} className="text-xs bg-white/5 rounded px-2 py-1 mt-1">
                  <span className={`${action.status === 'success' ? 'text-emerald-400' : 'text-amber-400'}`}>
                    [{action.status}]
                  </span>{' '}
                  {action.message}
                </div>
              ))}
            </div>
          )}

          {/* Suggestions */}
          {message.suggestions && message.suggestions.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/10">
              <p className="text-xs text-cyan-300 flex items-center gap-1 mb-2">
                <Sparkles className="w-3 h-3" /> Suggestions:
              </p>
              <div className="flex flex-wrap gap-2">
                {message.suggestions.map((suggestion, idx) => (
                  <span 
                    key={idx} 
                    className="text-xs bg-white/10 rounded-full px-2 py-1 cursor-pointer hover:bg-white/20 transition-colors"
                  >
                    {suggestion}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Feedback buttons for assistant messages */}
          {!isUser && message.messageId && (
            <FeedbackButtons 
              messageId={message.messageId}
              onFeedback={(helpful) => onFeedback(message.messageId!, helpful)}
            />
          )}

          {/* Copy button */}
          <button
            onClick={handleCopy}
            className={`
              absolute -bottom-2 ${isUser ? 'left-2' : 'right-2'} 
              opacity-0 group-hover:opacity-100 transition-opacity
              bg-white/10 backdrop-blur-xl rounded-full p-1.5 hover:bg-white/20
            `}
          >
            {copied ? (
              <Check className="w-3 h-3 text-emerald-400" />
            ) : (
              <Copy className="w-3 h-3 text-white/70" />
            )}
          </button>

          {/* Timestamp */}
          <span className={`
            text-[10px] text-white/40 absolute -bottom-5 
            ${isUser ? 'right-0' : 'left-0'}
          `}>
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    </motion.div>
  );
};

// Quick actions - context-aware
const QuickActions: React.FC<{ 
  onSelect: (prompt: string) => void;
  context: ReturnType<typeof useOi>['dashboardContext'];
}> = ({ onSelect, context }) => {
  // Build context-aware actions
  const actions = [];
  
  // If viewing a product, offer product-specific actions
  if (context.selectedProduct) {
    actions.push({
      icon: '[STATS]',
      label: `Analyze ${context.selectedProduct.name.slice(0, 20)}...`,
      prompt: `Analyze the product I'm looking at: ${context.selectedProduct.name}. Should I deploy it?`
    });
  }
  
  // If products are visible, offer comparison
  if (context.visibleProducts.length > 1) {
    actions.push({
      icon: '',
      label: `Compare ${context.visibleProducts.length} products`,
      prompt: `Compare the ${context.visibleProducts.length} products I can see. Which is the best opportunity?`
    });
  }
  
  // If store is connected, offer store actions
  if (context.storeMetrics) {
    actions.push({
      icon: '[TREND]',
      label: 'Store performance',
      prompt: 'How is my store performing? Any recommendations?'
    });
  }
  
  // Default actions
  if (actions.length < 4) {
    actions.push({
      icon: '[LINK]',
      label: 'Connect store',
      prompt: 'How do I connect my Shopify store?'
    });
  }
  
  if (actions.length < 4) {
    actions.push({
      icon: '[TIP]',
      label: 'Get started',
      prompt: 'What should I set up first to get the most out of Ospra?'
    });
  }
  
  if (actions.length < 4) {
    actions.push({
      icon: '[QUESTION]',
      label: 'Help',
      prompt: 'What can you help me with?'
    });
  }

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {actions.slice(0, 4).map((action, idx) => (
        <motion.button
          key={idx}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onSelect(action.prompt)}
          className="
            flex items-center gap-2 px-3 py-2 rounded-xl
            bg-white/5 hover:bg-white/10 border border-white/10
            text-sm text-white/80 transition-all
          "
        >
          <span>{action.icon}</span>
          <span>{action.label}</span>
        </motion.button>
      ))}
    </div>
  );
};

// Main component
export const OiChatPanel: React.FC<OiChatPanelProps> = ({ isOpen, onClose }) => {
  // Use the Oi context
  const { 
    dashboardContext, 
    chatWithOi, 
    isOiLoading, 
    trackFeedback 
  } = useOi();
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isHealthy, setIsHealthy] = useState(true);
  const [dataDisclaimer, setDataDisclaimer] = useState<string>('');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Check API health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/oi/health`);
        const health = await response.json();
        setIsHealthy(health.status === 'healthy');
      } catch {
        setIsHealthy(false);
      }
    };
    if (isOpen) checkHealth();
  }, [isOpen]);

  // Update disclaimer based on context
  useEffect(() => {
    const status = dashboardContext.connectionStatus;
    const connected = [];
    const notConnected = [];
    
    if (status.stores) connected.push('stores');
    else notConnected.push('stores');
    
    if (status.intelligence) connected.push('intelligence');
    else notConnected.push('intelligence');
    
    if (status.email) connected.push('email');
    else notConnected.push('email');
    
    if (connected.length === 0) {
      setDataDisclaimer('[WARNING] No data sources connected. Responses are general guidance only.');
    } else if (notConnected.length > 0) {
      setDataDisclaimer(`[STATS] Connected: ${connected.join(', ')} | Not connected: ${notConnected.join(', ')}`);
    } else {
      setDataDisclaimer('[SUCCESS] All data sources connected');
    }
  }, [dashboardContext.connectionStatus]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Add context-aware welcome message
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      let welcomeContent = `Hey! I'm Oi, your AI assistant for Ospra Intelligence.\n\n`;
      
      // Personalize based on what's connected
      if (dashboardContext.selectedStore) {
        welcomeContent += `I can see you have ${dashboardContext.selectedStore.store_name} connected. `;
      }
      
      if (dashboardContext.selectedProduct) {
        welcomeContent += `\n\nYou're looking at "${dashboardContext.selectedProduct.name}". Want me to analyze it?`;
      } else if (dashboardContext.visibleProducts.length > 0) {
        welcomeContent += `\n\nI can see ${dashboardContext.visibleProducts.length} products on your screen. Need help choosing the best one?`;
      } else {
        welcomeContent += `\nI can help you with:\n- Connecting and managing your stores\n- Analyzing products and market trends\n- Deploying products to your store\n\nWhat would you like to know?`;
      }
      
      setMessages([{
        id: 'welcome',
        role: 'assistant',
        content: welcomeContent,
        timestamp: new Date(),
      }]);
    }
  }, [isOpen, messages.length, dashboardContext]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isOiLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');

    try {
      // Use the context-aware chatWithOi
      const response = await chatWithOi(userMessage.content);
      
      // Update disclaimer
      if (response.data_disclaimer) {
        setDataDisclaimer(response.data_disclaimer);
      }
      
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        actions: response.actions_taken,
        suggestions: response.suggestions,
        warnings: response.validation_warnings,
        messageId: response.message_id,  // For feedback
        learnedFrom: response.learned_from,  // What patterns were used
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: "Sorry, I encountered an error. Please try again or check if the backend is running.",
        timestamp: new Date(),
      }]);
    }
  }, [input, isOiLoading, chatWithOi]);

  const handleClearChat = async () => {
    try {
      await fetch(`${apiBaseUrl}/api/oi/conversation/clear`, { method: 'POST' });
      setMessages([]);
    } catch (error) {
      console.error('Failed to clear chat:', error);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleQuickAction = (prompt: string) => {
    setInput(prompt);
    setTimeout(() => handleSend(), 100);
  };

  const handleFeedback = (messageId: string, helpful: boolean) => {
    trackFeedback(messageId, helpful);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
          />

          {/* Chat Panel */}
          <motion.div
            initial={{ opacity: 0, x: 100, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 100, scale: 0.95 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className={`
              fixed right-4 z-50
              ${isExpanded 
                ? 'top-4 bottom-4 w-[600px]' 
                : 'top-20 bottom-20 w-[420px]'
              }
              bg-gradient-to-br from-slate-900/95 via-slate-800/95 to-slate-900/95
              backdrop-blur-2xl border border-white/10 rounded-3xl
              flex flex-col overflow-hidden shadow-2xl
              transition-all duration-300
            `}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 flex items-center justify-center">
                    <Brain className="w-5 h-5 text-white" />
                  </div>
                  <div className={`
                    absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-slate-900
                    ${isHealthy ? 'bg-emerald-400' : 'bg-amber-400'}
                  `} />
                </div>
                <div>
                  <h3 className="text-white font-semibold flex items-center gap-2">
                    Oi
                    <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">
                      Context-Aware
                    </span>
                  </h3>
                  <p className="text-xs text-white/50">
                    {dashboardContext.currentPage && `Viewing: ${dashboardContext.currentPage}`}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleClearChat}
                  className="p-2 rounded-xl hover:bg-white/10 text-white/50 hover:text-white transition-colors"
                  title="Clear conversation"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="p-2 rounded-xl hover:bg-white/10 text-white/50 hover:text-white transition-colors"
                  title={isExpanded ? 'Collapse' : 'Expand'}
                >
                  {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                </button>
                <button
                  onClick={onClose}
                  className="p-2 rounded-xl hover:bg-white/10 text-white/50 hover:text-white transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Data Status Banner - Shows what Oi can see */}
            <DataStatusBanner disclaimer={dataDisclaimer} context={dashboardContext} />

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2">
              {messages.map((msg) => (
                <MessageBubble 
                  key={msg.id} 
                  message={msg} 
                  onCopy={handleCopy}
                  onFeedback={handleFeedback}
                />
              ))}
              
              {isOiLoading && (
                <div className="flex items-start gap-3 mb-4">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
                    <Brain className="w-4 h-4 text-white" />
                  </div>
                  <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl">
                    <TypingIndicator />
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* Quick Actions - Context-aware */}
            {messages.length <= 2 && (
              <div className="px-5 pb-2">
                <QuickActions onSelect={handleQuickAction} context={dashboardContext} />
              </div>
            )}

            {/* Input Area */}
            <div className="px-5 py-4 border-t border-white/10">
              <div className="flex items-end gap-3">
                <div className="flex-1 relative">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask Oi anything..."
                    rows={1}
                    className="
                      w-full px-4 py-3 pr-12 rounded-2xl resize-none
                      bg-white/5 border border-white/10 
                      text-white placeholder-white/40
                      focus:outline-none focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20
                      transition-all
                    "
                    style={{ minHeight: '48px', maxHeight: '120px' }}
                  />
                  
                  {input.length > 100 && (
                    <span className="absolute right-14 bottom-3 text-xs text-white/30">
                      {input.length}/4000
                    </span>
                  )}
                </div>

                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleSend}
                  disabled={!input.trim() || isOiLoading}
                  className={`
                    w-12 h-12 rounded-2xl flex items-center justify-center
                    ${input.trim() && !isOiLoading
                      ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white shadow-lg shadow-emerald-500/25'
                      : 'bg-white/10 text-white/30 cursor-not-allowed'
                    }
                    transition-all
                  `}
                >
                  {isOiLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </motion.button>
              </div>

              <p className="text-[10px] text-white/30 mt-2 text-center">
                Press Enter to send · Shift+Enter for new line · Cmd/Ctrl+K to toggle
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

// Floating Oi Button
export const OiFloatingButton: React.FC<{ onClick: () => void; hasUnread?: boolean }> = ({ 
  onClick, 
  hasUnread = false 
}) => {
  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className="
        fixed bottom-6 right-6 z-30
        w-14 h-14 rounded-2xl
        bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500
        shadow-lg shadow-emerald-500/30
        flex items-center justify-center
        group
      "
    >
      <Brain className="w-6 h-6 text-white group-hover:scale-110 transition-transform" />
      
      <span className="absolute inset-0 rounded-2xl bg-emerald-400 animate-ping opacity-20" />
      
      {hasUnread && (
        <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full border-2 border-slate-900 flex items-center justify-center">
          <span className="text-[8px] text-white font-bold">!</span>
        </span>
      )}
      
      <span className="
        absolute bottom-full mb-2 right-0
        px-3 py-1.5 rounded-lg
        bg-slate-800 text-white text-sm whitespace-nowrap
        opacity-0 group-hover:opacity-100 transition-opacity
        pointer-events-none
      ">
        Chat with Oi [BRAIN]
      </span>
    </motion.button>
  );
};

export default OiChatPanel;
